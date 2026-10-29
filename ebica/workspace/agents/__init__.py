"""
Micro-agentes de Fase 1 (documento base §5.10; CP10).

Cada uno es una función pura que mira una foto de la pizarra (`Board`) y
devuelve señales (`Signal`); nunca escribe nada. El orquestador aplica los
efectos. `run_agents` los ejecuta en orden fijo.
"""

from ebica.workspace.agents import (
    commitment_watch,
    distress_watch,
    homeostasis_watch,
    hostility_watch,
    repetition_watch,
)
from ebica.workspace.agents.base import Board, OpenCommitment, Signal

# Orden fijo de ejecución, para que los eventos salgan siempre igual. La vía
# baja (`hostility_watch`) corre antes del appraisal y por eso no está aquí.
TURN_AGENTS = (distress_watch, commitment_watch, repetition_watch)


def run_agents(board: Board) -> list[Signal]:
    """Ejecuta los micro-agentes del turno sobre la foto y junta sus señales."""
    return [signal for agent in TURN_AGENTS for signal in agent.observe(board)]


__all__ = [
    "Board", "OpenCommitment", "Signal", "TURN_AGENTS", "run_agents",
    "commitment_watch", "distress_watch", "homeostasis_watch", "hostility_watch", "repetition_watch",
]
