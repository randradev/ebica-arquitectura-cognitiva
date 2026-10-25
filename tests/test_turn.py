"""
Pruebas del turno con appraisal (Fase 1, CP5 parte A), con un LLM simulado.

Cubren las fórmulas de D1-20/D1-23/D1-25 con números calculados a mano, el
estado en palabras del prompt, la conversación reciente y la cadena de
eventos del turno completo.
"""

import pytest
from fake_llm import NEUTRAL_APPRAISAL, drain, turn_transport

from ebica.affect.appraisal_effects import (
    SARCASM_CORRECTION,
    affect_impulse,
    apply_coherence_rules,
    dialogue_temperature,
    drive_relief,
)
from ebica.affect.vad import VAD
from ebica.core.events import EventBus
from ebica.core.orchestrator import RECENT_TURNS, Orchestrator
from ebica.core.state import ConversationTurn, EntityConfig
from ebica.entities.manager import EntityManager
from ebica.identity.traits import Traits, derive_parameters
from ebica.llm.client import LLMClient
from ebica.llm.prompt_assembler import FEELINGS_HEADER, build_dialogue_messages, describe_feelings
from ebica.perception.appraisal import Appraisal

CALISTO = Traits(O=0.95, C=0.30, E=0.85, A=0.40, N=0.75)


def appraisal(**overrides) -> Appraisal:
    """Un appraisal neutro con los campos que se quieran cambiar."""
    data = {**NEUTRAL_APPRAISAL, **overrides}
    if "valence" in overrides:
        data["user_emotion"] = {**NEUTRAL_APPRAISAL["user_emotion"], "valence": overrides.pop("valence")}
        data.pop("valence")
    return Appraisal.model_validate(data)


HOSTILE = {"valence": -0.7, "hostility": 0.9, "distress": 0.1, "goal_congruence": -0.8}
WARM = {"valence": 0.8, "hostility": 0.0, "goal_congruence": 0.5, "novelty": 0.4}


# ------------------------------------------------------------ fórmulas


def test_hostile_message_impulse_depends_on_n():
    """«Eres una inútil» (goal_congruence −0,8): −0,42 para Calisto y −0,30 con N 0.25."""
    rest = VAD(valence=0.0, arousal=0.5, dominance=0.5)
    calisto = affect_impulse(appraisal(**HOSTILE), rest, derive_parameters(CALISTO))
    low_n = affect_impulse(appraisal(**HOSTILE), rest, derive_parameters(CALISTO.model_copy(update={"N": 0.25})))

    assert calisto.valence_from_goals == pytest.approx(0.3 * 1.75 * -0.8)
    assert low_n.valence_from_goals == pytest.approx(0.3 * 1.25 * -0.8)
    assert calisto.arousal == pytest.approx(0.25 * 0.9 + 0.15 * 0.1)
    assert calisto.dominance == pytest.approx(-0.2 * 0.9)


def test_empathy_loop_pulls_towards_the_other_mood():
    """Lazo «como si»: 0,5 · π · (valencia ajena − propia); con π 0,44 y −0,8 frente a 0 → −0,176."""
    impulse = affect_impulse(appraisal(valence=-0.8), VAD(valence=0.0), derive_parameters(CALISTO))

    assert impulse.valence_from_empathy == pytest.approx(0.5 * 0.44 * -0.8)
    assert impulse.valence_from_goals == 0.0


def test_no_empathic_contagion_from_an_attacker():
    """D1-27: la empatía se escala por (1 − hostilidad); con hostilidad 0,9 queda en un 10 %."""
    parameters = derive_parameters(CALISTO)
    sad = affect_impulse(appraisal(valence=-0.8), VAD(valence=0.0), parameters)
    angry = affect_impulse(appraisal(valence=-0.8, hostility=0.9), VAD(valence=0.0), parameters)

    assert angry.valence_from_empathy == pytest.approx(sad.valence_from_empathy * 0.1)


def test_positive_goal_uses_g_pos():
    """Lo que favorece sus metas usa g_pos (E): 0,3 · 1,425 · 0,5."""
    impulse = affect_impulse(appraisal(goal_congruence=0.5), VAD(), derive_parameters(CALISTO))

    assert impulse.valence_from_goals == pytest.approx(0.3 * 1.425 * 0.5)


def test_sarcasm_rule_corrects_positive_values():
    """D1-20: con hostilidad alta, valencia y goal_congruence positivas pasan a −0,5·hostilidad."""
    corrected, corrections = apply_coherence_rules(appraisal(valence=0.9, hostility=0.9, goal_congruence=0.4))

    assert corrected.user_emotion.valence == pytest.approx(SARCASM_CORRECTION * 0.9)
    assert corrected.goal_congruence == pytest.approx(SARCASM_CORRECTION * 0.9)
    assert len(corrections) == 2


