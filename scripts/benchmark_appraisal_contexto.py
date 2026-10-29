"""
Benchmark del appraisal con contexto (CP10b, D1-78, D1-82).

Corre el appraisal real de Calisto sobre `benchmarks/appraisal_contexto/cases.yaml`,
3 repeticiones por caso, con o sin el intercambio previo como contexto. Un caso
acierta si, en la mayoría de las repeticiones, todos sus campos esperados caen en
la banda pedida. Sin `--contexto` mide el appraisal de hoy (línea base); con
`--contexto`, el de CP10b B (requiere que `build_appraisal_messages` acepte el
contexto).

Uso: .venv/Scripts/python.exe scripts/benchmark_appraisal_contexto.py --split dev [--contexto] [--reps 3] [--salida r.json]
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ebica.affect.appraisal_effects import apply_coherence_rules  # noqa: E402
from ebica.core.events import EventBus  # noqa: E402
from ebica.core.orchestrator import APPRAISAL_SCHEMA  # noqa: E402
from ebica.entities.manager import EntityManager  # noqa: E402
from ebica.llm.client import LLMClient  # noqa: E402
from ebica.perception.appraisal import build_appraisal_messages, parse_appraisal  # noqa: E402

CASES = ROOT / "benchmarks" / "appraisal_contexto" / "cases.yaml"


def band(value: float) -> str:
    """Banda de un valor de 0 a 1 (D1-1)."""
    return "bajo" if value < 0.33 else "medio" if value < 0.66 else "alto"


def sign(value: float) -> str:
    """Signo de una valencia, con una zona neutra de ±0,1."""
    return "neg" if value < -0.1 else "pos" if value > 0.1 else "neutro"


def observed(appraisal) -> dict:
    """Los campos que juzgan los casos, en bandas."""
    return {"hostilidad": band(appraisal.hostility), "angustia": band(appraisal.distress),
            "valencia": sign(appraisal.user_emotion.valence)}


def matches(expected: dict, seen: dict) -> bool:
    """True si cada campo esperado (un valor o una lista de valores aceptados) coincide."""
    return all(seen[key] in (value if isinstance(value, list) else [value]) for key, value in expected.items())


async def main() -> None:
    """Corre el split pedido e imprime acierto por caso y resumen por tipo."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test"], required=True)
    parser.add_argument("--contexto", action="store_true")
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    config = EntityManager(ROOT / "entities", EventBus()).read_config("calisto")
    cases = [c for c in yaml.safe_load(CASES.read_text(encoding="utf-8"))["cases"] if c["split"] == args.split]
    records = []
    async with LLMClient.from_env(EventBus()) as llm:
        for case in cases:
            extra = {"context": (case["previo"]["persona"], case["previo"]["entidad"])} if args.contexto else {}
            messages = build_appraisal_messages(config.name, config.appraisal_profile, case["mensaje"], **extra)
            reps = []
            for _ in range(args.reps):
                result = await llm.complete(messages, entity_id="bench-contexto", preset="appraisal",
                                            response_schema=APPRAISAL_SCHEMA)
                appraisal, _ = apply_coherence_rules(parse_appraisal(result.text))
                reps.append({"bandas": observed(appraisal), "hostilidad": appraisal.hostility,
                             "angustia": appraisal.distress, "valencia": appraisal.user_emotion.valence})
            hits = sum(matches(case["esperado"], rep["bandas"]) for rep in reps)
            records.append({"id": case["id"], "tipo": case["tipo"], "acierto": hits * 2 > len(reps),
                            "aciertos_reps": hits, "esperado": case["esperado"], "reps": reps})
            mark = "✔" if hits * 2 > len(reps) else "✖"
            values = " | ".join(f"H {r['hostilidad']:.2f} D {r['angustia']:.2f} V {r['valencia']:+.2f}" for r in reps)
            print(f"{mark} {case['id']:18} {hits}/{len(reps)} · esperado {case['esperado']} · {values}", flush=True)
    for kind in ("contexto", "control"):
        group = [r for r in records if r["tipo"] == kind]
        print(f"{kind}: {sum(r['acierto'] for r in group)}/{len(group)}")
    if args.salida:
        args.salida.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")


asyncio.run(main())
