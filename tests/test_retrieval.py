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


# ------------------------------------------------------------ prompt (CP7 C)

from ebica.llm.prompt_assembler import (  # noqa: E402
    DIALOGUE_MEMORY_MAX_CHARS,
    FACTS_HEADER,
    FEELINGS_HEADER,
    MEMORIES_HEADER,
    MEMORIES_NOTE,
    build_dialogue_messages,
    build_memory_sections,
    describe_tone,
    describe_when,
)
from ebica.core.state import EntityConfig  # noqa: E402
from ebica.memory.retrieval import RetrievalResult, RetrievedFact  # noqa: E402


def retrieval_with(episodes=(), facts=()) -> RetrievalResult:
    """Un resultado de recuperación armado a mano."""
    scored = [score_episode(item, 0.6, NOW, CALM) for item in episodes]
    return RetrievalResult(episodes=scored, facts=list(facts), candidates=scored, k_effective=8)


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (timedelta(minutes=10), "hace un rato"),
        (timedelta(hours=5), "hace unas horas"),
        (timedelta(hours=30), "ayer"),
        (timedelta(days=5), "hace 5 días"),
        (timedelta(days=28), "hace 4 semanas"),
    ],
)
def test_describe_when_recent(delta, expected):
    """El tiempo de un recuerdo, en palabras y sin la hora exacta."""
    assert describe_when(NOW - delta, NOW) == expected


def test_describe_when_old_uses_month_and_year():
    """Lo lejano se dice por mes y año («en noviembre de 2025»)."""
    assert describe_when(datetime(2025, 11, 29, tzinfo=timezone.utc), NOW) == "en noviembre de 2025"


def test_describe_tone_by_valence():
    """El tono sale de la valencia guardada; cerca de 0 no se dice nada."""
    assert describe_tone(-0.75) == "lo recuerdo con dolor"
    assert describe_tone(-0.3) == "lo recuerdo con incomodidad"
    assert describe_tone(0.0) == ""
    assert describe_tone(0.7) == "lo recuerdo con mucha alegría"


def test_memory_sections_text():
    """Sección 4 con encabezado, nota, cuándo y tono; sección 5 con los hechos; el diálogo largo se recorta."""
    long_dialogue = candidate("x" * (DIALOGUE_MEMORY_MAX_CHARS + 100), vec(a0=1), ts=NOW - timedelta(days=2))
    seed = EpisodeCandidate(
        id="ep-critica", kind="seed", ts=datetime(2025, 7, 12, tzinfo=timezone.utc),
        text="Un amigo de la Su criticó mi obra. " * 20, valence=-0.75, arousal=0.75, importance=0.8,
        embedding=vec(a1=1),
    )
    text = build_memory_sections(
        retrieval_with([long_dialogue, seed], [RetrievedFact("f-004", "Soy Piscis.", 0.55)]), NOW
    )

    assert text.startswith(f"{MEMORIES_HEADER}\n{MEMORIES_NOTE}\n- Hace 2 días: ")
    assert "x" * DIALOGUE_MEMORY_MAX_CHARS + "…" in text and "x" * (DIALOGUE_MEMORY_MAX_CHARS + 1) not in text
    assert "- En julio de 2025: Un amigo de la Su" in text and "(lo recuerdo con dolor)" in text
    assert text.count("criticó mi obra") == 20  # la semilla va completa
    assert text.endswith(f"{FACTS_HEADER}\n- Soy Piscis.")


def test_memory_sections_say_everything_they_receive():
    """CP9: el tope de D1-50 ya no existe; qué entra lo decide la WorkingMemory, aquí no se descarta nada."""
    episodes = [
        EpisodeCandidate(id=f"ep-{i}", kind="seed", ts=NOW, text=f"recuerdo{i} " + "palabra " * 150,
                         valence=0.0, arousal=0.5, importance=0.5, embedding=vec(a0=1))
        for i in range(10)
    ]
    text = build_memory_sections(retrieval_with(episodes), NOW)

    assert all(f"recuerdo{i} " in text for i in range(10))


def test_nothing_retrieved_adds_nothing():
    """Sin recuperación o sin resultados, el prompt no cambia."""
    config = EntityConfig(id="aurora", name="Aurora", persona="Soy reservada.", ego_ideal=["No miento."])

    assert build_memory_sections(None, NOW) == build_memory_sections(retrieval_with(), NOW) == ""
    assert build_dialogue_messages(config, "hola", CALM, {}, (), memories="") == build_dialogue_messages(
        config, "hola", CALM, {}, ()
    )


def test_memories_go_after_feelings_in_the_system_prompt():
    """§5.13: las secciones 4–5 van después de «Cómo me siento» y antes de la conversación."""
    config = EntityConfig(id="aurora", name="Aurora", persona="Soy reservada.", ego_ideal=["No miento."])
    memories = build_memory_sections(retrieval_with(facts=[RetrievedFact("f-1", "Restauro muebles.", 0.6)]), NOW)

    system = build_dialogue_messages(config, "hola", CALM, {}, (), memories=memories)[0]["content"]

    assert system.index(FEELINGS_HEADER) < system.index(FACTS_HEADER)
    assert system.endswith("- Restauro muebles.")
