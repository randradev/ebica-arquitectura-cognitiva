"""
Pruebas del esquema y del prompt de appraisal (Fase 1, CP1). No usan GPU.
"""

import json

import pytest

from ebica.perception.appraisal import (
    AppraisalError,
    appraisal_json_schema,
    build_appraisal_messages,
    parse_appraisal,
)


def valid_payload(**overrides) -> dict:
    """Devuelve una salida de appraisal válida, con los campos que se quieran cambiar."""
    payload = {
        "user_emotion": {"valence": -0.4, "arousal": 0.6, "dominance": 0.3},
        "user_intent": "desahogarse",
        "topics": ["trabajo"],
        "hostility": 0.0,
        "distress": 0.7,
        "self_relevance": 0.1,
        "goal_congruence": 0.0,
        "novelty": 0.4,
        "commitments": [],
        "mentioned_people": [{"name": None, "relation": "jefe"}],
    }
    payload.update(overrides)
    return payload


def test_parses_valid_output():
    """Una salida completa se convierte en un `Appraisal` con sus valores."""
    appraisal = parse_appraisal(json.dumps(valid_payload()))

    assert appraisal.distress == 0.7
    assert appraisal.user_emotion.valence == -0.4
    assert appraisal.mentioned_people[0].relation == "jefe"


def test_out_of_range_values_are_clamped():
    """Los números fuera de rango se recortan al límite en lugar de rechazarse."""
    payload = valid_payload(hostility=1.4, goal_congruence=-3)
    payload["user_emotion"]["valence"] = -1.5

    appraisal = parse_appraisal(json.dumps(payload))

    assert appraisal.hostility == 1.0
    assert appraisal.goal_congruence == -1.0
    assert appraisal.user_emotion.valence == -1.0


def test_missing_field_gives_readable_error():
    """Si falta un campo pedido, el error nombra el campo."""
    payload = valid_payload()
    del payload["distress"]

    with pytest.raises(AppraisalError, match="distress"):
        parse_appraisal(json.dumps(payload))


def test_non_numeric_value_is_rejected():
    """Un texto donde va un número no se recorta: es un error."""
    with pytest.raises(AppraisalError, match="hostility"):
        parse_appraisal(json.dumps(valid_payload(hostility="mucha")))


def test_broken_json_gives_clear_error():
    """Una salida que no es JSON produce `AppraisalError`, no una excepción genérica."""
    with pytest.raises(AppraisalError, match="no es JSON"):
        parse_appraisal('{"hostility": 0.2,')


def test_extra_keys_are_ignored():
    """Las claves que el modelo añade sin que se pidan se descartan."""
    appraisal = parse_appraisal(json.dumps(valid_payload(sarcasm=0.8)))

    assert not hasattr(appraisal, "sarcasm")


def test_person_without_relation_gets_default():
    """Al validar, una persona sin `relation` no invalida todo el appraisal."""
    appraisal = parse_appraisal(json.dumps(valid_payload(mentioned_people=[{"name": "Rosa"}])))

    assert appraisal.mentioned_people[0].relation == ""


def test_json_schema_declares_ranges_and_required_fields():
    """El esquema enviado al servidor declara rangos y exige todos los campos de Fase 1."""
    schema = appraisal_json_schema()

    assert schema["properties"]["hostility"] == {"type": "number", "minimum": 0, "maximum": 1, "title": "Hostility"}
    assert schema["properties"]["goal_congruence"]["minimum"] == -1
    assert set(schema["required"]) == {
        "user_emotion", "user_intent", "topics", "hostility", "distress",
        "self_relevance", "goal_congruence", "novelty", "commitments", "mentioned_people",
    }
    assert schema["$defs"]["MentionedPerson"]["required"] == ["name", "relation"]


def test_messages_include_profile_and_keep_user_text_separate():
    """El perfil va en el sistema; el mensaje del usuario va en su propio rol."""
    messages = build_appraisal_messages("Inés", "Afinadora de pianos.", "hola")

    assert [m["role"] for m in messages] == ["system", "user"]
    assert "Afinadora de pianos." in messages[0]["content"]
    assert "Inés" in messages[0]["content"]
    assert messages[1]["content"] == 'Mensaje: "hola"'


def test_prompt_examples_are_valid_appraisals():
    """Los ejemplos del prompt cumplen el esquema (un ejemplo inválido enseñaría mal al modelo)."""
    system = build_appraisal_messages("Inés", "Perfil.", "x")[0]["content"]
    examples = [line for line in system.splitlines() if line.startswith("{")]

    assert len(examples) == 3
    for example in examples:
        parse_appraisal(example)
