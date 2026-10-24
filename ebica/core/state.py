"""
Esquemas de configuración y de estado de una entidad (documento base §4.2, §8.1).

`EntityConfig` es lo que define a la entidad y escribe el desarrollador
(`config.yaml`). `EntityState` es lo que cambia mientras vive (`state.json`).
En Fase 0 ambos son mínimos; rasgos, afecto, drives y memoria de trabajo se
añaden en Fase 1.
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ebica.core.events import ENTITY_ID_PATTERN

# Modos de la máquina de estados (§6.7). En Fase 0 solo se usa "wake";
# las transiciones entre modos llegan con el orquestador (Fase 1–2).
EntityMode = Literal["wake", "conversation", "sleep", "suspended"]


def _utc_now() -> datetime:
    """Devuelve la hora actual con zona horaria UTC."""
    return datetime.now(timezone.utc)


class EntityConfig(BaseModel):
    """
    Definición estable de una entidad, leída de `config.yaml`.

    Los rasgos (CB5T), la biografía semilla y el ideal del yo pertenecen aquí,
    pero se añadirán en Fase 1 y 3. `extra="forbid"` hace que un campo
    desconocido (p. ej. un error de tipeo como `nmae`) falle en vez de
    ignorarse en silencio.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ENTITY_ID_PATTERN)
    name: str = Field(min_length=1)
    description: str = ""
    # Descripción breve en primera persona; en Fase 0 es todo lo que el
    # prompt sabe de la entidad (ver PLAN, exclusiones).
    persona: str = ""


class EntityState(BaseModel):
    """
    Snapshot mínimo del estado vivo de una entidad, guardado en `state.json`.

    Es un subconjunto del `EntityState` de §8.1; crecerá fase a fase.
    """

    entity_id: str = Field(pattern=ENTITY_ID_PATTERN)
    mode: EntityMode = "wake"
    created_at: datetime = Field(default_factory=_utc_now)
    # None hasta la primera carga.
    last_loaded_at: datetime | None = None
