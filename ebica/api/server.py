"""
Servidor HTTP + WebSocket del motor (documento base §8.3).

- `GET/POST /api/entities`, `POST /api/entities/{id}/load`: crear, listar y cargar.
- `POST /api/affect/impulse`: inyectar afecto a mano (herramienta de desarrollador, D1-18).
- `WS /ws/chat`: chat con la entidad activa; la respuesta llega en streaming.
- `WS /ws/events?history=N`: los últimos N eventos del día de la entidad activa
  y después todos los eventos del bus en vivo, para la consola.

El servidor solo expone API; la consola (`console/`) corre aparte con Vite.
Hay una sola entidad activa a la vez (§4.2, restricción de GPU); mientras está
cargada, su bucle rápido (el orquestador) corre en segundo plano.

Memoria (CP6, D1-38): `create_app_from_env` (la que usa `python -m ebica.api`)
carga el embedder y aplica el esquema de Neo4j al arrancar; si algo falla, el
servidor no arranca, para no creer que hay memoria cuando no la hay. Con
`EBICA_MEMORY=off` arranca sin memoria a propósito (sin los ~2–3 GB de
bge-m3). Al cargar una entidad se importa su biografía semilla.
"""

import logging
import os
import time
from contextlib import aclosing, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi import Path as PathParam
from pydantic import BaseModel, Field

from ebica.core.events import ENTITY_ID_PATTERN, EventBus, JsonlEventLog
from ebica.core.gpu_queue import GpuQueue
from ebica.core.orchestrator import Orchestrator
from ebica.core.state import EntityConfig
from ebica.entities.manager import Entity, EntityConfigError, EntityManager
from ebica.llm.client import LLMClient, LLMError
from ebica.memory.episodes import MemoryWriter
from ebica.memory.graph import GraphStore
from ebica.memory.retrieval import MemoryRetriever
from ebica.perception.embeddings import SentenceTransformerEmbedder

# CONSTANTE: máximo de eventos de historial que se envían al conectar.
MAX_HISTORY_EVENTS = 500
# Valor de `EBICA_MEMORY` que arranca el servidor sin memoria (D1-38).
MEMORY_OFF = "off"

logger = logging.getLogger("uvicorn.error")


class MemoryUnavailableError(RuntimeError):
    """Neo4j o el embedder no están disponibles: la memoria no puede usarse."""


async def load_memory_from_env() -> MemoryWriter:
    """
    Prepara la memoria: conecta a Neo4j, carga el embedder y aplica el esquema.

    Lanza `MemoryUnavailableError` con la causa si algo falla (D1-38: el
    servidor no arranca). El tiempo total queda en el log.
    """
    started = time.perf_counter()
    try:
        graph = GraphStore.from_env()
        await graph.verify()
    except Exception as error:
        raise MemoryUnavailableError(
            f"Neo4j no disponible ({error}). ¿Está levantado el contenedor ebica-neo4j? "
            f"Para arrancar sin memoria: EBICA_MEMORY={MEMORY_OFF}"
        ) from error
    try:
        embedder = await SentenceTransformerEmbedder.load()
        await graph.apply_schema(embedder.dimension)
    except Exception as error:
        await graph.close()
        raise MemoryUnavailableError(f"No se pudo preparar la memoria: {error}") from error
    logger.info(
        "Memoria lista: %s (%d dimensiones, carga del modelo %.1f s); esquema aplicado; total %.1f s",
        embedder.model_name, embedder.dimension, embedder.load_seconds, time.perf_counter() - started,
    )
    return MemoryWriter(graph, embedder)


