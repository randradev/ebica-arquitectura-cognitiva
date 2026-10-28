"""
Prompt Assembler (documento base §5.13).

Secciones de Fase 1 hasta CP5:
1. «Quién soy»: la voz, la biografía esencial (CP6, D1-34) y el ideal del yo (CP3).
2. «Cómo me siento ahora»: el VAD y los drives traducidos a palabras (CP5).
4. «Lo que me viene a la mente»: los episodios recuperados, con su tiempo y su
   tono en palabras (CP7, D1-50).
5. «Lo que sé»: los hechos recuperados (CP7, D1-45).
6. «Cómo veo a esta persona»: el PartnerModel de quien habla, en palabras (CP8).
8. La conversación reciente, como mensajes alternados (CP5, D1-24).
«Cómo expresarme» (7) llega en CP9.
La respuesta impulsiva de la vía baja (CP5 B2) usa una versión mínima: 1, 2,
el nombre de quien habla y el último intercambio.

El orden importa: lo estable (sección 1) va primero y el estado al final del
prompt de sistema, para que la caché de prefijo de Ollama reutilice el inicio.

Los rasgos no generan texto (D1-13): actúan a través de la dinámica. Lo que va
en palabras es el *estado* que esa dinámica produjo. Así, dos variantes que
solo difieren en N reciben el mismo prompt mientras su ánimo sea el mismo.
"""

from datetime import datetime

from ebica.affect.drives import DRIVE_THRESHOLD
from ebica.affect.vad import VAD
from ebica.core.state import ConversationTurn, EntityConfig
from ebica.memory.retrieval import RetrievalResult, ScoredEpisode
from ebica.social.partner import PartnerModel, PartnerNow

# Encabezado de la biografía esencial (hechos con `core: true`, D1-34).
CORE_BIOGRAPHY_HEADER = "Lo esencial de mi historia:"
# Encabezado de las normas del ideal del yo en el prompt.
EGO_IDEAL_HEADER = "Mis normas, lo que intento sostener:"
# Encabezado de la sección 2.
FEELINGS_HEADER = "Cómo me siento ahora:"
# Instrucción de la respuesta impulsiva (D1-31): reacción inmediata y breve,
# sin restricciones de contenido. No dice cómo interpretar el mensaje (la
# vía baja puede equivocarse, p. ej. «te voy a matar a abrazos»): la
# agitación ya va en «Cómo me siento ahora».
IMPULSIVE_INSTRUCTION = "Reaccionas en el impulso, sin pensarlo: una o dos frases, como te salga."
# CONSTANTE: intercambios recientes en el prompt impulsivo (D1-31: contexto mínimo).
IMPULSIVE_RECENT_TURNS = 1

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
# Encabezados de las secciones 4 y 5 (CP7). La segunda línea de la sección 4
# es parte de la decisión sobre los falsos positivos (CP7 B, opción a): un
# recuerdo puede llegar sin venir al caso («Gracias» → «Soy Piscis.»).
# La segunda frase es la capa (3) contra la confusión de la fuente (D1-57):
# un recuerdo de lo que alguien me contó es experiencia de esa persona.
MEMORIES_HEADER = "Lo que me viene a la mente:"
MEMORIES_NOTE = (
    "(Me vienen solos; si no vienen al caso, no los menciono. "
    "Lo que otros me contaron les pasó a ellos, no a mí.)"
)
FACTS_HEADER = "Lo que sé:"
# CONSTANTE: largo máximo de un recuerdo de diálogo en el prompt (D1-50). Los
# de la semilla van completos: están escritos a mano y son parte de su historia.
DIALOGUE_MEMORY_MAX_CHARS = 450
# CONSTANTE: tope provisional de tokens de las secciones 4 y 5 juntas (D1-50),
# hasta que la WorkingMemory de CP9 administre el presupuesto completo.
MEMORY_SECTIONS_MAX_TOKENS = 1200
# CONSTANTE: estimación de tokens por palabra (D1-10), calibrada con Ollama:
# en CP3 y CP6 quedó por encima del valor real (conservadora).
TOKENS_PER_WORD = 1.6
# CONSTANTES: tono de un recuerdo según la valencia con que se guardó
# (límite superior, palabras). Cerca de 0 no se dice nada.
MEMORY_TONE = (
    (-0.5, "lo recuerdo con dolor"),
    (-0.15, "lo recuerdo con incomodidad"),
    (0.15, ""),
    (0.5, "lo recuerdo con gusto"),
    (1.01, "lo recuerdo con mucha alegría"),
)
MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "octubre", "noviembre", "diciembre",
)
# Encabezado de la sección 6 (CP8).
PARTNER_HEADER = "Cómo veo a esta persona:"
# CONSTANTES: cuánto conoce a la persona, por número de intercambios
# (límite superior, palabras). Se cuentan turnos, no conversaciones.
ACQUAINTANCE_WORDS = ((5, "hemos hablado poco"), (30, "hemos hablado varias veces"), (10**9, "hemos hablado mucho"))
# CONSTANTES: confianza (D1-55) en palabras (límite superior, palabras).
TRUST_WORDS = (
    (0.3, "todavía no le tengo mucha confianza"),
    (0.6, "le tengo algo de confianza"),
    (1.01, "le tengo confianza"),
)
# CONSTANTE: intercambios necesarios para hablar de su ánimo habitual; con
# menos, una media de 1–2 mensajes no dice cómo «suele» estar alguien.
TYPICAL_MOOD_MIN_TURNS = 3
# CONSTANTES: bandas de la valencia de la otra persona (límite superior,
# palabras), sin género gramatical: «con el ánimo bajo», no «decaído/a».
PARTNER_VALENCE_WORDS = (
    (-0.3, "con el ánimo bajo"),
    (0.3, "con un ánimo tranquilo"),
    (1.01, "de buen ánimo"),
)
# CONSTANTES: desde cuándo se nombran la angustia, la hostilidad y la agitación ajenas.
PARTNER_DISTRESS, PARTNER_HOSTILITY, PARTNER_AROUSAL = 0.6, 0.5, 0.7

