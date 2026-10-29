"""
Pruebas de los compromisos en la memoria (Fase 1, CP10 parte B).

Las funciones puras se prueban sin Neo4j. Las de integración necesitan Neo4j
encendido y `NEO4J_PASSWORD`; usan entidades temporales con el prefijo
`test_cp10_`, que se borran al terminar.
"""

import asyncio
import math
import os
from datetime import datetime, timedelta, timezone

import pytest
from neo4j.exceptions import ServiceUnavailable

from ebica.affect.vad import VAD
from ebica.identity.biography import PrimaryPerson
from ebica.memory.episodes import MemoryWriter, commitment_id, commitment_key
from ebica.memory.graph import GraphStore
from ebica.memory.people import PeopleStore
from ebica.memory.retrieval import W_COMMITMENT, EpisodeCandidate, MemoryRetriever, score_episode
from ebica.perception.appraisal import neutral_appraisal
from ebica.social.partner import PartnerModel
from fake_embedder import FakeEmbedder

DIMENSION = 1024
TEST_PREFIX = "test_cp10_"
NOW = datetime(2026, 10, 28, 20, 0, tzinfo=timezone.utc)
CALM = VAD(valence=0.0, arousal=0.5, dominance=0.5)
RICARDO = PartnerModel.for_primary(PrimaryPerson(id="ricardo", name="Ricardo", trust=0.4))


# ------------------------------------------------------------ funciones puras


def test_commitment_key_ignores_case_accents_and_punctuation():
    """D1-73: la misma promesa escrita distinto da la misma clave."""
    assert commitment_key("  Mañana te cuento CÓMO me fue. ") == "manana te cuento como me fue"
    assert commitment_key("mañana te cuento como me fue") == commitment_key("Mañana te cuento cómo me fue!!")


def test_commitment_id_depends_on_person_and_promise():
    """El id es estable para la misma persona y la misma promesa, y distinto entre personas."""
    assert commitment_id("ricardo", "Te cuento mañana") == commitment_id("ricardo", "te cuento mañana.")
    assert commitment_id("ricardo", "Te cuento mañana") != commitment_id("ana", "Te cuento mañana")
    assert commitment_id("ricardo", "Te cuento mañana").startswith("cm-")


def test_open_commitment_adds_the_weighted_term():
    """§7.3: un episodio sobre un compromiso abierto suma W_COMMITMENT · w_commit; sin compromiso, nada."""
    base = dict(id="ep", kind="dialogue", ts=NOW, text="x", valence=0.0, arousal=0.5, importance=0.0, embedding=[1.0])
    plain = score_episode(EpisodeCandidate(**base), 0.6, NOW, CALM, w_commit=0.8)
    promised = score_episode(EpisodeCandidate(**base, open_commitment=True), 0.6, NOW, CALM, w_commit=0.8)

    assert plain.commitment == 0.0
    assert promised.commitment == 0.8
    assert promised.total - plain.total == pytest.approx(W_COMMITMENT * 0.8)


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
    await store.execute("MATCH (n) WHERE n.entity_id STARTS WITH $prefix DETACH DELETE n", prefix=TEST_PREFIX)
    await store.close()


@pytest.fixture
def writer(graph):
    """Escritor con un embedder simulado de la dimensión real."""
    return MemoryWriter(graph, FakeEmbedder(dimension=DIMENSION))


async def count(graph, pattern: str, **params) -> int:
    """Cuenta las filas de un patrón Cypher (`MATCH <pattern> RETURN count(*)`)."""
    rows = await graph.execute(f"MATCH {pattern} RETURN count(*) AS c", **params)
    return rows[0]["c"]


async def promise(writer, entity_id, text, commitments, ts=NOW, person=RICARDO):
    """Un turno en el que la persona promete algo (el appraisal trae `commitments`)."""
    return await writer.write_turn(
        entity_id, ts=ts, user_text=text, entity_text="Dale, te espero.", affect=CALM,
        appraisal=neutral_appraisal().model_copy(update={"commitments": commitments}), person=person,
    )


@pytest.mark.integration
async def test_promise_creates_an_open_commitment_with_its_links(graph, writer):
    """«Mañana te cuento cómo me fue» crea un Commitment abierto, PROMISED desde Ricardo y ABOUT desde el episodio."""
    entity_id = f"{TEST_PREFIX}a"

    written = await promise(writer, entity_id, "Mañana tengo la entrevista, te cuento cómo me fue.",
                            ["contarte cómo me fue en la entrevista"])

    [cid] = written.commitments
    rows = await graph.execute(
        "MATCH (p:Person {entity_id: $e, id: 'ricardo'})-[:PROMISED]->(c:Commitment {entity_id: $e, id: $cid})"
        "<-[:ABOUT]-(ep:Episode {id: $ep}) RETURN c.text AS text, c.status AS status, c.due AS due",
        e=entity_id, cid=cid, ep=written.episode_id,
    )
    assert rows == [{"text": "contarte cómo me fue en la entrevista", "status": "open", "due": None}]
    assert written.as_dict()["commitments"] == [cid]


