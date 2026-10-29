"""
Prueba de la herramienta de reproducción afectiva (CP10b parte A).

Genera una conversación con el orquestador (LLM simulado, reloj real: el bus
pone la hora real a los eventos, igual que en el servidor) y comprueba que `scripts/reproducir_afecto.py` la vuelve a vivir con exactitud a
partir de sus eventos. Si alguien cambia el motor sin cambiar la herramienta (o
al revés), esta prueba lo avisa.
"""

import importlib.util
from pathlib import Path

import pytest
from fake_llm import NEUTRAL_APPRAISAL, turn_transport

from ebica.core.events import EventBus
from ebica.core.orchestrator import Orchestrator
from ebica.entities.manager import EntityManager
from ebica.llm.client import LLMClient

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reproducir_afecto", ROOT / "scripts" / "reproducir_afecto.py")
reproducir = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reproducir)

HOSTILE = {**NEUTRAL_APPRAISAL, "hostility": 0.9, "goal_congruence": -0.8,
           "user_emotion": {"valence": -0.7, "arousal": 0.6, "dominance": 0.6}}


async def test_replay_reproduces_a_recorded_conversation_exactly(tmp_path):
    """Con el motor sin cambios, la reproducción da el mismo VAD que se registró en cada turno."""
    bus = EventBus()
    events = []
    queue = bus.subscribe()
    manager = EntityManager(tmp_path, bus)
    entity = manager.create(EntityManager(ROOT / "entities", EventBus()).read_config("calisto").model_copy(
        update={"id": "prueba-reproduccion"}))
    transport, _ = turn_transport("Ho", "la", appraisal=HOSTILE)
    async with LLMClient(bus, transport=transport) as llm:
        orchestrator = Orchestrator(entity, bus, manager.save_state, llm=llm)
        orchestrator.wake()
        for text in ["¿Por qué eres así?", "No me gusta tu tono", "Bueno, ya pasó"]:
            _ = [piece async for piece in orchestrator.user_turn(text)]
        orchestrator.inject(valence=0.3)
    while not queue.empty():
        events.append(queue.get_nowait().model_dump(mode="json"))

    # Sin el bucle rápido corriendo, el orquestador salta de evento en evento: la reproducción también.
    # Entre la hora del evento y la del orquestador hay microsegundos: de ahí la tolerancia.
    turns = reproducir.replay(events, "calisto", step=None)
    result = reproducir.summary(turns)

    assert len(turns) == 3
    assert result["max_diferencia_con_lo_registrado"] == pytest.approx(0.0, abs=1e-3)
    assert turns[0].delta_valence < 0  # la hostilidad baja el ánimo también en la reproducción
