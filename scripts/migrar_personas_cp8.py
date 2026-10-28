"""
Migración de CP8 (D1-60): los episodios de diálogo anteriores a CP8 pasan a ser
de la persona principal.

Antes de CP8, cada turno se guardaba como «Me dijeron: «…» / Respondí: «…»»,
sin enlace a nadie. El usuario confirmó que en esos turnos habló siempre el
`primary` (Ricardo, en Calisto). Para cada episodio de diálogo sin `INVOLVES`:
- el texto pasa a «Ricardo me dijo: «…» / Le respondí: «…»» (D1-56), con su
  embedding recalculado;
- se crean `INVOLVES` (episodio → persona) y `SPOKEN_BY` (huella → persona).
Además se reconstruye el modelo de la persona (`PartnerModel`) con los appraisals
guardados en las huellas, en orden de fecha, como si se hubiera actualizado
turno a turno (D1-54). La huella (`Trace`) no se modifica: es de solo anexado (§7.1).

Todo se escribe en una sola consulta (una transacción): o se migra todo o nada.
Es idempotente: una segunda pasada no encuentra episodios pendientes y no hace nada.
El script no imprime el texto de las conversaciones, solo conteos.

Uso, desde la raíz del repositorio (con el servidor detenido):
    .venv/Scripts/python.exe scripts/migrar_personas_cp8.py --entidad calisto --simular
    .venv/Scripts/python.exe scripts/migrar_personas_cp8.py --entidad calisto --respaldo entities/calisto/respaldos/antes_cp8.json
`--config` permite migrar una copia de ensayo con la config de otra entidad.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ebica.core.events import EventBus  # noqa: E402
from ebica.entities.manager import EntityManager  # noqa: E402
from ebica.memory.graph import GraphStore  # noqa: E402
from ebica.memory.people import PeopleStore, person_properties  # noqa: E402
from ebica.perception.appraisal import parse_appraisal  # noqa: E402
from ebica.perception.embeddings import SentenceTransformerEmbedder  # noqa: E402
from ebica.social.partner import PartnerNow, update_partner_model  # noqa: E402

# Formato de CP6 (D1-35) y formato de CP8 (D1-56).
OLD_SAID, OLD_ANSWERED = "Me dijeron: ", "\nRespondí: "
NEW_ANSWERED = "\nLe respondí: "

_PENDING = """
MATCH (e:Episode {entity_id: $entity_id, kind: 'dialogue'})-[:DERIVED_FROM]->(t:Trace {entity_id: $entity_id})
WHERE NOT (e)-[:INVOLVES]->(:Person)
RETURN e.id AS id, t.id AS trace_id, e.text AS text, e.summary AS summary, e.ts AS ts
ORDER BY e.ts
"""

# Todos los turnos de diálogo con su appraisal, para reconstruir el modelo (los
# ya enlazados al primary y los pendientes; los de otras personas no).
_HISTORY = """
MATCH (e:Episode {entity_id: $entity_id, kind: 'dialogue'})-[:DERIVED_FROM]->(t:Trace {entity_id: $entity_id})
WHERE NOT (e)-[:INVOLVES]->(:Person) OR (e)-[:INVOLVES]->(:Person {id: $person_id})
RETURN e.ts AS ts, t.appraisal_json AS appraisal
ORDER BY e.ts
"""

# Una sola transacción: el modelo de la persona, los textos nuevos y los enlaces.
_MIGRATE = """
MATCH (p:Person {entity_id: $entity_id, id: $person_id})
SET p += $props
WITH p
UNWIND $rows AS r
MATCH (e:Episode {entity_id: $entity_id, id: r.id})-[:DERIVED_FROM]->(t:Trace {entity_id: $entity_id, id: r.trace_id})
WHERE NOT (e)-[:INVOLVES]->(:Person)
SET e.text = r.text, e.embedding = r.embedding,
    e.summary = CASE WHEN e.summary = r.old_text THEN r.text ELSE e.summary END
