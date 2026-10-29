"""
Pruebas de los micro-agentes en el turno (Fase 1, CP10 parte C), con LLM y memoria simulados.

Cubren la cadena `appraisal → agent.signal → wm.updated → llm.request` y el
efecto de cada señal: el factor de la pizarra (`distress_watch`), la promesa en
la sección 6 (`commitment_watch`), `novelty` y las notas de la sección 7
(`repetition_watch`), la alarma de la ruta impulsiva (`hostility_watch`) y la
presión de los drives (`homeostasis_watch`).
"""

from datetime import datetime, timedelta, timezone

import pytest
from fake_llm import NEUTRAL_APPRAISAL, drain, turn_transport

from ebica.core.events import EventBus
from ebica.core.orchestrator import Orchestrator
from ebica.core.state import EntityConfig
from ebica.entities.manager import EntityManager
from ebica.identity.biography import PrimaryPerson
from ebica.llm.client import LLMClient
from ebica.llm.prompt_assembler import ENTITY_REPEATS_NOTE, USER_REPEATS_NOTE
from ebica.memory.episodes import WrittenEpisode
from ebica.memory.people import EnsuredPerson
from ebica.memory.retrieval import EpisodeCandidate, RetrievalResult, score_episode
from ebica.social.partner import PartnerModel
from fake_embedder import FakeEmbedder

NOW = datetime(2026, 10, 28, 20, 0, tzinfo=timezone.utc)
CONFIG = EntityConfig(id="prueba", name="Prueba", persona="Soy Prueba.", appraisal_profile="Prueba, artista.",
                      primary_person=PrimaryPerson(id="ricardo", name="Ricardo", trust=0.4))
DISTRESS_REPLY = {**NEUTRAL_APPRAISAL, "distress": 0.8,
                  "user_emotion": {"valence": -0.6, "arousal": 0.6, "dominance": 0.3}}


class FakeMemory:
    """Hace las veces de `MemoryWriter`: embedder simulado y una escritura que no falla."""

    def __init__(self) -> None:
        """Embedder determinista: textos iguales dan vectores iguales."""
        self.embedder = FakeEmbedder()

    async def write_turn(self, entity_id, **values):
        """Devuelve un episodio escrito cualquiera."""
        return WrittenEpisode(episode_id="ep-x", trace_id="tr-x", importance=0.0, topics=[], new_topics=[],
                              previous_episode_id=None, embed_ms=1.0, write_ms=1.0)


class FakeRetriever:
    """Devuelve un recuerdo con Ricardo (para el factor de `distress_watch`)."""

    async def retrieve(self, entity_id, query_vector, **values):
        """Un episodio de diálogo con Ricardo, de relevancia conocida."""
        candidate = EpisodeCandidate(id="ep-ricardo", kind="dialogue", ts=values["now"] - timedelta(days=1),
                                     text="Ricardo me dijo: «Ando triste.»", valence=0.0, arousal=0.5,
                                     importance=0.0, embedding=query_vector, person_id="ricardo",
                                     person_name="Ricardo")
        scored = score_episode(candidate, 0.6, values["now"], values["affect"])
        return RetrievalResult(episodes=[scored], facts=[], candidates=[scored], k_effective=8)


class FakePeople:
    """Hace las veces de `PeopleStore`: el primary y, si se indica, una promesa abierta."""

    def __init__(self, promises=()) -> None:
        """`promises` son filas de `open_commitments` (id, text, ts)."""
        self.model = PartnerModel.for_primary(CONFIG.primary_person)
        self.promises = list(promises)

    async def ensure_primary(self, entity_id, primary):
        """El primary ya existe."""
        return EnsuredPerson(model=self.model, created=False)

    async def get(self, entity_id, person_id):
        """El modelo del primary."""
        return self.model if person_id == "ricardo" else None

    async def open_commitments(self, entity_id, person_id):
        """Las promesas abiertas configuradas."""
        return self.promises