@pytest.mark.integration
async def test_repeated_promise_is_not_duplicated(graph, writer):
    """La misma promesa (escrita distinto) no se duplica: el episodio nuevo se enlaza a la que ya existe."""
    entity_id = f"{TEST_PREFIX}a"
    first = await promise(writer, entity_id, "Te cuento mañana", ["Contarte cómo me fue."])
    second = await promise(writer, entity_id, "Oye, te cuento mañana sí o sí", ["contarte como me fue"],
                           ts=NOW + timedelta(minutes=5))

    assert first.commitments == second.commitments
    assert await count(graph, "(:Commitment {entity_id: $e})", e=entity_id) == 1
    assert await count(graph, "(:Episode {entity_id: $e})-[:ABOUT]->(:Commitment)", e=entity_id) == 2
    assert await count(graph, "(:Person {entity_id: $e})-[:PROMISED]->(:Commitment)", e=entity_id) == 1


@pytest.mark.integration
async def test_turn_without_person_or_commitments(graph, writer):
    """Sin persona: el compromiso existe pero sin PROMISED. Sin compromisos: nada se crea."""
    entity_id = f"{TEST_PREFIX}a"

    orphan = await promise(writer, entity_id, "Te traigo un dibujo", ["traerte un dibujo"], person=None)
    nothing = await promise(writer, entity_id, "Hola", [], ts=NOW + timedelta(minutes=1))

    assert len(orphan.commitments) == 1 and nothing.commitments == []
    assert await count(graph, "(:Commitment {entity_id: $e})", e=entity_id) == 1
    assert await count(graph, "()-[:PROMISED]->(:Commitment {entity_id: $e})", e=entity_id) == 0


@pytest.mark.integration
async def test_open_commitments_of_a_person_and_entity_isolation(graph, writer):
    """`open_commitments` trae solo las promesas abiertas de esa persona y de esa entidad."""
    a, b = f"{TEST_PREFIX}a", f"{TEST_PREFIX}b"
    ana = PartnerModel(id="ana", name="Ana")
    await promise(writer, a, "Te cuento mañana", ["contarte cómo me fue"])
    await promise(writer, a, "Te traigo un libro", ["traerte un libro"], ts=NOW + timedelta(hours=1))
    await promise(writer, a, "Te mando la foto", ["mandarte la foto de Mora"], person=ana)
    await promise(writer, b, "Te cuento mañana", ["contarte cómo me fue"])
    await graph.execute("MATCH (c:Commitment {entity_id: $e, text: 'traerte un libro'}) SET c.status = 'done'", e=a)

    people = PeopleStore(graph)
    ricardo_open = await people.open_commitments(a, "ricardo")

    assert [c["text"] for c in ricardo_open] == ["contarte cómo me fue"]
    assert ricardo_open[0]["ts"] == NOW
    assert [c["text"] for c in await people.open_commitments(a, "ana")] == ["mandarte la foto de Mora"]
    assert await count(graph, "(:Commitment {entity_id: $e})", e=b) == 1
    crossed = await count(graph, "(x {entity_id: $a})-[]-(y) WHERE y.entity_id <> $a", a=a)
    assert crossed == 0


@pytest.mark.integration
async def test_promise_episode_rises_in_retrieval(graph):
    """§7.3: con el mismo parecido, el episodio sobre un compromiso abierto gana por W_COMMITMENT · w_commit."""
    entity_id = f"{TEST_PREFIX}a"
    vector = [0.0] * DIMENSION
    vector[0] = 1.0
    for id_ in ("ep-promesa", "ep-normal"):
        await graph.execute(
            "CREATE (e:Episode {entity_id: $e, id: $id, kind: 'dialogue', ts: $ts, text: $id, summary: $id, "
            "embedding: $emb, valence: 0.0, arousal: 0.5, dominance: 0.5, importance: 0.3, "
            "lability: 0.0, access: 'open', version: 1})",
            e=entity_id, id=id_, ts=NOW - timedelta(days=1), emb=vector,
        )
    await graph.execute(
        "MATCH (e:Episode {entity_id: $e, id: 'ep-promesa'}) "
        "CREATE (e)-[:ABOUT]->(:Commitment {entity_id: $e, id: 'cm-1', text: 'x', status: 'open'})", e=entity_id,
    )

    result = None
    for _ in range(30):
        result = await MemoryRetriever(graph).retrieve(
            entity_id, vector, affect=CALM, k=8, lambda_mmr=0.9, now=NOW, w_commit=0.8, raise_lability=False,
        )
        if len(result.candidates) == 2:
            break
        await asyncio.sleep(0.1)
    by_id = {item.candidate.id: item for item in result.candidates}

    assert by_id["ep-promesa"].commitment == 0.8 and by_id["ep-normal"].commitment == 0.0
    assert math.isclose(by_id["ep-promesa"].total - by_id["ep-normal"].total, W_COMMITMENT * 0.8, abs_tol=1e-9)
    assert result.episodes[0].candidate.id == "ep-promesa"
