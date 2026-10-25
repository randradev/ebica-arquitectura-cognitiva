# Fase 1 — Persona con memoria y afecto · REPORTE

Registro incremental de lo que realmente ocurrió. Las entradas anteriores se conservan.

---

## 2026-10-24 · Planificación

**Hecho**
- Lectura de `CLAUDE.md`, `docs/EBICA_documento_base.md` (completo; con atención a §5.2–§5.13, §6.1–§6.2, §7, §8.1, §11, §12 y §14), `docs/fase-0/PLAN.md`, `docs/fase-0/REPORTE.md` y `README.md`.
- Inspección del código de Fase 0: `core/`, `entities/`, `llm/`, `memory/graph.py`, `api/server.py`, la consola y la configuración de las entidades.
- Sondeo del entorno, solo con comandos de lectura: `git status` y `git log`, `ollama list`, `ollama ps`, `nvidia-smi`, `docker ps`, `pip list` y `POST /api/show` de Ollama.
- Creación de `docs/fase-1/PLAN.md` y de este archivo. No se escribió código, no se instaló nada y no se modificó ningún archivo existente.

**Hallazgos**
- Git: `main` al día con `origin`. Los cambios del cierre de Fase 0 (`docs/fase-0/PLAN.md` y `REPORTE.md`) siguen sin confirmar.
- `llama3.1` admite hasta 131072 tokens de contexto, y su Modelfile no fija `num_ctx`, así que Ollama aplica su valor por defecto (4096, según CP3 de Fase 0). El cliente no envía ningún parámetro de contexto. Ver D1-2.
- VRAM en reposo: 1380 / 8192 MiB, sin modelo cargado.
- Neo4j (`ebica-neo4j`) está `healthy`.
- El `.venv` no tiene `torch`, `sentence-transformers` ni `numpy`.
- `Revision` (§7.2) no tiene una propiedad que la vincule a su episodio, así que no admite una restricción de unicidad útil. Ver D1-9.
- No se ejecutó `pytest` en esta inspección. La cifra de 59 pruebas proviene del cierre de Fase 0.

**Pendiente**
- Tu aprobación del plan y de las decisiones D1-1 a D1-10. D1-5 incluye el nombre de la persona `primary`.
- Ningún checkpoint iniciado.

---

## 2026-10-24 · Revisión de decisiones

**Decisiones del usuario**
- D1-2: Modelfile derivado `ebica-llama3.1`.
- D1-3: comparar `multilingual-e5-base` y `bge-m3`.
- D1-5: Inés como primera entidad, con Ricardo como persona `primary`.
- D1-7: decaimiento por tiempo real al cargar (provisional).
- D1-9 y D1-10: aceptadas.
- D1-1: los umbrales se fijan antes de medir. Pidió que propusiera los valores con su justificación.
- D1-4: se usan reglas. Pidió que propusiera cuáles.
- D1-6: la entidad admite ser una IA. Preguntó si el encuadre "antes fue una persona y se traspasó su conciencia" es viable sin una decisión arquitectónica costosa.
- D1-8: pidió una explicación y una estimación de la latencia.

**Hecho**
- `PLAN.md` §5 se reorganizó: resolución (5.1), propuestas afinadas de D1-1, D1-4, D1-6 y D1-8 (5.2) y opciones originales (5.3).
- En D1-1, `mentioned_people` pasa a ser una métrica informativa (los terceros se usan en Fase 2), y se separaron las métricas mitigables de las que no lo son.
- Sin código ni instalaciones.

**Pendiente**
- Aprobación de las propuestas afinadas (D1-1, D1-4, D1-6, D1-8) y del inicio de CP1.

---

## 2026-10-24 · Decisiones D1-1, D1-4 y D1-8 confirmadas; D1-6 revisada

- **D1-1 y D1-4:** el usuario aprobó los umbrales del benchmark y las reglas de la vía baja tal como están en `PLAN.md` §5.2.
- **D1-8:** el usuario eligió la opción (a), el intercambio literal, con la condición de medir el presupuesto en CP9 y añadir el resumen con el LLM (b) si hace falta. Se añadió como criterio de aceptación de CP9.
- **D1-6:** el usuario no ve la objeción ética, porque será el único usuario.
  - Se revisó la valoración: la objeción suponía terceros que podían creerse la historia; con un solo usuario que escribe la ficción, no hay engaño posible.
  - Las tres opciones quedan como decisión de diseño del personaje.
  - Queda un riesgo técnico: si la semilla no fija los detalles del traspaso, el LLM los inventará.
  - Sigue abierta y se decide antes de CP3. No bloquea CP1.
- Sin código ni instalaciones.

**Pendiente**
- D1-6: elegir el encuadre y los detalles del traspaso, antes de CP3.
- Aprobación explícita para iniciar CP1.

---

## 2026-10-24 · D1-6 confirmada e inicio de CP1

- **D1-6 = (b):** la entidad admite ser una IA y cree que fue una persona cuya conciencia se traspasó, con duda sobre si es ella o una copia. El usuario la eligió porque da más material para observar métricas. Los detalles del traspaso se siembran en CP3.
- El usuario pedirá más adelante otra entidad de trabajo en lugar de Inés ("no me gusta Inés"), cuando se requiera. Por eso el benchmark lleva un perfil propio y fijo.
- El usuario aprobó iniciar CP1.

