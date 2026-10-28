"""
Pruebas del esquema de Neo4j (Fase 0 CP4; Fase 1 CP2: índices vectoriales y restricciones de Self y Revision).

Las de integración necesitan Neo4j encendido (`docker compose up -d`) y
`NEO4J_PASSWORD` en el entorno; si no, se omiten con un aviso.
"""

import asyncio
import os

import pytest
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from ebica.memory.graph import (
    LABELS_WITH_ENTITY_INDEX,
    LABELS_WITH_ID,
    VECTOR_LABELS,
    GraphStore,
    SchemaMismatchError,
    schema_statements,
    vector_index_name,
)
from fake_embedder import FakeEmbedder

# Dimensión de bge-m3, el modelo elegido en CP2: es la de los índices reales.
DIMENSION = 1024

EXPECTED_CONSTRAINTS = {f"{label.lower()}_entity_id_id" for label in LABELS_WITH_ID} | {
    "topic_entity_id_name",
    "self_entity_id_unique",
    "revision_entity_id_episode_id_version",
}
EXPECTED_VECTOR_INDEXES = {vector_index_name(label) for label in VECTOR_LABELS}
EXPECTED_INDEXES = {f"{label.lower()}_entity_id" for label in LABELS_WITH_ENTITY_INDEX} | EXPECTED_VECTOR_INDEXES

# Prefijo de las entidades temporales de estas pruebas; se borran al terminar.
TEST_PREFIX = "test_cp2_"


def test_every_statement_is_idempotent():
    """Todas las sentencias son idempotentes, para poder aplicarse en cada arranque."""
    assert all(
        "IF NOT EXISTS" in statement or "IF EXISTS" in statement
        for statement in schema_statements(DIMENSION)
    )


def test_schema_covers_expected_names():
    """El esquema declara todas las restricciones e índices esperados."""
    text = "\n".join(schema_statements(DIMENSION))

    for name in EXPECTED_CONSTRAINTS | EXPECTED_INDEXES:
        assert f" {name} " in text


def test_vector_indexes_use_the_dimension_and_cosine():
    """Cada índice vectorial lleva la dimensión pedida y similitud coseno."""
    vector_statements = [s for s in schema_statements(768) if "VECTOR INDEX" in s]

    assert len(vector_statements) == len(VECTOR_LABELS)
    for statement in vector_statements:
        assert "`vector.dimensions`: 768" in statement
        assert "'cosine'" in statement


def test_self_index_is_dropped_before_its_constraint():
    """El índice simple de Fase 0 sobre Self se borra antes de crear la restricción (Neo4j no admite ambos)."""
    statements = schema_statements(DIMENSION)
    drop = statements.index("DROP INDEX self_entity_id IF EXISTS")
    constraint = next(i for i, s in enumerate(statements) if "self_entity_id_unique" in s)

    assert drop < constraint
    assert not any("CREATE INDEX self_entity_id " in s for s in statements)


def test_invalid_dimension_is_rejected():
    """Una dimensión no positiva es un error de configuración, no un índice válido."""
    with pytest.raises(ValueError):
        schema_statements(0)


def test_from_env_requires_password(monkeypatch):
    """Sin NEO4J_PASSWORD se falla con un mensaje que dice qué falta."""
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="NEO4J_PASSWORD"):
        GraphStore.from_env()


async def test_vector_search_rejects_labels_without_index():
    """Solo Episode, Fact y Topic tienen índice vectorial."""
    store = GraphStore("bolt://127.0.0.1:1", "neo4j", "x")  # no se conecta: falla antes
    try:
        with pytest.raises(ValueError):
            await store.vector_search("Trace", "e", [1.0], k=1)
    finally:
        await store.close()


@pytest.fixture
async def graph():
    """Conexión real a Neo4j con el esquema aplicado, o se omite la prueba si no está disponible."""
    if not os.environ.get("NEO4J_PASSWORD"):
        pytest.skip("NEO4J_PASSWORD no está definida en el entorno")
    store = GraphStore.from_env()
    try:
        await store.verify()
    except (ServiceUnavailable, Neo4jError, OSError) as error:
        await store.close()
        pytest.skip(f"Neo4j no disponible en {store.uri}: {error}")
    await store.apply_schema(DIMENSION)
    yield store
    await store.execute(
        "MATCH (n) WHERE n.entity_id STARTS WITH $prefix DETACH DELETE n", prefix=TEST_PREFIX
    )
    await store.close()


@pytest.mark.integration
async def test_apply_schema_twice_does_not_fail(graph):
    """Aplicar el esquema otra vez (la fixture ya lo aplicó una) no lanza errores."""
    await graph.apply_schema(DIMENSION)


@pytest.mark.integration
async def test_schema_is_listed_by_neo4j(graph):
    """SHOW CONSTRAINTS / SHOW INDEXES listan lo esperado, y el índice simple de Self ya no existe."""
    indexes = await graph.index_names()

    assert EXPECTED_CONSTRAINTS <= await graph.constraint_names()
    assert EXPECTED_INDEXES <= indexes
    assert "self_entity_id" not in indexes


@pytest.mark.integration
async def test_vector_indexes_are_online_with_the_dimension(graph):
    """Los 3 índices vectoriales están ONLINE y con la dimensión del modelo."""
    rows = await graph.execute(
        "SHOW INDEXES YIELD name, type, state WHERE type = 'VECTOR' RETURN name, state"
    )
    states = {row["name"]: row["state"] for row in rows}

    assert {states[name] for name in EXPECTED_VECTOR_INDEXES} == {"ONLINE"}
    dimensions = await graph.vector_index_dimensions()
    assert {dimensions[name] for name in EXPECTED_VECTOR_INDEXES} == {DIMENSION}


