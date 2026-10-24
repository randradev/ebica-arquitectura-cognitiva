# Fase 0 — Infraestructura · PLAN

> Estado: **propuesta, pendiente de aprobación.** Nada de este plan se ha ejecutado.
> Fuente: `docs/EBICA_documento_base.md` §4.2, §5.1, §5.13, §7, §8, §9, §10, §11 (Fase 0), §14.

---

## 1. Objetivo

Construir el "esqueleto observable" del motor: la tubería mínima por la que, en fases
posteriores, circularán percepción, afecto, memoria y pensamiento. No hay todavía
mecanismos cognitivos; hay **infraestructura que los hará posibles y visibles**.

**Criterio de terminado (documento base §11):** se puede crear una entidad, mandarle un
mensaje y ver en la consola el evento de entrada, el prompt enviado y la respuesta.

### Relación con EBICA

| Pieza de Fase 0 | Qué habilita después |
|---|---|
| EventBus + JSONL (D10) | Observabilidad total, reproducción de sesiones, métricas (§12) |
| EntityManager + `config.yaml` (D1) | Multi-instancia, clones, comparar entidades con N distinto (Fase 1) |
| Cliente LLM con presets y streaming (D5) | Appraisal, diálogo, monólogo, sueño |
| Neo4j con esquema e índices (D7) | Memoria episódica/semántica y recuperación híbrida (Fase 1) |
| Consola mínima | Ver el prompt exacto y el estado interno en vivo |

---

## 2. Estado actual (inspeccionado el 2026-10-24)

- La carpeta del proyecto solo contiene `CLAUDE.md` y `EBICA_documento_base.md`. No hay código.
- **Git:** la carpeta **no es un repositorio propio**. Está dentro de un repositorio cuya raíz es
  `C:\Users\Admn` (remoto `github.com/randradev/to-do-app`), y aparece como no rastreada. Ver D0-1.
- Python 3.11.9 (y 3.10) disponibles. Node 24 disponible (no necesario).
- GPU: RTX 3070, 8 GB VRAM (coincide con §1.4). CPU: i7-9700KF.
- **Ollama 0.40.10 instalado**, con modelos: `llama3`, `llama3.1`, `mistral`, `llama-3-lexi-uncensored`.
- **llama.cpp server:** no detectado. **Docker:** no instalado. **Java/Neo4j:** no detectados.

---

## 3. Alcance

1. Estructura del repositorio y entorno Python reproducible (`pyproject.toml`, entorno virtual, `pytest`).
2. Esquema de eventos (`ts`, `entity_id`, `type`, `payload`, `cause_id`) + EventBus asíncrono + persistencia JSONL diaria en `entities/<id>/events/`.
3. EntityManager: crear y cargar una entidad desde `config.yaml`, validar con Pydantic, guardar/leer `state.json` mínimo. Eventos `entity.created`, `entity.loaded`.
4. Cliente LLM (`ebica/llm/client.py`): API compatible con OpenAI, streaming, preset `dialogue`, cancelación de una generación en curso. Eventos `llm.request` (prompt completo), `llm.response`, `llm.cancelled`.
5. Neo4j levantado; `graph.py` con conexión, restricciones de unicidad por `(entity_id, id)` e índices (incluidos los vectoriales si se decide D0-5).
6. Backend FastAPI + WebSocket: endpoint de chat y stream de eventos.
7. Consola web mínima: chat + registro de eventos en vivo (con el prompt exacto visible).
8. Evaluación ligera de 2–3 modelos LLM en español y seguimiento de JSON (decisión abierta §14).

## 4. Exclusiones (fases posteriores)

- Rasgos y mapeo rasgo→parámetro, VAD, drives, vía baja, appraisal (Fase 1).
- Bucle rápido de 1 Hz, máquina de modos y **cola de GPU con prioridades** (§5.14: Fase 1–2). En Fase 0 hay una sola llamada a la vez; el cliente se diseña para permitir cancelación, pero sin cola.
- WorkingMemory, Prompt Assembler completo (en Fase 0 el prompt es trivial: nombre + descripción breve de la entidad desde `config.yaml` + mensaje).
- Escritura de `Episode`/`Trace` y recuperación (Fase 1). En Fase 0 solo se crea el esquema.
- Embeddings en tiempo de ejecución, PartnerModel, monólogo, sueño, clonación (Fases 1–2).
- `core/clock.py` simulado (Fase 2). Se usa la hora real.

---

## 5. Decisiones

### 5.1 Resolución (2026-10-24)

