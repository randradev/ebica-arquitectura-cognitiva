"""
Pruebas de la pizarra en el turno (Fase 1, CP9 parte B), con LLM y memoria simulados.

Cubren que la alerta alta deja entrar menos al prompt (con `wm.evicted`), que lo
fijo nunca se desaloja, la sección 7 «Cómo expresarme» y el aviso `wm.overflow`.
"""

import re
from datetime import timedelta

import pytest
from fake_llm import NEUTRAL_APPRAISAL, drain, turn_transport

import ebica.core.orchestrator as orchestrator_module
from ebica.affect.vad import VAD
from ebica.core.events import EventBus
from ebica.core.orchestrator import Orchestrator
from ebica.core.state import ConversationTurn, EntityConfig
from ebica.entities.manager import EntityManager
from ebica.llm.client import LLMClient
from ebica.llm.prompt_assembler import EXPRESSION_HEADER, describe_expression
from ebica.memory.episodes import WrittenEpisode
from ebica.memory.retrieval import EpisodeCandidate, RetrievalResult, score_episode
from fake_embedder import FakeEmbedder

CONFIG = EntityConfig(id="prueba", name="Prueba", persona="Soy Prueba.", appraisal_profile="Prueba, artista.")
CALM = VAD(valence=0.0, arousal=0.4, dominance=0.5)
THREAT = VAD(valence=-0.8, arousal=1.0, dominance=0.1)


class FakeMemory:
    """Hace las veces de `MemoryWriter` (solo su embedder y una escritura que no falla)."""

    def __init__(self) -> None:
        """Embedder simulado para la consulta."""
        self.embedder = FakeEmbedder()

    async def write_turn(self, entity_id, **values):
        """Devuelve un episodio escrito cualquiera."""
        return WrittenEpisode(episode_id="ep-x", trace_id="tr-x", importance=0.0, topics=[], new_topics=[],
                              previous_episode_id=None, embed_ms=1.0, write_ms=1.0)


class ManyMemories:
    """Recuperador que devuelve 8 recuerdos largos (unos 160 tokens cada uno) con relevancias decrecientes."""

    async def retrieve(self, entity_id, query_vector, **values):
        """8 episodios de la semilla, el primero el más relevante; el tercero, doloroso."""
        now = values["now"]
        scored = []
        for index in range(8):
            candidate = EpisodeCandidate(
                id=f"ep-{index}", kind="seed", ts=now - timedelta(days=400), text=f"recuerdo{index} " + "palabra " * 100,
                valence=-0.9 if index == 2 else 0.0, arousal=0.5, importance=0.3, embedding=query_vector,
            )
            scored.append(score_episode(candidate, 0.9 - 0.05 * index, now, values["affect"]))
        return RetrievalResult(episodes=scored, facts=[], candidates=scored, k_effective=8)


async def turn_with(tmp_path, affect: VAD, text="hola", old_turns=0):
    """Un turno normal con el ánimo fijado antes; devuelve los eventos y el prompt de diálogo."""
    bus = EventBus()
    manager = EntityManager(tmp_path, bus)
    entity = manager.create(CONFIG)
    entity.state.recent_turns = [
        ConversationTurn(user=f"mensaje viejo {i}", entity=f"respuesta vieja {i}", ts=entity.state.created_at)
        for i in range(old_turns)
    ]
    transport, bodies = turn_transport("Ho", "la", appraisal=NEUTRAL_APPRAISAL)
    async with LLMClient(bus, transport=transport) as llm:
        orchestrator = Orchestrator(entity, bus, manager.save_state, llm=llm, memory=FakeMemory(),
                                    retriever=ManyMemories())
        orchestrator.wake()
        orchestrator.state.affect = affect
        queue = bus.subscribe()
        _ = [piece async for piece in orchestrator.user_turn(text)]
    events: dict[str, list] = {}
    for event in drain(queue):
        events.setdefault(event.type, []).append(event)
    dialogue = [body["messages"] for body in bodies if "response_format" not in body][-1]
    return events, dialogue


def prompt_text(messages) -> str:
    """Todo el prompt de diálogo como un texto."""
    return "\n".join(message["content"] for message in messages)


