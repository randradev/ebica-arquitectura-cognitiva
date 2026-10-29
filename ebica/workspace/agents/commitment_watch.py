"""
`commitment_watch` (§5.10; D1-74): las promesas de quien habla, presentes.

Por cada compromiso abierto de la persona activa calcula su intensidad:

    intensidad = w_commit · 0,5^(edad / 7 días)

(w_commit = 0,5 + C, §5.2: alguien responsable tiene más presente lo
prometido). Si supera `MIN_STRENGTH`, emite `commitment`; el orquestador lo pone
en la pizarra y, si entra, va a la sección 6. Una promesa vieja se desvanece sin
cerrarse: el cierre es del sueño (Fase 2).
"""

from ebica.workspace.agents.base import Board, Signal

NAME = "commitment_watch"
# CONSTANTE: vida media de la intensidad de un compromiso (D1-74, calibrable).
HALF_LIFE_DAYS = 7.0
# CONSTANTE: intensidad mínima para estar presente (D1-74).
MIN_STRENGTH = 0.2


def strength(age_days: float, w_commit: float) -> float:
    """Intensidad de un compromiso con `age_days` días de antigüedad."""
    return w_commit * 0.5 ** (max(0.0, age_days) / HALF_LIFE_DAYS)


def observe(board: Board) -> list[Signal]:
    """Una señal `commitment` por cada compromiso abierto que todavía tiene fuerza, del más intenso al menos."""
    signals = []
    for commitment in board.commitments:
        age_days = (board.now - commitment.ts).total_seconds() / 86400
        value = strength(age_days, board.w_commit)
        if value >= MIN_STRENGTH:
            signals.append(Signal(NAME, "commitment", value, target=commitment.id,
                                  data={"text": commitment.text, "ts": commitment.ts.isoformat()}))
    return sorted(signals, key=lambda signal: signal.strength, reverse=True)
