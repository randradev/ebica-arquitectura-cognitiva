"""
Estado afectivo VAD y su dinámica (documento base §5.4).

El afecto son tres números: valencia (desagradable −1 ↔ agradable 1), alerta
(calma 0 ↔ activación 1) y dominancia (sin control 0 ↔ con control 1). Cada uno
vuelve solo hacia su punto de reposo (el atractor, que sale de los rasgos) con
una vida media: el tiempo que tarda en recorrer la mitad del camino de vuelta.

    x(t) = b + (x₀ − b) · ½^(t / h)        (equivale a e^(−t/τ) con τ = h / ln 2)

La forma cerrada es exacta para cualquier `dt`: un tick de 1 s y una ausencia
de una semana usan la misma función (D1-7) y no acumulan error.

Es una simulación computacional del ánimo, no una emoción sentida (CLAUDE.md §1).
"""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from ebica.identity.traits import BASE_NEGATIVE_HALF_LIFE_MINUTES, DerivedParameters

# CONSTANTES: vidas medias que §5.2 no define (D1-15; calibrables). La
# valencia negativa usa `h_neg`, que depende de N.
# Valencia positiva: igual a `h_neg` con N = 0, de modo que el malestar nunca
# dura menos que el bienestar (la asimetría que pide §5.4).
POSITIVE_VALENCE_HALF_LIFE_MINUTES = BASE_NEGATIVE_HALF_LIFE_MINUTES
# Alerta: la activación se disipa antes que el ánimo.
AROUSAL_HALF_LIFE_MINUTES = 10.0
# Dominancia: la sensación de control es más estable.
DOMINANCE_HALF_LIFE_MINUTES = 30.0


class VAD(BaseModel):
    """Un estado afectivo; inmutable: cada cambio produce un VAD nuevo."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    valence: float = Field(0.0, ge=-1.0, le=1.0)
    arousal: float = Field(0.0, ge=0.0, le=1.0)
    dominance: float = Field(0.0, ge=0.0, le=1.0)

    def max_difference(self, other: "VAD") -> float:
        """Mayor diferencia entre dimensiones; decide si vale la pena reportar un cambio."""
        return max(
            abs(self.valence - other.valence),
            abs(self.arousal - other.arousal),
            abs(self.dominance - other.dominance),
        )


@dataclass(frozen=True)
class AffectDynamics:
    """Los parámetros del afecto de una entidad: su reposo y sus vidas medias (en minutos)."""

    attractor: VAD
    negative_valence_half_life: float
    positive_valence_half_life: float = POSITIVE_VALENCE_HALF_LIFE_MINUTES
    arousal_half_life: float = AROUSAL_HALF_LIFE_MINUTES
    dominance_half_life: float = DOMINANCE_HALF_LIFE_MINUTES

    @classmethod
    def from_parameters(cls, parameters: DerivedParameters) -> "AffectDynamics":
        """Construye la dinámica desde los parámetros que derivan de los rasgos (§5.2)."""
        return cls(
            attractor=VAD(
                valence=parameters.b_valence,
                arousal=parameters.b_arousal,
                dominance=parameters.b_dominance,
            ),
            negative_valence_half_life=parameters.h_neg_minutes,
        )


def _clip(value: float, low: float, high: float) -> float:
    """Recorta un valor a su rango."""
    return max(low, min(high, value))


def relax(value: float, attractor: float, dt_seconds: float, half_life_minutes: float) -> float:
    """
    Acerca un valor a su atractor tras `dt_seconds` (forma cerrada).

    Nunca cruza el atractor: solo se aproxima.
    """
    remaining = 0.5 ** (dt_seconds / (half_life_minutes * 60.0))
    return attractor + (value - attractor) * remaining


def decay(state: VAD, dynamics: AffectDynamics, dt_seconds: float) -> VAD:
    """
    Aplica el regreso al reposo de las tres dimensiones durante `dt_seconds`.

    La vida media de la valencia depende de dónde está respecto del reposo:
    por debajo («peor que de costumbre») usa la negativa, que depende de N;
    por encima, la positiva. Como `relax` nunca cruza el atractor, el lado no
    cambia durante el intervalo y la forma cerrada sigue siendo exacta.
    """
    if dt_seconds <= 0:
        return state
    target = dynamics.attractor
    valence_half_life = (
        dynamics.negative_valence_half_life
        if state.valence < target.valence
        else dynamics.positive_valence_half_life
    )
    return VAD(
        valence=relax(state.valence, target.valence, dt_seconds, valence_half_life),
        arousal=relax(state.arousal, target.arousal, dt_seconds, dynamics.arousal_half_life),
        dominance=relax(state.dominance, target.dominance, dt_seconds, dynamics.dominance_half_life),
    )


# CONSTANTE: interruptor de la saturación suave (CP10b, D1-79). Con False, los
# impulsos de las vivencias vuelven a sumarse y recortarse como hasta CP10.
SOFT_SATURATION = True


def soften(value: float, delta: float, low: float, high: float) -> float:
    """
    El impulso `delta` amortiguado según cuánto se acercó ya `value` al extremo
    hacia el que empuja (D1-79): se multiplica por `1 − d²`, con `d` en [0, 1]
    la distancia recorrida desde el centro del rango hacia ese extremo.

    Ej. en la valencia: en 0, un impulso negativo vale el 100 %; en −0,5, el
    75 %; en −0,9, el 19 %. Un impulso en sentido contrario (que aleja del
    extremo) no se toca. Así un insulto más todavía se nota cerca del fondo,
    pero el estado no queda clavado en el tope.
    """
    if delta == 0:
        return 0.0
    center, half = (low + high) / 2, (high - low) / 2
    reached = max(0.0, (value - center) / half * (1 if delta > 0 else -1))
    return delta * (1.0 - min(1.0, reached) ** 2)


def apply_soft_impulse(
    state: VAD, valence: float = 0.0, arousal: float = 0.0, dominance: float = 0.0
) -> VAD:
    """
    Suma el impulso de una vivencia (appraisal, alarma de la vía baja) con
    saturación suave en cada dimensión (D1-79), y después recorta al rango.

    La inyección manual (D1-18) y el acople de los drives usan `apply_impulse`
    sin amortiguar: la primera es una herramienta de laboratorio que debe
    llevar el ánimo exactamente adonde se pide; el segundo mueve cantidades mínimas.
    """
    if not SOFT_SATURATION:
        return apply_impulse(state, valence, arousal, dominance)
    return apply_impulse(
        state,
        soften(state.valence, valence, -1.0, 1.0),
        soften(state.arousal, arousal, 0.0, 1.0),
        soften(state.dominance, dominance, 0.0, 1.0),
    )


def apply_impulse(
    state: VAD, valence: float = 0.0, arousal: float = 0.0, dominance: float = 0.0
) -> VAD:
    """Suma un impulso al estado y recorta cada dimensión a su rango."""
    return VAD(
        valence=_clip(state.valence + valence, -1.0, 1.0),
        arousal=_clip(state.arousal + arousal, 0.0, 1.0),
        dominance=_clip(state.dominance + dominance, 0.0, 1.0),
    )
