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
