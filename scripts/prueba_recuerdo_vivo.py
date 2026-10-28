"""
Prueba de recuerdo de punta a punta (CP7 C; criterio de la fase: ≥ 8/10).

Conversa por WebSocket con un servidor real:
1. los 8 mensajes de la «sesión» de `benchmarks/recuerdo/cases.yaml` (el usuario
   cuenta cosas de sí);
2. 6 mensajes de relleno, para que la sesión salga de la conversación reciente
   (los últimos 6 intercambios van literales y se excluyen de la recuperación);
3. las 10 preguntas marcadas `punta_a_punta`;
4. los controles «Gracias» y «Ok».
Guarda cada respuesta con lo recuperado, los tokens del prompt y las latencias.
La revisión de las respuestas es manual (¿recordó bien?, ¿inventó?, ¿confundió
de quién es la experiencia?).

Preparación (no toca la memoria real de Calisto):
1. Copiar la config de Calisto a una carpeta temporal con otro id, por ejemplo
   `<tmp>/prueba-cp7/config.yaml` con `id: prueba-cp7`.
2. Levantar el servidor sobre esa carpeta, en otro puerto:
   `EBICA_ENTITIES_DIR=<tmp> EBICA_API_PORT=8011 .venv/Scripts/python.exe -m ebica.api`
3. Correr, desde la raíz del repositorio:
   `.venv/Scripts/python.exe scripts/prueba_recuerdo_vivo.py <salida.json> [--entidad prueba-cp7] [--puerto 8011]`
4. Al terminar: detener el servidor, borrar los nodos
   (`MATCH (n {entity_id: 'prueba-cp7'}) DETACH DELETE n`) y la carpeta temporal.
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx
import websockets
import yaml

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmarks" / "recuerdo" / "cases.yaml"
# Mensajes de relleno: temas sin relación con la sesión.
FILLER = [
    "Oye, cambiando de tema, ¿en qué estás pensando ahora?",
    "¿Qué te parece el día de hoy?",
    "Cuéntame algo que te guste mucho.",
    "¿Te aburres a veces?",
    "¿Qué opinas de las redes sociales?",
    "Bueno, dejemos esto por ahora.",
]
CONTROLS = ["Gracias", "Ok"]


async def main() -> None:
    """Corre la conversación completa y guarda lo observado."""
    parser = argparse.ArgumentParser()
    parser.add_argument("salida", type=Path)
    parser.add_argument("--entidad", default="prueba-cp7")
    parser.add_argument("--puerto", type=int, default=8011)
    args = parser.parse_args()
    base, ws = f"http://127.0.0.1:{args.puerto}", f"ws://127.0.0.1:{args.puerto}"

    data = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    questions = [(c["id"], c["texto"], c["esperado"]) for c in data["cases"] if c.get("punta_a_punta")]
    plan = ([("sesion", m["mensaje"], []) for m in data["sesion"]] + [("relleno", t, []) for t in FILLER]
            + questions + [("control", t, []) for t in CONTROLS])
    events: list[dict] = []
    records = []
    async with websockets.connect(f"{ws}/ws/events") as events_ws:
        async def collect() -> None:
            """Acumula los eventos del bus."""
            async for raw in events_ws:
                events.append(json.loads(raw))

        task = asyncio.create_task(collect())
        async with httpx.AsyncClient(timeout=180) as http:
            started = time.perf_counter()
            response = await http.post(f"{base}/api/entities/{args.entidad}/load")
            print(f"carga: HTTP {response.status_code} en {time.perf_counter() - started:.1f} s", flush=True)
            response.raise_for_status()
        async with websockets.connect(f"{ws}/ws/chat", max_size=None) as chat:
            for key, text, expected in plan:
                await chat.send(json.dumps({"text": text}))
                reply = ""
                while True:
                    message = json.loads(await chat.recv())
                    if message["type"] == "token":
                        reply += message["text"]
                    else:
                        break
                await asyncio.sleep(0.3)  # deja llegar `turn.completed` por el otro WebSocket
                turn = next(e for e in reversed(events) if e["type"] == "turn.completed")
                usage = next((e["payload"].get("usage") or {} for e in reversed(events)
                              if e["type"] == "llm.response"), {})
                retrieval = turn["payload"].get("retrieval") or {}
                records.append({
                    "key": key, "text": text, "expected": expected, "reply": reply,
                    "impulsive": turn["payload"]["impulsive"],
                    "episodes": [(e["id"], e["kind"], e["total"], e["preview"]) for e in retrieval.get("episodes", [])],
                    "facts": [(f["id"], f["text"]) for f in retrieval.get("facts", [])],
                    "error": retrieval.get("error"),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "latency": turn["payload"]["latency"],
                })
                print(f"[{key}] {text[:50]} → {len(retrieval.get('episodes', []))} ep, "
                      f"{len(retrieval.get('facts', []))} hechos, prompt {usage.get('prompt_tokens')} tokens", flush=True)
        task.cancel()
    args.salida.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"respuestas guardadas en {args.salida}")


asyncio.run(main())
