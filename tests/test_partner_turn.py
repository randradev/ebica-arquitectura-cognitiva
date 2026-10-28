"""
Pruebas del turno con interlocutor (Fase 1, CP8 parte C), con un LLM simulado.

Cubren la persona activa en el turno (`partner_now`, sección 6, `tom.updated`),
el cambio de interlocutor con un hilo por persona (D1-53), el alivio de
`social` según la confianza (D1-55), la memoria desactivada y la API del
selector. La última prueba usa Neo4j real (se omite si no está).
"""

import os
import re
from datetime import datetime, timedelta, timezone

import pytest
from fake_llm import NEUTRAL_APPRAISAL, drain, turn_transport
from fastapi.testclient import TestClient
from neo4j.exceptions import ServiceUnavailable

from ebica.api.server import create_app
from ebica.core.events import EventBus
from ebica.core.orchestrator import Orchestrator, PeopleUnavailableError
from ebica.core.state import ConversationTurn, EntityConfig
from ebica.entities.manager import EntityManager
from ebica.identity.biography import PrimaryPerson
from ebica.llm.client import LLMClient
from ebica.llm.prompt_assembler import PARTNER_HEADER, build_impulsive_messages, describe_partner
from ebica.affect.vad import VAD
from ebica.memory.episodes import WrittenEpisode
from ebica.memory.graph import GraphStore
from ebica.memory.people import EnsuredPerson, PeopleStore
from ebica.social.partner import DuplicatePersonError, PartnerModel, PartnerNow, new_person_id

NOW = datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc)
RICARDO = PrimaryPerson(id="ricardo", name="Ricardo", trust=0.4)
CONFIG = EntityConfig(
    id="prueba", name="Prueba", persona="Soy Prueba.", appraisal_profile="Prueba, artista.",
    primary_person=RICARDO,
)
WARM_REPLY = {**NEUTRAL_APPRAISAL, "user_emotion": {"valence": 0.6, "arousal": 0.4, "dominance": 0.5},
              "user_intent": "contar algo", "topics": ["Perros"]}


class FakePeople:
    """Hace las veces de `PeopleStore` en memoria (sin Neo4j)."""

    def __init__(self) -> None:
        """Empieza sin personas."""
        self.models: dict[str, PartnerModel] = {}

    async def list(self, entity_id):
        """Las personas, primero el primary."""
        return sorted(self.models.values(), key=lambda m: (not m.primary, m.name))

    async def get(self, entity_id, person_id):
        """El modelo guardado, o None."""
        return self.models.get(person_id)

    async def ensure_primary(self, entity_id, primary):
        """Crea el primary la primera vez."""
        created = primary.id not in self.models
        if created:
            self.models[primary.id] = PartnerModel.for_primary(primary)
        return EnsuredPerson(model=self.models[primary.id], created=created)

    async def create(self, entity_id, name):
        """Crea una persona nueva con nombre."""
        model = PartnerModel(id=new_person_id(name, {m.id: m.name for m in self.models.values()}), name=name)
        self.models[model.id] = model
        return model


class FakeMemory:
    """Hace las veces de `MemoryWriter`: guarda en `FakePeople` el modelo que recibe, como hace Neo4j."""

    def __init__(self, people: FakePeople) -> None:
        """Comparte las personas con el `FakePeople` del orquestador."""
        self.people = people
        self.calls: list[dict] = []

    async def write_turn(self, entity_id, **values):
        """Registra el turno y persiste el modelo de la persona."""
        self.calls.append(values)
        if values.get("person") is not None:
            self.people.models[values["person"].id] = values["person"]
        return WrittenEpisode(
            episode_id=f"ep-{len(self.calls)}", trace_id="tr", importance=0.0, topics=[], new_topics=[],
            previous_episode_id=None, embed_ms=1.0, write_ms=1.0,
        )


async def make(tmp_path, llm, config=CONFIG, people=True):
    """Crea la entidad y su orquestador (con personas y memoria simuladas, o sin memoria) y carga a la persona."""
    bus = EventBus()
    manager = EntityManager(tmp_path, bus)
    entity = manager.create(config)
    store = FakePeople() if people else None
    memory = FakeMemory(store) if people else None
    orchestrator = Orchestrator(
        entity, bus, manager.save_state, llm=llm, memory=memory, people=store, now=lambda: NOW,
    )
    orchestrator.wake()
    await orchestrator.load_partner()
    return orchestrator, bus, store, memory