async def test_high_arousal_lets_less_into_the_prompt(tmp_path):
    """§5.4, D1-62: en calma entran los 8 recuerdos; bajo amenaza, menos, y queda `wm.evicted`."""
    calm_events, calm_prompt = await turn_with(tmp_path / "calma", CALM)
    threat_events, threat_prompt = await turn_with(tmp_path / "amenaza", THREAT)

    calm, threat = calm_events["wm.updated"][0].payload, threat_events["wm.updated"][0].payload
    assert calm["budget"] == 2500 and calm["evicted"] == [] and "wm.evicted" not in calm_events
    assert threat["budget"] < calm["budget"] and threat["used"] <= threat["budget"]
    assert len(threat["kept"]) < len(calm["kept"])
    evicted = threat_events["wm.evicted"][0]
    assert evicted.cause_id == threat_events["wm.updated"][0].id
    assert all(f"recuerdo{i} " in prompt_text(calm_prompt) for i in range(8))
    kept_threat = [i for i in range(8) if f"recuerdo{i} " in prompt_text(threat_prompt)]
    assert 0 in kept_threat and 2 in kept_threat  # el más relevante y el doloroso (|valencia| alta) ganan
    assert threat_events["turn.completed"][0].payload["workspace"]["evicted"] == evicted.payload["items"]


async def test_fixed_parts_are_never_evicted(tmp_path, monkeypatch):
    """D1-61: con presupuesto 0 sale todo lo desalojable, pero no quién soy, el estado, la forma ni el último intercambio."""
    monkeypatch.setattr(orchestrator_module, "workspace_budget", lambda arousal: 0)

    events, prompt = await turn_with(tmp_path, CALM, text="mensaje actual", old_turns=4)

    text = prompt_text(prompt)
    assert "recuerdo" not in text
    assert "mensaje viejo 0" not in text and "mensaje viejo 2" not in text
    assert "mensaje viejo 3" in text and "respuesta vieja 3" in text  # el último intercambio
    assert prompt[0]["content"].startswith("Eres Prueba.") and EXPRESSION_HEADER in prompt[0]["content"]
    assert prompt[-1] == {"role": "user", "content": "mensaje actual"}
    assert len(events["wm.evicted"][0].payload["items"]) == 8 + 3


@pytest.mark.parametrize(
    ("affect", "expected"),
    [
        (THREAT, "Respondo corto, una o dos frases; no me extiendo. Hablo con cautela."),
        (VAD(valence=0.6, arousal=0.5, dominance=0.6), "Me puedo extender un poco y asociar ideas, sin irme por las ramas."),
        (CALM, "Respondo con naturalidad, en pocas frases."),
        (VAD(valence=0.0, arousal=0.4, dominance=0.1), "Respondo con naturalidad, en pocas frases. Hablo con cautela."),
    ],
)
def test_expression_section_in_words(affect, expected):
    """D1-64: la sección 7 sale del estado, en palabras y sin números."""
    text = describe_expression(affect)
    assert text == expected and not re.search(r"\d", text)


async def test_expression_section_goes_last_in_the_system_prompt(tmp_path):
    """La sección 7 va al final del sistema, antes de la conversación."""
    _, prompt = await turn_with(tmp_path, THREAT)

    assert prompt[0]["content"].endswith(f"{EXPRESSION_HEADER}\nRespondo corto, una o dos frases; no me extiendo. Hablo con cautela.")


async def test_huge_message_raises_an_overflow_warning(tmp_path):
    """Un mensaje enorme hace que el prompt no quepa en 8.192 − max_tokens: queda `wm.overflow` (no se recorta)."""
    events, prompt = await turn_with(tmp_path, CALM, text="palabra " * 6000)

    [overflow] = events["wm.overflow"]
    assert overflow.payload["limit"] == 8192 - 400 and overflow.payload["estimated_tokens"] > overflow.payload["limit"]
    assert overflow.cause_id == events["wm.updated"][0].id
    assert "wm.overflow" not in (await turn_with(tmp_path / "normal", CALM))[0]
