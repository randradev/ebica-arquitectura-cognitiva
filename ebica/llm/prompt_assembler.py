"""
Prompt Assembler (documento base §5.13), versión trivial de Fase 0.

Solo usa la identidad de `config.yaml` y el mensaje actual. El ensamblaje
completo (estado afectivo en palabras, recuerdos, PartnerModel, conversación
reciente) llega en Fase 1. Sin historial, la entidad no recuerda el turno
anterior: es una limitación esperada de esta fase.
"""

from ebica.core.state import EntityConfig


def build_system_prompt(config: EntityConfig) -> str:
    """Describe quién es la entidad con su nombre, descripción y persona."""
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