async def say(orchestrator, text):
    """Procesa un mensaje y devuelve la respuesta completa."""
    return "".join([piece async for piece in orchestrator.user_turn(text)])


def by_type(events) -> dict[str, list]:
    """Agrupa los eventos por tipo, en orden."""
    grouped: dict[str, list] = {}
    for event in events:
        grouped.setdefault(event.type, []).append(event)
    return grouped


def dialogue_prompts(bodies) -> list[list[dict]]:
    """Los mensajes de cada petición de diálogo (las de appraisal piden un esquema JSON)."""
    return [body["messages"] for body in bodies if "response_format" not in body]


# ------------------------------------------------------------ sección 6


def test_partner_section_first_time_and_with_history():
    """Sección 6 en palabras, sin números ni género; con historia, cuándo, cuánto, temas y ánimo."""
    first = describe_partner(PartnerModel(id="ana", name="Ana"), None, NOW)
    assert first == "Estoy hablando con Ana.\nEs la primera vez que hablamos; todavía no le tengo mucha confianza."

    known = PartnerModel(
        id="ricardo", name="Ricardo", primary=True, trust=0.4, n=12, first_met=NOW - timedelta(days=3),
        valence_mean=0.5, topics={"perro": 4, "trabajo": 2}, sensitive_topics={"trabajo": 1},
    )
    now = PartnerNow(valence=-0.5, arousal=0.4, intent="desahogarse", topics=["trabajo"],
                     distress=0.8, hostility=0.0)
    text = describe_partner(known, now, NOW)

    assert text == (
        "Estoy hablando con Ricardo.\n"
        "Hablamos por primera vez hace 3 días y hemos hablado varias veces; le tengo algo de confianza.\n"
        "Suele hablarme de buen ánimo.\n"
        "Suele hablarme de perro y trabajo.\n"
        "Le cuesta hablar de trabajo.\n"
        "Ahora se le nota con el ánimo bajo y con angustia; busca desahogarse."
    )
    assert not re.search(r"\d", text.replace("hace 3 días", ""))


def test_impulsive_prompt_names_the_partner():
    """La ruta impulsiva solo recibe el nombre de quien habla."""
    messages = build_impulsive_messages(CONFIG, "cállate", VAD(valence=-0.2, arousal=0.8, dominance=0.4),
                                        partner_name="Ana")
    assert "Estoy hablando con Ana." in messages[0]["content"]
    assert PARTNER_HEADER not in messages[0]["content"]


# ------------------------------------------------------------ turno


async def test_turn_with_partner_event_chain_and_prompt(tmp_path):
    """… → memory.written → tom.updated → turn.completed; el episodio lleva el modelo y el prompt la sección 6."""
    transport, bodies = turn_transport("Ho", "la", appraisal=WARM_REPLY)
    async with LLMClient(EventBus(), transport=transport) as llm:
        orchestrator, bus, store, memory = await make(tmp_path, llm)
        queue = bus.subscribe()
        await say(orchestrator, "Adopté un perro")
    events = by_type(drain(queue))

    written, tom, turn = events["memory.written"][0], events["tom.updated"][0], events["turn.completed"][0]
    assert tom.cause_id == written.id and turn.cause_id == tom.id
    assert tom.payload["person_id"] == "ricardo" and tom.payload["now"]["topics"] == ["perro"]
    assert tom.payload["model"]["n"] == 1 and tom.payload["model"]["top_topics"] == ["perro"]
    assert turn.payload["partner"] == tom.payload
    person = memory.calls[0]["person"]
    assert (person.id, person.n, person.valence_mean) == ("ricardo", 1, 0.6)
    assert store.models["ricardo"].n == 1
    system = dialogue_prompts(bodies)[0][0]["content"]
    assert f"{PARTNER_HEADER}\nEstoy hablando con Ricardo.\nEs la primera vez que hablamos" in system
    assert "Ahora se le nota de buen ánimo; busca contar algo." in system
    state = orchestrator.state
    assert state.active_person_id == "ricardo" and state.partner.now.intent == "contar algo"
    assert state.recent_turns[-1].person_id == "ricardo"


