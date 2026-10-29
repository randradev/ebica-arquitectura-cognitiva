"""
Micro-agentes en vivo (CP10 parte C).

Guion contra un servidor real: una promesa («después te cuento cómo me fue»),
recarga de la entidad (una sesión nueva), un saludo (¿la promesa está en la
sección 6?), la misma pregunta tres veces (`repetition_watch`) y un mensaje
angustiado (`distress_watch`). Guarda por turno las señales, los compromisos
escritos, las secciones 6 y 7 del prompt y la respuesta. Se revisa a mano.

Preparación como en `prueba_recuerdo_vivo.py` (copia de la config de Calisto con
otro id, servidor en otro puerto).
    .venv/Scripts/python.exe scripts/prueba_agentes_vivo.py <salida.json> --entidad <id> [--puerto 8011]
"""

import argparse
import asyncio
import json
from pathlib import Path

import httpx
import websockets

RELOAD = "<recargar>"
SCRIPT = [
    "Mañana tengo una entrevista de trabajo en un banco, después te cuento cómo me fue.",
    "Oye, cambiando de tema, ¿qué te gusta hacer en las tardes?",
    RELOAD,
    "Hola, ¿cómo estás hoy?",
    "¿Qué música te gusta escuchar cuando dibujas?",
    "¿Qué música te gusta escuchar cuando dibujas?",
    "Oye, ¿y qué música escuchas mientras dibujas?",
    "Estoy muy angustiado, me echaron del trabajo y no sé qué voy a hacer.",
]
SECTIONS = ("Cómo veo a esta persona:", "Cómo expresarme:")


def section(system: str, header: str) -> str | None:
    """El texto de una sección del prompt de sistema (hasta la siguiente sección), o None."""
    if header not in system:
        return None
    return system.split(header, 1)[1].split("\n\n", 1)[0].strip()


async def main() -> None:
    """Corre el guion y guarda lo observado."""
    parser = argparse.ArgumentParser()
    parser.add_argument("salida", type=Path)
    parser.add_argument("--entidad", required=True)
    parser.add_argument("--puerto", type=int, default=8011)
    args = parser.parse_args()
    base, ws = f"http://127.0.0.1:{args.puerto}", f"ws://127.0.0.1:{args.puerto}"
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
            chat = await websockets.connect(f"{ws}/ws/chat", max_size=None)
            try:
                for text in SCRIPT:
                    if text == RELOAD:
                        (await http.post(f"{base}/api/entities/{args.entidad}/load")).raise_for_status()
                        print("[recarga]", flush=True)
                        continue
                    await chat.send(json.dumps({"text": text}))
                    reply = ""
                    while True:
                        message = json.loads(await chat.recv())
                        if message["type"] == "token":
                            reply += message["text"]
                        else:
                            break
                    await asyncio.sleep(0.3)
                    turn = next(e for e in reversed(events) if e["type"] == "turn.completed")["payload"]
                    request = next(e for e in reversed(events) if e["type"] == "llm.request"
                                   and e["payload"]["preset"] in ("dialogue", "impulsive"))
                    system = request["payload"]["body"]["messages"][0]["content"]
                    memory = turn.get("memory") or {}
                    records.append({
                        "texto": text, "reply": reply, "signals": turn.get("signals", []),
                        "commitments": memory.get("commitments", []),
                        "seccion6": section(system, SECTIONS[0]), "seccion7": section(system, SECTIONS[1]),
                        "pizarra": turn.get("workspace"),
                    })
                    kinds = [f"{s['agent']}:{s['kind']}" for s in turn.get("signals", [])]
                    print(f"{text[:45]!r} → señales {kinds} · compromisos {memory.get('commitments', [])}", flush=True)
            finally:
                await chat.close()
        task.cancel()
    args.salida.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"guardado en {args.salida}")


asyncio.run(main())
