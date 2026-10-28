"""
Pruebas de la recuperación híbrida (Fase 1, CP7 parte B).

Las funciones puras se prueban sin Neo4j. Las de integración escriben nodos
con vectores construidos a mano (pocos ejes), para controlar exactamente el
parecido; usan entidades `test_cp7_`, que se borran al terminar.
"""

import math
import os
from datetime import datetime, timedelta, timezone

import pytest
from neo4j.exceptions import ServiceUnavailable

from ebica.affect.vad import VAD
from ebica.memory.graph import GraphStore
from ebica.memory.retrieval import (
    FACTS_MAX,
    RECENCY_HALF_LIFE_SECONDS,
    EpisodeCandidate,
    MemoryRetriever,
    cosine,
    effective_k,
    lability_increment,
    mmr,
    mood_congruence,
    recency,
    score_episode,
)

DIMENSION = 1024
TEST_PREFIX = "test_cp7_"
NOW = datetime(2026, 10, 27, 15, 0, tzinfo=timezone.utc)
CALM = VAD(valence=0.0, arousal=0.45, dominance=0.5)


def vec(**axes: float) -> list[float]:
    """Vector de norma 1 con peso en los ejes indicados (`a0=1, a3=0.5` → ejes 0 y 3)."""
    values = [0.0] * DIMENSION
    for name, weight in axes.items():
        values[int(name[1:])] = weight
    norm = math.sqrt(sum(v * v for v in values))
    return [v / norm for v in values]


def candidate(id_: str, embedding, valence=0.0, importance=0.0, ts=NOW) -> EpisodeCandidate:
    """Un candidato con valores por defecto."""
    return EpisodeCandidate(
        id=id_, kind="dialogue", ts=ts, text=id_, valence=valence, arousal=0.5,
        importance=importance, embedding=embedding,
    )


# ------------------------------------------------------------ funciones puras


def test_recency_halves_every_half_life():
    """Ahora vale 1; tras una vida media (3 días), 0,5; tras dos, 0,25."""
    half = timedelta(seconds=RECENCY_HALF_LIFE_SECONDS)

    assert recency(NOW, NOW) == pytest.approx(1.0)
    assert recency(NOW - half, NOW) == pytest.approx(0.5)
    assert recency(NOW - 2 * half, NOW) == pytest.approx(0.25)


def test_mood_congruence_range():
    """Misma valencia → 1; opuestos extremos → 0."""
    assert mood_congruence(-0.6, -0.6) == pytest.approx(1.0)
    assert mood_congruence(-1.0, 1.0) == pytest.approx(0.0)
    assert mood_congruence(0.0, 0.5) == pytest.approx(0.75)


def test_effective_k_follows_the_mood():
    """D1-47: Calisto (k 8) recuerda 4 bajo amenaza, 9 de buen ánimo y 8 en calma; nunca menos de 2."""
    assert effective_k(8, VAD(valence=-0.4, arousal=0.8)) == 4
    assert effective_k(8, VAD(valence=0.5, arousal=0.5)) == 9
    assert effective_k(8, CALM) == 8
    assert effective_k(3, VAD(valence=-0.9, arousal=1.0)) == 2


def test_lability_increment_grows_with_discrepancy():
    """D1-48: 0,1 si el afecto coincide; hasta 0,3 si es opuesto."""
    assert lability_increment(0.5, 0.5) == pytest.approx(0.1)
    assert lability_increment(-1.0, 1.0) == pytest.approx(0.3)


def test_negative_mood_prefers_the_negative_memory():
    """Con la misma similitud, triste, gana el recuerdo triste (congruencia con el ánimo)."""
    sad, happy = candidate("triste", vec(a0=1), valence=-0.7), candidate("alegre", vec(a0=1), valence=0.7)
    low = VAD(valence=-0.6, arousal=0.4)

    assert score_episode(sad, 0.6, NOW, low).total > score_episode(happy, 0.6, NOW, low).total
    assert score_episode(happy, 0.6, NOW, VAD(valence=0.6)).total > score_episode(sad, 0.6, NOW, VAD(valence=0.6)).total


