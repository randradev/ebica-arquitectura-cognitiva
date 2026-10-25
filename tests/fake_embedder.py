"""
Embedder simulado para las pruebas (sin torch ni descargas).

Usa el "hashing trick": cada palabra suma 1 en una posición del vector elegida
por su hash. Textos con palabras en común quedan cerca; es determinista, de
modo que el mismo texto da siempre el mismo vector.
"""

import hashlib
import math
import re
from collections.abc import Sequence

from ebica.perception.embeddings import EmbedKind

WORD = re.compile(r"\w+")


class FakeEmbedder:
    """Cumple la interfaz `Embedder` y registra las llamadas para inspeccionarlas."""

    def __init__(self, dimension: int = 16, model_name: str = "fake") -> None:
        """Crea el embedder con una dimensión chica, suficiente para las pruebas."""
        self.model_name = model_name
        self.dimension = dimension
        self.calls: list[tuple[list[str], EmbedKind]] = []

    def vector(self, text: str) -> list[float]:
        """Vector de norma 1 del texto; un texto sin palabras da el primer eje."""
        values = [0.0] * self.dimension
        for word in WORD.findall(text.lower()):
            bucket = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16) % self.dimension
            values[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in values))
        if norm == 0:
            values[0] = 1.0
            return values
        return [v / norm for v in values]

    async def embed(self, texts: Sequence[str], kind: EmbedKind) -> list[list[float]]:
        """Devuelve un vector por texto (el tipo no cambia el resultado, solo se registra)."""
        self.calls.append((list(texts), kind))
        return [self.vector(text) for text in texts]
