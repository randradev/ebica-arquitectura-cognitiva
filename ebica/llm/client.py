"""
Cliente del LLM local (CorticalInferenceEngine, documento base §5.13).

Habla con cualquier servidor compatible con la API de OpenAI (Ollama en Fase 0,
D0-2; llama.cpp más adelante solo cambia la URL). Toda llamada emite eventos:
`llm.request` con el prompt completo, y después `llm.response`, `llm.cancelled`
o `llm.error`, encadenados por `cause_id`.

Cancelar una generación = cancelar la tarea asyncio que la consume. El cliente
cierra la conexión HTTP y el servidor deja de generar (base de la cola de GPU
con interrupción, D4, que llega en Fase 1).
"""

import asyncio
import json
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from ebica.core.events import EventBus

# CONSTANTES: valores por defecto si no hay variables de entorno (.env.example).
DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "llama3.1"

# CONSTANTE: tiempos de espera de la conexión HTTP.
# `read` es amplio porque la primera llamada carga el modelo en la GPU
# (medido: ~20 s con llama3.1 en la RTX 3070).
HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)


@dataclass(frozen=True)
class SamplingPreset:
    """Parámetros de muestreo para un uso concreto del mismo modelo (D5)."""

    name: str
    temperature: float
    max_tokens: int
    # Pide al servidor que la salida sea un objeto JSON válido.
    json_mode: bool = False


# Presets de §5.13. Fase 0 solo define los dos que usa; `thought`,
# `impulsive` y `consolidation` llegan con sus mecanismos (Fases 1–2).
PRESETS: dict[str, SamplingPreset] = {
    "dialogue": SamplingPreset("dialogue", temperature=0.7, max_tokens=400),
    "appraisal": SamplingPreset("appraisal", temperature=0.2, max_tokens=400, json_mode=True),
}


class LLMError(RuntimeError):
    """El servidor no está disponible o respondió con un error."""


@dataclass
class LLMResult:
    """Resultado completo de una generación, con métricas de rendimiento (§12)."""

    text: str = ""
    finish_reason: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    # Segundos desde el envío hasta el primer fragmento de texto y hasta el final.
    first_token_s: float | None = None
    total_s: float | None = None


