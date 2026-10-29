"""
Escritura de la memoria episódica (documento base §5.7, §7; Fase 1, CP6).

Dos operaciones, las únicas que escriben en vigilia (§7.1):
- `import_seed`: carga la biografía semilla de una entidad (`Self`, `Fact` de
  dominio `self` y `Episode` iniciales con su `Trace`). Es idempotente: cargar
  la entidad muchas veces no duplica nada (D1-39).
- `write_turn`: tras cada turno, un `Episode` (el recuerdo que la entidad
  evocará) y su `Trace` (la huella cruda, que la entidad nunca consulta), con
  los enlaces `NEXT`, `DERIVED_FROM` y `ABOUT` hacia los `Topic`. Desde CP8,
  también `INVOLVES` y `SPOKEN_BY` hacia el `Person` de quien habló, cuyo modelo
  se guarda en la misma transacción. Desde CP10, los `Commitment` que detectó
  el appraisal: `(:Person)-[:PROMISED]->(:Commitment)` y el episodio `ABOUT` de él.

Los hechos no se crean en vigilia (salvo la semilla): si el usuario cuenta
algo, la entidad lo recuerda a través del episodio hasta que el sueño de Fase 2
lo semantice. Los `Commitment` sí se crean en vigilia (§7.1: una promesa debe
poder recordarse antes del próximo sueño). Crear y leer las `Person` es tarea
de `people.py` (CP8). Recuperar lo escrito es trabajo de CP7.
"""

import hashlib
import json
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from ebica.affect.vad import VAD
from ebica.identity.biography import SeedBiography, SeedEpisode, SeedFact
from ebica.memory.graph import GraphStore
from ebica.perception.appraisal import Appraisal
from ebica.perception.embeddings import Embedder

if TYPE_CHECKING:
    # Solo para los tipos: `social.partner` importa `normalize_topics` de este módulo.
    from ebica.social.partner import PartnerModel

# CONSTANTE: largo máximo de la respuesta dentro del texto del episodio (D1-35).
# El recuerdo guarda lo esencial; la huella guarda la respuesta completa.
RESPONSE_MAX_CHARS = 600
# CONSTANTE: máximo de temas enlazados por episodio. El appraisal suele dar
# 1–3; el tope evita que una respuesta desbordada llene el grafo de temas.
MAX_TOPICS_PER_EPISODE = 5
# CONSTANTES: pesos de la importancia de un episodio (D1-36, calibrables).
# Suman 1, así que la importancia queda en [0, 1].
IMPORTANCE_SELF_RELEVANCE = 0.4
IMPORTANCE_GOAL_CONGRUENCE = 0.3
IMPORTANCE_INTENSITY = 0.3

# `kind` de los episodios de la semilla. §7.2 solo prevé dialogue, thought,
# initiative y dream; los recuerdos de origen no son ninguno de ellos
# (desviación menor, como `Revision.episode_id` en D1-9).
SEED_KIND = "seed"
DIALOGUE_KIND = "dialogue"


# ------------------------------------------------------------ funciones puras


def episode_text(
    user_text: str, entity_text: str, limit: int | None = RESPONSE_MAX_CHARS, speaker: str | None = None
) -> str:
    """
    Texto de un episodio de diálogo (D1-35, D1-56): quién me dijo qué y qué respondí.

    Va en primera persona porque es el recuerdo de la entidad. Con `speaker`,
    dice quién habló («Ricardo me dijo: …»): así, al recordarlo, la entidad
    sabe que la experiencia contada es de esa persona y no suya (la confusión
    de la fuente de CP7 C). Sin él (memoria sin personas), «Me dijeron». Con
    `limit`, la respuesta se recorta (el recuerdo); con `None`, queda completa
    (la huella).
    """
    response = entity_text.strip()
    if limit is not None and len(response) > limit:
        response = response[:limit].rstrip() + "…"
    if speaker:
        return f"{speaker} me dijo: «{user_text.strip()}»\nLe respondí: «{response}»"
    return f"Me dijeron: «{user_text.strip()}»\nRespondí: «{response}»"


