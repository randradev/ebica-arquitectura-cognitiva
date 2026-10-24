"""
Manejador de turno mínimo (Fase 0): mensaje del usuario → respuesta en streaming.

Es una versión reducida del ciclo de turno de §6.2: sin appraisal, afecto ni
memoria. Lo esencial ya está: cada paso emite su evento y queda encadenado
por `cause_id` (perception.input → llm.request → llm.response).
En Fase 1 esta lógica pasa al CognitiveOrchestrator.
"""

from collections.abc import AsyncIterator
from contextlib import aclosing

from ebica.core.events import EventBus
from ebica.entities.manager import Entity
from ebica.llm.client import LLMClient
from ebica.llm.prompt_assembler import build_dialogue_messages


async def run_user_turn(
    entity: Entity, text: str, bus: EventBus, llm: LLMClient
) -> AsyncIterator[str]:
    """
    Procesa un mensaje del usuario y entrega la respuesta fragmento a fragmento.

    Si quien consume deja de leer (p. ej. la consola se desconecta), cerrar este
    iterador cierra también el del LLM, que emite `llm.cancelled`.
    """
    entity_id = entity.config.id
    perception = bus.emit(entity_id, "perception.input", {"text": text, "source": "user"})
    messages = build_dialogue_messages(entity.config, text)

    # `aclosing` garantiza que el streaming del LLM se cierre en el acto si este
    # iterador se cierra; sin él, la conexión quedaría abierta hasta que el
    # recolector de basura lo finalice.
    stream = llm.stream(messages, entity_id=entity_id, preset="dialogue", cause_id=perception.id)
    async with aclosing(stream) as pieces:
        async for piece in pieces:
            yield piece
