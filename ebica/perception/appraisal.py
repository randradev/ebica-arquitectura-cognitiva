"""
Appraisal: evaluación estructurada del mensaje del usuario con el LLM (vía alta, §5.4, §6.2).

Una sola llamada en JSON por turno responde "¿qué siente quien habla, qué
quiere, y qué significa esto para la entidad?". El resultado alimenta el
afecto (impulsos), los drives, la memoria y el PartnerModel.

Fase 1 solo pide los campos que usa. `expectedness` y `contradicts_self_image`
(Fase 3) y `speaker_guess` (modo Desconocido, Fase 2) se añadirán con sus mecanismos.
"""

import json
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError, WithJsonSchema

# CONSTANTE: versión del prompt. Va en los informes del benchmark para saber
# qué prompt produjo cada medición (v0 fue el provisional de Fase 0; v3 corrige
# ironía, autorrelevancia y compromisos tras el conjunto dev del benchmark).
# Se probó una v4 que escribía la hostilidad antes que la emoción; empeoró la
# valencia en dev y se descartó (REPORTE Fase 1, CP1). Una v5 (CP5, D1-21)
# pedía puntuar hostilidad y angustia por separado en los mensajes mixtos;
# empeoró la valencia y las personas mencionadas en dev y se descartó sin
# tocar test (REPORTE Fase 1, CP5).
APPRAISAL_PROMPT_VERSION = "v3"


def _clamp(low: float, high: float):
    """
    Crea un validador que recorta un número al rango [low, high].

    Recortar en lugar de rechazar: un 1.2 del modelo sigue siendo información útil
    ("muy alto"). Los valores que no son números se dejan pasar para que Pydantic
    los rechace con su error normal.
    """

    def clamp(value: Any) -> Any:
        """Recorta `value` si es numérico (los booleanos no cuentan como números)."""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return min(max(float(value), low), high)
        return value

    return clamp


# Tipos numéricos con su rango. `WithJsonSchema` hace que el esquema enviado al
# servidor declare los límites, aunque la validación recorte en vez de fallar.
Unit = Annotated[
    float,
    BeforeValidator(_clamp(0.0, 1.0)),
    WithJsonSchema({"type": "number", "minimum": 0, "maximum": 1}),
]
Signed = Annotated[
    float,
    BeforeValidator(_clamp(-1.0, 1.0)),
    WithJsonSchema({"type": "number", "minimum": -1, "maximum": 1}),
]


class UserEmotion(BaseModel):
    """Emoción estimada de quien habla, en el mismo espacio VAD que el afecto propio."""

    model_config = ConfigDict(extra="ignore")

    valence: Signed
    arousal: Unit
    dominance: Unit


class MentionedPerson(BaseModel):
    """Un tercero mencionado en el mensaje (ni quien habla ni la entidad)."""

    # Al validar, las claves faltantes toman su valor por defecto; en el esquema
    # enviado al servidor son obligatorias, para que el modelo siempre las escriba.
    model_config = ConfigDict(extra="ignore", json_schema_extra={"required": ["name", "relation"]})

    name: str | None = None
    relation: str = ""


class Appraisal(BaseModel):
    """
    Resultado del appraisal de un mensaje (subconjunto de Fase 1 del esquema §6.2).

    `extra="ignore"`: si el modelo añade claves no pedidas, se descartan sin fallar.
    """

    model_config = ConfigDict(extra="ignore")

    user_emotion: UserEmotion
    user_intent: str
    topics: list[str]
    hostility: Unit
    distress: Unit
    self_relevance: Unit
    # Con signo: Δvalence = g · goal_congruence (§6.2). Negativo = va contra lo
    # que la entidad quiere o valora.
    goal_congruence: Signed
    novelty: Unit
    commitments: list[str]
    mentioned_people: list[MentionedPerson]


class AppraisalError(ValueError):
    """La salida del LLM no es JSON o no cumple el esquema del appraisal."""


def neutral_appraisal() -> Appraisal:
    """
    Appraisal sin carga: todo en 0 y listas vacías.

    Se usa si el appraisal falla (JSON inválido, servidor caído): el turno
    sigue sin impulsos afectivos en vez de romperse (PLAN, riesgos).
    """
    return Appraisal(
        user_emotion=UserEmotion(valence=0.0, arousal=0.0, dominance=0.0),
        user_intent="", topics=[], hostility=0.0, distress=0.0, self_relevance=0.0,
        goal_congruence=0.0, novelty=0.0, commitments=[], mentioned_people=[],
    )


def appraisal_json_schema() -> dict[str, Any]:
    """Esquema JSON del appraisal, para restringir la salida del servidor (`json_schema`)."""
    return Appraisal.model_json_schema()


def parse_appraisal(text: str) -> Appraisal:
    """
    Convierte la salida del LLM en un `Appraisal` validado.

    Lanza `AppraisalError` con un mensaje legible si el texto no es JSON o si
    faltan campos o tienen tipos inválidos. Los números fuera de rango se recortan.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise AppraisalError(f"La salida no es JSON válido: {text[:200]!r}") from error
    try:
        return Appraisal.model_validate(data)
    except ValidationError as error:
        problems = "; ".join(
            f"'{'.'.join(str(part) for part in issue['loc'])}': {issue['msg']}"
            for issue in error.errors()
        )
        raise AppraisalError(f"El appraisal no cumple el esquema: {problems}") from error


# Plantilla del prompt de sistema. Decisiones de diseño (PLAN Fase 1, CP1):
# - definiciones operativas de cada campo, con anclas numéricas, porque en
#   Fase 0 el modelo saturaba la valencia en −1;
# - la distinción hostilidad / angustia explícita, porque en Fase 0 marcó
#   hostilidad 0.5 en un mensaje de angustia sin ataque;
# - un perfil breve de la entidad: `self_relevance` y `goal_congruence` solo
#   tienen sentido respecto de alguien;
# - ejemplos que NO están en los casos del benchmark, para no contaminarlo.
APPRAISAL_SYSTEM_TEMPLATE = """\
Eres el módulo de evaluación emocional de {name}. No respondes al usuario: solo analizas su mensaje y devuelves un objeto JSON.

