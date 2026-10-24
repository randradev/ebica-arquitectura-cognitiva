"""
Servidor HTTP + WebSocket del motor (documento base §8.3).

- `GET/POST /api/entities`, `POST /api/entities/{id}/load`: crear, listar y cargar.
- `WS /ws/chat`: chat con la entidad activa; la respuesta llega en streaming.
- `WS /ws/events`: todos los eventos del bus en vivo, para la consola.

El servidor solo expone API; la consola (`console/`) corre aparte con Vite.
Hay una sola entidad activa a la vez (§4.2, restricción de GPU).
"""

import os
from contextlib import aclosing, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi import Path as PathParam

from ebica.core.events import ENTITY_ID_PATTERN, EventBus, JsonlEventLog
from ebica.core.state import EntityConfig
from ebica.core.turn import run_user_turn
from ebica.entities.manager import Entity, EntityConfigError, EntityManager
from ebica.llm.client import LLMClient, LLMError


@dataclass
class Engine:
    """Los componentes compartidos del motor durante la vida del servidor."""

    bus: EventBus
    manager: EntityManager
    llm: LLMClient
    active: Entity | None = None


def entity_summary(entity: Entity) -> dict:
    """Representación JSON de una entidad para la consola."""
    return {"config": entity.config.model_dump(), "state": entity.state.model_dump(mode="json")}


def create_app(
    entities_dir: Path | None = None, llm_transport: httpx.AsyncBaseTransport | None = None
) -> FastAPI:
    """
    Construye la aplicación con sus dependencias.

    Sin argumentos usa `EBICA_ENTITIES_DIR` y el LLM configurado en el entorno;
    las pruebas pasan una carpeta temporal y un servidor LLM simulado.
    """
    base_dir = Path(entities_dir or os.environ.get("EBICA_ENTITIES_DIR", "entities"))
    bus = EventBus(JsonlEventLog(base_dir))
    engine = Engine(
        bus=bus,
        manager=EntityManager(base_dir, bus),
        llm=LLMClient.from_env(bus, transport=llm_transport),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Cierra el cliente LLM al apagar el servidor."""
        yield
        await engine.llm.aclose()

    app = FastAPI(title="EBICA", lifespan=lifespan)
    app.state.engine = engine

    @app.get("/api/entities")
    async def list_entities() -> dict:
        """Lista las entidades disponibles y cuál está activa."""
        active_id = engine.active.config.id if engine.active else None
        return {"ids": engine.manager.list_ids(), "active": active_id}

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
            engine.active = engine.manager.load(entity_id)
        except EntityConfigError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return entity_summary(engine.active)

    @app.websocket("/ws/chat")
    async def chat(websocket: WebSocket) -> None:
        """
        Chat con la entidad activa.

        Recibe `{"text": "..."}` y responde `{"type": "token", "text": ...}` por
        fragmento, y al final `{"type": "done"}` o `{"type": "error", "message": ...}`.
        Los turnos se procesan de uno en uno (Fase 0 no tiene cola de GPU).
        """
        await websocket.accept()
        try:
            while True:
                message = await websocket.receive_json()
                text = str(message.get("text", "")).strip()
                if engine.active is None:
                    await websocket.send_json({"type": "error", "message": "No hay una entidad cargada"})
                    continue
                if not text:
                    await websocket.send_json({"type": "error", "message": "Mensaje vacío"})
                    continue
                try:
                    turn = run_user_turn(engine.active, text, engine.bus, engine.llm)
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
    async def events(websocket: WebSocket) -> None:
        """Envía cada evento del bus, en vivo, como JSON."""
        await websocket.accept()
        queue = engine.bus.subscribe()
        try:
            while True:
                event = await queue.get()
                await websocket.send_json(event.model_dump(mode="json"))
        except WebSocketDisconnect:
            pass
        finally:
            # Sin esto, la cola de una consola cerrada seguiría creciendo.
            engine.bus.unsubscribe(queue)

    return app
