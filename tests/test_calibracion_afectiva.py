"""
Pruebas de la calibración afectiva (Fase 1, CP10b parte B).

- Saturación suave (D1-79): lejos del extremo no cambia nada; cerca, amortigua;
  en sentido contrario, no frena.
- Empatía (D1-80): zona muerta ante mensajes neutros y modulación por confianza.
- Contexto en el appraisal (D1-78): sin contexto, la llamada es idéntica a la
  de antes; con contexto, lleva el intercambio previo; el orquestador lo pasa.
"""

import pytest
from fake_llm import NEUTRAL_APPRAISAL, turn_transport

import ebica.affect.vad as vad
from ebica.affect.appraisal_effects import affect_impulse
from ebica.affect.vad import VAD, apply_impulse, apply_soft_impulse, soften
from ebica.core.events import EventBus
from ebica.core.orchestrator import Orchestrator
from ebica.core.state import EntityConfig
from ebica.entities.manager import EntityManager
from ebica.identity.traits import Traits, derive_parameters
from ebica.llm.client import LLMClient
from ebica.perception.appraisal import Appraisal, build_appraisal_messages

CALISTO = derive_parameters(Traits(O=0.95, C=0.30, E=0.85, A=0.40, N=0.75))


def appraisal(valence=0.0, **values) -> Appraisal:
    """Un appraisal neutro con la valencia de quien habla y otros campos."""
    data = {**NEUTRAL_APPRAISAL, **values,
            "user_emotion": {**NEUTRAL_APPRAISAL["user_emotion"], "valence": valence}}
    return Appraisal.model_validate(data)


# ------------------------------------------------------------ D1-79


@pytest.mark.parametrize(
    ("value", "delta", "expected"),
    [
        (0.0, -0.3, -0.3),            # en el centro, entero
        (-0.5, -0.4, -0.4 * 0.75),    # a mitad de camino, el 75 %
        (-0.9, -0.3, -0.3 * 0.19),    # cerca del fondo, el 19 %
        (-1.0, -0.3, 0.0),            # en el fondo, nada
        (-0.9, 0.3, 0.3),             # hacia el otro lado, entero
        (0.8, 0.2, 0.2 * 0.36),       # lo mismo hacia arriba
    ],
)
def test_soften_valence(value, delta, expected):
    """El impulso hacia un extremo se multiplica por 1 − d²; el que se aleja no se toca."""
    assert soften(value, delta, -1.0, 1.0) == pytest.approx(expected)


def test_soften_on_a_zero_to_one_range():
    """En la alerta (0–1) el centro es 0,5: desde ahí hacia 1 se amortigua; bajo 0,5, no."""
    assert soften(0.5, 0.25, 0.0, 1.0) == pytest.approx(0.25)
    assert soften(0.9, 0.25, 0.0, 1.0) == pytest.approx(0.25 * (1 - 0.8 ** 2))
    assert soften(0.3, 0.25, 0.0, 1.0) == pytest.approx(0.25)


def test_soft_impulse_does_not_get_stuck_at_the_floor():
    """Tres insultos seguidos desde el reposo ya no clavan la valencia en −1 (con recorte duro, sí)."""
    hard = soft = VAD(valence=-0.04, arousal=0.47, dominance=0.42)
    for _ in range(3):
        hard = apply_impulse(hard, valence=-0.5, arousal=0.25, dominance=-0.2)
        soft = apply_soft_impulse(soft, valence=-0.5, arousal=0.25, dominance=-0.2)

    assert hard.valence == -1.0 and hard.arousal == 1.0
    assert -1.0 < soft.valence < -0.6 and soft.arousal < 1.0


def test_soft_saturation_switch(monkeypatch):
    """Con el interruptor apagado, el impulso de una vivencia vuelve a sumarse y recortarse."""
    monkeypatch.setattr(vad, "SOFT_SATURATION", False)
    state = VAD(valence=-0.9, arousal=0.5, dominance=0.5)

    assert apply_soft_impulse(state, valence=-0.3) == apply_impulse(state, valence=-0.3)


# ------------------------------------------------------------ D1-80


def test_no_contagion_from_a_neutral_message():
    """Zona muerta: con la entidad en −1 y un «Hola» neutro (0,1), la empatía no la sube."""
    floor = VAD(valence=-1.0, arousal=0.9, dominance=0.1)

    assert affect_impulse(appraisal(valence=0.1), floor, CALISTO).valence_from_empathy == 0.0
    assert affect_impulse(appraisal(valence=0.3), floor, CALISTO).valence_from_empathy > 0.0


def test_empathy_scales_with_trust():
    """π × (0,5 + 0,5·confianza): Ricardo (0,40) ×0,70 y Ana (0,20) ×0,60 frente a la confianza plena."""
    sad = appraisal(valence=-0.8)
    full = affect_impulse(sad, VAD(), CALISTO, trust=1.0).valence_from_empathy

    assert affect_impulse(sad, VAD(), CALISTO, trust=0.4).valence_from_empathy == pytest.approx(full * 0.7)
    assert affect_impulse(sad, VAD(), CALISTO, trust=0.2).valence_from_empathy == pytest.approx(full * 0.6)
    assert full == pytest.approx(0.5 * CALISTO.pi_empathy * (-0.8 - 0.0))  # sin personas, la fórmula de D1-23


# ------------------------------------------------------------ D1-78


def test_appraisal_without_context_is_unchanged():
    """Sin contexto, la llamada es la de siempre: el benchmark congelado de CP1 sigue valiendo."""
    messages = build_appraisal_messages("Calisto", "Perfil.", "hola")

    assert messages[1] == {"role": "user", "content": 'Mensaje: "hola"'}
    assert build_appraisal_messages("Calisto", "Perfil.", "hola", ("a", "b"))[0] == messages[0]


def test_appraisal_with_context_carries_the_previous_exchange():
    """Con contexto, el mensaje lleva el intercambio anterior y pide evaluar solo el mensaje nuevo."""
    content = build_appraisal_messages(
        "Calisto", "Perfil.", "¿Qué más te dijo?", ("¿Conociste a Ana?", "Sí. Me dijo que era desagradable.")
    )[1]["content"]

    assert 'Quien escribe: "¿Conociste a Ana?"' in content
    assert 'Calisto: "Sí. Me dijo que era desagradable."' in content
    assert content.endswith('Mensaje: "¿Qué más te dijo?"')
    assert "Evalúa solo el mensaje siguiente" in content


async def test_orchestrator_passes_the_last_exchange_to_the_appraisal(tmp_path):
    """El primer turno no lleva contexto; el segundo, el intercambio anterior con la misma persona."""
    bus = EventBus()
    manager = EntityManager(tmp_path, bus)
    entity = manager.create(EntityConfig(id="prueba", name="Prueba", persona="Soy Prueba.",
                                         appraisal_profile="Prueba, artista."))
    transport, bodies = turn_transport("Ho", "la")
    async with LLMClient(bus, transport=transport) as llm:
        orchestrator = Orchestrator(entity, bus, manager.save_state, llm=llm)
        orchestrator.wake()
        for text in ["¿Conociste a Ana?", "¿Qué más te dijo?"]:
            _ = [piece async for piece in orchestrator.user_turn(text)]
    appraisals = [body["messages"][1]["content"] for body in bodies if "response_format" in body]

    assert appraisals[0] == 'Mensaje: "¿Conociste a Ana?"'
    assert 'Quien escribe: "¿Conociste a Ana?"' in appraisals[1] and 'Prueba: "Hola"' in appraisals[1]
