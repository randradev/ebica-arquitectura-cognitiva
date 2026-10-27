"""
Pruebas del servidor y del transporte del turno, con un LLM simulado.

Cubren el criterio de Fase 0 (crear una entidad, enviarle un mensaje y ver la
cadena de eventos en el WebSocket y en el JSONL), actualizado al turno de
Fase 1 (CP5): el turno lo procesa el orquestador, con appraisal y afecto.
"""

import json

import httpx
import pytest
from fake_llm import drain, sse, turn_transport
from fastapi.testclient import TestClient

from ebica.api.server import create_app
from ebica.core.events import EventBus, JsonlEventLog
from ebica.core.state import EntityConfig
from ebica.core.orchestrator import Orchestrator
from ebica.entities.manager import EntityConfigError, EntityManager
from ebica.llm.client import LLMClient
from ebica.llm.prompt_assembler import build_dialogue_messages
from ebica.llm.refusal import BUFFER_CHARS
from ebica.memory.episodes import SeedImportReport

CONFIG = {"id": "aurora", "name": "Aurora", "description": "Restauradora.", "persona": "Soy reservada."}


def fake_transport(*pieces: str) -> httpx.MockTransport:
    """Servidor LLM simulado que siempre responde con esos fragmentos."""
    return httpx.MockTransport(lambda request: httpx.Response(200, content=sse(*pieces)))


@pytest.fixture
def client(tmp_path):
    """Aplicación completa sobre una carpeta temporal y un LLM simulado (appraisal + diálogo)."""
    transport, _ = turn_transport("Ho", "la")
    app = create_app(entities_dir=tmp_path, llm_transport=transport)
    with TestClient(app) as test_client:
        yield test_client


def test_dialogue_prompt_contains_identity_and_message():
    """El prompt trivial de Fase 0 lleva nombre, descripción, persona y el mensaje."""
    messages = build_dialogue_messages(EntityConfig(**CONFIG), "¿Qué tal?")

    assert messages[0] == {"role": "system", "content": "Eres Aurora. Restauradora. Soy reservada."}
    assert messages[1] == {"role": "user", "content": "¿Qué tal?"}


async def test_closing_turn_early_cancels_llm(tmp_path):
    """Si quien consume deja de leer y cierra el turno, se emite llm.cancelled y no se guarda el intercambio."""
    bus = EventBus()
    manager = EntityManager(tmp_path, bus)
    entity = manager.create(EntityConfig(**CONFIG))
    # El primer fragmento supera la retención anti-rechazos (D1-33): se muestra
    # de inmediato y el resto del streaming sigue pendiente al cerrar.
    first = "Ho" + "o" * BUFFER_CHARS
    transport, _ = turn_transport(first, "la", "!")
    async with LLMClient(bus, transport=transport) as llm:
        orchestrator = Orchestrator(entity, bus, manager.save_state, llm=llm)
        orchestrator.wake()
        queue = bus.subscribe()
        turn = orchestrator.user_turn("hola")
        assert await anext(turn) == first
        await turn.aclose()

    types = [event.type for event in drain(queue)]
    assert types[-1] == "llm.cancelled"
    assert "turn.completed" not in types
    assert entity.state.recent_turns == []


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
        live = []
        while not live or live[-1]["type"] != "turn.completed":
            live.append(events.receive_json())

    assert replies == [{"type": "token", "text": "Ho"}, {"type": "token", "text": "la"}, {"type": "done"}]
    perception = live[0]
    assert perception["type"] == "perception.input"
    dialogue_request = [e for e in live if e["type"] == "llm.request" and e["payload"]["preset"] == "dialogue"][0]
    assert dialogue_request["payload"]["body"]["messages"][-1] == {"role": "user", "content": "hola"}
    response = [e for e in live if e["type"] == "llm.response"][-1]
    assert response["payload"]["text"] == "Hola"

    day_file = next((tmp_path / "aurora" / "events").glob("*.jsonl"))
    logged = [json.loads(line) for line in day_file.read_text(encoding="utf-8").splitlines()]
    # Al cargar, el bucle rápido despierta a la entidad (CP4): affect.updated,
    # drive.updated y tick. Después, todo lo que se vio en vivo está en el JSONL.
    assert [event["type"] for event in logged[:6]] == [
        "entity.created", "entity.loaded", "identity.loaded",
        "affect.updated", "drive.updated", "tick",
    ]
    logged_ids = [event["id"] for event in logged]
    assert all(event["id"] in logged_ids for event in live)


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


