"""
WorkingMemory, la pizarra (documento base §5.6; Fase 1, CP9).

Lo que no está en la pizarra no existe para el LLM. Tiene capacidad acotada: un
presupuesto de tokens para el contexto variable, que la alerta alta reduce
(§5.4: bajo amenaza, la atención se estrecha). Cada ítem compite por entrar
según su saliencia:

    saliencia = relevancia · (1 + |valencia|·g_afectivo) · señal · precisión

Lo cargado afectivamente gana a lo neutro con la misma relevancia (Baars: gana
la coalición más saliente; Damasio: el afecto marca lo importante). La señal de
los micro-agentes llega en CP10 y la precisión de las defensas en Fase 3; hasta
entonces valen 1.

Qué compite (D1-61): los intercambios de la conversación reciente salvo el
último, los recuerdos y los hechos. Lo fijo (quién soy, el estado, la persona,
cómo expresarme, el mensaje y el último intercambio) no es un ítem: siempre va,
fuera del presupuesto. Este módulo solo decide qué entra; cómo se dice es tarea
del Prompt Assembler.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from ebica.llm.tokens import estimate_tokens

# CONSTANTE: presupuesto de tokens del contexto variable (§5.6, D1-62).
BASE_BUDGET_TOKENS = 2500
# CONSTANTES: reducción por la alerta (D1-62, calibrable). Desde una alerta de
# 0,6, el presupuesto baja linealmente hasta la mitad con la alerta en 1,0
# (2.500 → 1.250). Medido en CP9: en calma el contexto variable ronda 1.550
# tokens, así que solo bajo amenaza hay desalojo.
AROUSAL_REDUCTION_START = 0.6
AROUSAL_REDUCTION_MAX = 0.5
# CONSTANTE: peso de la carga afectiva en la saliencia (§5.6, D1-63). La tabla
# de §5.2 no lo define; queda como constante calibrable en vez de inventar una
# relación con un rasgo.
G_AFFECTIVE = 1.0
# CONSTANTE: relevancia de un intercambio según su antigüedad (D1-63): el
# penúltimo vale 0,9, el anterior 0,81… Bajo presión se van primero los más viejos.
TURN_RELEVANCE_DECAY = 0.9

ItemKind = Literal["turn", "memory", "fact"]


def workspace_budget(arousal: float, base: int = BASE_BUDGET_TOKENS) -> int:
    """
    Presupuesto de tokens del contexto variable según la alerta (§5.6, D1-62).

    Ej.: alerta 0,5 → 2.500; 0,8 → 1.875; 1,0 → 1.250.
    """
    excess = (arousal - AROUSAL_REDUCTION_START) / (1.0 - AROUSAL_REDUCTION_START)
    reduction = AROUSAL_REDUCTION_MAX * min(1.0, max(0.0, excess))
    return round(base * (1.0 - reduction))


def turn_relevance(age: int) -> float:
    """Relevancia de un intercambio con `age` turnos de antigüedad (1 = el penúltimo)."""
    return TURN_RELEVANCE_DECAY ** age


@dataclass
class WorkspaceItem:
    """
    Algo que compite por entrar a la pizarra.

    `order` es su posición natural dentro de su tipo (los recuerdos según MMR,
    los intercambios por fecha): lo que entra conserva ese orden en el prompt,
    aunque haya entrado por saliencia. `source` es el objeto original (un
    `ScoredEpisode`, un `RetrievedFact` o un `ConversationTurn`) para que el
    Prompt Assembler lo diga como corresponda.
    """

    kind: ItemKind
    key: str
    text: str
    relevance: float
    valence: float = 0.0
    order: int = 0
    signal: float = 1.0
    precision: float = 1.0
    source: Any = field(default=None, repr=False)

    @property
    def tokens(self) -> int:
        """Tokens estimados del texto (D1-10)."""
        return estimate_tokens(self.text)

    @property
    def salience(self) -> float:
        """Saliencia de §5.6: relevancia potenciada por la carga afectiva, la señal y la precisión."""
        return self.relevance * (1.0 + abs(self.valence) * G_AFFECTIVE) * self.signal * self.precision

    def as_dict(self) -> dict:
        """Versión JSON para `wm.updated` y `wm.evicted` (sin el texto)."""
        return {
            "kind": self.kind, "key": self.key, "tokens": self.tokens,
            "relevance": round(self.relevance, 3), "valence": round(self.valence, 3),
            "salience": round(self.salience, 3),
        }


@dataclass
class Selection:
    """Lo que entró a la pizarra y lo que se desalojó, con el presupuesto y lo usado."""

    kept: list[WorkspaceItem]
    evicted: list[WorkspaceItem]
    budget: int
    used: int

    def of_kind(self, kind: ItemKind) -> list[WorkspaceItem]:
        """Lo que entró de un tipo, en su orden natural."""
        return [item for item in self.kept if item.kind == kind]

    def as_dict(self) -> dict:
        """Versión JSON para el evento `wm.updated`."""
        return {
            "budget": self.budget, "used": self.used,
            "kept": [item.as_dict() for item in self.kept],
            "evicted": [item.as_dict() for item in self.evicted],
        }


def select(items: list[WorkspaceItem], budget: int) -> Selection:
    """
    Elige qué entra a la pizarra (§5.6): lo más saliente primero, mientras quepa.

    Recorre los ítems de mayor a menor saliencia y agrega cada uno si todavía
    cabe; uno que no cabe se desaloja y se sigue con los demás, porque uno
    menos saliente pero más corto puede caber igual. A igual saliencia decide
    el orden natural. Devuelve lo que entró en su orden natural (por tipo y
    `order`) y lo desalojado de mayor a menor saliencia.
    """
    ranked = sorted(enumerate(items), key=lambda pair: (-pair[1].salience, pair[1].order, pair[0]))
    kept_positions: list[int] = []
    evicted: list[WorkspaceItem] = []
    used = 0
    for position, item in ranked:
        if used + item.tokens <= budget:
            kept_positions.append(position)
            used += item.tokens
        else:
            evicted.append(item)
    kept = [items[position] for position in sorted(kept_positions, key=lambda p: (items[p].kind, items[p].order, p))]
    return Selection(kept=kept, evicted=evicted, budget=budget, used=used)