async def make(tmp_path, llm, clock, people=None, memory=True, bus=None):
    """Entidad con primary, memoria y recuperación simuladas; ya despierta y con su persona cargada.

    `bus` debe ser el mismo del cliente LLM si la prueba revisa `llm.request`.
    """
    bus = bus or EventBus()
    entity = EntityManager(tmp_path, bus).create(CONFIG)
    manager = EntityManager(tmp_path, bus)
    orchestrator = Orchestrator(
        entity, bus, manager.save_state, llm=llm, now=lambda: clock[0],
        memory=FakeMemory() if memory else None, retriever=FakeRetriever() if memory else None,
        people=people or FakePeople(),
    )
    orchestrator.wake()
    await orchestrator.load_partner()
    return orchestrator, bus


async def say(orchestrator, text):
    """Procesa un mensaje y devuelve la respuesta completa."""
    return "".join([piece async for piece in orchestrator.user_turn(text)])


def by_type(events) -> dict[str, list]:
    """Agrupa los eventos por tipo, en orden."""
    grouped: dict[str, list] = {}
    for event in events:
        grouped.setdefault(event.type, []).append(event)
    return grouped


def dialogue_prompts(bodies) -> list[str]:
    """El prompt de sistema de cada petición de diálogo."""
    return [body["messages"][0]["content"] for body in bodies if "response_format" not in body]


async def test_distress_signal_chain_and_attention_factor(tmp_path):
    """appraisal → agent.signal → wm.updated → llm.request; los recuerdos con quien sufre pesan ×1,5 (D1-71)."""
    transport, _ = turn_transport("Ho", "la", appraisal=DISTRESS_REPLY)
    shared = EventBus()
    async with LLMClient(shared, transport=transport) as llm:
        orchestrator, bus = await make(tmp_path, llm, [NOW], bus=shared)
        queue = bus.subscribe()
        await say(orchestrator, "Ando muy triste, no sé qué hacer")
    events = by_type(drain(queue))

    [signal] = [e for e in events["agent.signal"] if e.payload["agent"] == "distress_watch"]
    assert signal.payload["kind"] == "attend_partner" and signal.payload["target"] == "ricardo"
    assert signal.cause_id == events["memory.retrieved"][0].id
    workspace = events["wm.updated"][0]
    assert workspace.cause_id == events["agent.signal"][-1].id
    assert events["llm.request"][-1].cause_id == workspace.id
    [item] = [i for i in workspace.payload["kept"] if i["key"] == "ep-ricardo"]
    assert item["salience"] == pytest.approx(item["relevance"] * 1.5, abs=1e-3)
    assert events["turn.completed"][0].payload["signals"][0]["agent"] == "distress_watch"


async def test_open_promise_appears_in_section_6(tmp_path):
    """D1-74: una promesa de ayer entra a la pizarra y va en la sección 6 («Me prometió: …»)."""
    transport, bodies = turn_transport("Ho", "la")
    promise = {"id": "cm-1", "text": "te cuento", "ts": NOW - timedelta(days=1),
               "context": "Mañana tengo una entrevista en un banco, te cuento cómo me fue."}
    async with LLMClient(EventBus(), transport=transport) as llm:
        orchestrator, bus = await make(tmp_path, llm, [NOW], people=FakePeople([promise]))
        queue = bus.subscribe()
        await say(orchestrator, "Hola, ¿cómo estás?")
    events = by_type(drain(queue))

    assert ("Me prometió: «te cuento» (ayer), cuando me dijo: «Mañana tengo una entrevista en un banco, "
            "te cuento cómo me fue.»." in dialogue_prompts(bodies)[0])
    [signal] = [e for e in events["agent.signal"] if e.payload["agent"] == "commitment_watch"]
    assert signal.payload["target"] == "cm-1" and signal.payload["strength"] == pytest.approx(
        orchestrator.parameters.w_commit * 0.5 ** (1 / 7), abs=1e-3)  # rasgos neutros: w_commit = 1,0
    assert any(i["kind"] == "commitment" for i in events["wm.updated"][0].payload["kept"])


