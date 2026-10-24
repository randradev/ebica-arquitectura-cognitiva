"""
Conexión a Neo4j y esquema de la memoria (documento base §7, D7).

Fase 0 solo crea la estructura: restricciones de unicidad e índices. Escribir
episodios y recuperarlos llega en Fase 1; los índices vectoriales también,
cuando se elija el modelo de embeddings (PLAN D0-5).

Todas las entidades comparten una base de datos (Neo4j Community admite una
sola base de usuario), así que cada nodo lleva `entity_id` y toda consulta
filtra por él (§7.1).
"""

import os

from neo4j import AsyncDriver, AsyncGraphDatabase

DEFAULT_URI = "bolt://localhost:7687"
DEFAULT_USER = "neo4j"

# Etiquetas cuyos nodos se identifican por (entity_id, id): el mismo `id`
# puede repetirse en dos entidades distintas sin chocar (p. ej. un clon).
LABELS_WITH_ID = ("Person", "Episode", "Trace", "Fact", "Commitment")

# Todas las etiquetas del esquema §7.2: cada una lleva un índice por
# `entity_id`, porque toda consulta empieza filtrando por entidad.
ALL_LABELS = ("Self", "Person", "Episode", "Trace", "Revision", "Fact", "Topic", "Commitment")


def schema_statements() -> list[str]:
    """
    Devuelve las sentencias Cypher del esquema, en orden.

    Todas usan `IF NOT EXISTS`: ejecutarlas varias veces no falla ni duplica
    nada (son idempotentes), así que el esquema puede aplicarse en cada arranque.
    """
    statements = [
        f"CREATE CONSTRAINT {label.lower()}_entity_id_id IF NOT EXISTS "
        f"FOR (n:{label}) REQUIRE (n.entity_id, n.id) IS UNIQUE"
        for label in LABELS_WITH_ID
    ]
    # Un tema se identifica por su nombre dentro de cada entidad.
    statements.append(
        "CREATE CONSTRAINT topic_entity_id_name IF NOT EXISTS "
        "FOR (n:Topic) REQUIRE (n.entity_id, n.name) IS UNIQUE"
    )
    statements += [
        f"CREATE INDEX {label.lower()}_entity_id IF NOT EXISTS FOR (n:{label}) ON (n.entity_id)"
        for label in ALL_LABELS
    ]
    return statements


class GraphStore:
    """Acceso asíncrono a Neo4j (D3: el motor es un solo bucle asyncio)."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        """Crea el driver; la conexión real se abre en la primera consulta."""
        self.uri = uri
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    @classmethod
    def from_env(cls) -> "GraphStore":
        """
        Crea el acceso con `NEO4J_URI`, `NEO4J_USER` y `NEO4J_PASSWORD`.

        La contraseña no tiene valor por defecto: sin ella se falla con un
        mensaje claro en lugar de intentar una conexión que será rechazada.
        """
        password = os.environ.get("NEO4J_PASSWORD")
        if not password:
            raise RuntimeError("Falta la variable de entorno NEO4J_PASSWORD (ver .env.example)")
        return cls(
            uri=os.environ.get("NEO4J_URI", DEFAULT_URI),
            user=os.environ.get("NEO4J_USER", DEFAULT_USER),
            password=password,
        )

    async def __aenter__(self) -> "GraphStore":
        """Permite usar el acceso con `async with`."""
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Cierra el driver al salir del bloque `async with`."""
        await self.close()

    async def close(self) -> None:
        """Cierra el driver y sus conexiones."""
        await self._driver.close()

    async def verify(self) -> None:
        """Comprueba que el servidor responde y acepta las credenciales (lanza excepción si no)."""
        await self._driver.verify_connectivity()

    async def execute(self, query: str, **parameters: object) -> list[dict]:
        """
        Ejecuta una consulta Cypher y devuelve sus filas como diccionarios.

        Los valores se pasan como parámetros (`$nombre`), nunca pegados en el
        texto: así no hay inyección de Cypher y Neo4j reutiliza el plan.
        """
        records, _, _ = await self._driver.execute_query(query, parameters)
        return [record.data() for record in records]

    async def apply_schema(self) -> list[str]:
        """Crea las restricciones e índices que falten y devuelve las sentencias ejecutadas."""
        statements = schema_statements()
        for statement in statements:
            await self.execute(statement)
        return statements

    async def constraint_names(self) -> set[str]:
        """Devuelve los nombres de las restricciones existentes (`SHOW CONSTRAINTS`)."""
        return {row["name"] for row in await self.execute("SHOW CONSTRAINTS YIELD name")}

    async def index_names(self) -> set[str]:
        """Devuelve los nombres de los índices existentes (`SHOW INDEXES`)."""
        return {row["name"] for row in await self.execute("SHOW INDEXES YIELD name")}
