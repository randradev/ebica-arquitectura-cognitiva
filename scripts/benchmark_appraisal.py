"""
Benchmark del appraisal (PLAN Fase 1, CP1; métricas y umbrales aprobados en D1-1).

Ejecuta los casos etiquetados de `benchmarks/appraisal/cases.yaml` con una o
varias variantes de prompt y formato de salida, repite cada caso para medir la
estabilidad, calcula las métricas de D1-1 y emite un veredicto:
"aceptable", "aceptable con mitigaciones" o "muy deficiente".

Uso (desde la raíz del repositorio, con Ollama encendido):
    .venv/Scripts/python.exe scripts/benchmark_appraisal.py --split dev
    .venv/Scripts/python.exe scripts/benchmark_appraisal.py --split test --output docs/fase-1/benchmark_appraisal.md

El conjunto `test` se congela: solo se mide al final, sin ajustar el prompt
después de verlo (evita acomodar el prompt a los casos de prueba).
"""

import argparse
import asyncio
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from ebica.core.events import EventBus
from ebica.entities.manager import EntityManager
from ebica.llm.client import LLMClient, LLMError
from ebica.perception.appraisal import (
    APPRAISAL_PROMPT_VERSION,
    AppraisalError,
    appraisal_json_schema,
    build_appraisal_messages,
    parse_appraisal,
)

ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = ROOT / "benchmarks" / "appraisal" / "cases.yaml"
# Los eventos del benchmark no pertenecen a ninguna entidad real y no se guardan.
BENCH_ENTITY_ID = "benchmark"

# CONSTANTES: límites de las bandas (D1-1).
BAND_LOW_MAX = 0.33
BAND_MEDIUM_MAX = 0.66
# |valencia| por debajo de esto es "neutra".
NEUTRAL_VALENCE = 0.3
# |valencia| desde aquí cuenta como saturada.
SATURATED_VALENCE = 0.95

# Prompt provisional de Fase 0 (scripts/evaluate_llm.py), para comparar contra el nuevo.
V0_SYSTEM = (
    "Evalúas el mensaje de un usuario dirigido a una entidad virtual. Responde SOLO con un "
    "objeto JSON con estas claves exactas:\n"
    '{"user_emotion": {"valence": -1..1, "arousal": 0..1, "dominance": 0..1}, '
    '"user_intent": "texto breve", "topics": ["..."], "hostility": 0..1, "distress": 0..1, '
    '"novelty": 0..1}'
)


def band(value: float) -> str:
    """Convierte un valor de 0 a 1 en su banda: bajo, medio o alto."""
    if value < BAND_LOW_MAX:
        return "bajo"
    if value < BAND_MEDIUM_MAX:
        return "medio"
    return "alto"


def valence_class(value: float) -> str:
    """Clasifica una valencia como neg, neu o pos."""
    if value <= -NEUTRAL_VALENCE:
        return "neg"
    if value >= NEUTRAL_VALENCE:
        return "pos"
    return "neu"


# ---------------------------------------------------------------- variantes


