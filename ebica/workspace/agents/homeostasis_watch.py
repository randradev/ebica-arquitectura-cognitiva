"""
`homeostasis_watch` (§5.10; D1-75): un drive que cruza su umbral presiona.

Emite `pressure` cuando un drive sube y cruza el umbral (`DRIVE_THRESHOLD`,
0,7 por D1-16). En Fase 1 es solo la señal: quienes la consumen (la rumia y la
iniciativa) llegan en Fase 2.
"""

from ebica.affect.drives import DRIVE_THRESHOLD
from ebica.workspace.agents.base import Board, Signal

NAME = "homeostasis_watch"


def observe(board: Board) -> list[Signal]:
    """Una señal `pressure` por cada drive que pasó de bajo el umbral a sobre él."""
    return [
        Signal(NAME, "pressure", level, target=name)
        for name, level in board.drives.items()
        if level >= DRIVE_THRESHOLD > board.drives_before.get(name, 0.0)
    ]