async def test_user_repetition_raises_novelty_and_adds_a_note(tmp_path):
    """D1-72: la misma pregunta dos veces → `user_repeats`, novelty +0,15 y la nota en la sección 7."""
    transport, bodies = turn_transport("Ho", "la")
    async with LLMClient(EventBus(), transport=transport) as llm:
        orchestrator, bus = await make(tmp_path, llm, [NOW])
        await say(orchestrator, "¿A qué ciudad fui el fin de semana?")
        before = orchestrator.state.drives["novelty"]
        queue = bus.subscribe()
        await say(orchestrator, "¿A qué ciudad fui el fin de semana?")
    events = by_type(drain(queue))

    [signal] = [e for e in events["agent.signal"] if e.payload["kind"] == "user_repeats"]
    raised = next(e for e in events["drive.updated"] if e.cause_id == signal.id)
    assert raised.payload["novelty"] == pytest.approx(before + 0.15, abs=0.01)
    first, second = dialogue_prompts(bodies)
    assert USER_REPEATS_NOTE not in first and USER_REPEATS_NOTE in second


async def test_entity_repetition_adds_a_note_on_the_next_turn(tmp_path):
    """D1-72: si la entidad responde lo mismo dos veces, el turno siguiente lleva «No repito lo que ya dije»."""
    transport, bodies = turn_transport("Siempre", " lo mismo")
    async with LLMClient(EventBus(), transport=transport) as llm:
        orchestrator, bus = await make(tmp_path, llm, [NOW])
        await say(orchestrator, "primer mensaje distinto aquí")
        await say(orchestrator, "segundo tema sin relación alguna")
        queue = bus.subscribe()
        await say(orchestrator, "tercera cosa completamente nueva")
    events = by_type(drain(queue))

    assert [e.payload["kind"] for e in events["agent.signal"]] == ["entity_repeats"]
    prompts = dialogue_prompts(bodies)
    assert ENTITY_REPEATS_NOTE not in prompts[1] and ENTITY_REPEATS_NOTE in prompts[2]


async def test_impulsive_turn_carries_the_hostility_signal(tmp_path):
    """D1-70: la vía baja emite `agent.signal` (alarm) además de `affect.low_road_triggered`."""
    transport, _ = turn_transport("Ho", "la")
    async with LLMClient(EventBus(), transport=transport) as llm:
        orchestrator, bus = await make(tmp_path, llm, [NOW])
        queue = bus.subscribe()
        await say(orchestrator, "Eres una inútil.")
    events = by_type(drain(queue))

    [signal] = events["agent.signal"]
    assert signal.payload["agent"] == "hostility_watch" and signal.payload["kind"] == "alarm"
    assert signal.cause_id == events["perception.input"][0].id
    assert events["turn.completed"][0].payload["impulsive"] is True
    assert events["turn.completed"][0].payload["signals"] == [signal.payload]


async def test_drive_crossing_its_threshold_emits_pressure(tmp_path):
    """D1-75: un drive que cruza 0,7 con el paso del tiempo emite `pressure` (solo la señal)."""
    transport, _ = turn_transport("Ho", "la")
    clock = [NOW]
    async with LLMClient(EventBus(), transport=transport) as llm:
        orchestrator, bus = await make(tmp_path, llm, clock)
        orchestrator.state.drives = {"social": 0.695, "novelty": 0.0, "rest": 0.0}
        queue = bus.subscribe()
        clock[0] = NOW + timedelta(minutes=30)
        orchestrator.tick()
    signals = [e.payload for e in drain(queue) if e.type == "agent.signal"]

    assert [(s["agent"], s["kind"], s["target"]) for s in signals] == [("homeostasis_watch", "pressure", "social")]


async def test_without_memory_agents_still_run_without_repetition(tmp_path):
    """Sin memoria no hay embeddings: `repetition_watch` no puede comparar, pero el turno funciona."""
    transport, _ = turn_transport("Ho", "la", appraisal=DISTRESS_REPLY)
    async with LLMClient(EventBus(), transport=transport) as llm:
        orchestrator, bus = await make(tmp_path, llm, [NOW], memory=False)
        await say(orchestrator, "¿A qué ciudad fui el fin de semana?")
        queue = bus.subscribe()
        await say(orchestrator, "¿A qué ciudad fui el fin de semana?")
    kinds = [e.payload["kind"] for e in drain(queue) if e.type == "agent.signal"]

    assert kinds == ["attend_partner"]