| # | Estado | Resultado |
|---|---|---|
| D0-1 | **Confirmada** | Repositorio propio creado por el usuario en la carpeta del proyecto (rama `main`, remoto `origin` en GitHub). |
| D0-2 | **Confirmada** | Ollama como servidor LLM en Fase 0, vía su API compatible con OpenAI. |
| D0-3 | **Confirmada** | Se descarta `mistral`. Se evalúa primero `llama3.1` (8B, soporte oficial de español, contexto 128k). Solo si no rinde bien se evalúa `llama3`. Sin descargas. |
| D0-4 | **Confirmada: Docker** | Docker Desktop sobre WSL2 (ya instalado). El usuario lo instala siguiendo una guía paso a paso, antes de CP4. |
| D0-5 | **Confirmada** | Índices vectoriales y modelo de embeddings se posponen al inicio de Fase 1. |
| D0-6 | **Confirmada** | Vite + React + TypeScript en `console/` (frontend separado del paquete Python). |
| D0-7 | **Confirmada** | `venv` + `pip` con `pyproject.toml`. |
| D0-8 | **Confirmada** | El usuario movió el documento a `docs/EBICA_documento_base.md` (coincide con §10). `CLAUDE.md` actualizado para apuntar a `docs/`. |

### 5.2 Opciones originales

| # | Decisión | Opciones | Recomendación |
|---|---|---|---|
| **D0-1** | **Repositorio Git** | (a) `git init` dentro de la carpeta del proyecto (repo propio, anidado dentro del repo de tu carpeta de usuario); (b) dejarlo como está | **(a)**, ejecutado por ti o por mí con tu permiso. Hoy cualquier `git add` desde aquí iría al repo `to-do-app` de tu carpeta de usuario, que además ve `.ssh/` y `.git-credentials` como no rastreados. Conviene revisar ese repo de raíz aparte. |
| **D0-2** | **Servidor LLM** | llama.cpp server (doc base §5.13/§9) vs. Ollama (alternativa admitida) | **Ollama en Fase 0** (ya instalado, expone API compatible con OpenAI). El cliente se escribe contra la API OpenAI, así que cambiar a llama.cpp en Fase 3 (control vectors) solo cambia la URL. Riesgo: Ollama no ofrece control vectors. |
| **D0-3** | **Modelos LLM a evaluar** | Los instalados (`llama3.1` 8B, `mistral` 7B) + 1 multilingüe nuevo (p. ej. Qwen 2.5/3 7–8B o Gemma 9B Q4) | Evaluar `llama3.1` y `mistral` sin descargas; **descargar un tercero solo con tu aprobación**. Excluir el modelo "uncensored" de la evaluación base. |
| **D0-4** | **Neo4j** | Docker (no instalado) vs. Neo4j Desktop (Windows) | **Neo4j Desktop** ahora (no hay Docker; menos piezas). Se documenta la configuración para migrar a `docker-compose.yml` más adelante. Ambas opciones requieren una instalación que harías tú. |
| **D0-5** | **Modelo de embeddings / índices vectoriales** | bge-m3 (1024 dims, más pesado) vs. multilingual-e5 (base 768 / large 1024) | Los índices vectoriales de Neo4j **necesitan la dimensión fija al crearse**. Propuesta: crear en Fase 0 restricciones e índices normales, y **posponer los índices vectoriales y la elección de embeddings al inicio de Fase 1**, cuando se usen. Así no se descarga un modelo de embeddings sin necesidad. (Contradice levemente §11 "esquema e índices"; por eso lo consulto.) |
| **D0-6** | **Frontend de la consola** | HTML + JS sin framework vs. framework liviano | **HTML + JS + WebSocket nativo**, servido por FastAPI. Sin paso de build. Reevaluar si la consola crece en Fase 1. |
| **D0-7** | **Gestor de entorno** | `venv` + `pip` (estándar) vs. `uv` (más rápido, nueva herramienta) | **`venv` + `pip` con `pyproject.toml`**: nada nuevo que aprender ni instalar globalmente. |
| **D0-8** | **Ubicación del documento base** | Raíz (como está, y como dice `CLAUDE.md`) vs. `docs/` (como dice §10) | **Dejarlo en la raíz** y anotar la discrepancia. No muevo archivos existentes. |

**Dependencias previstas** (se instalarán solo dentro del entorno virtual del proyecto y tras aprobar el checkpoint correspondiente): `pydantic`, `pyyaml`, `httpx`, `neo4j`, `fastapi`, `uvicorn`, `pytest`, `pytest-asyncio`. Todas figuran o se derivan del stack de §9 (`httpx` es el cliente HTTP mencionado en "un cliente HTTP + Pydantic bastan"; `pyyaml` lee `config.yaml`).

---

## 6. Riesgos

| Riesgo | Mitigación |
|---|---|
| Commits accidentales al repo de la carpeta de usuario | Resolver D0-1 antes de crear código |
| VRAM: LLM + otras apps en la GPU | Medir uso con `nvidia-smi` en CP3; un solo modelo cargado |
| Neo4j en Windows (servicio, puertos, contraseña) | Configuración por variables de entorno (`.env` no versionado); test de conexión que falla con mensaje claro |
| Modelos 7–8B con JSON inestable | CP3 incluye prueba de seguimiento de JSON (se necesita en Fase 1 para el appraisal) |
| Privacidad: `state.json` y eventos contienen conversaciones | `.gitignore` excluye `entities/*/state.json` y `entities/*/events/` desde CP0 (§13.3) |
| Sobreingeniería en una fase de infraestructura | Solo los módulos que Fase 0 usa; sin carpetas vacías para fases futuras |

