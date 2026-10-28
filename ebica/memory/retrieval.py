"""
Recuperación híbrida de la memoria (documento base §7.3; Fase 1, CP7).

Antes de responder, la entidad «se acuerda» de lo que viene al caso:
1. Candidatos: los episodios y hechos más parecidos al mensaje (índice
   vectorial) y los episodios sobre los temas que detectó el appraisal (el
   grafo, a un salto). `Person` se suma en CP8.
2. Puntaje de cada episodio (§7.3, D1-44): parecido, recencia, importancia,
   congruencia con el ánimo y compromisos abiertos (0 hasta CP10).
3. Selección: MMR hasta k episodios (k según la apertura O y el ánimo, D1-47)
   y, aparte, hasta `FACTS_MAX` hechos solo por parecido (D1-45).
4. Efecto: lo evocado sube su labilidad (D1-48), la marca que usará la
   reinscripción del sueño (Fase 2). En Fase 1 no se reescribe nada.

Este módulo elige qué recordar; cómo se dice en el prompt (tiempo y tono en
palabras, tope de tokens) es tarea del Prompt Assembler.
"""

import math
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from ebica.affect.vad import VAD
from ebica.memory.graph import GraphStore

# CONSTANTES: pesos del puntaje de §7.3 (D1-44, iniciales; se ajustan con `dev`).
W_SIMILARITY = 0.5
W_RECENCY = 0.15
W_IMPORTANCE = 0.15
W_MOOD = 0.1
# Peso de los compromisos abiertos; el término vale 0 hasta CP10 (no hay `Commitment`).
W_COMMITMENT = 0.1
# CONSTANTE: vida media de la recencia (D1-44). Un recuerdo de hace 3 días
# conserva la mitad de su bono de recencia; los de la semilla (2025) casi nada.
RECENCY_HALF_LIFE_SECONDS = 3 * 24 * 3600
# CONSTANTE: coseno mínimo para ser candidato (D1-44). El plan proponía 0,45;
# ajustado con `dev` a 0,50: el acierto más bajo dio 0,516 («¿Y cómo crees que
# va el quiltro?») y el control más alto 0,487 («Ok» con un hecho cualquiera).
# Margen estrecho: bge-m3 da ~0,45–0,49 a frases sin relación.
SIMILARITY_FLOOR = 0.50
# CONSTANTE: hechos como máximo, aparte de los k episodios (D1-45).
FACTS_MAX = 3
# CONSTANTES: candidatos pedidos al índice vectorial por etiqueta. Más que k,
# para que el puntaje y MMR tengan dónde elegir.
EPISODE_CANDIDATES = 20
FACT_CANDIDATES = 10
# CONSTANTES: k según el ánimo (D1-47, §5.4). Bajo amenaza (alerta alta y
# valencia negativa) la atención se estrecha; con buen ánimo se abre.
THREAT_AROUSAL, THREAT_VALENCE, GOOD_MOOD_VALENCE = 0.6, -0.1, 0.3
K_MIN = 2
# CONSTANTES: aumento de la labilidad al evocar (D1-48): una base, más la
# discrepancia entre el afecto del recuerdo y el actual.
LABILITY_BASE, LABILITY_DISCREPANCY = 0.1, 0.2


