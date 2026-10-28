"""
PartnerModel, parte de Fase 1 (documento base §5.9; CP8).

Cada persona con la que la entidad habla tiene su propio modelo, separado del
self y del de las demás personas:
- `PartnerNow`: cómo parece estar quien habla *en este turno* (emoción,
  intención, foco), leído del appraisal. No se guarda: es percepción.
- `PartnerModel`: lo que la entidad sabe de esa persona a lo largo del tiempo
  (cuántas veces hablaron, su emoción típica, de qué suele hablar, qué temas le
  duelen, cuánto confía en ella). Vive en el nodo `Person` de Neo4j.

Este módulo solo calcula; leer y escribir el `Person` es tarea de la memoria
(`ebica/memory/people.py` y `MemoryWriter.write_turn`). Fuera de Fase 1: rasgos,
preferencias y estilo estimados con el LLM (sueño, Fase 2), personas ausentes y
modo Desconocido (Fase 2), y `partner_mismatch` (Fase 3).
"""

import re
import unicodedata
from datetime import datetime

from pydantic import BaseModel, Field

from ebica.identity.biography import SEED_ID_PATTERN, PrimaryPerson
from ebica.memory.episodes import normalize_topics
from ebica.perception.appraisal import Appraisal

# CONSTANTE: peso del turno nuevo en la media móvil de la emoción observada
# (D1-54, calibrable). Con 0,2, la emoción típica de alguien se mueve poco
# por un mal día, pero sigue un cambio que dura varias conversaciones.
EMOTION_EMA_ALPHA = 0.2
# CONSTANTE: angustia desde la que los temas del mensaje cuentan como
# sensibles para esa persona (D1-54): «del trabajo le cuesta hablar».
SENSITIVE_DISTRESS = 0.6
# CONSTANTES: cuántos temas se muestran (D1-54) y cuántos se guardan. Se
# guardan más de los que se muestran para que un tema que vuelve pueda subir
# al top; el tope evita que el modelo crezca sin límite.
TOP_TOPICS, TOP_SENSITIVE = 5, 3
MAX_TRACKED_TOPICS = 30
# CONSTANTE: confianza inicial de una persona nueva (D1-55, calibrable). El
# `primary` trae la suya de la config (Calisto: 0,40). Sin dinámica en Fase 1.
NEW_PERSON_TRUST = 0.2


class DuplicatePersonError(ValueError):
    """Ya existe una persona con ese nombre (en Fase 1 no hay alias, D1-52)."""


class PartnerNow(BaseModel):
    """Cómo parece estar quien habla en este turno, según el appraisal (§5.9)."""

    valence: float
    arousal: float
    intent: str
    topics: list[str]
    distress: float
    hostility: float

    @classmethod
    def from_appraisal(cls, appraisal: Appraisal) -> "PartnerNow":
        """Lee del appraisal la emoción, la intención y el foco (temas normalizados) de quien habla."""
        return cls(
            valence=appraisal.user_emotion.valence, arousal=appraisal.user_emotion.arousal,
            intent=appraisal.user_intent, topics=normalize_topics(appraisal.topics),
            distress=appraisal.distress, hostility=appraisal.hostility,
        )


