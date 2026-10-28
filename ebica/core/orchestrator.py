"""
CognitiveOrchestrator, parte de Fase 1, CP4 (documento base §5.14, §6.1).

El bucle rápido: mientras la entidad está cargada, cada ~1 s avanza los drives
y el afecto según el tiempo real transcurrido, sin usar el LLM. El estado vive
en memoria y se actualiza en cada tick; lo que se muestrea es solo el reporte
(eventos y guardado en disco, D1-17), así que la entidad no reacciona con
retraso.

Al despertar (cargar), aplica el tiempo que estuvo descargada (D1-7).

El turno del usuario (CP5, §6.2 sin las etapas de fases posteriores) también
vive aquí: percepción → appraisal → impulsos y drives → prompt → respuesta.
La API solo transporta. Antes del appraisal corre la vía baja (CP5 B1–B2):
si se dispara, la entidad responde en el impulso y el appraisal llega después.
Toda llamada al LLM pasa por la cola de GPU. Antes de responder, la vía alta
recupera recuerdos (CP7, §7.3); tras responder, el turno se escribe en la
memoria episódica (CP6, D1-37). La máquina de modos y el reloj
simulado llegan en Fase 2. El reloj solo es
inyectable (`now`), para probar con tiempo falso.
"""

import asyncio
import contextlib
import dataclasses
import time
from collections.abc import AsyncIterator, Callable
from contextlib import aclosing
from datetime import datetime, timezone

from ebica.affect.appraisal_effects import (
    affect_impulse,
    apply_coherence_rules,
    dialogue_temperature,
    discount_alarm,
    drive_relief,
)
from ebica.affect.drives import DriveDynamics, advance_drives, crossed_thresholds, valence_coupling
from ebica.affect.low_road import ALARM_AROUSAL, LowRoadResult
from ebica.affect.low_road import evaluate as evaluate_low_road
from ebica.affect.vad import VAD, AffectDynamics, apply_impulse, decay
from ebica.core.events import Event, EventBus
from ebica.core.gpu_queue import GpuPriority, GpuQueue
from ebica.core.state import ConversationTurn, EntityState
from ebica.entities.manager import Entity
from ebica.identity.traits import derive_parameters
from ebica.llm.client import LLMClient, LLMError, LLMResult
from ebica.llm.prompt_assembler import (
    build_dialogue_messages,
    build_impulsive_messages,
    build_memory_sections,
)
from ebica.llm.refusal import BUFFER_CHARS, choose_prefix, detect_refusal, join_prefill, with_prefill
from ebica.memory.episodes import MemoryWriter, normalize_topics
from ebica.memory.retrieval import MemoryRetriever, RetrievalResult
from ebica.perception.appraisal import (
    Appraisal,
    AppraisalError,
    appraisal_json_schema,
    build_appraisal_messages,
    neutral_appraisal,
    parse_appraisal,
)

# CONSTANTE: intercambios recientes que entran al prompt (D1-24).
RECENT_TURNS = 6
# Esquema JSON que restringe la salida del appraisal (D1-19); se calcula una vez.
APPRAISAL_SCHEMA = appraisal_json_schema()

# CONSTANTE: intervalo del bucle rápido (§6.1, ≈1 Hz).
TICK_SECONDS = 1.0
# CONSTANTE: cambio mínimo del VAD que se reporta de inmediato (D1-17).
AFFECT_REPORT_DELTA = 0.01
# CONSTANTE: cada cuánto se reportan afecto, drives y `tick`, y se guarda el
# estado, aunque no haya cambios (D1-17).
REPORT_INTERVAL_SECONDS = 60.0
# CONSTANTE: tamaño de los tramos con que se aplica el tiempo descargada
# (D1-7). Cada tramo usa la forma cerrada; los tramos solo permiten que el
# acople drive → valencia se reparta a lo largo de la ausencia.
CATCH_UP_STEP_SECONDS = 60.0


def _utc_now() -> datetime:
    """Hora actual con zona horaria UTC (el reloj por defecto)."""
    return datetime.now(timezone.utc)


