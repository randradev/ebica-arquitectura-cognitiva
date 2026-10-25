"""
Del appraisal a la dinámica: impulsos afectivos, satisfacción de drives y modulación (§6.2, §5.4).

Son funciones puras (sin estado ni eventos): el orquestador las aplica y
reporta. Así cada fórmula se prueba con números calculados a mano.

Ejemplo (Calisto, N 0.75 → g_neg 1,75): «eres una inútil» llega con
goal_congruence −0,8 → Δvalencia = 0,3 · 1,75 · (−0,8) = −0,42. Con N 0.25
(g_neg 1,25) serían −0,30: el mismo mensaje golpea distinto según el carácter.

Todas las magnitudes son las de D1-23 / D1-25, calibrables.
"""

from dataclasses import dataclass

from ebica.affect.vad import VAD
from ebica.identity.traits import DerivedParameters
from ebica.perception.appraisal import Appraisal

# CONSTANTE: escala de los impulsos de valencia por appraisal (D1-23). Sin
# ella, g_neg · goal_congruence llevaría la valencia a −1 con un solo insulto.
APPRAISAL_VALENCE_SCALE = 0.3
# CONSTANTE: escala del lazo «como si»: Δv = 0,5 · π · (valencia ajena − propia).
EMPATHY_SCALE = 0.5
# CONSTANTES: impulsos de alerta y dominancia (D1-23). Un ataque activa y
# quita sensación de control; la angustia ajena también activa.
AROUSAL_PER_HOSTILITY = 0.25
AROUSAL_PER_DISTRESS = 0.15
DOMINANCE_PER_HOSTILITY = -0.2
# CONSTANTES: satisfacción de drives por turno (D1-23). El contacto satisface
# `social` salvo que sea hostil, y más si es cálido; lo nuevo satisface `novelty`.
SOCIAL_CONTACT_RELIEF = 0.15
NOVELTY_RELIEF = 0.3
# CONSTANTE: hostilidad desde la que se aplica la regla del sarcasmo (D1-20):
# la banda «alto» del benchmark (D1-1).
SARCASM_HOSTILITY = 0.66
# CONSTANTE: valor corregido = este factor · hostilidad (hostilidad 0,9 → −0,45):
# la burla hiere, pero menos que un insulto con goal_congruence −0,8.
SARCASM_CORRECTION = -0.5

# CONSTANTES: temperatura del diálogo según el ánimo (D1-25, §5.4).
BASE_TEMPERATURE = 0.7
TEMPERATURE_PER_VALENCE = 0.1
TEMPERATURE_PER_EXCESS_AROUSAL = -0.15
AROUSAL_TEMPERATURE_KNEE = 0.6
MIN_TEMPERATURE = 0.5
MAX_TEMPERATURE = 0.85


@dataclass(frozen=True)
class AffectImpulse:
    """Impulso al VAD con su desglose, para mostrar en la consola de dónde salió cada parte."""

    valence: float
    arousal: float
    dominance: float
    # Partes de la valencia: por lo que el mensaje significa para la entidad
    # (goal_congruence) y por contagio del ánimo ajeno (lazo «como si»).
    valence_from_goals: float
    valence_from_empathy: float

    def as_dict(self) -> dict[str, float]:
        """Representación para los eventos."""
        return {
            "valence": self.valence,
            "arousal": self.arousal,
            "dominance": self.dominance,
            "valence_from_goals": self.valence_from_goals,
            "valence_from_empathy": self.valence_from_empathy,
        }


def apply_coherence_rules(appraisal: Appraisal) -> tuple[Appraisal, list[str]]:
    """
    Corrige incoherencias conocidas del appraisal y devuelve las correcciones hechas.

    Sarcasmo (D1-20): con hostilidad alta, la valencia de quien habla y la
    congruencia con las metas no pueden ser positivas. El benchmark mostró que
    el modelo detecta la burla («¡qué respuesta tan brillante!») pero puntúa
    la valencia literal (+0,9). Un valor positivo se reemplaza por
    −0,5 · hostilidad: si se dejara en 0, una burla no bajaría el ánimo.
    """
    corrections = []
    if appraisal.hostility < SARCASM_HOSTILITY:
        return appraisal, corrections
    corrected = SARCASM_CORRECTION * appraisal.hostility
    emotion = appraisal.user_emotion
    updates: dict = {}
    if emotion.valence > 0:
        updates["user_emotion"] = emotion.model_copy(update={"valence": corrected})
        corrections.append(f"sarcasmo: valencia del usuario {emotion.valence:+.2f} → {corrected:+.2f}")
    if appraisal.goal_congruence > 0:
        updates["goal_congruence"] = corrected
        corrections.append(f"sarcasmo: goal_congruence {appraisal.goal_congruence:+.2f} → {corrected:+.2f}")
    return appraisal.model_copy(update=updates), corrections


def affect_impulse(appraisal: Appraisal, current: VAD, parameters: DerivedParameters) -> AffectImpulse:
    """
    Impulso afectivo de un mensaje (§6.2, etapa 3; D1-23).

    - Valencia: 0,3 · g · goal_congruence, con g = g_neg si el mensaje va en
      contra y g_pos si va a favor (N y E deciden cuánto pesa cada lado), más
      el lazo «como si»: 0,5 · π · (valencia ajena − propia), con π por A.
    - Alerta: sube con la hostilidad y con la angustia ajena.
    - Dominancia: baja con la hostilidad.
    """
    congruence = appraisal.goal_congruence
    gain = parameters.g_neg if congruence < 0 else parameters.g_pos
    from_goals = APPRAISAL_VALENCE_SCALE * gain * congruence
    from_empathy = (
        EMPATHY_SCALE * parameters.pi_empathy * (appraisal.user_emotion.valence - current.valence)
    )
    return AffectImpulse(
        valence=from_goals + from_empathy,
        arousal=AROUSAL_PER_HOSTILITY * appraisal.hostility + AROUSAL_PER_DISTRESS * appraisal.distress,
        dominance=DOMINANCE_PER_HOSTILITY * appraisal.hostility,
        valence_from_goals=from_goals,
        valence_from_empathy=from_empathy,
    )


def drive_relief(appraisal: Appraisal) -> dict[str, float]:
    """
    Cuánto baja cada drive con este mensaje (valores ≥ 0; §6.2, D1-23).

    `social`: el contacto alivia, salvo que sea hostil; la calidez (valencia
    positiva de quien habla) lo duplica como máximo. `novelty`: según lo nuevo
    que aporte. `rest` no cambia con la conversación en Fase 1.
    """
    warmth = max(0.0, appraisal.user_emotion.valence)
    return {
        "social": SOCIAL_CONTACT_RELIEF * (1.0 - appraisal.hostility) * (1.0 + warmth),
        "novelty": NOVELTY_RELIEF * appraisal.novelty,
        "rest": 0.0,
    }


def dialogue_temperature(affect: VAD) -> float:
    """
    Temperatura de la respuesta según el ánimo (D1-25, §5.4).

    Un ánimo positivo la sube un poco (más asociaciones); la alerta alta la
    baja (respuestas más contenidas cuando hay tensión).
    """
    excess_arousal = max(0.0, affect.arousal - AROUSAL_TEMPERATURE_KNEE)
    value = (
        BASE_TEMPERATURE
        + TEMPERATURE_PER_VALENCE * affect.valence
        + TEMPERATURE_PER_EXCESS_AROUSAL * excess_arousal
    )
    return max(MIN_TEMPERATURE, min(MAX_TEMPERATURE, value))
