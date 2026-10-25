"""
Pruebas del cliente LLM con un servidor simulado (CP3).

No usan GPU ni Ollama: `httpx.MockTransport` responde como lo haría la API
compatible con OpenAI, con el mismo formato de streaming SSE.
"""

import asyncio
import json

import httpx
import pytest
from fake_llm import HangingStream, drain, sse

from ebica.core.events import EventBus
from ebica.llm.client import LLMClient, LLMError

MESSAGES = [
    {"role": "system", "content": "Eres Ejemplo."},
    {"role": "user", "content": "Hola"},
]


def make_client(bus: EventBus, handler) -> LLMClient:
    """Crea un cliente cuyo servidor es la función `handler`."""
    return LLMClient(bus, base_url="http://llm.test/v1", model="modelo-prueba",
                     transport=httpx.MockTransport(handler))


async def test_stream_yields_fragments_in_order():
    """El streaming entrega los fragmentos en el orden en que llegan."""
    bus = EventBus()
    async with make_client(bus, lambda request: httpx.Response(200, content=sse("Ho", "la", "!"))) as client:
        pieces = [piece async for piece in client.stream(MESSAGES, entity_id="ejemplo")]

    assert pieces == ["Ho", "la", "!"]


async def test_request_event_contains_full_prompt():
    """`llm.request` lleva el cuerpo exacto enviado al servidor, incluidos los mensajes."""
    bus = EventBus()
    queue = bus.subscribe()
    sent_bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        """Guarda lo que recibió el servidor simulado."""
        sent_bodies.append(json.loads(request.content))
        return httpx.Response(200, content=sse("ok"))

    async with make_client(bus, handler) as client:
        await client.complete(MESSAGES, entity_id="ejemplo", cause_id="perception-1")

    request_event = drain(queue)[0]
    assert request_event.type == "llm.request"
    assert request_event.cause_id == "perception-1"
    assert request_event.payload["body"] == sent_bodies[0]
    assert request_event.payload["body"]["messages"] == MESSAGES


async def test_response_event_chains_to_request():
    """`llm.response` trae el texto completo y apunta a su `llm.request`."""
    bus = EventBus()
    queue = bus.subscribe()
    usage = {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}

    async with make_client(bus, lambda request: httpx.Response(200, content=sse("Ho", "la", usage=usage))) as client:
        result = await client.complete(MESSAGES, entity_id="ejemplo")

    request_event, response_event = drain(queue)
    assert response_event.type == "llm.response"
    assert response_event.cause_id == request_event.id
    assert response_event.payload["text"] == "Hola" == result.text
    assert result.usage == usage
    assert result.finish_reason == "stop"
    assert result.first_token_s is not None and result.total_s >= result.first_token_s


async def test_presets_change_sampling_and_json_mode():
    """`dialogue` y `appraisal` envían temperaturas distintas; solo `appraisal` pide JSON."""
    bus = EventBus()
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        """Guarda cada cuerpo recibido."""
        bodies.append(json.loads(request.content))
        return httpx.Response(200, content=sse("{}"))

    async with make_client(bus, handler) as client:
        await client.complete(MESSAGES, entity_id="ejemplo", preset="dialogue")
        await client.complete(MESSAGES, entity_id="ejemplo", preset="appraisal")

    dialogue, appraisal = bodies
    assert dialogue["temperature"] == 0.7 and "response_format" not in dialogue
    assert appraisal["temperature"] == 0.2
    assert appraisal["response_format"] == {"type": "json_object"}


async def test_unknown_preset_is_rejected():
    """Un preset inexistente falla antes de llamar al servidor."""
    bus = EventBus()
    async with make_client(bus, lambda request: httpx.Response(200, content=sse("x"))) as client:
        with pytest.raises(ValueError, match="Preset desconocido"):
            await client.complete(MESSAGES, entity_id="ejemplo", preset="inventado")


