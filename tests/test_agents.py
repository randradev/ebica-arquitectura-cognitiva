"""
Pruebas de los micro-agentes (Fase 1, CP10 parte A), con pizarras sintéticas.

Cada micro-agente emite su señal al pasar el umbral y nada por debajo; ninguno
puede modificar la foto; `hostility_watch` da lo mismo que la vía baja de CP5.
"""

import dataclasses
import math
from datetime import datetime, timedelta, timezone

import pytest

from ebica.affect.low_road import evaluate as evaluate_low_road
from ebica.perception.appraisal import neutral_appraisal
from ebica.workspace.agents import (
    Board,
    OpenCommitment,
    commitment_watch,
    distress_watch,
    homeostasis_watch,
    hostility_watch,
    repetition_watch,
    run_agents,
)

NOW = datetime(2026, 10, 28, 20, 0, tzinfo=timezone.utc)


def vec(*values: float) -> tuple[float, ...]:
    """Vector normalizado a partir de sus componentes."""
    norm = math.sqrt(sum(v * v for v in values))
    return tuple(v / norm for v in values)


def at_cosine(c: float) -> tuple[float, ...]:
    """Un vector cuyo coseno con (1, 0) es exactamente `c`."""
    return (c, math.sqrt(1 - c * c))


BASE = (1.0, 0.0)


# ------------------------------------------------------------ contrato


def test_board_is_read_only():
    """D1-69: la foto no se puede modificar, ni sus campos ni el contenido de los drives."""
    board = Board(now=NOW, drives={"social": 0.5})

    with pytest.raises(dataclasses.FrozenInstanceError):
        board.text = "otra cosa"
    with pytest.raises(TypeError):
        board.drives["social"] = 1.0


def test_signal_payload():
    """Una señal se serializa para `agent.signal` con su intensidad redondeada."""
    [signal] = distress_watch.observe(Board(now=NOW, partner_id="ana",
                                            appraisal=neutral_appraisal().model_copy(update={"distress": 0.8123})))
    assert signal.as_dict() == {"agent": "distress_watch", "kind": "attend_partner", "strength": 0.812,
                                "target": "ana", "data": {"factor": 1.5}}


# ------------------------------------------------------------ hostility_watch


@pytest.mark.parametrize("text", ["Callate mierda", "eres una inútil", "te voy a borrar", "hola, ¿cómo estás?",
                                  "mi jefe es un idiota"])
def test_hostility_watch_matches_the_low_road(text):
    """D1-70: mismo puntaje que la vía baja de CP5; señal solo si se dispara."""
    board = Board(now=NOW, text=text, theta_low_road=0.575)
    expected = evaluate_low_road(text, 0.575)

    assert hostility_watch.evaluate(board) == expected
    signals = hostility_watch.observe(board)
    assert bool(signals) == expected.triggered
    if signals:
        assert signals[0].kind == "alarm" and signals[0].strength == expected.score


# ------------------------------------------------------------ distress_watch


@pytest.mark.parametrize(("distress", "fires"), [(0.59, False), (0.6, True), (0.9, True)])
def test_distress_watch_threshold(distress, fires):
    """D1-71: angustia ≥ 0,6 → `attend_partner` con el factor de la pizarra; menos, nada."""
    board = Board(now=NOW, partner_id="ana", appraisal=neutral_appraisal().model_copy(update={"distress": distress}))

    assert bool(distress_watch.observe(board)) == fires
    assert distress_watch.observe(Board(now=NOW)) == []  # sin appraisal (p. ej. falló), nada


# ------------------------------------------------------------ homeostasis_watch


def test_homeostasis_watch_only_on_upward_crossing():
    """D1-75: señal al cruzar 0,7 hacia arriba; ni por quedarse arriba ni por bajar."""
    board = Board(now=NOW, drives_before={"social": 0.69, "novelty": 0.8, "rest": 0.9},
                  drives={"social": 0.71, "novelty": 0.85, "rest": 0.6})

    [signal] = homeostasis_watch.observe(board)
    assert (signal.kind, signal.target, signal.strength) == ("pressure", "social", 0.71)


# ------------------------------------------------------------ commitment_watch