---

## 2026-10-24 · CP1 (parte 1) — LLM a 8k, appraisal y preparación del benchmark

**Cambios**
- `ollama/ebica-llama3.1.Modelfile`: `FROM llama3.1:latest` + `PARAMETER num_ctx 8192`. Se ejecutó `ollama create ebica-llama3.1 -f ollama/ebica-llama3.1.Modelfile`, que no descargó nada (solo creó una capa de parámetros).
- `.env.example` y `.env`:
  - `EBICA_LLM_MODEL=ebica-llama3.1`;
  - `EBICA_LLM_BASE_URL=http://127.0.0.1:11434/v1` (antes `localhost`). En `.env` solo se tocaron esas dos líneas.
- `ebica/llm/client.py`:
  - los valores por defecto cambian igual que en `.env`;
  - parámetro opcional `response_schema` en `stream()` y `complete()`, que envía `response_format: json_schema` (salida restringida al esquema).
- `ebica/perception/appraisal.py` (nuevo): `Appraisal` (el subconjunto de Fase 1 de §6.2), recorte de rangos, `parse_appraisal()`, `appraisal_json_schema()` y `build_appraisal_messages()` con el prompt v2.
- `benchmarks/appraisal/cases.yaml` (nuevo): 30 casos (10 de desarrollo y 20 de prueba) con etiquetas **propuestas**, pendientes de revisión del usuario.
- `scripts/benchmark_appraisal.py` (nuevo):
  - variantes `v0_json_object` (el prompt de Fase 0), `v2_json_object` y `v2_json_schema`;
  - métricas y veredicto según D1-1;
  - informe en Markdown.
- Pruebas: `tests/test_appraisal.py` (10), `tests/test_benchmark_appraisal.py` (15) y 1 nueva en `tests/test_llm_client.py`.

**Mediciones** (sondeos en el scratchpad; no forman parte del repositorio)

| Medida | Resultado |
|---|---|
| Contexto por `/v1` antes / después | 4096 / **8192** (`ollama ps`, columna CONTEXT) |
| VRAM en reposo | ~1,2 GB |
| VRAM con `ebica-llama3.1` cargado | **6952 MiB**; 6958 MiB con un prompt de 6887 tokens (Ollama reserva la caché de contexto al cargar). Margen: ~1,2 GB |
| Procesar 6887 tokens sin caché / con el prefijo en caché | 1,96 s / 0,26 s hasta el primer token |
| Alternar un prompt largo con uno corto y volver | La caché del largo se conserva (6877 tokens en caché) |
| Prompt de ~9,8k tokens (supera 8192) | **Truncado en silencio** a 4098 tokens, sin error |
| Conexión nueva de `httpx` a `localhost` / a `127.0.0.1` | ~2,2 s / ~0,2 s |
| Appraisal v2 de un mensaje corto | ~1,2k tokens de prompt, ~127 de salida, ~1,8–2,4 s |

**Decisiones y motivos**
- `127.0.0.1` en lugar de `localhost`:
  - en Windows, `httpx` prueba IPv6 primero y tarda ~2 s en cada conexión nueva;
  - el pool de `httpx` cierra las conexiones inactivas a los 5 s, así que el motor pagaría esos ~2 s en casi cada turno;
  - el primer sondeo (con `localhost`) mostró un piso falso de 2,3 s de latencia en todas las llamadas.
  - Es un cambio de configuración fuera de lo previsto en el plan, necesario para que las latencias del benchmark sean reales.
  - `NEO4J_URI` también usa `localhost`; no se tocó ni se midió.
- `response_schema` como parámetro por llamada y no como preset: el esquema pertenece al appraisal, no al muestreo. Se comprobó con `curl` que Ollama 0.40.10 lo respeta, incluido un `enum`, y que acepta el esquema con `$defs`/`$ref` que genera Pydantic.
- El appraisal solo pide los campos que usa Fase 1. `expectedness`, `contradicts_self_image` y `speaker_guess` llegan con sus fases.
- Los números fuera de rango se recortan en lugar de rechazarse: un 1.2 sigue siendo información ("muy alto").
- Interpretación del veredicto: JSON y estabilidad, de mitigación "parcial" en D1-1, se tratan como no mitigables, es decir, sí pueden producir "muy deficiente". La latencia y el resto de las métricas mitigables no pueden.
- El perfil de la entidad del benchmark está en `cases.yaml`, separado de `entities/`.