def test_mmr_avoids_near_duplicates():
    """Dos versiones casi iguales del mismo recuerdo no entran juntas si hay otro distinto."""
    duplicate_a = score_episode(candidate("perro-1", vec(a0=1)), 0.80, NOW, CALM)
    duplicate_b = score_episode(candidate("perro-2", vec(a0=1, a1=0.05)), 0.79, NOW, CALM)
    different = score_episode(candidate("banco", vec(a2=1)), 0.60, NOW, CALM)

    chosen = mmr([duplicate_a, duplicate_b, different], k=2, lambda_mmr=0.32)

    assert [item.candidate.id for item in chosen] == ["perro-1", "banco"]


def test_mmr_with_high_lambda_keeps_relevance():
    """Con λ alto (apertura baja) manda la relevancia, aunque se repita."""
    duplicate_a = score_episode(candidate("perro-1", vec(a0=1)), 0.80, NOW, CALM)
    duplicate_b = score_episode(candidate("perro-2", vec(a0=1, a1=0.05)), 0.79, NOW, CALM)
    different = score_episode(candidate("banco", vec(a2=1)), 0.30, NOW, CALM)

    chosen = mmr([duplicate_a, duplicate_b, different], k=2, lambda_mmr=0.95)

    assert [item.candidate.id for item in chosen] == ["perro-1", "perro-2"]


def test_cosine_of_built_vectors():
    """Los vectores de prueba tienen el coseno esperado."""
    assert cosine(vec(a0=1), vec(a0=1)) == pytest.approx(1.0)
    assert cosine(vec(a0=1), vec(a1=1)) == pytest.approx(0.0)
    assert cosine(vec(a0=1), vec(a0=1, a1=1)) == pytest.approx(1 / math.sqrt(2))


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


async def add_episode(graph, entity_id, id_, embedding, *, kind="dialogue", ts=NOW - timedelta(days=1),
                      valence=0.0, importance=0.3, access="open", topics=()):
    """Escribe un episodio con un vector dado (y sus temas)."""
    await graph.execute(
        "CREATE (e:Episode {entity_id: $e, id: $id, kind: $kind, ts: $ts, text: $id, summary: $id, "
        "embedding: $emb, valence: $v, arousal: 0.5, dominance: 0.5, importance: $imp, "
        "lability: 0.0, access: $access, version: 1}) "
        "FOREACH (name IN $topics | MERGE (t:Topic {entity_id: $e, name: name}) MERGE (e)-[:ABOUT]->(t))",
        e=entity_id, id=id_, kind=kind, ts=ts, emb=embedding, v=valence, imp=importance,
        access=access, topics=list(topics),
    )


async def add_fact(graph, entity_id, id_, embedding):
    """Escribe un hecho de la semilla con un vector dado."""
    await graph.execute(
        "CREATE (:Fact {entity_id: $e, id: $id, text: $id, embedding: $emb, domain: 'self', source: 'seed'})",
        e=entity_id, id=id_, emb=embedding,
    )


async def retrieve(graph, entity_id, query, **values):
    """Recupera con valores por defecto (los índices tardan un instante en ver nodos nuevos)."""
    import asyncio

    defaults = {"affect": CALM, "k": 8, "lambda_mmr": 0.32, "now": NOW, "raise_lability": False}
    defaults.update(values)
    result = None
    for _ in range(30):
        result = await MemoryRetriever(graph).retrieve(entity_id, query, **defaults)
        if result.candidates or result.facts:
            return result
        await asyncio.sleep(0.1)
    return result


