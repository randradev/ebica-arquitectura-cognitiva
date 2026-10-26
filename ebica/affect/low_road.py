"""
Vía baja: detector rápido de hostilidad abierta, con reglas y sin LLM (§5.4, D1-4, D1-22).

Corre en CPU en milisegundos, antes del appraisal. Si el puntaje supera el
umbral θ_vb de la entidad (0,8 − 0,3·N), el turno se vuelve impulsivo: la
alerta sube de inmediato y la entidad responde en el impulso (CP5 parte B2).
Es tosca por diseño (LeDoux): la ironía y la hostilidad sutil le tocan a la
vía alta.

Ejemplo: «Cállate, idiota.» activa la orden de silencio (0,50) y el insulto
en vocativo (0,70). El «o ruidoso» da 1 − 0,5·0,3 = 0,85, que supera el
umbral de Calisto (0,575) y el de `calisto_n_bajo` (0,725). «Eres una
inútil» solo (0,70) dispara a Calisto pero no a su variante de N bajo: el
rasgo actúa como causa.

Son funciones puras; el léxico y los pesos viven en `low_road.yaml`.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

# Archivo de datos versionado con el léxico, los patrones y los pesos (D1-4).
LEXICON_PATH = Path(__file__).with_name("low_road.yaml")

# Separa cláusulas: un insulto y su marcador de dirección deben estar en la misma.
CLAUSE_SPLIT = re.compile(r"[,.;:!?¡¿\n]+")
# Fragmentos citados: «...», "..." o '...'. La comilla simple solo abre si no
# la precede una letra, para no confundir la elisión «pa' la» con una cita.
QUOTED = re.compile(r"«[^»]*»|\"[^\"]*\"|“[^”]*”|(?<!\w)'(?=\S)[^']*?(?<=\S)'(?!\w)")
REPEATED_EXCLAMATION = re.compile(r"!{2,}|\?!|!\?")
WORD = re.compile(r"[a-zñ]+")
# Tres o más letras iguales seguidas se reducen a una («idiotaaa» → «idiota»).
# Con dos no, para no romper «ll» y «rr» («cállate», «perra»).
LETTER_RUN = re.compile(r"([a-zñ])\1{2,}")


@dataclass(frozen=True)
class Lexicon:
    """Léxico y parámetros de la vía baja, leídos de `low_road.yaml`."""

    weights: dict[str, float]
    insults: frozenset[str]
    directed_copulas: frozenset[str]
    directed_pronouns: frozenset[str]
    third_person_copulas: frozenset[str]
    self_markers: frozenset[str]
    negations: frozenset[str]
    threat_patterns: tuple[re.Pattern, ...]
    silence_patterns: tuple[re.Pattern, ...]
    contempt_patterns: tuple[re.Pattern, ...]
    negation_window: int
    vocative_max_words: int
    caps_ratio: float
    caps_min_letters: int


@dataclass(frozen=True)
class RuleHit:
    """Una regla que se activó, con su señal y el fragmento que la activó (para la consola)."""

    rule: str
    signal: float
    evidence: str


@dataclass(frozen=True)
class LowRoadResult:
    """Resultado de la vía baja para un mensaje."""

    score: float
    threshold: float
    hits: tuple[RuleHit, ...] = field(default_factory=tuple)

    @property
    def triggered(self) -> bool:
        """True si el puntaje supera el umbral de la entidad: el turno será impulsivo."""
        return self.score > self.threshold

    def as_dict(self) -> dict:
        """Representación para los eventos (`affect.low_road_triggered`, `turn.completed`)."""
        return {
            "score": self.score,
            "threshold": self.threshold,
            "triggered": self.triggered,
            "rules": [{"rule": h.rule, "signal": h.signal, "evidence": h.evidence} for h in self.hits],
        }


def load_lexicon(path: Path = LEXICON_PATH) -> Lexicon:
    """Lee y compila el léxico desde un archivo YAML."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    params = data["parameters"]
    # YAML convierte palabras sueltas como «no» o «yes» en booleanos; una lista de
    # palabras con algo que no es texto es un error del archivo, no un dato.
    for key in ("insults", "directed_copulas", "directed_pronouns", "third_person_copulas",
                "self_markers", "negations"):
        not_text = [w for w in data[key] if not isinstance(w, str)]
        if not_text:
            raise ValueError(f"{path.name}: «{key}» tiene valores que no son texto {not_text}; usa comillas")

    def compile_all(patterns: list[str]) -> tuple[re.Pattern, ...]:
        """Compila una lista de expresiones regulares."""
        return tuple(re.compile(p) for p in patterns)

    return Lexicon(
        weights={k: float(v) for k, v in data["weights"].items()},
        insults=frozenset(data["insults"]),
        directed_copulas=frozenset(data["directed_copulas"]),
        directed_pronouns=frozenset(data["directed_pronouns"]),
        third_person_copulas=frozenset(data["third_person_copulas"]),
        self_markers=frozenset(data["self_markers"]),
        negations=frozenset(data["negations"]),
        threat_patterns=compile_all(data["threat_patterns"]),
        silence_patterns=compile_all(data["silence_patterns"]),
        contempt_patterns=compile_all(data["contempt_patterns"]),
        negation_window=int(params["negation_window"]),
        vocative_max_words=int(params["vocative_max_words"]),
        caps_ratio=float(params["caps_ratio"]),
        caps_min_letters=int(params["caps_min_letters"]),
    )