CREATE (e)-[:INVOLVES]->(p)
CREATE (t)-[:SPOKEN_BY]->(p)
RETURN count(e) AS migrated
"""


def new_text(text: str, name: str) -> str | None:
    """El texto en el formato de CP8, o None si no sigue el formato de CP6 (no se toca)."""
    if not text.startswith(OLD_SAID) or OLD_ANSWERED not in text:
        return None
    body = text[len(OLD_SAID):].replace(OLD_ANSWERED, NEW_ANSWERED, 1)
    return f"{name} me dijo: {body}"


def jsonable(value):
    """Convierte los valores de Neo4j (fechas) a algo que JSON pueda guardar."""
    if hasattr(value, "iso_format"):
        return value.iso_format()
    if isinstance(value, datetime):
        return value.isoformat()
    return value


async def backup(graph: GraphStore, entity_id: str, path: Path) -> tuple[int, int]:
    """Guarda en JSON todos los nodos (con sus propiedades) y relaciones de la entidad."""
    nodes = await graph.execute(
        "MATCH (n {entity_id: $e}) RETURN elementId(n) AS eid, labels(n) AS labels, properties(n) AS props",
        e=entity_id,
    )
    rels = await graph.execute(
        "MATCH (a {entity_id: $e})-[r]->(b {entity_id: $e}) "
        "RETURN elementId(a) AS start, type(r) AS type, elementId(b) AS end, properties(r) AS props",
        e=entity_id,
    )
    data = {
        "entity_id": entity_id,
        "nodes": [{**n, "props": {k: jsonable(v) for k, v in n["props"].items()}} for n in nodes],
        "relationships": rels,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return len(nodes), len(rels)


async def main() -> None:
    """Cuenta, respalda, reconstruye el modelo y migra en una transacción."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--entidad", required=True)
    parser.add_argument("--config", help="entidad cuya config se usa (por defecto, la misma)")
    parser.add_argument("--simular", action="store_true")
    parser.add_argument("--respaldo", type=Path)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    config = EntityManager(ROOT / "entities", EventBus()).read_config(args.config or args.entidad)
    primary = config.primary_person
    if primary is None:
        sys.exit("La entidad no tiene `primary_person`: no hay a quién asignar los episodios")

    graph = GraphStore.from_env()
    try:
        pending = await graph.execute(_PENDING, entity_id=args.entidad)
        convertible = [(row, new_text(row["text"], primary.name)) for row in pending]
        skipped = [row["id"] for row, text in convertible if text is None]
        convertible = [(row, text) for row, text in convertible if text is not None]
        print(f"episodios de diálogo sin persona: {len(pending)}; con formato de CP6: {len(convertible)}; "
              f"otro formato (no se tocan): {len(skipped)}")
        if args.simular or not convertible:
            print("simulación: no se escribió nada" if args.simular else "nada que migrar")
            return
        if args.respaldo is None:
            sys.exit("Falta --respaldo: no se migra sin un respaldo previo")
        nodes, rels = await backup(graph, args.entidad, args.respaldo)
        print(f"respaldo: {nodes} nodos y {rels} relaciones en {args.respaldo}")

        model = (await PeopleStore(graph).ensure_primary(args.entidad, primary)).model.model_copy(update={
            "n": 0, "first_met": None, "last_seen": None, "valence_mean": 0.0, "arousal_mean": 0.0,
            "topics": {}, "sensitive_topics": {},
        })
        history = await graph.execute(_HISTORY, entity_id=args.entidad, person_id=primary.id)
        broken = 0
        for row in history:
            try:
                appraisal = parse_appraisal(row["appraisal"])
            except Exception:  # noqa: BLE001 — un appraisal ilegible no debe frenar la migración
                broken += 1
                continue
            model = update_partner_model(model, PartnerNow.from_appraisal(appraisal), row["ts"].to_native())
        print(f"modelo de {primary.name}: {model.n} turnos (appraisals ilegibles: {broken}), "
              f"temas {model.top_topics}, sensibles {model.top_sensitive}")

        embedder = await SentenceTransformerEmbedder.load()
        vectors = await embedder.embed([text for _, text in convertible], "passage")
        rows = [{"id": row["id"], "trace_id": row["trace_id"], "old_text": row["text"], "text": text,
                 "embedding": vector} for (row, text), vector in zip(convertible, vectors)]
        [result] = await graph.execute(
            _MIGRATE, entity_id=args.entidad, person_id=primary.id, props=person_properties(model), rows=rows,
        )
        print(f"migrados: {result['migrated']} episodios")
    finally:
        await graph.close()


asyncio.run(main())
