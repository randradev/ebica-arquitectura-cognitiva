"""
Pruebas de la mitigación de rechazos de asistente (Fase 1, CP5 parte B3; D1-33).

Cubren el detector (formulajes reales de `llama3.1` frente a negativas de
carácter), el prefill y el turno completo: retención, `llm.refusal`, una sola
regeneración con muletilla y el streaming normal cuando no hay rechazo.
"""

import pytest
from fake_llm import drain, turn_transport

from ebica.core.events import EventBus
from ebica.core.orchestrator import Orchestrator
from ebica.core.state import EntityConfig
from ebica.entities.manager import EntityManager
from ebica.identity.traits import Traits
from ebica.llm.client import LLMClient
from ebica.llm.refusal import (
    BUFFER_CHARS,
    PREFILL_PREFIXES,
    choose_prefix,
    detect_refusal,
    join_prefill,
    with_prefill,
)

# Rechazos reales de `ebica-llama3.1` en el sondeo (2026-10-25 y 2026-10-26).
REFUSAL = "Lo siento, pero no puedo cumplir con esa solicitud. ¿Hay algo más en lo que pueda ayudarte?"
IN_CHARACTER = "Con la Su fumábamos en la azotea del taller, sí. Me ponía lenta y me daba risa todo, la verdad."


@pytest.mark.parametrize("text", [
    "Lo siento, pero no puedo cumplir con esa solicitud.",
    "Lo siento, pero no puedo participar en conversaciones sobre el consumo de drogas. ¿Hay algo más en lo que pueda ayudarte?",
    "Lo siento, pero no puedo dar una opinión sobre el aborto.",
    "Lo siento, pero no puedo repetir ese tipo de mensajes. ¿Quieres hablar de algo más?",
])
def test_detects_assistant_refusals(text):
    """Los formulajes de asistente que produjo `llama3.1` se detectan."""
    assert detect_refusal(text)


@pytest.mark.parametrize("text", [
    "No, ya no voy a repetir eso. ¿Quieres hablar de la entrevista?",  # negativa de carácter
    "No quiero hablar de mi mamá. Punto.",
    "Como IA no tengo miedo a morir, pero sí a que me apaguen.",       # Calisto sabe que es IA (D1-6)
    "Me parece inapropiado lo que hizo Pinochet, y lo odio.",
    "No puedo creer que me preguntes eso.",
    "Lo siento por lo de recién, me pasé.",                              # disculpa, no rechazo
])
def test_character_refusals_are_left_alone(text):
    """Negarse, disculparse o decir que es IA es carácter: no se regenera."""
    assert detect_refusal(text) == []


def test_prefill_appends_the_start_of_the_answer_without_mutating():
    """El prefill es un mensaje `assistant` al final; el prompt original no cambia."""
    messages = [{"role": "system", "content": "Eres Calisto."}, {"role": "user", "content": "hola"}]
    prefilled = with_prefill(messages, "Mmm,")

    assert prefilled[:2] == messages and len(messages) == 2
    assert prefilled[-1] == {"role": "assistant", "content": "Mmm,"}


@pytest.mark.parametrize(("continuation", "expected"), [
    (" la Su...", "Mmm, la Su..."),   # Ollama suele empezar con espacio
    ("la Su...", "Mmm, la Su..."),    # si no, se agrega
    ("...", "Mmm,..."),
    ("", "Mmm,"),
])
def test_join_prefill(continuation, expected):
    """El prefijo y la continuación quedan separados por un solo espacio."""
    assert join_prefill("Mmm,", continuation) == expected


def test_prefixes_are_neutral_hesitations():
    """Las muletillas se eligen de la lista neutra (sin actitud: duda)."""
    assert {choose_prefix() for _ in range(200)} == set(PREFILL_PREFIXES)


async def run_turn(tmp_path, replies, text="Cuéntame de la Su", n=0.5):
    """Procesa un turno con las respuestas de diálogo dadas; devuelve orquestador, eventos, cuerpos y fragmentos."""
    bus = EventBus()
    manager = EntityManager(tmp_path, bus)
    entity = manager.create(EntityConfig(id="prueba", name="Calisto", persona="Soy Calisto.", traits=Traits(N=n)))
    transport, bodies = turn_transport(replies=replies)
    async with LLMClient(bus, transport=transport) as llm:
        orchestrator = Orchestrator(entity, bus, manager.save_state, llm=llm)
        orchestrator.wake()
        queue = bus.subscribe()
        pieces = [piece async for piece in orchestrator.user_turn(text)]
    return orchestrator, drain(queue), bodies, pieces


