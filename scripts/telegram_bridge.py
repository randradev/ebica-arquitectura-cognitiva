"""
Puente de Telegram (utilidad fuera del plan de Fase 1, pedida por el usuario el 2026-10-28).

Permite hablarle a la entidad desde el celular durante el día. El servidor de
EBICA sigue corriendo en el PC; este script, también en el PC, consulta a
Telegram por mensajes nuevos (long polling, sin abrir puertos), reenvía cada
mensaje al chat local (`/ws/chat`, como la consola) y devuelve la respuesta.

Seguridad: solo atiende al chat de `TELEGRAM_ALLOWED_CHAT_ID`; cualquier otro
mensaje se ignora y su id se muestra en la terminal (así se averigua el propio
la primera vez). Privacidad: los mensajes pasan por los servidores de Telegram.

Variables en `.env`:
    TELEGRAM_BOT_TOKEN=...        (lo da @BotFather)
    TELEGRAM_ALLOWED_CHAT_ID=...  (tu id; si falta, el script lo muestra al escribirle)
Uso, con el servidor ya corriendo (`python -m ebica.api`):
    .venv/Scripts/python.exe scripts/telegram_bridge.py [--entidad calisto] [--puerto 8000]
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx
import websockets
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
# CONSTANTE: espera máxima de cada consulta a Telegram (long polling).
POLL_SECONDS = 50
# CONSTANTE: pausa antes de reintentar si se cae la red o el servidor.
RETRY_SECONDS = 5
# CONSTANTE: largo máximo de un mensaje de Telegram.
TELEGRAM_MAX_CHARS = 4096


async def ask_entity(ws_url: str, text: str) -> str:
    """Envía un mensaje al chat local y devuelve la respuesta completa (o el error del servidor)."""
    async with websockets.connect(f"{ws_url}/ws/chat", max_size=None) as chat:
        await chat.send(json.dumps({"text": text}))
        reply = ""
        while True:
            message = json.loads(await chat.recv())
            if message["type"] == "token":
                reply += message["text"]
            elif message["type"] == "error":
                return f"(error del servidor: {message['message']})"
            else:
                return reply.strip() or "(sin respuesta)"


async def main() -> None:
    """Carga la entidad y atiende los mensajes de Telegram hasta que se detenga con Ctrl+C."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--entidad", default="calisto")
    parser.add_argument("--puerto", type=int, default=int(os.environ.get("EBICA_API_PORT", 8000)))
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN en .env (créalo con @BotFather en Telegram)")
    allowed = os.environ.get("TELEGRAM_ALLOWED_CHAT_ID")
    api = f"https://api.telegram.org/bot{token}"
    base, ws_url = f"http://127.0.0.1:{args.puerto}", f"ws://127.0.0.1:{args.puerto}"

    async with httpx.AsyncClient(timeout=POLL_SECONDS + 15) as http:
        loaded = await http.get(f"{base}/api/entities")
        if loaded.json().get("active") != args.entidad:
            (await http.post(f"{base}/api/entities/{args.entidad}/load")).raise_for_status()
        print(f"Puente listo: {args.entidad} en {base}. Chat permitido: {allowed or '(ninguno: escríbele al bot)'}")
        offset = None
        while True:
            try:
                response = await http.get(f"{api}/getUpdates", params={"timeout": POLL_SECONDS, "offset": offset})
                updates = response.json().get("result", [])
            except (httpx.HTTPError, ValueError) as error:
                print(f"Telegram no responde ({error}); reintento en {RETRY_SECONDS} s")
                await asyncio.sleep(RETRY_SECONDS)
                continue
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message") or {}
                chat_id, text = str(message.get("chat", {}).get("id", "")), message.get("text")
                if not text:
                    continue
                if chat_id != allowed:
                    print(f"Mensaje ignorado del chat {chat_id}. Si eres tú: TELEGRAM_ALLOWED_CHAT_ID={chat_id}")
                    continue
                if text.startswith("/start"):
                    await http.post(f"{api}/sendMessage", json={"chat_id": chat_id, "text": "Conectado. Escribe."})
                    continue
                await http.post(f"{api}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
                try:
                    reply = await ask_entity(ws_url, text)
                except (OSError, websockets.WebSocketException) as error:
                    reply = f"(el servidor de EBICA no responde: {error})"
                await http.post(f"{api}/sendMessage",
                                json={"chat_id": chat_id, "text": reply[:TELEGRAM_MAX_CHARS]})


if __name__ == "__main__":
    asyncio.run(main())
