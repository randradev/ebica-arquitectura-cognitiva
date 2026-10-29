"""
Repite en vivo los mensajes de una sesión registrada (CP10b parte C).

Lee el JSONL de eventos de una sesión real, toma en orden los mensajes del
usuario (`perception.input`) y los cambios de interlocutor
(`tom.partner_switched`), y los vuelve a enviar a un servidor real, con el motor
actual: mismas personas y mismos mensajes, pero nuevos appraisals y nuevas
respuestas. Los eventos de la sesión nueva quedan en la carpeta de la entidad
de prueba y se comparan con `reproducir_afecto.py`.

Preparación como en `prueba_recuerdo_vivo.py` (copia de la config con otro id,
servidor en otro puerto).
    .venv/Scripts/python.exe scripts/repetir_sesion_vivo.py <eventos.jsonl> --entidad <id> [--puerto 8011]
"""

import argparse
import asyncio
import json
from pathlib import Path

import httpx
import websockets


def plan(events: list[dict]) -> list[tuple[str, str]]:
    """Los pasos de la sesión: ("persona", nombre) al cambiar de interlocutor y ("mensaje", texto)."""
    names: dict[str, str] = {}
    steps: list[tuple[str, str]] = []
    for event in events:
        if event["type"] == "tom.partner_switched":
            person = event["payload"]["person"]
            names[person["id"]] = person["name"]
            steps.append(("persona", person["name"]))
        elif event["type"] == "perception.input" and event["payload"].get("source") == "user":
            steps.append(("mensaje", event["payload"]["text"]))
    return steps


async def main() -> None:
    """Envía la sesión paso a paso e informa la valencia tras cada turno."""
    parser = argparse.ArgumentParser()
    parser.add_argument("eventos", type=Path)
    parser.add_argument("--entidad", required=True)
    parser.add_argument("--puerto", type=int, default=8011)
    args = parser.parse_args()
    base, ws = f"http://127.0.0.1:{args.puerto}", f"ws://127.0.0.1:{args.puerto}"
    events = [json.loads(line) for line in args.eventos.read_text(encoding="utf-8").splitlines() if line.strip()]
    async with httpx.AsyncClient(timeout=180) as http:
        (await http.post(f"{base}/api/entities/{args.entidad}/load")).raise_for_status()
        async with websockets.connect(f"{ws}/ws/chat", max_size=None) as chat:
            for kind, value in plan(events):
                if kind == "persona":
                    people = (await http.get(f"{base}/api/people")).json()["people"]
                    known = next((p for p in people if p["name"] == value), None)
                    if known:
                        (await http.post(f"{base}/api/people/{known['id']}/activate")).raise_for_status()
                    else:
                        (await http.post(f"{base}/api/people", json={"name": value})).raise_for_status()
                    print(f"[persona] {value}", flush=True)
                    continue
                await chat.send(json.dumps({"text": value}))
                while json.loads(await chat.recv())["type"] == "token":
                    pass
                print(f"enviado: {value[:60]!r}", flush=True)


asyncio.run(main())
