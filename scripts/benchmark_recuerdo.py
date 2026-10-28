"""
Benchmark del recuperador (CP7 parte B, D1-51): ¿trae el recuerdo correcto?

Arma una entidad de prueba (`bench-recuerdo`) con la semilla de Calisto y la
«sesión» de `benchmarks/recuerdo/cases.yaml`, escrita como episodios con el
appraisal real (D1-43 a: con las importancias que daría el turno) y `bge-m3`.
Después hace cada pregunta del split pedido: el appraisal de la pregunta da los
temas, y el recuperador elige con los parámetros de Calisto y su ánimo en
reposo. Un caso acierta si alguno de sus `esperado` entra (episodio o hecho);
un control acierta si no entra nada. La entidad se borra al terminar.

Desde CP8 (D1-56, D1-58), la sesión la cuenta el `primary` de Calisto (Ricardo):
cada episodio lleva su nombre y su `INVOLVES`, y la recuperación usa a Ricardo
como persona activa y los nombres que menciona la pregunta, como el turno real.
Con `--sin-personas`, se mide como en CP7 (para comparar).

Con `--desfase-dias N` (CP8 A, sondeo de envejecimiento, D1-59), las preguntas
se hacen N días después de lo normal: la recencia de la sesión se apaga y se ve
si las confidencias con importancia 0 pierden frente al resto.

Necesita Ollama, Neo4j y `bge-m3`. Uso, desde la raíz del repositorio:
    .venv/Scripts/python.exe scripts/benchmark_recuerdo.py --split dev [--desfase-dias 30] [--salida resultado.json]
"""

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ebica.affect.appraisal_effects import apply_coherence_rules  # noqa: E402
from ebica.affect.vad import VAD  # noqa: E402
from ebica.core.events import EventBus  # noqa: E402
from ebica.core.orchestrator import APPRAISAL_SCHEMA  # noqa: E402
from ebica.entities.manager import EntityManager  # noqa: E402
from ebica.identity.traits import derive_parameters  # noqa: E402
from ebica.llm.client import LLMClient  # noqa: E402
from ebica.memory.episodes import MemoryWriter, normalize_topics  # noqa: E402
from ebica.memory.graph import GraphStore  # noqa: E402
from ebica.memory.people import PeopleStore  # noqa: E402
from ebica.memory.retrieval import MemoryRetriever  # noqa: E402
from ebica.perception.appraisal import build_appraisal_messages, parse_appraisal  # noqa: E402
from ebica.perception.embeddings import SentenceTransformerEmbedder  # noqa: E402
from ebica.social.partner import PartnerNow, update_partner_model  # noqa: E402

ENTITY_ID = "bench-recuerdo"
CASES = ROOT / "benchmarks" / "recuerdo" / "cases.yaml"
# Reposo de Calisto (atractor de §5.2), como en los sondeos.
REST_AFFECT = VAD(valence=-0.04, arousal=0.47, dominance=0.42)
# CONSTANTE: la sesión ocurrió hace 2 días (recencia ≈ 0,63 con vida media de 3 días).
SESSION_AGE = timedelta(days=2)


async def appraise(llm: LLMClient, config, text: str):
    """Appraisal real de Calisto para un mensaje, con las reglas de coherencia."""
    messages = build_appraisal_messages(config.name, config.appraisal_profile, text)
    result = await llm.complete(messages, entity_id=ENTITY_ID, preset="appraisal", response_schema=APPRAISAL_SCHEMA)
    appraisal, _ = apply_coherence_rules(parse_appraisal(result.text))
    return appraisal


