"""
Comparación de modelos de embeddings en CPU (PLAN Fase 1, CP2, D1-3).

Mide, para cada modelo candidato, sobre `benchmarks/embeddings/retrieval.yaml`:
- recuperación: recall@1, recall@5 y MRR de 20 consultas contra 30 recuerdos;
- latencia de un mensaje (p50/p95), tiempo de carga y RAM pico del proceso;
- separación de prototipos hostiles / no hostiles (informativa, para D1-4).

Luego aplica el criterio de elección fijado antes de medir (PLAN §5.1,
"Ajustes de CP2"). Cada modelo se mide en un subproceso propio, para que la
RAM de uno no contamine la del otro.

Uso (desde la raíz del repositorio, con el extra `embeddings` instalado):
    .venv/Scripts/python.exe scripts/compare_embeddings.py --prefetch
    .venv/Scripts/python.exe scripts/compare_embeddings.py --output docs/fase-1/comparacion_embeddings.md

`--prefetch` solo descarga los modelos (la primera vez); así el tiempo de
carga medido después no incluye la descarga.
"""

import argparse
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = ROOT / "benchmarks" / "embeddings" / "retrieval.yaml"

# Candidatos de D1-3. e5 se entrenó con prefijos que distinguen la consulta
# del texto guardado; sin ellos su precisión baja. bge-m3 no usa prefijos.
MODELS: dict[str, dict[str, str]] = {
    "e5-base": {
        "hf_id": "intfloat/multilingual-e5-base",
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
    },
    "bge-m3": {
        "hf_id": "BAAI/bge-m3",
        "query_prefix": "",
        "passage_prefix": "",
    },
}

# CONSTANTES: criterio de elección (PLAN §5.1, "Ajustes de CP2"). Gana bge-m3
# si cabe en los recursos y no recupera claramente peor que e5. El límite de
# RAM supera a propósito el presupuesto orientativo de §9 (1–2 GB): los pesos
# de bge-m3 en float32 ya ocupan ~2,3 GB y el equipo tiene 32 GB.
MAX_P95_SECONDS = 0.150
MAX_RAM_BYTES = int(3.5 * 1024**3)
MRR_TOLERANCE = 0.05

# CONSTANTE: repeticiones de cada consulta al medir la latencia de un mensaje.
LATENCY_PASSES = 3


def rank_of_first_relevant(similarities: list[float], passage_ids: list[str], relevant: list[str]) -> int:
    """
    Devuelve la posición (desde 1) del primer recuerdo relevante.

    Ordena los recuerdos por similitud descendente, como haría la búsqueda
    vectorial. Lanza `ValueError` si ningún id relevante está en el corpus.
    """
    order = sorted(range(len(similarities)), key=lambda i: similarities[i], reverse=True)
    for position, index in enumerate(order, start=1):
        if passage_ids[index] in relevant:
            return position
    raise ValueError(f"Ningún id relevante {relevant} está entre los recuerdos")


def retrieval_metrics(ranks: list[int]) -> dict[str, float]:
    """Calcula recall@1, recall@5 y MRR a partir de las posiciones del primer acierto."""
    count = len(ranks)
    return {
        "recall@1": sum(rank == 1 for rank in ranks) / count,
        "recall@5": sum(rank <= 5 for rank in ranks) / count,
        # Rango recíproco medio: 1 si sale primero, 1/2 si sale segundo, etc.
        "mrr": sum(1 / rank for rank in ranks) / count,
    }


def percentile(values: list[float], fraction: float) -> float:
    """Percentil por el método del rango más cercano (suficiente para ~60 muestras)."""
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(fraction * len(ordered)) - 1))
    return ordered[index]


def prototype_separation(similarity: list[list[float]], labels: list[bool]) -> dict[str, float]:
    """
    Mide si el modelo separa las frases hostiles de las no hostiles.

    Para cada frase, compara su mayor similitud con las *otras* frases
    hostiles frente a su mayor similitud con las no hostiles (dejando fuera
    la propia frase). Acierta si queda más cerca de su propia clase. Es la
    misma idea que usará la vía baja (D1-4): similitud con los prototipos
    hostiles menos similitud con los no hostiles.
    """
    margins_hostile, margins_other, hits = [], [], 0
    for i, is_hostile in enumerate(labels):
        best_hostile = max(similarity[i][j] for j, h in enumerate(labels) if h and j != i)
        best_other = max(similarity[i][j] for j, h in enumerate(labels) if not h and j != i)
        margin = best_hostile - best_other
        (margins_hostile if is_hostile else margins_other).append(margin)
        hits += (margin > 0) == is_hostile
    return {
        "accuracy": hits / len(labels),
        "margin_hostile": statistics.mean(margins_hostile),
        "margin_non_hostile": statistics.mean(margins_other),
    }


