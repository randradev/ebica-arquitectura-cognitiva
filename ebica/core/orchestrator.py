"""
CognitiveOrchestrator, parte de Fase 1, CP4 (documento base §5.14, §6.1).

El bucle rápido: mientras la entidad está cargada, cada ~1 s avanza los drives
y el afecto según el tiempo real transcurrido, sin usar el LLM. El estado vive
en memoria y se actualiza en cada tick; lo que se muestrea es solo el reporte
(eventos y guardado en disco, D1-17), así que la entidad no reacciona con
retraso.

Al despertar (cargar), aplica el tiempo que estuvo descargada (D1-7).

La cola de GPU y el turno con appraisal llegan en CP5; la máquina de modos y
el reloj simulado, en Fase 2. Aquí el reloj solo es inyectable (`now`), para
probar con tiempo falso.
"""

import asyncio
import contextlib
from collections.abc import Callable
from datetime import datetime, timezone

from ebica.affect.drives import DriveDynamics, advance_drives, crossed_thresholds, valence_coupling
from ebica.affect.vad import VAD, AffectDynamics, apply_impulse, decay
from ebica.core.events import Event, EventBus
from ebica.core.state import EntityState
from ebica.entities.manager import Entity
from ebica.identity.traits import derive_parameters

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
    ) -> None:
        """
        Prepara la dinámica con los parámetros que derivan de los rasgos.

        `save_state` persiste el estado (lo da el EntityManager); `now` y
        `tick_seconds` se reemplazan en las pruebas.
        """
        self.entity = entity
        self.bus = bus
        self.now = now
        self.tick_seconds = tick_seconds
        self._save_state = save_state
        parameters = derive_parameters(entity.config.traits)
        self.affect_dynamics = AffectDynamics.from_parameters(parameters)
        self.drive_dynamics = DriveDynamics.from_parameters(parameters)
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

    def _report_affect(self, now: datetime, source: str, extra: dict | None = None) -> Event:
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
        return self.bus.emit(self.entity_id, "affect.updated", payload)

    def _report_periodic(self, now: datetime) -> None:
        """Emite `drive.updated` y `tick` (el resumen muestreado del bucle rápido, §6.1)."""
        self._last_periodic_at = now
        self.bus.emit(self.entity_id, "drive.updated", dict(self.state.drives))
        self.bus.emit(self.entity_id, "tick", {"ticks": self._ticks})
