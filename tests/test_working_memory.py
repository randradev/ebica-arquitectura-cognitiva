"""
Pruebas de la WorkingMemory (Fase 1, CP9 parte A): presupuesto, saliencia y desalojo.

Funciones puras, sin LLM ni Neo4j. Los textos se arman con un número conocido de
palabras, así los tokens estimados (1,6 por palabra) son exactos.
"""

import pytest

from ebica.llm.tokens import estimate_tokens
from ebica.workspace.working_memory import (
    BASE_BUDGET_TOKENS,
    WorkspaceItem,
    select,
    turn_relevance,
    workspace_budget,
)


def item(key, kind="memory", words=10, relevance=0.5, valence=0.0, order=0) -> WorkspaceItem:
    """Un ítem con `words` palabras (16 tokens por cada 10 palabras)."""
    return WorkspaceItem(kind=kind, key=key, text=" ".join(["palabra"] * words),
                         relevance=relevance, valence=valence, order=order)


@pytest.mark.parametrize(
    ("arousal", "expected"),
    [(0.2, BASE_BUDGET_TOKENS), (0.6, 2500), (0.8, 1875), (1.0, 1250), (1.3, 1250)],
)
def test_budget_shrinks_with_high_arousal(arousal, expected):
    """D1-62: igual hasta una alerta de 0,6; después baja linealmente hasta la mitad con alerta 1,0."""
    assert workspace_budget(arousal) == expected


def test_turn_relevance_decays_with_age():
    """D1-63: el penúltimo intercambio vale 0,9, el anterior 0,81."""
    assert turn_relevance(1) == pytest.approx(0.9)
    assert turn_relevance(2) == pytest.approx(0.81)


def test_charged_item_beats_neutral_with_same_relevance():
    """§5.6: con la misma relevancia, el recuerdo cargado afectivamente es más saliente."""
    neutral, painful = item("neutro", valence=0.0), item("doloroso", valence=-0.8)

    assert painful.salience == pytest.approx(0.5 * 1.8)
    assert painful.salience > neutral.salience
    chosen = select([neutral, painful], budget=painful.tokens)
    assert [i.key for i in chosen.kept] == ["doloroso"]
    assert [i.key for i in chosen.evicted] == ["neutro"]


def test_small_budget_evicts_the_least_salient_first():
    """Con poco presupuesto se va primero lo menos saliente; lo usado nunca supera el presupuesto."""
    items = [item("a", relevance=0.9), item("b", relevance=0.3), item("c", relevance=0.6)]

    chosen = select(items, budget=2 * items[0].tokens)

    assert {i.key for i in chosen.kept} == {"a", "c"}
    assert [i.key for i in chosen.evicted] == ["b"]
    assert chosen.used <= chosen.budget


def test_plenty_of_budget_keeps_everything_in_natural_order():
    """Sin presión no se desaloja nada, y lo que entra conserva su orden natural (no el de saliencia)."""
    items = [item("t2", kind="turn", relevance=0.81, order=0), item("t1", kind="turn", relevance=0.9, order=1),
             item("m-poco", relevance=0.2, order=1), item("m-mucho", relevance=0.7, order=0),
             item("f", kind="fact", relevance=0.6)]

    chosen = select(items, budget=10_000)

    assert chosen.evicted == []
    assert [i.key for i in chosen.of_kind("turn")] == ["t2", "t1"]
    assert [i.key for i in chosen.of_kind("memory")] == ["m-mucho", "m-poco"]
    assert chosen.used == sum(i.tokens for i in items)


def test_a_shorter_item_can_fill_the_gap():
    """Si el siguiente más saliente no cabe, uno menos saliente pero más corto puede entrar."""
    long_one, short_one = item("largo", words=50, relevance=0.8), item("corto", words=5, relevance=0.4)
    first = item("primero", words=40, relevance=0.9)

    chosen = select([first, long_one, short_one], budget=first.tokens + short_one.tokens)

    assert {i.key for i in chosen.kept} == {"primero", "corto"}
    assert [i.key for i in chosen.evicted] == ["largo"]


def test_event_payload_has_no_text():
    """`wm.updated` lleva saliencias y tokens, no el texto (puede ser una conversación)."""
    chosen = select([item("a", valence=0.5)], budget=1000)

    payload = chosen.as_dict()
    assert payload["budget"] == 1000 and payload["used"] == estimate_tokens(" ".join(["palabra"] * 10))
    assert payload["kept"][0] == {"kind": "memory", "key": "a", "tokens": 16, "relevance": 0.5,
                                  "valence": 0.5, "salience": 0.75}
    assert "text" not in payload["kept"][0]