---

## 7. Checkpoints

Cada checkpoint se ejecuta solo tras tu aprobación explícita y termina con validación,
entrada en `REPORTE.md` y una pausa.

### CP0 — Repositorio y entorno
- Resolver D0-1 (git), crear `pyproject.toml`, `.gitignore`, `README.md` breve, `.env.example`, entorno virtual, paquete `ebica/` con solo los subpaquetes de Fase 0 (`core`, `entities`, `llm`, `memory`, `api`), carpeta `tests/`.
- **Aceptación:** `pip install -e .[dev]` funciona en el venv; `pytest` se ejecuta (0 tests o un smoke test) sin errores; `git status` dentro del proyecto muestra solo archivos del proyecto.

### CP1 — Eventos (`ebica/core/events.py`)
- Modelo Pydantic `Event` (`ts`, `entity_id`, `type`, `payload`, `cause_id`, `id`).
- `EventBus` asíncrono con suscriptores (para el WebSocket) + escritor JSONL por día.
- **Aceptación (pytest):** un evento emitido llega a un suscriptor; se escribe una línea JSON válida en `entities/<id>/events/AAAA-MM-DD.jsonl`; leer el archivo reconstruye eventos idénticos; `cause_id` encadena dos eventos.

### CP2 — Entidades (`ebica/core/state.py`, `ebica/entities/manager.py`)
- `EntityConfig` (id, nombre, descripción, `persona` breve; campos de rasgos/biografía **reservados para Fase 1**, no implementados) y `EntityState` mínimo (`entity_id`, `mode`, `created_at`, `last_loaded_at`).
- `EntityManager.create()` y `.load()`; entidad de ejemplo en `entities/ejemplo/config.yaml`.
- **Aceptación (pytest):** crear → existe `config.yaml` + `state.json` y se emite `entity.created`; cargar → estado reconstruido y `entity.loaded`; un `config.yaml` inválido produce un error de validación legible.

### CP3 — Cliente LLM y evaluación de modelos (`ebica/llm/client.py`)
- Cliente asíncrono `httpx` contra la API OpenAI de Ollama; presets (al menos `dialogue` y `appraisal` definidos); streaming; cancelación.
- Script de evaluación en `scripts/` (no en el núcleo): mismas 5–10 consignas en español + una de salida JSON, para `llama3.1` (y `llama3` solo si `llama3.1` no rinde, D0-3); resultados en `REPORTE.md`.
- **Aceptación:** pytest con servidor simulado (sin GPU) verifica eventos `llm.request` con prompt completo, `llm.response` y `llm.cancelled`; prueba manual real con Ollama devuelve texto en streaming; uso de VRAM registrado; tabla comparativa y elección de modelo propuesta (decisión tuya).

### CP4 — Neo4j (`ebica/memory/graph.py`, `docker-compose.yml`)
- Requisito previo: Docker Desktop instalado por el usuario (D0-4). `docker-compose.yml` con la imagen `neo4j` Community 5.x de versión fija, volumen persistente y límite de memoria (§9: 2–4 GB).
- Conexión con variables de entorno; creación idempotente de restricciones de unicidad (`entity_id` + `id`) para `Person`, `Episode`, `Trace`, `Fact`, `Commitment`, y `(entity_id, name)` para `Topic`; índices por `entity_id`. Vectoriales según D0-5.
- **Aceptación:** test de integración (se omite con aviso si Neo4j no está disponible): ejecutar el esquema dos veces no falla; `SHOW CONSTRAINTS` / `SHOW INDEXES` listan lo esperado.

### CP5 — API, consola y flujo extremo a extremo
- `ebica/api/server.py`: FastAPI; `POST`/WebSocket de chat por entidad; WebSocket de eventos.
- Manejador de turno mínimo: recibe mensaje → `perception.input` → arma prompt trivial → `llm.request` → streaming → `llm.response` (todos con `cause_id` encadenado).
- `console/` (Vite + React, D0-6): chat y registro de eventos filtrable por tipo; el prompt de `llm.request` visible completo. En desarrollo corre con el servidor de Vite; el backend expone solo API y WebSocket.
- **Aceptación (= criterio de Fase 0):** demostración manual: crear entidad, enviar mensaje, ver en la consola `perception.input`, el prompt exacto y la respuesta; los mismos eventos están en el JSONL. Test automatizado del flujo con LLM simulado.

---

## 8. Criterios de aceptación de la fase

- [ ] CP0–CP5 completados y registrados en `REPORTE.md`.
- [ ] `pytest` pasa completo (tests de Neo4j/LLM real marcados como integración).
- [ ] Demostración del criterio §11 realizada y documentada.
- [ ] Decisiones D0-1 a D0-8 registradas con lo que se eligió y por qué.
- [ ] Ningún dato de entidad (estado, eventos) queda versionado.
