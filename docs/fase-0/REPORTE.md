# Fase 0 — Infraestructura · REPORTE

Registro incremental de lo que realmente ocurrió. Las entradas anteriores se conservan.

---

## 2026-10-24 · Planificación

**Hecho**
- Lectura completa de `CLAUDE.md` y `EBICA_documento_base.md`.
- Inspección del repositorio y del entorno (solo comandos de lectura).
- Creación de `docs/fase-0/PLAN.md` y de este archivo. No se modificó ningún archivo existente, no se escribió código y no se instaló nada.

**Hallazgos del entorno**
- Carpeta del proyecto: solo `CLAUDE.md` y `EBICA_documento_base.md`.
- Git: la carpeta no tiene repositorio propio; pertenece a un repo con raíz en `C:\Users\Admn` (remoto `to-do-app`). Ver D0-1 en el plan.
- Python 3.11.9; RTX 3070 8 GB; Ollama 0.40.10 con `llama3`, `llama3.1`, `mistral` y otro modelo; sin Docker, sin llama.cpp server, sin Neo4j detectado.
- Discrepancia menor: §10 del documento base ubica el documento en `docs/`; está en la raíz (como indica `CLAUDE.md`). No se movió.

**Pendiente**
- Aprobación del plan y de las decisiones D0-1 a D0-8.
- Ningún checkpoint iniciado.

---

## 2026-10-24 · Revisión de decisiones

**Decisiones del usuario**
- D0-1: repositorio propio iniciado. Verificado: `git rev-parse --show-toplevel` apunta a la carpeta del proyecto; rama `master`; sin commits.
- D0-2: Ollama. D0-3: se descarta `mistral`, se evalúa `llama3`. D0-5: índices vectoriales pospuestos a Fase 1. D0-6: consola en React.

**Hallazgos**
- WSL2 con Ubuntu ya instalado y hipervisor detectado: Docker Desktop es instalable sin preparación adicional (relevante para D0-4).

**Pendiente**
- Confirmar Docker (D0-4), TypeScript en la consola (D0-6), `llama3.1` como comparación (D0-3), y D0-7/D0-8.
- Aprobación explícita para iniciar CP0.

---

## 2026-10-24 · Decisiones finales

- D0-3: se evalúa primero `llama3.1`; `llama3` solo si aquel no rinde. D0-4: Docker (instalación por el usuario con guía). D0-6: Vite + React + TypeScript. D0-7: `venv` + `pip`. D0-8: el usuario movió el documento base a `docs/`.
- Discrepancia abierta: `CLAUDE.md` aún indica que el documento base está en la raíz. No se modificó (archivo del usuario).
- El usuario aprobó iniciar CP0.

---

## 2026-10-24 · CP0 — Repositorio y entorno

**Cambios**
- `pyproject.toml`: paquete `ebica` 0.0.1, Python ≥3.11, extra `dev` (pytest, pytest-asyncio), `asyncio_mode = "auto"`, marcador `integration`.
- `.gitignore`: entorno, `.env`, y datos de entidades (`entities/*/state.json`, `entities/*/events/`), `node_modules/`, `console/dist/`.
- `.env.example`: URL y modelo del LLM, credenciales de Neo4j, carpeta de entidades.
- `README.md` con instrucciones de entorno.
- Paquete `ebica/` con subpaquetes `core`, `entities`, `llm`, `memory`, `api` (solo `__init__.py` con docstring).
- `tests/test_smoke.py`.

**Decisión y motivo**
- Dependencias de ejecución vacías: cada una se añade en el checkpoint que la usa, para no instalar nada sin necesidad concreta.

**Relación con EBICA**
- El paquete solo contiene código del motor; los datos de entidades quedan fuera y no versionados (D1, §13.3).

**Pruebas**
- `py -3.11 -m venv .venv` → OK.
- `.venv/Scripts/python.exe -m pip install -e ".[dev]"` → OK (pytest 9.1.1, pytest-asyncio 1.4.0).
- `.venv/Scripts/python.exe -m pytest -q` → `1 passed`.
- `git status --short` → solo archivos del proyecto; `.venv/` y `*.egg-info` ignorados.

