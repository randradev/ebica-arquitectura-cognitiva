"""
Pruebas del PartnerModel y de las personas en la memoria (Fase 1, CP8 parte B).

Las funciones puras se prueban sin Neo4j. Las de integración necesitan Neo4j
encendido y `NEO4J_PASSWORD`; si no, se omiten con un aviso. Usan entidades
temporales con el prefijo `test_cp8_`, que se borran al terminar.
"""

import asyncio
import json
import math
import os
from datetime import datetime, timedelta, timezone

import pytest
from neo4j.exceptions import ServiceUnavailable

from ebica.affect.vad import VAD
from ebica.identity.biography import PrimaryPerson
from ebica.memory.episodes import MemoryWriter, episode_text
from ebica.memory.graph import GraphStore
from ebica.memory.people import PeopleStore
from ebica.memory.retrieval import MemoryRetriever
from ebica.perception.appraisal import UserEmotion, neutral_appraisal
from ebica.social.partner import (
    EMOTION_EMA_ALPHA,
    MAX_TRACKED_TOPICS,
    NEW_PERSON_TRUST,
    DuplicatePersonError,
    PartnerModel,
    PartnerNow,
    new_person_id,
    normalize_name,
    update_partner_model,
)
from fake_embedder import FakeEmbedder

DIMENSION = 1024
TEST_PREFIX = "test_cp8_"
NOW = datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc)
RICARDO = PrimaryPerson(id="ricardo", name="Ricardo", trust=0.4)


def appraisal(valence=0.0, arousal=0.0, **values):
    """Un appraisal neutro con la emoción de quien habla y los campos indicados cambiados."""
    emotion = UserEmotion(valence=valence, arousal=arousal, dominance=0.5)
    return neutral_appraisal().model_copy(update={"user_emotion": emotion, **values})


def now_from(**values) -> PartnerNow:
    """`PartnerNow` de un appraisal de prueba."""
    return PartnerNow.from_appraisal(appraisal(**values))


# ------------------------------------------------------------ funciones puras


def test_partner_now_reads_emotion_intent_and_normalized_focus():
    """`partner_now` sale del appraisal, con los temas normalizados como en la memoria."""
    now = now_from(valence=-0.6, arousal=0.7, user_intent="desahogarse",
                   topics=["Perros", "Trabajo"], distress=0.8)

    assert (now.valence, now.arousal, now.intent) == (-0.6, 0.7, "desahogarse")
    assert now.topics == ["perro", "trabajo"] and now.distress == 0.8


def test_first_turn_sets_the_emotion_and_later_turns_average():
    """D1-54: la primera vez la emoción típica es la observada; después, media móvil con α."""
    model = PartnerModel.for_primary(RICARDO)

    first = update_partner_model(model, now_from(valence=0.6, arousal=0.4), NOW)
    second = update_partner_model(first, now_from(valence=-0.4, arousal=0.4), NOW + timedelta(hours=1))

    assert (first.n, first.valence_mean, first.first_met) == (1, 0.6, NOW)
    assert second.valence_mean == pytest.approx(0.6 + EMOTION_EMA_ALPHA * (-0.4 - 0.6))
    assert second.first_met == NOW and second.last_seen == NOW + timedelta(hours=1)
    assert model.n == 0  # el original no cambia


def test_topics_are_counted_and_sensitive_only_with_distress():
    """Los temas suman apariciones; solo los de un mensaje con angustia alta cuentan como sensibles."""
    model = PartnerModel(id="ana", name="Ana")
    model = update_partner_model(model, now_from(topics=["trabajo", "gato"]), NOW)
    model = update_partner_model(model, now_from(topics=["trabajo"], distress=0.8), NOW)
    model = update_partner_model(model, now_from(topics=["gato"], distress=0.3), NOW)

    assert model.topics == {"trabajo": 2, "gato": 2}
    assert model.top_topics == ["gato", "trabajo"]  # empate: orden alfabético
    assert model.sensitive_topics == {"trabajo": 1}


def test_tracked_topics_are_capped():
    """El modelo no crece sin límite: se guardan los `MAX_TRACKED_TOPICS` más contados."""
    model = PartnerModel(id="ana", name="Ana")
    model = update_partner_model(model, now_from(topics=["perro"]), NOW)
    model = update_partner_model(model, now_from(topics=["perro"]), NOW)
    for index in range(MAX_TRACKED_TOPICS + 5):
        model = update_partner_model(model, now_from(topics=[f"tema {index}"]), NOW)

    assert len(model.topics) == MAX_TRACKED_TOPICS
    assert model.topics["perro"] == 2