@dataclass
class Engine:
    """Los componentes compartidos del motor durante la vida del servidor."""

    bus: EventBus
    log: JsonlEventLog
    manager: EntityManager
    llm: LLMClient
    # Una sola cola para todo el motor: hay una sola GPU (§5.14).
    gpu: GpuQueue
    # None si el servidor corre sin memoria (EBICA_MEMORY=off o pruebas).
    memory: MemoryWriter | None = None
    active: Entity | None = None
    orchestrator: Orchestrator | None = None

    async def activate(self, entity: Entity) -> None:
        """
        Deja `entity` como la activa: importa su biografía semilla a la
        memoria, detiene el bucle rápido de la anterior (que guarda su estado)
        y arranca el de la nueva.

        La semilla se importa primero: si Neo4j falla, la excepción sube y la
        entidad anterior sigue activa. La importación es idempotente, así que
        cargar muchas veces solo cuesta una consulta (D1-39).
        """
        if self.memory is not None:
            config = entity.config
            report = await self.memory.import_seed(config.id, config.name, config.seed_biography)
            self.bus.emit(config.id, "memory.seed_imported", report.as_dict())
        await self.deactivate()
        self.active = entity
        retriever = MemoryRetriever(self.memory.graph) if self.memory is not None else None
        self.orchestrator = Orchestrator(
            entity, self.bus, self.manager.save_state, llm=self.llm, gpu=self.gpu,
            memory=self.memory, retriever=retriever,
        )
        self.orchestrator.start()

    async def deactivate(self) -> None:
        """Detiene el bucle rápido de la entidad activa, si hay una."""
        if self.orchestrator is not None:
            await self.orchestrator.stop()
            self.orchestrator = None


class Impulse(BaseModel):
    """Impulso manual al VAD; cada dimensión entre −1 y 1 (luego se recorta a su rango)."""

    valence: float = Field(0.0, ge=-1.0, le=1.0)
    arousal: float = Field(0.0, ge=-1.0, le=1.0)
    dominance: float = Field(0.0, ge=-1.0, le=1.0)


def entity_summary(entity: Entity) -> dict:
    """Representación JSON de una entidad para la consola."""
    return {"config": entity.config.model_dump(), "state": entity.state.model_dump(mode="json")}


