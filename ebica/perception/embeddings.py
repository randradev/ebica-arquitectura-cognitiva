"""
Embeddings en CPU: convertir texto en vectores de significado (§5.5, §9; D1-3).

Es la parte bottom-up del transductor perceptual. El mismo vector del mensaje
sirve para recuperar recuerdos (§7.3), para la vía baja (D1-4) y, más adelante,
para `repetition_watch` y la sorpresa de Fase 3.

El modelo elegido en CP2 es `BAAI/bge-m3` (1024 dimensiones): ver
`docs/fase-1/comparacion_embeddings.md`. La dimensión queda fija en los índices
vectoriales de Neo4j; cambiar de modelo obliga a recalcular la memoria.

`sentence-transformers` y `torch` son un extra opcional (`.[embeddings]`): se
importan solo al crear un `SentenceTransformerEmbedder`, de modo que el resto
del paquete y las pruebas unitarias funcionan sin ellos.
"""

import asyncio
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

# "query": el texto con que se busca (el mensaje que llega).
# "passage": el texto que se guarda para ser encontrado (un recuerdo).
EmbedKind = Literal["query", "passage"]

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"


@dataclass(frozen=True)
class ModelSpec:
    """Lo que hay que saber de un modelo para usarlo bien."""

    dimension: int
    # Prefijos con que se entrenó el modelo; sin ellos e5 recupera peor.
    query_prefix: str = ""
    passage_prefix: str = ""


# Modelos comparados en CP2. Solo se admiten modelos conocidos: así la
# dimensión del esquema se conoce sin cargar el modelo y no se olvida un prefijo.
KNOWN_MODELS: dict[str, ModelSpec] = {
    "BAAI/bge-m3": ModelSpec(dimension=1024),
    "intfloat/multilingual-e5-base": ModelSpec(
        dimension=768, query_prefix="query: ", passage_prefix="passage: "
    ),
}


class Embedder(Protocol):
    """Interfaz que usa el resto del sistema; las pruebas usan una implementación falsa."""

    model_name: str
    dimension: int

    async def embed(self, texts: Sequence[str], kind: EmbedKind) -> list[list[float]]:
        """Devuelve un vector de norma 1 por texto, en el mismo orden."""
        ...


def configured_model_name() -> str:
    """Nombre del modelo según `EBICA_EMBEDDING_MODEL`, o el elegido en CP2."""
    return os.environ.get("EBICA_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def model_spec(model_name: str) -> ModelSpec:
    """Devuelve la ficha de un modelo conocido, o falla con la lista de opciones."""
    try:
        return KNOWN_MODELS[model_name]
    except KeyError:
        raise ValueError(
            f"Modelo de embeddings desconocido: {model_name}. Opciones: {', '.join(KNOWN_MODELS)}"
        ) from None


class SentenceTransformerEmbedder:
    """
    Embedder real con `sentence-transformers`, en CPU.

    El modelo es lento de cargar (~3 s) y de invocar (~85 ms por mensaje con
    bge-m3), así que se carga una vez y cada llamada corre en un hilo aparte
    para no bloquear el bucle asyncio del motor (D3).
    """

    def __init__(self, model_name: str, model: Any, load_seconds: float = 0.0) -> None:
        """
        Envuelve un modelo ya cargado. Para cargarlo, usa `load()`.

        Recibir el modelo (en lugar de crearlo aquí) permite probar la clase
        con un modelo simulado, sin descargas.
        """
        spec = model_spec(model_name)
        self.model_name = model_name
        self.dimension = spec.dimension
        self.load_seconds = load_seconds
        self._spec = spec
        self._model = model
        # Una llamada a la vez: dos en paralelo competirían por los mismos
        # núcleos de CPU sin terminar antes.
        self._lock = asyncio.Lock()

    @classmethod
    async def load(cls, model_name: str | None = None) -> "SentenceTransformerEmbedder":
        """
        Carga el modelo (de la caché de HuggingFace; lo descarga si no está) en un hilo.

        Comprueba que la dimensión real coincida con la ficha, porque de ella
        depende el esquema de Neo4j.
        """
        name = model_name or configured_model_name()
        spec = model_spec(name)
        from sentence_transformers import SentenceTransformer

        started = time.perf_counter()
        model = await asyncio.to_thread(SentenceTransformer, name, device="cpu")
        load_seconds = time.perf_counter() - started
        actual = model.get_embedding_dimension()
        if actual != spec.dimension:
            raise ValueError(f"{name} produce vectores de {actual} dimensiones, no {spec.dimension}")
        return cls(name, model, load_seconds)

    async def embed(self, texts: Sequence[str], kind: EmbedKind) -> list[list[float]]:
        """
        Convierte textos en vectores de norma 1 (así coseno = producto punto).

        Añade el prefijo que corresponda a `kind` según el modelo.
        """
        if not texts:
            return []
        prefix = self._spec.query_prefix if kind == "query" else self._spec.passage_prefix
        prefixed = [prefix + text for text in texts]
        async with self._lock:
            vectors = await asyncio.to_thread(
                self._model.encode, prefixed, normalize_embeddings=True
            )
        return [list(map(float, vector)) for vector in vectors]