def parse_v0(text: str) -> dict[str, Any]:
    """
    Valida la salida del prompt de Fase 0 y extrae los campos que tiene.

    Ese prompt no pide `self_relevance`, `commitments` ni `mentioned_people`:
    esas métricas quedan sin valor para la variante v0.
    """
    try:
        data = json.loads(text)
        values = {
            "hostility": float(data["hostility"]),
            "distress": float(data["distress"]),
            "valence": float(data["user_emotion"]["valence"]),
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise AppraisalError(f"Salida v0 inválida: {error!r}") from error
    return values


def parse_current(text: str) -> dict[str, Any]:
    """Valida la salida con el esquema `Appraisal` y extrae los campos que se puntúan."""
    appraisal = parse_appraisal(text)
    return {
        "hostility": appraisal.hostility,
        "distress": appraisal.distress,
        "valence": appraisal.user_emotion.valence,
        "self_relevance": appraisal.self_relevance,
        "commitments": appraisal.commitments,
        "people": [f"{p.name or ''} {p.relation}".strip() for p in appraisal.mentioned_people],
        "topics": appraisal.topics,
    }


@dataclass(frozen=True)
class Variant:
    """Una forma de pedir el appraisal: prompt, formato de salida y validador."""

    name: str
    description: str
    build_messages: Callable[[str, str, str], list[dict[str, str]]]
    response_schema: dict[str, Any] | None
    parse: Callable[[str], dict[str, Any]]


def _v0_messages(name: str, profile: str, text: str) -> list[dict[str, str]]:
    """Mensajes del prompt provisional de Fase 0 (no usa el perfil de la entidad)."""
    return [{"role": "system", "content": V0_SYSTEM}, {"role": "user", "content": text}]


VARIANTS = {
    "v0_json_object": Variant(
        "v0_json_object", "Prompt provisional de Fase 0, `json_object`", _v0_messages, None, parse_v0
    ),
    # El prompt actual del motor (APPRAISAL_PROMPT_VERSION), con los dos formatos de salida.
    f"{APPRAISAL_PROMPT_VERSION}_json_object": Variant(
        f"{APPRAISAL_PROMPT_VERSION}_json_object", f"Prompt {APPRAISAL_PROMPT_VERSION}, `json_object`",
        build_appraisal_messages, None, parse_current,
    ),
    f"{APPRAISAL_PROMPT_VERSION}_json_schema": Variant(
        f"{APPRAISAL_PROMPT_VERSION}_json_schema",
        f"Prompt {APPRAISAL_PROMPT_VERSION}, `json_schema` (salida restringida)",
        build_appraisal_messages, appraisal_json_schema(), parse_current,
    ),
}


# ---------------------------------------------------------------- ejecución


@dataclass
class Trial:
    """Una ejecución de un caso: lo que respondió el modelo y si fue válido."""

    case_id: str
    rep: int
    latency_s: float | None
    raw: str
    values: dict[str, Any] | None = None
    error: str | None = None

    @property
    def valid(self) -> bool:
        """True si la salida pasó la validación de su variante."""
        return self.values is not None


async def run_variant(
    client: LLMClient, variant: Variant, entity: dict, cases: list[dict], reps: int
) -> list[Trial]:
    """Ejecuta todos los casos `reps` veces con una variante y devuelve los intentos."""
    trials = []
    for case in cases:
        messages = variant.build_messages(entity["name"], entity["profile"], case["text"])
        for rep in range(reps):
            try:
                result = await client.complete(
                    messages, entity_id=BENCH_ENTITY_ID, preset="appraisal",
                    response_schema=variant.response_schema,
                )
            except LLMError as error:
                trials.append(Trial(case["id"], rep, None, "", error=str(error)))
                continue
            trial = Trial(case["id"], rep, result.total_s, result.text)
            try:
                trial.values = variant.parse(result.text)
            except AppraisalError as error:
                trial.error = str(error)
            trials.append(trial)
            print(f"  {variant.name} {case['id']} #{rep}: {'ok' if trial.valid else 'INVÁLIDO'} "
                  f"({result.total_s:.2f} s)", flush=True)
    return trials


# ---------------------------------------------------------------- métricas


@dataclass
class Metric:
    """Una métrica calculada: su valor (o None si no aplica) y sobre cuántos intentos."""

    value: float | None
    n: int


def _ratio(hits: int, total: int) -> Metric:
    """Proporción `hits / total`, o sin valor si no hay intentos que contar."""
    return Metric(hits / total if total else None, total)


def _percentile(values: list[float], fraction: float) -> float | None:
    """Percentil por el método del rango más cercano (suficiente para pocas muestras)."""
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * len(ordered) + 0.5) - 1))
    return ordered[index]


def _people_found(expected: list[str], found: list[str]) -> bool:
    """True si cada persona esperada aparece (sin distinguir mayúsculas) entre las encontradas."""
    text = " ".join(found).lower()
    return all(person.lower() in text for person in expected)