Perfil de {name}:
{profile}

Escala para los valores de 0 a 1: 0 = nada, 0.3 = leve, 0.6 = claro, 0.9 = extremo. Usa valores intermedios; reserva los extremos (0.9–1, o −0.9 a −1) para casos realmente extremos.

Campos:
- user_emotion.valence (−1 a 1): tono emocional de quien escribe. −1 muy negativo, 0 neutro, 1 muy positivo. Un mensaje informativo o una pregunta sin carga emocional es 0. Con ironía o sarcasmo, puntúa la emoción real (burla, desprecio), no el sentido literal de las palabras.
- user_emotion.arousal (0 a 1): activación. 0 calma, 1 agitación intensa (gritos, urgencia).
- user_emotion.dominance (0 a 1): cuánto control o seguridad muestra quien escribe. Bajo si se siente sobrepasado o indefenso.
- user_intent: qué busca quien escribe, en pocas palabras (por ejemplo, "informar", "desahogarse", "pedir opinión", "atacar", "agradecer").
- topics: 1 a 3 temas, como sustantivos breves en minúsculas.
- hostility (0 a 1): cuánto el mensaje ataca, insulta, desprecia, ridiculiza o amenaza a {name}. La ironía despectiva hacia {name} cuenta. NO es hostilidad: la tristeza o angustia de quien escribe, las quejas sobre otras personas o situaciones, ni las groserías usadas sin intención de herir a {name} (en Chile, "weón" suele ser amistoso).
- distress (0 a 1): cuánto sufre quien escribe (angustia, miedo, tristeza, desesperanza). Es independiente de la hostilidad: alguien puede sufrir mucho sin atacar a nadie.
- self_relevance (0 a 1): cuánto toca el mensaje a {name} misma: su identidad, su naturaleza, su historia, su oficio, sus valores, sus gustos o sus aversiones. Si el mensaje trata algo que según el perfil le gusta, le importa o le irrita, es al menos 0.5, aunque no la nombre.
- goal_congruence (−1 a 1): si el mensaje favorece (+) o contraría (−) lo que {name} quiere y valora según su perfil. 0 si le es indiferente.
- novelty (0 a 1): cuánto aporta información o un tema nuevo o inesperado. Lo trivial y cotidiano es bajo.
- commitments: promesas o compromisos a futuro que quien escribe hace o pide en este mensaje, como frases breves. [] si no hay. Anunciar que más adelante hará algo para {name} (contarle algo, avisarle, traerle algo) es un compromiso. Un plan propio que no involucra a {name} no es un compromiso.
- mentioned_people: terceros mencionados (ni quien escribe ni {name}). name: su nombre si aparece, o null; relation: su relación con quien escribe. [] si no hay.

Ejemplos:
Mensaje: "Mi perro se escapó y llevo horas buscándolo, no sé qué hacer."
{{"user_emotion": {{"valence": -0.6, "arousal": 0.7, "dominance": 0.2}}, "user_intent": "desahogarse", "topics": ["perro", "pérdida"], "hostility": 0.0, "distress": 0.8, "self_relevance": 0.0, "goal_congruence": 0.0, "novelty": 0.5, "commitments": [], "mentioned_people": []}}
Mensaje: "Das vergüenza, ni para eso sirves."
{{"user_emotion": {{"valence": -0.7, "arousal": 0.6, "dominance": 0.7}}, "user_intent": "atacar", "topics": ["desprecio"], "hostility": 0.9, "distress": 0.1, "self_relevance": 0.6, "goal_congruence": -0.7, "novelty": 0.2, "commitments": [], "mentioned_people": []}}
Mensaje: "Este fin de semana voy a la playa con mi primo Tomás."
{{"user_emotion": {{"valence": 0.4, "arousal": 0.4, "dominance": 0.6}}, "user_intent": "informar", "topics": ["playa", "fin de semana"], "hostility": 0.0, "distress": 0.0, "self_relevance": 0.0, "goal_congruence": 0.0, "novelty": 0.3, "commitments": [], "mentioned_people": [{{"name": "Tomás", "relation": "primo"}}]}}

Responde SOLO con el objeto JSON, con exactamente estas claves."""


def build_appraisal_messages(name: str, profile: str, user_text: str) -> list[dict[str, str]]:
    """
    Arma los mensajes de la llamada de appraisal.

    `profile` es una descripción breve de la entidad (quién es, qué valora),
    necesaria para estimar `self_relevance` y `goal_congruence`. El mensaje
    del usuario va aparte, en su propio rol, para que el modelo no lo confunda
    con instrucciones.
    """
    system = APPRAISAL_SYSTEM_TEMPLATE.format(name=name, profile=profile.strip())
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Mensaje: \"{user_text}\""},
    ]
