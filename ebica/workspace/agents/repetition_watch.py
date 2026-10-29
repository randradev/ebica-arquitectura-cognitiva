"""
`repetition_watch` (§5.10; D1-72): la conversación que da vueltas.

Dos detecciones, con umbrales fijados con el sondeo de CP10 A (`bge-m3`):
- **La persona se repite** (`user_repeats`): el mensaje se parece ≥ 0,85 a uno
  anterior del mismo hilo. Las repeticiones medidas dieron 0,867–1,000; las
  preguntas distintas del mismo tema, como máximo 0,785. Solo con mensajes de 3
  palabras o más: un «Sí» repetido no es repetición. Efecto: la necesidad de
  novedad sube (aburrimiento) y una nota en la sección 7.
- **La entidad se repite** (`entity_repeats`): su última respuesta se parece
  ≥ 0,90 a alguna de sus 10 anteriores, con cualquier persona. La copia real
  de la sesión manual dio 0,94; las 356 respuestas normales, como máximo 0,873.
  Se detecta al empezar el turno siguiente; efecto: una nota en la sección 7.
"""

from ebica.memory.retrieval import cosine
from ebica.workspace.agents.base import Board, Signal

NAME = "repetition_watch"
# CONSTANTES: umbrales de coseno (sondeo de CP10 A, aprobados por el usuario).
USER_THRESHOLD = 0.85
ENTITY_THRESHOLD = 0.90
# CONSTANTE: palabras mínimas para que un mensaje cuente como repetición.
MIN_WORDS = 3
# CONSTANTE: respuestas anteriores de la entidad con que se compara la última.
ENTITY_WINDOW = 10
# CONSTANTE: cuánto sube el error del drive `novelty` cuando la persona se
# repite (D1-72, calibrable). Con w = 0,15 (D1-16), baja la valencia ~0,02.
NOVELTY_INCREASE = 0.15


def _long_enough(text: str) -> bool:
    """True si el mensaje tiene al menos `MIN_WORDS` palabras."""
    return len(text.split()) >= MIN_WORDS


def observe(board: Board) -> list[Signal]:
    """Señales de repetición de la persona y de la entidad, si corresponde."""
    signals = []
    if board.query_vector is not None and _long_enough(board.text):
        similar = [cosine(board.query_vector, vector) for text, vector in board.user_history if _long_enough(text)]
        best = max(similar, default=0.0)
        if best >= USER_THRESHOLD:
            signals.append(Signal(NAME, "user_repeats", best, target=board.partner_id,
                                  data={"novelty": NOVELTY_INCREASE}))
    if len(board.entity_replies) >= 2:
        last, previous = board.entity_replies[-1], board.entity_replies[-1 - ENTITY_WINDOW:-1]
        best = max(cosine(last, vector) for vector in previous)
        if best >= ENTITY_THRESHOLD:
            signals.append(Signal(NAME, "entity_repeats", best))
    return signals
