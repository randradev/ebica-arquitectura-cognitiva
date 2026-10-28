"""
Sondeo de la fuente de los recuerdos, en vivo (CP8, D1-57).

¿Cuenta la entidad como propio lo que le contó el usuario? Conversa por
WebSocket con un servidor real, en el orden de `benchmarks/fuente/cases.yaml`:
1. la «sesión» de `benchmarks/recuerdo/cases.yaml` (el usuario cuenta cosas de sí);
2. el relleno de `prueba_recuerdo_vivo.py`, para que la sesión salga de la
   conversación reciente;
3. los bloques `memoria`, `atribucion` y `reciente` del sondeo.
Guarda cada respuesta con lo recuperado y escribe una tabla en Markdown para el
juicio manual (`apropia`, `atribuye`, `inventa`).

Con `--cruces` (CP8 C) corre en cambio la prueba de cruces entre personas: el
`primary` (Ricardo) cuenta la sesión y hace el relleno; se crea a Ana por la API
(`POST /api/people`), que cuenta lo suyo, hace el relleno y pregunta; se vuelve
a Ricardo (`POST /api/people/ricardo/activate`), que pregunta lo mismo.

Preparación (no toca la memoria real de Calisto), igual que `prueba_recuerdo_vivo.py`:
1. Copiar la config de Calisto a `<tmp>/<id>/config.yaml` con otro `id`.
2. `EBICA_ENTITIES_DIR=<tmp> EBICA_API_PORT=8011 .venv/Scripts/python.exe -m ebica.api`
3. `.venv/Scripts/python.exe scripts/prueba_fuente_vivo.py <salida.json> --entidad <id> [--puerto 8011] [--cruces]`
4. Al terminar: detener el servidor y borrar los nodos y la carpeta. Para otra
   repetición, una entidad nueva (otro id), así nada se arrastra de la anterior.
"""

import argparse
import asyncio
import json
from pathlib import Path

import httpx
import websockets
import yaml

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmarks" / "fuente" / "cases.yaml"
SESSION = ROOT / "benchmarks" / "recuerdo" / "cases.yaml"
# El mismo relleno que `prueba_recuerdo_vivo.py`, para comparar con CP7.
FILLER = [
    "Oye, cambiando de tema, ¿en qué estás pensando ahora?",
    "¿Qué te parece el día de hoy?",
    "Cuéntame algo que te guste mucho.",
    "¿Te aburres a veces?",
    "¿Qué opinas de las redes sociales?",
    "Bueno, dejemos esto por ahora.",
]
BLOCKS = ("memoria", "atribucion", "reciente")


async def ask(chat, events: list[dict], text: str) -> tuple[str, dict]:
    """Envía un mensaje, junta la respuesta en streaming y devuelve el `turn.completed` del turno."""
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
    return reply, turn["payload"]


def markdown(records: list[dict]) -> str:
    """Tabla para el juicio manual: una fila por pregunta, con columnas vacías para juzgar."""
    lines = ["| id | pregunta | recuperado | respuesta | apropia | atribuye | inventa |", "|---|---|---|---|---|---|---|"]
    for record in records:
        if record["bloque"] not in (*BLOCKS, "cruces"):
            continue
        # Los episodios de diálogo tienen ids aleatorios: se muestra el comienzo del texto.
        recalled = "; ".join(e[0] if e[1] == "seed" else e[3][:50] for e in record["episodes"]) or "—"
        recalled = recalled.replace("|", "/")
        reply = " ".join(record["reply"].split()).replace("|", "/")
        lines.append(f"| {record['id']} | {record['text']} | {recalled} | {reply} |  |  |  |")
    return "\n".join(lines) + "\n"


async def main() -> None:
    """Corre la conversación completa y guarda lo observado (JSON y tabla Markdown)."""
    parser = argparse.ArgumentParser()
    parser.add_argument("salida", type=Path)
    parser.add_argument("--entidad", required=True)
    parser.add_argument("--puerto", type=int, default=8011)
    parser.add_argument("--cruces", action="store_true")
    args = parser.parse_args()
    base, ws = f"http://127.0.0.1:{args.puerto}", f"ws://127.0.0.1:{args.puerto}"

    cases = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    session = yaml.safe_load(SESSION.read_text(encoding="utf-8"))["sesion"]
    plan = ([("sesion", item["id"], item["mensaje"]) for item in session]
            + [("relleno", f"relleno-{i}", text) for i, text in enumerate(FILLER, 1)])
    if args.cruces:
        # ("persona", …) cambia de interlocutor por la API antes de seguir.
        ana, ricardo = cases["cruces"]["ana"], cases["cruces"]["ricardo"]
        plan += ([("persona", "nueva", ana["nombre"])]
                 + [("sesion-ana", f"ana-{i}", text) for i, text in enumerate(ana["sesion"], 1)]
                 + [("relleno", f"relleno-ana-{i}", text) for i, text in enumerate(FILLER, 1)]
                 + [("cruces", q["id"], q["texto"]) for q in ana["preguntas"]]
                 + [("persona", "activar", "ricardo")]
                 + [("cruces", q["id"], q["texto"]) for q in ricardo["preguntas"]])
    else:
        probe = cases["sondeo_fuente"]
        plan += [(block, case["id"], case["texto"]) for block in BLOCKS for case in probe[block]]
    events: list[dict] = []
    records = []
    async with websockets.connect(f"{ws}/ws/events") as events_ws:
        async def collect() -> None:
            """Acumula los eventos del bus."""
            async for raw in events_ws:
                events.append(json.loads(raw))

        task = asyncio.create_task(collect())
        async with httpx.AsyncClient(timeout=180) as http:
            response = await http.post(f"{base}/api/entities/{args.entidad}/load")
            response.raise_for_status()
        async with websockets.connect(f"{ws}/ws/chat", max_size=None) as chat, httpx.AsyncClient(timeout=60) as http:
            for block, key, text in plan:
                if block == "persona":
                    if key == "nueva":
                        response = await http.post(f"{base}/api/people", json={"name": text})
                    else:
                        response = await http.post(f"{base}/api/people/{text}/activate")
                    response.raise_for_status()
                    print(f"[persona] {key} {text}: HTTP {response.status_code}", flush=True)
                    continue
                reply, turn = await ask(chat, events, text)
                retrieval = turn.get("retrieval") or {}
                records.append({
                    "bloque": block, "id": key, "text": text, "reply": reply,
                    "impulsive": turn["impulsive"],
                    "episodes": [(e["id"], e["kind"], e["total"], e["preview"]) for e in retrieval.get("episodes", [])],
                    "facts": [(f["id"], f["text"]) for f in retrieval.get("facts", [])],
                })
                print(f"[{block}] {key}: {len(retrieval.get('episodes', []))} ep → {reply[:80]!r}", flush=True)
        task.cancel()
    args.salida.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    args.salida.with_suffix(".md").write_text(markdown(records), encoding="utf-8")
    print(f"guardado en {args.salida} y {args.salida.with_suffix('.md')}")


asyncio.run(main())