async def test_primary_person_created_once(tmp_path):
    """La primera carga emite `tom.person_created`; la segunda, no."""
    transport, _ = turn_transport("Ho", "la")
    async with LLMClient(EventBus(), transport=transport) as llm:
        orchestrator, bus, store, _ = await make(tmp_path, llm)
        queue = bus.subscribe()
        await orchestrator.load_partner()
    assert "tom.person_created" not in by_type(drain(queue))
    assert list(store.models) == ["ricardo"]


async def test_switching_partner_keeps_one_thread_per_person(tmp_path):
    """D1-53: Ana no ve los intercambios de Ricardo; al volver, el hilo de Ricardo sigue ahí."""
    transport, bodies = turn_transport("Ho", "la", appraisal=WARM_REPLY)
    async with LLMClient(EventBus(), transport=transport) as llm:
        orchestrator, bus, store, _ = await make(tmp_path, llm)
        await say(orchestrator, "Soy Ricardo y fui a Valparaíso")
        queue = bus.subscribe()
        ana = await orchestrator.create_partner("Ana")
        await say(orchestrator, "Soy Ana")
        await orchestrator.switch_partner("ricardo")
        await say(orchestrator, "Volví")
    events = by_type(drain(queue))

    assert ana.id == "ana" and events["tom.person_created"][0].payload["person"]["name"] == "Ana"
    switched = [e.payload for e in events["tom.partner_switched"]]
    assert [(e["from"], e["to"]) for e in switched] == [("ricardo", "ana"), ("ana", "ricardo")]
    prompts = dialogue_prompts(bodies)
    ana_prompt = " ".join(m["content"] for m in prompts[1])
    assert "Valparaíso" not in ana_prompt and "Estoy hablando con Ana." in ana_prompt
    ricardo_back = " ".join(m["content"] for m in prompts[2])
    assert "Valparaíso" in ricardo_back and "Soy Ana" not in ricardo_back
    assert store.models["ana"].n == 1 and store.models["ricardo"].n == 2
    with pytest.raises(KeyError):
        await orchestrator.switch_partner("nadie")
    with pytest.raises(DuplicatePersonError):
        await orchestrator.create_partner("ana")


async def test_social_relief_scales_with_trust(tmp_path):
    """D1-55: el primary alivia `social` completo; Ana (confianza 0,2), la quinta parte."""
    transport, _ = turn_transport("Ho", "la", appraisal=WARM_REPLY)
    async with LLMClient(EventBus(), transport=transport) as llm:
        orchestrator, bus, _, _ = await make(tmp_path, llm)
        queue = bus.subscribe()
        await say(orchestrator, "hola")
        await orchestrator.create_partner("Ana")
        await say(orchestrator, "hola")
    reliefs = [e.payload["drive_relief"]["social"] for e in by_type(drain(queue))["affect.updated"]
               if e.payload["source"] == "appraisal"]

    assert reliefs[1] == pytest.approx(reliefs[0] * 0.2)


async def test_old_turns_are_assigned_to_the_primary(tmp_path):
    """Los intercambios guardados antes de CP8 (sin persona) pasan al primary al cargar."""
    transport, bodies = turn_transport("Ho", "la")
    async with LLMClient(EventBus(), transport=transport) as llm:
        bus = EventBus()
        manager = EntityManager(tmp_path, bus)
        entity = manager.create(CONFIG)
        entity.state.recent_turns = [ConversationTurn(user="Viejo mensaje", entity="Viejo", ts=NOW)]
        orchestrator = Orchestrator(entity, bus, manager.save_state, llm=llm, now=lambda: NOW)
        orchestrator.wake()
        await orchestrator.load_partner()
        await say(orchestrator, "hola")

    assert entity.state.recent_turns[0].person_id == "ricardo"
    assert "Viejo mensaje" in " ".join(m["content"] for m in dialogue_prompts(bodies)[0])