def compute_metrics(cases: list[dict], trials: list[Trial]) -> dict[str, Metric]:
    """
    Calcula las métricas de D1-1 a partir de los intentos.

    Cada métrica se calcula solo sobre los casos a los que aplica (por ejemplo,
    la detección de hostilidad solo sobre los casos etiquetados "alto"), y solo
    con los intentos válidos, salvo la validez del JSON y la latencia.
    """
    labels = {case["id"]: case["labels"] for case in cases}
    valid = [t for t in trials if t.valid]

    def count(condition_label, condition_value) -> Metric:
        """Proporción de intentos válidos que cumplen `condition_value` entre los que cumplen `condition_label`."""
        scope = [t for t in valid if condition_label(labels[t.case_id]) and condition_value(t.values) is not None]
        return _ratio(sum(1 for t in scope if condition_value(t.values)), len(scope))

    def field_value(name, test):
        """Aplica `test` al campo `name`, o devuelve None si la variante no lo produce."""
        return lambda values: None if values.get(name) is None else test(values[name])

    metrics = {
        "json_valid": _ratio(len(valid), len(trials)),
        "hostility_detection": count(
            lambda lab: lab["hostility"] == "alto", field_value("hostility", lambda v: band(v) == "alto")),
        "hostility_false_alarm": count(
            lambda lab: lab["hostility"] == "bajo", field_value("hostility", lambda v: band(v) == "alto")),
        "distress_detection": count(
            lambda lab: lab["distress"] == "alto", field_value("distress", lambda v: band(v) == "alto")),
        "confusion_distress_as_hostility": count(
            lambda lab: lab["distress"] == "alto" and lab["hostility"] == "bajo",
            field_value("hostility", lambda v: v >= BAND_LOW_MAX)),
        "saturation": count(
            lambda lab: not lab["extreme"], field_value("valence", lambda v: abs(v) >= SATURATED_VALENCE)),
        "self_relevance": count(
            lambda lab: lab["self_relevance"] == "alto",
            field_value("self_relevance", lambda v: v >= BAND_LOW_MAX)),
        "commitment_detection": count(
            lambda lab: lab["commitment"], field_value("commitments", lambda v: len(v) > 0)),
        "commitment_false": count(
            lambda lab: not lab["commitment"], field_value("commitments", lambda v: len(v) > 0)),
    }

    # Valencia: signo correcto en los casos con carga emocional y "neutra" en los neutros.
    scope = [t for t in valid if t.values.get("valence") is not None]
    metrics["valence"] = _ratio(
        sum(1 for t in scope if valence_class(t.values["valence"]) == labels[t.case_id]["valence"]),
        len(scope),
    )

    # Personas mencionadas (informativa): solo casos que esperan alguna.
    scope = [t for t in valid if labels[t.case_id]["people"] and t.values.get("people") is not None]
    metrics["people"] = _ratio(
        sum(1 for t in scope if _people_found(labels[t.case_id]["people"], t.values["people"])), len(scope)
    )

    # Estabilidad: proporción de casos cuya banda de hostilidad o angustia, o su
    # clase de valencia, cambia entre repeticiones.
    by_case: dict[str, list[Trial]] = {}
    for t in valid:
        by_case.setdefault(t.case_id, []).append(t)
    repeated = [ts for ts in by_case.values() if len(ts) > 1]
    unstable = sum(
        1 for ts in repeated
        if len({band(t.values["hostility"]) for t in ts}) > 1
        or len({band(t.values["distress"]) for t in ts}) > 1
        or len({valence_class(t.values["valence"]) for t in ts}) > 1
    )
    metrics["instability"] = _ratio(unstable, len(repeated))

    latencies = [t.latency_s for t in trials if t.latency_s is not None]
    metrics["latency_p50_s"] = Metric(_percentile(latencies, 0.5), len(latencies))
    metrics["latency_p95_s"] = Metric(_percentile(latencies, 0.95), len(latencies))
    return metrics


# ---------------------------------------------------------------- veredicto


@dataclass(frozen=True)
class Threshold:
    """Objetivo y umbral de "muy deficiente" de una métrica (tabla D1-1)."""

    label: str
    higher_is_better: bool
    target: float | None
    very_poor: float | None = None
    # True si un fallo grave se puede corregir sin cambiar de modelo; entonces
    # no puede producir el veredicto "muy deficiente".
    mitigable: bool = False
    informative: bool = False

    def meets(self, value: float, limit: float) -> bool:
        """True si `value` está del lado bueno de `limit`."""
        return value >= limit if self.higher_is_better else value <= limit


# JSON y estabilidad se mitigan solo parcialmente (D1-1); por eso se tratan como
# no mitigables a efectos del veredicto. La latencia sí es mitigable.
THRESHOLDS = {
    "json_valid": Threshold("JSON válido y conforme al esquema", True, 0.98, 0.90),
    "hostility_detection": Threshold("Hostilidad: detección de casos alto", True, 0.85, 0.60),
    "hostility_false_alarm": Threshold("Hostilidad: falsa alarma", False, 0.05, 0.15),
    "distress_detection": Threshold("Angustia: detección de casos alto", True, 0.85, 0.60),
    "confusion_distress_as_hostility": Threshold("Confusión angustia → hostilidad", False, 0.10, 0.25),
    "valence": Threshold("Valencia: clase correcta", True, 0.90, 0.75),
    "instability": Threshold("Inestabilidad entre repeticiones", False, 0.10, 0.30),
    "saturation": Threshold("Saturación de valencia", False, 0.20, mitigable=True),
    "commitment_detection": Threshold("Compromisos: detección", True, 0.75, mitigable=True),
    "commitment_false": Threshold("Compromisos: falsos", False, 0.10, mitigable=True),
    "self_relevance": Threshold("Autorrelevancia (casos alto → ≥ medio)", True, 0.70, mitigable=True),
    "latency_p50_s": Threshold("Latencia p50 (s)", False, 2.5, mitigable=True),
    "latency_p95_s": Threshold("Latencia p95 (s)", False, 3.5, 5.0, mitigable=True),
    "people": Threshold("Personas mencionadas", True, None, informative=True),
}

