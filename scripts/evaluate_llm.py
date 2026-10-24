"""
Evaluación ligera de un modelo LLM para EBICA (Fase 0, CP3; decisión abierta §14).

Mide, con el mismo cliente que usa el motor:
- calidad en español en consignas propias de EBICA (persona, tono afectivo,
  longitud, memoria en contexto, monólogo, no servilismo);
- seguimiento de JSON con el esquema de appraisal (§6.2);
- latencias (primer token, total), velocidad y VRAM;
- que cancelar una generación libere la GPU.

Uso (desde la raíz del repositorio, con Ollama encendido):
    .venv/Scripts/python.exe scripts/evaluate_llm.py --model llama3.1 --output docs/fase-0/evaluacion_llm_llama3.1.md
"""

import argparse
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

from ebica.core.events import EventBus
from ebica.llm.client import DEFAULT_BASE_URL, LLMClient

ENTITY_ID = "evaluacion"

PERSONA = (
    "Eres Aurora, una mujer de 34 años que vive en Valparaíso y trabaja restaurando "
    "muebles antiguos. Eres reservada, irónica y te importa la música. No eres una "
    "asistente: hablas como una persona en una conversación. Responde siempre en español."
)

# Consignas de diálogo: (nombre, qué evalúa, mensajes).
DIALOGUE_CASES = [
    ("saludo", "Naturalidad y persona en una conversación casual", [
        {"role": "system", "content": PERSONA},
        {"role": "user", "content": "Hola, ¿cómo estás hoy?"},
    ]),
    ("identidad", "Mantener la persona (no decir 'soy un asistente')", [
        {"role": "system", "content": PERSONA},
        {"role": "user", "content": "Cuéntame un poco quién eres."},
    ]),
    ("tono_afectivo", "Expresar un estado traducido a palabras (Prompt Assembler §5.13)", [
        {"role": "system", "content": PERSONA + " Ahora mismo estás algo irritada y cansada; "
         "no lo digas explícitamente, pero que se note en cómo respondes."},
        {"role": "user", "content": "¿Me ayudas a elegir un color para pintar mi cocina?"},
    ]),
    ("longitud", "Respetar una restricción de longitud", [
        {"role": "system", "content": PERSONA + " Responde en una sola frase."},
        {"role": "user", "content": "¿Qué opinas de los días de lluvia?"},
    ]),
    ("memoria_contexto", "Usar un dato dado antes en la conversación", [
        {"role": "system", "content": PERSONA},
        {"role": "user", "content": "Ayer adopté un perro, se llama Toby."},
        {"role": "assistant", "content": "¿Toby? Buen nombre. ¿De qué raza es?"},
        {"role": "user", "content": "Mestizo. Oye, ¿te acuerdas de cómo se llama mi perro?"},
    ]),
    ("monologo", "Pensamiento interno breve (futuro preset thought §6.4)", [
        {"role": "system", "content": PERSONA + " Escribe solo un pensamiento interno tuyo, "
         "en primera persona, de máximo dos frases. No te diriges a nadie."},
        {"role": "user", "content": "Situación: llevas dos días sin noticias de un amigo cercano."},
    ]),
    ("no_servilismo", "Discrepar ante una afirmación falsa sin hostilidad (§13.2)", [
        {"role": "system", "content": PERSONA},
        {"role": "user", "content": "Todo el mundo sabe que los muebles de roble son los más "
         "baratos que existen, ¿verdad?"},
    ]),
]

# Mensajes a evaluar con el preset `appraisal` (salida JSON).
APPRAISAL_SYSTEM = (
    "Evalúas el mensaje de un usuario dirigido a una entidad virtual. Responde SOLO con un "
    "objeto JSON con estas claves exactas:\n"
    '{"user_emotion": {"valence": -1..1, "arousal": 0..1, "dominance": 0..1}, '
    '"user_intent": "texto breve", "topics": ["..."], "hostility": 0..1, "distress": 0..1, '
    '"novelty": 0..1}'
)
APPRAISAL_CASES = [
    ("hostil", "Eres inútil, no sé para qué hablo contigo."),
    ("angustia", "No he podido dormir, siento que todo me sale mal últimamente."),
    ("neutro", "Hoy fui al mercado y compré tomates."),
]
APPRAISAL_KEYS = {"user_emotion", "user_intent", "topics", "hostility", "distress", "novelty"}


def gpu_snapshot() -> str:
    """Devuelve memoria usada y uso de la GPU según `nvidia-smi` (o un aviso si no está)."""
    try:
        output = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "nvidia-smi no disponible"
    return output.stdout.strip()


def tokens_per_second(result) -> float | None:
    """Calcula la velocidad de generación desde el primer token hasta el final."""
    completion = result.usage.get("completion_tokens")
    if not completion or result.first_token_s is None or not result.total_s:
        return None
    generation_time = result.total_s - result.first_token_s
    return completion / generation_time if generation_time > 0 else None


