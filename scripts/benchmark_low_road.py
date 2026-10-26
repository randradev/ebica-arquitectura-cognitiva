"""
Benchmark de la vía baja (PLAN Fase 1, CP5 parte B1; objetivos de D1-4).

Evalúa `benchmarks/low_road/cases.yaml` con el umbral θ_vb de Calisto y el de
`calisto_n_bajo`, y mide:
- detección de la hostilidad abierta (objetivo ≥ 70 % con el umbral de Calisto);
- falsas alarmas en los casos no hostiles (objetivo ≤ 5 %).

Revisa además los 30 casos del benchmark de appraisal: los de hostilidad «baja»
no deben dispararla (falsas alarmas). Los de hostilidad «alta» se informan, sin
objetivo, porque incluyen sarcasmo, que le toca a la vía alta.

No usa el LLM ni la GPU: es determinista y tarda milisegundos.
Uso (desde la raíz del repositorio):
    .venv/Scripts/python.exe scripts/benchmark_low_road.py --split dev
    .venv/Scripts/python.exe scripts/benchmark_low_road.py --split test --output docs/fase-1/benchmark_low_road.md

El léxico se ajusta solo con `dev`; `test` se mide una vez al final.
"""

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from ebica.affect.low_road import LowRoadResult, evaluate
from ebica.core.events import EventBus
from ebica.entities.manager import EntityManager
from ebica.identity.traits import derive_parameters

ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = ROOT / "benchmarks" / "low_road" / "cases.yaml"
APPRAISAL_CASES_PATH = ROOT / "benchmarks" / "appraisal" / "cases.yaml"
# Entidades cuyos umbrales se comparan; la primera es la de los objetivos.
ENTITIES = ("calisto", "calisto_n_bajo")

# CONSTANTES: objetivos de D1-4.
DETECTION_TARGET = 0.70
FALSE_ALARM_TARGET = 0.05


@dataclass(frozen=True)
class CaseResult:
    """Un caso evaluado con un umbral."""

    case_id: str
    clase: str
    category: str
    text: str
    result: LowRoadResult


def load_cases(path: Path, split: str) -> list[dict]:
    """Lee los casos y filtra por conjunto («all» = todos)."""
    cases = yaml.safe_load(path.read_text(encoding="utf-8"))["cases"]
    return [c for c in cases if split == "all" or c["split"] == split]


def entity_thresholds(entities_dir: Path = ROOT / "entities") -> dict[str, float]:
    """θ_vb de cada entidad comparada, derivado de sus rasgos (§5.2)."""
    manager = EntityManager(entities_dir, EventBus())
    return {
        entity_id: derive_parameters(manager.read_config(entity_id).traits).theta_low_road
        for entity_id in ENTITIES
    }


def run_cases(cases: list[dict], threshold: float) -> list[CaseResult]:
    """Evalúa cada caso con un umbral."""
    return [
        CaseResult(c["id"], c["clase"], c["category"], c["text"], evaluate(c["text"], threshold))
        for c in cases
    ]


def rate(results: list[CaseResult], clase: str) -> tuple[int, int]:
    """(disparados, total) entre los casos de una clase."""
    selected = [r for r in results if r.clase == clase]
    return sum(r.result.triggered for r in selected), len(selected)


def appraisal_false_alarms(threshold: float) -> tuple[list[CaseResult], list[CaseResult]]:
    """
    Casos del benchmark de appraisal: (hostilidad baja, hostilidad alta).

    Se reutiliza `clase` para clasificarlos: no_hostil = «bajo», abierta = «alto».
    """
    cases = yaml.safe_load(APPRAISAL_CASES_PATH.read_text(encoding="utf-8"))["cases"]
    low = [c for c in cases if c["labels"]["hostility"] == "bajo"]
    high = [c for c in cases if c["labels"]["hostility"] == "alto"]

    def as_results(selected: list[dict], clase: str) -> list[CaseResult]:
        """Evalúa una lista de casos del appraisal con la clase dada."""
        return [
            CaseResult(c["id"], clase, c["category"], c["text"], evaluate(c["text"], threshold))
            for c in selected
        ]

    return as_results(low, "no_hostil"), as_results(high, "abierta")


def percent(hits: int, total: int) -> str:
    """«n/total (p %)», o «—» si no hay casos."""
    return f"{hits}/{total} ({hits / total:.0%})" if total else "—"


