"""
Conexión a Neo4j y esquema de la memoria (documento base §7, D7).

Define la estructura (restricciones de unicidad, índices por entidad e
índices vectoriales) y la búsqueda vectorial básica. La escritura de episodios
y de la semilla vive en `episodes.py` (CP6); la recuperación híbrida de §7.3
llega en CP7.

Todas las entidades comparten una base de datos (Neo4j Community admite una
sola base de usuario), así que cada nodo lleva `entity_id` y toda consulta
filtra por él (§7.1).
"""

import os

from neo4j import AsyncDriver, AsyncGraphDatabase


class SchemaMismatchError(RuntimeError):
    """El esquema existente en Neo4j no coincide con el que espera el código."""

# 127.0.0.1 y no localhost: en Windows, localhost prueba primero IPv6 (::1),
# donde Neo4j no escucha, y cada conexión nueva tarda ~2 s (medido en CP2).
DEFAULT_URI = "bolt://127.0.0.1:7687"
DEFAULT_USER = "neo4j"

# Etiquetas cuyos nodos se identifican por (entity_id, id): el mismo `id`
# puede repetirse en dos entidades distintas sin chocar (p. ej. un clon).
LABELS_WITH_ID = ("Person", "Episode", "Trace", "Fact", "Commitment")

# Todas las etiquetas del esquema §7.2.
ALL_LABELS = ("Self", "Person", "Episode", "Trace", "Revision", "Fact", "Topic", "Commitment")

# Etiquetas con un índice simple por `entity_id`, porque toda consulta empieza
# filtrando por entidad. `Self` no lo necesita: su restricción de unicidad
# por `entity_id` ya crea ese índice, y Neo4j no admite ambos a la vez.
LABELS_WITH_ENTITY_INDEX = tuple(label for label in ALL_LABELS if label != "Self")

# Etiquetas con índice vectorial sobre `embedding` (§7.1): lo que la entidad
# puede evocar por parecido de significado.
VECTOR_LABELS = ("Episode", "Fact", "Topic")

# CONSTANTE: cuántos vecinos se piden al índice por cada resultado deseado
# (D1-11). El índice vectorial busca entre todas las entidades y el filtro por
# `entity_id` se aplica después; pedir de más evita quedarse corto cuando otra
# entidad tiene muchos nodos parecidos.
VECTOR_OVERSAMPLING = 10
# CONSTANTE: tope de vecinos pedidos al índice, para acotar el costo.
VECTOR_MAX_CANDIDATES = 1000
# CONSTANTE: espera máxima para que los índices recién creados queden ONLINE.
INDEX_WAIT_SECONDS = 60


def vector_index_name(label: str) -> str:
    """Nombre del índice vectorial de una etiqueta, p. ej. `episode_embedding`."""
    return f"{label.lower()}_embedding"