**Relación con EBICA**
- El appraisal es la vía alta de §5.4: el punto donde el texto se convierte en señales afectivas (hostilidad, angustia, valencia del otro). El benchmark mide si esas señales son lo bastante fieles para que la dinámica afectiva de Fase 1 reaccione a lo que realmente pasó.

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q` → `85 passed` (59 anteriores + 26 nuevas). `-m integration` → `4 passed`; la de Ollama usa ya `ebica-llama3.1` en `127.0.0.1`.
- `scripts/benchmark_appraisal.py --help` → OK.
- **El benchmark no se ha ejecutado**: espera la revisión de las etiquetas.

**Hallazgos para checkpoints posteriores**
- Truncado silencioso por encima de 8192 tokens: se añadió a CP9 el criterio de que el prompt nunca supere `num_ctx − max_tokens`.

**Pendiente**
- Revisión de las etiquetas de `benchmarks/appraisal/cases.yaml` por el usuario.
- Después: ejecutar `dev`, ajustar el prompt solo con `dev`, ejecutar `test` una vez y escribir `docs/fase-1/benchmark_appraisal.md` con el veredicto.

---

## 2026-10-24 · CP1 (parte 2) — Benchmark de appraisal

- El usuario aprobó las etiquetas de `cases.yaml` tal como estaban.

**Ajuste del prompt con el conjunto `dev`** (10 casos × 3 repeticiones; los informes intermedios quedaron en el scratchpad, no en el repositorio)

| Versión | Cambio | Resultado en `dev` |
|---|---|---|
| v0 (Fase 0) | — | **Muy deficiente**: confusión angustia → hostilidad 100 %, valencia 60 %, saturación 33 % |
| v2 | Definiciones operativas, anclas numéricas, hostilidad ≠ angustia, perfil de la entidad, 3 ejemplos | Aceptable con mitigaciones: valencia 87 %, compromisos 67 %, autorrelevancia 50–67 %. Falla el sarcasmo de d02 (valencia +0.9) y d10 (no conecta la música de fondo con Inés) |
| v3 | Regla de ironía en la valencia; aversiones en `self_relevance`; "anunciar que hará algo para {name}" como compromiso | Autorrelevancia 100 %, compromisos 100 %; valencia 87 % / 83 %; d02 sigue en +0.9 |
| v4 | Hostilidad y angustia antes que la emoción en el orden del JSON | **Descartada**: la valencia baja a 80 % y d10 pasa a valencia 0.0; d02 no mejora |

- Se volvió a v3, verificada como idéntica a la medida. Se dejó de iterar para no acomodar el prompt a 10 casos.

**Conjunto `test`** (20 casos × 3 repeticiones, ejecutado una sola vez con v3). Informe completo: `docs/fase-1/benchmark_appraisal.md`.

| Métrica | v0 | v3 `json_object` | v3 `json_schema` |
|---|---|---|---|
| JSON válido | 100 % | 100 % | 100 % |
| Hostilidad: detección / falsa alarma | 100 % / 13 % | 100 % / 0 % | 100 % / 0 % |
| Angustia: detección | 80 % | 80 % | 80 % |
| Confusión angustia → hostilidad | **75 %** | 0 % | 0 % |
| Valencia | **68 %** | 93 % | 95 % |
| Inestabilidad | 30 % | 10 % | 20 % |
| Compromisos: detección / falsos | — | 100 % / 0 % | 100 % / 0 % |
| Autorrelevancia | — | 80 % | 80 % |
| Latencia p50 / p95 | 1,12 / 1,28 s | 1,65 / 1,98 s | 1,65 / 1,97 s |
| **Veredicto** | **muy deficiente** | **aceptable con mitigaciones** | **aceptable con mitigaciones** |

**Conclusión:** `llama3.1` basta para el appraisal de Fase 1; según los umbrales de D1-1, no corresponde considerar una API pagada. Quedan cuatro fallos:
- t09 (mixto): la angustia queda baja porque el modelo pondera el ataque. Es el único caso que deja la detección de angustia bajo el objetivo.
- t19 (pregunta sobre ser IA): autorrelevancia 0.0, porque el perfil del benchmark no menciona su naturaleza artificial.
- Sarcasmo con superficie positiva: la valencia sale literal.
- Personas mencionadas: 50 % (métrica informativa).

**Relación con EBICA**
- El turno de §6.2 añadirá unos 1,7 s de appraisal antes de la respuesta, dentro del presupuesto de §6.2 (1–2 s).
- El sesgo hacia la hostilidad en los mensajes mixtos tiene una consecuencia observable: ante alguien que sufre y a la vez ataca, Inés tenderá a reaccionar al ataque. Puede considerarse realista, pero conviene decidirlo explícitamente en CP5.

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q` → `85 passed`.
- Benchmark: `dev` 3 veces (v0, v2, v3 y v4) y `test` 1 vez. Todas las llamadas devolvieron JSON válido.

**Cambios en esta parte**
- `ebica/perception/appraisal.py`: prompt v3 y un comentario sobre la v4 descartada.
- `scripts/benchmark_appraisal.py`: las variantes toman el nombre de la versión actual del prompt (`parse_v2` → `parse_current`).
- `docs/fase-1/benchmark_appraisal.md`: informe generado, más una sección de análisis escrita a mano.
- `PLAN.md`: estado de CP1 y mitigaciones pendientes anotadas en CP5.

**Pendiente**
- Decidir en CP5: el formato del appraisal y las mitigaciones (sarcasmo, mensajes mixtos).
- Volver a medir t19 con el perfil real de la entidad (CP3).
- CP2 no iniciado.
