"""
Temperamento (CB5T) y su traducción a parámetros de la dinámica (documento base §5.2).

En CB5T un rasgo no es una autodescripción, sino un parámetro de mecanismos:
el neuroticismo, por ejemplo, es la sensibilidad a la amenaza. Por eso aquí
los rasgos no generan texto para el prompt (D1-13): se convierten en números
que usan el afecto (CP4), la vía baja (CP5), la recuperación (CP7) y, más
adelante, la rumia y la iniciativa (Fase 2) y las defensas (Fase 3).

Los rasgos de `config.yaml` son el origen `t0`. En vigilia son de solo
lectura; la deriva durante el sueño (Fase 2) vivirá en el estado.

Todas las fórmulas son los valores iniciales de §5.2, "a calibrar": están
juntas en `derive_parameters` para poder revisarlas y medirlas en un lugar.
"""

import math
from dataclasses import asdict, dataclass

from pydantic import BaseModel, ConfigDict, Field

# CONSTANTE: valor neutro de un rasgo. Las entidades sin rasgos (p. ej. las de
# Fase 0) cargan con él, de modo que su dinámica queda en el punto medio.
NEUTRAL_TRAIT = 0.5

# CONSTANTE: vida media base de la valencia negativa, en minutos (§5.2).
# N la alarga hasta 2,5 veces: h_neg = 20 min · (1 + 1,5·N).
BASE_NEGATIVE_HALF_LIFE_MINUTES = 20.0


class Traits(BaseModel):
    """
    Los cinco rasgos CB5T, cada uno en [0, 1].

    Se escriben con su letra, como en el documento base: O (apertura),
    C (responsabilidad), E (extraversión), A (amabilidad) y N (neuroticismo).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    O: float = Field(NEUTRAL_TRAIT, ge=0.0, le=1.0)
    C: float = Field(NEUTRAL_TRAIT, ge=0.0, le=1.0)
    E: float = Field(NEUTRAL_TRAIT, ge=0.0, le=1.0)
    A: float = Field(NEUTRAL_TRAIT, ge=0.0, le=1.0)
    N: float = Field(NEUTRAL_TRAIT, ge=0.0, le=1.0)

    @property
    def stability(self) -> float:
        """Meta-rasgo Estabilidad = media(C, A, 1 − N): mantener el rumbo pese a las perturbaciones."""
        return (self.C + self.A + (1.0 - self.N)) / 3.0

    @property
    def plasticity(self) -> float:
        """Meta-rasgo Plasticidad = media(E, O): disposición a explorar lo nuevo."""
        return (self.E + self.O) / 2.0


@dataclass(frozen=True)
class DerivedParameters:
    """
    Parámetros de la dinámica calculados desde los rasgos (tabla de §5.2).

    El comentario de cada grupo indica qué checkpoint o fase los consume.
    Existen todos desde ya para que `identity.loaded` muestre el cuadro
    completo de la personalidad, aunque algunos aún no tengan efecto.
    """

    # --- Afecto (CP4) y vía baja (CP5): N y E.
    h_neg_minutes: float      # vida media de la valencia negativa
    g_neg: float              # ganancia ante appraisals negativos
    g_pos: float              # ganancia ante recompensa social
    theta_low_road: float     # umbral de la vía baja (θ_vb)
    # Atractor basal: el VAD de reposo hacia el que decae el ánimo.
    b_valence: float
    b_arousal: float
    b_dominance: float
    # --- Drives (CP4): multiplicador de la tasa base de `social` (r0 vive en los drives).
    r_soc_factor: float
    # --- Lazo "como si" y conflicto (CP5): A.
    pi_empathy: float         # permeabilidad empática (π)
    theta_disagree: float     # umbral para discrepar
    c_conflict: float         # costo percibido del conflicto
    # --- Recuperación (CP7) y compromisos (CP10): O y C.
    k_retrieval: int          # cuántos recuerdos entran como máximo
    lambda_mmr: float         # peso de la relevancia frente a la diversidad en MMR
    w_commit: float           # peso de los compromisos pendientes
    # --- Fase 2 (rumia, iniciativa, divagación): existen, sin efecto todavía.
    p_rum_neg: float          # probabilidad de semilla negativa en la rumia
    theta_init: float         # umbral de iniciativa
    p_wander: float           # probabilidad de divagación
    p_stay_topic: float       # persistencia de tema
    # --- Fase 3 (defensas).
    theta_defense: float      # umbral de activación de defensas

    def as_dict(self) -> dict[str, float | int]:
        """Devuelve los parámetros como diccionario, para eventos y la consola."""
        return asdict(self)


def _round_half_up(value: float) -> int:
    """
    Redondea .5 hacia arriba.

    `round()` de Python redondea al par más cercano (round(2.5) == 2), lo que
    haría saltos irregulares en `k` al variar O.
    """
    return math.floor(value + 0.5)


def derive_parameters(traits: Traits) -> DerivedParameters:
    """Calcula los parámetros de la dinámica con las fórmulas iniciales de §5.2."""
    o, c, e, a, n = traits.O, traits.C, traits.E, traits.A, traits.N
    return DerivedParameters(
        h_neg_minutes=BASE_NEGATIVE_HALF_LIFE_MINUTES * (1.0 + 1.5 * n),
        g_neg=1.0 + n,
        g_pos=1.0 + 0.5 * e,
        theta_low_road=0.8 - 0.3 * n,
        b_valence=0.1 - 0.3 * n + 0.1 * e,
        b_arousal=0.3 + 0.2 * e,
        b_dominance=0.4 + 0.2 * e - 0.2 * n,
        r_soc_factor=0.5 + e,
        pi_empathy=0.2 + 0.6 * a,
        theta_disagree=0.3 + 0.5 * a,
        c_conflict=0.5 + a,
        k_retrieval=4 + _round_half_up(4.0 * o),
        lambda_mmr=0.7 - 0.4 * o,
        w_commit=0.5 + c,
        p_rum_neg=0.2 + 0.5 * n,
        theta_init=0.8 - 0.3 * e,
        p_wander=0.2 + 0.4 * o,
        p_stay_topic=0.4 + 0.4 * c,
        theta_defense=0.4 + 0.4 * traits.stability,
    )