def episode_importance(appraisal: Appraisal) -> float:
    """
    Importancia de un episodio a partir del appraisal (D1-36).

    Lo que toca a la entidad (`self_relevance`), lo que favorece o frustra lo
    que quiere (|`goal_congruence`|) y la carga del mensaje (hostilidad o
    angustia) hacen un recuerdo más importante. Ej.: «hola, ¿cómo estás?» ≈
    0,14; «eres una inútil» ≈ 0,89. CP7 la usa en el puntaje de recuperación.
    """
    intensity = max(appraisal.hostility, appraisal.distress)
    value = (
        IMPORTANCE_SELF_RELEVANCE * appraisal.self_relevance
        + IMPORTANCE_GOAL_CONGRUENCE * abs(appraisal.goal_congruence)
        + IMPORTANCE_INTENSITY * intensity
    )
    return min(1.0, max(0.0, value))


def _singular(word: str) -> str:
    """
    Singular simple y conservador: solo las terminaciones casi siempre seguras.

    «pianos» → «piano», «gatas» → «gata», «canciones» → «cancion». No toca
    «series», «crisis», «padres» ni «flores»: sin un léxico no se puede saber
    el singular, y un error fusionaría temas distintos. Los sinónimos y
    plurales que queden separados los fusiona el sueño (Fase 2).
    """
    if len(word) > 5 and word.endswith("ones"):
        return word[:-2]
    if len(word) > 4 and word.endswith(("os", "as")):
        return word[:-1]
    return word


def normalize_topic(name: str) -> str:
    """
    Nombre canónico de un tema: minúsculas, singular simple, sin tildes y espacios simples.

    El singular se aplica *antes* de quitar las tildes (D1-68): una palabra con
    la última vocal acentuada («adiós», «compás») no es un plural, y sin la
    tilde se confundía con uno («adios» → «adio»).
    """
    words = unicodedata.normalize("NFC", name.lower()).split()
    singular = " ".join(_singular(word) for word in words)
    decomposed = unicodedata.normalize("NFD", singular)
    # Se quitan las tildes, pero no la virgulilla de la ñ (como en la vía baja).
    without_accents = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn" or char == "̃"
    )
    return unicodedata.normalize("NFC", without_accents)


def normalize_topics(names: list[str]) -> list[str]:
    """Normaliza, descarta vacíos y repetidos (conservando el orden) y aplica el tope."""
    result: list[str] = []
    for name in names:
        topic = normalize_topic(name)
        if topic and topic not in result:
            result.append(topic)
    return result[:MAX_TOPICS_PER_EPISODE]


def commitment_key(text: str) -> str:
    """
    Forma comparable de un compromiso (D1-73): minúsculas, sin tildes, sin
    puntuación y con espacios simples. «Mañana te cuento cómo me fue.» y
    «mañana te cuento como me fue» son la misma promesa.
    """
    decomposed = unicodedata.normalize("NFD", text.lower())
    plain = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return " ".join("".join(char if char.isalnum() else " " for char in plain).split())


def commitment_id(person_id: str | None, text: str) -> str:
    """
    Id estable de un compromiso: la misma promesa de la misma persona da el
    mismo id, así que repetirla no la duplica (D1-73).
    """
    return f"cm-{content_hash(person_id or '-', commitment_key(text))[:12]}"


