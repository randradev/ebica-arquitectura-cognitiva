"""
`distress_watch` (§5.10, §6.3; D1-71): la angustia de quien habla atrae la atención.

Si el appraisal marca angustia ≥ 0,6, emite `attend_partner`: el orquestador
multiplica por `ATTENTION_FACTOR` la saliencia, en la pizarra, de los recuerdos
con esa persona (el factor `señal` de §5.6). No obliga a la entidad a consolar
(§6.3: «nada de esto está forzado»); solo hace que lo de esa persona ocupe más
la atención. El contagio emocional ya lo hace el lazo «como si» (π).
"""

from ebica.workspace.agents.base import Board, Signal

NAME = "distress_watch"
# CONSTANTE: angustia ajena desde la que se dispara (la misma que la sección 6
# usa para decir «con angustia» y el PartnerModel para los temas sensibles).
DISTRESS_THRESHOLD = 0.6
# CONSTANTE: factor de saliencia para los recuerdos con la persona que sufre
# (D1-71, calibrable).
ATTENTION_FACTOR = 1.5


def observe(board: Board) -> list[Signal]:
    """`attend_partner` si la persona que habla muestra angustia alta; nada si no."""
    if board.appraisal is None or board.appraisal.distress < DISTRESS_THRESHOLD:
        return []
    return [Signal(NAME, "attend_partner", board.appraisal.distress, target=board.partner_id,
                   data={"factor": ATTENTION_FACTOR})]
