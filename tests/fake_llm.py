"""
Servidor LLM simulado para las pruebas (sin GPU ni Ollama).

Produce respuestas con el mismo formato de streaming SSE que la API
compatible con OpenAI de Ollama.
"""

import asyncio
import json

import httpx


def sse(*pieces: str, usage: dict | None = None) -> bytes:
    """Construye un cuerpo SSE como el de Ollama: un fragmento por pieza, usage y [DONE]."""
    lines = []
    for index, piece in enumerate(pieces):
        finish = "stop" if index == len(pieces) - 1 else None
        chunk = {"choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": finish}]}
        lines.append(f"data: {json.dumps(chunk)}\n\n")
    if usage is not None:
        lines.append(f"data: {json.dumps({'choices': [], 'usage': usage})}\n\n")
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode("utf-8")


class HangingStream(httpx.AsyncByteStream):
    """Cuerpo que envía un fragmento y luego queda esperando, como un modelo generando lento."""

    def __init__(self) -> None:
        """Prepara la señal de que el cliente cerró la conexión."""
        self.closed = asyncio.Event()

    async def __aiter__(self):
        """Entrega un fragmento y se bloquea indefinidamente."""
        chunk = {"choices": [{"index": 0, "delta": {"content": "Hola"}, "finish_reason": None}]}
        yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
        await asyncio.Event().wait()

    async def aclose(self) -> None:
        """Registra que el cliente cerró la conexión (el servidor dejaría de generar)."""
        self.closed.set()


def drain(queue: asyncio.Queue) -> list:
    """Saca todos los eventos pendientes de una cola de suscriptor."""
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events