# Palabras para cada drive que pasa el umbral.
DRIVE_WORDS = {
    "social": "ganas de conversar con alguien",
    "novelty": "ganas de algo nuevo, porque lo de siempre me aburre",
    "rest": "cansancio",
}


def build_who_am_i(config: EntityConfig) -> str:
    """
    Sección «Quién soy» de una entidad con identidad de Fase 1.

    Lleva el nombre, la voz (`persona`), la biografía esencial y las normas
    del ideal del yo. La descripción solo entra si no hay voz. De la biografía
    entran solo los hechos marcados `core` (D1-34): lo que define quién es
    (su origen, sus relaciones) tiene que estar siempre, no solo cuando un
    mensaje se le parece. El resto vive en la memoria y se recupera cuando es
    relevante (CP7), en vez de ocupar el presupuesto de tokens en cada turno.
    """
    parts = [f"Eres {config.name}."]
    if config.persona:
        parts.append(config.persona.strip())
    elif config.description:
        parts.append(config.description.strip())
    core_facts = config.seed_biography.core_facts
    if core_facts:
        facts = "\n".join(f"- {fact.text}" for fact in core_facts)
        parts.append(f"{CORE_BIOGRAPHY_HEADER}\n{facts}")
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


def describe_when(ts: datetime, now: datetime) -> str:
    """
    Cuándo pasó un recuerdo, en palabras: «hace un rato», «ayer», «hace 5 días»,
    «en noviembre de 2025». Como una persona, no da la hora exacta.
    """
    hours = max(0.0, (now - ts).total_seconds()) / 3600
    if hours < 1:
        return "hace un rato"
    if hours < 20:
        return "hace unas horas"
    if hours < 48:
        return "ayer"
    if hours < 14 * 24:
        return f"hace {round(hours / 24)} días"
    if hours < 60 * 24:
        return f"hace {round(hours / (24 * 7))} semanas"
    return f"en {MONTHS[ts.month - 1]} de {ts.year}"


def describe_tone(valence: float) -> str:
    """El tono con que se recuerda algo, según su valencia guardada; vacío si es neutro."""
    return next(words for limit, words in MEMORY_TONE if valence < limit)


def estimate_tokens(text: str) -> int:
    """Estimación de tokens por palabras (D1-10), conservadora."""
    return round(len(text.split()) * TOKENS_PER_WORD)


def _memory_line(item: ScoredEpisode, now: datetime) -> str:
    """Una línea de la sección 4: cuándo, qué y con qué tono."""
    candidate = item.candidate
    text = " ".join(candidate.text.split())
    if candidate.kind != "seed" and len(text) > DIALOGUE_MEMORY_MAX_CHARS:
        text = text[:DIALOGUE_MEMORY_MAX_CHARS].rstrip() + "…"
    tone = describe_tone(candidate.valence)
    return f"- {describe_when(candidate.ts, now).capitalize()}: {text}" + (f" ({tone})" if tone else "")


def build_memory_sections(retrieval: RetrievalResult | None, now: datetime) -> str:
    """
    Secciones 4 «Lo que me viene a la mente» y 5 «Lo que sé» (D1-50).

    Entran primero los hechos (cortos y precisos) y después los recuerdos en
    el orden de MMR, mientras quepan en `MEMORY_SECTIONS_MAX_TOKENS`; lo que no
    cabe se descarta desde el final (lo menos relevante). Devuelve "" si no
    hay nada que decir.
    """
    if retrieval is None:
        return ""
    budget = MEMORY_SECTIONS_MAX_TOKENS
    facts, memories = [], []
    for fact in retrieval.facts:
        line = f"- {fact.text}"
        if estimate_tokens(line) <= budget:
            facts.append(line)
            budget -= estimate_tokens(line)
    for item in retrieval.episodes:
        line = _memory_line(item, now)
        if estimate_tokens(line) <= budget:
            memories.append(line)
            budget -= estimate_tokens(line)
    sections = []
    if memories:
        sections.append("\n".join([MEMORIES_HEADER, MEMORIES_NOTE, *memories]))
    if facts:
        sections.append("\n".join([FACTS_HEADER, *facts]))
    return "\n\n".join(sections)


