"""
Esquemas de configuración y de estado de una entidad (documento base §4.2, §8.1).

`EntityConfig` es lo que define a la entidad y escribe el desarrollador
(`config.yaml`). `EntityState` es lo que cambia mientras vive (`state.json`).
La identidad (rasgos, ideal del yo, biografía semilla) se añadió en Fase 1,
CP3; afecto, drives y memoria de trabajo llegan en los checkpoints siguientes.
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ebica.core.events import ENTITY_ID_PATTERN
from ebica.identity.biography import PrimaryPerson, SeedBiography
from ebica.identity.traits import Traits

# Modos de la máquina de estados (§6.7). En Fase 0 solo se usa "wake";
# las transiciones entre modos llegan con el orquestador (Fase 1–2).
EntityMode = Literal["wake", "conversation", "sleep", "suspended"]


def _utc_now() -> datetime:
    """Devuelve la hora actual con zona horaria UTC."""
    return datetime.now(timezone.utc)


class EntityConfig(BaseModel):
    """
    Definición estable de una entidad, leída de `config.yaml`.

    Todos los campos de identidad tienen valores por defecto, para que las
    entidades de Fase 0 (`ejemplo`, `ines`) sigan cargando sin cambios.
    `extra="forbid"` hace que un campo desconocido (p. ej. un error de
    tipeo como `nmae`) falle en vez de ignorarse en silencio.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ENTITY_ID_PATTERN)
    # Entidad de la que hereda los campos que no redefine (D1-12). El
    # EntityManager ya hizo la fusión; aquí queda solo como registro.
    base: str | None = Field(None, pattern=ENTITY_ID_PATTERN)
    name: str = Field(min_length=1)
    # Para la consola y, si falta `appraisal_profile`, para el appraisal.
    description: str = ""
    # La voz: cómo habla, en primera persona. Va en la sección «Quién soy».
    persona: str = ""
    # Perfil breve para el appraisal (CP5): quién es, qué le importa y qué le
    # molesta. Lo necesitan `self_relevance` y `goal_congruence`.
    appraisal_profile: str = ""
    # Temperamento CB5T: actúa a través de la dinámica, no del texto (D1-13).
    traits: Traits = Traits()
    # Ideal del yo (§5.2 b): normas en primera persona. En Fase 1 solo van al
    # prompt; en Fase 3 son la referencia de las defensas.
    ego_ideal: list[str] = []
    seed_biography: SeedBiography = SeedBiography()
    primary_person: PrimaryPerson | None = None
    # Si admite ser una IA ante una pregunta sincera (D1-6, §13.4). En Fase 1
    # es declarativo: el comportamiento lo pide una norma del ideal del yo, y
    # la validación de la fase lo comprueba.
    discloses_artificial: bool = True


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