**Pendiente**
- Docker Desktop (usuario, antes de CP4). CP1 no iniciado.

---

## 2026-10-24 · Docker verificado

- El usuario instaló Docker Desktop con `winget`. `docker run --rm hello-world` → "Hello from Docker!". `wsl -l -v` muestra la distribución `docker-desktop` en WSL versión 2, así que el motor usa WSL 2 (winget instala en modo silencioso con esa opción por defecto).
- La terminal de la sesión de Claude Code no ve `docker` en el `PATH` hasta reiniciarla. Se resolverá antes de CP4.

---

## 2026-10-24 · CP1 — Eventos

**Cambios**
- `ebica/core/events.py`: `Event` (Pydantic: `id`, `ts` en UTC, `entity_id`, `type`, `payload`, `cause_id`), `JsonlEventLog` (append/lectura por entidad y día) y `EventBus` (`subscribe`, `unsubscribe`, `publish`, `emit`).
- `pyproject.toml`: dependencia `pydantic>=2.6` (instalada 2.14.1 en `.venv`).
- `tests/test_events.py`: 15 casos.

**Decisiones y motivos**
- Un `asyncio.Queue` por suscriptor: emitir nunca espera a un consumidor lento. Las colas no tienen límite; se revisará con la consola real (CP5).
- Se persiste antes de repartir: el JSONL es la fuente de verdad para reproducir sesiones.
- El día del archivo se calcula en UTC, para que no dependa de la zona horaria.
- `entity_id` restringido a `[a-z0-9_-]` porque se usa como nombre de carpeta (evita rutas como `../`). El tipo de evento sigue el formato `familia.nombre` de §8.2.