class LLMClient:
    """
    Cliente asíncrono con streaming, presets y cancelación.

    Úsalo con `async with LLMClient(...) as client:` para cerrar la conexión al terminar.
    """

    def __init__(
        self,
        bus: EventBus,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """
        Prepara el cliente HTTP.

        `transport` permite sustituir el servidor real por uno simulado en las pruebas.
        """
        self.bus = bus
        self.base_url = base_url
        self.model = model
        self._http = httpx.AsyncClient(base_url=base_url, timeout=HTTP_TIMEOUT, transport=transport)

    @classmethod
    def from_env(
        cls, bus: EventBus, transport: httpx.AsyncBaseTransport | None = None
    ) -> "LLMClient":
        """Crea el cliente con `EBICA_LLM_BASE_URL` y `EBICA_LLM_MODEL` (o los valores por defecto)."""
        return cls(
            bus,
            base_url=os.environ.get("EBICA_LLM_BASE_URL", DEFAULT_BASE_URL),
            model=os.environ.get("EBICA_LLM_MODEL", DEFAULT_MODEL),
            transport=transport,
        )

    async def __aenter__(self) -> "LLMClient":
        """Permite usar el cliente con `async with`."""
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Cierra la conexión HTTP al salir del bloque `async with`."""
        await self.aclose()

    async def aclose(self) -> None:
        """Cierra el cliente HTTP y sus conexiones."""
        await self._http.aclose()

    async def is_available(self) -> bool:
        """Comprueba con una petición ligera (`GET /models`) si el servidor responde."""
        try:
            response = await self._http.get("/models", timeout=2.0)
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        entity_id: str,
        preset: str = "dialogue",
        cause_id: str | None = None,
    ) -> AsyncIterator[str]:
        """
        Genera una respuesta y la entrega fragmento a fragmento.

        `messages` usa el formato de OpenAI (`{"role": ..., "content": ...}`).
        Para cancelar, cancela la tarea que recorre el iterador.
        """
        return self._generate(messages, entity_id, preset, cause_id, LLMResult())

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        entity_id: str,
        preset: str = "dialogue",
        cause_id: str | None = None,
    ) -> LLMResult:
        """Genera una respuesta completa (usa streaming por dentro) y devuelve el resultado."""
        result = LLMResult()
        async for _ in self._generate(messages, entity_id, preset, cause_id, result):
            pass
        return result

    def _build_body(self, messages: list[dict[str, str]], sampling: SamplingPreset) -> dict[str, Any]:
        """Arma el cuerpo de la petición `/chat/completions` según el preset."""
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": sampling.temperature,
            "max_tokens": sampling.max_tokens,
            "stream": True,
            # Pide el conteo de tokens en el último fragmento del streaming.
            "stream_options": {"include_usage": True},
        }
        if sampling.json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    async def _generate(
        self,
        messages: list[dict[str, str]],
        entity_id: str,
        preset: str,
        cause_id: str | None,
        result: LLMResult,
    ) -> AsyncIterator[str]:
        """
        Envía la petición, recorre el streaming y emite los eventos.

        Rellena `result` a medida que avanza, para que `complete()` lo devuelva.
        """
        if preset not in PRESETS:
            raise ValueError(f"Preset desconocido: '{preset}'. Disponibles: {sorted(PRESETS)}")
        body = self._build_body(messages, PRESETS[preset])

        # El evento lleva el cuerpo completo: es exactamente lo que recibe el
        # modelo, para poder verlo en la consola (§8.3, "PROMPT EXACTO").
        request_event = self.bus.emit(
            entity_id, "llm.request", {"preset": preset, "body": body}, cause_id=cause_id
        )
        started = time.perf_counter()
        chunks: list[str] = []

        try:
            async with self._http.stream("POST", "/chat/completions", json=body) as response:
                if response.status_code != 200:
                    detail = (await response.aread()).decode("utf-8", errors="replace")
                    raise LLMError(f"El servidor LLM respondió {response.status_code}: {detail[:300]}")
                async for line in response.aiter_lines():
                    delta = self._parse_line(line, result)
                    if delta:
                        if result.first_token_s is None:
                            result.first_token_s = time.perf_counter() - started
                        chunks.append(delta)
                        yield delta
        except (asyncio.CancelledError, GeneratorExit):
            # Se registra lo que alcanzó a generarse antes de la interrupción
            # (en Fase 1, un pensamiento cancelado → `thought.interrupted`).
            self.bus.emit(
                entity_id,
                "llm.cancelled",
                {"partial_text": "".join(chunks), "elapsed_s": time.perf_counter() - started},
                cause_id=request_event.id,
            )
            raise
        except httpx.HTTPError as error:
            message = f"No se pudo completar la llamada al LLM en {self.base_url}: {error!r}"
            self._emit_error(entity_id, message, request_event.id)
            raise LLMError(message) from error
        except LLMError as error:
            self._emit_error(entity_id, str(error), request_event.id)
            raise

        result.text = "".join(chunks)
        result.total_s = time.perf_counter() - started
        self.bus.emit(
            entity_id,
            "llm.response",
            {
                "text": result.text,
                "finish_reason": result.finish_reason,
                "usage": result.usage,
                "first_token_s": result.first_token_s,
                "total_s": result.total_s,
            },
            cause_id=request_event.id,
        )

    def _emit_error(self, entity_id: str, message: str, request_id: str) -> None:
        """
        Emite `llm.error` encadenado a su `llm.request`.

        No figura en la tabla §8.2; se añade para que un fallo del servidor
        quede visible en la consola y en el JSONL, igual que un éxito (D10).
        """
        self.bus.emit(entity_id, "llm.error", {"message": message}, cause_id=request_id)

    @staticmethod
    def _parse_line(line: str, result: LLMResult) -> str:
        """
        Interpreta una línea del streaming SSE y devuelve el texto nuevo ("" si no hay).

        Formato: `data: {json}` por fragmento y `data: [DONE]` al final. El
        último fragmento trae `usage` con `choices` vacío. Efecto secundario:
        guarda `finish_reason` y `usage` en `result`.
        """
        if not line.startswith("data: "):
            return ""
        data = line[len("data: "):]
        if data == "[DONE]":
            return ""
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError as error:
            raise LLMError(f"Fragmento de streaming no es JSON válido: {data[:200]}") from error
        if chunk.get("usage"):
            result.usage = chunk["usage"]
        choices = chunk.get("choices") or []
        if not choices:
            return ""
        if choices[0].get("finish_reason"):
            result.finish_reason = choices[0]["finish_reason"]
        return choices[0].get("delta", {}).get("content") or ""