def content_hash(*parts: object) -> str:
    """
    Huella del contenido de un nodo de la semilla (D1-39).

    Si cambia el texto (o el afecto de un episodio) en `config.yaml`, la huella
    cambia y el nodo se actualiza al cargar, con su embedding nuevo.
    """
    payload = json.dumps([str(part) for part in parts], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _fact_hash(fact: SeedFact) -> str:
    """Huella de un hecho de la semilla: solo su texto (`core` no cambia el nodo)."""
    return content_hash(fact.text)


def _episode_hash(episode: SeedEpisode) -> str:
    """Huella de un episodio de la semilla: texto, fecha y afecto con que se recuerda."""
    return content_hash(
        episode.text, episode.ts.isoformat(), episode.valence, episode.arousal,
        episode.dominance, episode.importance,
    )


def _trace_id(episode_id: str) -> str:
    """Id de la huella de un episodio: el mismo sufijo, para encontrarlas juntas en Neo4j Browser."""
    return f"tr-{episode_id.removeprefix('ep-')}"


# ------------------------------------------------------------ resultados


@dataclass
class SeedImportReport:
    """Qué hizo una importación de la semilla (para el evento `memory.seed_imported`)."""

    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: int = 0
    # Ids de la semilla que están en Neo4j pero ya no en `config.yaml`: no se
    # borran (Fase 2 podría haberlos enlazado), solo se informan (D1-39).
    orphaned: list[str] = field(default_factory=list)
    embed_ms: float = 0.0
    write_ms: float = 0.0

    def as_dict(self) -> dict:
        """Versión JSON para el evento."""
        return {
            "created": len(self.created), "updated": self.updated, "unchanged": self.unchanged,
            "orphaned": self.orphaned, "embed_ms": round(self.embed_ms, 1),
            "write_ms": round(self.write_ms, 1),
        }


@dataclass
class WrittenEpisode:
    """Lo que escribió un turno (para el evento `memory.written`)."""

    episode_id: str
    trace_id: str
    importance: float
    topics: list[str]
    new_topics: list[str]
    previous_episode_id: str | None
    embed_ms: float
    write_ms: float
    # Ids de los compromisos del turno (creados o ya existentes), CP10.
    commitments: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        """Versión JSON para el evento."""
        return {
            "episode_id": self.episode_id, "trace_id": self.trace_id,
            "importance": round(self.importance, 3), "topics": self.topics,
            "new_topics": self.new_topics, "previous_episode_id": self.previous_episode_id,
            "commitments": self.commitments,
            "embed_ms": round(self.embed_ms, 1), "write_ms": round(self.write_ms, 1),
        }


# ------------------------------------------------------------ escritura

# Datos comunes de un episodio recién vivido o sembrado (§7.2): todavía no se
# evocó (lability 0), no está bloqueado y es su primera versión.
_NEW_EPISODE_PROPS = "confidence: 1.0, lability: 0.0, access: 'open', tension: 0.0, version: 1"

_UPSERT_FACTS = """
UNWIND $rows AS r
MERGE (f:Fact {entity_id: $entity_id, id: r.id})
SET f.text = r.text, f.embedding = r.embedding, f.content_hash = r.hash,
    f.confidence = 1.0, f.domain = 'self', f.source = 'seed'
"""

_UPSERT_SEED_EPISODES = f"""
UNWIND $rows AS r
MERGE (e:Episode {{entity_id: $entity_id, id: r.id}})
ON CREATE SET e += {{{_NEW_EPISODE_PROPS}}}
SET e.ts = r.ts, e.kind = '{SEED_KIND}', e.source = 'seed', e.summary = r.text, e.text = r.text,
    e.embedding = r.embedding, e.valence = r.valence, e.arousal = r.arousal,
    e.dominance = r.dominance, e.importance = r.importance, e.content_hash = r.hash
MERGE (t:Trace {{entity_id: $entity_id, id: r.trace_id}})
SET t.ts = r.ts, t.raw_text = r.text, t.raw_affect_json = r.affect_json, t.appraisal_json = null
MERGE (e)-[:DERIVED_FROM]->(t)
"""

# Rehace la cadena NEXT entre los episodios de la semilla, por fecha. Solo
# toca los enlaces entre dos episodios de la semilla: el que une el último
# recuerdo de origen con la primera conversación se crea al escribir esa
# conversación y no se modifica aquí.
_RELINK_SEED_EPISODES = """
MATCH (:Episode {entity_id: $entity_id, source: 'seed'})-[n:NEXT]->(:Episode {entity_id: $entity_id, source: 'seed'})
DELETE n
WITH count(*) AS removed
MATCH (e:Episode {entity_id: $entity_id, source: 'seed'})
WITH e ORDER BY e.ts
WITH collect(e) AS episodes
UNWIND range(0, size(episodes) - 2) AS i
WITH episodes[i] AS earlier, episodes[i + 1] AS later
CREATE (earlier)-[:NEXT]->(later)
"""

# Un turno en una sola consulta, que Neo4j ejecuta como una transacción: o se
# escribe todo (episodio, huella, enlaces y temas) o nada.
_WRITE_TURN = f"""
OPTIONAL MATCH (previous:Episode {{entity_id: $entity_id}})
WITH previous ORDER BY previous.ts DESC LIMIT 1
CREATE (e:Episode {{entity_id: $entity_id, id: $episode_id, ts: $ts, kind: '{DIALOGUE_KIND}',
                   summary: $text, text: $text, embedding: $embedding,
                   valence: $valence, arousal: $arousal, dominance: $dominance,
                   importance: $importance, {_NEW_EPISODE_PROPS}}})
CREATE (t:Trace {{entity_id: $entity_id, id: $trace_id, ts: $ts, raw_text: $raw_text,
                 raw_affect_json: $affect_json, appraisal_json: $appraisal_json, route: $route}})
CREATE (e)-[:DERIVED_FROM]->(t)
FOREACH (p IN CASE WHEN previous IS NULL THEN [] ELSE [previous] END | CREATE (p)-[:NEXT]->(e))
FOREACH (topic IN $topics |
    MERGE (tp:Topic {{entity_id: $entity_id, name: topic.name}})
    ON CREATE SET tp.embedding = topic.embedding, tp.n = 0
    SET tp.n = tp.n + 1
    MERGE (e)-[:ABOUT]->(tp))
FOREACH (person IN CASE WHEN $person IS NULL THEN [] ELSE [$person] END |
    MERGE (p:Person {{entity_id: $entity_id, id: person.id}})
    SET p += person.props
    CREATE (e)-[:INVOLVES]->(p)
    CREATE (t)-[:SPOKEN_BY]->(p))
FOREACH (c IN $commitments |
    MERGE (cm:Commitment {{entity_id: $entity_id, id: c.id}})
    ON CREATE SET cm.text = c.text, cm.key = c.key, cm.status = 'open', cm.ts = $ts, cm.due = null
    MERGE (e)-[:ABOUT]->(cm)
    FOREACH (pid IN CASE WHEN $person IS NULL THEN [] ELSE [$person.id] END |
        MERGE (owner:Person {{entity_id: $entity_id, id: pid}})
        MERGE (owner)-[:PROMISED]->(cm)))
RETURN previous.id AS previous_id
"""


def _affect_json(valence: float, arousal: float, dominance: float) -> str:
    """El afecto como JSON, para la huella (la entidad no la consulta; la consola sí)."""
    return json.dumps({"valence": valence, "arousal": arousal, "dominance": dominance})


class MemoryWriter:
    """
    Escribe en Neo4j lo que la entidad vive y lo que trae de origen.

    Usa el `GraphStore` (consultas) y el `Embedder` (vectores). Comprueba la
    dimensión de cada vector antes de escribir: Neo4j acepta un vector de otra
    dimensión sin error y lo deja fuera del índice, invisible para la búsqueda
    (sondeado en CP2).
    """

    def __init__(self, graph: GraphStore, embedder: Embedder) -> None:
        """Guarda el acceso al grafo y el embedder; no se conecta todavía."""
        self.graph = graph
        self.embedder = embedder

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        """Embeddings de textos que se guardan para ser encontrados; falla si la dimensión no es la esperada."""
        if not texts:
            return []
        vectors = await self.embedder.embed(texts, "passage")
        wrong = {len(vector) for vector in vectors if len(vector) != self.embedder.dimension}
        if wrong:
            raise ValueError(
                f"El embedder devolvió vectores de dimensión {sorted(wrong)}, "
                f"se esperaba {self.embedder.dimension}: no se escribe nada"
            )
        return vectors

    async def import_seed(self, entity_id: str, name: str, biography: SeedBiography) -> SeedImportReport:
        """
        Importa la biografía semilla de forma idempotente (D1-39).

        Crea los nodos que faltan, actualiza los que cambiaron en
        `config.yaml` (con embedding nuevo) y deja igual el resto. Solo calcula
        embeddings de lo creado o cambiado, así que una carga sin cambios es
        rápida. Los ids que desaparecieron de la configuración se informan,
        no se borran.
        """
        report = SeedImportReport()
        existing = {
            row["id"]: row["hash"]
            for row in await self.graph.execute(
                "MATCH (n {entity_id: $entity_id, source: 'seed'}) WHERE n:Fact OR n:Episode "
                "RETURN n.id AS id, n.content_hash AS hash",
                entity_id=entity_id,
            )
        }
        facts = [(fact, _fact_hash(fact)) for fact in biography.facts]
        episodes = [(episode, _episode_hash(episode)) for episode in biography.episodes]
        pending_facts = [(fact, digest) for fact, digest in facts if existing.get(fact.id) != digest]
        pending_episodes = [(ep, digest) for ep, digest in episodes if existing.get(ep.id) != digest]
        for item, _ in [*pending_facts, *pending_episodes]:
            (report.updated if item.id in existing else report.created).append(item.id)
        report.unchanged = len(facts) + len(episodes) - len(pending_facts) - len(pending_episodes)
        configured = {item.id for item, _ in [*facts, *episodes]}
        report.orphaned = sorted(set(existing) - configured)

        started = time.perf_counter()
        vectors = await self._embed([item.text for item, _ in [*pending_facts, *pending_episodes]])
        report.embed_ms = (time.perf_counter() - started) * 1000
        fact_vectors, episode_vectors = vectors[: len(pending_facts)], vectors[len(pending_facts):]

        started = time.perf_counter()
        await self.graph.execute(
            "MERGE (s:Self {entity_id: $entity_id}) SET s.name = $name", entity_id=entity_id, name=name
        )
        if pending_facts:
            await self.graph.execute(
                _UPSERT_FACTS, entity_id=entity_id,
                rows=[{"id": fact.id, "text": fact.text, "embedding": vector, "hash": digest}
                      for (fact, digest), vector in zip(pending_facts, fact_vectors)],
            )
        if pending_episodes:
            await self.graph.execute(
                _UPSERT_SEED_EPISODES, entity_id=entity_id,
                rows=[{"id": ep.id, "trace_id": _trace_id(ep.id), "ts": ep.ts, "text": ep.text,
                       "embedding": vector, "valence": ep.valence, "arousal": ep.arousal,
                       "dominance": ep.dominance, "importance": ep.importance, "hash": digest,
                       "affect_json": _affect_json(ep.valence, ep.arousal, ep.dominance)}
                      for (ep, digest), vector in zip(pending_episodes, episode_vectors)],
            )
            # Una fecha nueva o un episodio nuevo pueden cambiar el orden.
            await self.graph.execute(_RELINK_SEED_EPISODES, entity_id=entity_id)
        report.write_ms = (time.perf_counter() - started) * 1000
        return report

    async def write_turn(
        self,
        entity_id: str,
        *,
        ts: datetime,
        user_text: str,
        entity_text: str,
        affect: VAD,
        appraisal: Appraisal,
        impulsive: bool = False,
        person: "PartnerModel | None" = None,
    ) -> WrittenEpisode:
        """
        Escribe el recuerdo y la huella de un turno (§6.2, post-turno).

        `affect` es el ánimo tras el turno: el afecto con que se vivió y con el
        que se recordará (lo que la reinscripción de Fase 2 podrá ir moviendo).
        El episodio se enlaza con `NEXT` desde el más reciente de la entidad
        (el último de la semilla, si es la primera conversación) y con `ABOUT`
        hacia los temas del appraisal; los temas nuevos se crean con su
        embedding y los existentes suman una aparición (`n`).

        `person` es el modelo de quien habló, *ya actualizado* con este turno
        (lo calcula `social.partner`): el episodio lleva su nombre (D1-56), se
        enlaza con `INVOLVES` y la huella con `SPOKEN_BY` (en Fase 1 coinciden;
        en Fase 2, con el modo Desconocido, pueden diferir), y el `Person` se
        guarda en la misma transacción (D1-54). Sin `person`, nada de eso.

        Los compromisos del appraisal se crean en la misma transacción (CP10,
        D1-73): abiertos, con `PROMISED` desde la persona (sin persona, sin ese
        enlace) y el episodio `ABOUT` de cada uno. Una promesa repetida (mismo
        texto normalizado, misma persona) no se duplica: el episodio nuevo se
        enlaza a la que ya existe.
        """
        # Importación diferida: `people` importa `social.partner`, que importa este módulo.
        from ebica.memory.people import person_properties

        episode_id = f"ep-{uuid.uuid4().hex[:12]}"
        speaker = person.name if person is not None else None
        text = episode_text(user_text, entity_text, speaker=speaker)
        topics = normalize_topics(appraisal.topics)
        known = {
            row["name"]
            for row in await self.graph.execute(
                "MATCH (t:Topic {entity_id: $entity_id}) WHERE t.name IN $names RETURN t.name AS name",
                entity_id=entity_id, names=topics,
            )
        } if topics else set()
        new_topics = [topic for topic in topics if topic not in known]

        started = time.perf_counter()
        # Un solo lote: el texto del episodio y los temas nuevos.
        vectors = await self._embed([text, *new_topics])
        embed_ms = (time.perf_counter() - started) * 1000
        topic_vectors = dict(zip(new_topics, vectors[1:]))

        importance = episode_importance(appraisal)
        person_id = person.id if person is not None else None
        commitments = []
        for text_ in appraisal.commitments:
            if commitment_key(text_) and commitment_id(person_id, text_) not in {c["id"] for c in commitments}:
                commitments.append({"id": commitment_id(person_id, text_), "text": text_.strip(),
                                    "key": commitment_key(text_)})
        started = time.perf_counter()
        rows = await self.graph.execute(
            _WRITE_TURN, entity_id=entity_id, episode_id=episode_id, trace_id=_trace_id(episode_id),
            ts=ts, text=text, embedding=vectors[0],
            valence=affect.valence, arousal=affect.arousal, dominance=affect.dominance,
            importance=importance,
            raw_text=episode_text(user_text, entity_text, limit=None, speaker=speaker),
            affect_json=_affect_json(affect.valence, affect.arousal, affect.dominance),
            appraisal_json=appraisal.model_dump_json(),
            route="impulsive" if impulsive else "normal",
            topics=[{"name": topic, "embedding": topic_vectors.get(topic)} for topic in topics],
            person={"id": person.id, "props": person_properties(person)} if person is not None else None,
            commitments=commitments,
        )
        write_ms = (time.perf_counter() - started) * 1000
        return WrittenEpisode(
            episode_id=episode_id, trace_id=_trace_id(episode_id), importance=importance,
            topics=topics, new_topics=new_topics, previous_episode_id=rows[0]["previous_id"],
            embed_ms=embed_ms, write_ms=write_ms, commitments=[c["id"] for c in commitments],
        )