@pytest.mark.integration
async def test_dimension_mismatch_is_detected(graph):
    """Si el modelo configurado tiene otra dimensión, se avisa en lugar de seguir con índices inservibles."""
    with pytest.raises(SchemaMismatchError, match="768"):
        await graph.check_vector_dimensions(768)


@pytest.mark.integration
async def test_uniqueness_is_per_entity(graph):
    """El mismo id puede existir en dos entidades, pero no dos veces en la misma."""
    create = "CREATE (:Episode {entity_id: $entity_id, id: 'ep-1'})"
    await graph.execute(create, entity_id=f"{TEST_PREFIX}a")
    await graph.execute(create, entity_id=f"{TEST_PREFIX}b")
    with pytest.raises(Neo4jError):
        await graph.execute(create, entity_id=f"{TEST_PREFIX}a")


@pytest.mark.integration
async def test_one_self_per_entity(graph):
    """Cada entidad tiene un solo nodo Self."""
    create = "CREATE (:Self {entity_id: $entity_id})"
    await graph.execute(create, entity_id=f"{TEST_PREFIX}a")
    await graph.execute(create, entity_id=f"{TEST_PREFIX}b")
    with pytest.raises(Neo4jError):
        await graph.execute(create, entity_id=f"{TEST_PREFIX}a")


@pytest.mark.integration
async def test_revision_version_is_unique_per_episode(graph):
    """Un episodio no puede tener dos revisiones con la misma versión (D1-9); otra versión sí."""
    create = "CREATE (:Revision {entity_id: $entity_id, episode_id: 'ep-1', version: $version})"
    entity_id = f"{TEST_PREFIX}a"
    await graph.execute(create, entity_id=entity_id, version=2)
    await graph.execute(create, entity_id=entity_id, version=3)
    with pytest.raises(Neo4jError):
        await graph.execute(create, entity_id=entity_id, version=2)


async def _search_until(graph, *args, expected_count: int, **kwargs) -> list[dict]:
    """
    Repite la búsqueda vectorial hasta ver `expected_count` resultados (máx. ~3 s).

    El índice vectorial incorpora los nodos recién escritos con un pequeño
    retraso, así que una búsqueda inmediata puede no verlos todavía.
    """
    rows: list[dict] = []
    for _ in range(30):
        rows = await graph.vector_search(*args, **kwargs)
        if len(rows) >= expected_count:
            break
        await asyncio.sleep(0.1)
    return rows


@pytest.mark.integration
async def test_vector_search_returns_expected_neighbour_of_the_entity(graph):
    """
    La búsqueda devuelve el episodio más parecido de la entidad, no los de otra.

    La entidad `b` tiene un episodio idéntico a la consulta: si el filtro por
    `entity_id` fallara, aparecería primero.
    """
    embedder = FakeEmbedder(dimension=DIMENSION)
    texts = {
        "ep-perro": "adopté un perro que se llama Toby",
        "ep-banco": "mañana tengo la entrevista en el banco",
        "ep-playa": "fui a la playa y el agua estaba helada",
    }
    vectors = await embedder.embed(list(texts.values()), "passage")
    rows = [{"id": ep_id, "embedding": vector} for ep_id, vector in zip(texts, vectors)]
    await graph.execute(
        "UNWIND $rows AS r CREATE (:Episode {entity_id: $entity_id, id: r.id, embedding: r.embedding})",
        rows=rows, entity_id=f"{TEST_PREFIX}a",
    )
    [query] = await embedder.embed(["¿cómo está tu perro Toby?"], "query")
    await graph.execute(
        "CREATE (:Episode {entity_id: $entity_id, id: 'ep-clon', embedding: $embedding})",
        entity_id=f"{TEST_PREFIX}b", embedding=query,
    )

    found = await _search_until(graph, "Episode", f"{TEST_PREFIX}a", query, k=3, expected_count=3)

    assert [row["id"] for row in found][0] == "ep-perro"
    assert "ep-clon" not in {row["id"] for row in found}
    # El score de Neo4j es (1 + coseno) / 2: siempre en [0, 1] y ordenado.
    scores = [row["score"] for row in found]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= score <= 1.0 for score in scores)


@pytest.mark.integration
async def test_vector_search_falls_back_to_exact_when_another_entity_crowds_the_index(graph):
    """
    Si los vecinos del índice son todos de otra entidad, el respaldo exacto
    igual devuelve el nodo propio (D1-11; respaldo de CP7).

    La entidad `b` tiene 15 nodos idénticos a la consulta; `a`, uno solo y
    menos parecido. Con k = 1 el índice trae 10 vecinos, todos de `b`.
    """
    def axis(*weights: float) -> list[float]:
        """Vector de norma 1 con los pesos dados en los primeros ejes."""
        values = [0.0] * DIMENSION
        values[: len(weights)] = weights
        norm = sum(v * v for v in values) ** 0.5
        return [v / norm for v in values]

    await graph.execute(
        "UNWIND range(1, 15) AS i CREATE (:Episode {entity_id: $e, id: 'ep-' + toString(i), embedding: $v})",
        e=f"{TEST_PREFIX}b", v=axis(1.0),
    )
    await graph.execute(
        "CREATE (:Episode {entity_id: $e, id: 'ep-propio', embedding: $v})", e=f"{TEST_PREFIX}a", v=axis(1.0, 1.0),
    )

    found = await graph.vector_search("Episode", f"{TEST_PREFIX}a", axis(1.0), k=1)

    assert [row["id"] for row in found] == ["ep-propio"]
    # Misma escala que el índice: (1 + coseno) / 2, con coseno = 1/√2.
    assert found[0]["score"] == pytest.approx((1 + 2 ** -0.5) / 2, abs=1e-4)