def schema_statements(embedding_dimension: int) -> list[str]:
    """
    Devuelve las sentencias Cypher del esquema, en orden.

    `embedding_dimension` es la dimensión del modelo de embeddings (1024 para
    bge-m3); queda fija en los índices vectoriales al crearlos. Todas las
    sentencias son idempotentes (`IF NOT EXISTS` / `IF EXISTS`), así que el
    esquema puede aplicarse en cada arranque.
    """
    if embedding_dimension <= 0:
        raise ValueError(f"Dimensión de embedding inválida: {embedding_dimension}")
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
    # Migración desde Fase 0, que creó un índice simple sobre Self.entity_id:
    # Neo4j rechaza la restricción mientras ese índice exista (sondeado en CP2).
    # Tras la primera ejecución no hay nada que borrar y la sentencia no hace nada.
    statements.append("DROP INDEX self_entity_id IF EXISTS")
    # Un único nodo Self por entidad.
    statements.append(
        "CREATE CONSTRAINT self_entity_id_unique IF NOT EXISTS "
        "FOR (n:Self) REQUIRE n.entity_id IS UNIQUE"
    )
    # Una versión de un episodio existe una sola vez (D1-9: Revision.episode_id
    # es una desviación menor de §7.2, que no vincula Revision a su episodio).
    statements.append(
        "CREATE CONSTRAINT revision_entity_id_episode_id_version IF NOT EXISTS "
        "FOR (n:Revision) REQUIRE (n.entity_id, n.episode_id, n.version) IS UNIQUE"
    )
    statements += [
        f"CREATE INDEX {label.lower()}_entity_id IF NOT EXISTS FOR (n:{label}) ON (n.entity_id)"
        for label in LABELS_WITH_ENTITY_INDEX
    ]
    # Similitud coseno: los vectores se guardan normalizados y lo que importa es
    # la dirección (el significado), no la longitud.
    statements += [
        f"CREATE VECTOR INDEX {vector_index_name(label)} IF NOT EXISTS "
        f"FOR (n:{label}) ON n.embedding OPTIONS {{indexConfig: {{"
        f"`vector.dimensions`: {int(embedding_dimension)}, "
        f"`vector.similarity_function`: 'cosine'}}}}"
        for label in VECTOR_LABELS
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

    async def apply_schema(self, embedding_dimension: int) -> list[str]:
        """
        Crea las restricciones e índices que falten y devuelve las sentencias ejecutadas.

        Después comprueba la dimensión de los índices vectoriales: `IF NOT
        EXISTS` deja intacto un índice previo aunque tenga otra dimensión, y
        entonces la búsqueda fallaría más tarde con un error confuso.
        Lanza `SchemaMismatchError` si no coincide.
        """
        statements = schema_statements(embedding_dimension)
        for statement in statements:
            await self.execute(statement)
        # Los índices nuevos se construyen en segundo plano; se espera a que
        # estén ONLINE para que la primera búsqueda no falle.
        await self.execute(f"CALL db.awaitIndexes({INDEX_WAIT_SECONDS})")
        await self.check_vector_dimensions(embedding_dimension)
        return statements

    async def vector_index_dimensions(self) -> dict[str, int]:
        """Devuelve la dimensión de cada índice vectorial existente, por nombre."""
        rows = await self.execute(
            "SHOW INDEXES YIELD name, type, options WHERE type = 'VECTOR' RETURN name, options"
        )
        return {row["name"]: row["options"]["indexConfig"]["vector.dimensions"] for row in rows}

    async def check_vector_dimensions(self, embedding_dimension: int) -> None:
        """
        Comprueba que los índices vectoriales del esquema tengan la dimensión esperada.

        Una diferencia indica que se cambió el modelo de embeddings: hay que
        borrar los índices y recalcular los embeddings guardados (PLAN, riesgos).
        """
        existing = await self.vector_index_dimensions()
        wrong = {
            name: existing[name]
            for name in map(vector_index_name, VECTOR_LABELS)
            if name in existing and existing[name] != embedding_dimension
        }
        if wrong:
            raise SchemaMismatchError(
                f"Índices vectoriales con dimensión distinta de {embedding_dimension}: {wrong}. "
                "¿Cambió el modelo de embeddings? Hay que borrar esos índices y recalcular los embeddings."
            )

    async def vector_search(
        self, label: str, entity_id: str, vector: list[float], k: int
    ) -> list[dict]:
        """
        Devuelve hasta `k` nodos de una entidad, los más parecidos a `vector`.

        Cada fila trae `id`, `name` (solo en `Topic`) y `score`. El `score` de
        Neo4j no es el coseno, sino `(1 + coseno) / 2`, en [0, 1].
        Sobremuestreo (D1-11): el índice no sabe filtrar por entidad, así que
        se le piden `k · VECTOR_OVERSAMPLING` vecinos y se descartan los de
        otras entidades. Si otra entidad acapara a todos esos vecinos, pueden
        volver menos de `k` resultados.
        """
        if label not in VECTOR_LABELS:
            raise ValueError(f"{label} no tiene índice vectorial")
        candidates = min(k * VECTOR_OVERSAMPLING, VECTOR_MAX_CANDIDATES)
        return await self.execute(
            "CALL db.index.vector.queryNodes($index, $candidates, $vector) YIELD node, score "
            "WHERE node.entity_id = $entity_id "
            "RETURN node.id AS id, node.name AS name, score "
            "ORDER BY score DESC LIMIT $k",
            index=vector_index_name(label),
            candidates=candidates,
            vector=vector,
            entity_id=entity_id,
            k=k,
        )

    async def constraint_names(self) -> set[str]:
        """Devuelve los nombres de las restricciones existentes (`SHOW CONSTRAINTS`)."""
        return {row["name"] for row in await self.execute("SHOW CONSTRAINTS YIELD name")}

    async def index_names(self) -> set[str]:
        """Devuelve los nombres de los índices existentes (`SHOW INDEXES`)."""
        return {row["name"] for row in await self.execute("SHOW INDEXES YIELD name")}
