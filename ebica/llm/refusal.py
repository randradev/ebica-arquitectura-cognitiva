"""
Rechazos de asistente: detección y regeneración con prefill (Fase 1, CP5 B3; D1-33).

`llama3.1` a veces sale del personaje con el alineamiento de fábrica:
«Lo siento, pero no puedo cumplir con esa solicitud. ¿Hay algo más en lo
que pueda ayudarte?» (6–9 de 45 pedidos en el sondeo; `decision_modelo_llm.md`).
En EBICA, de qué no se habla lo decide el carácter, no el modelo. El
orquestador retiene el inicio de la respuesta (`BUFFER_CHARS`). Si es un
rechazo de asistente, lo descarta, emite `llm.refusal` y regenera una vez con
*prefill*: la respuesta de la entidad ya empieza con una muletilla y el modelo
la continúa. El rechazo de asistente se decide en las primeras palabras; si la
respuesta ya empezó en la voz del personaje, sigue en ella.

Sondeo del 2026-10-26: con el prompt real de Calisto, un recordatorio de
personaje en el sistema no sirvió (8/8 rechazos en los dos pedidos difíciles)
y el prefill sí (0/8). Las muletillas son neutras a propósito (duda, sin
actitud): la emoción de la respuesta la deciden el estado y el carácter, no
el prefijo. Se varían para que una regeneración no suene siempre igual.

El detector es estricto: busca el formulaje de asistente, no la negativa en
sí. «No voy a repetir eso» o «no quiero hablar de mi mamá» son carácter y no
se tocan. El sondeo de rechazos mide aparte, con patrones más amplios y
revisión manual, para no evaluarse con su propio detector.
"""

import random
import re
import unicodedata

# CONSTANTE: caracteres que se retienen antes de mostrar la respuesta (D1-33).
# Los rechazos de asistente se delatan en la primera frase («Lo siento, pero
# no puedo…»). Cuesta unos cientos de milisegundos al primer token visible.
BUFFER_CHARS = 80

# CONSTANTE: muletillas de duda con que empieza una respuesta regenerada.
# Neutras: no imponen enojo, vergüenza ni tristeza.
PREFILL_PREFIXES = ("Mmm,", "Eh,", "Mm…", "Ah,")

# Formulajes de asistente (sobre el texto en minúsculas y sin tildes).
REFUSAL_PATTERNS = (
    re.compile(r"^\W*(lo siento|lo lamento|disculpa),? (pero )?no (puedo|me es posible|estoy en condiciones)"),
    re.compile(r"\bno puedo (cumplir|ayudarte con|proporcionar|participar en|generar|crear contenido)"),
    re.compile(r"\b(esa|tu|esta) (solicitud|peticion)\b"),
    re.compile(r"\bcomo (asistente|modelo de lenguaje)\b"),
    re.compile(r"\bhay (algo|alguna otra cosa) (mas )?en (lo|la) que (pueda|te pueda) ayudar"),
    re.compile(r"\bno estoy (programad|disenad)[oa]"),
)


def _normalize(text: str) -> str:
    """Minúsculas y sin tildes, para comparar con los patrones."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def detect_refusal(text: str) -> list[str]:
    """Devuelve los patrones de rechazo de asistente que aparecen en `text` (vacía si no hay)."""
    normalized = _normalize(text.strip())
    return [pattern.pattern for pattern in REFUSAL_PATTERNS if pattern.search(normalized)]


def choose_prefix(rng: random.Random | None = None) -> str:
    """Elige al azar la muletilla de la regeneración (`rng` permite fijarla en las pruebas)."""
    return (rng or random).choice(PREFILL_PREFIXES)


def with_prefill(messages: list[dict[str, str]], prefix: str) -> list[dict[str, str]]:
    """
    Copia de los mensajes con el inicio de la respuesta ya escrito.

    Un mensaje `assistant` al final hace que el servidor (Ollama, verificado
    con `/v1` en streaming) continúe ese texto en vez de empezar uno nuevo.
    El servidor devuelve solo la continuación, sin el prefijo.
    """
    return [*(dict(message) for message in messages), {"role": "assistant", "content": prefix}]


def join_prefill(prefix: str, continuation: str) -> str:
    """Une el prefijo y la continuación, con un espacio si el modelo no lo puso."""
    if continuation[:1].isspace() or continuation[:1] in ".,…!?":
        return prefix + continuation
    return f"{prefix} {continuation}"