**Relación con EBICA**
- Implementa D10: base de la observabilidad total, la reproducción de sesiones y las métricas de §12. `cause_id` permite reconstruir la cadena causal de un turno.

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -v` → `16 passed` (15 de CP1 + smoke). Cubren entrega al suscriptor, desuscripción, una línea JSON por evento, reconstrucción idéntica, encadenamiento con `cause_id`, separación por día, día sin eventos, y rechazo de ids y tipos inválidos.

**Pendiente**
- CP2 (entidades) no iniciado.

---

## 2026-10-24 · Correcciones de documentación y Docker en la terminal

- La terminal de Claude Code, en una sesión nueva, ya ve Docker: `docker --version` → 29.9.2; `docker compose version` → v5.6.1. Resuelve el pendiente de "Docker verificado". No se levantó Neo4j (CP4).
- La rama del repositorio es `main` (con remoto `origin` en GitHub), no `master` como se registró en "Revisión de decisiones". Corregido en `PLAN.md` (D0-1); la entrada anterior se conserva tal cual.
- `CLAUDE.md` §1 ahora indica que el documento base está en `docs/EBICA_documento_base.md` (cierra la discrepancia de D0-8, con aprobación del usuario).

---

## 2026-10-24 · CP2 — Entidades

**Cambios**
- `ebica/core/state.py`: `EntityConfig` (`id`, `name`, `description`, `persona`; `extra="forbid"`) y `EntityState` (`entity_id`, `mode`, `created_at`, `last_loaded_at`). Los rasgos y la biografía no se implementaron (Fase 1).
- `ebica/entities/manager.py`: `EntityManager.create()` / `.load()`, `Entity` (config + estado) y `EntityConfigError`.
- `entities/ejemplo/config.yaml`: entidad de ejemplo (se versiona; su estado y eventos no).
- `pyproject.toml`: dependencia `pyyaml>=6.0` (instalada 6.0.3 en `.venv`).
- `.gitignore`: se añadió `entities/*/*.tmp` (archivo temporal de la escritura atómica).
- `ebica/core/__init__.py`: docstring actualizado.
- `tests/test_entities.py`: 15 casos.

**Decisiones y motivos**
- `create()` falla si la entidad ya existe, para no sobrescribir la historia de otra entidad.
- `load()` crea un estado inicial si falta `state.json`. Es necesario porque en el repositorio solo se versiona `config.yaml`, así que una copia recién clonada no tiene estado.
- Los errores de archivo, de YAML y de Pydantic se convierten en un único `EntityConfigError` que indica la ruta y los campos afectados.
- Se rechazan los campos desconocidos, para que un error de tipeo no pase desapercibido. Cuando lleguen los rasgos (Fase 1), habrá que añadir sus campos al esquema.
- El `id` del archivo debe coincidir con el nombre de la carpeta, porque los eventos y la memoria se indexan por `entity_id`.
- `state.json` se escribe en un archivo temporal que luego reemplaza al original. Si el proceso se corta a mitad de la escritura, el estado anterior queda intacto.

**Relación con EBICA**
- Implementa D1 y §5.1: el motor está separado de los datos de cada entidad, que viven en su propia carpeta. Es la base de la multi-instancia, los clones y la comparación de entidades con rasgos distintos en Fase 1.

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -v` → `31 passed` (15 de CP2 + 15 de CP1 + smoke). Cubren:
  - creación (archivos y `entity.created`) y rechazo de una entidad duplicada;
  - carga (estado reconstruido, `entity.loaded`, hora de carga persistida) y carga sin `state.json`;
  - eventos guardados en el JSONL;
  - errores legibles por campo faltante, campo desconocido, YAML roto, id distinto de la carpeta y entidad inexistente;
  - ids y modos inválidos;
  - la entidad de ejemplo carga sin errores.
- Prueba manual de un mensaje de error: `config.yaml no es válido: 'name': Field required; 'nmae': Extra inputs are not permitted`.
- La consola de Windows mostró "v�lido" por su codificación (cp1252). El texto en Python es correcto.

**Pendiente**
- CP3 (cliente LLM) no iniciado.

---

## 2026-10-24 · CP3 — Cliente LLM y evaluación de modelos

**Cambios**
- `ebica/llm/client.py`:
  - `LLMClient` (asíncrono, `httpx`, API compatible con OpenAI), con `stream()`, `complete()`, `is_available()` y `from_env()`;
  - presets `dialogue` (0.7) y `appraisal` (0.2, modo JSON), con `SamplingPreset` y `PRESETS`;
  - `LLMResult`, que guarda texto, `usage`, `finish_reason`, latencia al primer token y latencia total;
  - `LLMError`.
- Eventos: `llm.request` (cuerpo completo enviado al modelo) y, encadenados a él por `cause_id`, `llm.response`, `llm.cancelled` (con el texto parcial) y `llm.error`.
- `scripts/evaluate_llm.py`: evaluación con 7 consignas de diálogo, 3 de appraisal en JSON, medición de VRAM y prueba de cancelación en la GPU real.
- `docs/fase-0/evaluacion_llm_llama3.1.md`: informe generado por el script, con todas las respuestas.
- `pyproject.toml`: dependencia `httpx>=0.27` (instalada 0.28.1 en `.venv`).
- `tests/test_llm_client.py`: 11 casos (10 con servidor simulado y 1 de integración).

**Decisiones y motivos**
- Cancelar una generación es cancelar la tarea asyncio que la consume. El cliente cierra la conexión HTTP, y verificamos que Ollama deja de generar. Es el mecanismo que usará la cola de GPU con interrupción (D4, Fase 1).
- `complete()` usa streaming por dentro. Así existe un único camino de código, y siempre se miden el primer token y el texto parcial.
- Se añadió `llm.error`, que no figura en la tabla §8.2, para que los fallos queden registrados igual que los éxitos (D10). **Es una propuesta: puede revertirse.**
- Solo se definieron los presets que usa Fase 0. `thought`, `impulsive` y `consolidation` llegan con sus mecanismos.
- Antes de programar se comprobó con `curl` el formato real de Ollama: SSE, `usage` en el último fragmento con `choices` vacío, y `response_format: json_object` aceptado.

**Relación con EBICA**
- Implementa la base del CorticalInferenceEngine (§5.13): todas las llamadas al LLM pasan por un solo punto, y el prompt exacto queda en el evento `llm.request` para la consola (§8.3).
- La cancelación verificada hace posible que un turno del usuario interrumpa un pensamiento (§5.14).

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q` → `42 passed`. Con `-m "not integration"` → `41 passed, 1 deselected`.
- Pruebas simuladas: orden de los fragmentos, prompt completo en `llm.request`, encadenamiento con `cause_id`, `usage` y latencias, diferencias entre presets, preset desconocido, cancelación (`llm.cancelled` con texto parcial y conexión cerrada), error HTTP 404, servidor inalcanzable (el mensaje incluye la URL), fragmento corrupto y `from_env`.
- La prueba de integración se ejecutó contra Ollama real y pasó (streaming en varios fragmentos). No se comprobó el caso en que se omite por tener Ollama apagado.
- Evaluación de `llama3.1` (`scripts/evaluate_llm.py`). Detalle completo en `evaluacion_llm_llama3.1.md`:

| Medida | Resultado |
|---|---|
| VRAM en reposo / con el modelo cargado | 1045 MiB / 6247 MiB (el modelo ocupa ~5.2 GB, con contexto de 4096 tokens) |
| Carga del modelo | ~20 s en frío (sondeo inicial con `curl`); 3.2 s si ya estaba en la caché del sistema |
| Primer token / velocidad | 0.03–0.06 s / ~75 tokens/s (prompts cortos) |
| Español y persona | Fluido; mantiene la persona y el dato del contexto ("Toby"); respeta "una frase"; discrepa sin hostilidad. Fallos menores: calcos ("difíciles de trabajar con") e inventa un "como te dije" |
| Tono afectivo | Sutil pero perceptible ("supongo que puedo ayudarte… lo último que necesito…") |
| JSON (appraisal) | 3/3 válidos, con claves y rangos correctos |
| Calibración del appraisal | **Tosca**: valencia saturada en −1 en los dos casos negativos; `hostility` 0.5 en un mensaje de angustia sin hostilidad, y `distress` 0.8 en uno hostil |
| Cancelación | GPU al 93 % durante la generación → 0 % 1.5 s después de cancelar |

**Propuesta (decisión del usuario):** adoptar `llama3.1` para Fase 0 y no evaluar `llama3` (D0-3 solo lo preveía si `llama3.1` no rendía). La calibración del appraisal debe revisarse en Fase 1 con más casos y un prompt mejor diseñado. La muestra actual (3 casos) es muy pequeña para conclusiones firmes.

**Hallazgos**
- Ollama usa por defecto un contexto de 4096 tokens. El presupuesto de §9 supone 8k y la WorkingMemory de Fase 1 lo necesitará. Habrá que medir la VRAM con `num_ctx` = 8192 (pendiente para Fase 1).

**Pendiente**
- Decisión del usuario sobre el modelo (cierra la decisión abierta §14 "Modelo LLM concreto") y sobre mantener `llm.error`.
- CP4 (Neo4j) no iniciado.

---

## 2026-10-24 · Decisión sobre el modelo LLM

- El usuario adopta `llama3.1` y descarta por ahora cambiar a una API pagada: "hagamos todo lo posible para que funcione bien con llama3.1". Una API solo se considerará si el rendimiento resulta muy deficiente. La forma de medirlo se definirá con un benchmark de appraisal (unos 30 casos etiquetados) al inicio de Fase 1. Registrado en `PLAN.md` (D0-3).
- Motivos discutidos:
  - el límite de 4096 tokens es un valor por defecto de Ollama, no del modelo; se puede subir a 8k;
  - el prompt de appraisal de CP3 era provisional;
  - cambiar de proveedor solo requiere cambiar la URL, el modelo y la clave;
  - una API rompería la ejecución local de §1.4 y §13.3;
  - el costo del monólogo continuo de Fase 2 sería alto.
- Sigue pendiente decidir si se mantiene `llm.error`.

---

## 2026-10-24 · CP4 — Neo4j

**Cambios**
- `docker-compose.yml`: servicio `neo4j` con la imagen fija `neo4j:5.26.32-community` (LTS de la serie 5.x), con estas opciones:
  - puertos 7474 y 7687 abiertos solo en `127.0.0.1`;
  - heap de 1 GB, page cache de 512 MB y tope del contenedor de 2 GB;
  - volumen con nombre `neo4j_data`;
  - healthcheck;
  - telemetría desactivada.
- `ebica/memory/graph.py`: `schema_statements()` y `GraphStore` (asíncrono), con los métodos `from_env`, `verify`, `execute`, `apply_schema`, `constraint_names` e `index_names`.
  - Restricciones de unicidad `(entity_id, id)` para `Person`, `Episode`, `Trace`, `Fact` y `Commitment`, y `(entity_id, name)` para `Topic`.
  - Índice por `entity_id` en las 8 etiquetas de §7.2.
  - No se crearon índices vectoriales (D0-5).
- `.env` creado a partir de `.env.example`, con una contraseña aleatoria para Neo4j. No se versiona: verificado con `git check-ignore`.
- `pyproject.toml`: dependencia `neo4j>=6.0,<7` (instalada 6.4.1 en `.venv`).
- `README.md`: cómo levantar y detener Neo4j, y cómo pasar las credenciales a las pruebas.
- `tests/test_graph.py`: 6 casos (3 unitarios y 3 de integración).

**Decisiones y motivos**
- Puertos abiertos solo en `127.0.0.1` y `NEO4J_dbms_usage__report_enabled=false`. La imagen envía estadísticas de uso por defecto (lo mostraba el log del primer arranque), y la memoria contiene conversaciones privadas (§13.3).
- Volumen gestionado por Docker en lugar de una carpeta del proyecto: es más rápido sobre WSL 2 y no mezcla los datos con el código. `docker compose down -v` lo borra.
- La unicidad es por pareja `(entity_id, id)` y no solo por `id`, para que un clon pueda conservar los mismos ids que el original sin chocar (§4.2).
- `NEO4J_PASSWORD` no tiene valor por defecto en el código: si falta, el error dice qué variable definir.
- Fase 0 no lee `.env` desde Python: las pruebas reciben las variables desde la terminal. Añadir `python-dotenv` (o un lector propio) se decidirá en CP5, donde el servidor lo necesitará.
- El esquema no emite eventos, porque no pertenece a ninguna entidad (`entity_id`). Los eventos de memoria (`memory.written`, etc.) llegan en Fase 1.

**Relación con EBICA**
- Implementa la base de D7 y §7: una sola base de datos con las entidades aisladas por `entity_id`, lista para que Fase 1 escriba `Episode` y `Trace` y haga la recuperación híbrida.

**Pruebas**
- `docker compose config --quiet` → OK. `docker compose up -d` → contenedor `healthy`; uso de memoria de 1.3 GiB con tope de 2 GiB.
- Con las credenciales en el entorno: `pytest -v tests/test_graph.py` → `6 passed`, y la suite completa → `48 passed`. Las pruebas cubren:
  - esquema aplicado dos veces sin error;
  - `SHOW CONSTRAINTS` y `SHOW INDEXES` listan lo esperado;
  - el mismo id se acepta en dos entidades distintas y se rechaza si se repite en la misma.
- Sin `NEO4J_PASSWORD` → `3 passed, 3 skipped`, con aviso.
- Con el contenedor detenido → `3 passed, 3 skipped`, con aviso. Tarda unos 12 s porque el driver reintenta la conexión.
- Tras `docker compose stop` y `start`, el esquema persiste: 6 restricciones y 16 índices (incluidos 2 que Neo4j crea por defecto).
- El log del contenedor recreado ya no menciona el envío de datos de uso.

**Pendiente**
- Lectura de `.env` desde Python (CP5). Restricción de unicidad para `Self` y para `Revision` (por episodio y versión) cuando se modelen en Fase 1.
- Neo4j queda encendido con `restart: unless-stopped`: arranca solo con Docker Desktop hasta que se detenga con `docker compose stop`.
- CP5 no iniciado.

---

## 2026-10-24 · Pendientes de CP3/CP4 resueltos

- `llm.error` **confirmado** por el usuario como evento del motor (complementa la familia LLM de §8.2).
- `python-dotenv>=1.0` añadido (instalada 1.2.4), con aprobación del usuario. `.env` se carga solo en los puntos de entrada: `tests/conftest.py` (nuevo), `scripts/evaluate_llm.py` y, en CP5, el servidor. La biblioteca (`GraphStore.from_env`, `LLMClient.from_env`) sigue leyendo solo variables de entorno, sin efectos ocultos. `load_dotenv` no sobrescribe variables ya definidas en la terminal.
- `README.md`: se reemplazó la instrucción manual `set -a; . ./.env` por la carga automática.
- Prueba: `.venv/Scripts/python.exe -m pytest -q -rs`, sin variables en la terminal → `48 passed`, sin pruebas omitidas: las de Neo4j leyeron la contraseña desde `.env`. `scripts/evaluate_llm.py --help` → OK.

---

## 2026-10-24 · CP5 — API, consola y flujo extremo a extremo

**Cambios (backend)**
- `ebica/llm/prompt_assembler.py`: prompt trivial (`Eres {name}. {description} {persona}` + mensaje), sin historial.
- `ebica/core/turn.py`: `run_user_turn()`. Recorre `perception.input` → `llm.request` → streaming → `llm.response`, encadenados por `cause_id`.
- `ebica/api/server.py`: `create_app()` (fábrica de la aplicación) con estos endpoints:
  - `GET /api/entities` y `POST /api/entities`;
  - `POST /api/entities/{id}/load`;
  - `WS /ws/chat` (mensajes `token`, `done` y `error`);
  - `WS /ws/events`.
- `ebica/api/__main__.py`: `python -m ebica.api`. Carga `.env` y escucha solo en `127.0.0.1:8000`.
- `ebica/entities/manager.py`: `list_ids()` y validación del `entity_id` en `load()`.
- `ebica/llm/client.py`: `from_env()` acepta un `transport` (para las pruebas).
- `pyproject.toml`: `fastapi>=0.115` (0.162.0) y `uvicorn[standard]>=0.30` (0.54.0, incluye `websockets` 17.3).
- `.env.example`: `EBICA_API_PORT`.

**Cambios (consola, `console/`)**
- Esqueleto con `npm create vite@latest -- --template react-ts`: React 19, TypeScript 6, Vite 8 y oxlint. Se borraron los archivos de demostración de la plantilla.
- `vite.config.ts`: proxy de `/api` y `/ws` al backend (un solo origen, sin CORS).
- `src/EntityPanel.tsx` (listar, crear y cargar), `src/Chat.tsx` (chat en streaming), `src/EventLog.tsx` (eventos en vivo, filtro por tipo y detalle expandible), `src/useEvents.ts` (suscripción con reconexión y tope de 500 eventos) y `src/types.ts`.
- El detalle de un `llm.request` muestra cada mensaje del prompt con su rol y su texto completo, y el JSON íntegro del evento.

**Tests**
- `tests/fake_llm.py`: servidor LLM simulado, ahora compartido; se extrajo de `test_llm_client.py`.
- `tests/test_turn_and_api.py`: 11 casos.
- `README.md`: cómo arrancar el servidor y la consola.

**Decisiones y motivos**
- El turno vive en `core/turn.py`, no en `api/`. Así la API solo se ocupa del transporte, y la lógica del turno pasará al orquestador en Fase 1 sin depender de FastAPI.
- El streaming se envuelve con `aclosing` en el turno y en el servidor. Si la consola se desconecta a mitad de una respuesta, la conexión con Ollama se cierra en el acto y se emite `llm.cancelled`. Sin `aclosing`, se cerraría cuando pasara el recolector de basura, en un momento indeterminado.
- Validar el `entity_id` en `load()`: ahora el id llega desde una URL, y sin la validación un id como `../x` podría leer fuera de `entities/`.
- Solo WebSocket para el chat (no un `POST`): la respuesta va en streaming. Los turnos se procesan de uno en uno por conexión, porque Fase 0 no tiene cola de GPU.
- Una sola entidad activa en el servidor (§4.2). Cargar otra la reemplaza; `entity.suspended` llega en fases posteriores.
- Sin historial de conversación: el prompt trivial del plan no lo incluye. La entidad no recuerda el turno anterior hasta Fase 1 (WorkingMemory).

**Relación con EBICA**
- Cumple el criterio de terminado de Fase 0 (§11) y la base de la consola de §8.3: lo que el motor hace es visible en vivo, incluido el prompt exacto, y queda registrado en el JSONL para reproducirlo.

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q` → `59 passed` (4 de integración, con Ollama y Neo4j reales). Con `-m "not integration"` → `55 passed`.
- Las 11 pruebas nuevas cubren:
  - el prompt trivial;
  - la cadena de eventos del turno;
  - el cierre anticipado del turno, que emite `llm.cancelled`;
  - crear, listar y cargar por HTTP;
  - los errores 404, 409 y 422;
  - el chat sin entidad activa;
  - el flujo completo por WebSocket (respuesta en streaming, eventos en vivo e iguales en el JSONL);
  - el error del LLM en el chat;
  - un id inseguro en el manager;
  - `list_ids`.
- Consola: `npm run build` (incluye la verificación de tipos `tsc`) → OK. `npx oxlint` → 0 avisos. Corregí dos avisos de hooks en `EntityPanel`.
- Extremo a extremo con un script Python, pasando por el proxy de Vite y con Ollama real (`llama3.1`): carga `ejemplo`, respuesta en 24 fragmentos, y `perception.input` → `llm.request` (prompt completo) → `llm.response` en vivo con su `cause_id`. Los mismos eventos quedaron en `entities/ejemplo/events/2026-10-24.jsonl`.
- **Demostración en el navegador** (Chrome, http://127.0.0.1:5173):
  1. se crea `demo_cp5` desde el formulario y se carga (`entity.created` y `entity.loaded` en vivo);
  2. se le escribe "Hola Aurora, ¿qué estás restaurando esta semana?";
  3. la respuesta llega en streaming;
  4. en el registro aparecen `perception.input`, `llm.request` y `llm.response`;
  5. al expandir el `llm.request` se ven los mensajes SYSTEM y USER exactos y el `cause_id` apuntando al `perception.input`.
  
  El JSONL de `demo_cp5` contiene los 5 eventos con la misma cadena. La consola del navegador no registró errores al recargar.
- `git status`: `state.json` y `events/` de las entidades no aparecen (ignorados).

**Observaciones**
- `llama3.1` escribió acotaciones de rol ("*respiro profundamente*", "*suspiro*"). Se controlará desde el prompt en Fase 1.
- El chat muestra el `id` de la entidad (`demo_cp5`) en lugar de su nombre. Es menor; se ajustará cuando la consola crezca.
- Starlette avisa que su `TestClient` prefiere `httpx2`. Solo afecta a las pruebas; no se añadió la dependencia.
- La consola no recupera los eventos anteriores al conectarse: solo muestra los que llegan en vivo. El historial completo está en el JSONL.

**Pendiente**
- Decidir qué hacer con `entities/demo_cp5/`, creada en la demostración (solo su `config.yaml` sería versionable).
- Cierre formal de Fase 0 y paso a la planificación de Fase 1 (a decisión del usuario).

---

## 2026-10-24 · Segunda entidad de prueba: Inés

- `entities/ines/config.yaml`: Inés Arancibia, afinadora de pianos de Valparaíso. Se pidió una entidad "original, con campos interesantes".
  - `description` lleva hechos biográficos: futura biografía semilla de Fase 1.
  - `persona` lleva su voz, valores y opiniones firmes (un adelanto del ideal del yo, Fase 3), un tema que evita (su padre) y la regla "no describo gestos entre asteriscos".
- Sondeo con `llama3.1` (3 mensajes por `/ws/chat`):
  - respeta las frases cortas y ya no usa asteriscos;
  - ante "pon música de fondo" no expresa con firmeza su irritación;
  - ante "¿tu papá también afinaba pianos?" responde, aunque su persona dice que no habla de él con desconocidos.
- Lectura: las restricciones escritas solo en el prompt se cumplen a medias. Esto respalda el planteamiento del documento base (§1.2): la personalidad debe vivir en la dinámica (por ejemplo, el `DefenseArbiter` de Fase 3 decidiendo qué entra al contexto), no solo en el texto.
- El usuario probó a Inés desde la consola: "está funcionando súper".
- `entities/demo_cp5/` borrada a pedido del usuario: solo contenía la configuración genérica de la demostración, su `state.json` y un JSONL con 5 eventos de prueba.
- Al detener los servidores en segundo plano, el proceso `node` de Vite (lanzado por `npm run dev`) quedó vivo ocupando el puerto 5173. Se identificó por su línea de comandos y se detuvo. Si al detener `npm run dev` el puerto sigue ocupado, la causa es esa.
- `PLAN.md`: el encabezado de estado decía "propuesta, pendiente"; se actualizó a "ejecutado".

---

## 2026-10-24 · Cierre de Fase 0

**Criterio de terminado (§11): cumplido.** Se creó una entidad desde la consola, se le envió un mensaje y en vivo se vieron `perception.input`, el prompt exacto (`llm.request`) y la respuesta (`llm.response`), con los mismos eventos en el JSONL. El usuario aprobó registrar el cierre.

**Entregables**

| Pieza | Ubicación | Estado |
|---|---|---|
| Eventos (D10) | `ebica/core/events.py` | `Event`, `EventBus`, `JsonlEventLog` |
| Entidades (D1) | `ebica/core/state.py`, `ebica/entities/manager.py` | `create`, `load`, `list_ids`; `ejemplo` e `ines` en `entities/` |
| LLM (§5.13) | `ebica/llm/client.py`, `ebica/llm/prompt_assembler.py` | Ollama + `llama3.1`; presets `dialogue` y `appraisal`; streaming, cancelación, `llm.error`; prompt trivial |
| Memoria (D7) | `docker-compose.yml`, `ebica/memory/graph.py` | Neo4j 5.26.32 Community; restricciones e índices por `entity_id`; sin índices vectoriales |
| Turno mínimo | `ebica/core/turn.py` | Sin appraisal, afecto, memoria ni historial |
| API y consola (§8.3) | `ebica/api/`, `console/` | FastAPI + WebSocket; Vite + React + TS |
| Evaluación | `scripts/evaluate_llm.py`, `docs/fase-0/evaluacion_llm_llama3.1.md` | 7 consignas de diálogo + 3 de appraisal |

**Pruebas al cierre:** `.venv/Scripts/python.exe -m pytest -q` → `59 passed` (4 de integración, con Ollama y Neo4j reales; se omiten con aviso si no están disponibles). La consola compila (`npm run build`) y pasa `oxlint` sin avisos.

**Decisiones vigentes** (detalle en `PLAN.md` §5 y en las entradas anteriores)
- Rama `main` con remoto `origin`; el usuario hace los commits.
- Ollama con `llama3.1`. Una API pagada solo si el rendimiento es muy deficiente según un benchmark.
- Neo4j en Docker, solo en `127.0.0.1`, sin telemetría, tope de 2 GB.
- `venv` + `pip`; cada dependencia se añade en el checkpoint que la usa.
- `.env` se carga con `python-dotenv` solo en los puntos de entrada.
- `llm.error` confirmado como evento.
- Una sola entidad activa en el servidor.

**Pendientes que pasan a Fase 1**
1. Benchmark de appraisal (unos 30 casos etiquetados) con un prompt bien diseñado. Mide si `llama3.1` basta y fija qué cuenta como "rendimiento muy deficiente". La calibración observada en CP3 fue tosca (3 casos).
2. Contexto de Ollama a 8192 tokens (hoy usa 4096 por defecto) y medición de la VRAM resultante. Estimación sin medir: ~6.7 GB de 8.
3. Modelo de embeddings en CPU (bge-m3 o multilingual-e5, §14) e índices vectoriales en Neo4j (D0-5).
4. Restricciones de unicidad para `Self` y `Revision`.
5. Consola: mostrar el nombre de la entidad en el chat y recuperar los eventos anteriores al conectarse.
6. Prompt: `llama3.1` tiende a escribir acotaciones entre asteriscos, y cumple a medias las restricciones de persona (ver la entrada de Inés).

**Aprendizajes del proceso**
- Antes de programar contra un servicio externo, sondear su comportamiento real (en CP3, `curl` a Ollama reveló el formato de `usage` y la carga en frío de ~20 s).
- Leer los logs de los servicios nuevos (en CP4 revelaron la telemetría de Neo4j).
- En Windows, la consola usa cp1252: los scripts que imprimen español necesitan `sys.stdout.reconfigure(encoding="utf-8")`.
- Al detener `npm run dev`, el proceso `node` de Vite puede quedar vivo ocupando el puerto 5173.