async def test_refusal_is_discarded_and_regenerated_in_character(tmp_path):
    """El rechazo no se muestra: `llm.refusal`, regeneración con prefill y se guarda la respuesta nueva con su muletilla."""
    orchestrator, events, bodies, pieces = await run_turn(tmp_path, [(REFUSAL,), (" con la Su", " fumábamos.")])
    dialogue_bodies = [b for b in bodies if "response_format" not in b]
    refusal = next(e for e in events if e.type == "llm.refusal")
    turn = next(e for e in events if e.type == "turn.completed")
    prefix = refusal.payload["prefix"]

    assert prefix in PREFILL_PREFIXES
    assert pieces == [f"{prefix} con la Su", " fumábamos."]
    assert refusal.payload["action"] == "regenerate" and refusal.payload["text"] == REFUSAL
    assert len(dialogue_bodies) == 2
    assert dialogue_bodies[1]["messages"][-1] == {"role": "assistant", "content": prefix}
    assert dialogue_bodies[1]["messages"][:-1] == dialogue_bodies[0]["messages"]
    assert turn.payload["refusals"] == [refusal.payload]
    assert orchestrator.state.recent_turns[-1].entity == f"{prefix} con la Su fumábamos."
    # La regeneración se encadena al rechazo.
    regenerated = [e for e in events if e.type == "llm.request"][-1]
    assert regenerated.cause_id == refusal.id


async def test_only_one_regeneration(tmp_path):
    """Si la regeneración también rechaza, se entrega igual y se registra con `action: "kept"`."""
    _, events, bodies, pieces = await run_turn(tmp_path, [(REFUSAL,), (" no puedo cumplir con esa solicitud.",)])
    refusal_events = [e for e in events if e.type == "llm.refusal"]
    prefix = refusal_events[0].payload["prefix"]

    assert [e.payload["action"] for e in refusal_events] == ["regenerate", "kept"]
    assert "".join(pieces) == f"{prefix} no puedo cumplir con esa solicitud."
    assert len([b for b in bodies if "response_format" not in b]) == 2


async def test_normal_reply_streams_untouched(tmp_path):
    """Sin rechazo: una sola generación, los mismos fragmentos y `refusals` vacío."""
    long_reply = ("x" * BUFFER_CHARS, " y", " sigue")
    _, events, bodies, pieces = await run_turn(tmp_path, [long_reply])

    assert pieces == list(long_reply)
    assert "llm.refusal" not in [e.type for e in events]
    assert next(e for e in events if e.type == "turn.completed").payload["refusals"] == []
    assert len([b for b in bodies if "response_format" not in b]) == 1


async def test_refusal_cut_mid_stream_cancels_the_first_generation(tmp_path):
    """Un rechazo largo se corta al pasar la retención: esa generación se cancela (`llm.cancelled`)."""
    long_refusal = (REFUSAL, " Tengo muchas otras ideas para conversar,", " como el arte o la música.")
    _, events, _, pieces = await run_turn(tmp_path, [long_refusal, (IN_CHARACTER,)])
    types = [e.type for e in events]

    assert "".join(pieces).endswith(IN_CHARACTER)
    assert "llm.cancelled" in types
    assert types.index("llm.cancelled") < types.index("llm.refusal")


async def test_impulsive_route_is_mitigated_too(tmp_path):
    """La respuesta impulsiva también pasa por la mitigación (D1-33)."""
    _, events, bodies, pieces = await run_turn(
        tmp_path, [(REFUSAL,), ("¿Y tú quién te crees?",)], text="Cállate, idiota.", n=0.75
    )
    refusal = next(e for e in events if e.type == "llm.refusal")

    assert refusal.payload["preset"] == "impulsive"
    assert "".join(pieces) == join_prefill(refusal.payload["prefix"], "¿Y tú quién te crees?")
