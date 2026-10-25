"""
Pruebas del turno mínimo y del servidor (CP5), con un LLM simulado.

Cubren el criterio de Fase 0 de forma automática: crear una entidad, enviarle
un mensaje y obtener `perception.input` → `llm.request` → `llm.response`
encadenados, en el WebSocket de eventos y en el JSONL.
"""

import json

import httpx
import pytest
from fake_llm import drain, sse
from fastapi.testclient import TestClient

from ebica.api.server import create_app
from ebica.core.events import EventBus, JsonlEventLog
from ebica.core.state import EntityConfig
from ebica.core.turn import run_user_turn
from ebica.entities.manager import EntityConfigError, EntityManager
from ebica.llm.client import LLMClient
from ebica.llm.prompt_assembler import build_dialogue_messages

CONFIG = {"id": "aurora", "name": "Aurora", "description": "Restauradora.", "persona": "Soy reservada."}


def fake_transport(*pieces: str) -> httpx.MockTransport:
    """Servidor LLM simulado que siempre responde con esos fragmentos."""
    return httpx.MockTransport(lambda request: httpx.Response(200, content=sse(*pieces)))


@pytest.fixture
def client(tmp_path):
    """Aplicación completa sobre una carpeta temporal y un LLM simulado."""
    app = create_app(entities_dir=tmp_path, llm_transport=fake_transport("Ho", "la"))
    with TestClient(app) as test_client:
        yield test_client


def test_dialogue_prompt_contains_identity_and_message():
    """El prompt trivial de Fase 0 lleva nombre, descripción, persona y el mensaje."""
    messages = build_dialogue_messages(EntityConfig(**CONFIG), "¿Qué tal?")

    assert messages[0] == {"role": "system", "content": "Eres Aurora. Restauradora. Soy reservada."}
    assert messages[1] == {"role": "user", "content": "¿Qué tal?"}


async def test_turn_chains_events_by_cause(tmp_path):
    """Un turno emite perception.input → llm.request → llm.response, encadenados."""
    bus = EventBus()
    entity = EntityManager(tmp_path, bus).create(EntityConfig(**CONFIG))
    queue = bus.subscribe()
    async with LLMClient(bus, transport=fake_transport("Ho", "la")) as llm:
        pieces = [piece async for piece in run_user_turn(entity, "hola", bus, llm)]

    perception, request, response = drain(queue)
    assert pieces == ["Ho", "la"]
    assert perception.type == "perception.input" and perception.payload["text"] == "hola"
    assert request.type == "llm.request" and request.cause_id == perception.id
    assert response.type == "llm.response" and response.cause_id == request.id


async def test_closing_turn_early_cancels_llm(tmp_path):
    """Si quien consume deja de leer y cierra el turno, se emite llm.cancelled en el acto."""
    bus = EventBus()
    entity = EntityManager(tmp_path, bus).create(EntityConfig(**CONFIG))
    queue = bus.subscribe()
    async with LLMClient(bus, transport=fake_transport("Ho", "la", "!")) as llm:
        turn = run_user_turn(entity, "hola", bus, llm)
        assert await anext(turn) == "Ho"
        await turn.aclose()

    assert [event.type for event in drain(queue)] == ["perception.input", "llm.request", "llm.cancelled"]


def test_create_list_and_load_entity(client):
    """Por HTTP se crea, se lista y se carga una entidad, que queda activa."""
    assert client.post("/api/entities", json=CONFIG).status_code == 201
    assert client.post("/api/entities", json=CONFIG).status_code == 409

    loaded = client.post("/api/entities/aurora/load")

    assert loaded.status_code == 200
    assert loaded.json()["config"]["name"] == "Aurora"
    assert client.get("/api/entities").json() == {"ids": ["aurora"], "active": "aurora", "active_name": "Aurora"}


def test_load_errors(client):
    """Cargar una entidad inexistente da 404; un id con formato inseguro, 422."""
    assert client.post("/api/entities/fantasma/load").status_code == 404
    assert client.post("/api/entities/..%2Ffuera/load").status_code in (404, 422)
    assert client.post("/api/entities/MAYUS/load").status_code == 422


def test_invalid_config_is_rejected(client):
    """Crear con un campo desconocido devuelve 422 (validación de EntityConfig)."""
    response = client.post("/api/entities", json={**CONFIG, "nmae": "x"})

    assert response.status_code == 422


def test_chat_without_active_entity_reports_error(client):
    """Chatear sin entidad cargada responde un error, sin cerrar la conexión."""
    with client.websocket_connect("/ws/chat") as chat:
        chat.send_json({"text": "hola"})
        assert chat.receive_json() == {"type": "error", "message": "No hay una entidad cargada"}