def test_primary_and_new_person_trust():
    """D1-55: el primary trae su confianza de la config; una persona nueva, la inicial."""
    assert PartnerModel.for_primary(RICARDO).trust == 0.4
    assert PartnerModel.for_primary(RICARDO).primary is True
    assert PartnerModel(id="ana", name="Ana").trust == NEW_PERSON_TRUST


@pytest.mark.parametrize(
    ("name", "existing", "expected"),
    [
        ("Ana", {}, "ana"),
        ("  Ana María ", {}, "ana-maria"),
        ("Begoña", {}, "begona"),
        ("Ana-María", {"ana-maria": "Ana Maria Pérez"}, "ana-maria-2"),
        ("¿?", {}, "persona"),
    ],
)
def test_new_person_id(name, existing, expected):
    """D1-52: el id sale del nombre; si solo choca el id, se numera."""
    assert new_person_id(name, existing) == expected


def test_repeated_name_is_rejected():
    """D1-52: sin alias en Fase 1, dos personas no pueden llamarse igual (ni con otra tilde o mayúscula)."""
    with pytest.raises(DuplicatePersonError):
        new_person_id("ána", {"ana": "Ana"})
    with pytest.raises(ValueError):
        new_person_id("   ", {})


def test_normalize_name():
    """Nombres comparables: sin mayúsculas, tildes ni espacios de más."""
    assert normalize_name("  Ána   María ") == "ana maria"


def test_episode_text_with_speaker():
    """D1-56: el recuerdo dice quién habló; sin persona, se mantiene el formato de CP6."""
    assert episode_text("Fui a Valparaíso.", "¡Qué bueno!", speaker="Ricardo") == (
        "Ricardo me dijo: «Fui a Valparaíso.»\nLe respondí: «¡Qué bueno!»"
    )
    assert episode_text("Hola", "Hola").startswith("Me dijeron: «Hola»")


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


async def talk(writer, entity_id: str, model: PartnerModel, text: str, ts: datetime = NOW, **values):
    """Un turno de `model`: actualiza su modelo con el appraisal y lo escribe con el episodio."""
    turn_appraisal = appraisal(**values)
    updated = update_partner_model(model, PartnerNow.from_appraisal(turn_appraisal), ts)
    written = await writer.write_turn(
        entity_id, ts=ts, user_text=text, entity_text="Ah, cuéntame más.",
        affect=VAD(valence=0.1, arousal=0.5, dominance=0.5), appraisal=turn_appraisal, person=updated,
    )
    return updated, written


@pytest.mark.integration
async def test_primary_is_ensured_once_and_synced_with_the_config(graph):
    """Cargar dos veces crea un solo Person del primary; la confianza sigue a la config sin borrar lo aprendido."""
    entity_id = f"{TEST_PREFIX}a"
    people = PeopleStore(graph)

    first = await people.ensure_primary(entity_id, RICARDO)
    await graph.execute("MATCH (p:Person {entity_id: $e, id: 'ricardo'}) SET p.n = 7", e=entity_id)
    second = await people.ensure_primary(entity_id, RICARDO.model_copy(update={"trust": 0.5}))

    assert first.created is True and second.created is False
    assert await count(graph, "(:Person {entity_id: $e})", e=entity_id) == 1
    assert (second.model.trust, second.model.n, second.model.primary) == (0.5, 7, True)
    rows = await graph.execute(
        "MATCH (p:Person {entity_id: $e}) RETURN p.known_via AS via, p.provisional AS provisional", e=entity_id
    )
    assert rows == [{"via": "direct", "provisional": False}]


@pytest.mark.integration
async def test_changing_the_primary_keeps_a_single_one(graph):
    """Si la config cambia de primary, el anterior deja de serlo pero conserva su nodo."""
    entity_id = f"{TEST_PREFIX}a"
    people = PeopleStore(graph)
    await people.ensure_primary(entity_id, RICARDO)

    await people.ensure_primary(entity_id, PrimaryPerson(id="ana", name="Ana"))

    assert [(m.id, m.primary) for m in await people.list(entity_id)] == [("ana", True), ("ricardo", False)]