# ------------------------------------------------------------ funciones puras


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Coseno entre dos vectores (los embeddings se guardan con norma 1, pero no se asume)."""
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def recency(ts: datetime, now: datetime) -> float:
    """Bono de recencia en [0, 1]: 1 ahora, 0,5 tras una vida media, tiende a 0."""
    elapsed = max(0.0, (now - ts).total_seconds())
    return 0.5 ** (elapsed / RECENCY_HALF_LIFE_SECONDS)


def mood_congruence(memory_valence: float, current_valence: float) -> float:
    """
    Congruencia con el ánimo en [0, 1] (recuerdo congruente con el ánimo, Damasio/Bower).

    1 si el recuerdo tiene la misma valencia que el ánimo actual; 0 si son
    opuestos extremos (−1 frente a +1). Así, triste, se recuerda más lo triste.
    """
    return 1.0 - abs(memory_valence - current_valence) / 2.0


def effective_k(k: int, affect: VAD) -> int:
    """
    Cuántos episodios recordar según el ánimo (D1-47, §5.4).

    Calisto (k = 8): 4 bajo amenaza (alerta ≥ 0,6 y valencia < −0,1), 9 de
    buen ánimo (valencia > 0,3), 8 en otro caso.
    """
    if affect.arousal >= THREAT_AROUSAL and affect.valence < THREAT_VALENCE:
        return max(K_MIN, round(k / 2))
    if affect.valence > GOOD_MOOD_VALENCE:
        return k + 1
    return k


def lability_increment(memory_valence: float, current_valence: float) -> float:
    """Cuánto sube la labilidad de un recuerdo evocado (D1-48): 0,1 a 0,3."""
    return LABILITY_BASE + LABILITY_DISCREPANCY * abs(memory_valence - current_valence) / 2.0


@dataclass
class EpisodeCandidate:
    """Un episodio candidato, con lo que el puntaje necesita."""

    id: str
    kind: str
    ts: datetime
    text: str
    valence: float
    arousal: float
    importance: float
    embedding: list[float]
    # Por qué entró: "vector", "topic" o ambos.
    sources: set[str] = field(default_factory=set)


@dataclass
class ScoredEpisode:
    """Un episodio con su puntaje y el desglose (para la consola y el benchmark)."""

    candidate: EpisodeCandidate
    similarity: float
    recency: float
    importance: float
    mood: float
    commitment: float
    total: float

    def as_dict(self) -> dict:
        """Versión JSON, sin el embedding ni el texto completo."""
        c = self.candidate
        return {
            "id": c.id, "kind": c.kind, "sources": sorted(c.sources),
            "similarity": round(self.similarity, 3), "recency": round(self.recency, 3),
            "importance": round(self.importance, 3), "mood": round(self.mood, 3),
            "commitment": self.commitment, "total": round(self.total, 3),
        }


def score_episode(candidate: EpisodeCandidate, similarity: float, now: datetime, affect: VAD) -> ScoredEpisode:
    """Puntaje de §7.3 con su desglose (D1-44). El término de compromisos vale 0 hasta CP10."""
    rec = recency(candidate.ts, now)
    mood = mood_congruence(candidate.valence, affect.valence)
    commitment = 0.0
    total = (
        W_SIMILARITY * similarity + W_RECENCY * rec + W_IMPORTANCE * candidate.importance
        + W_MOOD * mood + W_COMMITMENT * commitment
    )
    return ScoredEpisode(candidate, similarity, rec, candidate.importance, mood, commitment, total)


def mmr(scored: list[ScoredEpisode], k: int, lambda_mmr: float) -> list[ScoredEpisode]:
    """
    Selección por relevancia marginal máxima (MMR), hasta `k`.

    En cada paso elige el que maximiza `λ·puntaje − (1 − λ)·parecido con lo ya
    elegido`. Con λ bajo (apertura alta) prefiere variedad; con λ alto, lo más
    relevante aunque se repita. Evita traer dos versiones del mismo recuerdo.
    """
    pool = list(scored)
    selected: list[ScoredEpisode] = []
    while pool and len(selected) < k:
        def value(item: ScoredEpisode) -> float:
            """Valor MMR de un candidato frente a lo ya elegido."""
            redundancy = max(
                (cosine(item.candidate.embedding, chosen.candidate.embedding) for chosen in selected),
                default=0.0,
            )
            return lambda_mmr * item.total - (1.0 - lambda_mmr) * redundancy

        best = max(pool, key=value)
        selected.append(best)
        pool.remove(best)
    return selected


# ------------------------------------------------------------ resultado


@dataclass
class RetrievedFact:
    """Un hecho recuperado y su parecido con el mensaje."""

    id: str
    text: str
    similarity: float

    def as_dict(self) -> dict:
        """Versión JSON."""
        return {"id": self.id, "similarity": round(self.similarity, 3)}


@dataclass
class RetrievalResult:
    """Lo que la entidad recordó en un turno, y por qué (para `memory.retrieved`)."""

    episodes: list[ScoredEpisode]
    facts: list[RetrievedFact]
    # Todos los episodios que pasaron el umbral, elegidos o no, con su desglose.
    candidates: list[ScoredEpisode]
    k_effective: int
    elapsed_ms: float = 0.0

    def as_dict(self) -> dict:
        """Versión JSON para el evento."""
        return {
            "episodes": [item.as_dict() for item in self.episodes],
            "facts": [item.as_dict() for item in self.facts],
            "candidates": [item.as_dict() for item in self.candidates],
            "k_effective": self.k_effective,
            "elapsed_ms": round(self.elapsed_ms, 1),
        }


# ------------------------------------------------------------ consultas

# Propiedades de los episodios candidatos. Excluye lo bloqueado (§7.3) y los
# episodios de diálogo desde `since`: esos intercambios ya están literales en
# la conversación reciente (D1-46). La semilla nunca se excluye por fecha.
_EPISODES = """
MATCH (e:Episode {entity_id: $entity_id})
WHERE e.id IN $ids AND coalesce(e.access, 'open') <> 'blocked'
  AND ($since IS NULL OR e.kind = 'seed' OR e.ts < $since)