def test_commitment_strength_halves_every_week():
    """D1-74: intensidad = w_commit · 0,5^(días/7)."""
    assert commitment_watch.strength(0, 0.8) == pytest.approx(0.8)
    assert commitment_watch.strength(7, 0.8) == pytest.approx(0.4)
    assert commitment_watch.strength(14, 0.8) == pytest.approx(0.2)


def test_commitment_watch_keeps_recent_promises_and_lets_old_ones_fade():
    """Las promesas recientes se señalan (de más a menos intensa); bajo 0,2 se desvanecen."""
    commitments = (
        OpenCommitment("c-vieja", "contarte del viaje", NOW - timedelta(days=20)),
        OpenCommitment("c-ayer", "contarte cómo me fue en la entrevista", NOW - timedelta(days=1)),
        OpenCommitment("c-hoy", "traerte un dibujo", NOW - timedelta(hours=1)),
    )
    signals = commitment_watch.observe(Board(now=NOW, commitments=commitments, w_commit=0.8))

    assert [s.target for s in signals] == ["c-hoy", "c-ayer"]
    assert signals[1].data["text"] == "contarte cómo me fue en la entrevista"


# ------------------------------------------------------------ repetition_watch


def history(*cosines: float, text="una pregunta larga cualquiera"):
    """Mensajes anteriores de la persona con vectores a un coseno dado de BASE."""
    return tuple((text, at_cosine(c)) for c in cosines)


@pytest.mark.parametrize(("best", "fires"), [(0.84, False), (0.85, True), (1.0, True)])
def test_user_repeats_threshold(best, fires):
    """D1-72: la persona se repite desde 0,85 frente a un mensaje anterior del hilo."""
    board = Board(now=NOW, text="¿A qué ciudad fui el fin de semana?", query_vector=BASE,
                  user_history=history(0.3, best), partner_id="ricardo")

    signals = repetition_watch.observe(board)
    assert bool(signals) == fires
    if fires:
        assert signals[0].kind == "user_repeats" and signals[0].data == {"novelty": 0.15}


def test_short_messages_do_not_count_as_repetition():
    """Un «Sí» repetido no es una conversación repetitiva (mínimo 3 palabras, en los dos mensajes)."""
    assert repetition_watch.observe(Board(now=NOW, text="Sí", query_vector=BASE,
                                          user_history=(("Sí", BASE),))) == []
    assert repetition_watch.observe(Board(now=NOW, text="¿Qué te gusta más?", query_vector=BASE,
                                          user_history=(("Ok", BASE),))) == []


@pytest.mark.parametrize(("best", "fires"), [(0.89, False), (0.90, True), (0.94, True)])
def test_entity_repeats_threshold(best, fires):
    """D1-72: la última respuesta de la entidad se parece ≥ 0,90 a alguna de sus 10 anteriores."""
    board = Board(now=NOW, entity_replies=(at_cosine(best), at_cosine(0.2), BASE))

    assert [s.kind for s in repetition_watch.observe(board)] == (["entity_repeats"] if fires else [])


def test_entity_repetition_window_is_ten_replies():
    """Una respuesta igual a la de hace 11 respuestas ya no cuenta; la de hace 10, sí."""
    others = tuple(vec(0.0, 1.0, float(i)) for i in range(10))

    assert repetition_watch.observe(Board(now=NOW, entity_replies=(BASE, *others, BASE))) == []
    assert repetition_watch.observe(Board(now=NOW, entity_replies=(BASE, *others[1:], BASE)))[0].kind == "entity_repeats"


# ------------------------------------------------------------ conjunto


def test_run_agents_collects_in_fixed_order():
    """`run_agents` corre distress → commitment → repetition, sin la vía baja ni la homeostasis."""
    board = Board(
        now=NOW, text="otra vez la misma pregunta larga", query_vector=BASE, user_history=history(1.0),
        appraisal=neutral_appraisal().model_copy(update={"distress": 0.9}),
        commitments=(OpenCommitment("c-1", "contarte algo", NOW),), w_commit=0.8,
        drives_before={"social": 0.5}, drives={"social": 0.9},
    )

    assert [s.agent for s in run_agents(board)] == ["distress_watch", "commitment_watch", "repetition_watch"]