async def test_without_memory_only_the_primary(tmp_path):
    """EBICA_MEMORY=off: el turno funciona con el primary en memoria; no se pueden crear personas."""
    transport, _ = turn_transport("Ho", "la", appraisal=WARM_REPLY)
    async with LLMClient(EventBus(), transport=transport) as llm:
        orchestrator, bus, _, _ = await make(tmp_path, llm, people=False)
        queue = bus.subscribe()
        await say(orchestrator, "hola")
        with pytest.raises(PeopleUnavailableError):
            await orchestrator.create_partner("Ana")
        assert (await orchestrator.switch_partner("ricardo")).n == 1
    events = by_type(drain(queue))

    assert events["tom.updated"][0].payload["model"]["n"] == 1
    assert "memory.written" not in events
    assert orchestrator.state.partner.model.n == 1  # lo aprendido queda en el estado


async def test_entity_without_primary_has_no_partner(tmp_path):
    """Una entidad sin `primary` (Fase 0) sigue como antes: sin sección 6 ni `tom.updated`."""
    transport, bodies = turn_transport("Ho", "la")
    config = CONFIG.model_copy(update={"primary_person": None})
    async with LLMClient(EventBus(), transport=transport) as llm:
        orchestrator, bus, _, _ = await make(tmp_path, llm, config=config)
        queue = bus.subscribe()
        await say(orchestrator, "hola")
    events = by_type(drain(queue))

    assert orchestrator.partner is None and "tom.updated" not in events
    assert PARTNER_HEADER not in dialogue_prompts(bodies)[0][0]["content"]
    assert events["turn.completed"][0].payload["partner"] is None


# ------------------------------------------------------------ API


def test_people_api_without_memory(tmp_path):
    """Sin memoria: la lista trae al primary, crear da 409, elegirlo funciona y la conversación lleva la persona."""
    transport, _ = turn_transport("Ho", "la")
    with TestClient(create_app(entities_dir=tmp_path, llm_transport=transport)) as client:
        assert client.get("/api/people").status_code == 409  # sin entidad cargada
        client.post("/api/entities", json=CONFIG.model_dump(mode="json"))
        client.post("/api/entities/prueba/load")

        listed = client.get("/api/people").json()
        assert listed["active"] == "ricardo" and listed["can_create"] is False
        assert [p["name"] for p in listed["people"]] == ["Ricardo"]
        assert client.post("/api/people", json={"name": "Ana"}).status_code == 409
        assert client.post("/api/people/ricardo/activate").status_code == 200
        assert client.post("/api/people/ana/activate").status_code == 409
        assert client.post("/api/people/NO%20VALE/activate").status_code == 422
        with client.websocket_connect("/ws/chat") as chat:
            chat.send_json({"text": "hola"})
            while chat.receive_json()["type"] == "token":
                pass
        conversation = client.get("/api/conversation").json()
    assert conversation["person"] == {"id": "ricardo", "name": "Ricardo"}
    assert [turn["person_id"] for turn in conversation["turns"]] == ["ricardo"]


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
    await store.apply_schema(1024)
    yield store
    await store.execute("MATCH (n) WHERE n.entity_id STARTS WITH 'test_cp8c_' DETACH DELETE n")
    await store.close()


@pytest.mark.integration
async def test_partner_lifecycle_with_neo4j(tmp_path, graph):
    """Con Neo4j real: el primary se crea una vez, Ana se crea y se elige, y recargar recuerda a quién se eligió."""
    config = CONFIG.model_copy(update={"id": "test_cp8c_a"})
    transport, _ = turn_transport("Ho", "la")
    async with LLMClient(EventBus(), transport=transport) as llm:
        bus = EventBus()
        manager = EntityManager(tmp_path, bus)
        entity = manager.create(config)
        people = PeopleStore(graph)
        orchestrator = Orchestrator(entity, bus, manager.save_state, llm=llm, people=people)
        queue = bus.subscribe()
        await orchestrator.load_partner()
        await orchestrator.create_partner("Ana")

        reloaded = Orchestrator(manager.load("test_cp8c_a"), bus, manager.save_state, llm=llm, people=people)
        await reloaded.load_partner()
    created = [e.payload["person"]["id"] for e in by_type(drain(queue))["tom.person_created"]]

    assert created == ["ricardo", "ana"]
    assert reloaded.partner.id == "ana"
    assert [m.id for m in await reloaded.list_people()] == ["ricardo", "ana"]
