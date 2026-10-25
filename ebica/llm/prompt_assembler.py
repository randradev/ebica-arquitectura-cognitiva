"""
Prompt Assembler (documento base §5.13).

Secciones de Fase 1 hasta CP5:
1. «Quién soy»: la voz y el ideal del yo (CP3).
2. «Cómo me siento ahora»: el VAD y los drives traducidos a palabras (CP5).
8. La conversación reciente, como mensajes alternados (CP5, D1-24).
Los recuerdos (4–5), el PartnerModel (6) y «Cómo expresarme» (7) llegan en CP7–CP9.

El orden importa: lo estable (sección 1) va primero y el estado al final del
prompt de sistema, para que la caché de prefijo de Ollama reutilice el inicio.

Los rasgos no generan texto (D1-13): actúan a través de la dinámica. Lo que va
en palabras es el *estado* que esa dinámica produjo. Así, dos variantes que
solo difieren en N reciben el mismo prompt mientras su ánimo sea el mismo.
"""

from ebica.affect.drives import DRIVE_THRESHOLD
from ebica.affect.vad import VAD
from ebica.core.state import ConversationTurn, EntityConfig

# Encabezado de las normas del ideal del yo en el prompt.
EGO_IDEAL_HEADER = "Mis normas, lo que intento sostener:"
# Encabezado de la sección 2.
FEELINGS_HEADER = "Cómo me siento ahora:"

# CONSTANTES: bandas de la valencia (límite superior, palabras). Se describen
# con sustantivos ("ánimo bastante bajo") para no imponer género gramatical.
VALENCE_WORDS = (
    (-0.6, "el ánimo por el suelo"),
    (-0.3, "el ánimo bastante bajo"),
    (-0.1, "el ánimo algo bajo"),
    (0.1, "el ánimo tranquilo, ni bien ni mal"),
    (0.3, "buen ánimo"),
    (0.6, "muy buen ánimo"),
    (1.01, "el ánimo por las nubes"),
)
# CONSTANTES: bandas de la alerta. La banda media no se menciona.
LOW_AROUSAL, HIGH_AROUSAL, VERY_HIGH_AROUSAL = 0.3, 0.6, 0.8
# CONSTANTES: bandas de la dominancia. La banda media no se menciona.
LOW_DOMINANCE, HIGH_DOMINANCE = 0.25, 0.7
# Palabras para cada drive que pasa el umbral.
DRIVE_WORDS = {
    "social": "ganas de conversar con alguien",
    "novelty": "ganas de algo nuevo, porque lo de siempre me aburre",
    "rest": "cansancio",
}


def build_who_am_i(config: EntityConfig) -> str:
    """
    Sección «Quién soy» de una entidad con identidad de Fase 1.

    Lleva el nombre, la voz (`persona`) y las normas del ideal del yo. La
    descripción solo entra si no hay voz: lo biográfico vive en la memoria
    (los hechos de la semilla) y se recupera cuando es relevante, en vez de
    ocupar el presupuesto de tokens en cada turno.
    """
    parts = [f"Eres {config.name}."]
    if config.persona:
        parts.append(config.persona.strip())
    elif config.description:
        parts.append(config.description.strip())
    if config.ego_ideal:
        norms = "\n".join(f"- {norm}" for norm in config.ego_ideal)
        parts.append(f"{EGO_IDEAL_HEADER}\n{norms}")
    return "\n\n".join(parts)


def build_system_prompt(config: EntityConfig) -> str:
    """
    Describe quién es la entidad.

    Las entidades de Fase 0, sin ideal del yo ni biografía semilla, conservan
    su prompt de siempre (nombre, descripción y persona en una línea).
    """
    if config.ego_ideal or not config.seed_biography.is_empty:
        return build_who_am_i(config)
    parts = [f"Eres {config.name}."]
    if config.description:
        parts.append(config.description)
    if config.persona:
        parts.append(config.persona)
    return " ".join(parts)


def describe_feelings(affect: VAD, drives: dict[str, float]) -> str:
    """
    Sección 2: el estado afectivo y los drives en palabras, sin números.

    Ej.: «Ahora mismo tengo el ánimo bastante bajo, mucha agitación y poca
    sensación de control. También siento cansancio.» El LLM no recibe el VAD
    crudo: recibe cómo se vive ese estado, como una persona no sabe su nivel
    de cortisol pero sabe que está tensa.
    """
    parts = [next(words for limit, words in VALENCE_WORDS if affect.valence < limit)]
    if affect.arousal >= VERY_HIGH_AROUSAL:
        parts.append("mucha agitación")
    elif affect.arousal >= HIGH_AROUSAL:
        parts.append("algo de agitación")
    elif affect.arousal < LOW_AROUSAL:
        parts.append("poca energía")
    if affect.dominance < LOW_DOMINANCE:
        parts.append("poca sensación de control")
    elif affect.dominance >= HIGH_DOMINANCE:
        parts.append("la sensación de tener las cosas bajo control")
    feelings = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " y " + parts[-1]
    text = f"Ahora mismo tengo {feelings}."
    needs = [DRIVE_WORDS[name] for name in DRIVE_WORDS if drives.get(name, 0.0) >= DRIVE_THRESHOLD]
    if needs:
        text += " También siento " + " y ".join(needs) + "."
    text += " No lo explico salvo que venga al caso: se nota en cómo respondo."
    return text


def build_dialogue_messages(
    config: EntityConfig,
    user_text: str,
    affect: VAD | None = None,
    drives: dict[str, float] | None = None,
    recent_turns: list[ConversationTurn] | tuple = (),
) -> list[dict[str, str]]:
    """
    Arma los mensajes para el preset `dialogue`.

    Sistema (identidad y, si hay afecto, cómo se siente) → los intercambios
    recientes como pares user/assistant → el mensaje actual. Sin afecto ni
    historial produce el prompt de Fase 0.
    """
    system = build_system_prompt(config)
    if affect is not None:
        system += f"\n\n{FEELINGS_HEADER}\n{describe_feelings(affect, drives or {})}"
    messages = [{"role": "system", "content": system}]
    for turn in recent_turns:
        messages.append({"role": "user", "content": turn.user})
        messages.append({"role": "assistant", "content": turn.entity})
    messages.append({"role": "user", "content": user_text})
    return messages