RETURN e.id AS id, e.kind AS kind, e.ts AS ts, e.text AS text, e.valence AS valence,
       e.arousal AS arousal, coalesce(e.importance, 0.0) AS importance, e.embedding AS embedding
"""

_TOPIC_NEIGHBOURS = """
MATCH (t:Topic {entity_id: $entity_id})<-[:ABOUT]-(e:Episode {entity_id: $entity_id})
WHERE t.name IN $topics
RETURN DISTINCT e.id AS id
"""

_FACTS = """
MATCH (f:Fact {entity_id: $entity_id})
WHERE f.id IN $ids AND NOT f.id IN $excluded
RETURN f.id AS id, f.text AS text, f.embedding AS embedding
"""

_RAISE_LABILITY = """
UNWIND $rows AS r
MATCH (e:Episode {entity_id: $entity_id, id: r.id})
SET e.lability = CASE WHEN coalesce(e.lability, 0.0) + r.delta > 1.0 THEN 1.0
                      ELSE coalesce(e.lability, 0.0) + r.delta END,
    e.last_evoked_at = $now
"""


class MemoryRetriever:
    """Elige qué recuerdos y hechos entran al turno (§7.3)."""

    def __init__(self, graph: GraphStore) -> None:
        """Guarda el acceso al grafo; el vector del mensaje lo calcula quien llama."""
        self.graph = graph

    async def retrieve(
        self,
        entity_id: str,
        query_vector: list[float],
        *,
        affect: VAD,
        k: int,
        lambda_mmr: float,
        now: datetime,
        topics: Sequence[str] = (),
        since: datetime | None = None,
        excluded_fact_ids: Sequence[str] = (),
        raise_lability: bool = True,
    ) -> RetrievalResult:
        """
        Recupera hasta k episodios (k ajustado por el ánimo) y hasta `FACTS_MAX` hechos.

        `topics` son los temas normalizados del appraisal; `since` excluye los
        episodios de diálogo que ya están en la conversación reciente;
        `excluded_fact_ids`, los hechos esenciales que ya van en «Quién soy».
        Con `raise_lability=False` no escribe nada (el benchmark lo usa para
        poder repetir la medición).
        """
        started = time.perf_counter()
        vector_episodes = await self.graph.vector_search("Episode", entity_id, query_vector, k=EPISODE_CANDIDATES)
        topic_rows = await self.graph.execute(
            _TOPIC_NEIGHBOURS, entity_id=entity_id, topics=list(topics)
        ) if topics else []
        sources: dict[str, set[str]] = {}
        for row in vector_episodes:
            sources.setdefault(row["id"], set()).add("vector")
        for row in topic_rows:
            sources.setdefault(row["id"], set()).add("topic")

        rows = await self.graph.execute(_EPISODES, entity_id=entity_id, ids=list(sources), since=since)
        scored = []
        for row in rows:
            similarity = cosine(query_vector, row["embedding"])
            if similarity < SIMILARITY_FLOOR:
                continue
            candidate = EpisodeCandidate(
                id=row["id"], kind=row["kind"], ts=row["ts"].to_native(), text=row["text"],
                valence=row["valence"], arousal=row["arousal"], importance=row["importance"],
                embedding=row["embedding"], sources=sources[row["id"]],
            )
            scored.append(score_episode(candidate, similarity, now, affect))
        scored.sort(key=lambda item: item.total, reverse=True)
        k_eff = effective_k(k, affect)
        episodes = mmr(scored, k_eff, lambda_mmr)

        fact_ids = [row["id"] for row in await self.graph.vector_search("Fact", entity_id, query_vector, k=FACT_CANDIDATES)]
        fact_rows = await self.graph.execute(
            _FACTS, entity_id=entity_id, ids=fact_ids, excluded=list(excluded_fact_ids)
        ) if fact_ids else []
        facts = sorted(
            (RetrievedFact(row["id"], row["text"], cosine(query_vector, row["embedding"])) for row in fact_rows),
            key=lambda item: item.similarity, reverse=True,
        )
        facts = [fact for fact in facts if fact.similarity >= SIMILARITY_FLOOR][:FACTS_MAX]

        if raise_lability and episodes:
            await self.graph.execute(
                _RAISE_LABILITY, entity_id=entity_id, now=now,
                rows=[{"id": item.candidate.id,
                       "delta": lability_increment(item.candidate.valence, affect.valence)}
                      for item in episodes],
            )
        return RetrievalResult(
            episodes=episodes, facts=facts, candidates=scored, k_effective=k_eff,
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
