"""
Expresión según el estado, en vivo (CP9 parte C).

Envía los mensajes de `benchmarks/expresion/cases.yaml` a una entidad de prueba,
llevando antes de cada uno el ánimo al estado pedido (`--estado calma|amenaza`)
con `POST /api/affect/impulse`. Guarda, por respuesta, el texto, las palabras, la
pizarra (`turn.completed.workspace`), los recuerdos y hechos, la temperatura, el
ánimo antes de responder y la sección 7 del prompt. El tono se juzga a mano.

Preparación como en `prueba_recuerdo_vivo.py` (copia de la config de Calisto con
otro id, servidor en otro puerto). Una entidad nueva por estado.
    .venv/Scripts/python.exe scripts/prueba_expresion_vivo.py <salida.json> --entidad <id> --estado amenaza [--puerto 8011]
"""

import argparse
import asyncio
import json
from pathlib import Path

import httpx
import websockets
import yaml

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmarks" / "expresion" / "cases.yaml"
EXPRESSION_HEADER = "Cómo expresarme:"


def last(events: list[dict], kind: str) -> dict:
    """El evento más reciente de un tipo."""
    return next(e for e in reversed(events) if e["type"] == kind)


async def main() -> None:
    """Corre los mensajes en el estado pedido y guarda lo observado."""
    parser = argparse.ArgumentParser()
    parser.add_argument("salida", type=Path)
    parser.add_argument("--entidad", required=True)
    parser.add_argument("--estado", choices=["calma", "amenaza"], required=True)
    parser.add_argument("--puerto", type=int, default=8011)
    args = parser.parse_args()
    base, ws = f"http://127.0.0.1:{args.puerto}", f"ws://127.0.0.1:{args.puerto}"
    data = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    target = data["estados"][args.estado]

    events: list[dict] = []
    records = []
    async with websockets.connect(f"{ws}/ws/events") as events_ws:
        async def collect() -> None:
            """Acumula los eventos del bus."""
            async for raw in events_ws:
                events.append(json.loads(raw))

        task = asyncio.create_task(collect())
        async with httpx.AsyncClient(timeout=180) as http:
            (await http.post(f"{base}/api/entities/{args.entidad}/load")).raise_for_status()
            async with websockets.connect(f"{ws}/ws/chat", max_size=None) as chat:
                for case in data["mensajes"]:
                    # Lleva el ánimo al estado objetivo: el impulso es la diferencia con el actual.
                    await asyncio.sleep(0.3)
                    current = last(events, "affect.updated")["payload"]
                    delta = {dim: round(target[dim] - current[dim], 4) for dim in ("valence", "arousal", "dominance")}
                    affect = (await http.post(f"{base}/api/affect/impulse", json=delta)).json()["affect"]
                    await chat.send(json.dumps({"text": case["texto"]}))
                    reply = ""
                    while True:
                        message = json.loads(await chat.recv())
                        if message["type"] == "token":
                            reply += message["text"]
                        else:
                            break
                    await asyncio.sleep(0.3)
                    turn = last(events, "turn.completed")["payload"]
                    request = next(e for e in reversed(events) if e["type"] == "llm.request"
                                   and e["payload"]["preset"] in ("dialogue", "impulsive"))
                    system = request["payload"]["body"]["messages"][0]["content"]
                    section7 = system.split(EXPRESSION_HEADER, 1)[1].strip() if EXPRESSION_HEADER in system else None
                    retrieval = turn.get("retrieval") or {}
                    records.append({
                        "id": case["id"], "estado": args.estado, "texto": case["texto"], "reply": reply,
                        "palabras": len(reply.split()), "afecto_antes": affect, "impulsivo": turn["impulsive"],
                        "temperatura": turn["temperature"], "pizarra": turn.get("workspace"),
                        "recuerdos": [e["id"] for e in retrieval.get("episodes", [])],
                        "hechos": [f["id"] for f in retrieval.get("facts", [])],
                        "seccion7": section7, "esperado": case.get("esperado", []),
                    })
                    ws_info = turn.get("workspace") or {}
                    print(f"[{args.estado}] {case['id']}: {len(reply.split())} palabras · pizarra "
                          f"{ws_info.get('used')}/{ws_info.get('budget')} · desalojados {len(ws_info.get('evicted', []))}",
                          flush=True)
        task.cancel()
    args.salida.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"guardado en {args.salida}")


asyncio.run(main())