def create_app(
    entities_dir: Path | None = None,
    llm_transport: httpx.AsyncBaseTransport | None = None,
    memory: MemoryWriter | None = None,
    load_memory: bool = False,
) -> FastAPI:
    """
    Construye la aplicación con sus dependencias.

    Sin argumentos usa `EBICA_ENTITIES_DIR` y el LLM configurado en el
    entorno, y no tiene memoria. Las pruebas pasan una carpeta temporal, un
    servidor LLM simulado y, si la necesitan, una memoria (`memory`). Con
    `load_memory`, la memoria se prepara al arrancar desde el entorno, salvo
    con `EBICA_MEMORY=off`.
    """
    base_dir = Path(entities_dir or os.environ.get("EBICA_ENTITIES_DIR", "entities"))
    log = JsonlEventLog(base_dir)
    bus = EventBus(log)
    engine = Engine(
        bus=bus,
        log=log,
        manager=EntityManager(base_dir, bus),
        llm=LLMClient.from_env(bus, transport=llm_transport),
        gpu=GpuQueue(bus),
        memory=memory,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """
        Al arrancar, prepara la memoria si se pidió (si falla, el servidor no
        arranca). Al apagar: detiene el bucle rápido (guarda el estado) y
        cierra el cliente LLM y Neo4j.
        """
        # Solo se cierra la memoria que se cargó aquí; una inyectada la cierra quien la creó.
        loaded: MemoryWriter | None = None
        if load_memory:
            if os.environ.get("EBICA_MEMORY", "").strip().lower() == MEMORY_OFF:
                logger.warning("Memoria desactivada (EBICA_MEMORY=off): los turnos no se guardan en Neo4j")
            else:
                loaded = engine.memory = await load_memory_from_env()
        yield
        await engine.deactivate()
        await engine.llm.aclose()
        if loaded is not None:
            await loaded.graph.close()

    app = FastAPI(title="EBICA", lifespan=lifespan)
    app.state.engine = engine

    @app.get("/api/entities")
    async def list_entities() -> dict:
        """Lista las entidades disponibles y cuál está activa (con su nombre, para el chat)."""
        active = engine.active.config if engine.active else None
        return {
            "ids": engine.manager.list_ids(),
            "active": active.id if active else None,
            "active_name": active.name if active else None,
        }

    @app.post("/api/entities", status_code=201)
    async def create_entity(config: EntityConfig) -> dict:
        """Crea una entidad nueva (409 si el id ya existe)."""
        try:
            entity = engine.manager.create(config)
        except FileExistsError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return entity_summary(entity)

    @app.post("/api/entities/{entity_id}/load")
    async def load_entity(entity_id: str = PathParam(pattern=ENTITY_ID_PATTERN)) -> dict:
        """Carga una entidad y la deja activa (404 si no existe, 422 si su config es inválida)."""
        if entity_id not in engine.manager.list_ids():
            raise HTTPException(status_code=404, detail=f"No existe la entidad '{entity_id}'")
        try:
            entity = engine.manager.load(entity_id)
        except EntityConfigError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        try:
            await engine.activate(entity)
        except Exception as error:  # noqa: BLE001 — la importación de la semilla (Neo4j, embedder)
            raise HTTPException(
                status_code=503, detail=f"No se pudo importar la semilla a la memoria: {error}"
            ) from error
        return entity_summary(engine.active)

    @app.get("/api/conversation")
    async def conversation() -> dict:
        """
        Los últimos intercambios guardados de la entidad activa (D1-24), para que
        la consola muestre la conversación al recargar o al cambiar de entidad.
        Sin entidad cargada devuelve una lista vacía.
        """
        if engine.active is None:
            return {"entity_id": None, "turns": []}
        turns = engine.active.state.recent_turns
        return {
            "entity_id": engine.active.config.id,
            "turns": [turn.model_dump(mode="json") for turn in turns],
        }

    @app.post("/api/affect/impulse")
    async def inject_affect(impulse: Impulse) -> dict:
        """
        Suma un impulso al VAD de la entidad activa (D1-18, §8.3 «inyectar afecto»).

        Es un estímulo de laboratorio: queda registrado con `source: "manual"`.
        409 si no hay una entidad cargada.
        """
        if engine.orchestrator is None:
            raise HTTPException(status_code=409, detail="No hay una entidad cargada")
        event = engine.orchestrator.inject(**impulse.model_dump())
        return {"affect": engine.active.state.affect.model_dump(), "event_id": event.id}

    @app.websocket("/ws/chat")
    async def chat(websocket: WebSocket) -> None:
        """
        Chat con la entidad activa.

        Recibe `{"text": "..."}` y responde `{"type": "token", "text": ...}` por
        fragmento, y al final `{"type": "done"}` o `{"type": "error", "message": ...}`.
        El turno lo procesa el orquestador (§6.2); aquí solo se transporta.
        """
        await websocket.accept()
        try:
            while True:
                message = await websocket.receive_json()
                text = str(message.get("text", "")).strip()
                if engine.orchestrator is None:
                    await websocket.send_json({"type": "error", "message": "No hay una entidad cargada"})
                    continue
                if not text:
                    await websocket.send_json({"type": "error", "message": "Mensaje vacío"})
                    continue
                try:
                    turn = engine.orchestrator.user_turn(text)
                    async with aclosing(turn) as pieces:
                        async for piece in pieces:
                            await websocket.send_json({"type": "token", "text": piece})
                except LLMError as error:
                    await websocket.send_json({"type": "error", "message": str(error)})
                    continue
                await websocket.send_json({"type": "done"})
        except WebSocketDisconnect:
            # Si la consola se va a mitad de una respuesta, `aclosing` ya cerró
            # el streaming y el cliente LLM emitió `llm.cancelled`.
            pass

    @app.websocket("/ws/events")
    async def events(
        websocket: WebSocket, history: int = Query(0, ge=0, le=MAX_HISTORY_EVENTS)
    ) -> None:
        """
        Envía cada evento del bus, en vivo, como JSON.

        Con `?history=N`, antes envía los últimos N eventos de hoy de la entidad
        activa (del JSONL), para que una consola que se conecta tarde vea el
        estado actual. Se suscribe *antes* de leer el historial y descarta lo
        repetido: así no se pierde ni se duplica un evento emitido en medio.
        """
        await websocket.accept()
        queue = engine.bus.subscribe()
        try:
            sent: set[str] = set()
            if history and engine.active is not None:
                today = engine.log.read(engine.active.config.id, datetime.now(timezone.utc))
                for event in today[-history:]:
                    sent.add(event.id)
                    await websocket.send_json(event.model_dump(mode="json"))
            while True:
                event = await queue.get()
                if event.id in sent:
                    continue
                await websocket.send_json(event.model_dump(mode="json"))
        except WebSocketDisconnect:
            pass
        finally:
            # Sin esto, la cola de una consola cerrada seguiría creciendo.
            engine.bus.unsubscribe(queue)

    return app


def create_app_from_env() -> FastAPI:
    """Fábrica de `python -m ebica.api`: la aplicación con la memoria cargada desde el entorno (D1-38)."""
    return create_app(load_memory=True)