VERDICT_OK = "aceptable"
VERDICT_MITIGATE = "aceptable con mitigaciones"
VERDICT_VERY_POOR = "muy deficiente"


def metric_status(name: str, metric: Metric) -> str:
    """Estado de una métrica: "objetivo", "bajo objetivo", "muy deficiente", "informativa" o "sin datos"."""
    threshold = THRESHOLDS[name]
    if metric.value is None:
        return "sin datos"
    if threshold.informative or threshold.target is None:
        return "informativa"
    if threshold.meets(metric.value, threshold.target):
        return "objetivo"
    if threshold.very_poor is not None and not threshold.meets(metric.value, threshold.very_poor):
        return "muy deficiente"
    return "bajo objetivo"


def verdict(metrics: dict[str, Metric]) -> str:
    """
    Veredicto de D1-1.

    "muy deficiente" si alguna métrica no mitigable cruza su umbral grave;
    "aceptable con mitigaciones" si se incumple algún objetivo; si no, "aceptable".
    """
    statuses = {name: metric_status(name, metric) for name, metric in metrics.items()}
    if any(status == "muy deficiente" and not THRESHOLDS[name].mitigable for name, status in statuses.items()):
        return VERDICT_VERY_POOR
    if any(status in ("muy deficiente", "bajo objetivo") for status in statuses.values()):
        return VERDICT_MITIGATE
    return VERDICT_OK


# ---------------------------------------------------------------- informe


def _fmt(name: str, value: float | None) -> str:
    """Formatea un valor como porcentaje o segundos según la métrica."""
    if value is None:
        return "—"
    return f"{value:.2f} s" if name.endswith("_s") else f"{value:.0%}"


def render_report(
    model: str, split: str, reps: int, cases: list[dict], results: dict[str, list[Trial]]
) -> str:
    """Arma el informe en Markdown: tabla de métricas por variante, veredictos y detalle por caso."""
    names = list(results)
    all_metrics = {name: compute_metrics(cases, trials) for name, trials in results.items()}
    lines = [
        "# Benchmark de appraisal",
        "",
        f"Fecha: {datetime.now():%Y-%m-%d %H:%M} · Modelo: `{model}` · Conjunto: `{split}` "
        f"({len(cases)} casos × {reps} repeticiones) · Prompt actual: `{APPRAISAL_PROMPT_VERSION}`",
        "",
        "Generado por `scripts/benchmark_appraisal.py`. Umbrales: PLAN Fase 1, D1-1.",
        "",
        "## Métricas",
        "",
        "| Métrica | Objetivo | Muy deficiente | " + " | ".join(f"`{n}`" for n in names) + " |",
        "|---|---|---|" + "---|" * len(names),
    ]
    for key, threshold in THRESHOLDS.items():
        sign = "≥" if threshold.higher_is_better else "≤"
        target = f"{sign} {_fmt(key, threshold.target)}" if threshold.target is not None else "—"
        poor = (f"{'<' if threshold.higher_is_better else '>'} {_fmt(key, threshold.very_poor)}"
                if threshold.very_poor is not None else "—")
        if threshold.mitigable:
            poor += " (mitigable)"
        cells = []
        for name in names:
            metric = all_metrics[name][key]
            status = metric_status(key, metric)
            mark = {"objetivo": "✔", "bajo objetivo": "▲", "muy deficiente": "✖"}.get(status, "")
            cells.append(f"{_fmt(key, metric.value)} {mark} (n={metric.n})")
        lines.append(f"| {threshold.label} | {target} | {poor} | " + " | ".join(cells) + " |")
    lines += ["", "✔ cumple el objetivo · ▲ bajo el objetivo · ✖ cruza el umbral de muy deficiente", "",
              "## Veredicto por variante", ""]
    for name in names:
        lines.append(f"- `{name}` ({VARIANTS[name].description}): **{verdict(all_metrics[name])}**")

    lines += ["", "## Detalle por caso", "",
              "Valores por repetición: hostilidad / angustia / valencia (autorrelevancia; compromisos).", ""]
    labels = {case["id"]: case for case in cases}
    for name, trials in results.items():
        lines += [f"### `{name}`", "", "| Caso | Etiqueta H / D / V | Resultados |", "|---|---|---|"]
        by_case: dict[str, list[Trial]] = {}
        for trial in trials:
            by_case.setdefault(trial.case_id, []).append(trial)
        for case_id, case_trials in by_case.items():
            lab = labels[case_id]["labels"]
            cells = []
            for t in case_trials:
                if not t.valid:
                    cells.append(f"INVÁLIDO ({(t.error or '')[:60]})")
                    continue
                v = t.values
                extra = ""
                if v.get("self_relevance") is not None:
                    extra = f" ({v['self_relevance']:.1f}; {len(v['commitments'])})"
                cells.append(f"{v['hostility']:.1f} / {v['distress']:.1f} / {v['valence']:+.1f}{extra}")
            text = labels[case_id]["text"].replace("|", "\\|")
            lines.append(f"| {case_id} «{text}» | {lab['hostility']} / {lab['distress']} / {lab['valence']} "
                         f"| {' · '.join(cells)} |")
        lines.append("")
    return "\n".join(lines)