@pytest.mark.integration
async def test_new_person_with_name(graph):
    """Persona nueva: id del nombre, confianza inicial, sin historia; el nombre repetido se rechaza."""
    entity_id = f"{TEST_PREFIX}a"
    people = PeopleStore(graph)
    await people.ensure_primary(entity_id, RICARDO)

    ana = await people.create(entity_id, " Ana ")

    assert (ana.id, ana.name, ana.trust, ana.n, ana.primary) == ("ana", "Ana", NEW_PERSON_TRUST, 0, False)
    assert await people.get(entity_id, "ana") == ana
    with pytest.raises(DuplicatePersonError):
        await people.create(entity_id, "ANA")
    assert await people.get(entity_id, "nadie") is None


@pytest.mark.integration
async def test_turn_links_the_person_and_saves_the_model(graph, writer):
    """Un turno con persona: texto con el nombre, INVOLVES, SPOKEN_BY y el Person actualizado, juntos."""
    entity_id = f"{TEST_PREFIX}a"
    people = PeopleStore(graph)
    ricardo = (await people.ensure_primary(entity_id, RICARDO)).model

    updated, written = await talk(writer, entity_id, ricardo, "Adopté un perro, Toby.",
                                  valence=0.5, arousal=0.4, topics=["perro"])

    params = {"e": entity_id, "id": written.episode_id}
    rows = await graph.execute(
        "MATCH (ep:Episode {entity_id: $e, id: $id})-[:INVOLVES]->(p:Person {id: 'ricardo'}), "
        "(ep)-[:DERIVED_FROM]->(t:Trace)-[:SPOKEN_BY]->(p) RETURN ep.text AS text, t.raw_text AS raw",
        **params,
    )
    assert len(rows) == 1
    assert rows[0]["text"].startswith("Ricardo me dijo: «Adopté un perro, Toby.»\nLe respondí:")
    assert rows[0]["raw"].startswith("Ricardo me dijo:")
    stored = await people.get(entity_id, "ricardo")
    assert stored == updated
    assert (stored.n, stored.valence_mean, stored.topics, stored.primary) == (1, 0.5, {"perro": 1}, True)
    [row] = await graph.execute("MATCH (p:Person {entity_id: $e}) RETURN p.model_json AS j", e=entity_id)
    assert json.loads(row["j"])["topics"] == {"perro": 1}


@pytest.mark.integration
async def test_two_people_do_not_cross(graph, writer):
    """§12: dos personas cuentan cosas distintas y el modelo de cada una contiene solo lo suyo."""
    entity_id = f"{TEST_PREFIX}a"
    people = PeopleStore(graph)
    ricardo = (await people.ensure_primary(entity_id, RICARDO)).model
    ana = await people.create(entity_id, "Ana")

    ricardo, first = await talk(writer, entity_id, ricardo, "Adopté un perro.", topics=["perro"], valence=0.6)
    ana, _ = await talk(writer, entity_id, ana, "Tengo una gata, Mora.", NOW + timedelta(minutes=1),
                        topics=["gata"], valence=-0.2, distress=0.7)
    ricardo, _ = await talk(writer, entity_id, ricardo, "Fui a Valparaíso.", NOW + timedelta(minutes=2),
                            topics=["valparaiso"], valence=0.6)

    stored_ricardo, stored_ana = await people.get(entity_id, "ricardo"), await people.get(entity_id, "ana")
    assert (stored_ricardo.n, set(stored_ricardo.topics)) == (2, {"perro", "valparaiso"})
    assert (stored_ana.n, stored_ana.topics, stored_ana.sensitive_topics) == (1, {"gata": 1}, {"gata": 1})
    assert stored_ricardo.sensitive_topics == {} and stored_ricardo.valence_mean == pytest.approx(0.6)
    assert await count(graph, "(:Episode {entity_id: $e})-[:INVOLVES]->(:Person {id: 'ricardo'})", e=entity_id) == 2
    assert await count(graph, "(:Episode {entity_id: $e})-[:INVOLVES]->(:Person {id: 'ana'})", e=entity_id) == 1
    assert await count(graph, "(e:Episode {entity_id: $e})-[:INVOLVES]->() WITH e, count(*) AS c WHERE c > 1",
                       e=entity_id) == 0
    # Sin persona (memoria sin PartnerModel) no se crea ningún enlace.
    await writer.write_turn(entity_id, ts=NOW + timedelta(minutes=3), user_text="Hola", entity_text="Hola",
                            affect=VAD(valence=0, arousal=0.5, dominance=0.5), appraisal=neutral_appraisal())
    # 3 turnos con persona × (INVOLVES + SPOKEN_BY); el turno sin persona no suma.
    assert await count(graph, "({entity_id: $e})-[:INVOLVES|SPOKEN_BY]->(:Person)", e=entity_id) == 6
    assert first.previous_episode_id is None


