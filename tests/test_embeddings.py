"""
Pruebas del embedder (Fase 1, CP2).

Las unitarias usan un modelo simulado o el embedder falso, sin descargas. La de
integración usa bge-m3 real y se omite si el extra `embeddings` no está
instalado o el modelo no está en la caché de HuggingFace.
"""

import math
import statistics
import time

import pytest

from ebica.perception.embeddings import (
    DEFAULT_EMBEDDING_MODEL,
    KNOWN_MODELS,
    SentenceTransformerEmbedder,
    configured_model_name,
    model_spec,
)
from fake_embedder import FakeEmbedder

# CONSTANTE: objetivo de latencia de un mensaje (PLAN, CP2).
MAX_MESSAGE_SECONDS = 0.150


class StubModel:
    """Imita `SentenceTransformer.encode` y guarda lo que recibió."""

    def __init__(self, dimension: int) -> None:
        """Modelo simulado que devuelve vectores fijos de la dimensión dada."""
        self.dimension = dimension
        self.received: list[tuple[list[str], dict]] = []

    def encode(self, texts: list[str], **kwargs) -> list[list[float]]:
        """Devuelve el primer eje para cada texto y registra la llamada."""
        self.received.append((texts, kwargs))
        return [[1.0] + [0.0] * (self.dimension - 1) for _ in texts]


def dot(a: list[float], b: list[float]) -> float:
    """Producto punto (coseno, con vectores normalizados)."""
    return sum(x * y for x, y in zip(a, b))


async def test_fake_embedder_is_deterministic_and_normalized():
    """El mismo texto da el mismo vector, de norma 1; las palabras compartidas acercan."""
    embedder = FakeEmbedder(dimension=64)
    perro, perro_again, banco = await embedder.embed(
        ["mi perro Toby", "mi perro Toby", "entrevista en el banco"], "passage"
    )
    [query] = await embedder.embed(["¿cómo está Toby?"], "query")

    assert perro == perro_again
    assert math.isclose(math.sqrt(dot(perro, perro)), 1.0)
    assert dot(query, perro) > dot(query, banco)


@pytest.mark.parametrize(
    ("model_name", "kind", "expected_text"),
    [
        ("intfloat/multilingual-e5-base", "query", "query: hola"),
        ("intfloat/multilingual-e5-base", "passage", "passage: hola"),
        ("BAAI/bge-m3", "query", "hola"),
        ("BAAI/bge-m3", "passage", "hola"),
    ],
)
async def test_embed_adds_the_model_prefix_and_normalizes(model_name, kind, expected_text):
    """Cada modelo recibe su prefijo según el tipo de texto, y se pide normalizar."""
    stub = StubModel(KNOWN_MODELS[model_name].dimension)
    embedder = SentenceTransformerEmbedder(model_name, stub)

    [vector] = await embedder.embed(["hola"], kind)

    texts, kwargs = stub.received[0]
    assert texts == [expected_text]
    assert kwargs["normalize_embeddings"] is True
    assert len(vector) == embedder.dimension
    assert all(isinstance(value, float) for value in vector)


async def test_embed_empty_list_does_not_call_the_model():
    """Sin textos no se invoca al modelo (ahorra una llamada en CPU)."""
    stub = StubModel(1024)
    embedder = SentenceTransformerEmbedder("BAAI/bge-m3", stub)

    assert await embedder.embed([], "query") == []
    assert stub.received == []


def test_unknown_model_is_rejected():
    """Un modelo fuera de la lista falla y dice cuáles se admiten."""
    with pytest.raises(ValueError, match="bge-m3"):
        model_spec("otro/modelo")


def test_configured_model_defaults_to_bge_m3(monkeypatch):
    """Sin `EBICA_EMBEDDING_MODEL` se usa el modelo elegido en CP2; con ella, el indicado."""
    monkeypatch.delenv("EBICA_EMBEDDING_MODEL", raising=False)
    assert configured_model_name() == DEFAULT_EMBEDDING_MODEL == "BAAI/bge-m3"

    monkeypatch.setenv("EBICA_EMBEDDING_MODEL", "intfloat/multilingual-e5-base")
    assert configured_model_name() == "intfloat/multilingual-e5-base"


@pytest.fixture
async def real_embedder():
    """bge-m3 real desde la caché, o se omite si no está instalado o descargado."""
    pytest.importorskip("sentence_transformers")
    from huggingface_hub import try_to_load_from_cache

    if not isinstance(try_to_load_from_cache(DEFAULT_EMBEDDING_MODEL, "config.json"), str):
        pytest.skip(f"{DEFAULT_EMBEDDING_MODEL} no está en la caché de HuggingFace")
    return await SentenceTransformerEmbedder.load(DEFAULT_EMBEDDING_MODEL)


@pytest.mark.integration
async def test_real_embedder_dimension_meaning_and_latency(real_embedder):
    """
    bge-m3 real: 1024 dimensiones, norma 1, una paráfrasis queda más cerca
    que un texto ajeno, y un mensaje tarda menos que el objetivo de CP2.
    """
    fear, storm, bread = await real_embedder.embed(
        ["Le tengo miedo a las tormentas eléctricas.", "Los truenos me asustan mucho.",
         "Compré pan en la panadería de la esquina."],
        "passage",
    )

    assert len(fear) == 1024
    assert math.isclose(math.sqrt(dot(fear, fear)), 1.0, rel_tol=1e-4)
    assert dot(fear, storm) > dot(fear, bread)

    await real_embedder.embed(["calentamiento"], "query")
    latencies = []
    for _ in range(10):
        started = time.perf_counter()
        await real_embedder.embed(["¿Hay algo que te asuste?"], "query")
        latencies.append(time.perf_counter() - started)
    print(f"\nbge-m3: carga {real_embedder.load_seconds:.1f} s, mediana por mensaje "
          f"{statistics.median(latencies) * 1000:.0f} ms (máx. {max(latencies) * 1000:.0f} ms)")
    assert statistics.median(latencies) < MAX_MESSAGE_SECONDS