async def test_cancelling_task_emits_cancelled_and_closes_connection():
    """Cancelar la tarea emite `llm.cancelled` con el texto parcial y cierra la conexión."""
    bus = EventBus()
    queue = bus.subscribe()
    body = HangingStream()
    received = []

    async with make_client(bus, lambda request: httpx.Response(200, stream=body)) as client:

        async def consume() -> None:
            """Recorre el streaming como lo haría la consola."""
            async for piece in client.stream(MESSAGES, entity_id="ejemplo"):
                received.append(piece)

        task = asyncio.create_task(consume())
        while not received:  # esperar al primer fragmento
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    request_event, cancelled_event = drain(queue)
    assert cancelled_event.type == "llm.cancelled"
    assert cancelled_event.cause_id == request_event.id
    assert cancelled_event.payload["partial_text"] == "Hola"
    assert body.closed.is_set()


async def test_server_error_raises_and_emits_error_event():
    """Una respuesta HTTP de error produce `LLMError` y un evento `llm.error`."""
    bus = EventBus()
    queue = bus.subscribe()

    async with make_client(bus, lambda request: httpx.Response(404, text="model not found")) as client:
        with pytest.raises(LLMError, match="404"):
            await client.complete(MESSAGES, entity_id="ejemplo")

    request_event, error_event = drain(queue)
    assert error_event.type == "llm.error"
    assert error_event.cause_id == request_event.id
    assert "model not found" in error_event.payload["message"]


async def test_unreachable_server_gives_clear_error():
    """Si el servidor no responde, el error dice a qué URL se intentó conectar."""
    bus = EventBus()

    def handler(request: httpx.Request) -> httpx.Response:
        """Simula un servidor apagado."""
        raise httpx.ConnectError("conexión rechazada", request=request)

    async with make_client(bus, handler) as client:
        with pytest.raises(LLMError, match="http://llm.test/v1"):
            await client.complete(MESSAGES, entity_id="ejemplo")


async def test_malformed_chunk_raises_llm_error():
    """Un fragmento que no es JSON se informa como `LLMError`, no como un error crudo."""
    bus = EventBus()
    async with make_client(bus, lambda request: httpx.Response(200, content=b"data: {roto\n\n")) as client:
        with pytest.raises(LLMError, match="no es JSON"):
            await client.complete(MESSAGES, entity_id="ejemplo")


@pytest.mark.integration
async def test_real_ollama_streams_text():
    """Con Ollama encendido, la respuesta real llega en varios fragmentos (se omite si no hay servidor)."""
    bus = EventBus()
    async with LLMClient.from_env(bus) as client:
        if not await client.is_available():
            pytest.skip(f"Servidor LLM no disponible en {client.base_url}")
        pieces = [
            piece
            async for piece in client.stream(
                [{"role": "user", "content": "Cuenta del uno al cinco en español."}],
                entity_id="ejemplo",
            )
        ]

    assert len(pieces) > 1
    assert "".join(pieces).strip()


async def test_from_env_reads_variables(monkeypatch):
    """`from_env` usa las variables de `.env.example`."""
    monkeypatch.setenv("EBICA_LLM_BASE_URL", "http://otro:1234/v1")
    monkeypatch.setenv("EBICA_LLM_MODEL", "otro-modelo")

    async with LLMClient.from_env(EventBus()) as client:
        assert client.base_url == "http://otro:1234/v1"
        assert client.model == "otro-modelo"


async def test_response_schema_restricts_output_format():
    """Con `response_schema` se envía `json_schema` (salida restringida) en lugar de `json_object`."""
    bus = EventBus()
    sent_bodies = []
    schema = {"type": "object", "properties": {"x": {"type": "number"}}, "required": ["x"]}

    def handler(request: httpx.Request) -> httpx.Response:
        """Guarda lo que recibió el servidor simulado."""
        sent_bodies.append(json.loads(request.content))
        return httpx.Response(200, content=sse('{"x": 1}'))

    async with make_client(bus, handler) as client:
        await client.complete(MESSAGES, entity_id="ejemplo", preset="appraisal", response_schema=schema)
        await client.complete(MESSAGES, entity_id="ejemplo", preset="appraisal")

    with_schema, without_schema = sent_bodies
    assert with_schema["response_format"] == {
        "type": "json_schema", "json_schema": {"name": "response", "strict": True, "schema": schema}}
    assert without_schema["response_format"] == {"type": "json_object"}
