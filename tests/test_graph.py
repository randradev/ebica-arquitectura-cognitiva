"""
Pruebas del esquema de Neo4j (CP4).

Las de integración necesitan Neo4j encendido (`docker compose up -d`) y
`NEO4J_PASSWORD` en el entorno; si no, se omiten con un aviso.
"""

import os

import pytest
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from ebica.memory.graph import ALL_LABELS, LABELS_WITH_ID, GraphStore, schema_statements

EXPECTED_CONSTRAINTS = {f"{label.lower()}_entity_id_id" for label in LABELS_WITH_ID} | {
    "topic_entity_id_name"
}
EXPECTED_INDEXES = {f"{label.lower()}_entity_id" for label in ALL_LABELS}


def test_every_statement_is_idempotent():
    """Todas las sentencias usan IF NOT EXISTS, para poder aplicarse en cada arranque."""
    assert all("IF NOT EXISTS" in statement for statement in schema_statements())


def test_schema_covers_expected_names():
    """El esquema declara una restricción por etiqueta con id, la de Topic y un índice por etiqueta."""
    text = "\n".join(schema_statements())

    for name in EXPECTED_CONSTRAINTS | EXPECTED_INDEXES:
        assert f" {name} " in text


def test_from_env_requires_password(monkeypatch):
    """Sin NEO4J_PASSWORD se falla con un mensaje que dice qué falta."""
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="NEO4J_PASSWORD"):
        GraphStore.from_env()


@pytest.fixture
async def graph():
    """Conexión real a Neo4j, o se omite la prueba si no está disponible."""
    if not os.environ.get("NEO4J_PASSWORD"):
        pytest.skip("NEO4J_PASSWORD no está definida en el entorno")
    store = GraphStore.from_env()
    try:
        await store.verify()
    except (ServiceUnavailable, Neo4jError, OSError) as error:
        await store.close()
        pytest.skip(f"Neo4j no disponible en {store.uri}: {error}")
    yield store
    await store.close()


@pytest.mark.integration
async def test_apply_schema_twice_does_not_fail(graph):
    """Aplicar el esquema dos veces no lanza errores (idempotencia)."""
    await graph.apply_schema()
    await graph.apply_schema()


@pytest.mark.integration
async def test_schema_is_listed_by_neo4j(graph):
    """Tras aplicar el esquema, SHOW CONSTRAINTS / SHOW INDEXES listan lo esperado."""
    await graph.apply_schema()

    assert EXPECTED_CONSTRAINTS <= await graph.constraint_names()
    assert EXPECTED_INDEXES <= await graph.index_names()


@pytest.mark.integration
async def test_uniqueness_is_per_entity(graph):
    """El mismo id puede existir en dos entidades, pero no dos veces en la misma."""
    await graph.apply_schema()
    create = "CREATE (:Episode {entity_id: $entity_id, id: 'ep-1'})"
    cleanup = "MATCH (n:Episode) WHERE n.entity_id STARTS WITH 'test_cp4_' DETACH DELETE n"
    try:
        await graph.execute(create, entity_id="test_cp4_a")
        await graph.execute(create, entity_id="test_cp4_b")
        with pytest.raises(Neo4jError):
            await graph.execute(create, entity_id="test_cp4_a")
    finally:
        await graph.execute(cleanup)