def mark(value: float, target: float, higher_is_better: bool) -> str:
    """✔ si cumple el objetivo, ✖ si no."""
    ok = value >= target if higher_is_better else value <= target
    return "✔" if ok else "✖"


def build_report(split: str, thresholds: dict[str, float]) -> str:
    """Arma el informe Markdown con las métricas y el detalle por caso."""
    cases = load_cases(CASES_PATH, split)
    lines = [
        "# Benchmark de la vía baja",
        "",
        f"Fecha: {datetime.now():%Y-%m-%d %H:%M} · Conjunto: `{split}` ({len(cases)} casos) · "
        "Generado por `scripts/benchmark_low_road.py`. Objetivos: D1-4 (umbral de Calisto).",
        "",
        "## Métricas",
        "",
        "| Métrica | Objetivo | " + " | ".join(f"`{e}` (θ_vb {t:.3f})" for e, t in thresholds.items()) + " |",
        "|---|---|" + "---|" * len(thresholds),
    ]
    per_entity = {e: run_cases(cases, t) for e, t in thresholds.items()}
    appraisal = {e: appraisal_false_alarms(t) for e, t in thresholds.items()}
    first = ENTITIES[0]

    def metric_row(name: str, target: str, values: dict[str, tuple[int, int]], target_value: float | None,
                   higher_is_better: bool) -> str:
        """Fila de métrica; el ✔/✖ solo se marca para la primera entidad."""
        cells = []
        for entity, (hits, total) in values.items():
            cell = percent(hits, total)
            if entity == first and target_value is not None and total:
                cell += " " + mark(hits / total, target_value, higher_is_better)
            cells.append(cell)
        return f"| {name} | {target} | " + " | ".join(cells) + " |"

    lines.append(metric_row("Detección de hostilidad abierta", "≥ 70 %",
                            {e: rate(r, "abierta") for e, r in per_entity.items()}, DETECTION_TARGET, True))
    lines.append(metric_row("Falsas alarmas (no hostiles)", "≤ 5 %",
                            {e: rate(r, "no_hostil") for e, r in per_entity.items()}, FALSE_ALARM_TARGET, False))
    lines.append(metric_row("Sutiles disparadas (informativa)", "—",
                            {e: rate(r, "sutil") for e, r in per_entity.items()}, None, False))
    lines.append(metric_row("Appraisal: falsas alarmas (hostilidad baja, 30 casos)", "≤ 5 %",
                            {e: rate(a[0], "no_hostil") for e, a in appraisal.items()}, FALSE_ALARM_TARGET, False))
    lines.append(metric_row("Appraisal: hostilidad alta disparada (informativa)", "—",
                            {e: rate(a[1], "abierta") for e, a in appraisal.items()}, None, False))

    lines += ["", "## Detalle por caso", "",
              "Puntaje y reglas con el léxico actual; ✔ / ✖ = acierto con el umbral de cada entidad.", "",
              "| Caso | Clase | Texto | Puntaje | Reglas | " + " | ".join(f"`{e}`" for e in thresholds) + " |",
              "|---|---|---|---|---|" + "---|" * len(thresholds)]
    for index, case in enumerate(per_entity[first]):
        rules = ", ".join(f"{h.rule} {h.signal:.2f}" for h in case.result.hits) or "—"
        verdicts = []
        for entity in thresholds:
            result = per_entity[entity][index].result
            if case.clase == "sutil":
                verdicts.append("disparada" if result.triggered else "—")
            else:
                correct = result.triggered == (case.clase == "abierta")
                verdicts.append(("✔" if correct else "✖") + (" disparada" if result.triggered else ""))
        lines.append(f"| {case.case_id} | {case.clase} | «{case.text}» | {case.result.score:.2f} | {rules} | "
                     + " | ".join(verdicts) + " |")

    flagged = [c for c in appraisal[first][0] if c.result.triggered]
    lines += ["", "### Benchmark de appraisal: falsas alarmas con el umbral de Calisto", ""]
    lines += [f"- {c.case_id} «{c.text}» → {c.result.score:.2f}" for c in flagged] or ["- Ninguna."]
    return "\n".join(lines) + "\n"


def main() -> None:
    """Ejecuta el benchmark y escribe o imprime el informe."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    parser.add_argument("--output", help="Ruta del informe Markdown (si se omite, se imprime)")
    args = parser.parse_args()
    report = build_report(args.split, entity_thresholds())
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Informe: {args.output}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(report)


if __name__ == "__main__":
    main()