def test_conversation_endpoint_returns_saved_turns(client):
    """Hallazgo 4 de CP5: la consola puede recuperar la conversación guardada de la entidad activa."""
    assert client.get("/api/conversation").json() == {"entity_id": None, "turns": []}
    client.post("/api/entities", json=CONFIG)
    client.post("/api/entities/aurora/load")
    with client.websocket_connect("/ws/chat") as chat:
        chat.send_json({"text": "hola"})
        while chat.receive_json()["type"] != "done":
            pass

    data = client.get("/api/conversation").json()

    assert data["entity_id"] == "aurora"
    assert [(turn["user"], turn["entity"]) for turn in data["turns"]] == [("hola", "Hola")]


# ------------------------------------------------------------ memoria (CP6 C)


class FakeSeedMemory:
    """Hace las veces de `MemoryWriter` en la API: registra las importaciones o falla a pedido."""

    def __init__(self, fail: bool = False) -> None:
        """`fail=True` simula que Neo4j no responde."""
        self.fail = fail
        self.imported: list[str] = []

    async def import_seed(self, entity_id, name, biography):
        """Registra la importación y devuelve un reporte vacío, o lanza un error."""
        if self.fail:
            raise ConnectionError("Neo4j no responde")
        self.imported.append(entity_id)
        return SeedImportReport(created=["f-1"])


def memory_client(tmp_path, memory):
    """Cliente con una memoria simulada inyectada."""
    transport, _ = turn_transport("Ho", "la")
    return TestClient(create_app(entities_dir=tmp_path, llm_transport=transport, memory=memory))


def test_loading_an_entity_imports_its_seed(tmp_path):
    """Al cargar una entidad se importa su semilla y se emite `memory.seed_imported`."""
    memory = FakeSeedMemory()
    with memory_client(tmp_path, memory) as client:
        client.post("/api/entities", json=CONFIG)
        assert client.post("/api/entities/aurora/load").status_code == 200

    assert memory.imported == ["aurora"]
    log = "".join(path.read_text(encoding="utf-8") for path in (tmp_path / "aurora" / "events").glob("*.jsonl"))
    assert '"type": "memory.seed_imported"' in log or '"type":"memory.seed_imported"' in log


def test_seed_import_failure_answers_503_and_keeps_the_active_entity(tmp_path):
    """Si Neo4j falla al cargar, la API responde 503 y la entidad anterior sigue activa."""
    memory = FakeSeedMemory()
    with memory_client(tmp_path, memory) as client:
        client.post("/api/entities", json=CONFIG)
        client.post("/api/entities", json={**CONFIG, "id": "bruna", "name": "Bruna"})
        client.post("/api/entities/aurora/load")
        memory.fail = True

        response = client.post("/api/entities/bruna/load")

        assert response.status_code == 503 and "Neo4j no responde" in response.json()["detail"]
        assert client.get("/api/entities").json()["active"] == "aurora"


def test_server_without_memory_does_not_load_it(tmp_path, monkeypatch):
    """`create_app` sin `load_memory` no intenta conectar a Neo4j ni cargar bge-m3 (las pruebas siguen livianas)."""
    import ebica.api.server as server

    async def forbidden():
        """Falla si alguien intenta cargar la memoria."""
        raise AssertionError("no debía cargarse la memoria")

    monkeypatch.setattr(server, "load_memory_from_env", forbidden)
    with memory_client(tmp_path, None) as client:
        assert client.get("/api/entities").status_code == 200


def test_memory_off_skips_loading(tmp_path, monkeypatch):
    """D1-38: con `load_memory` y `EBICA_MEMORY=off`, el servidor arranca sin memoria."""
    import ebica.api.server as server

    async def forbidden():
        """Falla si alguien intenta cargar la memoria."""
        raise AssertionError("no debía cargarse la memoria")

    monkeypatch.setattr(server, "load_memory_from_env", forbidden)
    monkeypatch.setenv("EBICA_MEMORY", "off")
    transport, _ = turn_transport("Ho", "la")
    app = create_app(entities_dir=tmp_path, llm_transport=transport, load_memory=True)
    with TestClient(app) as client:
        assert client.get("/api/entities").status_code == 200
    assert app.state.engine.memory is None


def test_memory_load_failure_stops_startup(tmp_path, monkeypatch):
    """D1-38: si la memoria no puede prepararse, el servidor no arranca."""
    import ebica.api.server as server

    async def broken():
        """Simula Neo4j caído."""
        raise server.MemoryUnavailableError("Neo4j no disponible")

    monkeypatch.setattr(server, "load_memory_from_env", broken)
    monkeypatch.delenv("EBICA_MEMORY", raising=False)
    transport, _ = turn_transport("Ho", "la")
    app = create_app(entities_dir=tmp_path, llm_transport=transport, load_memory=True)
    with pytest.raises(server.MemoryUnavailableError):
        with TestClient(app):
            pass