@pytest.mark.integration
async def test_retrieves_the_similar_episode_and_ignores_unrelated(graph):
    """Entra el episodio parecido; uno sin relación queda bajo el umbral; los de otra entidad no se ven."""
    a, b = f"{TEST_PREFIX}a", f"{TEST_PREFIX}b"
    await add_episode(graph, a, "ep-perro", vec(a0=1, a1=0.3))
    await add_episode(graph, a, "ep-playa", vec(a5=1))
    await add_episode(graph, b, "ep-clon", vec(a0=1))

    result = await retrieve(graph, a, vec(a0=1))

    assert [item.candidate.id for item in result.episodes] == ["ep-perro"]
    assert "ep-playa" not in {item.candidate.id for item in result.candidates}


@pytest.mark.integration
async def test_exclusions(graph):
    """D1-46: fuera lo bloqueado, el diálogo ya presente en la conversación reciente y los hechos esenciales."""
    a = f"{TEST_PREFIX}a"
    await add_episode(graph, a, "ep-viejo", vec(a0=1), ts=NOW - timedelta(days=2))
    await add_episode(graph, a, "ep-reciente", vec(a0=1), ts=NOW - timedelta(minutes=5))
    await add_episode(graph, a, "ep-semilla", vec(a0=1), kind="seed", ts=NOW - timedelta(minutes=1))
    await add_episode(graph, a, "ep-bloqueado", vec(a0=1), access="blocked")
    await add_fact(graph, a, "f-core", vec(a0=1))
    await add_fact(graph, a, "f-otro", vec(a0=1, a1=0.2))

    result = await retrieve(graph, a, vec(a0=1), since=NOW - timedelta(minutes=10), excluded_fact_ids=["f-core"])

    assert {item.candidate.id for item in result.episodes} == {"ep-viejo", "ep-semilla"}
    assert [fact.id for fact in result.facts] == ["f-otro"]


@pytest.mark.integration
async def test_topic_neighbours_join_the_candidates(graph):
    """Un episodio sobre un tema activo entra como candidato aunque no esté entre los vecinos vectoriales."""
    a = f"{TEST_PREFIX}a"
    await add_episode(graph, a, "ep-tema", vec(a0=1, a1=1), topics=["perro"])

    result = await retrieve(graph, a, vec(a0=1), topics=["perro"])

    [item] = result.candidates
    assert item.candidate.sources == {"vector", "topic"}


@pytest.mark.integration
async def test_facts_are_capped_and_k_follows_the_mood(graph):
    """Como máximo FACTS_MAX hechos; bajo amenaza entran menos episodios."""
    a = f"{TEST_PREFIX}a"
    for index in range(6):
        await add_fact(graph, a, f"f-{index}", vec(a0=1, **{f"a{index + 1}": 0.3}))
        await add_episode(graph, a, f"ep-{index}", vec(a0=1, **{f"a{index + 10}": 0.5}))

    calm = await retrieve(graph, a, vec(a0=1), k=4)
    threat = await retrieve(graph, a, vec(a0=1), k=4, affect=VAD(valence=-0.5, arousal=0.9))

    assert len(calm.facts) == FACTS_MAX
    assert len(calm.episodes) == 4 and calm.k_effective == 4
    assert len(threat.episodes) == 2 and threat.k_effective == 2


@pytest.mark.integration
async def test_evoking_raises_lability_only_when_asked(graph):
    """D1-48: lo evocado sube su labilidad y guarda cuándo; con raise_lability=False no se escribe nada."""
    a = f"{TEST_PREFIX}a"
    await add_episode(graph, a, "ep-triste", vec(a0=1), valence=-0.8)

    await retrieve(graph, a, vec(a0=1), raise_lability=False)
    untouched = await graph.execute("MATCH (e:Episode {entity_id: $e}) RETURN e.lability AS l", e=a)
    await retrieve(graph, a, vec(a0=1), raise_lability=True, affect=VAD(valence=0.6, arousal=0.4))
    raised = await graph.execute(
        "MATCH (e:Episode {entity_id: $e}) RETURN e.lability AS l, e.last_evoked_at IS NOT NULL AS evoked", e=a
    )

    assert untouched == [{"l": 0.0}]
    assert raised[0]["l"] == pytest.approx(lability_increment(-0.8, 0.6))
    assert raised[0]["evoked"]
