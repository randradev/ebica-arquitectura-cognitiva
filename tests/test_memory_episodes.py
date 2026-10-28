"""
Pruebas de la escritura de memoria (Fase 1, CP6 parte B).

Las funciones puras se prueban sin Neo4j. Las de integración necesitan Neo4j
encendido y `NEO4J_PASSWORD`; si no, se omiten con un aviso. Usan entidades
temporales con el prefijo `test_cp6_`, que se borran al terminar, y un
embedder simulado de la dimensión real (1024).
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from neo4j.exceptions import ServiceUnavailable

from ebica.affect.vad import VAD
from ebica.core.events import EventBus
from ebica.entities.manager import EntityManager
from ebica.identity.biography import SeedBiography
from ebica.memory.episodes import (
    MAX_TOPICS_PER_EPISODE,
    RESPONSE_MAX_CHARS,
    MemoryWriter,
    content_hash,
    episode_importance,
    episode_text,
    normalize_topic,
    normalize_topics,
)
from ebica.memory.graph import GraphStore
from ebica.perception.appraisal import neutral_appraisal
from fake_embedder import FakeEmbedder

DIMENSION = 1024
TEST_PREFIX = "test_cp6_"
REPO_ENTITIES = Path(__file__).resolve().parent.parent / "entities"
NOW = datetime(2026, 10, 27, 15, 0, tzinfo=timezone.utc)


def appraisal(**values):
    """Un appraisal neutro con los campos indicados cambiados."""
    return neutral_appraisal().model_copy(update=values)


def biography(**changes) -> SeedBiography:
    """Biografía mínima: dos hechos y dos episodios (el segundo, el más reciente)."""
    data = {
        "facts": [{"id": "f-1", "text": "Restauro muebles."}, {"id": "f-2", "text": "Tengo una gata."}],
        "episodes": [
            {"id": "ep-taller", "ts": "2025-05-01T10:00:00-04:00", "text": "Abrí el taller.",
             "valence": 0.6, "arousal": 0.5, "dominance": 0.6, "importance": 0.5},
            {"id": "ep-origen", "ts": "2026-03-14T23:00:00-03:00", "text": "Una luz y un ruido.",
             "valence": -0.6, "arousal": 0.8, "dominance": 0.1, "importance": 0.9},
        ],
    }
    data.update(changes)
    return SeedBiography.model_validate(data)


# ------------------------------------------------------------ funciones puras


def test_episode_text_is_first_person_and_truncates_only_the_response():
    """D1-35: el recuerdo guarda el mensaje completo y la respuesta recortada."""
    long_reply = "a" * (RESPONSE_MAX_CHARS + 50)

    text = episode_text("  Adopté un perro, Toby.  ", long_reply)

    assert text.startswith("Me dijeron: «Adopté un perro, Toby.»\nRespondí: «")
    assert text.endswith("…»")
    assert text.count("a") == RESPONSE_MAX_CHARS
    assert episode_text("eh", long_reply, limit=None).count("a") == RESPONSE_MAX_CHARS + 50


def test_importance_examples_and_range():
    """D1-36: un saludo pesa poco, un insulto mucho, y nunca sale de [0, 1]."""
    greeting = appraisal(self_relevance=0.2, goal_congruence=0.2)
    insult = appraisal(self_relevance=0.8, goal_congruence=-1.0, hostility=0.9)
    extreme = appraisal(self_relevance=1.0, goal_congruence=1.0, hostility=1.0, distress=1.0)

    assert episode_importance(greeting) == pytest.approx(0.14)
    assert episode_importance(insult) == pytest.approx(0.89)
    assert episode_importance(extreme) == pytest.approx(1.0)
    assert episode_importance(neutral_appraisal()) == 0.0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Música", "musica"),
        ("  Los   Pianos ", "los piano"),
        ("canciones", "cancion"),
        ("Gatas", "gata"),
        ("crisis", "crisis"),
        ("series", "series"),
        ("padres", "padres"),
        ("Año nuevo", "año nuevo"),
        # D1-68: una palabra con la última vocal acentuada no es un plural.
        ("Adiós", "adios"),
        ("compás", "compas"),
        ("teléfonos", "telefono"),
    ],
)
def test_normalize_topic(raw, expected):
    """Minúsculas, sin tildes (la ñ se conserva) y un singular conservador."""
    assert normalize_topic(raw) == expected


def test_normalize_topics_deduplicates_and_caps():
    """Variantes del mismo tema se fusionan, los vacíos se descartan y hay un tope."""
    topics = normalize_topics(["Perros", "perro", " ", "arte", "música", "cine", "política", "tarot"])

    assert topics[:2] == ["perro", "arte"]
    assert len(topics) == MAX_TOPICS_PER_EPISODE


def test_content_hash_changes_with_content():
    """La huella cambia si cambia el contenido y es estable si no."""
    assert content_hash("a", 0.5) == content_hash("a", 0.5)
    assert content_hash("a", 0.5) != content_hash("b", 0.5)


# ------------------------------------------------------------ integración


@pytest.fixture
async def graph():
    """Neo4j con el esquema aplicado; borra las entidades de prueba al terminar."""
    if not os.environ.get("NEO4J_PASSWORD"):
        pytest.skip("NEO4J_PASSWORD no está definida en el entorno")
    store = GraphStore.from_env()
    try:
        await store.verify()
    except (ServiceUnavailable, OSError) as error:
        await store.close()
        pytest.skip(f"Neo4j no disponible en {store.uri}: {error}")
    await store.apply_schema(DIMENSION)
    yield store
    await store.execute(
        "MATCH (n) WHERE n.entity_id STARTS WITH $prefix DETACH DELETE n", prefix=TEST_PREFIX
    )
    await store.close()


@pytest.fixture
def writer(graph):
    """Escritor con un embedder simulado de la dimensión real."""
    return MemoryWriter(graph, FakeEmbedder(dimension=DIMENSION))


async def count(graph, pattern: str, **params) -> int:
    """Cuenta las filas de un patrón Cypher (`MATCH <pattern> RETURN count(*)`)."""
    rows = await graph.execute(f"MATCH {pattern} RETURN count(*) AS c", **params)
    return rows[0]["c"]


async def write(writer, entity_id: str, ts: datetime = NOW, **values):
    """Escribe un turno de prueba con valores por defecto."""
    return await writer.write_turn(
        entity_id, ts=ts, user_text=values.pop("user_text", "Adopté un perro, se llama Toby."),
        entity_text=values.pop("entity_text", "¡Qué buena! ¿De qué raza es?"),
        affect=VAD(valence=0.2, arousal=0.5, dominance=0.5),
        appraisal=values.pop("appraisal", appraisal(topics=["Perros", "adopción"], self_relevance=0.3)),
        **values,
    )


@pytest.mark.integration
async def test_seed_import_is_idempotent(graph, writer):
    """Importar dos veces no duplica: un Self, los hechos, los episodios con su huella y la cadena NEXT."""
    entity_id = f"{TEST_PREFIX}a"

    first = await writer.import_seed(entity_id, "Aurora", biography())
    second = await writer.import_seed(entity_id, "Aurora", biography())

    assert sorted(first.created) == ["ep-origen", "ep-taller", "f-1", "f-2"]
    assert second.created == [] and second.updated == [] and second.unchanged == 4
    params = {"e": entity_id}
    assert await count(graph, "(:Self {entity_id: $e})", **params) == 1
    assert await count(graph, "(:Fact {entity_id: $e, domain: 'self', source: 'seed'})", **params) == 2
    assert await count(graph, "(:Episode {entity_id: $e, kind: 'seed'})-[:DERIVED_FROM]->(:Trace)", **params) == 2
    chain = await graph.execute(
        "MATCH (a:Episode {entity_id: $e})-[:NEXT]->(b:Episode) RETURN a.id AS a, b.id AS b", **params
    )
    assert chain == [{"a": "ep-taller", "b": "ep-origen"}]


@pytest.mark.integration
async def test_seed_import_updates_changed_and_reports_orphans(graph, writer):
    """D1-39: un hecho editado se actualiza con su embedding; uno quitado se informa y no se borra."""
    entity_id = f"{TEST_PREFIX}a"
    await writer.import_seed(entity_id, "Aurora", biography())
    edited = biography(facts=[{"id": "f-1", "text": "Restauro muebles antiguos."}])

    report = await writer.import_seed(entity_id, "Aurora", edited)

    assert report.updated == ["f-1"] and report.orphaned == ["f-2"]
    rows = await graph.execute(
        "MATCH (f:Fact {entity_id: $e, id: 'f-1'}) RETURN f.text AS text, f.embedding AS embedding",
        e=entity_id,
    )
    assert rows[0]["text"] == "Restauro muebles antiguos."
    assert rows[0]["embedding"] == pytest.approx(FakeEmbedder(DIMENSION).vector("Restauro muebles antiguos."))
    assert await count(graph, "(:Fact {entity_id: $e, id: 'f-2'})", e=entity_id) == 1


@pytest.mark.integration
async def test_turn_writes_one_episode_with_trace_links_and_topics(graph, writer):
    """Un turno crea exactamente un Episode y una Trace, enlazados, después del último recuerdo."""
    entity_id = f"{TEST_PREFIX}a"
    await writer.import_seed(entity_id, "Aurora", biography())
    long_reply = "Me encantan los perros. " * 40

    written = await write(writer, entity_id, entity_text=long_reply, impulsive=True)

    assert written.previous_episode_id == "ep-origen"
    assert written.topics == ["perro", "adopcion"] and written.new_topics == written.topics
    params = {"e": entity_id, "id": written.episode_id}
    assert await count(graph, "(:Episode {entity_id: $e, kind: 'dialogue'})", **params) == 1
    rows = await graph.execute(
        "MATCH (ep:Episode {entity_id: $e, id: $id})-[:DERIVED_FROM]->(t:Trace) "
        "RETURN ep.text AS text, ep.lability AS lability, ep.version AS version, ep.access AS access, "
        "t.raw_text AS raw, t.route AS route, t.appraisal_json AS appraisal",
        **params,
    )
    [row] = rows
    assert len(row["text"]) < len(row["raw"])  # el recuerdo recorta, la huella no
    assert long_reply.strip() in row["raw"]
    assert (row["lability"], row["version"], row["access"], row["route"]) == (0.0, 1, "open", "impulsive")
    assert '"self_relevance":0.3' in row["appraisal"]
    assert await count(graph, "(:Episode {entity_id: $e, id: 'ep-origen'})-[:NEXT]->(:Episode {id: $id})", **params) == 1
    assert await count(graph, "(:Episode {entity_id: $e, id: $id})-[:ABOUT]->(:Topic)", **params) == 2


@pytest.mark.integration
async def test_second_turn_chains_and_reuses_topics(graph, writer):
    """El segundo turno sigue al primero; un tema repetido no se duplica y suma una aparición."""
    entity_id = f"{TEST_PREFIX}a"
    first = await write(writer, entity_id)

    second = await write(writer, entity_id, ts=NOW + timedelta(minutes=1),
                         appraisal=appraisal(topics=["perro"]))

    assert first.previous_episode_id is None  # sin semilla, el primero no tiene anterior
    assert second.previous_episode_id == first.episode_id and second.new_topics == []
    rows = await graph.execute("MATCH (t:Topic {entity_id: $e, name: 'perro'}) RETURN t.n AS n", e=entity_id)
    assert rows == [{"n": 2}]


@pytest.mark.integration
async def test_entities_do_not_cross(graph, writer):
    """Dos entidades con los mismos ids y temas no comparten nodos (§7.1)."""
    a, b = f"{TEST_PREFIX}a", f"{TEST_PREFIX}b"
    await writer.import_seed(a, "Aurora", biography())
    await writer.import_seed(b, "Bruna", biography())

    written = await write(writer, a)

    assert written.previous_episode_id == "ep-origen"
    assert await count(graph, "(:Episode {entity_id: $e})", e=a) == 3
    assert await count(graph, "(:Episode {entity_id: $e})", e=b) == 2
    assert await count(graph, "(:Topic {entity_id: $e})", e=b) == 0
    crossed = await count(
        graph, "(x {entity_id: $a})-[]-(y) WHERE y.entity_id <> $a", a=a
    )
    assert crossed == 0


@pytest.mark.integration
async def test_written_episode_is_found_by_vector_search(graph, writer):
    """El episodio escrito entra al índice vectorial y es el vecino de una consulta parecida."""
    entity_id = f"{TEST_PREFIX}a"
    await writer.import_seed(entity_id, "Aurora", biography())
    written = await write(writer, entity_id)
    [query] = await writer.embedder.embed(["¿cómo está Toby, tu perro?"], "query")

    found = []
    # El índice incorpora los nodos nuevos con un pequeño retraso (ver test_graph.py).
    for _ in range(30):
        found = await graph.vector_search("Episode", entity_id, query, k=1)
        if found and found[0]["id"] == written.episode_id:
            break
        await asyncio.sleep(0.1)
    assert found[0]["id"] == written.episode_id


@pytest.mark.integration
async def test_wrong_dimension_writes_nothing(graph):
    """Un vector de otra dimensión se rechaza antes de escribir: no queda ningún nodo."""
    entity_id = f"{TEST_PREFIX}a"

    class WrongEmbedder(FakeEmbedder):
        """Dice tener la dimensión del índice, pero devuelve vectores más cortos."""

        async def embed(self, texts, kind):
            """Vectores de dimensión 16."""
            return [FakeEmbedder(16).vector(text) for text in texts]

    writer = MemoryWriter(graph, WrongEmbedder(dimension=DIMENSION))

    with pytest.raises(ValueError, match="dimensión"):
        await write(writer, entity_id)
    with pytest.raises(ValueError, match="dimensión"):
        await writer.import_seed(entity_id, "Aurora", biography())
    assert await count(graph, "(n {entity_id: $e})", e=entity_id) == 0


@pytest.mark.integration
async def test_calisto_seed_imports(graph, writer):
    """La semilla real de Calisto (63 hechos, 6 episodios) se importa completa en una entidad de prueba."""
    config = EntityManager(REPO_ENTITIES, EventBus()).read_config("calisto")
    entity_id = f"{TEST_PREFIX}calisto"

    report = await writer.import_seed(entity_id, config.name, config.seed_biography)

    assert len(report.created) == 63 + 6
    assert await count(graph, "(:Fact {entity_id: $e})", e=entity_id) == 63
    last = await graph.execute(
        "MATCH (e:Episode {entity_id: $e}) WHERE NOT (e)-[:NEXT]->() RETURN e.id AS id", e=entity_id
    )
    assert last == [{"id": "ep-origen"}]
