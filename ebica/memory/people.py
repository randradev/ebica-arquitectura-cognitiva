"""
Las personas que conoce una entidad, en Neo4j (documento base §5.9, §7.2; CP8).

Cada persona es un nodo `Person` con su modelo (`PartnerModel`): las
propiedades de §7.2 (`name`, `primary`, `provisional`, `known_via`, `trust`,
`n`, `valence_mean`, `arousal_mean`) más `model_json` con los conteos de temas
y las fechas. Aquí se leen, se crean y se asegura el `primary`; la
actualización de cada turno va en la misma transacción que el episodio
(`MemoryWriter.write_turn`), para que el recuerdo y el modelo no se desfasen.
"""

import json
from dataclasses import dataclass
from ebica.identity.biography import PrimaryPerson
from ebica.memory.graph import GraphStore
from ebica.social.partner import PartnerModel, new_person_id

# Propiedades que se guardan en `model_json` (el resto son propiedades de §7.2).
_JSON_FIELDS = ("first_met", "last_seen", "topics", "sensitive_topics")

_PERSON_FIELDS = """
p.id AS id, p.name AS name, p.primary AS primary, p.trust AS trust, p.n AS n,
p.valence_mean AS valence_mean, p.arousal_mean AS arousal_mean, p.model_json AS model_json
"""

# Crea el `Person` del usuario principal si falta. Si ya existe, actualiza
# nombre y confianza desde la config (en Fase 1 la confianza es estática,
# D1-55) sin tocar lo aprendido (n, medias, temas).
_ENSURE_PRIMARY = f"""
MERGE (p:Person {{entity_id: $entity_id, id: $id}})
ON CREATE SET p += $props
SET p.name = $name, p.trust = $trust, p.primary = true
RETURN {_PERSON_FIELDS}
"""

# Desmarca a cualquier otra persona como `primary`: hay uno solo por entidad (§5.9).
_UNMARK_OTHER_PRIMARY = """
MATCH (p:Person {entity_id: $entity_id, primary: true}) WHERE p.id <> $id
SET p.primary = false
"""


def person_properties(model: PartnerModel) -> dict:
    """Propiedades del nodo `Person` para un modelo (las de §7.2 más `model_json`)."""
    data = model.model_dump(mode="json", include=set(_JSON_FIELDS))
    return {
        "name": model.name, "primary": model.primary, "provisional": False, "known_via": "direct",
        "trust": model.trust, "n": model.n, "valence_mean": model.valence_mean,
        "arousal_mean": model.arousal_mean, "model_json": json.dumps(data, ensure_ascii=False),
    }


def model_from_row(row: dict) -> PartnerModel:
    """Reconstruye el modelo desde una fila de Neo4j (las propiedades y `model_json`)."""
    extra = json.loads(row["model_json"]) if row.get("model_json") else {}
    return PartnerModel.model_validate({
        "id": row["id"], "name": row["name"], "primary": bool(row["primary"]),
        "trust": row["trust"], "n": row["n"] or 0, "valence_mean": row["valence_mean"] or 0.0,
        "arousal_mean": row["arousal_mean"] or 0.0, **extra,
    })


@dataclass
class EnsuredPerson:
    """Resultado de asegurar una persona: su modelo y si se creó ahora (para `tom.person_created`)."""

    model: PartnerModel
    created: bool


class PeopleStore:
    """Lee y crea los `Person` de una entidad; todo patrón lleva su `entity_id` (§7.1)."""

    def __init__(self, graph: GraphStore) -> None:
        """Guarda el acceso al grafo."""
        self.graph = graph

    async def list(self, entity_id: str) -> list[PartnerModel]:
        """Todas las personas de la entidad: primero el `primary`, después por nombre."""
        rows = await self.graph.execute(
            f"MATCH (p:Person {{entity_id: $entity_id}}) RETURN {_PERSON_FIELDS} "
            "ORDER BY p.primary DESC, toLower(p.name)",
            entity_id=entity_id,
        )
        return [model_from_row(row) for row in rows]

    async def get(self, entity_id: str, person_id: str) -> PartnerModel | None:
        """El modelo de una persona, o None si la entidad no la conoce."""
        rows = await self.graph.execute(
            f"MATCH (p:Person {{entity_id: $entity_id, id: $id}}) RETURN {_PERSON_FIELDS}",
            entity_id=entity_id, id=person_id,
        )
        return model_from_row(rows[0]) if rows else None

    async def ensure_primary(self, entity_id: str, primary: PrimaryPerson) -> EnsuredPerson:
        """
        Asegura el `Person` del usuario principal, de forma idempotente.

        La primera carga lo crea; las siguientes solo sincronizan nombre y
        confianza con la config. Si la config cambió de `primary`, el anterior
        deja de serlo (pero conserva su historia).
        """
        existed = await self.get(entity_id, primary.id) is not None
        await self.graph.execute(_UNMARK_OTHER_PRIMARY, entity_id=entity_id, id=primary.id)
        [row] = await self.graph.execute(
            _ENSURE_PRIMARY, entity_id=entity_id, id=primary.id, name=primary.name,
            trust=primary.trust, props=person_properties(PartnerModel.for_primary(primary)),
        )
        return EnsuredPerson(model=model_from_row(row), created=not existed)

    async def open_commitments(self, entity_id: str, person_id: str) -> "list[dict]":  # `list` es un método de esta clase
        """
        Los compromisos abiertos que prometió una persona (CP10, `commitment_watch`),
        del más reciente al más viejo: filas con `id`, `text`, `context` (el
        comienzo del mensaje en que se prometió) y `ts`.
        """
        rows = await self.graph.execute(
            "MATCH (:Person {entity_id: $entity_id, id: $person_id})-[:PROMISED]->"
            "(c:Commitment {entity_id: $entity_id, status: 'open'}) "
            "RETURN c.id AS id, c.text AS text, c.context AS context, c.ts AS ts ORDER BY c.ts DESC",
            entity_id=entity_id, person_id=person_id,
        )
        return [{"id": row["id"], "text": row["text"], "context": row["context"], "ts": row["ts"].to_native()}
                for row in rows]

    async def create(self, entity_id: str, name: str) -> PartnerModel:
        """
        Crea una persona nueva con nombre, sin historia (§5.9, «persona nueva con nombre»).

        El id sale del nombre (D1-52). Lanza `DuplicatePersonError` si ya
        existe alguien con ese nombre. La confianza es la inicial de las
        personas nuevas (D1-55). `first_met` se fija en su primer turno.
        """
        existing = {model.id: model.name for model in await self.list(entity_id)}
        model = PartnerModel(id=new_person_id(name, existing), name=name.strip())
        await self.graph.execute(
            "CREATE (p:Person {entity_id: $entity_id, id: $id}) SET p += $props",
            entity_id=entity_id, id=model.id, props=person_properties(model),
        )
        return model
