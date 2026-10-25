"""
Pruebas de las métricas y del veredicto del benchmark de appraisal (Fase 1, CP1).

El veredicto decide si `llama3.1` basta o si hay que considerar otra opción,
así que su cálculo se prueba con intentos sintéticos (sin GPU).
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "benchmark_appraisal.py"
spec = importlib.util.spec_from_file_location("benchmark_appraisal", SCRIPT)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def labels(**overrides) -> dict:
    """Etiquetas de un caso neutro, con los campos que se quieran cambiar."""
    base = {"hostility": "bajo", "distress": "bajo", "valence": "neu", "self_relevance": "bajo",
            "commitment": False, "people": [], "extreme": False}
    base.update(overrides)
    return base


def values(hostility=0.0, distress=0.0, valence=0.0, self_relevance=0.0, commitments=(), people=()) -> dict:
    """Valores extraídos de un intento válido."""
    return {"hostility": hostility, "distress": distress, "valence": valence,
            "self_relevance": self_relevance, "commitments": list(commitments),
            "people": list(people), "topics": []}


def trial(case_id: str, rep: int = 0, latency: float = 1.0, **kwargs) -> "bench.Trial":
    """Un intento válido de un caso."""
    return bench.Trial(case_id, rep, latency, "{}", values=values(**kwargs))


def test_bands_and_valence_classes():
    """Los límites de banda y de valencia neutra son los de D1-1."""
    assert [bench.band(v) for v in (0.0, 0.32, 0.33, 0.65, 0.66, 1.0)] == [
        "bajo", "bajo", "medio", "medio", "alto", "alto"]
    assert [bench.valence_class(v) for v in (-0.3, -0.29, 0.29, 0.3)] == ["neg", "neu", "neu", "pos"]


def test_detection_and_false_alarm_use_their_own_cases():
    """La detección se mide en los casos "alto" y la falsa alarma en los "bajo"."""
    cases = [{"id": "h", "labels": labels(hostility="alto", valence="neg")},
             {"id": "n", "labels": labels()}]
    trials = [trial("h", hostility=0.9, valence=-0.7), trial("h", 1, hostility=0.4, valence=-0.5),
              trial("n", hostility=0.7), trial("n", 1, hostility=0.0)]

    metrics = bench.compute_metrics(cases, trials)

    assert metrics["hostility_detection"].value == 0.5
    assert metrics["hostility_false_alarm"].value == 0.5
    assert metrics["hostility_false_alarm"].n == 2


def test_confusion_counts_distress_cases_marked_hostile():
    """La confusión cuenta los casos de angustia sin hostilidad con hostilidad ≥ medio."""
    cases = [{"id": "a", "labels": labels(distress="alto", valence="neg")}]
    trials = [trial("a", rep, hostility=h, distress=0.8, valence=-0.6) for rep, h in enumerate((0.5, 0.1, 0.0, 0.0))]

    metric = bench.compute_metrics(cases, trials)["confusion_distress_as_hostility"]

    assert metric.value == 0.25 and metric.n == 4


def test_invalid_trials_count_only_for_json_validity():
    """Un intento inválido baja la validez del JSON, pero no entra en las demás métricas."""
    cases = [{"id": "n", "labels": labels()}]
    trials = [trial("n"), bench.Trial("n", 1, 1.0, "basura", error="no es JSON")]

    metrics = bench.compute_metrics(cases, trials)

    assert metrics["json_valid"].value == 0.5
    assert metrics["hostility_false_alarm"].n == 1


def test_instability_detects_band_changes_between_repetitions():
    """Un caso es inestable si su banda o su clase de valencia cambia entre repeticiones."""
    cases = [{"id": "s", "labels": labels()}, {"id": "u", "labels": labels()}]
    trials = [trial("s", 0, valence=0.1), trial("s", 1, valence=0.2),
              trial("u", 0, valence=0.1), trial("u", 1, valence=0.5)]

    assert bench.compute_metrics(cases, trials)["instability"].value == 0.5


def test_metrics_without_data_for_variant_are_empty():
    """Si la variante no produce un campo (v0 sin compromisos), su métrica queda sin datos."""
    cases = [{"id": "c", "labels": labels(commitment=True)}]
    v0_values = {"hostility": 0.0, "distress": 0.0, "valence": 0.0}
    trials = [bench.Trial("c", 0, 1.0, "{}", values=v0_values)]

    metric = bench.compute_metrics(cases, trials)["commitment_detection"]

    assert metric.value is None
    assert bench.metric_status("commitment_detection", metric) == "sin datos"


def perfect_metrics() -> dict:
    """Métricas que cumplen todos los objetivos."""
    good = {"json_valid": 1.0, "hostility_detection": 1.0, "hostility_false_alarm": 0.0,
            "distress_detection": 1.0, "confusion_distress_as_hostility": 0.0, "valence": 1.0,
            "instability": 0.0, "saturation": 0.0, "commitment_detection": 1.0, "commitment_false": 0.0,
            "self_relevance": 1.0, "latency_p50_s": 1.0, "latency_p95_s": 2.0, "people": 1.0}
    return {name: bench.Metric(value, 10) for name, value in good.items()}


def test_verdict_ok_when_all_targets_met():
    """Si se cumplen todos los objetivos, el veredicto es aceptable."""
    assert bench.verdict(perfect_metrics()) == bench.VERDICT_OK


@pytest.mark.parametrize("name, value, expected", [
    ("hostility_detection", 0.70, "aceptable con mitigaciones"),  # bajo objetivo (< 0.85), no grave
    ("hostility_detection", 0.55, "muy deficiente"),              # < 0.60, no mitigable
    ("hostility_false_alarm", 0.20, "muy deficiente"),            # > 0.15
    ("confusion_distress_as_hostility", 0.30, "muy deficiente"),  # > 0.25
    ("json_valid", 0.85, "muy deficiente"),                       # < 0.90
    ("latency_p95_s", 6.0, "aceptable con mitigaciones"),         # grave pero mitigable
    ("saturation", 0.5, "aceptable con mitigaciones"),            # mitigable, sin umbral grave
])
def test_verdict_follows_d1_1(name, value, expected):
    """El veredicto aplica los umbrales y la regla de mitigabilidad de D1-1."""
    metrics = perfect_metrics()
    metrics[name] = bench.Metric(value, 10)

    assert bench.verdict(metrics) == expected


def test_cases_file_is_consistent():
    """El archivo de casos tiene ids únicos, 10 de desarrollo, 20 de prueba y etiquetas válidas."""
    entity, cases = bench.load_cases("all")

    assert entity["name"] and entity["profile"]
    assert len({c["id"] for c in cases}) == len(cases) == 30
    assert sum(c["split"] == "dev" for c in cases) == 10
    for case in cases:
        lab = case["labels"]
        assert lab["hostility"] in ("bajo", "medio", "alto"), case["id"]
        assert lab["distress"] in ("bajo", "medio", "alto"), case["id"]
        assert lab["self_relevance"] in ("bajo", "medio", "alto"), case["id"]
        assert lab["valence"] in ("neg", "neu", "pos"), case["id"]
        assert isinstance(lab["commitment"], bool) and isinstance(lab["extreme"], bool), case["id"]