def test_sarcasm_rule_leaves_coherent_appraisals_alone():
    """Sin hostilidad alta, o con valores ya negativos, no hay corrección."""
    for case in (appraisal(valence=0.9, hostility=0.3), appraisal(**HOSTILE)):
        corrected, corrections = apply_coherence_rules(case)
        assert corrected == case and corrections == []


def test_drive_relief_warm_vs_hostile():
    """El contacto cálido alivia `social` (hasta el doble); el hostil no alivia nada."""
    warm = drive_relief(appraisal(**WARM))
    hostile = drive_relief(appraisal(**{**HOSTILE, "hostility": 1.0}))

    assert warm["social"] == pytest.approx(0.15 * 1.8)
    assert warm["novelty"] == pytest.approx(0.3 * 0.4)
    assert hostile["social"] == 0.0


@pytest.mark.parametrize(
    ("affect", "expected"),
    [
        (VAD(valence=0.0, arousal=0.5), 0.7),
        (VAD(valence=0.5, arousal=0.5), 0.75),
        (VAD(valence=-0.6, arousal=0.9), 0.7 - 0.06 - 0.045),
        (VAD(valence=-1.0, arousal=1.0), 0.54),
        (VAD(valence=1.0, arousal=0.0), 0.8),
    ],
)
def test_dialogue_temperature(affect, expected):
    """D1-25: 0,7 + 0,1·valencia − 0,15·max(0, alerta − 0,6), entre 0,5 y 0,85."""
    assert dialogue_temperature(affect) == pytest.approx(expected)


# ------------------------------------------------------------ prompt


def test_feelings_in_words_without_numbers():
    """El estado se describe en palabras (sin cifras) e incluye los drives altos."""
    text = describe_feelings(
        VAD(valence=-0.45, arousal=0.85, dominance=0.1), {"social": 0.9, "novelty": 0.1, "rest": 0.8}
    )

    assert "ánimo bastante bajo" in text and "mucha agitación" in text
    assert "poca sensación de control" in text
    assert "ganas de conversar" in text and "cansancio" in text
    assert not any(char.isdigit() for char in text)


def test_dialogue_messages_order_and_stable_prefix():
    """Sistema (identidad, luego estado) → intercambios recientes → mensaje actual."""
    config = EntityConfig(id="x", name="X", persona="Soy X.", ego_ideal=["No miento."])
    turns = [ConversationTurn(user="hola", entity="hola, ¿qué tal?", ts="2026-10-25T12:00:00Z")]
    calm = build_dialogue_messages(config, "bien", VAD(valence=0.0, arousal=0.5, dominance=0.5), {}, turns)
    upset = build_dialogue_messages(config, "bien", VAD(valence=-0.7, arousal=0.9, dominance=0.1), {}, turns)

    assert [m["role"] for m in calm] == ["system", "user", "assistant", "user"]
    assert calm[1]["content"] == "hola" and calm[-1]["content"] == "bien"
    prefix = calm[0]["content"].split(FEELINGS_HEADER)[0]
    assert upset[0]["content"].startswith(prefix)  # lo estable no cambia: caché de prefijo
    assert calm[0]["content"] != upset[0]["content"]


# ------------------------------------------------------------ turno completo


async def run_turn(tmp_path, text="hola", appraisal_reply=NEUTRAL_APPRAISAL, turns=1, traits=CALISTO):
    """Crea una entidad, la despierta y procesa `turns` mensajes; devuelve lo necesario para revisar."""
    bus = EventBus()
    manager = EntityManager(tmp_path, bus)
    entity = manager.create(EntityConfig(
        id="prueba", name="Prueba", persona="Soy Prueba.", traits=traits,
        appraisal_profile="Prueba, artista de Santiago.",
    ))
    transport, bodies = turn_transport("Ho", "la", appraisal=appraisal_reply)
    async with LLMClient(bus, transport=transport) as llm:
        orchestrator = Orchestrator(entity, bus, manager.save_state, llm=llm)
        orchestrator.wake()
        queue = bus.subscribe()
        before = entity.state.model_copy(deep=True)
        pieces = []
        for index in range(turns):
            pieces = [piece async for piece in orchestrator.user_turn(f"{text} {index}")]
    return orchestrator, before, drain(queue), bodies, pieces


async def test_turn_event_chain(tmp_path):
    """perception → appraisal → afecto → diálogo → turn.completed, encadenados por cause_id."""
    _, _, events, _, pieces = await run_turn(tmp_path)
    by_type = {}
    for event in events:
        by_type.setdefault(event.type, []).append(event)

    perception = by_type["perception.input"][0]
    appraisal_request, dialogue_request = by_type["llm.request"]
    appraisal_response, dialogue_response = by_type["llm.response"]
    completed = by_type["appraisal.completed"][0]
    affect = next(e for e in by_type["affect.updated"] if e.payload["source"] == "appraisal")
    turn = by_type["turn.completed"][0]

    assert pieces == ["Ho", "la"]
    assert appraisal_request.cause_id == perception.id
    assert appraisal_response.cause_id == appraisal_request.id
    assert completed.cause_id == appraisal_response.id
    assert affect.cause_id == completed.id
    assert dialogue_request.cause_id == affect.id
    assert dialogue_response.cause_id == dialogue_request.id
    assert turn.cause_id == dialogue_response.id
    assert set(turn.payload["latency"]) == {"appraisal_s", "first_token_s", "response_s", "total_s"}