class PartnerModel(BaseModel):
    """
    Lo que la entidad sabe de una persona (§5.9, §7.2; contenido de Fase 1, D1-54).

    `topics` y `sensitive_topics` guardan conteos; `top_topics` y
    `top_sensitive` son lo que se muestra. `n` cuenta los turnos con esa persona.
    """

    id: str = Field(pattern=SEED_ID_PATTERN)
    name: str = Field(min_length=1)
    primary: bool = False
    trust: float = Field(NEW_PERSON_TRUST, ge=0.0, le=1.0)
    n: int = 0
    first_met: datetime | None = None
    last_seen: datetime | None = None
    valence_mean: float = 0.0
    arousal_mean: float = 0.0
    topics: dict[str, int] = {}
    sensitive_topics: dict[str, int] = {}

    @classmethod
    def for_primary(cls, primary: PrimaryPerson) -> "PartnerModel":
        """Modelo inicial del usuario principal, con la confianza de la config."""
        return cls(id=primary.id, name=primary.name, primary=True, trust=primary.trust)

    @property
    def top_topics(self) -> list[str]:
        """Los temas de los que más habla esta persona."""
        return _top(self.topics, TOP_TOPICS)

    @property
    def top_sensitive(self) -> list[str]:
        """Los temas que más angustia le traen."""
        return _top(self.sensitive_topics, TOP_SENSITIVE)

    def summary(self) -> dict:
        """Versión JSON para los eventos y la consola (sin los conteos completos)."""
        return {
            "id": self.id, "name": self.name, "primary": self.primary, "trust": self.trust,
            "n": self.n, "first_met": self.first_met.isoformat() if self.first_met else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "valence_mean": round(self.valence_mean, 3), "arousal_mean": round(self.arousal_mean, 3),
            "top_topics": self.top_topics, "top_sensitive": self.top_sensitive,
        }


def _top(counts: dict[str, int], limit: int) -> list[str]:
    """Los `limit` temas más contados; a igual conteo, por orden alfabético (determinista)."""
    return [name for name, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def _count(counts: dict[str, int], names: list[str]) -> dict[str, int]:
    """Suma una aparición a cada tema y conserva solo los `MAX_TRACKED_TOPICS` más contados."""
    updated = dict(counts)
    for name in names:
        updated[name] = updated.get(name, 0) + 1
    return {name: updated[name] for name in _top(updated, MAX_TRACKED_TOPICS)}


def update_partner_model(model: PartnerModel, now: PartnerNow, ts: datetime) -> PartnerModel:
    """
    Actualiza el modelo de una persona con lo percibido en un turno (§5.9, D1-54).

    La primera vez, la emoción típica es la observada; después, una media
    móvil con `EMOTION_EMA_ALPHA`. Los temas del mensaje suman una aparición, y
    también como sensibles si el mensaje traía angustia alta. Devuelve un
    modelo nuevo: el original no cambia.
    """
    first = model.n == 0
    alpha = 1.0 if first else EMOTION_EMA_ALPHA
    return model.model_copy(update={
        "n": model.n + 1,
        "first_met": model.first_met or ts,
        "last_seen": ts,
        "valence_mean": model.valence_mean + alpha * (now.valence - model.valence_mean),
        "arousal_mean": model.arousal_mean + alpha * (now.arousal - model.arousal_mean),
        "topics": _count(model.topics, now.topics),
        "sensitive_topics": _count(
            model.sensitive_topics, now.topics if now.distress >= SENSITIVE_DISTRESS else []
        ),
    })


def normalize_name(name: str) -> str:
    """Nombre comparable: minúsculas, sin tildes y con espacios simples («  Ána » → «ana»)."""
    decomposed = unicodedata.normalize("NFD", name.lower())
    plain = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return " ".join(plain.split())


def new_person_id(name: str, existing: dict[str, str]) -> str:
    """
    Id estable de una persona nueva a partir de su nombre (D1-52): «Ana María» → `ana-maria`.

    `existing` mapea id → nombre de las personas que ya conoce la entidad. Un
    nombre repetido lanza `DuplicatePersonError` (sin alias en Fase 1, no
    habría forma de distinguirlas); si solo choca el id, se le agrega un
    número (`ana-maria-2`).
    """
    wanted = normalize_name(name)
    if not wanted:
        raise ValueError("El nombre de la persona está vacío")
    if any(normalize_name(known) == wanted for known in existing.values()):
        raise DuplicatePersonError(f"Ya existe una persona llamada «{name.strip()}»")
    base = re.sub(r"[^a-z0-9]+", "-", wanted.replace("ñ", "n")).strip("-") or "persona"
    candidate, suffix = base, 2
    while candidate in existing:
        candidate, suffix = f"{base}-{suffix}", suffix + 1
    return candidate
