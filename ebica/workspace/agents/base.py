"""
Contrato de los micro-agentes (§5.10; D1-69).

- `Board`: la foto de lo que los micro-agentes pueden mirar en un turno. Es
  inmutable (`frozen`): un micro-agente no puede cambiar la pizarra, solo leerla.
- `Signal`: lo único que un micro-agente produce. El orquestador decide qué
  efecto tiene (§5.6: solo el orquestador escribe).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from ebica.perception.appraisal import Appraisal


@dataclass(frozen=True)
class OpenCommitment:
    """Un compromiso abierto de la persona activa (para `commitment_watch`)."""

    id: str
    text: str
    ts: datetime
    # El comienzo del mensaje en que se prometió (puede faltar en datos viejos).
    context: str | None = None


@dataclass(frozen=True)
class Board:
    """
    Foto de solo lectura del turno, armada por el orquestador.

    Los vectores son embeddings de `bge-m3` (o del embedder simulado en las
    pruebas). `user_history` son los mensajes anteriores de la persona activa
    con su vector; `entity_replies`, los vectores de las últimas respuestas de
    la entidad, con cualquier persona, de la más vieja a la más reciente.
    """

    now: datetime
    text: str = ""
    query_vector: tuple[float, ...] | None = None
    appraisal: Appraisal | None = None
    partner_id: str | None = None
    theta_low_road: float = 1.0
    user_history: tuple[tuple[str, tuple[float, ...]], ...] = ()
    entity_replies: tuple[tuple[float, ...], ...] = ()
    drives_before: Mapping[str, float] = field(default_factory=dict)
    drives: Mapping[str, float] = field(default_factory=dict)
    commitments: tuple[OpenCommitment, ...] = ()
    w_commit: float = 1.0

    def __post_init__(self) -> None:
        """Copia los drives en vistas de solo lectura: `frozen` no impide cambiar el contenido de un dict."""
        object.__setattr__(self, "drives_before", MappingProxyType(dict(self.drives_before)))
        object.__setattr__(self, "drives", MappingProxyType(dict(self.drives)))


@dataclass(frozen=True)
class Signal:
    """
    Una señal de un micro-agente: quién la emite, de qué tipo, con qué
    intensidad, sobre qué (`target`) y con qué datos para el orquestador.
    """

    agent: str
    kind: str
    strength: float
    target: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        """Versión JSON para el evento `agent.signal`."""
        return {
            "agent": self.agent, "kind": self.kind, "strength": round(self.strength, 3),
            "target": self.target, "data": self.data,
        }