class Orchestrator:
    """Hace vivir la dinámica de una entidad cargada: un tick por segundo."""

    def __init__(
        self,
        entity: Entity,
        bus: EventBus,
        save_state: Callable[[EntityState], None],
        now: Callable[[], datetime] = _utc_now,
        tick_seconds: float = TICK_SECONDS,
        llm: LLMClient | None = None,
        gpu: GpuQueue | None = None,
        memory: MemoryWriter | None = None,
        retriever: MemoryRetriever | None = None,
    ) -> None:
        """
        Prepara la dinámica con los parámetros que derivan de los rasgos.

        `save_state` persiste el estado (lo da el EntityManager); `llm` es
        necesario para los turnos; `gpu` es la cola compartida del motor (si
        falta, se crea una propia); `memory` escribe cada turno en Neo4j (CP6; sin
        ella, la entidad no guarda episodios); `retriever` recupera recuerdos
        (CP7; usa el embedder de `memory`, así que solo funciona junto a ella); `now` y
        `tick_seconds` se reemplazan en las pruebas.
        """
        self.entity = entity
        self.bus = bus
        self.now = now
        self.tick_seconds = tick_seconds
        self.llm = llm
        self.gpu = gpu or GpuQueue(bus)
        self.memory = memory
        self.retriever = retriever
        # Los hechos esenciales ya van en «Quién soy»: no se recuperan (D1-46).
        self.core_fact_ids = [fact.id for fact in entity.config.seed_biography.core_facts]
        self._save_state = save_state
        self.parameters = derive_parameters(entity.config.traits)
        self.affect_dynamics = AffectDynamics.from_parameters(self.parameters)
        self.drive_dynamics = DriveDynamics.from_parameters(self.parameters)
        # Un turno a la vez: dos consolas escribiendo a la vez no deben
        # intercalar sus etapas. La cola de GPU ordena las llamadas al LLM;
        # este lock ordena los turnos (D1-32).
        self._turn_lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._ticks = 0
        self._last_affect_report: VAD | None = None
        self._last_affect_report_at: datetime | None = None
        self._last_periodic_at: datetime | None = None

    @property
    def entity_id(self) -> str:
        """Id de la entidad que mueve este orquestador."""
        return self.entity.config.id

    @property
    def state(self) -> EntityState:
        """Estado vivo de la entidad (se modifica en cada tick)."""
        return self.entity.state

    # ------------------------------------------------------------ ciclo de vida

    def wake(self) -> None:
        """
        Despierta a la entidad: inicializa el ánimo si es nuevo y aplica el
        tiempo transcurrido desde el último tick como tiempo descargada (D1-7).

        Emite `affect.updated` con `source: "wake"` y los segundos aplicados.
        """
        now = self.now()
        state = self.state
        if state.affect is None:
            state.affect = self.affect_dynamics.attractor
        elapsed = 0.0
        if state.last_tick_at is not None:
            elapsed = max(0.0, (now - state.last_tick_at).total_seconds())
            remaining = elapsed
            while remaining > 0:
                step = min(CATCH_UP_STEP_SECONDS, remaining)
                self._advance(step, awake=False)
                remaining -= step
        state.last_tick_at = now
        self._report_affect(now, "wake", {"elapsed_seconds": elapsed})
        self._report_periodic(now)
        self._save_state(state)

    def start(self) -> None:
        """Despierta a la entidad y lanza el bucle rápido como tarea asyncio."""
        self.wake()
        self._task = asyncio.create_task(self._run(), name=f"fast-loop:{self.entity_id}")

    async def stop(self) -> None:
        """Detiene el bucle, aplica el último tramo de tiempo y guarda el estado."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self.tick()
        self._save_state(self.state)

    async def _run(self) -> None:
        """Bucle rápido: un tick cada `tick_seconds` hasta que lo cancelen."""
        while True:
            await asyncio.sleep(self.tick_seconds)
            self.tick()

    # ------------------------------------------------------------ dinámica

    def tick(self) -> None:
        """
        Avanza la dinámica desde el último tick hasta ahora y reporta lo que toque.

        Usa el tiempo real transcurrido (no cuenta ticks): si uno se atrasa, el
        resultado no cambia, porque las fórmulas son exactas para cualquier `dt`.
        """
        now = self.now()
        state = self.state
        dt = max(0.0, (now - state.last_tick_at).total_seconds()) if state.last_tick_at else 0.0
        self._advance(dt, awake=True)
        state.last_tick_at = now
        self._ticks += 1
        changed = self._last_affect_report is None or (
            state.affect.max_difference(self._last_affect_report) >= AFFECT_REPORT_DELTA
        )
        if changed or self._due(self._last_affect_report_at, now):
            self._report_affect(now, "tick")
        if self._due(self._last_periodic_at, now):
            self._report_periodic(now)
            self._save_state(state)

    def inject(self, valence: float = 0.0, arousal: float = 0.0, dominance: float = 0.0) -> Event:
        """
        Aplica un impulso manual al VAD (herramienta de desarrollador, D1-18).

        Primero se pone al día la dinámica, para que el impulso caiga sobre el
        ánimo actual. Se reporta de inmediato con `source: "manual"`, para
        distinguirlo de una vivencia.
        """
        self.tick()
        self.state.affect = apply_impulse(self.state.affect, valence, arousal, dominance)
        impulse = {"valence": valence, "arousal": arousal, "dominance": dominance}
        return self._report_affect(self.now(), "manual", {"impulse": impulse})

    def _advance(self, dt_seconds: float, awake: bool) -> None:
        """
        Un paso de dinámica: drives, regreso al reposo y acople drive → valencia.

        Emite `drive.threshold_crossed` si un drive cruza el umbral.
        """
        state = self.state
        before = state.drives
        after = advance_drives(before, self.drive_dynamics, dt_seconds, awake)
        affect = decay(state.affect, self.affect_dynamics, dt_seconds)
        state.affect = apply_impulse(affect, valence=valence_coupling(before, after))
        state.drives = after
        for name, direction in crossed_thresholds(before, after):
            self.bus.emit(
                self.entity_id, "drive.threshold_crossed",
                {"drive": name, "direction": direction, "level": after[name], "awake": awake},
            )

    # ------------------------------------------------------------ reporte

    @staticmethod
    def _due(last: datetime | None, now: datetime) -> bool:
        """True si pasó el intervalo de reporte desde `last` (o si nunca se reportó)."""
        return last is None or (now - last).total_seconds() >= REPORT_INTERVAL_SECONDS

    def _report_affect(
        self, now: datetime, source: str, extra: dict | None = None, cause_id: str | None = None
    ) -> Event:
        """Emite `affect.updated` con el VAD actual y el reposo, para la consola."""
        affect = self.state.affect
        self._last_affect_report = affect
        self._last_affect_report_at = now
        payload = {
            **affect.model_dump(),
            "attractor": self.affect_dynamics.attractor.model_dump(),
            "source": source,
            **(extra or {}),
        }
        return self.bus.emit(self.entity_id, "affect.updated", payload, cause_id=cause_id)

    def _report_periodic(self, now: datetime) -> None:
        """Emite `drive.updated` y `tick` (el resumen muestreado del bucle rápido, §6.1)."""
        self._last_periodic_at = now
        self.bus.emit(self.entity_id, "drive.updated", dict(self.state.drives))
        self.bus.emit(self.entity_id, "tick", {"ticks": self._ticks})

    # ------------------------------------------------------------ turno (CP5)

    async def user_turn(self, text: str) -> AsyncIterator[str]:
        """
        Procesa un mensaje del usuario y entrega la respuesta fragmento a fragmento.

        Primero corre la vía baja (CPU, milisegundos). Si no se dispara, sigue
        el turno normal de §6.2 (`_normal_turn`); si se dispara, la ruta
        impulsiva (`_impulsive_turn`). Al terminar, guarda el intercambio y
        lo escribe en la memoria (`memory.written`) y emite `turn.completed` con
        el resumen para la consola. Cada evento se encadena por `cause_id` con
        el que lo provocó.

        Si quien consume deja de leer, cerrar este iterador cierra el streaming
        del LLM (`llm.cancelled`) y el intercambio no se guarda.
        """
        if self.llm is None:
            raise RuntimeError("El orquestador no tiene cliente LLM: no puede procesar turnos")
        async with self._turn_lock:
            started = time.perf_counter()
            perception = self.bus.emit(self.entity_id, "perception.input", {"text": text, "source": "user"})
            low_road = evaluate_low_road(text, self.parameters.theta_low_road)
            low_road_ms = (time.perf_counter() - started) * 1000
            # Cada ruta deja aquí lo que `turn.completed` necesita.
            summary: dict = {}
            if low_road.triggered:
                turn = self._impulsive_turn(text, perception.id, low_road, summary)
            else:
                turn = self._normal_turn(text, perception.id, summary)
            async with aclosing(turn) as pieces:
                async for piece in pieces:
                    yield piece

            result: LLMResult = summary["result"]
            self._remember_turn(text, result.text)
            memory_started = time.perf_counter()
            memory_event = await self._write_memory(text, result.text, low_road.triggered, summary)
            memory_s = time.perf_counter() - memory_started
            self.bus.emit(
                self.entity_id, "turn.completed",
                {
                    "impulsive": low_road.triggered,
                    "low_road": low_road.as_dict(),
                    "appraisal": summary["appraisal"].model_dump(),
                    "corrections": summary["corrections"],
                    "affect_after": summary["affect_event"].payload,
                    "temperature": summary["temperature"],
                    "refusals": summary["refusals"],
                    # Lo recordado (episodios, hechos, desglose) o el error; None
                    # sin memoria o en la ruta impulsiva, que no recupera (§5.4).
                    "retrieval": summary.get("retrieval"),
                    # None si la memoria está desactivada; si no, lo escrito o el error.
                    "memory": memory_event.payload if memory_event else None,
                    "latency": {
                        "low_road_ms": low_road_ms,
                        "appraisal_s": summary["appraisal_s"],
                        "retrieval_ms": summary.get("retrieval_ms"),
                        "first_token_s": result.first_token_s,
                        "response_s": result.total_s,
                        "memory_s": memory_s if memory_event else None,
                        "total_s": time.perf_counter() - started,
                    },
                },
                cause_id=memory_event.id if memory_event else summary["completed_cause_id"],
            )
            self._save_state(self.state)

    async def _normal_turn(self, text: str, perception_id: str, summary: dict) -> AsyncIterator[str]:
        """
        Vía alta (§6.2): appraisal (con la regla del sarcasmo) → impulsos y
        alivio de drives → recuerdos con el ánimo ya actualizado (CP7) →
        respuesta `dialogue` con la temperatura del ánimo.

        El embedding del mensaje se calcula en paralelo con el appraisal (D1-49):
        la CPU trabaja mientras la GPU evalúa, así la recuperación casi no
        retrasa el primer token.
        """
        retrieving = self.retriever is not None and self.memory is not None
        query = asyncio.create_task(self._embed_query(text)) if retrieving else None
        try:
            appraisal_started = time.perf_counter()
            appraisal, corrections, appraisal_event = await self._appraise(text, perception_id)
            summary["appraisal_s"] = time.perf_counter() - appraisal_started
            affect_event = self.apply_appraisal(appraisal, corrections, cause_id=appraisal_event.id)
            retrieval, retrieval_event = await self._retrieve(query, appraisal, cause_id=affect_event.id)
        finally:
            if query is not None and not query.done():
                query.cancel()
        summary.update(
            retrieval=retrieval_event.payload if retrieval_event else None,
            retrieval_ms=retrieval.elapsed_ms if retrieval else None,
        )

        state = self.state
        temperature = dialogue_temperature(state.affect)
        messages = build_dialogue_messages(
            self.entity.config, text, state.affect, state.drives, state.recent_turns,
            memories=build_memory_sections(retrieval, self.now()),
        )
        result = LLMResult()
        refusals: list[dict] = []
        response = self._respond(
            messages, "dialogue", GpuPriority.RESPONSE,
            retrieval_event.id if retrieval_event else affect_event.id, result, refusals, temperature,
        )
        async with aclosing(response) as pieces:
            async for piece in pieces:
                yield piece
        summary.update(
            appraisal=appraisal, corrections=corrections, affect_event=affect_event,
            temperature=temperature, result=result, refusals=refusals,
            completed_cause_id=result.response_event_id,
        )

    async def _embed_query(self, text: str) -> tuple[list[float], float]:
        """Embedding del mensaje para buscar recuerdos; devuelve el vector y los ms que tardó."""
        started = time.perf_counter()
        [vector] = await self.memory.embedder.embed([text], "query")
        return vector, (time.perf_counter() - started) * 1000

    async def _retrieve(
        self, query: asyncio.Task | None, appraisal: Appraisal, cause_id: str
    ) -> tuple[RetrievalResult | None, Event | None]:
        """
        Recupera recuerdos y hechos con el ánimo actual (§6.2, etapa 4; §7.3).

        Excluye los intercambios que ya están literales en la conversación
        reciente y los hechos esenciales (D1-46). Emite `memory.retrieved`; si
        Neo4j o el embedder fallan, `memory.retrieve_failed` y el turno sigue
        sin recuerdos (D1-49). Devuelve (None, None) si no hay recuperador.
        """
        if query is None:
            return None, None
        state = self.state
        try:
            vector, embed_ms = await query
            result = await self.retriever.retrieve(
                self.entity_id, vector, affect=state.affect, k=self.parameters.k_retrieval,
                lambda_mmr=self.parameters.lambda_mmr, now=self.now(),
                topics=normalize_topics(appraisal.topics),
                since=state.recent_turns[0].ts if state.recent_turns else None,
                excluded_fact_ids=self.core_fact_ids,
            )
        except Exception as error:  # noqa: BLE001 — cualquier fallo de Neo4j o del embedder
            event = self.bus.emit(
                self.entity_id, "memory.retrieve_failed",
                {"error": f"{type(error).__name__}: {error}"}, cause_id=cause_id,
            )
            return None, event
        event = self.bus.emit(
            self.entity_id, "memory.retrieved", result.as_dict() | {"embed_ms": round(embed_ms, 1)},
            cause_id=cause_id,
        )
        return result, event

    async def _impulsive_turn(
        self, text: str, perception_id: str, low_road: LowRoadResult, summary: dict
    ) -> AsyncIterator[str]:
        """
        Vía baja (§5.4; D1-22, D1-29 a D1-31): alarma → respuesta impulsiva → appraisal.

        La alarma sube la alerta de inmediato (+0,35) y la entidad responde en
        el impulso, con contexto mínimo. Después, dentro del mismo turno, corre
        el appraisal: pone la valencia y suma solo la alerta que exceda la de
        la alarma (D1-30). No genera otro mensaje: lo que la entidad haga con
        su reacción se verá en el turno siguiente.
        """
        triggered = self.bus.emit(
            self.entity_id, "affect.low_road_triggered", low_road.as_dict(), cause_id=perception_id
        )
        self.tick()
        self.state.affect = apply_impulse(self.state.affect, arousal=ALARM_AROUSAL)
        alarm = self._report_affect(
            self.now(), "low_road", {"impulse": {"arousal": ALARM_AROUSAL}}, cause_id=triggered.id
        )

        state = self.state
        messages = build_impulsive_messages(
            self.entity.config, text, state.affect, state.drives, state.recent_turns
        )
        result = LLMResult()
        refusals: list[dict] = []
        response = self._respond(messages, "impulsive", GpuPriority.IMPULSIVE, alarm.id, result, refusals)
        async with aclosing(response) as pieces:
            async for piece in pieces:
                yield piece

        appraisal_started = time.perf_counter()
        appraisal, corrections, appraisal_event = await self._appraise(text, perception_id)
        summary["appraisal_s"] = time.perf_counter() - appraisal_started
        affect_event = self.apply_appraisal(
            appraisal, corrections, cause_id=appraisal_event.id, alarm_arousal=ALARM_AROUSAL
        )
        summary.update(
            appraisal=appraisal, corrections=corrections, affect_event=affect_event,
            temperature=None, result=result, refusals=refusals, completed_cause_id=affect_event.id,
        )

    async def _respond(
        self,
        messages: list[dict[str, str]],
        preset: str,
        priority: GpuPriority,
        cause_id: str,
        result: LLMResult,
        refusals: list[dict],
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """
        Genera la respuesta y la entrega fragmento a fragmento, sin rechazos de asistente (D1-33).

        Retiene los primeros `BUFFER_CHARS` caracteres antes de mostrarlos. Si
        son un rechazo de asistente («Lo siento, pero no puedo…»), corta esa
        generación, emite `llm.refusal` y regenera una sola vez con prefill:
        la respuesta empieza con una muletilla neutra («Mmm,», «Eh,»…) que el
        modelo continúa. Si la regeneración también rechaza, se
        entrega igual (sin más intentos) y se emite otro `llm.refusal` con
        `action: "kept"`. Cada rechazo detectado se agrega a `refusals`.
        """
        # Fragmentos retenidos: se sueltan tal cual llegaron, así la consola ve el streaming normal.
        held: list[str] = []
        shown = False
        response = self._generate(messages, preset, priority, cause_id, result, temperature)
        async with aclosing(response) as pieces:
            async for piece in pieces:
                if shown:
                    yield piece
                    continue
                held.append(piece)
                if sum(len(p) for p in held) >= BUFFER_CHARS:
                    if detect_refusal("".join(held)):
                        break
                    shown = True
                    for kept_piece in held:
                        yield kept_piece
        buffer = "".join(held)
        patterns = [] if shown else detect_refusal(buffer)
        if not patterns:
            if not shown:
                for kept_piece in held:  # respuesta más corta que la retención
                    yield kept_piece
            return

        prefix = choose_prefix()
        refusal = self.bus.emit(
            self.entity_id, "llm.refusal",
            {"preset": preset, "text": buffer, "patterns": patterns, "action": "regenerate", "prefix": prefix},
            cause_id=result.request_event_id,
        )
        refusals.append(refusal.payload)
        # La regeneración reemplaza al intento cortado: sus métricas y su texto son los del turno.
        for item in dataclasses.fields(LLMResult):
            setattr(result, item.name, getattr(LLMResult(), item.name))
        response = self._generate(
            with_prefill(messages, prefix), preset, priority, refusal.id, result, temperature
        )
        started = False
        async with aclosing(response) as pieces:
            async for piece in pieces:
                if not started:
                    # El servidor devuelve solo la continuación: el prefijo se muestra con el primer fragmento.
                    piece = join_prefill(prefix, piece)
                    started = True
                yield piece
        if not started:
            yield prefix
        continuation = result.text
        # Lo guardado y lo que ve la persona incluyen el prefijo (`llm.response` lleva solo la continuación).
        result.text = join_prefill(prefix, continuation)
        patterns = detect_refusal(continuation[:BUFFER_CHARS])
        if patterns:
            kept = self.bus.emit(
                self.entity_id, "llm.refusal",
                {"preset": preset, "text": result.text, "patterns": patterns, "action": "kept", "prefix": prefix},
                cause_id=result.request_event_id,
            )
            refusals.append(kept.payload)

    async def _generate(
        self,
        messages: list[dict[str, str]],
        preset: str,
        priority: GpuPriority,
        cause_id: str,
        result: LLMResult,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """Una generación en streaming a través de la cola de GPU."""
        stream = self.gpu.stream(
            priority, preset, self.entity_id,
            lambda: self.llm.stream(
                messages, entity_id=self.entity_id, preset=preset,
                cause_id=cause_id, temperature=temperature, result=result,
            ),
            cause_id=cause_id,
        )
        async with aclosing(stream) as pieces:
            async for piece in pieces:
                yield piece

    async def _appraise(self, text: str, cause_id: str) -> tuple[Appraisal, list[str], Event]:
        """
        Pide el appraisal al LLM (D1-19: salida restringida al esquema) y aplica
        las reglas de coherencia (D1-20).

        Si el LLM falla o la salida no cumple el esquema, emite
        `appraisal.invalid` y sigue con un appraisal neutro: el turno no se rompe.
        """
        config = self.entity.config
        profile = config.appraisal_profile or config.description
        messages = build_appraisal_messages(config.name, profile, text)
        try:
            result = await self.gpu.run(
                GpuPriority.APPRAISAL, "appraisal", self.entity_id,
                lambda: self.llm.complete(
                    messages, entity_id=self.entity_id, preset="appraisal", cause_id=cause_id,
                    response_schema=APPRAISAL_SCHEMA,
                ),
                cause_id=cause_id,
            )
            appraisal = parse_appraisal(result.text)
        except (LLMError, AppraisalError) as error:
            event = self.bus.emit(
                self.entity_id, "appraisal.invalid", {"error": str(error)}, cause_id=cause_id
            )
            return neutral_appraisal(), [], event
        appraisal, corrections = apply_coherence_rules(appraisal)
        event = self.bus.emit(
            self.entity_id, "appraisal.completed",
            {"appraisal": appraisal.model_dump(), "corrections": corrections},
            cause_id=result.response_event_id,
        )
        return appraisal, corrections, event

    def apply_appraisal(
        self,
        appraisal: Appraisal,
        corrections: list[str] | None = None,
        cause_id: str | None = None,
        alarm_arousal: float = 0.0,
    ) -> Event:
        """
        Aplica los efectos de un appraisal: impulso al VAD y alivio de drives (§6.2, etapa 3).

        El alivio de los drives produce placer por el acople de CP4 (−Σ w·Δe),
        que se suma al impulso. `alarm_arousal` es la alerta que ya sumó la vía
        baja en este turno y se descuenta (D1-30). Emite `affect.updated`
        (`source: "appraisal"`, con el desglose) y `drive.updated`, y devuelve el primero.
        """
        self.tick()
        state = self.state
        impulse = affect_impulse(appraisal, state.affect, self.parameters)
        if alarm_arousal:
            impulse = discount_alarm(impulse, alarm_arousal)
        relief = drive_relief(appraisal)
        before = state.drives
        after = {name: max(0.0, level - relief[name]) for name, level in before.items()}
        from_drives = valence_coupling(before, after)
        state.drives = after
        state.affect = apply_impulse(
            state.affect, impulse.valence + from_drives, impulse.arousal, impulse.dominance
        )
        for name, direction in crossed_thresholds(before, after):
            self.bus.emit(
                self.entity_id, "drive.threshold_crossed",
                {"drive": name, "direction": direction, "level": after[name], "awake": True},
                cause_id=cause_id,
            )
        event = self._report_affect(
            self.now(), "appraisal",
            {
                "impulse": impulse.as_dict(),
                "drive_relief": relief,
                "valence_from_drives": from_drives,
                "alarm_arousal_discounted": alarm_arousal,
                "corrections": corrections or [],
            },
            cause_id=cause_id,
        )
        self.bus.emit(self.entity_id, "drive.updated", dict(after), cause_id=event.id)
        return event

    async def _write_memory(
        self, user_text: str, entity_text: str, impulsive: bool, summary: dict
    ) -> Event | None:
        """
        Escribe el episodio y la huella del turno (§6.2, post-turno; D1-37).

        Corre después de la respuesta, así que no retrasa el primer token, y
        antes de `turn.completed`, así que el turno siguiente ya lo encuentra.
        Emite `memory.written` o, si Neo4j o el embedder fallan,
        `memory.write_failed`: un recuerdo perdido no debe romper la
        conversación, que ya ocurrió y sigue en la conversación reciente.
        Devuelve el evento emitido, o None si no hay memoria.
        """
        if self.memory is None:
            return None
        try:
            written = await self.memory.write_turn(
                self.entity_id, ts=self.now(), user_text=user_text, entity_text=entity_text,
                affect=self.state.affect, appraisal=summary["appraisal"], impulsive=impulsive,
            )
        except Exception as error:  # noqa: BLE001 — cualquier fallo de Neo4j o del embedder
            return self.bus.emit(
                self.entity_id, "memory.write_failed",
                {"error": f"{type(error).__name__}: {error}"},
                cause_id=summary["completed_cause_id"],
            )
        return self.bus.emit(
            self.entity_id, "memory.written", written.as_dict(), cause_id=summary["completed_cause_id"]
        )

    def _remember_turn(self, user_text: str, entity_text: str) -> None:
        """Guarda el intercambio y conserva solo los últimos `RECENT_TURNS` (D1-24)."""
        turns = [*self.state.recent_turns, ConversationTurn(user=user_text, entity=entity_text, ts=self.now())]
        self.state.recent_turns = turns[-RECENT_TURNS:]
