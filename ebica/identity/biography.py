"""
Biografía semilla y persona principal (documento base §5.2 c, §7.1, §5.9).

La biografía semilla es lo único que entra a la memoria sin haberse vivido en
una conversación (§7.1, "regla de nacimiento"):
- `SeedFact`: lo que la entidad *sabe* de sí (un `Fact` de dominio `self`).
- `SeedEpisode`: lo que puede *recordar* como vivencia (un `Episode`), con el
  afecto con que se recuerda.

Aquí solo se define y valida; CP6 la importa a Neo4j. Los `id` deben ser
estables (no renumerar): la importación usa `(entity_id, id)` para no
duplicar la semilla al cargar varias veces.
"""

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

# Ids de la semilla: minúsculas, dígitos y guiones (p. ej. "f-012", "ep-origen").
SEED_ID_PATTERN = r"^[a-z0-9][a-z0-9-]*$"


class SeedFact(BaseModel):
    """
    Un hecho atómico que la entidad sabe de sí misma (una idea por hecho).

    `core` marca la biografía esencial (§5.13, sección 1; D1-34): lo que define
    quién es y va siempre en «Quién soy». El resto se recupera de la memoria
    solo cuando viene al caso (CP7).
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=SEED_ID_PATTERN)
    text: str = Field(min_length=1)
    core: bool = False


class SeedEpisode(BaseModel):
    """
    Un recuerdo de origen, con fecha y el afecto con que se recuerda.

    `ts` exige zona horaria: ordena los episodios (`NEXT`) y alimenta la
    recencia de la recuperación (§7.3), así que no puede quedar ambigua.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=SEED_ID_PATTERN)
    ts: AwareDatetime
    text: str = Field(min_length=1)
    valence: float = Field(ge=-1.0, le=1.0)
    arousal: float = Field(ge=0.0, le=1.0)
    dominance: float = Field(ge=0.0, le=1.0)
    importance: float = Field(ge=0.0, le=1.0)


class SeedBiography(BaseModel):
    """Hechos y recuerdos de origen; los ids no se repiten entre ambos."""

    model_config = ConfigDict(extra="forbid")

    facts: list[SeedFact] = []
    episodes: list[SeedEpisode] = []

    @model_validator(mode="after")
    def _ids_are_unique(self) -> "SeedBiography":
        """Rechaza ids repetidos: en Neo4j la clave es (entity_id, id)."""
        ids = [item.id for item in [*self.facts, *self.episodes]]
        repeated = sorted({item for item in ids if ids.count(item) > 1})
        if repeated:
            raise ValueError(f"ids repetidos en la biografía semilla: {repeated}")
        return self

    @property
    def is_empty(self) -> bool:
        """True si no hay ni hechos ni episodios."""
        return not self.facts and not self.episodes

    @property
    def core_facts(self) -> list[SeedFact]:
        """Los hechos de la biografía esencial, en el orden del archivo."""
        return [fact for fact in self.facts if fact.core]


class PrimaryPerson(BaseModel):
    """
    La persona principal de la entidad (§5.9): con quien conversa por defecto.

    `trust` es la confianza inicial del PartnerModel (CP8); en Fase 1 no tiene
    dinámica propia.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=SEED_ID_PATTERN)
    name: str = Field(min_length=1)
    trust: float = Field(0.5, ge=0.0, le=1.0)