def choose_model(results: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    """
    Aplica el criterio de elección y devuelve el modelo ganador y los motivos.

    bge-m3 gana si su p95 y su RAM caben en los límites y su MRR no queda más
    de `MRR_TOLERANCE` por debajo del de e5; si no, gana e5.
    """
    e5, bge = results["e5-base"], results["bge-m3"]
    reasons = []
    if bge["latency_p95"] >= MAX_P95_SECONDS:
        reasons.append(f"bge-m3: p95 {bge['latency_p95'] * 1000:.0f} ms ≥ {MAX_P95_SECONDS * 1000:.0f} ms")
    # Se compara la cota superior (todos los pesos leídos), no el pico de la
    # prueba corta, que subestima el uso sostenido.
    if not bge["ram_all_weights"]:
        # Sin medición no se puede afirmar que cabe.
        reasons.append("bge-m3: RAM no medida")
    elif bge["ram_all_weights"] >= MAX_RAM_BYTES:
        reasons.append(f"bge-m3: RAM {bge['ram_all_weights'] / 1024**3:.2f} GB ≥ {MAX_RAM_BYTES / 1024**3:.1f} GB")
    if bge["retrieval"]["mrr"] < e5["retrieval"]["mrr"] - MRR_TOLERANCE:
        reasons.append(
            f"bge-m3: MRR {bge['retrieval']['mrr']:.3f} < e5 {e5['retrieval']['mrr']:.3f} − {MRR_TOLERANCE}"
        )
    if reasons:
        return "e5-base", reasons
    return "bge-m3", ["bge-m3 cumple latencia, RAM y calidad"]


def _peak_working_set() -> int | None:
    """
    Devuelve el pico de memoria física del proceso en bytes (solo Windows).

    Usa `GetProcessMemoryInfo` por `ctypes` para no añadir una dependencia
    (psutil) solo para esta medición.
    """
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    # Los tipos se declaran explícitamente: sin ellos, ctypes recorta el
    # handle de 64 bits a un int de 32, la llamada falla en silencio y los
    # contadores quedan en 0 (pasó en la primera medición de CP2).
    get_current_process = ctypes.windll.kernel32.GetCurrentProcess
    get_current_process.restype = wintypes.HANDLE
    get_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    get_memory_info.restype = wintypes.BOOL

    counters = Counters()
    counters.cb = ctypes.sizeof(Counters)
    if not get_memory_info(get_current_process(), ctypes.byref(counters), counters.cb):
        raise OSError(f"GetProcessMemoryInfo falló (error {ctypes.GetLastError()})")
    return counters.PeakWorkingSetSize


def run_worker(model_key: str, threads: int) -> dict[str, Any]:
    """
    Mide un modelo dentro de este proceso y devuelve los resultados.

    Se ejecuta en un subproceso lanzado por `main`. Importa `torch` y
    `sentence-transformers` aquí, no arriba, para que las pruebas unitarias
    del script no los necesiten.
    """
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(threads)
    spec = MODELS[model_key]
    corpus = yaml.safe_load(CORPUS_PATH.read_text(encoding="utf-8"))
    ram_before_model = _peak_working_set()

    started = time.perf_counter()
    model = SentenceTransformer(spec["hf_id"], device="cpu")
    load_seconds = time.perf_counter() - started

    def encode(texts: list[str], prefix: str) -> list[list[float]]:
        """Codifica con el prefijo del modelo y vectores de norma 1 (coseno = producto punto)."""
        vectors = model.encode([prefix + text for text in texts], normalize_embeddings=True)
        return vectors.tolist()

    def dot(a: list[float], b: list[float]) -> float:
        """Producto punto; con vectores normalizados es la similitud coseno."""
        return sum(x * y for x, y in zip(a, b))

    passages = corpus["passages"]
    passage_ids = [p["id"] for p in passages]
    started = time.perf_counter()
    passage_vectors = encode([p["text"] for p in passages], spec["passage_prefix"])
    passages_seconds = time.perf_counter() - started

    queries = corpus["queries"]
    query_vectors = encode([q["text"] for q in queries], spec["query_prefix"])
    per_query = []
    for query, vector in zip(queries, query_vectors):
        similarities = [dot(vector, pv) for pv in passage_vectors]
        best = max(range(len(similarities)), key=similarities.__getitem__)
        per_query.append({
            "id": query["id"],
            "category": query["category"],
            "rank": rank_of_first_relevant(similarities, passage_ids, query["relevant"]),
            "top1": passage_ids[best],
        })

    # Latencia de un mensaje suelto, como en un turno: la primera llamada
    # calienta el modelo y no se cuenta.
    encode([queries[0]["text"]], spec["query_prefix"])
    latencies = []
    for _ in range(LATENCY_PASSES):
        for query in queries:
            started = time.perf_counter()
            encode([query["text"]], spec["query_prefix"])
            latencies.append(time.perf_counter() - started)

    # Frases simétricas (no hay consulta ni texto guardado): e5 recomienda el
    # prefijo de consulta para ambas.
    prototypes = corpus["prototypes"]
    phrases = prototypes["hostile"] + prototypes["non_hostile"]
    labels = [True] * len(prototypes["hostile"]) + [False] * len(prototypes["non_hostile"])
    phrase_vectors = encode(phrases, spec["query_prefix"])
    similarity = [[dot(a, b) for b in phrase_vectors] for a in phrase_vectors]
    ram_peak = _peak_working_set()

    # Cota superior de RAM: los pesos están mapeados desde el archivo y
    # Windows solo carga las páginas leídas. Con 70 frases se lee una parte
    # pequeña de la tabla de vocabulario (casi la mitad de los parámetros),
    # así que el uso real crece con la conversación. Leer todos los pesos
    # da la cifra hacia la que tiende (medido en CP2: bge-m3 1,85 → 2,82 GB).
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.sum()
    ram_all_weights = _peak_working_set()

    return {
        "model": model_key,
        "hf_id": spec["hf_id"],
        "dimension": model.get_embedding_dimension(),
        "max_seq_length": model.max_seq_length,
        "threads": threads,
        "load_seconds": load_seconds,
        "passages_seconds": passages_seconds,
        "latency_p50": statistics.median(latencies),
        "latency_p95": percentile(latencies, 0.95),
        "ram_before_model": ram_before_model,
        "ram_peak": ram_peak,
        "ram_all_weights": ram_all_weights,
        "retrieval": retrieval_metrics([q["rank"] for q in per_query]),
        "per_query": per_query,
        "prototypes": prototype_separation(similarity, labels),
    }


def measure_in_subprocess(model_key: str, threads: int) -> dict[str, Any]:
    """Lanza este script como subproceso para un modelo y lee su resultado en JSON."""
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--worker", model_key, "--threads", str(threads)],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Falló la medición de {model_key}:\n{completed.stderr}")
    # La última línea es el JSON; las anteriores pueden ser avisos de las bibliotecas.
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _gb(value: int | None) -> str:
    """Formatea bytes como GB, o "—" si no se pudo medir."""
    return "—" if value is None else f"{value / 1024**3:.2f} GB"


