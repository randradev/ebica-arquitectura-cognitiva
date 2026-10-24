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