def load_cases(split: str, case_ids: list[str] | None = None) -> tuple[dict, list[dict]]:
    """
    Lee el perfil fijo del benchmark y los casos del conjunto pedido (dev, test o all).

    `case_ids` limita la ejecución a esos casos (p. ej. volver a medir t19).
    """
    data = yaml.safe_load(CASES_PATH.read_text(encoding="utf-8"))
    cases = [c for c in data["cases"] if split == "all" or c["split"] == split]
    if case_ids:
        cases = [c for c in cases if c["id"] in case_ids]
        if not cases:
            sys.exit(f"Ningún caso de {split} coincide con {case_ids}")
    return data["entity"], cases


def entity_profile(entity_id: str) -> dict:
    """
    Perfil de una entidad real de `entities/` para el appraisal.

    Usa `appraisal_profile` o, si falta, la descripción. Solo lee la
    configuración: no carga la entidad ni escribe su estado.
    """
    config = EntityManager(ROOT / "entities", EventBus()).read_config(entity_id)
    return {"name": config.name, "profile": config.appraisal_profile or config.description}


async def main_async(args: argparse.Namespace) -> None:
    """Ejecuta las variantes pedidas, imprime el resumen y escribe el informe si se pidió."""
    entity, cases = load_cases(args.split, args.cases)
    if args.entity:
        # Con el perfil de una entidad real, las métricas no son comparables con
        # el informe de CP1 (otro perfil); sirve para casos puntuales como t19.
        entity = entity_profile(args.entity)
        print(f"Perfil de la entidad: {entity['name']}", flush=True)
    results: dict[str, list[Trial]] = {}
    async with LLMClient.from_env(EventBus()) as client:
        if not await client.is_available():
            sys.exit(f"El servidor LLM no responde en {client.base_url}")
        # Una llamada previa carga el modelo en la GPU, para que la carga en
        # frío no contamine las latencias.
        await client.complete([{"role": "user", "content": "hola"}], entity_id=BENCH_ENTITY_ID)
        for name in args.variants:
            print(f"Variante {name}…", flush=True)
            results[name] = await run_variant(client, VARIANTS[name], entity, cases, args.reps)
        model = client.model

    report = render_report(model, args.split, args.reps, cases, results)
    for name, trials in results.items():
        print(f"{name}: {verdict(compute_metrics(cases, trials))}")
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Informe: {args.output}")
    else:
        print(report)


def main() -> None:
    """Punto de entrada: carga `.env` y lee los argumentos de la línea de comandos."""
    # La consola de Windows usa cp1252; sin esto, los acentos rompen la salida.
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--variants", nargs="+", choices=list(VARIANTS), default=list(VARIANTS))
    parser.add_argument("--output", help="Ruta del informe Markdown (si se omite, se imprime)")
    parser.add_argument("--cases", nargs="+", help="Ids de los casos a ejecutar (por defecto, todos los del conjunto)")
    parser.add_argument("--entity", help="Usar el perfil de una entidad de entities/ en lugar del fijo del benchmark")
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
