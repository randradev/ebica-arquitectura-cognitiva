"""
`hostility_watch` (§5.10; D1-70): la vía baja de CP5 expresada como micro-agente.

No reimplementa nada: envuelve `low_road.evaluate` (mismo léxico, mismas reglas,
mismo umbral θ_vb que depende de N). Si se dispara, emite una señal `alarm` con
el puntaje y las reglas; el orquestador sigue respondiendo por la ruta impulsiva.
"""

from ebica.affect.low_road import LowRoadResult
from ebica.affect.low_road import evaluate as evaluate_low_road
from ebica.workspace.agents.base import Board, Signal

NAME = "hostility_watch"


def evaluate(board: Board) -> LowRoadResult:
    """El resultado de la vía baja para el mensaje de la foto (el mismo de CP5)."""
    return evaluate_low_road(board.text, board.theta_low_road)


def signal_for(result: LowRoadResult) -> list[Signal]:
    """La señal `alarm` si la vía baja se disparó; nada si no."""
    if not result.triggered:
        return []
    return [Signal(NAME, "alarm", result.score, data=result.as_dict())]


def observe(board: Board) -> list[Signal]:
    """Corre la vía baja sobre el mensaje y devuelve la señal de alarma, si corresponde."""
    return signal_for(evaluate(board))