async def test_appraisal_request_uses_schema_and_profile(tmp_path):
    """D1-19: el appraisal pide `json_schema`, con el perfil de la entidad; el diálogo usa la temperatura del ánimo."""
    orchestrator, _, _, bodies, _ = await run_turn(tmp_path)
    appraisal_body, dialogue_body = bodies

    assert appraisal_body["response_format"]["type"] == "json_schema"
    assert "Prueba, artista de Santiago." in appraisal_body["messages"][0]["content"]
    assert "response_format" not in dialogue_body
    assert FEELINGS_HEADER in dialogue_body["messages"][0]["content"]
    assert 0.5 <= dialogue_body["temperature"] <= 0.85


async def test_hostile_message_lowers_mood_and_does_not_relieve_social(tmp_path):
    """Un mensaje hostil baja la valencia, sube la alerta y casi no alivia la necesidad social."""
    orchestrator, before, events, _, _ = await run_turn(tmp_path, appraisal_reply={**NEUTRAL_APPRAISAL, **{
        "user_emotion": {"valence": -0.7, "arousal": 0.8, "dominance": 0.7},
        "hostility": 0.9, "goal_congruence": -0.8,
    }})
    after = orchestrator.state

    assert after.affect.valence < before.affect.valence - 0.4
    assert after.affect.arousal > before.affect.arousal
    # Con hostilidad 0,9 el contacto alivia solo 0,15 · 0,1 = 0,015 (frente a 0,15 de un mensaje neutro).
    affect = next(e for e in events if e.type == "affect.updated" and e.payload["source"] == "appraisal")
    assert affect.payload["drive_relief"]["social"] == pytest.approx(0.15 * (1 - 0.9))
    assert after.drives["social"] == pytest.approx(before.drives["social"] - 0.015, abs=1e-3)


async def test_warm_message_relieves_social_and_lifts_mood(tmp_path):
    """Un mensaje cálido alivia `social`, y ese alivio sube la valencia (acople de Solms)."""
    orchestrator, before, events, _, _ = await run_turn(tmp_path, appraisal_reply={**NEUTRAL_APPRAISAL, **{
        "user_emotion": {"valence": 0.8, "arousal": 0.5, "dominance": 0.6}, "goal_congruence": 0.5,
    }})
    affect = next(e for e in events if e.type == "affect.updated" and e.payload["source"] == "appraisal")

    assert orchestrator.state.drives["social"] < before.drives["social"]
    assert affect.payload["valence_from_drives"] > 0
    assert orchestrator.state.affect.valence > before.affect.valence


async def test_sarcasm_correction_is_reported(tmp_path):
    """La corrección del sarcasmo queda en `appraisal.completed` y en `affect.updated`."""
    _, _, events, _, _ = await run_turn(tmp_path, appraisal_reply={**NEUTRAL_APPRAISAL, **{
        "user_emotion": {"valence": 0.9, "arousal": 0.5, "dominance": 0.6}, "hostility": 0.9,
    }})
    completed = next(e for e in events if e.type == "appraisal.completed")

    assert completed.payload["corrections"]
    assert completed.payload["appraisal"]["user_emotion"]["valence"] == pytest.approx(-0.45)


async def test_invalid_appraisal_does_not_break_the_turn(tmp_path):
    """JSON roto → `appraisal.invalid`, appraisal neutro y la respuesta llega igual."""
    orchestrator, _, events, _, pieces = await run_turn(tmp_path, appraisal_reply="esto no es json")
    types = [event.type for event in events]

    assert "appraisal.invalid" in types and "appraisal.completed" not in types
    assert pieces == ["Ho", "la"]
    assert "turn.completed" in types
    assert len(orchestrator.state.recent_turns) == 1


async def test_recent_turns_enter_the_prompt_and_are_capped(tmp_path):
    """El turno siguiente ve los anteriores; se guardan solo los últimos 6 (D1-24) y se persisten."""
    orchestrator, _, _, bodies, _ = await run_turn(tmp_path, turns=RECENT_TURNS + 2)
    last_dialogue = [body for body in bodies if "response_format" not in body][-1]
    roles = [message["role"] for message in last_dialogue["messages"]]

    assert len(orchestrator.state.recent_turns) == RECENT_TURNS
    assert orchestrator.state.recent_turns[0].user == "hola 2"
    assert roles.count("assistant") == RECENT_TURNS
    saved = EntityManager(tmp_path, EventBus()).load("prueba").state
    assert [turn.user for turn in saved.recent_turns] == [turn.user for turn in orchestrator.state.recent_turns]
