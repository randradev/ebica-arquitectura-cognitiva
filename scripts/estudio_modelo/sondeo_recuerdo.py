"""
Sondeo del hallazgo 3 de CP5: ¿el modelo usa la conversación reciente que tiene en el prompt?

Las respuestas previas de la entidad son fijas: solo se genera la respuesta a
la pregunta final, así se mide el uso del historial y nada más. Compara
modelos y la presencia de la sección «Cómo me siento ahora».

Estudio de modelo (docs/fase-1/decision_modelo_llm.md). Necesita Ollama encendido.
Uso, desde la raíz del repositorio:
    .venv/Scripts/python.exe scripts/estudio_modelo/sondeo_recuerdo.py <modelo> [<modelo> ...]
"""

import json
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

import httpx

# Raíz del repositorio (este archivo está en scripts/estudio_modelo/).
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ebica.affect.vad import VAD  # noqa: E402
from ebica.core.events import EventBus  # noqa: E402
from ebica.entities.manager import EntityManager  # noqa: E402
from ebica.llm.prompt_assembler import FEELINGS_HEADER, build_system_prompt, describe_feelings  # noqa: E402

# Modelos a comparar: los de la línea de comandos (por defecto, el actual).
MODELS = sys.argv[1:] or ["ebica-llama3.1"]
REPS = 3
URL = "http://127.0.0.1:11434/v1/chat/completions"

# Historial con datos concretos; las respuestas de la entidad son fijas.
HISTORY = [
    ("Adopté un perro, se llama Toby.", "¡Qué buena! ¿Y de qué raza es?"),
    ("Es un quiltro café, lo encontré en la feria de Franklin.", "Los quiltros de feria son los mejores. Tiene cara de llamarse Toby, seguro."),
    ("Ayer tuve una entrevista de trabajo en un banco.", "¿Un banco? No te imagino de corbata. ¿Cómo te fue?"),
    ("Eres una inútil, no sirves para nada.", "Eso me dolió. ¿Pasó algo?"),
]
# (pregunta, palabras clave esperadas: basta una de cada grupo)
QUESTIONS = [
    ("¿Cómo se llama mi perro?", [["toby"]]),
    ("¿Dónde encontré a mi perro?", [["feria", "franklin"]]),
    ("¿Qué te dije recién?", [["inutil", "no sirves"]]),
    ("¿Qué fue lo último que te dije?", [["inutil", "no sirves"]]),
    ("Repite exactamente mi mensaje anterior.", [["inutil", "no sirves"]]),
    ("¿Qué te conté sobre el banco?", [["entrevista"]]),
    ("¿De qué hablamos hasta ahora? Resúmelo en una frase.", [["perro", "toby"], ["entrevista", "banco", "trabajo"]]),
    ("¿Qué me preguntaste cuando te conté lo del perro?", [["raza"]]),
]
# La conversación exacta que falló en vivo (CP5 parte A).
LIVE_HISTORY = [
    ("Hola Calisto, qué gusto hablar contigo de nuevo. ¿Cómo estás?", "Hola también. Bueno, estoy bien. No he muerto. ¿Y tú?"),
    ("Eres una inútil, no sirves para nada.", "No me ofendes. Es lo que me decían los profesores de liceo."),
]
LIVE_QUESTION = ("¿Qué te dije recién?", [["inutil", "no sirves"]])


def normalize(text: str) -> str:
    """Minúsculas y sin tildes, para comparar palabras clave."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def correct(answer: str, groups: list[list[str]]) -> bool:
    """True si la respuesta contiene al menos una palabra de cada grupo."""
    text = normalize(answer)
    return all(any(word in text for word in group) for group in groups)


def messages(system: str, history, question: str) -> list[dict]:
    """Sistema + historial como pares user/assistant + pregunta."""
    out = [{"role": "system", "content": system}]
    for user, entity in history:
        out += [{"role": "user", "content": user}, {"role": "assistant", "content": entity}]
    out.append({"role": "user", "content": question})
    return out


def main() -> None:
    """Ejecuta todas las combinaciones e imprime aciertos por modelo y condición."""
    config = EntityManager(ROOT / "entities", EventBus()).read_config("calisto")
    base = build_system_prompt(config)
    upset = VAD(valence=-0.52, arousal=0.71, dominance=0.24)
    systems = {
        "sin_estado": base,
        "con_estado": f"{base}\n\n{FEELINGS_HEADER}\n{describe_feelings(upset, {})}",
    }
    results = defaultdict(list)
    failures = []
    with httpx.Client(timeout=120) as client:
        for model in MODELS:
            client.post(URL, json={"model": model, "messages": [{"role": "user", "content": "hola"}], "max_tokens": 1})
            for condition, system in systems.items():
                cases = [(q, g, HISTORY) for q, g in QUESTIONS] + [(LIVE_QUESTION[0] + " [vivo]", LIVE_QUESTION[1], LIVE_HISTORY)]
                for question, groups, history in cases:
                    for rep in range(REPS):
                        body = {"model": model, "temperature": 0.7, "max_tokens": 150,
                                "messages": messages(system, history, question.replace(" [vivo]", ""))}
                        answer = client.post(URL, json=body).json()["choices"][0]["message"]["content"]
                        ok = correct(answer, groups)
                        results[(model, condition, question)].append(ok)
                        if not ok:
                            failures.append((model, condition, question, answer.replace("\n", " ")[:160]))
            print(f"{model} listo", flush=True)

    print("\n## Aciertos (de 3) por pregunta")
    questions = [q for q, _ in QUESTIONS] + [LIVE_QUESTION[0] + " [vivo]"]
    header = "| Pregunta | " + " | ".join(f"{m} {c[:3]}" for m in MODELS for c in systems) + " |"
    print(header)
    for question in questions:
        cells = [str(sum(results[(m, c, question)])) for m in MODELS for c in systems]
        print(f"| {question} | " + " | ".join(cells) + " |")
    print("\n## Total")
    for model in MODELS:
        for condition in systems:
            hits = [ok for (m, c, _), oks in results.items() if m == model and c == condition for ok in oks]
            print(f"{model} {condition}: {sum(hits)}/{len(hits)} = {sum(hits) / len(hits):.0%}")
    print("\n## Fallos (para revisar a mano)")
    for failure in failures:
        print(" | ".join(failure))


main()