async def main() -> None:
    """Prepara la entidad, corre las preguntas del split y resume los aciertos."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test"], required=True)
    parser.add_argument("--salida", type=Path)
    parser.add_argument("--desfase-dias", type=float, default=0.0)
    parser.add_argument("--sin-personas", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    data = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    config = EntityManager(ROOT / "entities", EventBus()).read_config("calisto")
    parameters = derive_parameters(config.traits)
    core_ids = [fact.id for fact in config.seed_biography.core_facts]
    now = datetime.now(timezone.utc)

    embedder = await SentenceTransformerEmbedder.load()
    graph = GraphStore.from_env()
    records = []
    try:
        await graph.apply_schema(embedder.dimension)
        await graph.execute("MATCH (n {entity_id: $e}) DETACH DELETE n", e=ENTITY_ID)
        writer = MemoryWriter(graph, embedder)
        await writer.import_seed(ENTITY_ID, config.name, config.seed_biography)
        person = None
        if not args.sin_personas:
            person = (await PeopleStore(graph).ensure_primary(ENTITY_ID, config.primary_person)).model
        async with LLMClient.from_env(EventBus()) as llm:
            # La sesión: un episodio por mensaje, con su appraisal real.
            episode_ids = {}
            for index, item in enumerate(data["sesion"]):
                appraisal = await appraise(llm, config, item["mensaje"])
                ts = now - SESSION_AGE + timedelta(minutes=index)
                if person is not None:
                    person = update_partner_model(person, PartnerNow.from_appraisal(appraisal), ts)
                written = await writer.write_turn(
                    ENTITY_ID, ts=ts, user_text=item["mensaje"], entity_text=item["respuesta"],
                    affect=REST_AFFECT, appraisal=appraisal, person=person,
                )
                episode_ids[written.episode_id] = item["id"]
                print(f"  sesión {item['id']}: importancia {written.importance:.2f}, temas {written.topics}")
            await asyncio.sleep(1.0)  # el índice vectorial incorpora los nodos nuevos con un breve retraso

            retriever = MemoryRetriever(graph)
            for case in (c for c in data["cases"] if c["split"] == args.split):
                appraisal = await appraise(llm, config, case["texto"])
                [query] = await embedder.embed([case["texto"]], "query")
                result = await retriever.retrieve(
                    ENTITY_ID, query, affect=REST_AFFECT, k=parameters.k_retrieval,
                    lambda_mmr=parameters.lambda_mmr, now=now + timedelta(days=args.desfase_dias),
                    topics=normalize_topics(appraisal.topics), excluded_fact_ids=core_ids,
                    person_id=person.id if person is not None else None,
                    mentioned_names=[p.name for p in appraisal.mentioned_people if p.name],
                    raise_lability=False,
                )
                episodes = [episode_ids.get(item.candidate.id, item.candidate.id) for item in result.episodes]
                facts = [fact.id for fact in result.facts]
                chosen = set(episodes) | set(facts)
                expected = set(case["esperado"])
                hit = bool(chosen & expected) if expected else not chosen
                candidates = {episode_ids.get(item.candidate.id, item.candidate.id): item.as_dict()
                              for item in result.candidates}
                records.append({
                    "id": case["id"], "grupo": case["grupo"], "texto": case["texto"], "acierto": hit,
                    "esperado": case["esperado"], "episodios": episodes, "hechos": facts,
                    "temas": normalize_topics(appraisal.topics), "ms": round(result.elapsed_ms, 1),
                    "desglose_esperado": {key: candidates[key] for key in expected if key in candidates},
                    "similitud_hechos": {fact.id: round(fact.similarity, 3) for fact in result.facts},
                    "max_similitud": max((item.similarity for item in result.candidates), default=None),
                })
    finally:
        await graph.execute("MATCH (n {entity_id: $e}) DETACH DELETE n", e=ENTITY_ID)
        await graph.close()

    by_group = defaultdict(list)
    for record in records:
        by_group[record["grupo"]].append(record["acierto"])
        mark = "✔" if record["acierto"] else "✖"
        print(f"{mark} {record['id']:16} episodios {record['episodios']} hechos {record['hechos']} "
              f"temas {record['temas']} ({record['ms']} ms)")
        if not record["acierto"]:
            print(f"    esperado {record['esperado']}: {record['desglose_esperado']}")
    print()
    recall = [r["acierto"] for r in records if r["grupo"] != "control"]
    controls = [r for r in records if r["grupo"] == "control"]
    for group, hits in by_group.items():
        print(f"{group:9} {sum(hits)}/{len(hits)}")
    print(f"recall (sin controles): {sum(recall)}/{len(recall)} = {sum(recall) / len(recall):.0%}")
    print(f"controles con recuerdos: {sum(not r['acierto'] for r in controls)}/{len(controls)}")
    if args.salida:
        args.salida.write_text(json.dumps(records, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


asyncio.run(main())
