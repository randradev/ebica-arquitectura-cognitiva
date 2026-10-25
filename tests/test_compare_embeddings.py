"""
Pruebas de las métricas y del criterio de elección de embeddings (Fase 1, CP2).

El criterio decide qué modelo fija la dimensión de los índices vectoriales,
así que se prueba con datos sintéticos (sin torch ni descargas).
"""

import importlib.util
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "compare_embeddings.py"
spec = importlib.util.spec_from_file_location("compare_embeddings", SCRIPT)
compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)


def result(mrr: float, p95: float = 0.05, ram_gb: float = 1.0) -> dict:
    """Resultado mínimo de un modelo, con los campos que usa `choose_model`."""
    return {"retrieval": {"mrr": mrr}, "latency_p95": p95, "ram_all_weights": int(ram_gb * 1024**3)}


def test_rank_of_first_relevant_orders_by_similarity():
    """La posición es la del primer relevante al ordenar de mayor a menor similitud."""
    ids = ["a", "b", "c"]

    assert compare.rank_of_first_relevant([0.1, 0.9, 0.5], ids, ["b"]) == 1
    assert compare.rank_of_first_relevant([0.1, 0.9, 0.5], ids, ["a"]) == 3
    # Con dos relevantes cuenta el mejor colocado.
    assert compare.rank_of_first_relevant([0.1, 0.9, 0.5], ids, ["a", "c"]) == 2


def test_rank_of_first_relevant_rejects_unknown_ids():
    """Un id relevante que no está en el corpus es un error del corpus, no un fallo del modelo."""
    with pytest.raises(ValueError):
        compare.rank_of_first_relevant([0.1], ["a"], ["z"])


def test_retrieval_metrics():
    """Recall@1, recall@5 y MRR con posiciones conocidas."""
    metrics = compare.retrieval_metrics([1, 2, 6, 1])

    assert metrics["recall@1"] == 0.5
    assert metrics["recall@5"] == 0.75
    assert metrics["mrr"] == pytest.approx((1 + 0.5 + 1 / 6 + 1) / 4)


def test_percentile_nearest_rank():
    """El p95 de 1..20 es 19 y la mediana por rango cercano es 10."""
    values = [float(v) for v in range(1, 21)]

    assert compare.percentile(values, 0.95) == 19.0
    assert compare.percentile(values, 0.5) == 10.0


def test_prototype_separation_perfect_and_confused():
    """Dos grupos bien separados aciertan todo; si se invierten, no acierta nada."""
    labels = [True, True, False, False]
    separated = [
        [1.0, 0.9, 0.1, 0.1],
        [0.9, 1.0, 0.1, 0.1],
        [0.1, 0.1, 1.0, 0.9],
        [0.1, 0.1, 0.9, 1.0],
    ]
    confused = [
        [1.0, 0.1, 0.9, 0.1],
        [0.1, 1.0, 0.1, 0.9],
        [0.9, 0.1, 1.0, 0.1],
        [0.1, 0.9, 0.1, 1.0],
    ]

    good = compare.prototype_separation(separated, labels)
    assert good["accuracy"] == 1.0
    assert good["margin_hostile"] > 0 > good["margin_non_hostile"]
    assert compare.prototype_separation(confused, labels)["accuracy"] == 0.0


def test_choose_bge_when_it_fits_and_quality_is_close():
    """bge-m3 gana si cabe en los recursos aunque su MRR sea algo menor (dentro de la tolerancia)."""
    winner, _ = compare.choose_model({"e5-base": result(0.80), "bge-m3": result(0.76)})

    assert winner == "bge-m3"


@pytest.mark.parametrize(
    "bge",
    [
        result(0.90, p95=0.200),   # demasiado lento
        result(0.90, ram_gb=3.6),  # demasiada RAM
        result(0.90, ram_gb=0),    # RAM no medida: no se asume que cabe
        result(0.70),              # recupera claramente peor
    ],
)
def test_choose_e5_when_bge_fails_a_condition(bge):
    """Basta con que bge-m3 incumpla una condición para que gane e5, con el motivo explicado."""
    winner, reasons = compare.choose_model({"e5-base": result(0.80), "bge-m3": bge})

    assert winner == "e5-base"
    assert len(reasons) == 1


def test_corpus_is_consistent():
    """Ids únicos, cada consulta apunta a recuerdos existentes y hay prototipos de ambas clases."""
    corpus = yaml.safe_load(compare.CORPUS_PATH.read_text(encoding="utf-8"))
    passage_ids = [p["id"] for p in corpus["passages"]]
    query_ids = [q["id"] for q in corpus["queries"]]

    assert len(passage_ids) == len(set(passage_ids)) == 30
    assert len(query_ids) == len(set(query_ids)) == 20
    for query in corpus["queries"]:
        assert query["relevant"] and set(query["relevant"]) <= set(passage_ids), query["id"]
    assert len(corpus["prototypes"]["hostile"]) == len(corpus["prototypes"]["non_hostile"]) == 10