@pytest.mark.integration
async def test_people_of_another_entity_are_not_seen(graph):
    """El mismo id de persona en dos entidades son dos nodos distintos (§7.1)."""
    a, b = f"{TEST_PREFIX}a", f"{TEST_PREFIX}b"
    people = PeopleStore(graph)
    await people.ensure_primary(a, RICARDO)

    assert await people.list(b) == []
    created = await people.ensure_primary(b, RICARDO)
    assert created.created is True
    assert await count(graph, "(p:Person {id: 'ricardo'}) WHERE p.entity_id IN [$a, $b]", a=a, b=b) == 2


# ------------------------------------------------------------ recuperación (D1-58)


def vec(**axes: float) -> list[float]:
    """Vector de dimensión 1024 con valores en los ejes indicados (a0, a1…), de norma 1."""
    values = [0.0] * DIMENSION
    for name, value in axes.items():
        values[int(name[1:])] = value
    norm = math.sqrt(sum(v * v for v in values))
    return [v / norm for v in values]


async def add_episode(graph, entity_id, id_, embedding, ts=NOW - timedelta(days=1), person_id=None):
    """Escribe un episodio con un vector dado, enlazado a una persona si se indica."""
    await graph.execute(
        "CREATE (e:Episode {entity_id: $e, id: $id, kind: 'dialogue', ts: $ts, text: $id, summary: $id, "
        "embedding: $emb, valence: 0.0, arousal: 0.5, dominance: 0.5, importance: 0.3, "
        "lability: 0.0, access: 'open', version: 1}) "
        "FOREACH (pid IN CASE WHEN $pid IS NULL THEN [] ELSE [$pid] END | "
        "  MERGE (p:Person {entity_id: $e, id: pid}) ON CREATE SET p.name = pid CREATE (e)-[:INVOLVES]->(p))",
        e=entity_id, id=id_, ts=ts, emb=embedding, pid=person_id,
    )


async def candidates(graph, entity_id, query, expected=20, **values) -> dict[str, set[str]]:
    """Candidatos de la recuperación (id → fuentes); espera a que el índice vea al menos `expected`."""
    result = None
    for _ in range(30):
        result = await MemoryRetriever(graph).retrieve(
            entity_id, query, affect=VAD(valence=0.0, arousal=0.5, dominance=0.5), k=8,
            lambda_mmr=0.5, now=NOW, raise_lability=False, **values,
        )
        if len(result.candidates) >= expected:
            break
        await asyncio.sleep(0.1)
    return {item.candidate.id: item.candidate.sources for item in result.candidates}


@pytest.mark.integration
async def test_episodes_with_the_active_person_join_the_candidates(graph):
    """D1-58: un episodio con la persona activa entra aunque quede fuera del top-20 vectorial."""
    entity_id = f"{TEST_PREFIX}a"
    await graph.execute("CREATE (:Person {entity_id: $e, id: 'ana', name: 'Ana'})", e=entity_id)
    for index in range(25):  # más parecidos a la consulta que el de Ricardo
        await add_episode(graph, entity_id, f"ep-otro-{index}", vec(a0=1, **{f"a{index + 10}": 0.05}))
    await add_episode(graph, entity_id, "ep-ricardo", vec(a0=1, a1=0.9), person_id="ricardo")
    await add_episode(graph, entity_id, "ep-ana", vec(a0=1, a2=0.9), person_id="ana")

    without = await candidates(graph, entity_id, vec(a0=1))
    with_person = await candidates(graph, entity_id, vec(a0=1), person_id="ricardo")
    mentioned = await candidates(graph, entity_id, vec(a0=1), mentioned_names=["ÁNA"])

    assert "ep-ricardo" not in without and "ep-ana" not in without
    assert with_person["ep-ricardo"] == {"person"} and "ep-ana" not in with_person
    assert mentioned["ep-ana"] == {"person"} and "ep-ricardo" not in mentioned


@pytest.mark.integration
async def test_person_neighbours_still_need_similarity(graph):
    """Los vecinos Person pasan por el mismo umbral: un episodio sin parecido no entra."""
    entity_id = f"{TEST_PREFIX}a"
    await add_episode(graph, entity_id, "ep-cerca", vec(a0=1), person_id="ricardo")
    await add_episode(graph, entity_id, "ep-lejos", vec(a5=1), person_id="ricardo")

    found = await candidates(graph, entity_id, vec(a0=1), expected=1, person_id="ricardo")

    assert "ep-cerca" in found and "ep-lejos" not in found