def test_chat_end_to_end_with_events_and_jsonl(client, tmp_path):
    """
    Criterio de Fase 0 (con LLM simulado): la consola recibe la respuesta en
    streaming y ve perception.input, el prompt exacto y la respuesta; los mismos
    eventos quedan en el JSONL.
    """
    client.post("/api/entities", json=CONFIG)
    client.post("/api/entities/aurora/load")

    with client.websocket_connect("/ws/events") as events, client.websocket_connect("/ws/chat") as chat:
        chat.send_json({"text": "hola"})
        replies = [chat.receive_json() for _ in range(3)]
        live = [events.receive_json() for _ in range(3)]

    assert replies == [{"type": "token", "text": "Ho"}, {"type": "token", "text": "la"}, {"type": "done"}]
    perception, request, response = live
    assert perception["type"] == "perception.input"
    assert request["type"] == "llm.request"
    assert request["payload"]["body"]["messages"][1] == {"role": "user", "content": "hola"}
    assert response["type"] == "llm.response" and response["payload"]["text"] == "Hola"

    day_file = next((tmp_path / "aurora" / "events").glob("*.jsonl"))
    logged = [json.loads(line) for line in day_file.read_text(encoding="utf-8").splitlines()]
    # Al cargar, el bucle rápido despierta a la entidad (CP4): affect.updated,
    # drive.updated y tick. Los demás eventos del bucle solo salen ante un
    # cambio o cada 60 s, así que no se cuelan entre los del turno.
    assert [event["type"] for event in logged] == [
        "entity.created", "entity.loaded", "identity.loaded",
        "affect.updated", "drive.updated", "tick",
        "perception.input", "llm.request", "llm.response",
    ]
    assert [event["id"] for event in logged[6:]] == [event["id"] for event in live]


def test_llm_error_is_reported_in_chat(tmp_path):
    """Si el servidor LLM falla, el chat recibe un mensaje de error y sigue abierto."""
    transport = httpx.MockTransport(lambda request: httpx.Response(500, text="fallo"))
    app = create_app(entities_dir=tmp_path, llm_transport=transport)
    with TestClient(app) as client:
        client.post("/api/entities", json=CONFIG)
        client.post("/api/entities/aurora/load")
        with client.websocket_connect("/ws/chat") as chat:
            chat.send_json({"text": "hola"})
            reply = chat.receive_json()
            chat.send_json({"text": ""})
            empty = chat.receive_json()

    assert reply["type"] == "error" and "500" in reply["message"]
    assert empty == {"type": "error", "message": "Mensaje vacío"}


def test_invalid_entity_id_in_manager_is_rejected(tmp_path):
    """El manager rechaza un id inseguro aunque no venga de la API."""
    with pytest.raises(EntityConfigError, match="inválido"):
        EntityManager(tmp_path, EventBus()).load("../fuera")


def test_list_ids_only_counts_folders_with_config(tmp_path):
    """`list_ids` ignora carpetas sin `config.yaml`."""
    manager = EntityManager(tmp_path, EventBus(JsonlEventLog(tmp_path)))
    manager.create(EntityConfig(**CONFIG))
    (tmp_path / "vacia").mkdir()

    assert manager.list_ids() == ["aurora"]


# ------------------------------------------------------------ CP4: bucle rápido en el servidor


def test_impulse_requires_an_active_entity(client):
    """Sin entidad cargada no hay ánimo que mover: 409."""
    assert client.post("/api/affect/impulse", json={"valence": -0.5}).status_code == 409


def test_impulse_moves_affect_and_is_marked_manual(client):
    """Un impulso manual baja la valencia de inmediato y se emite con `source: "manual"`."""
    client.post("/api/entities", json=CONFIG)
    before = client.post("/api/entities/aurora/load").json()["state"]["affect"]["valence"]

    with client.websocket_connect("/ws/events") as events:
        response = client.post("/api/affect/impulse", json={"valence": -0.5})
        event = events.receive_json()

    assert response.status_code == 200
    assert response.json()["affect"]["valence"] == pytest.approx(before - 0.5, abs=0.01)
    assert event["type"] == "affect.updated" and event["payload"]["source"] == "manual"
    assert event["id"] == response.json()["event_id"]


def test_impulse_out_of_range_is_rejected(client):
    """Un impulso fuera de [−1, 1] es un error de la petición, no se recorta en silencio."""
    client.post("/api/entities", json=CONFIG)
    client.post("/api/entities/aurora/load")

    assert client.post("/api/affect/impulse", json={"valence": -5}).status_code == 422


def test_events_history_on_connect(client):
    """Con ?history=N, la consola recibe primero los eventos de hoy y luego los nuevos, sin repetir."""
    client.post("/api/entities", json=CONFIG)
    client.post("/api/entities/aurora/load")

    with client.websocket_connect("/ws/events?history=50") as events:
        history = [events.receive_json() for _ in range(6)]
        client.post("/api/affect/impulse", json={"arousal": 0.3})
        live = events.receive_json()

    assert [event["type"] for event in history] == [
        "entity.created", "entity.loaded", "identity.loaded", "affect.updated", "drive.updated", "tick",
    ]
    assert live["payload"]["source"] == "manual"
    assert live["id"] not in {event["id"] for event in history}


def test_switching_entity_stops_the_previous_loop_and_saves(client, tmp_path):
    """Al cargar otra entidad, el bucle de la anterior se detiene y su estado queda guardado."""
    client.post("/api/entities", json=CONFIG)
    client.post("/api/entities", json={**CONFIG, "id": "boris", "name": "Boris"})
    client.post("/api/entities/aurora/load")
    client.post("/api/affect/impulse", json={"valence": -0.3})

    client.post("/api/entities/boris/load")

    saved = json.loads((tmp_path / "aurora" / "state.json").read_text(encoding="utf-8"))
    assert saved["affect"]["valence"] < 0
    assert saved["last_tick_at"] is not None
    engine = client.app.state.engine
    assert engine.active.config.id == "boris" and engine.orchestrator.entity_id == "boris"