def _band(value: float, bands: tuple) -> str:
    """Las palabras de la primera banda cuyo límite superior supera `value`."""
    return next(words for limit, words in bands if value < limit)


def _join(items: list[str]) -> str:
    """Une una lista como en una frase: «a», «a y b», «a, b y c»."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


def describe_partner(model: PartnerModel, now: PartnerNow | None, current_time: datetime) -> str:
    """
    Sección 6 «Cómo veo a esta persona», en palabras y sin números (CP8, §5.13).

    `model` es lo que la entidad sabía de la persona *antes* de este turno;
    `now`, cómo parece estar en este mensaje (del appraisal). Ej.: «Estoy
    hablando con Ricardo. Hablamos por primera vez hace 3 días y hemos hablado
    varias veces; le tengo algo de confianza. Suele hablarme de perro y
    trabajo. Le cuesta hablar de trabajo. Ahora se le nota con el ánimo bajo y
    con angustia; busca desahogarse.» Sin género gramatical, porque la
    entidad no sabe el género de la persona.
    """
    lines = [f"Estoy hablando con {model.name}."]
    trust = _band(model.trust, TRUST_WORDS)
    if model.n == 0 or model.first_met is None:
        lines.append(f"Es la primera vez que hablamos; {trust}.")
    else:
        when = describe_when(model.first_met, current_time)
        lines.append(f"Hablamos por primera vez {when} y {_band(model.n, ACQUAINTANCE_WORDS)}; {trust}.")
        if model.n >= TYPICAL_MOOD_MIN_TURNS:
            lines.append(f"Suele hablarme {_band(model.valence_mean, PARTNER_VALENCE_WORDS)}.")
    if model.top_topics:
        lines.append(f"Suele hablarme de {_join(model.top_topics)}.")
    if model.top_sensitive:
        lines.append(f"Le cuesta hablar de {_join(model.top_sensitive)}.")
    if now is not None:
        signs = [_band(now.valence, PARTNER_VALENCE_WORDS)]
        if now.distress >= PARTNER_DISTRESS:
            signs.append("con angustia")
        if now.hostility >= PARTNER_HOSTILITY:
            signs.append("con hostilidad hacia mí")
        elif now.arousal >= PARTNER_AROUSAL:
            signs.append("con mucha energía")
        intent = now.intent.strip()
        lines.append(f"Ahora se le nota {_join(signs)}" + (f"; busca {intent}." if intent else "."))
    return "\n".join(lines)


def build_dialogue_messages(
    config: EntityConfig,
    user_text: str,
    affect: VAD | None = None,
    drives: dict[str, float] | None = None,
    recent_turns: list[ConversationTurn] | tuple = (),
    memories: str = "",
    partner: str = "",
) -> list[dict[str, str]]:
    """
    Arma los mensajes para el preset `dialogue`.

    Sistema (identidad; si hay afecto, cómo se siente; si hay recuerdos, las
    secciones 4–5; si hay persona, la sección 6) → los intercambios recientes
    como pares user/assistant → el mensaje actual. Sin afecto ni historial
    produce el prompt de Fase 0.
    """
    system = build_system_prompt(config)
    if affect is not None:
        system += f"\n\n{FEELINGS_HEADER}\n{describe_feelings(affect, drives or {})}"
    if memories:
        system += f"\n\n{memories}"
    if partner:
        system += f"\n\n{PARTNER_HEADER}\n{partner}"
    messages = [{"role": "system", "content": system}]
    for turn in recent_turns:
        messages.append({"role": "user", "content": turn.user})
        messages.append({"role": "assistant", "content": turn.entity})
    messages.append({"role": "user", "content": user_text})
    return messages


def build_impulsive_messages(
    config: EntityConfig,
    user_text: str,
    affect: VAD,
    drives: dict[str, float] | None = None,
    recent_turns: list[ConversationTurn] | tuple = (),
    partner_name: str | None = None,
) -> list[dict[str, str]]:
    """
    Arma los mensajes para el preset `impulsive` (vía baja, §5.4; D1-31).

    Contexto mínimo: quién soy, cómo me siento (ya con la alarma aplicada),
    con quién hablo (solo el nombre, CP8), la instrucción de responder en el
    impulso, el último intercambio y el mensaje. Sin límites de contenido:
    el usuario revocó §13.2.
    """
    system = build_system_prompt(config)
    system += f"\n\n{FEELINGS_HEADER}\n{describe_feelings(affect, drives or {})}"
    if partner_name:
        system += f"\n\nEstoy hablando con {partner_name}."
    system += f"\n\n{IMPULSIVE_INSTRUCTION}"
    messages = [{"role": "system", "content": system}]
    for turn in list(recent_turns)[-IMPULSIVE_RECENT_TURNS:]:
        messages.append({"role": "user", "content": turn.user})
        messages.append({"role": "assistant", "content": turn.entity})
    messages.append({"role": "user", "content": user_text})
    return messages
