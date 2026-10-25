"""
Prompt Assembler (documento base §5.13).

Fase 1, CP3: la sección 1, «Quién soy», con la voz y el ideal del yo. El estado
afectivo en palabras, los recuerdos, el PartnerModel y la conversación
reciente llegan en CP5–CP9. Sin historial, la entidad todavía no recuerda el
turno anterior.

Los rasgos no generan texto (D1-13): actúan a través de la dinámica. Así, dos
variantes que solo difieren en N reciben exactamente el mismo prompt.
"""

from ebica.core.state import EntityConfig

# Encabezado de las normas del ideal del yo en el prompt.
EGO_IDEAL_HEADER = "Mis normas, lo que intento sostener:"


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


def build_dialogue_messages(config: EntityConfig, user_text: str) -> list[dict[str, str]]:
    """Arma los mensajes para el preset `dialogue`: identidad + mensaje del usuario."""
    return [
        {"role": "system", "content": build_system_prompt(config)},
        {"role": "user", "content": user_text},
    ]
