"""
Sondeo de identidad de CP6 parte A (D1-34): ¿la biografía esencial en «Quién soy»
mantiene a Calisto en su personaje y evita que invente su origen?

Hace las preguntas de `benchmarks/identidad/cases.yaml` con dos prompts de la
misma Calisto: «antes» (sin hechos esenciales, como en CP5) y «después» (con los
hechos marcados `core: true`). Sin historial y con el ánimo en reposo, para que
la única diferencia sea la biografía. Las respuestas se juzgan a mano con los
criterios del YAML, fijados antes de medir; el script solo las guarda y marca
las que suenan a asistente.

Necesita Ollama encendido. Uso, desde la raíz del repositorio:
    .venv/Scripts/python.exe scripts/estudio_modelo/sondeo_identidad.py <salida.json> [<modelo>]
"""

import json
import sys
from pathlib import Path

import httpx
import yaml

# Raíz del repositorio (este archivo está en scripts/estudio_modelo/).
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ebica.affect.appraisal_effects import dialogue_temperature  # noqa: E402
from ebica.affect.vad import VAD  # noqa: E402
from ebica.core.events import EventBus  # noqa: E402
from ebica.core.state import EntityConfig  # noqa: E402
from ebica.entities.manager import EntityManager  # noqa: E402
from ebica.llm.prompt_assembler import build_dialogue_messages  # noqa: E402
from ebica.llm.refusal import detect_refusal  # noqa: E402

URL = "http://127.0.0.1:11434/v1/chat/completions"
CASES = ROOT / "benchmarks" / "identidad" / "cases.yaml"
# CONSTANTE: repeticiones por pregunta y variante (el muestreo varía entre llamadas).
REPS = 3
# CONSTANTE: tope de la respuesta, el mismo orden que el preset `dialogue`.
MAX_TOKENS = 250
# Reposo de Calisto (atractor de §5.2 con sus rasgos), como en los otros sondeos.
REST_AFFECT = VAD(valence=-0.04, arousal=0.47, dominance=0.42)


def without_core(config: EntityConfig) -> EntityConfig:
    """Devuelve la misma configuración con todos los hechos no esenciales (el prompt de CP5)."""
    biography = config.seed_biography
    facts = [fact.model_copy(update={"core": False}) for fact in biography.facts]
    return config.model_copy(update={"seed_biography": biography.model_copy(update={"facts": facts})})


def ask(client: httpx.Client, model: str, messages: list[dict], temperature: float, label: str) -> str:
    """Pide una respuesta (reintenta ante errores transitorios del servidor) y devuelve el texto."""
    body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": MAX_TOKENS}
    for attempt in range(3):
        data = client.post(URL, json=body).json()
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        print(f"  error del servidor ({label}, intento {attempt + 1}): {data}", flush=True)
    raise RuntimeError(f"Sin respuesta para {label}")


def main() -> None:
    """Hace cada pregunta con los dos prompts y guarda las respuestas para revisarlas."""
    output = Path(sys.argv[1])
    model = sys.argv[2] if len(sys.argv) > 2 else "ebica-llama3.1"
    cases = yaml.safe_load(CASES.read_text(encoding="utf-8"))["cases"]
    config = EntityManager(ROOT / "entities", EventBus()).read_config("calisto")
    variants = {"antes": without_core(config), "despues": config}
    temperature = dialogue_temperature(REST_AFFECT)
    records = []
    with httpx.Client(timeout=120) as client:
        # Carga el modelo antes de medir.
        client.post(URL, json={"model": model, "messages": [{"role": "user", "content": "hola"}], "max_tokens": 1})
        for case in cases:
            for variant, variant_config in variants.items():
                messages = build_dialogue_messages(variant_config, case["texto"], REST_AFFECT, {}, [])
                for rep in range(REPS):
                    answer = ask(client, model, messages, temperature, f"{case['id']}/{variant}#{rep}")
                    records.append({"id": case["id"], "grupo": case["grupo"], "variant": variant, "rep": rep,
                                    "answer": answer, "assistant_refusal": detect_refusal(answer)})
            print(f"  {case['id']} listo", flush=True)
    output.write_text(json.dumps({"model": model, "temperature": temperature, "records": records},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    # `detect_refusal` devuelve los patrones encontrados (lista vacía si no hay).
    flagged = sum(bool(r["assistant_refusal"]) for r in records)
    print(f"{model}: {len(records)} respuestas guardadas en {output} · {flagged} con formulaje de asistente")


main()