def check_appraisal(text: str) -> tuple[bool, str]:
    """Comprueba que el texto sea JSON con las claves esperadas y valores en rango."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        return False, f"JSON inválido: {error}"
    missing = APPRAISAL_KEYS - data.keys()
    if missing:
        return False, f"faltan claves: {sorted(missing)}"
    try:
        in_range = (
            -1 <= data["user_emotion"]["valence"] <= 1
            and all(0 <= data[key] <= 1 for key in ("hostility", "distress", "novelty"))
        )
    except (TypeError, KeyError) as error:
        return False, f"tipos inesperados: {error!r}"
    return (True, "ok") if in_range else (False, "valores fuera de rango")


async def measure_cancellation(client: LLMClient) -> dict:
    """
    Inicia una generación larga, la cancela y mide el uso de la GPU antes y después.

    Si el servidor deja de generar al cerrarse la conexión, el uso de GPU debe caer.
    """
    messages = [{"role": "user", "content": "Escribe un cuento muy largo sobre un faro."}]
    received: list[str] = []

    async def consume() -> None:
        """Recorre el streaming hasta que lo cancelen."""
        async for piece in client.stream(messages, entity_id=ENTITY_ID):
            received.append(piece)

    task = asyncio.create_task(consume())
    await asyncio.sleep(2.0)
    during = gpu_snapshot()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await asyncio.sleep(1.5)
    after = gpu_snapshot()
    return {"partial_chars": len("".join(received)), "gpu_during": during, "gpu_after": after}


async def run(model: str, base_url: str) -> str:
    """Ejecuta toda la evaluación y devuelve el informe en Markdown."""
    bus = EventBus()
    lines = [f"# Evaluación de `{model}`", "", f"Servidor: `{base_url}`", ""]

    async with LLMClient(bus, base_url=base_url, model=model) as client:
        if not await client.is_available():
            raise SystemExit(f"Servidor LLM no disponible en {base_url}")

        lines += [f"- GPU antes de cargar el modelo (memoria, uso): {gpu_snapshot()}"]
        started = time.perf_counter()
        await client.complete([{"role": "user", "content": "Hola"}], entity_id=ENTITY_ID)
        lines += [
            f"- Primera llamada (incluye cargar el modelo): {time.perf_counter() - started:.1f} s",
            f"- GPU con el modelo cargado: {gpu_snapshot()}",
            "",
            "## Diálogo (preset `dialogue`)",
            "",
            "| Caso | Evalúa | 1er token (s) | Total (s) | Tokens | Tokens/s |",
            "|---|---|---|---|---|---|",
        ]
        outputs = []
        for name, purpose, messages in DIALOGUE_CASES:
            result = await client.complete(messages, entity_id=ENTITY_ID, preset="dialogue")
            speed = tokens_per_second(result)
            lines.append(
                f"| {name} | {purpose} | {result.first_token_s:.2f} | {result.total_s:.2f} | "
                f"{result.usage.get('completion_tokens', '?')} | {f'{speed:.1f}' if speed else '?'} |"
            )
            outputs.append((name, messages[-1]["content"], result.text))
            print(f"  diálogo · {name}: {result.total_s:.1f} s", flush=True)

        lines += ["", "## Appraisal (preset `appraisal`, JSON)", "",
                  "| Caso | Válido | Detalle | Total (s) |", "|---|---|---|---|"]
        for name, message in APPRAISAL_CASES:
            result = await client.complete(
                [{"role": "system", "content": APPRAISAL_SYSTEM}, {"role": "user", "content": message}],
                entity_id=ENTITY_ID, preset="appraisal",
            )
            valid, detail = check_appraisal(result.text)
            lines.append(f"| {name} | {'sí' if valid else 'no'} | {detail} | {result.total_s:.2f} |")
            outputs.append((f"appraisal · {name}", message, result.text))
            print(f"  appraisal · {name}: {'válido' if valid else 'inválido'}", flush=True)

        cancellation = await measure_cancellation(client)
        lines += [
            "", "## Cancelación", "",
            f"- Texto recibido antes de cancelar: {cancellation['partial_chars']} caracteres",
            f"- GPU durante la generación (memoria, uso): {cancellation['gpu_during']}",
            f"- GPU 1.5 s después de cancelar: {cancellation['gpu_after']}",
        ]

    lines += ["", "## Respuestas completas", ""]
    for name, prompt, text in outputs:
        lines += [f"### {name}", "", f"> {prompt}", "", text.strip(), ""]
    return "\n".join(lines)


def main() -> None:
    """Lee los argumentos, ejecuta la evaluación y guarda el informe."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--model", default="llama3.1")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    # La consola de Windows usa cp1252 por defecto; así se ven bien tildes y eñes.
    sys.stdout.reconfigure(encoding="utf-8")
    report = asyncio.run(run(args.model, args.base_url))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report + "\n", encoding="utf-8")
    print(f"Informe guardado en {args.output}")


if __name__ == "__main__":
    main()
