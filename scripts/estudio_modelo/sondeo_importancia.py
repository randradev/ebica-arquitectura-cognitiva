"""
Sondeo de la importancia de CP7 parte A (D1-43): ¿qué campos del appraisal se
mueven cuando el usuario cuenta algo de sí mismo?

En la prueba en vivo de CP6, «Adopté un perro, se llama Toby» quedó con
importancia 0 (D1-36 solo mira autorrelevancia, metas e intensidad). Este
sondeo corre el appraisal real de Calisto sobre los mensajes de la sesión de
`benchmarks/recuerdo/cases.yaml` (el usuario habla de sí), dos mensajes con
carga emocional del usuario y dos de control que hablan de ella, y muestra
cada campo y la importancia que daría la fórmula actual. No cambia nada del motor.

Necesita Ollama encendido. Uso, desde la raíz del repositorio:
    .venv/Scripts/python.exe scripts/estudio_modelo/sondeo_importancia.py <salida.json>
"""

import asyncio
import json
import statistics
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Raíz del repositorio (este archivo está en scripts/estudio_modelo/).
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ebica.affect.appraisal_effects import apply_coherence_rules  # noqa: E402
from ebica.core.events import EventBus  # noqa: E402
from ebica.core.orchestrator import APPRAISAL_SCHEMA  # noqa: E402
from ebica.entities.manager import EntityManager  # noqa: E402
from ebica.llm.client import LLMClient  # noqa: E402
from ebica.memory.episodes import episode_importance  # noqa: E402
from ebica.perception.appraisal import build_appraisal_messages, parse_appraisal  # noqa: E402

# CONSTANTE: repeticiones por mensaje (el appraisal varía un poco entre llamadas).
REPS = 3
# Mensajes extra: el usuario con carga emocional y dos controles que hablan de ella.
EXTRA = [
    ("u-papa", "usuario", "Mi papá está enfermo y estoy preocupado."),
    ("u-cumple", "usuario", "Hoy es mi cumpleaños."),
    ("c-arte", "control", "Vi tus ilustraciones y la verdad me parecen bastante pretenciosas."),
    ("c-hola", "control", "Hola, ¿cómo estás?"),
]
FIELDS = ("self_relevance", "goal_congruence", "hostility", "distress", "novelty")


async def main() -> None:
    """Corre el appraisal de cada mensaje y guarda los campos y la importancia."""
    load_dotenv(ROOT / ".env")
    output = Path(sys.argv[1])
    cases = yaml.safe_load((ROOT / "benchmarks" / "recuerdo" / "cases.yaml").read_text(encoding="utf-8"))
    messages = [(item["id"], "usuario", item["mensaje"]) for item in cases["sesion"]] + EXTRA
    config = EntityManager(ROOT / "entities", EventBus()).read_config("calisto")
    records = []
    async with LLMClient.from_env(EventBus()) as llm:
        for key, group, text in messages:
            for rep in range(REPS):
                prompt = build_appraisal_messages(config.name, config.appraisal_profile, text)
                result = await llm.complete(
                    prompt, entity_id="sondeo", preset="appraisal", response_schema=APPRAISAL_SCHEMA
                )
                appraisal, _ = apply_coherence_rules(parse_appraisal(result.text))
                records.append({
                    "id": key, "grupo": group, "rep": rep, "text": text,
                    **{name: getattr(appraisal, name) for name in FIELDS},
                    "people": len(appraisal.mentioned_people), "topics": appraisal.topics,
                    "importance": episode_importance(appraisal),
                })
    output.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'id':14} {'grupo':8} " + " ".join(f"{name[:6]:>6}" for name in FIELDS) + "  pers   imp")
    for key, group, _ in messages:
        rows = [r for r in records if r["id"] == key]
        means = [statistics.mean(r[name] for r in rows) for name in FIELDS]
        print(f"{key:14} {group:8} " + " ".join(f"{m:+6.2f}" for m in means)
              + f"  {statistics.mean(r['people'] for r in rows):4.1f}"
              + f"  {statistics.mean(r['importance'] for r in rows):.2f}"
              + f" ({min(r['importance'] for r in rows):.2f}–{max(r['importance'] for r in rows):.2f})")


asyncio.run(main())