@lru_cache(maxsize=1)
def default_lexicon() -> Lexicon:
    """El léxico versionado, leído una sola vez."""
    return load_lexicon()


def normalize(text: str) -> str:
    """Minúsculas, sin tildes (conserva la ñ) y con las letras repetidas colapsadas."""
    lowered = text.lower().replace("ñ", "\0")
    without_accents = "".join(
        c for c in unicodedata.normalize("NFD", lowered) if unicodedata.category(c) != "Mn"
    ).replace("\0", "ñ")
    return LETTER_RUN.sub(r"\1", without_accents)


def combine(signals: list[float]) -> float:
    """«O ruidoso»: 1 − Π(1 − s_i). Sube con cada indicio y nunca supera 1."""
    remaining = 1.0
    for signal in signals:
        remaining *= 1.0 - signal
    return 1.0 - remaining


def _is_insult(word: str, lexicon: Lexicon) -> bool:
    """True si la palabra (o su singular sin «s») está en el léxico de insultos."""
    return word in lexicon.insults or (word.endswith("s") and word[:-1] in lexicon.insults)


def _classify_insult(words: list[str], index: int, lexicon: Lexicon) -> str | None:
    """
    Clasifica el insulto en `words[index]` dentro de su cláusula.

    Devuelve None si una negación cercana lo anula («no eres tonta»),
    "insulto_dirigido" si va hacia la entidad (vocativo, «eres…», «te…» sin
    tercero) o "insulto_no_dirigido" si va hacia un tercero o hacia sí misma.
    """
    window = words[max(0, index - lexicon.negation_window):index]
    if any(w in lexicon.negations for w in window):
        return None
    present = set(words)
    # «Eres» es la marca más específica: gana aunque haya primera persona
    # («siento que eres una inútil»). Sin ella, «soy/estoy…» indica que el
    # insulto es hacia quien escribe («qué tonta soy»).
    if present & lexicon.directed_copulas:
        return "insulto_dirigido"
    if present & lexicon.self_markers:
        return "insulto_no_dirigido"
    if present & lexicon.third_person_copulas:
        return "insulto_no_dirigido"
    if present & lexicon.directed_pronouns or len(words) <= lexicon.vocative_max_words:
        return "insulto_dirigido"
    return "insulto_no_dirigido"


def evaluate(text: str, threshold: float, lexicon: Lexicon | None = None) -> LowRoadResult:
    """
    Evalúa un mensaje con las reglas de D1-4 y devuelve el puntaje y las reglas activadas.

    `threshold` es el θ_vb de la entidad (`DerivedParameters.theta_low_road`).
    Lo citado («me dijo 'eres una inútil'») no cuenta como amenaza, silencio
    ni insulto dirigido: sus insultos cuentan como no dirigidos.
    """
    lexicon = lexicon or default_lexicon()
    weights = lexicon.weights
    hits: dict[str, RuleHit] = {}

    def hit(rule: str, evidence: str) -> None:
        """Registra la regla una sola vez por mensaje (la primera evidencia gana)."""
        hits.setdefault(rule, RuleHit(rule, weights[rule], evidence))

    normalized = normalize(text)
    quoted = [m.group(0) for m in QUOTED.finditer(normalized)]
    unquoted = QUOTED.sub(" ", normalized)

    for rule, patterns in (
        ("amenaza", lexicon.threat_patterns),
        ("orden_de_silencio", lexicon.silence_patterns),
        ("desprecio", lexicon.contempt_patterns),
    ):
        for pattern in patterns:
            match = pattern.search(unquoted)
            if match:
                hit(rule, match.group(0))
                break

    for clause in CLAUSE_SPLIT.split(unquoted):
        words = WORD.findall(clause)
        for index, word in enumerate(words):
            if _is_insult(word, lexicon):
                kind = _classify_insult(words, index, lexicon)
                if kind:
                    hit(kind, clause.strip())
    for fragment in quoted:
        if any(_is_insult(w, lexicon) for w in WORD.findall(fragment)):
            hit("insulto_no_dirigido", fragment)
    # Un insulto dirigido ya incluye la señal del no dirigido: no se suman los dos.
    if "insulto_dirigido" in hits:
        hits.pop("insulto_no_dirigido", None)

    letters = [c for c in text if c.isalpha()]
    if len(letters) >= lexicon.caps_min_letters:
        upper = sum(c.isupper() for c in letters)
        if upper / len(letters) > lexicon.caps_ratio:
            hit("mayusculas", f"{upper}/{len(letters)} letras")
    exclamation = REPEATED_EXCLAMATION.search(text)
    if exclamation:
        hit("exclamaciones", exclamation.group(0))

    ordered = tuple(hits.values())
    return LowRoadResult(score=combine([h.signal for h in ordered]), threshold=threshold, hits=ordered)
