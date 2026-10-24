"""Pruebas del esquema de eventos, el EventBus y la persistencia JSONL (CP1)."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ebica.core.events import Event, EventBus, JsonlEventLog


@pytest.fixture
def log(tmp_path):
    """Registro JSONL sobre una carpeta temporal, para no tocar `entities/`."""
    return JsonlEventLog(tmp_path)


async def test_subscriber_receives_emitted_event():
    """Un evento emitido llega intacto a la cola del suscriptor."""
    bus = EventBus()
    queue = bus.subscribe()

    sent = bus.emit("ejemplo", "entity.loaded", {"name": "Ejemplo"})

    received = queue.get_nowait()
    assert received == sent
    assert received.payload == {"name": "Ejemplo"}


async def test_unsubscribed_queue_stops_receiving():
    """Tras `unsubscribe`, la cola ya no recibe eventos nuevos."""
    bus = EventBus()
    queue = bus.subscribe()
    bus.unsubscribe(queue)

    bus.emit("ejemplo", "tick")

    assert queue.empty()


def test_event_is_written_as_one_json_line(log, tmp_path):
    """Cada evento ocupa una línea JSON válida en el archivo de su día."""
    bus = EventBus(log)
    event = bus.emit("ejemplo", "perception.input", {"text": "hola"})

    path = tmp_path / "ejemplo" / "events" / f"{event.ts.date().isoformat()}.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["type"] == "perception.input"
    assert data["entity_id"] == "ejemplo"
    assert data["payload"] == {"text": "hola"}


def test_reading_log_rebuilds_identical_events(log):
    """Leer el archivo reconstruye los mismos eventos, en el mismo orden."""
    bus = EventBus(log)
    first = bus.emit("ejemplo", "perception.input", {"text": "hola"})
    second = bus.emit("ejemplo", "llm.response", {"text": "buenas"})

    assert log.read("ejemplo", first.ts) == [first, second]


def test_cause_id_chains_events(log):
    """`cause_id` enlaza el efecto con el evento que lo causó y sobrevive al disco."""
    bus = EventBus(log)
    cause = bus.emit("ejemplo", "perception.input", {"text": "hola"})
    effect = bus.emit("ejemplo", "llm.request", {"prompt": "..."}, cause_id=cause.id)

    stored = {event.id: event for event in log.read("ejemplo", cause.ts)}
    assert stored[effect.id].cause_id == cause.id


def test_events_of_different_days_go_to_different_files(log):
    """Eventos de días distintos (en UTC) se guardan en archivos distintos."""
    bus = EventBus(log)
    today = datetime(2026, 10, 24, 23, 0, tzinfo=timezone.utc)
    tomorrow = today + timedelta(hours=2)

    bus.publish(Event(entity_id="ejemplo", type="tick", ts=today))
    bus.publish(Event(entity_id="ejemplo", type="tick", ts=tomorrow))

    assert len(log.read("ejemplo", today)) == 1
    assert len(log.read("ejemplo", tomorrow)) == 1
    assert log.path_for("ejemplo", today) != log.path_for("ejemplo", tomorrow)


def test_reading_missing_day_returns_empty_list(log):
    """Si no hubo eventos ese día, la lectura devuelve una lista vacía."""
    assert log.read("ejemplo", datetime.now(timezone.utc)) == []


@pytest.mark.parametrize("bad_id", ["../fuera", "Con Espacios", "MAYUS", ""])
def test_unsafe_entity_id_is_rejected(bad_id):
    """Un `entity_id` que no sirve como nombre de carpeta seguro se rechaza."""
    with pytest.raises(ValidationError):
        Event(entity_id=bad_id, type="tick")


@pytest.mark.parametrize("bad_type", ["Entity.Loaded", "entity..loaded", "entity loaded", ""])
def test_malformed_event_type_is_rejected(bad_type):
    """El tipo de evento debe seguir el formato `familia.nombre` en minúsculas."""
    with pytest.raises(ValidationError):
        Event(entity_id="ejemplo", type=bad_type)
