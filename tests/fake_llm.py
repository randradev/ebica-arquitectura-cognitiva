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


# Appraisal de un mensaje neutro, para las pruebas que no miran el afecto.
NEUTRAL_APPRAISAL = {
    "user_emotion": {"valence": 0.0, "arousal": 0.2, "dominance": 0.5},
    "user_intent": "saludar", "topics": ["saludo"], "hostility": 0.0, "distress": 0.0,
    "self_relevance": 0.0, "goal_congruence": 0.0, "novelty": 0.0,
    "commitments": [], "mentioned_people": [],
}


def turn_transport(*pieces: str, appraisal: dict | str = NEUTRAL_APPRAISAL):
    """
    Servidor LLM simulado para un turno completo (CP5): appraisal + diálogo.

    Si la petición pide salida estructurada (`response_format`), es el
    appraisal y responde `appraisal` (un dict, o un texto para simular JSON
    roto); si no, responde el diálogo con `pieces`. Devuelve el transporte y
    la lista donde se guardan los cuerpos recibidos, para inspeccionarlos.
    """
    bodies: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        """Elige la respuesta según el tipo de llamada."""
        body = json.loads(request.content)
        bodies.append(body)
        if "response_format" in body:
            text = appraisal if isinstance(appraisal, str) else json.dumps(appraisal)
            return httpx.Response(200, content=sse(text))
        return httpx.Response(200, content=sse(*pieces))

    return httpx.MockTransport(handle), bodies