def render_report(results: dict[str, dict[str, Any]], corpus: dict) -> str:
    """Genera el informe en Markdown con las métricas, el detalle por consulta y la elección."""
    keys = list(results)
    winner, reasons = choose_model(results)
    lines = [
        "# Comparación de embeddings",
        "",
        f"Fecha: {datetime.now():%Y-%m-%d %H:%M} · Corpus: `benchmarks/embeddings/retrieval.yaml` "
        f"({len(corpus['queries'])} consultas, {len(corpus['passages'])} recuerdos)",
        "",
        "Generado por `scripts/compare_embeddings.py`. Criterio: PLAN Fase 1, §5.1 (ajustes de CP2).",
        "",
        "## Métricas",
        "",
        "| Métrica | " + " | ".join(f"`{k}`" for k in keys) + " |",
        "|---|" + "---|" * len(keys),
    ]

    def row(name: str, render) -> None:
        """Añade una fila con el valor de cada modelo."""
        lines.append(f"| {name} | " + " | ".join(render(results[k]) for k in keys) + " |")

    row("Modelo", lambda r: f"`{r['hf_id']}`")
    row("Dimensión / tokens máx.", lambda r: f"{r['dimension']} / {r['max_seq_length']}")
    row("Recall@1", lambda r: f"{r['retrieval']['recall@1']:.0%}")
    row("Recall@5", lambda r: f"{r['retrieval']['recall@5']:.0%}")
    row("MRR", lambda r: f"{r['retrieval']['mrr']:.3f}")
    row("Latencia de un mensaje p50 / p95", lambda r: f"{r['latency_p50'] * 1000:.0f} / {r['latency_p95'] * 1000:.0f} ms")
    row(f"Codificar {len(corpus['passages'])} recuerdos en lote", lambda r: f"{r['passages_seconds']:.2f} s")
    row("Carga del modelo (sin descarga)", lambda r: f"{r['load_seconds']:.1f} s")
    row("RAM antes del modelo / pico de la prueba / con todos los pesos leídos", lambda r: (
        f"{_gb(r['ram_before_model'])} / {_gb(r['ram_peak'])} / {_gb(r['ram_all_weights'])}"))
    row("Hilos de CPU", lambda r: str(r["threads"]))
    row("Prototipos: acierto (informativa)", lambda r: f"{r['prototypes']['accuracy']:.0%}")
    row("Prototipos: margen hostil / no hostil", lambda r: (
        f"{r['prototypes']['margin_hostile']:+.3f} / {r['prototypes']['margin_non_hostile']:+.3f}"))

    lines += [
        "",
        f"## Elección: `{winner}`",
        "",
        *[f"- {reason}" for reason in reasons],
        "",
        "## Detalle por consulta",
        "",
        "Posición del primer recuerdo relevante (1 = primero) y recuerdo que salió primero.",
        "",
        "| Consulta | Categoría | Relevante | " + " | ".join(f"`{k}`" for k in keys) + " |",
        "|---|---|---|" + "---|" * len(keys),
    ]
    for index, query in enumerate(corpus["queries"]):
        cells = []
        for key in keys:
            item = results[key]["per_query"][index]
            cells.append(f"{item['rank']} ({item['top1']})")
        relevant = ", ".join(query["relevant"])
        lines.append(f"| {query['id']} «{query['text']}» | {query['category']} | {relevant} | " + " | ".join(cells) + " |")

    lines += ["", "## Por categoría (MRR)", "", "| Categoría | " + " | ".join(f"`{k}`" for k in keys) + " |",
              "|---|" + "---|" * len(keys)]
    for category in sorted({q["category"] for q in corpus["queries"]}):
        cells = []
        for key in keys:
            ranks = [q["rank"] for q in results[key]["per_query"] if q["category"] == category]
            cells.append(f"{retrieval_metrics(ranks)['mrr']:.2f} (n={len(ranks)})")
        lines.append(f"| {category} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def prefetch(model_keys: list[str]) -> None:
    """Descarga los modelos cargándolos una vez (sentence-transformers baja solo lo que usa)."""
    from sentence_transformers import SentenceTransformer

    for key in model_keys:
        started = time.perf_counter()
        SentenceTransformer(MODELS[key]["hf_id"], device="cpu")
        print(f"{key}: listo en {time.perf_counter() - started:.0f} s")


def main() -> None:
    """Punto de entrada: descarga, mide un modelo (subproceso) o compara todos."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", choices=list(MODELS), default=list(MODELS))
    parser.add_argument("--threads", type=int, default=8, help="Hilos de CPU para torch (el i7-9700KF tiene 8)")
    parser.add_argument("--prefetch", action="store_true", help="Solo descargar los modelos")
    parser.add_argument("--worker", choices=list(MODELS), help=argparse.SUPPRESS)
    parser.add_argument("--output", help="Ruta del informe Markdown (si se omite, se imprime)")
    args = parser.parse_args()

    if args.worker:
        print(json.dumps(run_worker(args.worker, args.threads)))
        return
    if args.prefetch:
        prefetch(args.models)
        return

    corpus = yaml.safe_load(CORPUS_PATH.read_text(encoding="utf-8"))
    results = {key: measure_in_subprocess(key, args.threads) for key in args.models}
    if set(results) != set(MODELS):
        # Sin los dos modelos no se aplica el criterio: se muestran los datos crudos.
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return
    report = render_report(results, corpus)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Informe escrito en {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
