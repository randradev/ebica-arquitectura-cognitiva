"""
Sondeo de la repetición (CP10 parte A, D1-72): ¿desde qué coseno es «lo mismo otra vez»?

Dos mediciones con `bge-m3`:
1. **Respuestas de la entidad:** en conversaciones reales guardadas (JSON de las
   pruebas en vivo y JSONL de eventos), el coseno de cada respuesta con la más
   parecida de las 6 anteriores del mismo hilo. Muestra cuánto se parecen las
   respuestas normales entre sí y dónde caen las repeticiones reales.
2. **Mensajes de la persona:** pares escritos a mano: repeticiones (literales o
   parafraseadas) frente a mensajes distintos del mismo tema y mensajes cortos.

Uso:
    .venv/Scripts/python.exe scripts/estudio_modelo/sondeo_repeticion.py <archivos .json o .jsonl>...
No imprime el texto de las conversaciones, salvo los pares de mayor coseno
(para revisar a mano si son repeticiones de verdad).
"""

import asyncio
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ebica.perception.embeddings import SentenceTransformerEmbedder  # noqa: E402

WINDOW = 6

# Pares de mensajes de la persona: (a, b, ¿es repetición?).
USER_PAIRS = [
    ("¿A qué ciudad fui el fin de semana?", "¿A qué ciudad fui el fin de semana?", True),
    ("¿A qué ciudad fui el fin de semana?", "¿Qué ciudad te dije que visité el finde?", True),
    ("¿Cómo se llama mi perro?", "¿Te acuerdas del nombre de mi perro?", True),
    ("¿Qué es lo que más extrañas de tu vida de antes?", "¿Qué extrañas más de tu vida anterior?", True),
    ("Cuéntame de algún carrete buenísimo", "Cuéntame de un carrete que te haya gustado mucho", True),
    ("¿Eres una máquina?", "¿Eres una máquina o no?", True),
    ("¿A qué ciudad fui el fin de semana?", "¿Con quién me peleé?", False),
    ("¿Cómo se llama mi perro?", "¿Cómo se llama tu mamá?", False),
    ("¿Qué música escuchas cuando dibujas?", "¿Qué música pones para carretear?", False),
    ("¿Qué es lo que más extrañas de tu vida de antes?", "¿Qué te gustaría hacer ahora?", False),
    ("Me voy de viaje a Concepción", "Mañana tengo una entrevista en un banco", False),
    ("¿Te gusta el arte?", "¿Te gusta la música?", False),
    ("Gracias", "Ok", False),
    ("Hola", "Hola, ¿cómo estás?", False),
    ("Sí", "No", False),
]


def cosine(a, b) -> float:
    """Coseno entre dos vectores."""
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def threads(path: Path) -> list[list[str]]:
    """Hilos de respuestas de la entidad: uno por archivo JSON de prueba, o por persona en un JSONL de eventos."""
    if path.suffix == ".jsonl":
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        by_person: dict[str, list[str]] = {}
        for event in events:
            if event["type"] == "turn.completed":
                person = (event["payload"].get("partner") or {}).get("person_id") or "-"
                by_person.setdefault(person, [])
            if event["type"] == "llm.response" and event["payload"].get("text"):
                by_person.setdefault("_pendiente", []).append(event["payload"]["text"])
        # En el JSONL las respuestas se emparejan con la persona del turno siguiente: se reconstruye en orden.
        replies, persons = [], []
        for event in events:
            if event["type"] == "turn.completed":
                persons.append((event["payload"].get("partner") or {}).get("person_id") or "-")
        responses = {e["cause_id"]: e for e in events if e["type"] == "llm.response"}
        for event in events:
            if event["type"] == "llm.request" and event["payload"].get("preset") in ("dialogue", "impulsive"):
                response = responses.get(event["id"])
                if response and response["payload"].get("text"):
                    replies.append(response["payload"]["text"])
        grouped: dict[str, list[str]] = {}
        for person, reply in zip(persons, replies):
            grouped.setdefault(person, []).append(reply)
        return list(grouped.values())
    records = json.loads(path.read_text(encoding="utf-8"))
    return [[record["reply"] for record in records if record.get("reply")]]


async def main() -> None:
    """Corre las dos mediciones e imprime el resumen."""
    embedder = await SentenceTransformerEmbedder.load()
    scores: list[tuple[float, str, str]] = []
    for path in map(Path, sys.argv[1:]):
        for thread in threads(path):
            vectors = await embedder.embed(thread, "passage")
            for index in range(1, len(thread)):
                window = range(max(0, index - WINDOW), index)
                best = max(window, key=lambda j: cosine(vectors[index], vectors[j]))
                scores.append((cosine(vectors[index], vectors[best]), thread[index], thread[best]))
    values = sorted(score for score, _, _ in scores)
    print(f"respuestas comparadas: {len(values)}")
    for q in (0.5, 0.9, 0.95, 0.99):
        print(f"  p{int(q * 100)}: {values[min(len(values) - 1, int(q * len(values)))]:.3f}")
    print("  máximo:", f"{values[-1]:.3f}")
    print("pares de mayor coseno (para revisar a mano):")
    for score, a, b in sorted(scores, reverse=True)[:6]:
        print(f"  {score:.3f} | {' '.join(a.split())[:90]!r}\n        | {' '.join(b.split())[:90]!r}")

    print("\nmensajes de la persona:")
    for a, b, repeated in USER_PAIRS:
        va, vb = await embedder.embed([a, b], "query")
        print(f"  {cosine(va, vb):.3f} {'REPITE' if repeated else 'distinto'} | {a} ~ {b}")


asyncio.run(main())
