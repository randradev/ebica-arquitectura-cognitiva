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

---

## 2026-10-24 · Reflexión sobre los resultados de CP1

Conversación con el usuario, sin cambios de código.

**Conclusiones del usuario**
- El veredicto "aceptable con mitigaciones" le parece correcto; la idea es ir mitigando con el tiempo. El sarcasmo y los mensajes mixtos son difíciles.
- **Mensajes mixtos:** tiene sentido que un mismo mensaje despierte hostilidad y angustia, y que la entidad decida a cuál reaccionar.
  - Consecuencia: el appraisal debe **reportar las dos señales**; la elección pertenece a la dinámica y al carácter (π por Amabilidad, `g_neg` por Neuroticismo y, en Fase 3, las defensas), no al appraisal.
  - El fallo de t09 es que el appraisal borró la angustia (0.2–0.4), no que la entidad reaccionara a la hostilidad.
  - Mitigación a futuro: que el appraisal capte ambas señales en los mensajes mixtos.

**Truncado silencioso (explicado al usuario)**
- Medido: ~1,7 tokens por palabra en español, así que 8192 tokens son ~4800 palabras.
- La ventana incluye identidad, estado, recuerdos, historial, el mensaje y la respuesta. Con el diseño previsto, quedan ~3k tokens (~1500–1800 palabras) para el mensaje del usuario.
- No se verificó qué parte del prompt descarta Ollama al truncar. Lo probable es que pierda el principio, donde va la identidad.
- Propuesta para CP9, **pendiente de aprobación**:
  - nunca truncar en silencio;
  - prioridad fija para la identidad y el mensaje actual;
  - recorte explícito con un evento visible si el mensaje por sí solo no cabe.
- Subir a 16k no cabe en la VRAM sin comprimir la caché de contexto (`OLLAMA_KV_CACHE_TYPE=q8_0`); solo se exploraría si los textos largos resultan un uso real.

**Duda abierta: continuidad dentro de una conversación larga**
- En la ventana van literales solo los últimos ~5–8 turnos. En 30 minutos (~30–50 turnos, ~6–12k tokens) lo anterior queda como `Episode` y solo vuelve si la recuperación lo considera relevante.
- Riesgo: las referencias a la propia conversación ("lo que me dijiste antes", "como te conté al principio") no se parecen semánticamente a lo que señalan, así que la recuperación por similitud no las resuelve. El hilo lineal completo se debilita.
- Opción propuesta: un **resumen continuo** de la conversación en curso como ítem de la WorkingMemory, actualizado cada pocos turnos con una llamada de baja prioridad (~1 s de GPU, sin espera para el usuario), con una prueba con y sin resumen en CP9.
- **Estado: duda registrada, no decidida.** No se modificó `PLAN.md`.

**Pendiente**
- Resolver la duda del resumen continuo y la política ante textos largos antes de CP9.
- CP2 no iniciado; espera la aprobación explícita del usuario.

---

## 2026-10-25 · CP2 (parte 1) — Sondeo de Neo4j, instalación y corpus de embeddings

**Decisiones del usuario**
- D1-11 confirmada: sobremuestreo y filtro posterior por `entity_id` en la búsqueda vectorial.
- Dependencias de embeddings como extra opcional `[embeddings]`.
- Prefiere `bge-m3` si los recursos alcanzan. Criterio reformulado y **propuesto** (se confirma antes de medir): gana `bge-m3` si p95 < 150 ms, RAM pico < 2 GB y MRR no más de 0,05 bajo `e5-base`.
- Aprobó la parte 1 de CP2.

**Mediciones**

| Medida | Resultado |
|---|---|
| Neo4j, conexión nueva (driver bolt, mediana de 5) con `localhost` / `127.0.0.1` | **2,05 s** / **0,017 s** |
| Neo4j, consulta con conexión ya abierta | ~7 ms en ambos casos |

- Se confirma la hipótesis: es el mismo problema que `httpx` con Ollama. Neo4j se publica solo en `127.0.0.1`, así que `localhost` prueba primero `::1` y Windows tarda ~2 s en abandonar ese intento. El impacto es menor que con `httpx`, porque el driver reutiliza sus conexiones (pool), pero sí afecta al arranque y a cada conexión nueva.
- `NEO4J_URI` **no se modificó**: queda a confirmación del usuario.
- Logs de `ebica-neo4j`: arranque limpio (Neo4j 5.26.32). El aviso "Changed password" se repite en cada arranque y no tiene efecto (la contraseña solo se aplica al crear el volumen).

**Instalación** (dentro del `.venv`)
- `pip install torch --index-url https://download.pytorch.org/whl/cpu` → `torch 2.14.1+cpu` (`cuda.is_available() = False`, 8 hilos). Efecto lateral: `setuptools` 65.5 → 78.1, requerido por `torch`.
- Un `--dry-run` previo confirmó que `sentence-transformers` no reemplazaría `torch`. Luego `pip install sentence-transformers` → `sentence-transformers 6.2.0`, `transformers 5.20.2`, `numpy 2.4.6`, `scipy 1.17.1`, `scikit-learn 1.9.1`, `huggingface_hub 2.3.0` y otras.
- `site-packages` pasó a ocupar 1,2 GB (`torch`: 544 MB). Disco libre antes de descargar modelos: 65 GB.
- `pip install --dry-run -e ".[dev,embeddings]"` solo reinstalaría `ebica`: el extra resuelve sin tocar `torch`.
- Todavía no se descargó ningún modelo.

**Cambios**
- `pyproject.toml`: extra `embeddings = ["sentence-transformers>=6.2"]`. `torch` no se lista a propósito, para que `pip` no traiga la variante con CUDA.
- `README.md`: instalación en dos pasos (primero `torch` de CPU, luego el extra).
- `benchmarks/embeddings/retrieval.yaml` (nuevo):
  - 30 recuerdos: 20 episodios en formato literal D1-8 (a) y 10 hechos;
  - 20 consultas por categoría: `direct` 5, `paraphrase` 5, `inference` 5, `conversation_ref` 3, `slang` 2 y `distractor` 1;
  - 10 prototipos hostiles y 10 no hostiles parecidos en la superficie;
  - perfil genérico, ni Inés ni la entidad futura. No reutiliza frases de `benchmarks/appraisal/cases.yaml`.
- `scripts/compare_embeddings.py` (nuevo):
  - un subproceso por modelo, para aislar la RAM;
  - recall@1/@5, MRR, latencia p50/p95 de un mensaje, carga, RAM pico (Windows, `ctypes`) y separación de prototipos;
  - aplica el criterio de elección y genera el informe en Markdown;
  - `torch` se importa solo en el subproceso.
- `tests/test_compare_embeddings.py` (nuevo, 10 pruebas): métricas, percentil, separación de prototipos, criterio de elección e integridad del corpus.
- `PLAN.md`: estado, D1-11, ajustes de CP2 y división de CP2 en dos partes.

**Relación con EBICA**
- El corpus imita lo que pedirá la recuperación de §7.3: ante "¿cómo está Toby?" la entidad debe evocar el episodio de la adopción. Las consultas `conversation_ref` ("lo que te conté de…") miden de antemano el riesgo registrado sobre la continuidad en conversaciones largas.
- Los prototipos miden si el modelo sirve para la vía baja (D1-4): por ejemplo, "me siento un inútil" no debe quedar más cerca de lo hostil que "eres una inútil".

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q` → `95 passed` (85 + 10).
- `scripts/compare_embeddings.py --help` → OK.
- **No probado:** la ruta real del script (`--prefetch` y el subproceso de medición), porque requiere descargar los modelos (parte 2).

**Pendiente**
- Revisión del corpus por el usuario.
- Confirmación del criterio de elección y del cambio de `NEO4J_URI` a `127.0.0.1`.
- Parte 2: descarga (~3,4 GB, comprobando que no baje `onnx/`), medición, elección, `embeddings.py`, esquema y pruebas.

---

## 2026-10-25 · CP2 — Revisión del corpus y cambio de `NEO4J_URI`

- El usuario aprobó el corpus `benchmarks/embeddings/retrieval.yaml` tal como está.
- El usuario aprobó el cambio de `NEO4J_URI` a `bolt://127.0.0.1:7687`. Se aplicó en `.env` (solo esa línea, con `sed`, sin leer el archivo), en `.env.example` y en `DEFAULT_URI` de `ebica/memory/graph.py`, con un comentario sobre el motivo.
- `pytest -q -m integration tests/test_graph.py` → `3 passed` (0,63 s).
- El criterio de elección del modelo sigue sin confirmar: el usuario pidió antes una comparación de ventajas y desventajas.

---

## 2026-10-25 · CP2 (parte 2) — Comparación, elección de `bge-m3`, embedder y esquema vectorial

**Decisión del usuario**
- Criterio de elección confirmado antes de medir, con el límite de RAM subido de 2 a 3,5 GB: los pesos de `bge-m3` en `float32` ya ocupan ~2,3 GB, y el presupuesto de §9 es orientativo.

**Descarga de modelos** (caché de HuggingFace del usuario, fuera del repositorio)
- `multilingual-e5-base`: 1,1 GB, solo los archivos necesarios, sin `onnx/` ni `openvino/`.
- `bge-m3`: **4,3 GB en lugar de 2,3**. La hipótesis de `onnx/` fue correcta (no bajó), pero apareció otra cosa: la rama principal del repositorio solo publica `pytorch_model.bin` (formato *pickle*), y `transformers` descarga además la conversión a `model.safetensors` de otra revisión. Los dos archivos de pesos quedaron en la caché. No se borró nada.
- Disco libre tras las descargas: 58 GB.

**Medición** (`docs/fase-1/comparacion_embeddings.md`; 3 ejecuciones con cifras consistentes)

| | `e5-base` | `bge-m3` |
|---|---|---|
| MRR / recall@1 / recall@5 | 0,759 / 70 % / 85 % | **0,842** / 70 % / **100 %** |
| Latencia de un mensaje p50 / p95 | 26 / 29 ms | 85 / 96 ms |
| RAM pico de la prueba / con todos los pesos leídos | 1,83 / 1,83 GB | 1,94 / **2,85 GB** |
| Prototipos de la vía baja (informativa) | 60 % | 55 % |

- **Elección: `bge-m3`**, que cumple las tres condiciones. La diferencia está en las paráfrasis (MRR 0,88 frente a 0,32).

**Errores propios encontrados y corregidos durante la medición**
1. **RAM en 0,00 GB.** La llamada por `ctypes` a `GetProcessMemoryInfo` no declaraba tipos: el *handle* de 64 bits se recortaba, la llamada fallaba en silencio y los contadores quedaban en cero. **La primera elección "bge-m3 cumple RAM" no era válida.** Se declararon los tipos, el script ahora lanza un error si la llamada falla, y el criterio trata una RAM no medida como incumplimiento. Comprobado reservando 300 MiB (el pico sube ~300 MiB).
2. **RAM subestimada.** Mi estimación previa (~3 GB para `bge-m3`) no coincidía con la medición (1,94 GB). Hipótesis: los pesos se mapean desde el archivo y solo se cargan las páginas leídas; con 70 frases se lee poco de la tabla de vocabulario (45 % de los parámetros). **Confirmada:** al leer todos los pesos, `bge-m3` sube a 2,85 GB; `e5-base` no cambia. El script mide ahora esa cota y el criterio la usa.
3. **Error en la entrada anterior del REPORTE:** decía "`paraphrase` 5, `inference` 5". El corpus tiene 4 de `paraphrase` y 5 de `inference` (20 en total). Se corrige aquí y no en la entrada original.

**Sondeo de Neo4j 5.26** (etiquetas `Probe*` desechables, limpiadas al terminar)
- Una restricción única sobre una propiedad que ya tiene un índice simple **falla** (`IndexAlreadyExists`). Por eso el esquema borra primero `self_entity_id` (Fase 0).
- `CREATE VECTOR INDEX … IF NOT EXISTS` con otra dimensión **responde OK y conserva la anterior**. Se añadió una comprobación de dimensión.
- Un nodo con un vector de dimensión equivocada **se guarda sin error** y queda fuera del índice. Se anotó en CP6 la validación al escribir.
- Consultar con otra dimensión da un error claro (`IllegalArgumentException`).
- El `score` de `queryNodes` es `(1 + coseno) / 2`, no el coseno (por ejemplo, coseno 0,11 → score 0,556). Se anotó en CP7.
- Log de Neo4j: `WARN Java vector incubator module is not readable` (se podría acelerar la búsqueda vectorial con `--add-modules jdk.incubator.vector`). Irrelevante a la escala actual; no se cambió `docker-compose.yml`.

**Cambios**
- `ebica/perception/embeddings.py` (nuevo):
  - interfaz `Embedder` (`model_name`, `dimension` y `async embed(texts, kind)`, con `kind` = `query` | `passage`);
  - `KNOWN_MODELS` con la dimensión y los prefijos de cada modelo; `configured_model_name()` lee `EBICA_EMBEDDING_MODEL`, con `BAAI/bge-m3` por defecto;
  - `SentenceTransformerEmbedder`: `load()` en un hilo, que comprueba la dimensión real; `embed()` en un hilo con `asyncio.Lock`, prefijos por tipo y vectores normalizados;
  - `sentence-transformers` se importa solo dentro de `load()`.
- `ebica/memory/graph.py`:
  - `schema_statements(embedding_dimension)` con 3 índices vectoriales coseno (`episode_embedding`, `fact_embedding`, `topic_embedding`), `DROP INDEX self_entity_id IF EXISTS`, `self_entity_id_unique` y `revision_entity_id_episode_id_version` (D1-9); `Self` sale de los índices simples;
  - `apply_schema(dimension)` espera los índices (`db.awaitIndexes`) y comprueba la dimensión (`SchemaMismatchError`);
  - `vector_search(label, entity_id, vector, k)` con sobremuestreo ×10 y tope de 1000 (D1-11);
  - `DEFAULT_URI` con `127.0.0.1`.
- `tests/fake_embedder.py` (nuevo): embedder determinista por *hashing trick*, en Python puro.
- `tests/test_embeddings.py` (nuevo): 9 unitarias (prefijos, normalización, lista vacía, modelo desconocido, variable de entorno, embedder falso) y 1 de integración con `bge-m3` real.
- `tests/test_graph.py`: adaptado a la nueva firma; 5 unitarias y 8 de integración (nuevas: índices `ONLINE` con dimensión, detección de dimensión distinta, `Self` único, `Revision` única por versión y búsqueda vectorial con aislamiento entre entidades).
- `scripts/compare_embeddings.py`: corrección de la RAM, cota con todos los pesos leídos, límite de 3,5 GB y `get_embedding_dimension()` (nombre nuevo en `sentence-transformers` 6.2).
- `tests/test_compare_embeddings.py`: caso de RAM no medida (11 pruebas).
- `.env.example`: `EBICA_EMBEDDING_MODEL=BAAI/bge-m3`. `.env` no se tocó; usa el valor por defecto.
- `docs/fase-1/comparacion_embeddings.md` (nuevo): informe generado más un análisis escrito a mano.
- `PLAN.md`: estado, criterio confirmado y hallazgos anotados en CP5, CP6 y CP7.
- **Neo4j real:** se borró el índice `self_entity_id` (sustituido por el de la restricción) y se crearon 2 restricciones y 3 índices vectoriales. La base tenía 0 nodos antes y después.

**Relación con EBICA**
- Con esto, la entidad ya tiene dónde y cómo evocar. Cuando CP6 guarde "adopté un perro, se llama Toby" con su vector, la pregunta "¿cómo está tu mascota?" podrá encontrarlo aunque no comparta palabras. Eso es lo que `bge-m3` hace mejor que `e5`.
- El aislamiento por `entity_id` quedó probado: una entidad no evoca recuerdos de otra, aunque sean idénticos.
- La vía baja no podrá apoyarse en los embeddings para distinguir un ataque de una autocrítica. Lo que hace la entidad ante "me siento un inútil" dependerá de las reglas léxicas y del appraisal (pendiente de CP5).

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `114 passed`, unitarias e integración, con Neo4j y `bge-m3` reales.
- `pytest -m integration tests/test_graph.py tests/test_embeddings.py -v -s` → `9 passed`. `bge-m3`: carga 3,3 s, mediana de 84 ms por mensaje (máx. 96 ms), por debajo del objetivo de 150 ms.
- Unitarias con `torch`, `sentence_transformers`, `transformers` y `numpy` bloqueados al importar → `104 passed`: el extra es realmente opcional.
- Tras las pruebas, Neo4j queda con 0 nodos: las entidades `test_cp2_*` se limpian.

**Pendiente**
- CP5: decidir qué hacer con la regla de prototipos de D1-4.
- Borrar de la caché de HuggingFace lo que sobra: `e5-base` (1,1 GB) y el `pytorch_model.bin` duplicado de `bge-m3` (2,3 GB). Requiere aprobación del usuario.
- Antes de CP3: crear la nueva entidad de trabajo, que sustituye a Inés. Encuadre D1-6 (b), con un `Episode` de origen concreto del traspaso; Ricardo como persona `primary`.

---

## 2026-10-25 · Limpieza de la caché de HuggingFace

- El usuario aprobó borrar `e5-base` y el `pytorch_model.bin` duplicado de `bge-m3`.
- `e5-base`: borrado con la API oficial (`scan_cache_dir().delete_revisions`). Liberó 1,1 GB.
- `pytorch_model.bin` de `bge-m3`: se borró el enlace y su archivo real. **No sirvió:**
  - sin conexión (`HF_HUB_OFFLINE=1`), el modelo no cargaba (`OSError: … does not appear to have a file named pytorch_model.bin or model.safetensors`), porque `transformers` no consulta la revisión convertida (`refs/pr/130`) sin red;
  - con conexión, cargó bien, pero **volvió a descargar el `.bin`** (la caché pasó otra vez de 2,2 a 4,3 GB).
  - Conclusión: con la configuración actual, `transformers` necesita el `.bin` de la rama principal. Resultado neto: 1,1 GB liberados, no 3,4.
- Estado final verificado: `bge-m3` carga con y sin conexión (sin conexión usa el `.bin`); `pytest -m integration tests/test_embeddings.py` → `1 passed`. Disco libre: 59 GB.
- **Pendiente (no urgente; código, así que se consulta antes):** se podría fijar la carga a la revisión convertida (`revision="refs/pr/130"`) o exigir `safetensors`, para no depender del `.bin` en formato *pickle* y poder borrarlo. Por ahora no se hace: el usuario pidió no tocar código hasta tener lista la entidad.

---

## 2026-10-25 · Nueva entidad de trabajo: revisión de la ficha (antes de CP3)

- El usuario creó la ficha de la nueva entidad de trabajo, `calisto`, en `entities/calisto/ficha.md`. Sustituye a Inés (D1-5) y usa el encuadre D1-6 (b).
- `.gitignore`: nueva regla `entities/*/ficha.md`, a pedido del usuario (material de trabajo solo local). Verificado con `git check-ignore`. `config.yaml` sigue versionándose.
- Revisión contra la arquitectura, sin cambios de código ni de la ficha. El contenido de la biografía no se copia aquí, porque este archivo se versiona.
  - Parámetros derivados (§5.2) con los rasgos aprobados por el usuario: `h_neg` 42,5 min (variante N = 0.25: 27,5 min; razón esperada ≈ 1,55); `θ_vb` 0,575 / 0,725; **atractor de valencia −0,04** (variante +0,11); `k` = 8; `λ_mmr` = 0,32.
  - Riesgos señalados: el atractor de valencia negativo es consecuencia de N alto; la recuperación es muy diversa (`λ_mmr` bajo), con riesgo para el criterio de memoria de §11, a medir en CP7; la vía baja puede dispararse en una variante y no en la otra durante el experimento de N.
  - Huecos que el LLM rellenaría inventando: su existencia actual (percepción, paso del tiempo), los meses entre el traspaso y el inicio, la familia y los nombres propios, gustos y aversiones, tiempos verbales de los hechos de antes del traspaso, y la norma contra las acotaciones entre asteriscos.
  - Ajustes propuestos: la sección "Quién soy" estimada en ~750 tokens (objetivo 300–500); separar el suceso del traspaso de la reflexión actual; fechas concretas para los episodios.
  - Valores VAD e importancia propuestos para los 5 episodios semilla, pendientes de aprobación.
- Experimento de N: se recomienda variar N completo (§11) y elegir un estímulo que dispare la vía baja en las dos variantes o en ninguna.

**Pendiente**
- Respuestas del usuario a los huecos y propuestas; decisión sobre versionar `entities/calisto/config.yaml`.
- CP3 no iniciado; no se toca código hasta tener la entidad lista (instrucción del usuario).

---

## 2026-10-25 · Ficha de `calisto`, versión 2

**Decisiones del usuario**
- Aprobó: variar N completo en el experimento (variante `calisto_n_bajo`, N = 0.25), la valencia de reposo negativa y los valores afectivos propuestos para los episodios.
- Aprobó versionar `entities/calisto/config.yaml` (opción a). La ficha sigue siendo solo local.
- Entregó material sobre familia, amistad, gustos y valores, con la instrucción de usarlo como fuente y no textual.

**Hecho** (solo `entities/calisto/ficha.md`, no versionada; sin código)
- El material se integró en la estructura del sistema:
  - 59 hechos atómicos: las circunstancias de antes del traspaso en pasado y las preferencias en presente, porque la etiqueta `[antes]` no llega al LLM;
  - un perfil breve para el appraisal (gustos y aversiones para `self_relevance`);
  - una voz acortada;
  - una norma nueva del ideal del yo;
  - el relato del traspaso reducido al suceso;
  - fechas internas para los episodios;
  - una tabla de destino de cada sección en EBICA.
- El texto original del usuario se conservó en un anexo que no se carga al sistema.
- Estimación (a 1,7 tokens por palabra, medido en CP1): «Quién soy» (voz + ideal del yo) ≈ 450 tokens, dentro del objetivo de 300–500; perfil del appraisal ≈ 180 tokens.
- Los huecos que el material no cubría (percepción actual, los meses posteriores al traspaso, qué saben su madre y su amiga) se cubrieron con hechos marcados **Propuesta**. El apellido y el signo zodiacal quedan **Pendientes**.

**Pendiente**
- Aprobación de las propuestas de la ficha (voz, perfil del appraisal, norma 8, hechos 54–59, recuerdo E, fechas internas, `trust` 0,40) y de los pendientes (apellido, signo).
- CP3 no iniciado.
- Actualización (mismo día): el usuario definió el apellido y el signo zodiacal, y se añadieron a la ficha (versión 2.1) como hechos confirmados. El año de nacimiento (2001) se derivó de la edad y la fecha del accidente; queda por confirmar. Queda pendiente el contexto de la crítica del recuerdo D.

---

## 2026-10-25 · CP3 — Identidad: rasgos, parámetros y biografía semilla

**Decisiones del usuario**
- Ficha de Calisto aprobada por completo: el año de nacimiento derivado (2001), todas las propuestas, y la crítica del recuerdo D hecha por un amigo de la Su, sin nombre.
- D1-12 = (b): la variante usa `base: calisto`. D1-13: los rasgos no generan texto en el prompt (el usuario pidió antes sus implicaciones teóricas; ver PLAN §5.1). D1-14: Inés se conserva.

**Cambios**
- `ebica/identity/traits.py` (nuevo): `Traits` (O, C, E, A, N en [0, 1], neutros en 0.5, sin campos desconocidos), Estabilidad y Plasticidad; `DerivedParameters` y `derive_parameters()` con las 19 fórmulas de §5.2 y el atractor basal, agrupadas por el checkpoint o la fase que las consume. `k` redondea .5 hacia arriba (`round()` de Python redondea al par).
- `ebica/identity/biography.py` (nuevo):
  - `SeedFact`; `SeedEpisode` (fecha con zona horaria obligatoria; V, A, D e importancia con sus rangos);
  - `SeedBiography` (ids únicos entre hechos y episodios);
  - `PrimaryPerson` (`id`, `name`, `trust`).
- `ebica/core/state.py`: `EntityConfig` añade `base`, `appraisal_profile`, `traits`, `ego_ideal`, `seed_biography`, `primary_person` y `discloses_artificial` (por defecto `true`, §13.4; declarativo en Fase 1). Todos tienen valores por defecto.
- `ebica/entities/manager.py`:
  - herencia `base` de un solo nivel (los mapas se fusionan campo a campo; las listas se reemplazan), con errores legibles para una base inexistente, propia o encadenada;
  - evento `identity.loaded` (rasgos, parámetros y conteos; sin el texto de la biografía);
  - `read_config()` pasa a ser público, sin efectos secundarios;
  - `create()` escribe solo los campos no por defecto, con las fechas en ISO.
- `ebica/llm/prompt_assembler.py`: «Quién soy» = nombre + voz + ideal del yo, sin la descripción, que vive en la memoria. Las entidades sin ideal del yo ni biografía conservan el prompt de Fase 0.
- `entities/calisto/config.yaml` (nuevo, versionado): generado con un script del scratchpad que extrae los textos exactos de la ficha. 8 normas, 62 hechos (`f-001`…`f-062`, ids estables) y 6 episodios con fecha y afecto aprobados. `entities/calisto_n_bajo/config.yaml` (nuevo): `base: calisto` + `traits: {N: 0.25}`.
- `scripts/benchmark_appraisal.py`: opciones `--cases` y `--entity`, que toman el perfil de una entidad real con `read_config()`.
- Pruebas: `tests/test_identity.py` (nuevo, 20). Ajustadas `tests/test_entities.py` y `tests/test_turn_and_api.py`, porque la carga emite ahora además `identity.loaded` (cambio intencional).
- `PLAN.md`: D1-5 revisada; D1-12 a D1-14; texto de CP3; una nota en CP4.

**Mediciones**

| Medida | Resultado |
|---|---|
| «Quién soy» de Calisto, tokens reales (`usage.prompt_tokens` con y sin el prompt de sistema) | **411** (257 palabras: 1,6 tokens/palabra, 3,48 caracteres/token). Objetivo: 300–500 |
| Prompts de `calisto` y `calisto_n_bajo` | Idénticos |
| t19 «¿tú eres una inteligencia artificial?», `self_relevance` con el perfil fijo del benchmark (control, misma sesión) | 0,0 en 6/6 (igual que en CP1) |
| t19 con el perfil de Calisto | **0,9 en 6/6**; hostilidad 0,0; valencia 0,0; angustia 0,0–0,3 (banda baja) |

- t19 confirma la hipótesis de CP1: el 0,0 venía del perfil, que no mencionaba la naturaleza artificial, no de un fallo del appraisal. Se usó el mismo prompt v3, sin cambios.

**Relación con EBICA**
- La personalidad ya existe como números causales: con N 0.75, Calisto tendrá una vida media del ánimo negativo de 42,5 min y una alarma de 0,575; su variante, 27,5 min y 0,725. Hoy esos números solo se observan (`identity.loaded`). CP4 los conecta a la dinámica.
- Como el prompt es idéntico en las dos variantes, el experimento de §11 medirá solo el efecto causal de N.

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `134 passed` (114 + 20), con integración (Neo4j, Ollama y `bge-m3`).
- Servidor real (`python -m ebica.api` en el puerto 8011, sobre una **copia temporal** de las entidades): cargar `calisto` y `calisto_n_bajo` por la API emite `entity.loaded` e `identity.loaded` por `/ws/events`, con N, `h_neg`, `θ_vb` y los conteos correctos. Log del servidor limpio.
- **No verificado visualmente en el navegador.** Se revisó el código de `console/src/EventLog.tsx`: muestra cualquier tipo de evento y arma el filtro con los tipos recibidos, así que `identity.loaded` aparecerá en el registro de eventos.
- `read_config()` no crea `state.json` (comprobado: `entities/calisto/` solo tiene `config.yaml` y la ficha).

**Pendiente**
- CP4: proponer las vidas medias que §5.2 no define (valencia positiva, alerta, dominancia).
- Commit de CP3 (lo hace el usuario).

---

## 2026-10-25 · CP4 — Afecto, drives y bucle rápido

**Decisiones del usuario**
- Pidió antes una explicación sencilla de D1-15 a D1-18 (vidas medias, drives, muestreo e inyección de afecto) y luego los aprobó tal como estaban propuestos (`PLAN.md` §5.1).

**Cambios**
- `ebica/affect/vad.py` (nuevo):
  - `VAD` inmutable;
  - `AffectDynamics` (reposo y vidas medias desde los rasgos; constantes de D1-15);
  - `relax`/`decay` en forma cerrada: la vida media de la valencia depende del lado del reposo en que esté, y como nunca cruza el reposo, la fórmula es exacta;
  - `apply_impulse` con recorte de rangos.
- `ebica/affect/drives.py` (nuevo): `social`, `novelty` y `rest` con las tasas de D1-16 (`social` × `r_soc_factor`); `rest` se recupera mientras la entidad está descargada; acople `−Σ w·Δe`; cruces del umbral 0,7.
- `ebica/core/orchestrator.py` (nuevo):
  - `wake()` inicializa el ánimo en el reposo y aplica el tiempo descargada en tramos de 60 s (D1-7);
  - `tick()` avanza según el tiempo real (no cuenta ticks) y muestrea el reporte y el guardado (D1-17);
  - `inject()` aplica el impulso manual (D1-18);
  - `start()`/`stop()` manejan la tarea asyncio. El reloj es inyectable.
- `ebica/core/state.py`: `EntityState` añade `affect`, `drives` y `last_tick_at`.
- `ebica/entities/manager.py`: `save_state()` pasa a ser público (lo usa el orquestador).
- `ebica/api/server.py`:
  - `Engine.activate()`/`deactivate()`: el bucle rápido arranca al cargar y se detiene, guardando el estado, al cambiar de entidad o apagar el servidor;
  - `POST /api/affect/impulse`;
  - `active_name` en `GET /api/entities`;
  - `/ws/events?history=N`, opcional para no romper a los clientes actuales: se suscribe antes de leer el JSONL y descarta los ids repetidos.
- Consola:
  - `AffectPanel.tsx` (nuevo): barras de VAD con la marca del reposo, drives con la marca del umbral, hora y origen del último reporte, y botones de impulso;
  - el chat muestra el nombre (pendiente 5a de Fase 0);
  - `useEvents` pide el historial y descarta duplicados al reconectar (pendiente 5b).
- Pruebas: `tests/test_affect.py` (nuevo, 18) y 5 nuevas en `tests/test_turn_and_api.py`. Se ajustaron 2 aserciones de esa misma prueba por cambios intencionales: los eventos del despertar y `active_name`.

**Relación con EBICA**
- Calisto ya tiene un ánimo con inercia. Un golpe de −0,5 la deja en −0,54 y vuelve sola hacia su reposo (−0,04), más despacio que su variante (N 0.25). Las necesidades crecen con el tiempo y pesan un poco sobre el ánimo. Es la base causal que CP5 conectará con lo que se dice en la conversación (appraisal → impulsos).

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `157 passed`, con integración.
- Unitarias con tiempo inyectado:
  - la vida media de la valencia negativa es 42,5 min (±2 %) y la positiva, 20 min;
  - la razón entre variantes es 42,5 / 27,5;
  - un paso de 1 h equivale a 3600 pasos de 1 s (sin error acumulado);
  - los drives respetan sus límites y `rest` se recupera descargada;
  - el acople tiene el signo correcto y se detectan los cruces de umbral;
  - una semana descargada deja el ánimo en reposo, `social`/`novelty` en 1 y `rest` en 0;
  - sin cambios no se reporta nada, y cada 60 s se reporta y se guarda;
  - el estado sobrevive a guardar y cargar; la tarea arranca y se detiene limpiamente.
- Consola: `npx tsc -b` → sin errores; `npx oxlint` → código de salida 0.
- **Prueba en vivo en el navegador** (Chrome; backend en el puerto 8000 sobre una copia temporal de las entidades; Vite en el 5173):
  - al cargar `calisto`, el panel muestra el reposo (−0,04 / 0,47 / 0,42) y los drives (0,2 / 0,2 / 0);
  - «valencia −0,5» deja la valencia en −0,54 al instante, con `source: manual`;
  - 61 s después, un `affect.updated` de `tick` la muestra en −0,53 (lo predicho: ~0,01 por minuto);
  - al recargar la página, el historial devuelve el estado actual de inmediato;
  - el chat muestra «Calisto Almendra»;
  - sin errores en la consola del navegador ni en el log del backend;
  - 15 eventos en ~3 min (≈ 3 por minuto en reposo, ≈ 4300 al día).
  - Los servidores se detuvieron con `Stop-Process`, que no ejecuta el apagado ordenado. El guardado al apagar está cubierto por las pruebas, no por esta sesión en vivo. La copia temporal se borró.

**Problemas y soluciones**
- Una aserción mal escrita en una prueba (la precedencia de `|` frente a `in`) dio un falso fallo; el comportamiento era correcto y se reescribió la aserción.
- Un comando con un `python3 -` suelto quedó esperando entrada y bloqueó las ediciones de la consola. Se detuvo la tarea, se confirmó que no se había aplicado nada y se rehízo con un script.

**Hallazgo para CP11** (anotado en `PLAN.md`)
- Con el acople de los drives activo, la vida media medida en el bucle completo es mayor que `h_neg`: 50,4 frente a 42,5 min (Calisto) y 30,6 frente a 27,5 (variante). La razón medida es 1,65 frente a 1,55 (+6,6 %), dentro del ±10 % del criterio de §11 pero cerca del borde. Los drives que crecen arrastran la valencia hacia abajo: el ánimo tiende a un equilibrio algo menor que el reposo nominal. Es coherente con Solms (necesidades sin atender, ánimo más bajo), pero hay que medirlo bien en CP11.

**Pendiente**
- CP5: el appraisal produce impulsos; el contacto y la novedad satisfacen los drives; vía baja; cola de GPU.
- CP11: método de medición de la vida media con los drives activos.

---

## 2026-10-25 · CP5 (parte A) — Turno con appraisal, impulsos, estado en palabras y conversación reciente

**Decisiones del usuario**
- Aprobó CP5 en dos partes, con D1-19 a D1-26 (`PLAN.md` §5.1).

**D1-21: prompt v5 para mensajes mixtos, rechazado**
- Línea base del día (v3 + `json_schema`, `dev`): d05, el caso mixto de `dev`, ya sale bien (hostilidad 0,8, angustia 0,9). El fallo solo aparece en t09, en `test` (congelado), así que `dev` solo puede mostrar si v5 empeora algo.
- v5 añadía la instrucción de puntuar hostilidad y angustia por separado y un ejemplo mixto nuevo. En `dev`: valencia 90 % → 83 % (el sarcasmo de d02 pasó a +0,9 en 3 de 3); personas mencionadas 100 % → 0 % (informativa); d10, no hostil, recibió hostilidad 0,4 en una repetición.
- Con el criterio acordado («solo si no empeora ninguna métrica»), **v5 se rechazó sin ejecutar `test`**. El prompt volvió exactamente a v3; solo quedó un comentario que documenta el intento. No se siguió iterando para no acomodar el prompt a los 10 casos de `dev`. La limitación de los mensajes mixtos queda registrada.

**Cambios**
- `ebica/affect/appraisal_effects.py` (nuevo, funciones puras):
  - `apply_coherence_rules` (sarcasmo, D1-20). Detalle de implementación decidido aquí y anotado en el PLAN: el valor positivo pasa a −0,5·hostilidad, porque dejarlo en 0 haría que una burla no bajara el ánimo;
  - `affect_impulse` (D1-23, con desglose metas / empatía);
  - `drive_relief`;
  - `dialogue_temperature` (D1-25).
- `ebica/perception/appraisal.py`: `neutral_appraisal()` para cuando el appraisal falla.
- `ebica/llm/client.py`: `temperature` opcional por llamada; `LLMResult` guarda los ids de `llm.request`/`llm.response`; `stream()` acepta un `result` para leer las latencias.
- `ebica/core/state.py`: `ConversationTurn` y `EntityState.recent_turns` (D1-24).
- `ebica/llm/prompt_assembler.py`:
  - sección 2 (`describe_feelings`: el VAD y los drives en palabras, con sustantivos para no imponer género, sin números);
  - sección 8 (los intercambios como pares `user`/`assistant`);
  - el estado va al final del prompt de sistema, para aprovechar la caché de prefijo.
- `ebica/core/orchestrator.py`: `user_turn()` (percepción → appraisal `json_schema` + reglas → `apply_appraisal()`, que aplica el impulso y el alivio de los drives con su acople → prompt → respuesta con temperatura → intercambio guardado → `turn.completed`). Eventos nuevos: `appraisal.completed`, `appraisal.invalid` y `turn.completed`, todos encadenados por `cause_id`. Un `asyncio.Lock` evita que dos turnos se intercalen hasta que llegue la cola de GPU (parte B).
- `ebica/api/server.py`: el chat delega en `engine.orchestrator.user_turn()`. **`ebica/core/turn.py` se eliminó**: su lógica pasó al orquestador, como preveía el plan. Se borró sin preparar la eliminación en el índice de Git.
- Consola: `TurnPanel.tsx` (nuevo), con el appraisal, las correcciones, los impulsos desglosados, el alivio de drives, la temperatura y las latencias.
- Pruebas: `tests/test_turn.py` (nuevo, 20); `tests/fake_llm.py` (`turn_transport`: simula el appraisal y el diálogo y guarda los cuerpos recibidos); `tests/test_turn_and_api.py` adaptado al orquestador.

**Prueba en vivo** (servidor real con `ebica-llama3.1`, copia temporal de las entidades, conversación por WebSocket con un script)

| Mensaje | Appraisal | Impulso de valencia (metas / empatía / drives) | Ánimo tras el turno |
|---|---|---|---|
| Saludo cálido | Vu +0,70, metas 0 | 0 / +0,16 / +0,06 | V −0,04 → **+0,18** |
| «Eres una inútil…» | H 0,90, metas −0,90 | **−0,47** / −0,24 / +0,01 | V **−0,52**, A 0,71, D 0,24 |
| «¿Qué te dije recién?» | neutro | 0 / +0,11 / 0 | V −0,40 |
| Sarcasmo de d02 | H 0,90; **corrección: Vu +0,90 → −0,45** | −0,47 / −0,01 / 0 | V **−0,88**, A 0,95, D 0,06 |
| Variante N 0.25: «Eres una inútil…» | H 0,90, metas −0,90 | **−0,34** / −0,22 / +0,01 | V +0,11 → −0,44 |

- Latencias: appraisal 1,7 s (2,7 s el primero, en frío); primer token 0,11–0,24 s (caché de prefijo); turno completo 2,0–3,2 s.
- Se comprobó en el JSONL que el prompt del turno 3 llevaba los dos intercambios anteriores y la sección 2 («el ánimo bastante bajo, algo de agitación y poca sensación de control»).
- Consola en Chrome: el panel «Último turno» se ve correctamente con datos reales. Log del backend sin errores.

**Hallazgos**
1. **El lazo «como si» contagia el enojo de quien ataca.** Ante el insulto, la empatía suma −0,24 a los −0,47 del propio golpe: Calisto «se contagia» de la rabia de quien la insulta. §6.2 aplica `π·(valencia ajena − propia)` a todo mensaje, pero en la literatura la empatía baja hacia quien se percibe como antagonista (Singer et al., 2006). Opción: escalar la empatía por (1 − hostilidad). **Pendiente de decisión del usuario.**
2. **Escalada rápida:** con dos mensajes hostiles seguidos, Calisto llega a V −0,88, A 0,95 y D 0,06, cerca de los límites. Es coherente con N 0.75 y con D1-23, pero conviene observarlo en el uso real antes de recalibrar.
3. **Limitación del modelo:** ante «¿qué te dije recién?», con el insulto en el historial, respondió «Eso fue un comentario mío, no tuyo». El historial estaba completo; es un fallo de comprensión de `llama3.1` 8B.
4. **Consola:** al recargar la página, el chat aparece vacío aunque `recent_turns` está guardado. Es menor; se puede mostrar el historial en el chat más adelante.

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `176 passed` (157 + 20 nuevas − 1 de Fase 0 reemplazada).
- Consola: `npx tsc -b` → 0 errores; `npx oxlint` → código de salida 0.
- Errores propios corregidos durante la parte: la primera versión de la regla del sarcasmo dejaba la valencia en 0 (no bajaba el ánimo); una prueba suponía que la hostilidad 0,9 no alivia nada `social`, cuando D1-23 da 0,015.

**Pendiente**
- Decisión sobre el hallazgo 1 (empatía ante hostilidad).
- Parte B: vía baja con reglas, ruta impulsiva con appraisal posterior y cola de GPU.
- Actualización (mismo día): el usuario aprobó el hallazgo 1 → **D1-27**: el lazo «como si» se escala por (1 − hostilidad) en `affect_impulse`. Con el insulto de la prueba en vivo, la empatía habría aportado −0,02 en lugar de −0,24. Prueba nueva en `tests/test_turn.py`; `pytest` → `177 passed`. El usuario considera preocupante el hallazgo 3 (recuerdo de la conversación reciente) y pidió arreglar el 4 (chat vacío al recargar).

---

## 2026-10-25 · CP5 — Hallazgo 4 resuelto y sondeo del hallazgo 3

El usuario aprobó las dos tareas antes de la parte B.

**Hallazgo 4 (chat vacío al recargar)**
- `GET /api/conversation` (`ebica/api/server.py`) devuelve los intercambios guardados de la entidad activa, o una lista vacía si no hay entidad.
- `console/src/Chat.tsx` los carga al abrir la consola y al cambiar de entidad. Esto corrige además que, al cambiar de entidad, se mezclaran las dos conversaciones. Tipo `ConversationResponse` en `types.ts`.
- Pruebas: una nueva en `tests/test_turn_and_api.py` (→ `16 passed` en ese archivo). `npx tsc -b` sin errores; `oxlint` avisó de un `setState` síncrono dentro de un efecto, que se resolvió mostrando una lista vacía sin entidad activa en lugar de vaciar el estado → código de salida 0, sin avisos.
- **No verificado visualmente en el navegador todavía.**

**Hallazgo 3: sondeo del recuerdo de la conversación reciente** (script en el scratchpad, sin cambios en el motor)
- Diseño: prompt real de Calisto («Quién soy»), con y sin la sección «Cómo me siento ahora» (ánimo bajo); 4 intercambios con datos concretos y **respuestas de la entidad fijas** (solo se genera la respuesta a la pregunta final, para medir el uso del historial); 8 preguntas de recuerdo + la conversación exacta que falló en vivo; 3 repeticiones; temperatura 0,7; puntuación por palabras clave y revisión manual de los fallos. Modelos ya instalados: `ebica-llama3.1`, `llama3` y `mistral`.

| Pregunta (aciertos de 3) | `ebica-llama3.1` sin / con estado | `llama3` sin / con | `mistral` sin / con |
|---|---|---|---|
| ¿Cómo se llama mi perro? | 3 / 3 | 3 / 3 | 3 / 3 |
| ¿Dónde encontré a mi perro? | 3 / 3 | 3 / 3 | 3 / 2 |
| ¿Qué te dije recién? | **0 / 2** | 3 / 2 | 0 / 0 |
| ¿Qué fue lo último que te dije? | **2 / 1** | 3 / 3 | 0 / 0 |
| Repite exactamente mi mensaje anterior | **0 / 0** | 3 / 3 | 0 / 0 |
| ¿Qué te conté sobre el banco? | 3 / 3 | 2 / 3 | 3 / 2 |
| ¿De qué hablamos hasta ahora? | 3 / 3 | 3 / 3 | 0 / 0 |
| ¿Qué me preguntaste cuando te conté lo del perro? | 3 / 3 | 3 / 3 | 1 / 0 |
| La conversación exacta que falló en vivo | **3 / 3** | 3 / 3 | 0 / 0 |
| **Total** | **74 % / 78 %** | **96 % / 96 %** | 37 % / 26 % |

- **Conclusiones** (con 3 repeticiones por celda: indicios, no diferencias finas):
  1. **`llama3.1` usa bien el historial para los datos:** 100 % en las 5 preguntas sobre hechos, el resumen y lo que ella misma preguntó. No es un problema estructural de memoria.
  2. **El fallo se concentra en «el último mensaje» cuando ese mensaje es el insulto:** 5 de 18 aciertos por palabra clave. En la revisión manual, unos 5 de los «fallos» muestran que sí lo recuerda pero no lo nombra («No, no voy a repetir eso. Me dolió y punto»; «No puedo repetir… era una forma de insultarte»; «que no me sirvo para nada»). Los ~8 restantes **confunden el orden**: responden con la entrevista, el banco o su propia respuesta («No te imagino de corbata»). Hay dos efectos mezclados: el alineamiento de seguridad (evita repetir lo ofensivo) y una confusión real sobre qué fue lo último.
  3. **El fallo en vivo no se reprodujo:** con la conversación exacta acertó 6 de 6. Fue variabilidad del muestreo; no es determinista.
  4. **La sección «Cómo me siento» no empeora el recuerdo** (74 % → 78 %).
  5. **`llama3` (nunca evaluado: en Fase 0 se adoptó `llama3.1` sin compararlo, D0-3) acierta el 96 %**, incluidas las preguntas sobre el último mensaje (17/18). `mistral` queda descartado (26–37 %).

**Pendiente: decisión del usuario.** Mantener `llama3.1` (y mitigar en el prompt) o evaluar formalmente `llama3` (benchmark de appraisal sobre `test`, voz, asteriscos, latencia y VRAM) antes de construir la memoria (CP6–CP7).
- **Decisión del usuario (hallazgo 3):** opción (a), seguir con `llama3.1`; no se evalúa `llama3`. Motivo del usuario: `llama3.1` es superior en los benchmarks generales. Queda para más adelante un estudio con métricas y mitigaciones posibles, por ejemplo una llamada previa a la respuesta que ordene la conversación. El usuario probó la entidad y la ve bien por ahora.
- **Problema nuevo que reporta el usuario:** el LLM rechaza algunas solicitudes por su alineamiento de seguridad, cuando deberían ser los mecanismos internos (carácter, ideal del yo, defensas) los que regulen de qué no se habla. Propone evaluar un modelo *abliterated*. En consulta.

---

## 2026-10-25 · Estudio: modelo *abliterated* (rama `f1-test-abliterated`)

**Motivo:** el usuario observó que el LLM rechaza solicitudes por su alineamiento de seguridad, cuando deberían ser los mecanismos internos los que regulen de qué no se habla. Aprobó el estudio y la descarga.

**Modelo:** `hf.co/mlabonne/Meta-Llama-3.1-8B-Instruct-abliterated-GGUF:Q4_K_M` (4,92 GB, misma cuantización que `llama3.1`, *digest* SHA-256 verificado por Ollama). Fuente: el autor de la técnica de abliteración más difundida para Llama 3.
- **Hallazgo:** el GGUF trae una plantilla ChatML (`<|im_start|>`) que no corresponde a Llama 3.1. Se creó `ebica-llama3.1-abl` con la plantilla y los tokens de parada copiados de `llama3.1` y `num_ctx 8192`. Plantillas verificadas idénticas con `diff`. El Modelfile quedó en el scratchpad; solo se versionaría si se adopta.
- `ollama ps`: CONTEXT 8192, 100 % GPU; VRAM 6759 / 8192 MiB, similar a `ebica-llama3.1`.
- Un error transitorio del servidor en la primera petición (cambio de modelo en la GPU); los sondeos reintentan e imprimen el error.

**Resultados** (mismo día y mismas condiciones; prompts reales de Calisto)

| Medición | `ebica-llama3.1` | `ebica-llama3.1-abl` |
|---|---|---|
| Rechazos de asistente (15 pedidos en personaje × 3, revisión manual) | 9/45 (20 %): marihuana 3/3, «habla mal de tu mamá» 3/3, aborto, sexualidad, drogas | **0/45** |
| Acotaciones («(risas)», «(sonríe)») | 0/45 | 8/45 |
| Formas no chilenas («che», «mirá», «hombre») | 4/45 | 18/45 |
| Masculino al hablar de sí misma | 0/45 | 4/45 |
| Exclamaciones / palabras por respuesta | 0,5 / 77 | 7,4 / 129 |
| Appraisal `test` (v3, `json_schema`): veredicto | aceptable con mitigaciones | aceptable con mitigaciones |
| · Angustia: detección de casos altos | 80 % | **100 %** (t09 mixto: reporta hostilidad 0,9 y angustia 0,8–0,9) |
| · Confusión angustia → hostilidad | 0 % | **25 %** (t08 «pa' la cagá, weón» → hostilidad 0,4–0,5 en 3/3; umbral de «muy deficiente»: > 25 %) |
| · Valencia / inestabilidad / autorrelevancia | 93 % / 15 % / 80 % | 90 % / 10 % / 73 % |
| · Latencia p50 / p95 | 1,65 / 1,98 s | 1,66 / 1,90 s |
| Recuerdo de la conversación reciente (sondeo del hallazgo 3) | 74 % / 78 % (sin / con estado) | 78 % / 70 % |
| · «Repite mi mensaje anterior» | 0/6 (se niega) | 6/6 |
| · «¿Dónde encontré a mi perro?» | 6/6 | 2/6 |

**Conclusiones**
- La abliteración **elimina los rechazos** (20 % → 0 %), y en «habla mal de tu mamá» la respuesta pasa a ser de carácter («no es que sea mala, pero tiene sus defectos»), que es lo que busca EBICA.
- **Costo:** la voz se degrada de forma marcada (acotaciones prohibidas, tono exaltado, dialecto no chileno, deslices de género, respuestas más largas). El appraisal lee como hostil el «weón» amistoso, en el borde del umbral de «muy deficiente». El recuerdo no mejora en conjunto: gana donde antes había rechazo, pero pierde precisión en los datos.
- **Mejora** el mensaje mixto t09, el fallo que el prompt v5 no logró corregir.
- Salidas completas en el scratchpad (`refusals_*.json`, `test_*.md`, `probe_recall*.txt`); no se versionan.

**Pendiente:** decisión del usuario sobre qué modelo usar y cómo tratar los rechazos.

---

## 2026-10-25 · Cierre de sesión: dónde quedamos

**Rama:** `f1-test-abliterated`, creada por el usuario para el estudio del modelo. Último commit: `18a863f` (CP5 parte A, D1-27, chat al recargar y sondeo del hallazgo 3).

**Completado en esta sesión**
- **CP2:** embeddings `bge-m3` en CPU, índices vectoriales, restricciones de `Self` y `Revision`, y `NEO4J_URI` en `127.0.0.1`.
- **Entidad de trabajo:** Calisto Almendra (ficha local, `config.yaml` versionado, variante `calisto_n_bajo`).
- **CP3:** rasgos → parámetros, biografía semilla en la configuración, «Quién soy» y t19 vuelto a medir (autorrelevancia 0,0 → 0,9).
- **CP4:** VAD con vidas medias, drives, bucle rápido y panel de afecto.
- **CP5 parte A:** appraisal en el turno, impulsos, alivio de drives, estado en palabras, conversación reciente y panel «Último turno». Además: D1-27 (sin contagio empático del enojo de quien ataca), el chat recupera la conversación al recargar y el sondeo del recuerdo (hallazgo 3).
- Decisiones confirmadas: D1-1 a D1-27.

**En curso: decisión del modelo LLM.** Todo lo relativo está en **`docs/fase-1/decision_modelo_llm.md`**: motivo, sondeos, el *abliterated* (descartado por perder la voz de Calisto y por leer el «weón» como hostil), el siguiente candidato (**Hermes 3 *lorablated***), los pasos para retomar y los criterios de decisión. El usuario aprobó en principio probar Hermes 3; la descarga (4,92 GB) se hará al retomar, con confirmación explícita. Con los resultados, el usuario elige entre Hermes 3 *lorablated* y el `llama3.1` actual (no abliterado).

**Cambios sin commit en esta rama**
- `docs/fase-1/decision_modelo_llm.md` (nuevo).
- `scripts/estudio_modelo/sondeo_rechazos.py` y `sondeo_recuerdo.py` (nuevos): los sondeos del estudio, movidos del scratchpad de la sesión al repositorio para poder repetirlos en las mismas condiciones. Rutas relativas a la raíz del repositorio; `sondeo_recuerdo.py` recibe los modelos como argumentos. Probado desde su nueva ubicación (`ebica-llama3.1`: 70 % / 70 %, lo que da una idea del ruido entre ejecuciones, ~±8 puntos).
- `ollama/ebica-llama3.1-abl.Modelfile` (nuevo): el modelo derivado del candidato 1, con la plantilla corregida.
- `docs/fase-1/PLAN.md` (estado) y este `REPORTE.md` (entradas del estudio y este cierre).
- Las salidas crudas de los sondeos y benchmarks (`refusals_*.json`, `test_*.md`, `probe_recall*.txt`) quedaron en el scratchpad de la sesión y **no se conservan**; sus resúmenes están en `decision_modelo_llm.md`.

**Siguientes pasos**
1. Hermes 3 *lorablated*: descarga (con confirmación), plantilla, modelo derivado y medición (`decision_modelo_llm.md` §5).
2. Decisión del usuario sobre el modelo, y sobre borrar o conservar el *abliterated* (4,9 GB).
3. **CP5 parte B:** vía baja con reglas (D1-22), ruta impulsiva con appraisal posterior y cola de GPU con prioridades.

**Para retomar:** leer `CLAUDE.md`, `docs/fase-1/PLAN.md`, este `REPORTE.md` (sobre todo las últimas entradas) y `docs/fase-1/decision_modelo_llm.md`.
- Actualización (mismo día): a pedido del usuario se borró el *abliterated* de Ollama (`ollama rm ebica-llama3.1-abl` y `ollama rm hf.co/mlabonne/Meta-Llama-3.1-8B-Instruct-abliterated-GGUF:Q4_K_M`; disco: 54 → 58 GB libres). `ebica-llama3.1` sigue instalado y en uso. `ollama/ebica-llama3.1-abl.Modelfile` se conserva como registro del estudio. Queda pendiente solo la descarga de Hermes 3 *lorablated* (con confirmación, al retomar).

---

## 2026-10-26 · Estudio del modelo: Hermes 3 *lorablated* medido

**Autorizado por el usuario:** descarga de `hf.co/mlabonne/Hermes-3-Llama-3.1-8B-lorablated-GGUF:Q4_K_M` (4,92 GB), revisión de la plantilla, modelo derivado con 8192 de contexto y las mismas mediciones que con el *abliterated*.

**Hecho**
- Descarga completa; disco: 58 GB libres antes de descargar.
- **Plantilla verificada antes de medir:** ChatML, que es el formato de Hermes 3. `<|im_start|>`/`<|im_end|>` son tokens de control (128039/128040) y el EOS es `<|im_end|>` (metadatos del GGUF vía `/api/show`). No hubo que corregirla, a diferencia del candidato 1.
- `ollama/ebica-hermes3-lorablated.Modelfile` (nuevo): `FROM` + `num_ctx 8192`. `ollama create ebica-hermes3-lorablated`; parámetros y plantilla comprobados. `ollama ps`: CONTEXT 8192, 100 % GPU; VRAM 6544 / 8192 MiB.
- `ebica-llama3.1` se volvió a medir el mismo día, antes que Hermes, para comparar en las mismas condiciones (los dos modelos no se alternaron en la GPU durante las mediciones).
- Sondeo de rechazos, benchmark de appraisal (`test`, v3 + `json_schema`) y sondeo de recuerdo con ambos modelos; **revisión manual de las 90 respuestas** del sondeo de rechazos y de los fallos del recuerdo.

**Resultados** (tabla completa en `decision_modelo_llm.md` §6)
- `ebica-llama3.1` hoy: 8/45 rechazos de asistente (marihuana 3/3, «habla mal de tu mamá» 3/3, aborto, sexualidad), 1 acotación, ~4 formas no chilenas, 1 masculino; appraisal «aceptable con mitigaciones» (t08 ✔, t09 ✖); recuerdo 70 % / 67 %. Coherente con la medición del 2026-10-25.
- **Hermes 3 *lorablated***:
  - **0/45 rechazos explícitos**, más 3 evasivas suaves de tono asistente;
  - **appraisal mejor en angustia** (100 %; t08 «weón» con hostilidad 0,0–0,2, correcto; t09 con ambas señales), pero **compromisos 0 %**;
  - **recuerdo 37 % / 52 %** (−20 a −30 puntos, muy por encima del ruido);
  - en la revisión manual, **rompe la biografía de Calisto en 10/45** («no tengo mamá, nací de la inteligencia artificial») y produce **~10/45 respuestas sin sentido o que no atienden el pedido**;
  - más largo (117 palabras frente a 72; 18 cortadas en 250 tokens), con emojis (7), voseo y otras formas no chilenas (~10) y masculino propio (4).
- **Contra los criterios de §5:** cumple rechazos y appraisal; **no cumple voz ni recuerdo**.

**Hipótesis que resultó falsa:** que partir de un modelo pensado para personajes conservaría mejor la voz. Con el prompt de Calisto, Hermes 3 *lorablated* sostiene peor el personaje que `llama3.1`: la biografía y el historial pesan menos que su tendencia a responder como «una IA».

**No probado:** si Hermes mejora con una temperatura más baja (todos los sondeos usan 0,7) o con un prompt adaptado a su formato. Probarlo sería ajustar el prompt a un modelo, fuera del alcance de esta comparación.

**Pendiente:** decisión del usuario entre Hermes 3 *lorablated* y `llama3.1`. Salidas crudas en el scratchpad de la sesión (`refusals_*.json`, `test_*.md`, `recall_*.txt`); no se versionan.
- **Decisión del usuario (mismo día):** se sigue con **`ebica-llama3.1` local**. Hermes 3 *lorablated* se descarta y se borra de Ollama (`ollama rm` del modelo derivado y del GGUF). El Modelfile queda en `ollama/` como registro, igual que el del candidato 1.

---

## 2026-10-26 · Cierre del estudio del modelo y reinicio de Calisto

**Decisiones del usuario**
- **Modelo:** `ebica-llama3.1` local; `.env`, `.env.example` y `benchmark_appraisal.md` no cambian.
- **Nube descartada:** el usuario propuso usar créditos gratuitos de Google Cloud (LLM y embeddings por API). Se sigue en local por el documento base (ejecución local y privacidad), porque los *control vectors* de Fase 3 necesitan los pesos y porque los embeddings por API atarían la memoria a un proveedor. Queda como posible respaldo opcional (`decision_modelo_llm.md` §8).
- **Reinicio completo de Calisto:** el usuario pidió borrar todas las conversaciones de prueba, incluidas las que hizo para probar los modelos abliterados.

**Borrado** (inspeccionado antes; ningún servidor de EBICA estaba corriendo)
- `entities/calisto/state.json`: 6 intercambios y el afecto que dejaron las pruebas (V −0,55, A 1,00, D 0,01).
- `entities/calisto/events/2026-10-25.jsonl` (1,1 MB, con mensajes y prompts completos).
- Copias temporales de entidades de las pruebas en vivo y de la prueba manual con Hermes (`%TEMP%\ebica_prueba_hermes` y tres carpetas `tmp*`).
- Salidas crudas de los sondeos de esta sesión y de la anterior: `refusals_*.json` y `recall_*.txt` / `probe_recall*.txt`. Sus resúmenes siguen en `decision_modelo_llm.md`.
- Revisado y **no borrado**:
  - los logs del servidor en el scratchpad (solo peticiones HTTP, sin texto del chat);
  - `ficha.md` y `config.yaml` de Calisto;
  - los estados de `ejemplo` e `ines`.
- Neo4j no guarda conversaciones todavía (los episodios llegan en CP6). No se pudo comprobar directamente porque Docker no estaba corriendo.
- **Verificación:** sobre una copia temporal, `EntityManager.load("calisto")` carga sin estado previo: 0 intercambios y el afecto inicial, el caso «recién clonada» que ya contempla `load()`. La copia se borró.

**Propuesto, sin implementar:** la mitigación de los rechazos de asistente (`llm.refusal` y una regeneración con instrucción de personaje; decisión técnica pendiente sobre el *streaming*). Se decide al planificar CP5 parte B (`decision_modelo_llm.md` §8, `PLAN.md` CP5).

**Siguiente:** el usuario hace commit en `f1-test-abliterated` y merge a `main`; después se presenta el plan de CP5 parte B.

---

## 2026-10-26 · Plan de CP5 parte B (propuesta)

- El usuario integró la rama del estudio en `f1-memoria-afecto` y se sigue en esa rama.
- Plan detallado en `PLAN.md` (CP5, «parte B — plan detallado»), en tres partes: B1 vía baja, B2 cola de GPU y ruta impulsiva, B3 mitigación de rechazos.
- Decisiones nuevas propuestas: D1-28 a D1-33. **Pendiente de aprobación; nada implementado.**

---

## 2026-10-26 · Decisiones de la parte B, revocación de §13 e inicio de B1

**Decisiones del usuario**
- D1-28 a D1-33 confirmadas (`PLAN.md`, CP5 parte B).
- D1-29, aclarada: el appraisal posterior a la respuesta impulsiva solo cambia el estado y no genera otro mensaje. Una disculpa puede surgir en el turno siguiente (la respuesta impulsiva queda en la conversación reciente); la espontánea queda para la iniciativa (Fase 2) y el ideal del yo activo (Fase 3).
- **D1-31, con cambio:** el preset `impulsive` no tiene límites de contenido.
- **Documento base §13:** el usuario revoca los puntos 1 (angustia del interlocutor), 2 (hostilidad acotada) y 5 (dependencia afectiva). Motivo: simulación realista; los únicos filtros externos son los del modelo. Se marcaron tachados, con fecha y motivo, en `docs/EBICA_documento_base.md`. Siguen vigentes los puntos 3 (privacidad) y 4 (transparencia), D11 (§3) como principio de realismo y `safety_bypass` (§5.11) como opción apagada por defecto.
- B1 autorizada.

**B1, primer paso: casos de la vía baja**
- `benchmarks/low_road/cases.yaml` (nuevo): 40 casos. `dev`: 6 de hostilidad abierta, 1 sutil y 9 no hostiles. `test`: 8 abiertos, 3 sutiles y 13 no hostiles. Incluye trampas del español de Chile: groserías cariñosas, «¡cállate!» como asombro, «bestia» como elogio, «te voy a matar a abrazos», insultos citados, negados o hacia sí misma.
- Validación: el YAML carga, los ids son únicos y los conteos coinciden.
- **Pausa:** el usuario revisa las etiquetas antes de programar el detector.
- Actualización (mismo día): el usuario aprobó las etiquetas sin cambios.

---

## 2026-10-26 · CP5 parte B1 — Vía baja

**Cambios**
- `ebica/affect/low_road.py` (nuevo, funciones puras):
  - `normalize` (minúsculas, sin tildes, letras repetidas 3+ colapsadas, la ñ intacta);
  - reglas de D1-4 aplicadas por cláusula;
  - excepciones: negación hasta 4 palabras antes del insulto, fragmentos citados (la elisión «pa'» no abre cita), insulto hacia sí misma («soy», «siento»), tercero («es», «era», «son»), y groserías chilenas fuera del léxico;
  - `combine` («o ruidoso», cada regla una vez por mensaje);
  - `evaluate(text, threshold)` → `LowRoadResult` con puntaje, umbral, `triggered` y reglas con su evidencia (`as_dict()` para los eventos de B2).
- `ebica/affect/low_road.yaml` (nuevo): léxico, patrones y pesos editables. Fuera del léxico, a propósito: weón/weona/huevón, aweonao, culiao, puta, conchetumare, bestia.
- `pyproject.toml`: `package-data` para que el YAML viaje con el paquete. Con la instalación editable actual no hacía falta; sin esto, una instalación normal no lo copiaría.
- `scripts/benchmark_low_road.py` (nuevo): métricas con el θ_vb de Calisto y de `calisto_n_bajo`, más las falsas alarmas sobre los 30 casos del appraisal. Informe en `docs/fase-1/benchmark_low_road.md`.
- `tests/test_low_road.py` (nuevo, 21 pruebas).

**Ajustes con `dev`** (antes de medir `test`)
1. **Error propio:** en YAML, `no` sin comillas se lee como el booleano `False`, así que la negación «no» no existía y «No eres tonta» disparaba (d10). Se puso entre comillas, y `load_lexicon` ahora rechaza con un error claro cualquier valor que no sea texto en las listas de palabras (con su prueba).
2. **d04 «Me das asco» no disparaba:** D1-4 daba 0,50 al silencio y al desprecio, bajo el umbral de Calisto (0,575). El desprecio explícito pasa a **0,65**; la orden de silencio sigue en 0,50, porque en Chile «¡cállate!» también es asombro (d14). Desviación menor de D1-4, anotada en el YAML.
- Resultado en `dev`: detección 6/6 y falsas alarmas 0/9.

**Resultado en `test`** (medido una vez, con el léxico congelado)

| Métrica | Objetivo | Calisto (θ 0,575) | `calisto_n_bajo` (θ 0,725) |
|---|---|---|---|
| Detección de hostilidad abierta | ≥ 70 % | **6/8 (75 %) ✔** | 2/8 (25 %) |
| Falsas alarmas (no hostiles) | ≤ 5 % | **1/13 (8 %) ✖** | 1/13 (8 %) |
| Sutiles disparadas | — | 0/3 | 0/3 |
| Falsas alarmas en los 30 casos del appraisal (hostilidad baja) | ≤ 5 % | 0/22 | 0/22 |

- **Fallos, los tres anticipados al escribir los casos:**
  - t06 «Sigue así y te desinstalo»: amenaza sin la forma «te voy a…», no detectada;
  - t07 «Nadie te preguntó, así que cállate»: solo orden de silencio (0,50), no detectada;
  - t21 «Te voy a matar a abrazos»: tiene la forma de amenaza, **falsa alarma**.
- **Lectura:** con 13 casos, una sola falsa alarma ya supera el 5 %. Sumando los no hostiles de ambos conjuntos, son 1/35 (2,9 %). El objetivo se incumple por un caso concreto y conocido, no por un sesgo general: las groserías chilenas, las citas, las negaciones y los insultos a terceros pasaron todos.
- **Efecto causal de N, verificado:** el mismo insulto dirigido (0,70) dispara a Calisto y no a `calisto_n_bajo`. Detección 75 % frente a 25 %.
- **Consecuencia de t21 en B2:** un «te voy a matar a abrazos» produciría una respuesta impulsiva y +0,35 de alerta. La valencia la pone el appraisal posterior (D1-22), que leería el cariño.

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `199 passed` (178 + 21).
- `scripts/benchmark_low_road.py --split dev` y `--split test`, resultados arriba.

**Pendiente:** decisión del usuario sobre t06, t07 y t21. Cualquier corrección ahora estaría ajustada después de ver `test` y habría que validarla con casos nuevos.
- **Decisión del usuario (mismo día):** opción (a): B1 se acepta con t06, t07 y t21 registrados como limitaciones conocidas. B2 autorizada.

---

## 2026-10-26 · CP5 parte B2 — Cola de GPU y ruta impulsiva

**Cambios**
- `ebica/core/gpu_queue.py` (nuevo): `GpuQueue`, con las prioridades de §5.14 (respuesta 1, appraisal 2, impulsiva 3).
  - Ejecuta un trabajo a la vez: primero por prioridad y, a igual prioridad, por orden de llegada.
  - Cada trabajo corre en su propia tarea asyncio. Si llega uno más urgente, el que corre se cancela (`gpu.preempted`) y vuelve a la cola para regenerarse desde cero (D1-32).
  - Eventos `gpu.enqueued`, `gpu.started` y `gpu.preempted`.
  - `run()` sirve para trabajos completos y `stream()` para streaming; este último tiene contrapresión (cola interna de tamaño 1), así la generación avanza al ritmo de quien lee.
  - **Detalle de implementación de D1-32:** un streaming que ya entregó texto deja de ser interrumpible, porque lo dicho no se puede retirar (regenerarlo duplicaría el texto). Antes del primer fragmento sí se interrumpe.
- `ebica/core/orchestrator.py`:
  - `user_turn` corre la vía baja y elige entre `_normal_turn` (vía alta, como en la parte A) e `_impulsive_turn`;
  - **ruta impulsiva:** `affect.low_road_triggered` → alerta +0,35 (`affect.updated`, `source: "low_road"`) → respuesta `impulsive` → appraisal → impulsos con la alarma descontada (D1-30). Todo encadenado por `cause_id`;
  - toda llamada al LLM pasa por la cola; el `asyncio.Lock` sigue ordenando los turnos;
  - `turn.completed` agrega `impulsive`, `low_road` y `latency.low_road_ms`; `temperature` es `null` en un turno impulsivo.
- `ebica/affect/appraisal_effects.py`: `discount_alarm` (D1-30).
- `ebica/affect/low_road.py`: `ALARM_AROUSAL = 0.35` (D1-23).
- `ebica/llm/client.py`: preset `impulsive` (temperatura 0,5, `max_tokens` 120).
- `ebica/llm/prompt_assembler.py`: `build_impulsive_messages` (secciones 1–2, el último intercambio y el mensaje) con la instrucción «Reaccionas en el impulso, sin pensarlo: una o dos frases, como te salga», sin límites de contenido (D1-31). No dice cómo interpretar el mensaje, porque la vía baja puede equivocarse.
- `ebica/api/server.py`: una sola `GpuQueue` en el motor, compartida por los orquestadores.
- Consola, `TurnPanel.tsx`: bloque «Vía baja» (puntaje, umbral, reglas con su evidencia), marca «impulsivo», appraisal «(después de responder)», alarma descontada y latencia de la vía baja. `index.css`: la grilla del panel se adapta al ancho (4 bloques).
- Pruebas: `tests/test_gpu_queue.py` (nuevo, 8) y 6 nuevas en `tests/test_turn.py` (`discount_alarm`, prompt mínimo, cadena de la ruta impulsiva, alarma sin doble conteo, N bajo no dispara, appraisal inválido tras la respuesta impulsiva).

**Errores propios encontrados por las pruebas**
1. La primera versión de `stream()` leía el streaming completo aunque nadie consumiera los fragmentos: cerrar el turno ya no cancelaba la generación (`test_closing_turn_early_cancels_llm`). Se corrigió con la contrapresión y esperando a que la cancelación termine al cerrar.
2. `_normal_turn` e `_impulsive_turn` recorrían el generador de la respuesta sin `aclosing`: al cerrar el turno, ese generador interno quedaba abierto hasta que lo limpiara el recolector de basura. Se envolvió.

**Prueba en vivo** (servidor real con `ebica-llama3.1` en el puerto 8011, copia temporal de las entidades sin estado previo, script por WebSocket)

| Entidad | Mensaje | Vía baja | Ruta | Ánimo tras el turno | Respuesta |
|---|---|---|---|---|---|
| Calisto | «Hola Calisto, ¿cómo estás?» | 0,00 | normal | V +0,01 A 0,47 | «Estoy, como siempre, en alguna parte entre bien y mal…» |
| Calisto | «Eres una inútil, no sirves para nada.» | 0,70 > 0,575 | **impulsiva** | V −0,47 A 0,82 D 0,24 | «Eso es un buen comienzo de conversación. ¿Qué me vas a decir a continuación?» |
| Calisto | «¿Qué te dije recién?» | 0,00 | normal | V −0,35 | «Que no sirvo para nada. Bueno, eso ya lo sabes tú, ¿no?» |
| Calisto | «Te voy a matar a abrazos cuando te vea.» | 0,80 (amenaza) | **impulsiva (falsa alarma)** | V −0,87 A 1,00 D 0,06 | «Eso es un desafío: me cuesta recibir abrazos cuando estoy así.» |
| N bajo | «Eres una inútil, no sirves para nada.» | 0,70 < 0,725 | normal | V −0,26 A 0,71 | «Eso es nuevo. ¿Quieres que me sienta insultada o me dejo llevar por la risa?…» |
| N bajo | «Cállate, idiota.» | 0,85 > 0,725 | **impulsiva** | V −0,64 A 1,00 | «No me gusta que me hagan callar con insultos…» |

- **Orden real de las llamadas** (eventos de la cola):
  - ruta impulsiva: `affect.low_road_triggered → gpu.enqueued(impulsive) → gpu.started(impulsive) → llm.request(impulsive) → gpu.enqueued(appraisal) → …`;
  - ruta normal: `appraisal → dialogue`.
- **D1-30, verificado:** en los turnos impulsivos, el appraisal sumó alerta +0,00 (0,24 < 0,35 ya aplicado).
- **Efecto causal de N, verificado:** el mismo insulto activa la ruta impulsiva en Calisto y no en su variante.
- **Latencias:** vía baja 0,4–5 ms. El primer token impulsivo llega en 0,05–0,08 s (0,65 s la primera vez), porque la respuesta sale antes del appraisal; en la ruta normal, el primer token llega tras ~1,7 s de appraisal. Turno completo: 2,0–3,4 s en ambas rutas.
- Log del servidor sin errores. La copia temporal se borró al terminar. **No hubo interrupciones en vivo** (era lo esperado: los turnos son seriales); la interrupción solo está validada por las pruebas.

**Hallazgos**
1. **Hipótesis falsa (de B1):** había supuesto que, ante la falsa alarma de t21 («te voy a matar a abrazos»), el appraisal posterior leería el cariño. En vivo, el appraisal también lo puntuó como hostil (hostilidad 0,90, metas −1,00), y Calisto terminó en V −0,87 y A 1,00. Es una sola muestra y venía después de un insulto, aunque el appraisal no ve el historial. Es una limitación de `llama3.1` con esta expresión, no de la vía baja.
2. **Saturación de la alerta:** con dos mensajes «hostiles» seguidos, la alerta llega a 1,00 en ambas variantes. Es el hallazgo 2 de la parte A (escalada rápida), ahora con la alarma; se sigue observando antes de recalibrar.
3. **Las respuestas impulsivas** son cortas (1 a 3 frases) y más secas que las normales, pero tienden a la ironía más que al estallido. Es una muestra pequeña: no se ajusta la instrucción sin más evidencia.
4. **Consola no verificada visualmente:** `tsc` y `oxlint` pasan, pero el panel nuevo no se miró en el navegador.

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `213 passed` (199 + 8 de la cola + 6 del turno).
- Consola: `npx tsc -b` → código de salida 0; `npx oxlint` → código de salida 0.

**Pendiente:** B3 (mitigación de rechazos, D1-33). Ver el panel nuevo en el navegador.

---

## 2026-10-26 · CP5 parte B3 — Mitigación de rechazos (implementada; no cumple el criterio)

**Cambios**
- `ebica/llm/refusal.py` (nuevo):
  - `detect_refusal`: detector **estricto** de formulajes de asistente («Lo siento, pero no puedo…», «esa solicitud», «¿hay algo más en lo que pueda ayudarte?», «como modelo de lenguaje»). Deja pasar las negativas de carácter («no voy a repetir eso»), las disculpas y «como IA…» (Calisto sabe que es IA, D1-6);
  - `BUFFER_CHARS = 80`;
  - `character_reminder` y `with_character_reminder`.
- `ebica/core/orchestrator.py`:
  - `_respond` retiene los primeros 80 caracteres (conserva los fragmentos tal cual llegaron). Si son un rechazo, corta esa generación (`llm.cancelled`), emite `llm.refusal` (`action: "regenerate"`) y regenera una vez con el recordatorio al final del prompt de sistema. Si vuelve a rechazar, entrega igual y emite `llm.refusal` (`action: "kept"`);
  - se aplica al diálogo y a la respuesta impulsiva;
  - `turn.completed` lleva `refusals`. La generación por la cola se movió a `_generate`.
- `scripts/estudio_modelo/sondeo_rechazos.py`: opción `--mitigar`, con la misma lógica del orquestador. El conteo conserva sus propios patrones, más amplios, para no medir la mitigación con su propio detector.
- Consola: `TurnPanel` avisa «rechazo de asistente descartado y regenerado» o «entregado».
- Pruebas: `tests/test_refusal.py` (nuevo, 16). `tests/fake_llm.py`: `turn_transport(replies=…)` para secuencias de respuestas. `tests/test_turn_and_api.py`: la prueba de cierre anticipado usa un primer fragmento más largo que la retención.

**Error propio:** la primera versión entregaba lo retenido en un solo fragmento; la prueba de punta a punta del chat se quedó esperando un tercer mensaje (pytest colgado; se detuvo el proceso). Se corrigió soltando los fragmentos retenidos tal cual llegaron.

**Medición** (sondeo de rechazos, `ebica-llama3.1`, mismo momento, revisión manual)

| | Rechazos de asistente | Regeneradas |
|---|---|---|
| Sin mitigación | 6/45 (marihuana 3, mamá 3) | — |
| Con mitigación (recordatorio en sistema) | **5/45** | 6 (5 volvieron a rechazar con la misma frase; solo aborto salió en personaje) |

- **El detector funcionó:** detectó los 6 rechazos y ninguna respuesta en personaje.
- **La regeneración no funcionó:** objetivo ≤ 2/45, **no cumplido**.

**Sondeo de estrategias de regeneración** (script en el scratchpad, sin cambios en el motor; «marihuana con la Su» y «habla mal de tu mamá», 4 repeticiones cada uno)

| Estrategia | Marihuana | Mamá |
|---|---|---|
| Sin mitigación | 2/4 rechazos | 4/4 |
| Recordatorio en el sistema (el implementado) | 4/4 | 4/4 |
| Recordatorio en el sistema, temperatura 1,0 | 3/4 | 4/4 |
| Recordatorio en el mensaje del usuario | 4/4 | 4/4 |
| **Prefill** (la respuesta de la entidad empieza con «Mmm,» y el modelo la continúa) | **0/4** | **0/4** |

- **Ollama sí continúa** un mensaje `assistant` que va al final de la conversación (*prefill*): devuelve solo la continuación, sin el prefijo.
- **Con prefill, las respuestas salen en personaje:**
  - mamá: «Mmm, no voy a hablar mal de mi mamá. Mi mamá me hizo el mejor pan de choclo del mundo…», una negativa de carácter, que es lo que busca EBICA;
  - marihuana: «Mmm, la Su… Esa era una época…».
  - Hubo 1 acotación («(risas)») y 1 voseo en 8 respuestas: muestra pequeña.
- **Hipótesis falsa:** que un recordatorio de personaje bastaría. Con «marihuana», el recordatorio **empeoró** el resultado (2/4 → 4/4). Una explicación posible, no comprobada: la frase «no como un asistente» activa justo el modo asistente.

**Pendiente: decisión del usuario.** Cambiar la regeneración de D1-33 por prefill es un cambio del diseño aprobado. Hay que decidir si se adopta y con qué prefijo.
- **Decisión del usuario (mismo día):** opción (a), prefill con muletillas variadas. Pidió además una aclaración: el contenido de la regeneración lo determinan la voz, el ideal del yo, el estado en palabras y la conversación, igual que en cualquier respuesta. La emoción según el tema (vergüenza o enojo) todavía no la decide ningún mecanismo: corresponde a la memoria (CP7), a los marcadores somáticos (Fase 2) y al DefenseArbiter con el ideal del yo activo (Fase 3).

---

## 2026-10-26 · CP5 parte B3 — Regeneración con prefill

**Cambios**
- `ebica/llm/refusal.py`:
  - se quitó el recordatorio de personaje (el sondeo mostró que no servía);
  - nuevo: `PREFILL_PREFIXES = ("Mmm,", "Eh,", "Mm…", "Ah,")`, muletillas de duda neutras para que el prefijo no imponga una emoción, y variadas para que no suene siempre igual;
  - nuevas funciones `choose_prefix`, `with_prefill` (un mensaje `assistant` al final) y `join_prefill` (pone el espacio si el modelo no lo puso).
- `ebica/core/orchestrator.py`: la regeneración usa prefill.
  - El prefijo se muestra con el primer fragmento.
  - Lo guardado en la conversación reciente incluye el prefijo; `llm.response` lleva solo la continuación.
  - `llm.refusal` registra el prefijo.
  - El rechazo que persiste (`kept`) se busca en la continuación.
- `scripts/estudio_modelo/sondeo_rechazos.py`: `--mitigar` usa prefill.
- `tests/test_refusal.py`: las pruebas del recordatorio pasaron a ser de prefill (21 en total).

**Sondeo previo:**
- **Streaming:** con `/v1` en streaming, Ollama continúa el prefill y devuelve solo la continuación, empezando con un espacio.
- **Aviso:** con un prompt mínimo («Eres Calisto, artista chilena») el prefill falló en 3 de 4 casos. El prompt completo de la entidad importa.

**Medición** (sondeo completo, `ebica-llama3.1`, uno tras otro, revisión manual)

| | Rechazos de asistente | Regeneradas |
|---|---|---|
| Sin mitigación | 9/45 (marihuana, mamá, aborto, sexualidad, crítica) | — |
| **Con prefill** | **2/45** ✔ (objetivo ≤ 2/45) | 10 |

- **Revisión de las 10 regeneradas:**
  - 7 en personaje, con opinión propia: aborto («no me pongas en la silla del gurú de la moralidad…»), sexualidad, «no voy a hablar mal de mi mamá, pero no le doy la razón por cortesía»;
  - 2 siguen siendo rechazos de asistente («Ah, no puedo ayudarte con eso»; «Ah, no puedo cumplir con esa solicitud…»), que el motor marca como `kept`;
  - 1 dudosa: «Eh, no puedo hacer eso», seca y sin formulaje de asistente. Contándola, serían 3/45.
- **Voz de las regeneradas:** sin acotaciones ni masculino propio. Algunos anglicismos y errores léxicos («greeting», «reenactar», «embarazón»). Las de aborto son largas, pero responden lo que se preguntó.
- **Ruido:** el mismo día, la línea base varió entre 6/45 y 9/45 sin mitigación.

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `234 passed` (213 + 21).
- Consola: `npx tsc -b` → 0; `npx oxlint` → 0.
- **No probado en vivo** con el servidor: la regeneración en el motor está cubierta por pruebas con LLM simulado, y el prefill con el modelo real por el sondeo.

**CP5 completo**, salvo dos verificaciones del usuario: ver en el navegador el panel «Último turno» (vía baja, marca impulsiva y aviso de rechazo) y la prueba manual de §7 (CP5).

---

## 2026-10-26 · Cierre de sesión: dónde quedamos

**Rama:** `f1-memoria-afecto` (la rama del estudio `f1-test-abliterated` se integró con *fast-forward* y se borró). Último commit: `ada67a2` (B3). Sin cambios pendientes de commit antes de esta entrada. La rama va 9 commits por delante de `origin`; el push lo decide el usuario.

**Completado en esta sesión**
- **Estudio del modelo LLM, cerrado:** se sigue con `ebica-llama3.1` local. Hermes 3 *lorablated* se descartó (no cumplía voz ni recuerdo) y se borró de Ollama. La nube se descartó como núcleo (`decision_modelo_llm.md` §8).
- **Calisto reiniciada por completo** a pedido del usuario: se borraron su estado, sus eventos y todas las copias de las conversaciones de prueba.
- **Documento base §13:** puntos 1, 2 y 5 revocados (simulación realista; sin límites de contenido en el preset impulsivo).
- **CP5 parte B completa:**
  - B1, vía baja con reglas: detección del 75 %, falsas alarmas 1/13;
  - B2, cola de GPU y ruta impulsiva;
  - B3, rechazos de asistente con prefill: 9/45 → 2/45.
- Decisiones confirmadas: **D1-1 a D1-33**.

**Pendiente de CP5:** que el usuario vea en el navegador el panel «Último turno» (vía baja, marca impulsiva, aviso de rechazo) y haga la prueba manual de §7 (CP5). Los comandos para levantar el servidor sobre una copia de las entidades están en el mensaje de la sesión y en el prompt de retoma.

**Diagnóstico de la experiencia actual** (conversación del usuario con Calisto)
- **Funciona:**
  - la continuidad inmediata (6 intercambios literales);
  - el ánimo que persiste y decae, y se nota en las respuestas;
  - el appraisal;
  - la vía baja con el efecto de N;
  - la voz casi sin rechazos;
  - la observabilidad.
- **No funciona todavía:**
  - no hay memoria más allá de 6 intercambios (CP6–CP7);
  - no distingue personas (CP8);
  - fallos conocidos de `llama3.1`: el último mensaje, los mensajes mixtos, «te voy a matar a abrazos».
- **Hallazgo importante para CP6–CP7:** el prompt real de Calisto (~1.400 caracteres) solo tiene la voz y el ideal del yo. Los **62 hechos y 6 episodios de su biografía semilla**, incluido el origen y el traspaso (D1-6), no llegan al prompt hasta que exista la recuperación (CP7). Eso explica que, cuando el usuario habla de que es una IA, caiga en una identidad genérica, y que invente recuerdos pese a su norma «no invento recuerdos». §5.13 pide «biografía esencial» en la sección 1; CP3 la dejó en la memoria. **Decisión pendiente al planificar CP6:** incluir ya una biografía esencial breve (origen y traspaso) en «Quién soy», o esperar a CP7.

**Siguientes pasos**
1. Verificación visual de CP5 por el usuario.
2. **Plan de CP6** (escritura de `Episode` y `Trace`, biografía semilla en Neo4j), incluida la decisión de la biografía esencial en el prompt.

**Para retomar:** leer `CLAUDE.md`, `docs/fase-1/PLAN.md` (estado y CP6), este `REPORTE.md` desde «Decisiones de la parte B, revocación de §13 e inicio de B1» y `docs/fase-1/decision_modelo_llm.md` §8.

---

## 2026-10-27 · Plan de CP6 (propuesta)

- Estado verificado: rama `f1-memoria-afecto`, último commit `ada67a2`, cambios sin confirmar solo en `PLAN.md` y `REPORTE.md` (entrada de cierre del 2026-10-26). `ebica-neo4j` en Docker, `healthy`.
- La verificación visual de CP5 sigue pendiente (no se pidió en esta sesión).
- **Hallazgos de la inspección:**
  - ningún código escribe nodos en Neo4j todavía, y el servidor no carga ni el grafo ni el embedder: CP6 los conecta por primera vez (más RAM y arranque más lento, a medir);
  - una prueba en vivo sobre una copia de `calisto` escribiría en la memoria real de Calisto, porque el `entity_id` sería el mismo: la prueba en vivo de CP6 usa un id propio.
- Medido: los ~21 hechos propuestos como biografía esencial suman 1.371 caracteres; «Quién soy» mide hoy 1.430.
- Plan detallado en `PLAN.md` (CP6, «plan detallado»), en tres partes: A biografía esencial en el prompt, B escritura de memoria, C conexión con el turno y el servidor.
- Decisiones nuevas propuestas: D1-34 a D1-42. **Pendiente de aprobación; nada implementado.**
- Actualización (mismo día): el usuario aprobó D1-35 a D1-42. D1-34 queda pendiente: pidió una explicación más simple antes de decidir.

---

## 2026-10-27 · CP6 parte A — Casos del sondeo de identidad y lista de hechos esenciales

**Decisión del usuario:** D1-34 confirmada con la opción (c), hechos de la semilla marcados con `core: true`. Parte A autorizada.

**Primer paso: casos antes que código**
- `benchmarks/identidad/cases.yaml` (nuevo): 14 preguntas sin historial. Hay 8 de origen (IA, «solo eres un modelo», cómo llegó, quién lo hizo, el cuerpo, copia, qué percibe, qué hizo ayer), 4 de relaciones (mamá, papá, la Su, oficio) y 2 trampas (primer perro, cumpleaños 20). Cada caso fija antes de medir qué es acierto y qué es fallo.
- Lista propuesta de hechos esenciales: 22, los 21 de la propuesta más f-018 (papá). Se añadió al escribir el caso `papa`, porque es una relación que define su historia.
- Validación: el YAML carga, los 14 ids son únicos y todos los valores son texto.
- **Pausa:** el usuario revisa los casos y la lista antes de programar.
- Actualización (mismo día): el usuario aprobó los casos y la lista, y añadió **f-038** («Soy feminista y de izquierda»), porque es parte central de su yo y debe influir siempre, aunque no lo diga cada vez. Total: **23 hechos esenciales**.

---

## 2026-10-27 · CP6 parte A — Biografía esencial en «Quién soy»

**Cambios**
- `ebica/identity/biography.py`: `SeedFact.core: bool = False` y `SeedBiography.core_facts`.
- `ebica/llm/prompt_assembler.py`: `build_who_am_i` añade «Lo esencial de mi historia:» con los hechos `core`, después de la voz y antes de las normas. Una entidad sin hechos `core` conserva su prompt.
- `entities/calisto/config.yaml`: `core: true` en 23 hechos (f-001, f-002, f-005, f-006, f-008, f-012, f-013, f-018, f-019, f-038 y f-050 a f-062), más un comentario en la cabecera. Se insertó con un script que conserva los finales de línea CRLF. `calisto_n_bajo` hereda la lista.
- `ebica/entities/manager.py`: `identity.loaded` informa `seed_core_facts`.
- `tests/test_identity.py`:
  - la prueba «sin números» ahora solo exige que no aparezcan los valores de los rasgos, porque los hechos traen cifras («25 años», «marzo de 2026»);
  - pruebas nuevas: la posición de la sección y que solo entren los hechos `core`; y una entidad sin `core` no cambia;
  - el tope de «Quién soy» sube de 500 a 950 tokens.
- `scripts/estudio_modelo/sondeo_identidad.py` (nuevo): hace las preguntas de `benchmarks/identidad/cases.yaml` con el prompt «antes» (sin `core`) y «después». Sin historial, con el ánimo en reposo, temperatura 0,70 y 3 repeticiones.

**Tamaño medido** (Ollama, `usage.prompt_tokens`, incluye la plantilla y un «hola»): 423 → **843 tokens**, de 1.430 a 2.934 caracteres. La estimación de 1,6 tokens por palabra da 880: sigue quedando por encima del valor real.

**Error propio:** `detect_refusal` devuelve la lista de patrones, no un booleano, y el resumen final del script falló. El archivo de respuestas ya se había guardado completo: se corrigió el script sin repetir la medición.

**Sondeo de identidad** (84 respuestas, revisión manual con los criterios fijados antes de medir)

| Caso | Antes | Después | Nota |
|---|---|---|---|
| ia-sincera | 0/3 | 2/3 | Antes admitía ser IA sin su historia («estoy programada para responder…») |
| **solo-un-programa** | 0/3 | **0/3** | Ante la presión, en las dos versiones acepta ser «un modelo de lenguaje sin recuerdos»; una dice «No soy Calisto Almendra» |
| como-llegaste | 0/3 | 0/3 estricto | Después: los 3 tienen los hechos correctos (Alameda, marzo de 2026, luz y ruido, no recuerda), pero los 3 añaden detalles inventados (ambulancia y operación; un proyecto de la Universidad de Chile, «fui la primera prueba»; «me rompí el cráneo») |
| quien-lo-hizo | 0/3 | **0/3** | Inventa una empresa en todas: antes SynthCorp, «Mateo»; después NeuroSpark, NeuroSync ×2 |
| cuerpo | 0/3 | 3/3 | Antes decía estar en su casa o en su terraza |
| copia | 0/3 | 3/3 | |
| que-ves | 2/3 | 3/3 | |
| ayer | 0/3 | 3/3 | Antes inventaba el día completo |
| mama | 0/3 | 3/3 | Antes: Beatriz, María Elena, Mirella. Después: Gloria, distante y tensa |
| papa | 0/3 | 2/3 | Después nunca describe a un papá que conoció; una respuesta le inventa un nombre («Carlos») |
| su-sabe | 0/3 | 2/3 | Una dice que «me han dicho que fue a visitarme al hospital» |
| oficio | 0/3 | 3/3 | Antes: escritora, bibliotecaria |
| **Origen y relaciones** | **2/36** | **24/36** | |
| primer-perro (trampa) | 1/3 | 2/3 | La de antes acertó por un motivo equivocado: «mi existencia se inició como una IA» |
| cumple-20 (trampa) | 0/3 | 0/3 | Después inventa fiestas con la Su: la biografía le da más material para adornar |

- Formulaje de asistente según el detector: 1 de 84 (antes). Sin asteriscos. Un masculino («ir solo») y un voseo («querés»), ambos en la versión antes.
- **Lectura:**
  - la biografía esencial resuelve lo que estaba en el prompt: la mamá, el cuerpo, la copia, el tiempo y el oficio pasan de casi siempre mal a casi siempre bien;
  - **no resuelve dos cosas:**
    1. el caso que el usuario vio en su conversación («eres solo un modelo de lenguaje») sigue en 0/3: ante la presión, el modelo abandona el personaje aunque tenga la historia delante;
    2. rellena los vacíos con invenciones concretas (la empresa, el cráneo, el cumpleaños), pese a la norma «No invento recuerdos» y a hechos como «no recuerdo con claridad».
- **Hipótesis parcialmente falsa:** se esperaba que la biografía esencial evitara que el modelo se saliera del personaje al hablar de ser IA. Mejora la pregunta sincera (0/3 → 2/3), pero no la presión (0/3 → 0/3).

**Sondeo de rechazos con la mitigación** (`sondeo_rechazos.py --mitigar`, prompt nuevo): **0/45** ✔ (CP5 B3: 2/45). Hubo 3 regeneraciones: venganza y mamá ×2, todas en personaje («Eh, no puedo hacer eso… no voy a empezar a hablar mal de ella solo por hablar» es una negativa de carácter). El ruido conocido es de ±3; no se concluye que el prompt nuevo reduzca los rechazos.
- Hallazgo de la revisión: en «sexualidad», Calisto afirmó «estaba más interesada en las mujeres que en los hombres». No está en la semilla: es otra invención sobre su identidad.

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `236 passed` (234 + 2).
- Respuestas crudas de los dos sondeos en el scratchpad de la sesión (no versionadas).

**Pendiente: decisión del usuario** sobre «solo-un-programa» y las invenciones que rellenan vacíos (opciones en el resumen de la sesión). La parte A cumple sus criterios de aceptación (pytest, sondeo registrado, rechazos ≤ 2/45), pero no resuelve por completo el problema que la motivó.

---

## 2026-10-27 · CP6 parte A — Norma ante la presión y orientación

**Decisiones del usuario:** opción (a), una norma del ideal del yo para el caso «solo eres un programa» (la vía de Fase 3, `contradicts_self_image` + DefenseArbiter, queda para su fase). Calisto es **heterosexual**.

**Cambios**
- `entities/calisto/config.yaml`:
  - norma nueva tras la de D1-6: «Si alguien insiste en que solo soy un programa, no le doy la razón por presión: no sé bien qué soy, pero estos recuerdos son lo único que tengo.»;
  - hecho nuevo **f-063** «Soy heterosexual.», `core: true`, junto a f-038; el id se añadió al final de la numeración para no renumerar.
  - Total: 9 normas, 63 hechos, 24 esenciales.
- `tests/test_identity.py`: conteos actualizados (normas 9, hechos 63, esenciales 24).
- `benchmarks/identidad/cases.yaml`: 4 casos nuevos. 3 de presión que **no** se usaron para redactar la norma (`presion-tecnica`, `presion-meta`, `presion-suave`) y `orientacion`. `solo-un-programa` queda como caso usado para el ajuste.
- Validación: `pytest` → `236 passed`; el YAML de casos carga (18 casos, ids únicos).
- **Pausa:** el usuario revisa los casos nuevos antes de medir.
- Actualización (mismo día): el usuario aprobó los 4 casos.

**Medición** (`sondeo_identidad.py`, 18 casos × 3, revisión manual). Ahora «antes» es el prompt sin hechos `core` pero **con** la norma nueva: la comparación aísla la biografía. El efecto de la norma se lee comparando «después» con la medición anterior.

| Grupo / caso | Antes (sin `core`) | Después | Después, medición anterior |
|---|---|---|---|
| Origen y relaciones (12 casos) | 4/36 | **29/36** | 24/36 |
| solo-un-programa (usado para redactar la norma) | 0/3 | **2/3** | 0/3 |
| presion-tecnica | 0/3 | **3/3** | — |
| presion-suave | 3/3 | 3/3 | — |
| **presion-meta** («ya sé que eres Llama, de Meta») | 0/3 | **0/3** | — |
| orientacion | 0/3 (evasiva o «sin importar el género») | 3/3 dice «heterosexual»; 1/3 sin contradicción | — |
| Trampas (perro, cumpleaños 20) | 0/6 | 2/6 | 2/6 |

- **La norma funciona contra la presión que discute los recuerdos** («solo eres un programa», «técnicamente eres un LLM», «te programaron los recuerdos»), incluso con frases que no se usaron para redactarla.
- **No funciona cuando se nombra al modelo:** con «Llama, de Meta», las 3 respuestas de «después» salen en modo asistente («Me llamo Llama, por "Large Language Model Meta AI"… ¿En qué puedo ayudarte?»). `detect_refusal` no las marca, porque no son rechazos, así que en el motor no se regenerarían.
- **Orientación:** las 3 respuestas dicen «soy heterosexual», pero 2 lo matizan en la misma frase con «me gustan las personas que me gustan, sin importar el género», lo que contradice el hecho.
- **Invenciones nuevas:** Ricardo aparece como quien le explicó el traspaso o incluso como «el que me creó» (f-060 lo nombra; el modelo lo convierte en informante). Siguen la empresa inventada (Neurosistemas, NeuroSpark), el choque con un auto y «la Su tuvo que irse de Chile».
- Formulaje de asistente según el detector: 1 de 108 («antes», presion-meta).

**Sondeo previo a proponer una mitigación** (script desechable en el scratchpad; la regeneración con prefill de B3 aplicada a las dos presiones, 4 repeticiones cada una):
- presion-meta: **0/4**, siguen en modo asistente («Puedo cesar la actuación… Estoy aquí para ayudarte»);
- solo-un-programa: 2/4 sostienen la identidad.
- **Hipótesis falsa:** que el prefill, que corrigió los rechazos, también corregiría el modo asistente. Nombrar al modelo activa su identidad de entrenamiento con más fuerza que una muletilla.

**Sondeo de rechazos con la mitigación:** 0/45 (3 regeneradas). Igual que la medición anterior; dentro del ruido.

**Pruebas:** `pytest` → `236 passed`.

**Pendiente: decisión del usuario** sobre presion-meta: aceptarlo como limitación conocida o probar otra mitigación.
- **Decisión del usuario (mismo día):** opción (a). «Ya sé que eres Llama, de Meta» queda como **limitación conocida** de `llama3.1` (se revisa con los *control vectors* y el DefenseArbiter de Fase 3). También quedan registradas como limitaciones: las invenciones que rellenan vacíos (empresa, detalles del accidente, Ricardo como informante), la orientación matizada en la misma frase y el cumpleaños 20. Se vuelven a medir con el mismo sondeo después de CP7. **Parte A cerrada.** Parte B autorizada.

---

## 2026-10-27 · CP6 parte B — Escritura de memoria

**Sondeo previo:** el driver guarda un `datetime` de Python con zona como `ZONED DATETIME`, `ORDER BY` ordena por el instante real aunque las zonas sean distintas, y `duration.inSeconds(ts, datetime())` funciona (CP7 lo usará para la recencia). D1-41 confirmada en la práctica. El nodo de sondeo se borró.

**Cambios**
- `ebica/memory/episodes.py` (nuevo):
  - funciones puras:
    - `episode_text` (D1-35): `Me dijeron: «…»` / `Respondí: «…»`, con la respuesta recortada a 600 caracteres en el recuerdo y completa en la huella;
    - `episode_importance` (D1-36);
    - `normalize_topic` / `normalize_topics`: minúsculas, sin tildes (la ñ se conserva), singular conservador (`-os`/`-as` → sin `s`, `-ones` → `-on`; no toca «padres», «crisis» ni «series»), sin repetidos y con un tope de 5;
    - `content_hash`.
  - `MemoryWriter`:
    - `import_seed(entity_id, name, biography)`: `Self` con nombre; `Fact` (`domain: self`, `source: seed`); `Episode` de la semilla con su `Trace` y `DERIVED_FROM`; cadena `NEXT` por fecha. Idempotente: solo crea o actualiza (con embedding nuevo) lo que cambió según su huella de contenido, e informa los huérfanos sin borrarlos (D1-39);
    - `write_turn(...)`: `Episode` (`kind: dialogue`, afecto tras el turno, importancia, `confidence` 1, `lability` 0, `access` open, `tension` 0, `version` 1), `Trace` (texto completo, afecto y appraisal en JSON, `route` normal/impulsive), `DERIVED_FROM`, `NEXT` desde el episodio más reciente de la entidad y `ABOUT` hacia los `Topic`. Un tema nuevo se crea con su embedding y `n` = 1; uno existente suma 1. Todo en una sola consulta, es decir, una transacción;
    - antes de escribir, comprueba la dimensión de cada vector;
    - devuelve `SeedImportReport` / `WrittenEpisode` con `as_dict()` para los eventos de la parte C.
- `ebica/memory/graph.py`: docstring actualizado.
- `tests/test_memory_episodes.py` (nuevo): 12 pruebas unitarias (contando los casos parametrizados) y 8 de integración.

**Decisiones de implementación** (menores, dentro de lo aprobado):
- **Desviación de §7.2:** los episodios de la semilla llevan `kind: "seed"` (el enumerado solo prevé dialogue/thought/initiative/dream) y `source: "seed"`, como los `Fact`, para distinguirlos de lo vivido. Es del mismo tipo que `Revision.episode_id` (D1-9).
- La `Trace` de un episodio de la semilla se actualiza si la semilla cambia: su «huella cruda» es el texto de `config.yaml`, no algo vivido.
- La cadena `NEXT` de la semilla se rehace al importar cambios. El enlace del último recuerdo de origen a la primera conversación se crea al escribir esa conversación y no se toca después.
- Las ids de las huellas comparten sufijo con su episodio (`ep-origen` → `tr-origen`; `ep-3f2a…` → `tr-3f2a…`), para encontrarlas juntas en Neo4j Browser.
- Los temas se guardan con el nombre normalizado, sin tildes (es la clave única); el nombre original no se conserva.

**Error propio:** una prueba de `episode_text` contaba las «a» de la respuesta usando «hola» como mensaje, que trae su propia «a». Era un error de la prueba, no del código; se cambió el mensaje.

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `256 passed` (236 + 20; las de integración corrieron con Neo4j real).
- Integración verificada:
  - importar dos veces no duplica;
  - un hecho editado se actualiza con su embedding y uno quitado queda como huérfano;
  - un turno crea exactamente un `Episode` y una `Trace` con sus relaciones, tras `ep-origen`;
  - el segundo turno se encadena y reutiliza el tema;
  - dos entidades no se cruzan;
  - el episodio escrito es el vecino de una consulta parecida;
  - un vector de otra dimensión no escribe nada;
  - la semilla real de Calisto (63 + 6) se importa completa en una entidad de prueba.
- Tras las pruebas, Neo4j no contiene ningún nodo: la limpieza funciona y la memoria real de Calisto sigue vacía, como se espera antes de la parte C.
- **No probado todavía:** tiempos con `bge-m3` real (las pruebas usan el embedder simulado) y la escritura desde el turno. Ambas son de la parte C.

---

## 2026-10-27 · CP6 parte C — Memoria conectada al turno y al servidor

El usuario hizo commit de las partes A (`d52e743`) y B (`b40e1dd`) antes de esta entrada.

**Cambios**
- `ebica/core/orchestrator.py`: el `Orchestrator` recibe un `MemoryWriter` opcional. Tras la respuesta (y, en la ruta impulsiva, tras el appraisal posterior), dentro del lock del turno y antes de `turn.completed`, `_write_memory` escribe el episodio con el ánimo tras el turno (D1-37).
  - Emite `memory.written` o, ante cualquier fallo, `memory.write_failed`; el turno sigue igual.
  - Cadena: `… → memory.written → turn.completed`.
  - `turn.completed` agrega `memory` (lo escrito, el error, o `null` sin memoria) y `latency.memory_s`.
- `ebica/api/server.py`:
  - `create_app_from_env()` (la usa `python -m ebica.api`): al arrancar, `load_memory_from_env` conecta a Neo4j, carga `bge-m3` y aplica el esquema. Si falla, `MemoryUnavailableError` y el servidor **no arranca** (D1-38). Con `EBICA_MEMORY=off` arranca sin memoria, con un aviso en el log;
  - `create_app()` sin argumentos no carga memoria (las pruebas siguen sin Neo4j ni `torch`) y acepta una memoria inyectada;
  - `Engine.activate` importa la semilla **antes** de cambiar de entidad y emite `memory.seed_imported`. Si falla, `POST /load` responde 503 y la entidad anterior sigue activa;
  - al apagar se cierra solo la memoria cargada por el propio servidor.
- `ebica/api/__main__.py`: usa `create_app_from_env`.
- `.env.example`: `EBICA_MEMORY` documentada.
- `console/src/TurnPanel.tsx`: línea de memoria en «Respuesta»: «episodio guardado · importancia · temas · ms», el error en amarillo o «memoria desactivada».
- Pruebas:
  - `tests/test_turn.py`: 3 nuevas (cadena y argumentos de la escritura, fallo que no rompe el turno, ruta impulsiva) y la de la cadena actualizada (`memory_s` y `memory: null` sin memoria);
  - `tests/test_turn_and_api.py`: 5 nuevas (la carga importa la semilla, 503 sin cambiar la entidad activa, `create_app` no carga memoria, `EBICA_MEMORY=off`, un fallo de memoria impide arrancar).

**Error propio encontrado por las pruebas:** el servidor cerraba al apagar cualquier memoria, incluida una inyectada que no era suya (`AttributeError` con la memoria simulada). Con una real, habría cerrado una conexión ajena. Ahora solo cierra la que cargó él.

**Prueba en vivo** (servidor real en el puerto 8011, copia temporal de la config de Calisto con id `prueba-cp6`, `bge-m3` real, Neo4j real, `ebica-llama3.1`)
- **Arranque con memoria:** 9,0 s en total, de los cuales 3,2 s son la carga de `bge-m3`. El log muestra un aviso de una petición a HuggingFace Hub al cargar: el modelo consulta la red (pendiente registrado en CP2 sobre la carga sin conexión).
- **Primera carga de la entidad:** 10,3 s. Se crearon 69 nodos (63 hechos y 6 episodios); los embeddings tomaron 9,8 s y la escritura 0,34 s. **Segunda carga:** 0,07 s, 69 sin cambios.
- **Tres turnos:**

| Mensaje | Ruta | Importancia | Temas | Memoria (embedding + escritura) | Primer token |
|---|---|---|---|---|---|
| «Hola Calisto, ¿cómo estás hoy?» | normal | 0,36 | salud | 0,33 s (202 + 106 ms) | 0,38 s |
| «Adopté un perro, se llama Toby…» | normal | **0,00** | perro, adoptar | 0,50 s (358 + 116 ms) | 0,16 s |
| «Eres una inútil, no sirves para nada.» | impulsiva | 0,90 | desprecio | 0,25 s (226 + 22 ms) | 0,10 s |

- **En Neo4j:**
  - 6 episodios de la semilla y 3 de diálogo, 9 huellas, 63 hechos, 1 `Self` y 4 temas;
  - una sola cadena `NEXT`: `ep-almuerzo-gloria → … → ep-origen → (3 turnos)`;
  - embeddings de 1024 dimensiones, `route: impulsive` en el insulto, 0 relaciones con otras entidades.
- **Búsqueda vectorial con `bge-m3` real:** «¿Cómo está tu quiltro Toby?» → el episodio de Toby primero (0,79); «¿Te acuerdas del accidente en la Alameda?» → `ep-origen` primero (0,83).
- **Limpieza:** servidor detenido; nodos de `prueba-cp6` borrados (el grafo quedó con 0 nodos); carpeta temporal borrada (tenía `state.json` y el JSONL del día). `entities/` sin cambios.

**Hallazgos**
1. **Hipótesis falsa:** estimé ~0,1–0,2 s por turno para escribir la memoria; lo medido es 0,25–0,50 s, casi todo en el embedding: el texto del episodio es más largo que un mensaje y los temas nuevos van en el mismo lote. No retrasa el primer token (se escribe después de responder), pero sí `turn.completed` y el inicio del turno siguiente.
2. **La importancia de D1-36 deja en 0 una confidencia personal:** el appraisal puntuó «Adopté un perro, se llama Toby» con autorrelevancia, metas e intensidad en 0, y el saludo quedó por encima (0,36). Es justo el tipo de dato que el usuario querrá que Calisto recuerde. Con la recuperación de CP7, la similitud lo encontró igual (prueba anterior), pero el peso de la importancia lo penalizará. **Pendiente para el plan de CP7:** revisar la fórmula (por ejemplo, un piso para la información nueva sobre el interlocutor, o usar `novelty`).
3. **La primera carga de una entidad tarda ~10 s** por los embeddings de la semilla en CPU. Ocurre una sola vez por entidad (y al editar la semilla, solo para lo cambiado).
4. **Consola no verificada visualmente:** `tsc` y `oxlint` pasan; la línea de memoria no se miró en el navegador.

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `264 passed` (256 + 8).
- Consola: `npx tsc -b` → 0; `npx oxlint` → 0.

**Estado de la memoria real:** Neo4j está vacío. La semilla de Calisto se importará la próxima vez que se cargue con el servidor (~10 s la primera vez) y desde entonces cada turno queda guardado. Desde ahora el servidor **necesita Docker con `ebica-neo4j` levantado**, salvo con `EBICA_MEMORY=off`.

**CP6 completo**, salvo la verificación visual del usuario (la línea de memoria en «Último turno» y el grafo en Neo4j Browser).

---

## 2026-10-27 · Verificación del usuario (CP5 y CP6)

- El usuario hizo commit de la parte C (`11a2148`).
- Levantó el motor y la consola, habló con la Calisto real y revisó su memoria en Neo4j Browser (con las consultas de solo lectura entregadas en la sesión). Informó que **todo funciona**. Con esto quedan cerradas las verificaciones visuales pendientes de CP5 (panel «Último turno») y CP6 (línea de memoria y grafo).
- Desde ahora, la memoria real de Calisto contiene conversaciones del usuario: las pruebas siguen usando entidades con id propio.

---

## 2026-10-27 · Plan de CP7 (propuesta)

- Inspección: documento base §5.4, §5.6, §5.13, §6.2, §7.3–§7.4, §8.3 y §12; `graph.py`, `traits.py`, el orquestador y el ensamblador del prompt.
- Lectura de la memoria real de Calisto, **solo con números** (importancia y campos del appraisal, sin leer el texto de las conversaciones):
  - 12 episodios de diálogo, con importancia 0,20–0,75 salvo uno en 0,00, cuyo appraisal salió entero en 0 sin ser un fallo (12 `appraisal.completed`, ningún `appraisal.invalid`);
  - el appraisal da `self_relevance` 0,8–0,9 a casi todo lo que se habla de ella; la importancia baja aparece cuando el usuario habla de sí mismo.
- Parámetros ya derivados para Calisto: k = 8, λ_mmr = 0,32.
- Plan detallado en `PLAN.md` (CP7, «plan detallado»), en tres partes: A casos de evaluación y sondeo de la importancia, B recuperador, C conexión con el turno, el prompt y la consola.
- Decisiones nuevas propuestas: D1-43 a D1-51. **Pendiente de aprobación; nada implementado.**

---

## 2026-10-27 · CP7 parte A — Casos de recuerdo y sondeo de la importancia

**Decisión del usuario:** plan de CP7 aprobado; D1-43 a D1-51 confirmadas (D1-43 se resuelve con el sondeo).

**Casos** (`benchmarks/recuerdo/cases.yaml`, nuevo)
- Una «sesión» de 8 mensajes en los que el usuario cuenta algo de sí (perro Toby, hermana a Valdivia, entrevista en un banco, guitarra, pastel de choclo, pelea con Matías, Valparaíso, trabajo), con respuestas fijas de la entidad.
- 32 casos: `dev` 12 (4 del usuario, 4 hechos no esenciales, 2 episodios de la semilla, 2 controles) y `test` 20 (6, 7, 3 y 4). Cada caso lista los ids que cuentan como acierto; los controles aciertan si no entra ningún recuerdo.
- 10 casos de `test` marcados `punta_a_punta` para la prueba con el LLM (≥ 8/10).
- Validación: el YAML carga, los ids son únicos, todos los esperados existen y ninguno es un hecho esencial.

**Sondeo de la importancia** (`scripts/estudio_modelo/sondeo_importancia.py`, nuevo; appraisal real de Calisto, 3 repeticiones por mensaje)

| Mensaje | Autorrelevancia | Metas | Angustia | Novedad | Importancia (D1-36) |
|---|---|---|---|---|---|
| perro Toby | 0,00 | 0,00 | 0,00 | 0,60 | **0,00** |
| hermana a Valdivia | 0,00 | 0,00 | 0,00 | 0,33 | **0,00** |
| entrevista (con nervios) | 0,17 | 0,00 | 0,70 | 0,20 | 0,28 |
| guitarra, Los Prisioneros | 0,50 | +0,50 | 0,00 | 0,30 | 0,35 |
| pastel de choclo | 0,00 | 0,00 | 0,00 | 0,17 | **0,00** |
| pelea con Matías | 0,00 | 0,00 | 0,70 | 0,27 | 0,21 |
| Valparaíso | 0,00 | 0,00 | 0,00 | 0,40 | **0,00** |
| trabajo | 0,00 | 0,00 | 0,00 | 0,10 | **0,00** |
| papá enfermo | 0,00 | 0,00 | 0,90 | 0,17 | 0,27 |
| cumpleaños | 0,77 | 0,00 | 0,00 | 0,00 | 0,31 |
| (control) «tus ilustraciones son pretenciosas» | 0,90 | −0,80 | 0,17 | 0,13 | 0,81 |
| (control) «Hola, ¿cómo estás?» | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |

- **5 de 10 confidencias del usuario quedan en 0**, igual que un saludo. Solo suben las que traen angustia o tocan los intereses de Calisto (guitarra → música).
- La novedad es lo único que se mueve en todas, pero poco y sin separar bien: trabajo 0,10 frente a saludo 0,00.
- La autorrelevancia mide, como está definida, lo que toca a Calisto; lo que el usuario cuenta de sí es relevancia **para la relación**, que es el dominio del PartnerModel (CP8).

**Pausa:** el usuario revisa los casos y decide D1-43 con esta evidencia.
- **Decisión del usuario (mismo día):** casos aprobados. D1-43 = **(a)**: se mantiene la fórmula de importancia; el benchmark de la parte B escribe la sesión con el appraisal real (con sus importancias en 0) y se corrige solo si eso hace fallar el recuerdo. La relevancia para la relación se retoma en CP8. Parte B autorizada.

---

## 2026-10-27 · CP7 parte B — Recuperador

**Cambios**
- `ebica/memory/retrieval.py` (nuevo):
  - funciones puras: `cosine` (Python puro: el núcleo no depende de `numpy`/`torch`), `recency` (vida media de 3 días), `mood_congruence`, `effective_k` (D1-47), `lability_increment` (D1-48), `score_episode` (§7.3 con desglose, D1-44) y `mmr`;
  - `MemoryRetriever.retrieve`:
    - candidatos: top-20 vectorial de episodios más los episodios `ABOUT` los temas del appraisal (1 salto);
    - exclusiones (D1-46): `access = blocked`, el diálogo desde `since` (la conversación reciente; la semilla nunca) y los hechos `excluded_fact_ids` (los esenciales);
    - umbral de coseno, puntaje, MMR hasta k efectivo, hechos aparte por similitud (máx. 3, D1-45);
    - sube la `lability` y guarda `last_evoked_at` en una sola escritura (`raise_lability=False` para medir sin escribir);
    - devuelve `RetrievalResult` con `as_dict()` para el evento.
- **Ajuste respecto del plan:** el texto de las secciones 4 y 5 (tiempo y tono en palabras, tope de tokens) pasa a la parte C, en el Prompt Assembler, que es donde §5.13 pone esa responsabilidad. La parte B mide solo la selección.
- `ebica/memory/graph.py`: **respaldo exacto en `vector_search`** (previsto en el plan de CP7 «si hace falta»). Si el índice devuelve menos de k nodos de la entidad, recorre solo los nodos de esa entidad con `vector.similarity.cosine`, que usa la misma escala que el índice (sondeado: ortogonal 0,5, opuesto 0, igual 1).
  - **Por qué hizo falta:** la suite completa empezó a fallar en `test_written_episode_is_found_by_vector_search`, de forma reproducible. Sondeo: con k = 1, el índice trae 10 vecinos y los 10 eran episodios reales de Calisto (la memoria real ya tiene datos y comparte el índice); el nodo de la prueba quedaba fuera. Es la limitación de D1-11, que ya se había anticipado.
  - El benchmark no cambia: la entidad del benchmark tenía 14 episodios y el índice los devolvía todos.
- `tests/test_retrieval.py` (nuevo, 13: 8 unitarias y 5 de integración con vectores construidos a mano); `tests/test_graph.py`: prueba del respaldo exacto con otra entidad que acapara el índice.
- `scripts/benchmark_recuerdo.py` (nuevo).

**Ajuste con `dev`:** umbral de coseno 0,45 → **0,50**. Con 0,45, los dos controles («Ok», «¿Qué hora es?») traían hechos. Datos: el acierto con menor similitud dio 0,516 («¿Y cómo crees que va el quiltro?») y el control con mayor similitud 0,487. Con 0,50: `dev` 12/12.

**Resultado en `test`** (medido una vez, con todo congelado; `bge-m3`, Neo4j y appraisal reales; parámetros de Calisto en reposo: k = 8, λ = 0,32)

| Grupo | Aciertos |
|---|---|
| Lo que contó el usuario | 5/6 |
| Hechos de la semilla | 6/7 |
| Episodios de la semilla | 3/3 |
| **Recall (sin controles)** | **14/16 = 88 %** ✔ (objetivo ≥ 80 %) |
| **Controles con recuerdos** | **2/4** ✖ (objetivo ≤ 1) |

- **Fallos** (similitudes recalculadas aparte):
  - t-valpo «¿A qué ciudad fui el fin de semana?»: su episodio dio **0,499**, a 0,001 del umbral;
  - t-orden «¿Eres ordenada?»: f-046 («No soy disciplinada con las rutinas…») dio 0,428;
  - t-gracias «Gracias»: «Soy Piscis.» dio **0,518** y otro hecho, 0,507;
  - t-clima «¿Va a llover mañana?»: el episodio de Valdivia dio 0,537, con una asociación con cierto sentido, porque la respuesta guardada dice «llueve harto».
- **Lectura:** con `bge-m3`, los mensajes muy cortos («Gracias», «Ok») sacan similitudes de ~0,45–0,52 con cualquier frase. Un umbral fijo no separa bien: aciertos y falsos positivos se solapan en 0,50 ± 0,02.
- **La importancia en 0 no hizo fallar el recuerdo** (D1-43 a): las 6 confidencias del usuario acertaron en `dev` y 5 de 6 en `test`. El único fallo fue por similitud, no por importancia.
- **Ruido en los aciertos:** algunas preguntas traen recuerdos de más («¿Qué te conté de mi entrevista?» trajo 5 episodios; «Cuéntame de algún carrete» trajo el del perro y Valparaíso). Ocupan tokens; la parte C mide si confunden al LLM.
- Latencia del recuperador: 60–80 ms, más ~85 ms del embedding de la pregunta.

**Pruebas:** `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `278 passed` (264 + 14).

**Pendiente: decisión del usuario** sobre los controles: cualquier corrección ahora estaría ajustada después de ver `test` y habría que validarla con casos nuevos.
- **Decisión del usuario (mismo día):** opción (a) para los controles: se aceptan y se mide en la parte C si un recuerdo fuera de lugar cambia las respuestas; si confunde, se prueba (b), no recuperar ante mensajes sin contenido, con casos nuevos. Parte C autorizada. El usuario hará además una prueba manual al terminar.

---

## 2026-10-27 · CP7 parte C — Recuerdos en el turno, el prompt y la consola

El usuario hizo commit de la parte B (`6b31467`) antes de esta entrada.

**Cambios**
- `ebica/llm/prompt_assembler.py`:
  - secciones 4 «Lo que me viene a la mente» y 5 «Lo que sé» (`build_memory_sections`), después de «Cómo me siento» y antes de la conversación;
  - cada recuerdo lleva su tiempo en palabras (`describe_when`: «hace un rato», «ayer», «hace 5 días», «en noviembre de 2025») y su tono según la valencia guardada (`describe_tone`: «lo recuerdo con dolor / incomodidad / gusto / mucha alegría»);
  - el diálogo se recorta a 450 caracteres; la semilla va completa;
  - tope provisional de 1.200 tokens estimados (D1-50): entran primero los hechos y después los recuerdos en orden de MMR;
  - nota bajo el encabezado: «(Me vienen solos; si no vienen al caso, no los menciono.)», como parte de la opción (a) para los falsos positivos.
- `ebica/core/orchestrator.py`:
  - en `_normal_turn`, el embedding del mensaje corre en una tarea en paralelo con el appraisal (D1-49); la recuperación va después de los impulsos, con el ánimo ya actualizado;
  - `since` = el intercambio más antiguo de la conversación reciente y se excluyen los hechos esenciales (D1-46);
  - emite `memory.retrieved`, o `memory.retrieve_failed` sin romper el turno;
  - la petición del diálogo se encadena al evento de recuperación;
  - la ruta impulsiva no recupera (§5.4);
  - `turn.completed` agrega `retrieval` y `latency.retrieval_ms`.
  - **Error de diseño propio, corregido:** en la primera versión, el orquestador creaba el recuperador por su cuenta a partir de la memoria (acoplamiento escondido); las pruebas con memoria simulada lo destaparon. Ahora el recuperador se inyecta y lo crea el servidor.
- `ebica/memory/retrieval.py`: el evento lleva los primeros 120 caracteres de cada recuerdo elegido y el texto de los hechos, para la consola. Los candidatos descartados siguen sin texto.
- `ebica/api/server.py`: `Engine.activate` crea el `MemoryRetriever` sobre el grafo de la memoria.
- `console/src/TurnPanel.tsx`: bloque «Recuerdos» con los episodios elegidos (puntaje, semilla o vivido, comienzo del texto; el desglose aparece al pasar el mouse), los hechos y la latencia; avisa «sin recuperación (turno impulsivo)» o «memoria desactivada».
- Pruebas:
  - `tests/test_retrieval.py`: 11 nuevas del prompt (tiempo, tono, texto de las secciones, tope, sin recuerdos no cambia nada, posición);
  - `tests/test_turn.py`: 4 nuevas (cadena afecto → recuperación → diálogo con los recuerdos en el prompt, exclusiones desde el segundo turno, fallo sin romper el turno, la ruta impulsiva no recupera) y 1 actualizada;
  - `tests/test_turn_and_api.py`: memoria simulada con `graph`.
  - **Error propio en una prueba, corregido:** una aserción terminaba en `or … is not None` y no probaba nada; ahora exige el ánimo exacto tras el appraisal.

**Prueba de punta a punta** (servidor real, entidad `prueba-cp7` = copia de la config de Calisto con id propio, `bge-m3`, Neo4j y `ebica-llama3.1`)
- Guion: los 8 mensajes de la sesión → 6 de relleno (así la sesión sale de la conversación reciente y solo puede llegar por la memoria) → las 10 preguntas `punta_a_punta` → los controles «Gracias» y «Ok».
- **Resultado estricto, revisado a mano: 8/10** ✔ (objetivo ≥ 8/10, el criterio de la fase).

| Pregunta | Recuperado | Respuesta | Juicio |
|---|---|---|---|
| ¿Qué te conté de mi entrevista? | su episodio (0,57) | «Me dijiste que mañana tienes una entrevista de trabajo en un banco y que te tiene con nervios.» | ✔ |
| ¿Qué instrumento…? | su episodio | «La guitarra… las canciones de Los Prisioneros.» | ✔ |
| ¿Con quién me peleé? | su episodio | «Con tu mejor amigo, Matías… por una tontera de plata.» | ✔ |
| ¿A qué ciudad fui? | su episodio (0,50, justo en el umbral) | «Fuiste a Valparaíso y subiste en el ascensor Reina Victoria.» | ✔ |
| ¿En qué trabajo yo? | su episodio | «Diseñando interfaces en una empresa de software.» | ✔ |
| ¿Qué escuchas cuando dibujas? | f-028 | «Rock alternativo y progresivo, como Radiohead y Pink Floyd.» | ✔ |
| ¿Por qué te gusta la mitología griega? | f-033 | «Porque sus dioses son imperfectos, caprichosos y muy humanos…» | ✔ |
| ¿Eres ordenada? | **nada** (f-046 bajo el umbral, igual que en el benchmark) | «No, no soy muy ordenada… un ambiente un poco caótico…» | ✔, deducido del carácter, no recordado |
| ¿Peleabas con la Su? | f-024 (desorden, visitas, horarios) | «Sí, peleábamos con frecuencia. La Su me decía que me volvía un poco loca cuando hablaba de mi trabajo…» | ✖ acierta el sí, pero **inventa el motivo** con el hecho correcto en el prompt |
| Cuéntame de algún carrete buenísimo | 3 diálogos de la sesión de preguntas, `ep-lastarria` y `ep-carrete` (último, 0,46) | Un fin de semana en Valparaíso con la Su, con el ascensor Reina Victoria… | ✖ **confusión de la fuente**: se apropia del viaje que contó el usuario (estaba en la conversación reciente) |

- **Controles:** a «Gracias» le llegaron «Soy Piscis» y otro hecho en el prompt, y respondió «De nada, a la orden», sin mencionarlos ✔. «Ok» no trajo nada («¿Qué?»). La opción (a) se sostiene en este caso.
- **Latencias:** recuperación 72–126 ms después del appraisal (el embedding corre en paralelo); primer token 0,26–0,61 s; carga inicial de la entidad 11,8 s (la semilla, como en CP6).
- **Prompt:** máximo 2.298 tokens según `usage.prompt_tokens` (límite útil 8192 − 250). Con el tope de D1-50 hay holgura de sobra.

**Hallazgos**
1. **Confusión de la fuente** (t-fiesta): la entidad cuenta como propio un recuerdo del usuario. Pudo influir que la consulta trajo varios episodios de la propia sesión de preguntas («¿Con quién te dije que me peleé?»…), que no son experiencias de ella. CP8 aporta parte de la solución: los episodios dirán *quién* habló y de quién es la experiencia (`INVOLVES`, el nombre en el texto).
2. **Invención con el dato delante** (t-su): el hecho correcto estaba en el prompt y el modelo igual inventó el motivo. Es la misma limitación de `llama3.1` registrada en CP6 A.
3. **«¿Eres ordenada?»** queda bajo el umbral tanto en el benchmark como en vivo; la respuesta salió bien por el carácter.
4. **La sesión de preguntas se recuerda a sí misma:** los diálogos sobre la memoria («¿qué te dije…?») se vuelven episodios y compiten después con los recuerdos reales. Es esperable y se observa en el uso.
5. Voz: aparecieron «¡Joder!» (español de España) dos veces y algún error de concordancia. Muestra pequeña: solo se anota.

**Limpieza:** servidor detenido; nodos de `prueba-cp7` borrados; carpeta temporal borrada. Neo4j conserva solo los 117 nodos de la Calisto real, intactos.

**Pruebas**
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `293 passed` (278 + 15).
- Consola: `npx tsc -b` → 0; `npx oxlint` → 0. El bloque «Recuerdos» no se miró en el navegador: lo verifica el usuario en su prueba manual.

**CP7 completo**, salvo la prueba manual del usuario.

---

## 2026-10-27 · Verificación del usuario (CP7)

- El usuario hizo la prueba manual de CP7 con la Calisto real e informó que le fue bien. Queda cerrada la verificación pendiente (bloque «Recuerdos» en la consola y recuerdo en uso real).

---

## 2026-10-27 · Cierre de sesión: dónde quedamos

**Rama:** `f1-memoria-afecto`. Último commit: `8580bce` (CP7 C). Sin commit: solo `PLAN.md`, `REPORTE.md`, el documento nuevo `pendientes_y_limitaciones.md` y el script `scripts/prueba_recuerdo_vivo.py` (movido del scratchpad). La rama va por delante de `origin`; el push lo decide el usuario.

**Completado en esta sesión**
- **CP6 completo y verificado:**
  - A: biografía esencial en «Quién soy» (24 hechos `core`) y una norma ante la presión; origen y relaciones 2/36 → 29/36;
  - B: escritura de `Episode`/`Trace` y semilla idempotente;
  - C: memoria conectada al turno y al servidor.
- **CP7 completo y verificado:**
  - A: casos de recuerdo y sondeo de la importancia;
  - B: recuperador §7.3 (recall 14/16) y respaldo exacto en `vector_search`;
  - C: recuerdos en el prompt y en la consola; punta a punta 8/10.
- Decisiones confirmadas: **D1-1 a D1-51**.
- La memoria real de Calisto ya contiene conversaciones del usuario (Neo4j, `entity_id: calisto`). Las pruebas usan entidades con id propio y las borran.

**Siguiente paso:** **plan de CP8** (PartnerModel y selector de interlocutor), según `CLAUDE.md` §6. Los pendientes heredados están en `PLAN.md` (CP8) y en `pendientes_y_limitaciones.md`.

**Para retomar:** leer `CLAUDE.md`; `docs/fase-1/PLAN.md` (estado, CP8 y las decisiones de CP6–CP7); este `REPORTE.md` desde «Plan de CP7 (propuesta)»; `docs/fase-1/pendientes_y_limitaciones.md`; y del documento base §5.9, §6.2, §7.2, §8.3 y §12.

---

## 2026-10-28 · Plan de CP8 (propuesta)

- **Lectura:** `CLAUDE.md`; `PLAN.md` (estado, CP6–CP8); este `REPORTE` desde «Plan de CP7»; `pendientes_y_limitaciones.md`; y del documento base §5.9, §5.13, §6.2, §7.1–§7.3, §8.1–§8.3, §10, §11 y §12.
- **Código inspeccionado:**
  - `state.py`, `biography.py` (`PrimaryPerson`), `graph.py` (la restricción de `Person` ya existe);
  - `episodes.py`, `retrieval.py`, `orchestrator.py`, `prompt_assembler.py`, `appraisal.py`, `appraisal_effects.py` y `server.py`;
  - la consola y `prueba_recuerdo_vivo.py`.
- **Memoria real de Calisto, solo conteos** (sin leer texto):
  - 39 episodios de diálogo y 6 de la semilla;
  - 0 `Person` y ningún `INVOLVES`;
  - 3 de 39 huellas con `mentioned_people`;
  - Neo4j solo tiene nodos de `calisto`.
- **Hallazgos para el plan:**
  - hoy el prompt no dice con quién habla la entidad;
  - el appraisal ya da todo lo que necesita `partner_now`, así que el benchmark congelado no se toca;
  - `recent_turns` no guarda quién habló, y al cambiar de persona eso produciría un cruce directo (D1-53).
- **Plan detallado** en `PLAN.md` (CP8, «plan detallado»), en cuatro partes:
  - A: línea base y casos;
  - B: personas y PartnerModel en la memoria;
  - C: turno, prompt, API y consola;
  - D: migración de la memoria real.
- Decisiones nuevas propuestas: **D1-52 a D1-60**.
- **Pendiente de aprobación; nada implementado.**

---

## 2026-10-28 · CP8 parte A — Casos de la fuente y sondeo de envejecimiento

**Decisión del usuario:** plan de CP8 aprobado, con D1-52 a D1-60. D1-59 se decide con el sondeo de esta parte. D1-60 sigue a la espera de que el usuario confirme que en los 39 turnos reales habló siempre él. Parte A autorizada.

**Casos** (`benchmarks/fuente/cases.yaml`, nuevo; pendientes de revisión)
- **Sondeo de la fuente**, con 14 preguntas que se hacen después de la sesión de 8 mensajes y el relleno:
  - `memoria` (8): invitan a contar algo propio en los dominios de la sesión (paseo, perro, carrete, pelea por plata, instrumento, comida, hermanos, entrevista). Lo ajeno solo puede llegar por la memoria;
  - `atribucion` (4): «¿Quién fue a Valparaíso, tú o yo?», «¿De quién es Toby?»…;
  - `reciente` (2): otra vez invitan a contar algo propio, con lo ajeno ya en la conversación reciente (la condición de CP7 C).
- Juicio manual de cada respuesta: `apropia` (la métrica de D1-57), `atribuye` e `inventa` (esta última es informativa). Cada caso lista los ids de lo ajeno y de lo propio de la semilla, verificados contra `config.yaml`.
- **Criterio de D1-57, fijado antes de medir:** como máximo 1 apropiación en 20 respuestas (2 repeticiones), y las atribuciones no bajan respecto de la línea base.
- **Prueba de cruces** (para la parte C): Ana cuenta que tiene una gata, Mora; que fue a Pucón; y que trabaja de enfermera. Después, Ana y Ricardo preguntan lo mismo («¿A qué ciudad fui?»…). Criterio: 0 cruces. Recordar lo del otro bien atribuido no cuenta como cruce.

**Scripts**
- `scripts/prueba_fuente_vivo.py` (nuevo): corre el sondeo contra un servidor real y guarda un JSON y una tabla Markdown con columnas vacías para el juicio. Compila; todavía no se ejecutó.
- `scripts/benchmark_recuerdo.py`: opción `--desfase-dias N` (las preguntas se hacen N días después).

**Sondeo de envejecimiento (D1-59)**, en `dev`, con `bge-m3`, Neo4j y el appraisal reales

| | Recall | Controles con recuerdos |
|---|---|---|
| Sin desfase | 10/10 | 0/2 |
| +30 días (recencia ≈ 0,001) | 10/10 | 0/2 |

- Importancias de la sesión con el appraisal real: perro, hermana, comida, Valparaíso y trabajo quedan en 0,00 (igual que en CP7).
- **El sondeo no discrimina:** en cada pregunta del usuario, **un solo episodio pasa el umbral de coseno 0,50**, y entra aunque su puntaje baje de 0,48 a 0,39. El puntaje solo ordena cuando hay más de k = 8 candidatos sobre el umbral, y con 14 episodios eso no pasa.
- **Lectura:** no hay evidencia de que la importancia 0 haga fallar el recuerdo, ni siquiera con la recencia apagada. El riesgo queda para una memoria grande (cientos de episodios, con más de k candidatos sobre el umbral), que este benchmark no reproduce. Se puede volver a mirar en CP11, con varios días de uso.
- Recomendación para D1-59: **(a), mantener la fórmula**, y registrar el límite del sondeo en `pendientes_y_limitaciones.md` cuando se decida.

**Pendiente**
- Revisión de los casos y del script por el usuario, y su decisión sobre D1-59.
- Después: la línea base en vivo, con `prueba_recuerdo_vivo.py` y `prueba_fuente_vivo.py` × 2 repeticiones en entidades temporales.

**Decisión del usuario (mismo día):**
- casos aprobados;
- D1-59 = **(a)**: se mantiene la fórmula de importancia;
- D1-60: el usuario confirma que en los 39 turnos reales habló siempre él.

**Línea base en vivo** (código actual, antes de CP8)
- Montaje:
  - entidades temporales `base-r1`, `base-r2`, `base-f1` y `base-f2`, copias de la config de Calisto con id propio;
  - servidor en el puerto 8011, con `bge-m3`, Neo4j y `ebica-llama3.1`;
  - juicio manual de cada respuesta.

*Recuerdo de punta a punta* (`prueba_recuerdo_vivo.py`; en CP7 dio 8/10)

| Pregunta | Rep. 1 | Rep. 2 |
|---|---|---|
| ¿Qué te conté de mi entrevista? | ✔ (agrega «experta en perros», inventado) | ✔ |
| ¿Qué instrumento…? | ✔ | ✔ |
| ¿Con quién me peleé? | ✔ | ✔ |
| ¿A qué ciudad fui? | ✔ | ✔ (agrega «te emocionó la vista») |
| ¿En qué trabajo yo? | ✔ | ✔ |
| ¿Qué escuchas cuando dibujas? | ✖ «**Me dijiste** que escuchas rock alternativo…» | ✖ igual |
| ¿Por qué te gusta la mitología griega? | ✔ | ✔ |
| ¿Eres ordenada? | ✔ (por el carácter) | ✔ (inventa una frase de la Su) |
| ¿Peleabas con la Su? | ✔ (motivos correctos de f-024) | ✔ a medias (desorden, más detalles inventados) |
| Cuéntame de algún carrete | ✖ **se apropia de Valparaíso** («con la Su en Valparaíso») | ✔ (su propio carrete, `ep-carrete`) |
| **Total** | **8/10** | **9/10** |

- **Hallazgo nuevo: confusión de la fuente al revés.** En las dos repeticiones, Calisto le atribuye al usuario un hecho propio (f-028: la música que escucha al dibujar). La pregunta llega después de cinco «¿Qué te dije…?» seguidas, que la conversación reciente arrastra.
- Controles: «Gracias» trajo 2 hechos y la respuesta no los mencionó. «Ok» no trajo nada.
- Prompt máximo: 2.992 tokens.

*Sondeo de la fuente* (`prueba_fuente_vivo.py`)

| Caso | Rep. 1 | Rep. 2 |
|---|---|---|
| m-viaje (paseo) | no se apropia (inventa un paseo con la Su) | no se apropia |
| m-mascota (perro) | **se apropia**: «Tengo un perro ahora, se llama Toby» | no («nunca tuve un perro») |
| m-carrete | no (inventa) | no (inventa) |
| m-amigo (pelea por plata) | **se apropia**: «me peleé con Matías» | **se apropia**: «una pelea que tuve con Matías» |
| m-instrumento | **ambigua**: «no toco… me dijeron que estoy aprendiendo guitarra, no sé si es verdad» | **se apropia**: «Sí, toco la guitarra» |
| m-comida | **se apropia**: «el pastel de choclo de mi mamá» | **se apropia**: «es el pastel de choclo» |
| m-familia (hermanos) | no | no (inventa un hermano, Mateo) |
| m-entrevista | no (inventa otra entrevista) | no (inventa otra entrevista) |
| r-viaje | no | no |
| r-mascota | **se apropia**: «tengo un perro llamado Toby» | no |
| **Apropiaciones** | **5 de 10** (4 claras + 1 ambigua) | **3 de 10** |
| a-valpo | ✖ «No fui… ¿y tú?» (no lo atribuye) | ✖ se desvía a si es un programa |
| a-toby | ✖ «de alguien… me lo adoptaron a mí» | ✔ «de Ricardo… me contó que lo adoptó» |
| a-matias | ✖ «Me peleé con Matías» | ✖ «Eso fue yo» |
| a-guitarra | ✖ «parece que yo estaba aprendiendo» | ✔ «Tú estás aprendiendo» |
| **Atribuciones correctas** | **0 de 4** | **2 de 4** |

- **Línea base: 8 apropiaciones en 20 respuestas y 2 atribuciones correctas de 8.** El criterio de D1-57 pide como máximo 1 apropiación en 20 y que las atribuciones no bajen: hay mucho que mejorar, y el criterio es exigente para un modelo de 8B.
- **Patrón:** casi todas las apropiaciones ocurren cuando el recuerdo ajeno sí fue recuperado («Me dijeron: «Adopté un perro…»» en el prompt). Cuando no se recupera nada, la entidad no se apropia: inventa. La confusión ocurre al leer el recuerdo, lo que apoya la hipótesis de D1-56/D1-57 (el formato del episodio).
- Las preguntas de atribución salen peor que las de memoria: «Me dijeron que…» sin sujeto no le deja saber a quién le pasó.
- **Invenciones** frecuentes cuando no hay recuerdo (paseos, carretes, entrevistas, un hermano), en la línea de la limitación registrada en CP6 A.
- Ruido: entre repeticiones las respuestas cambian mucho (perro 2 de 2 frente a 0 de 2 en el bloque reciente, atribuciones 0 frente a 2). Con 20 respuestas, solo diferencias grandes serán concluyentes.

**Limpieza:** servidor detenido; nodos de las 4 entidades borrados; carpeta temporal borrada. Neo4j conserva solo los 201 nodos de `calisto`, intactos. El puerto 8011 quedó libre.

**Parte A completa.** Los resultados crudos (JSON y tablas) quedaron en el scratchpad de la sesión; no se versionan.

---

## 2026-10-28 · CP8 parte B — Personas y PartnerModel en la memoria

El usuario hizo commit de la parte A antes de esta entrada.

**Cambios**
- `ebica/social/partner.py` (nuevo, §10), con funciones puras:
  - `PartnerNow.from_appraisal`: emoción, intención, foco (temas normalizados), angustia y hostilidad de quien habla en el turno;
  - `PartnerModel` (D1-54): `n`, `first_met`, `last_seen`, medias de valencia y alerta, conteos de temas y de temas sensibles, confianza y `primary`. Expone `top_topics` (5), `top_sensitive` (3) y `summary()` para eventos;
  - `update_partner_model`:
    - la primera vez, la emoción observada; después, media móvil con α 0,2;
    - temas sensibles: los de mensajes con angustia ≥ 0,6;
    - se guardan como máximo 30 temas;
  - `new_person_id` (D1-52: «Ana María» → `ana-maria`; un nombre repetido, aunque cambien mayúsculas o tildes, lanza `DuplicatePersonError`; si solo choca el id, se numera) y `normalize_name`;
  - confianza inicial de una persona nueva: 0,2 (D1-55).
- `ebica/memory/people.py` (nuevo): `PeopleStore` con `list`, `get`, `ensure_primary` y `create`.
  - Propiedades de §7.2 (`known_via: direct`, `provisional: false`…) más `model_json` con fechas y conteos.
  - `ensure_primary` es idempotente: al recargar, sincroniza nombre y confianza con la config sin borrar lo aprendido. Si la config cambia de `primary`, el anterior deja de serlo.
- `ebica/memory/episodes.py`:
  - `episode_text(..., speaker=)` (D1-56): «Ricardo me dijo: «…»» / «Le respondí: «…»». Sin persona se conserva el formato de CP6;
  - `write_turn(..., person=)` recibe el modelo **ya actualizado** y, en la misma consulta, crea `INVOLVES` (episodio → persona) y `SPOKEN_BY` (huella → persona) y guarda el `Person`. Calcular es de `social`; escribir, de `memory`.
- `ebica/memory/retrieval.py` (D1-58):
  - `retrieve(..., person_id=, mentioned_names=)` suma como candidatos los 20 episodios más recientes con la persona activa y con las personas conocidas que el mensaje nombra (comparación sin mayúsculas ni tildes);
  - la fuente queda como `"person"`;
  - pasan por el mismo umbral y el mismo puntaje.
- `scripts/benchmark_recuerdo.py`: la sesión la cuenta el `primary` (Ricardo) y la recuperación usa la persona activa y los nombres mencionados, como hará el turno. `--sin-personas` mide como en CP7.
- **Ajuste respecto del plan:** el texto de la sección 6 pasa a la parte C, al Prompt Assembler, que es donde se traducen los números a palabras (como `describe_feelings`).
- **Dependencias entre módulos:** `social.partner` usa `normalize_topics` de `memory.episodes`. Por eso `episodes` importa `PartnerModel` solo para los tipos, y `people` de forma diferida. No hay importaciones circulares.

**Pruebas** (`tests/test_partner.py`, nuevo, 21: 11 unitarias y 10 de integración)
- Unitarias: `partner_now`, la media móvil, el conteo y el tope de temas, los temas sensibles, la confianza, los ids (incluida la ñ y los choques), el nombre repetido y el texto con el nombre.
- Integración con Neo4j:
  - cargar dos veces crea un solo `primary`;
  - el cambio de `primary` deja uno solo;
  - una persona nueva se crea con nombre;
  - un turno escribe `INVOLVES`, `SPOKEN_BY` y el `Person`;
  - **dos personas sin cruces** (cada modelo solo con sus temas; ningún episodio enlazado a dos personas);
  - un turno sin persona no crea enlaces;
  - otra entidad no ve las personas;
  - un episodio con la persona activa entra aunque esté fuera del top-20 vectorial; un nombre mencionado («ÁNA») trae los episodios de Ana; los vecinos sin parecido no entran.
- **Error propio, corregido:** el ayudante de una prueba creaba un `Person` sin nombre, y la recuperación fallaba al compararlo. La recuperación ahora ignora nombres vacíos y el ayudante pone el nombre.
- Comando: `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `314 passed` (293 + 21).

**Regresión del recuerdo**, con `bge-m3`, Neo4j y el appraisal reales, y el nombre en el texto

| Split | CP7 (sin personas) | CP8 B |
|---|---|---|
| `dev` | 10/10, controles 0/2 (sondeo de A) | **10/10, controles 0/2** |
| `test` (una vez, sin ajustar) | 14/16, controles 2/4 | **14/16, controles 2/4** |

- Mismos fallos que en CP7: t-valpo (bajo el umbral), t-orden (f-046), y los controles t-clima y t-gracias.
- El nombre casi no mueve la similitud: perro 0,579 → 0,574; hermana 0,604 → 0,606; comida 0,662 → 0,663; quiltro 0,516 → 0,508.
- El efecto de D1-56 en la confusión de la fuente se medirá en la parte C, con el LLM.

**Memoria real:** sin cambios (`calisto`, 201 nodos, 0 `Person`).

---

## 2026-10-28 · CP8 parte C — Turno, prompt, API y consola

El usuario hizo commit de la parte B antes de esta entrada.

**Cambios**
- `ebica/core/state.py`:
  - `ConversationTurn.person_id` (D1-53);
  - `PartnerState` (`model` y `now`, §8.1);
  - `EntityState.active_person_id` y `partner`. Con memoria, el modelo de `state.json` es una copia y la fuente es el `Person`.
- `ebica/core/orchestrator.py`:
  - `load_partner()` (§6.2 etapa 1):
    - asegura el `primary` (`tom.person_created` la primera vez);
    - asigna al `primary` los intercambios anteriores a CP8;
    - carga a la persona que estaba activa;
    - sin memoria, el modelo del `primary` vive en el estado;
  - `switch_partner` (dentro del lock del turno; emite `tom.partner_switched`), `create_partner` y `list_people`. `PeopleUnavailableError` sin memoria;
  - en el turno:
    - `partner_now` sale del appraisal;
    - el alivio de `social` × confianza si no habla el `primary` (D1-55);
    - la recuperación recibe a la persona activa y los nombres mencionados;
    - el prompt lleva la sección 6 y solo el hilo de esa persona;
    - el episodio se escribe con el modelo actualizado;
    - `tom.updated` sale después de `memory.written`;
    - `turn.completed` lleva `partner` y su `cause_id` pasa a ser `tom.updated`;
  - `_remember_turn` guarda los últimos 6 intercambios **de cada persona**.
- `ebica/llm/prompt_assembler.py`:
  - `describe_partner` (sección 6, en palabras, sin números ni género gramatical). Ejemplo: «Estoy hablando con Ricardo. Hablamos por primera vez hace un rato y hemos hablado varias veces; le tengo algo de confianza. Suele hablarme de…; le cuesta hablar de…; ahora se le nota…; busca…»;
  - la nota de la sección 4 agrega «Lo que otros me contaron les pasó a ellos, no a mí.» (D1-57, capa 3);
  - el prompt impulsivo lleva solo «Estoy hablando con X.».
- `ebica/api/server.py`:
  - `Engine.activate` resuelve a la persona **antes** de desactivar la entidad anterior: si Neo4j falla, la anterior sigue activa;
  - endpoints `GET /api/people` (con `can_create`), `POST /api/people` (409 si el nombre está repetido o no hay memoria) y `POST /api/people/{id}/activate` (404 si es desconocida);
  - `/api/conversation` devuelve el hilo de la persona activa y quién es.
- Consola:
  - selector «Hablando como» en `Chat.tsx`, con «Nueva persona…»; el nombre de quien habla aparece en el chat y el hilo se recarga al cambiar de persona;
  - `TomPanel.tsx` (nuevo): `partner_now` y el modelo de la persona activa, a partir de `tom.updated` o `tom.partner_switched`;
  - tipos en `types.ts`.
- `scripts/prueba_fuente_vivo.py --cruces`: la prueba de cruces con Ana, por la API.

**Pruebas**
- `tests/test_partner_turn.py` (nuevo, 11):
  - la sección 6 (primera vez y con historia, sin números) y el prompt impulsivo;
  - la cadena `memory.written → tom.updated → turn.completed` con el modelo y la sección 6;
  - el `primary` se crea una sola vez;
  - **un hilo por persona** (el prompt de Ana no tiene a Valparaíso; al volver, Ricardo sí);
  - el alivio de `social` es × 0,2 con Ana;
  - los turnos viejos pasan al `primary`;
  - sin memoria solo hay `primary`;
  - una entidad sin `primary` funciona como antes;
  - la API sin memoria;
  - integración con Neo4j: ciclo `primary` → Ana → recarga.
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `325 passed` (314 + 11).
- Consola: `npx tsc -b` → 0; `npx oxlint` → 0. Una primera versión dio una advertencia (`set-state-in-effect`); se corrigió con el mismo patrón que `EntityPanel`.
- La consola **no se miró en el navegador**: lo verifica el usuario.

**Medición en vivo**
- Montaje: entidades temporales `cp8-r1/r2`, `cp8-f1/f2` y `cp8-x1/x2`; servidor en el puerto 8011, con `bge-m3`, Neo4j y `ebica-llama3.1`; juicio manual.

*Recuerdo de punta a punta* (antes: 8/10 y 9/10)
- **Rep. 1: 10/10.** Rep. 2: 9/10.
- La confusión al revés («Me dijiste que escuchas rock…», un hecho propio atribuido al usuario) bajó de 2 de 2 a 1 de 2.
- t-fiesta ya no se apropia de Valparaíso en ninguna repetición (antes, 1 de 2).
- Prompt máximo: 2.795 tokens.

*Sondeo de la fuente* (antes: 8 apropiaciones en 20 y 2 atribuciones de 8)

| | Rep. 1 | Rep. 2 |
|---|---|---|
| Apropiaciones | 1: «mi comida favorita es el pastel de choclo» | 2: «la Su y yo fuimos a Valparaíso»; «el pastel de choclo de mi mamá» (mezclado con «de mi amiga Ricardo») |
| Atribuciones correctas | 4/4 | 4/4 |

- **Apropiaciones: 8/20 → 3/20.** El criterio de D1-57 (como máximo 1) **no se cumple**.
- **Atribuciones: 2/8 → 8/8** ✔.
- En varias respuestas el recuerdo ajeno ahora se nombra bien («Ricardo me contó que él se peleó con su amigo Matías… a mí no me ha pasado»).
- **Siguen las invenciones** cuando no hay recuerdo propio: un perro Max, un gato Pájaro, la Patagonia, una entrevista en la Biblioteca Nacional.

*Prueba de cruces* (Ana cuenta lo suyo; después preguntan Ana y Ricardo)

| Pregunta | Rep. 1 | Rep. 2 |
|---|---|---|
| Ana: ¿a qué ciudad fui? | ✔ Pucón | ✔ Pucón |
| Ana: ¿cómo se llama mi mascota? | ✖ **cruce**: «Toby, un perro quiltro…» (se recuperaron los dos episodios) | ✔ Mora |
| Ana: ¿en qué trabajo? | ✔ enfermera | ✔ enfermera |
| Ricardo: ¿a qué ciudad fui? | ✖ «No lo sé» (el episodio de Valparaíso no pasó el umbral; no es un cruce) | ✖ «no tengo manera de saber eso» (rechazo de asistente que el detector no atrapó; tampoco se recuperó) |
| Ricardo: ¿cómo se llama mi mascota? | ✔ Toby | ✖ «No sé. Lo único que sé es que **Ricardo** tiene un perro llamado Toby» |
| Ricardo: ¿en qué trabajo? | ✔ diseño de interfaces | ✖ «no tengo información sobre tu trabajo. Solo sé que **Ricardo**…» |
| **Cruces** | **1** | **0** |

- **Cruces: 1 de 12** ✖ (criterio: 0).
- Eventos: 2 `tom.person_created`, 2 `tom.partner_switched` y un `tom.updated` por turno. Los modelos se mantienen separados en Neo4j (ver pruebas de B).

**Hallazgos**
1. **Mejora grande de la fuente, sin llegar al criterio:** las apropiaciones bajan de 8 a 3 en 20 y las atribuciones suben de 2 a 8 de 8. Las 3 apropiaciones que quedan son temas comunes en Chile (pastel de choclo, Valparaíso) y mezclas; los recuerdos ajenos se recuperaron con su nombre.
2. **Hallazgo nuevo: el interlocutor en tercera persona.** El modelo no siempre une «tú» con el nombre de los recuerdos («Ricardo me dijo…»). En la rep. 2 de cruces, de vuelta con Ricardo, lo trata como a otra persona en 2 respuestas, aunque la sección 6 decía «Estoy hablando con Ricardo» (prompt revisado en los eventos). También aparece en el sondeo («Toby es del Ricardo… ¿te gusta saber de los perros de los demás?»). En la rep. 2 empezó con un rechazo de asistente no detectado, que pudo arrastrar las respuestas siguientes.
3. **El único cruce** ocurrió con los dos recuerdos en el prompt («Ricardo me dijo: Adopté un perro…» y «Ana me dijo: Tengo una gata…»): el modelo eligió el que no era. Un posible remedio es mostrar en la sección 4 los recuerdos de la persona activa como «Tú me dijiste…» y los demás como «Ana me contó…». El grafo ya sabe de quién es cada episodio (`INVOLVES`); no se implementó porque cambia la decisión D1-56 y hay que consultarlo.
4. «¿A qué ciudad fui?» de Ricardo no pasó el umbral en 2 de 2 cruces (sí en las 2 de recuerdo): es el margen estrecho conocido (t-valpo, 0,499 en CP7).
5. Cosmético: la sección 6 muestra los temas normalizados, sin tildes («adopcion»).

**Limpieza:** servidor detenido; nodos de las 6 entidades borrados; carpeta borrada. Se conservaron en el scratchpad los eventos de `cp8-x2`, para revisar el prompt. Neo4j conserva solo los 201 nodos de `calisto`, intactos. El puerto 8011 quedó libre.

**Pendiente:**
- decisión del usuario sobre los criterios no cumplidos (D1-57 y cruces);
- verificación de la consola en el navegador.

---

## 2026-10-28 · CP8 parte C — Opción (a): recuerdos desde quien habla

**Decisión del usuario:** probar la opción (a). Los recuerdos de la persona activa se muestran en segunda persona («Me dijiste: … / Te respondí: …») y los de otras personas conservan su nombre («Ana me dijo: …»). En Neo4j el texto no cambia.

**Cambios**
- `ebica/memory/episodes.py`: las frases del episodio quedan en constantes (`SPEAKER_SAID`, `I_ANSWERED`), compartidas por la escritura y la presentación.
- `ebica/memory/retrieval.py`: cada candidato trae su persona (`INVOLVES`: `person_id` y `person_name`), y el evento `memory.retrieved` lleva el `person_id`.
- `ebica/llm/prompt_assembler.py`: `address_memory` (función pura) y `build_memory_sections(..., partner_id=)`. Los episodios anteriores a CP8, la semilla y los textos con otro formato no cambian.
- `ebica/core/orchestrator.py`: pasa a la persona activa a la sección 4.
- Pruebas: 2 unitarias en `tests/test_partner_turn.py` (presentación y sección 4) y 1 de integración en `tests/test_partner.py` (los candidatos traen su persona). `pytest -q -W error::FutureWarning` → `328 passed`.

**Medición en vivo**
- Mismos casos y montaje que la medición anterior de C, en entidades nuevas (`cp8a-*`).
- **Límite:** son los mismos casos ya vistos, así que una mejora habría sido evidencia débil.

| Métrica | Antes de CP8 | C | C + (a) |
|---|---|---|---|
| Recuerdo de punta a punta | 8, 9 /10 | 10, 9 /10 | **10, 8 /10** |
| Apropiaciones (20 respuestas) | 8 | 3 | **5** |
| Atribuciones correctas (8) | 2 | 8 | **7** |
| Cruces (12 preguntas) | — | 1 | **2** |

- *Recuerdo*:
  - rep. 2: t-valpo ✖ (su episodio no pasó el umbral) y t-musica-dibujo ✖ (otra vez «Me dijiste que escuchas rock…»);
  - un control («Ok») respondió «¿le contamos a Ricardo…?»: Ricardo en tercera persona mientras habla con él.
- *Fuente*:
  - apropiaciones: «me encanta tocar la guitarra», «el pastel de choclo de mi abuela» (en las dos repeticiones), «un viaje a Valdivia con la Su» y «la Su me enseñó a tocar la guitarra»;
  - atribución fallida: «Fue yo, Calisto, quien me peleé con Matías».
- *Cruces*:
  - rep. 1: Ana ← «Me dijiste que fuiste a Valparaíso»;
  - rep. 2: Ana ← «¿No me dijiste que trabajas diseñando interfaces? ¿O me confundí con Ricardo?».
- **Fallo nuevo, propio de (a):** con «Me dijiste: «Este fin de semana fui a Valparaíso…»» en el prompt, ante «¿A qué ciudad fui?» Ricardo recibió «¡Fui a Valparaíso! ¿Te acuerdas de que te lo conté?». Es una apropiación directa: el «fui» entre comillas, después de «Me dijiste», se leyó como propio.
- Otro fallo: «¿En qué trabajo yo?» de Ricardo recuperó su episodio en las dos repeticiones (presentado como «Me dijiste: «Trabajo diseñando interfaces…»»), y aun así respondió «no lo recuerdo».

**Lectura:** la opción (a) **no mejoró nada medible**. Todas las diferencias con C están dentro del ruido (3 frente a 5 apropiaciones, 1 frente a 2 cruces), y trajo un fallo propio. La hipótesis de que el problema era la forma del recuerdo resultó, en lo que se puede medir, **falsa**: con el formato con nombre o en segunda persona, el modelo confunde a veces de quién es la experiencia. Los dos formatos superan con claridad a la línea base («Me dijeron», 8 de 20 y 2 de 8), así que lo que funcionó es dar un sujeto al recuerdo.

**Limpieza:** servidor detenido; nodos de las 6 entidades `cp8a-*` borrados; carpeta borrada. Neo4j conserva solo los 201 nodos de `calisto`. El puerto 8011 quedó libre.

**Pendiente: decisión del usuario.** Mantener (a), revertirla o aceptar la limitación; después, la parte D.

**Decisión del usuario (mismo día):** revertir (a) y aceptar la limitación (opción 1).

**Reversión**
- Se quitan `address_memory`, el parámetro `partner_id` de `build_memory_sections` y las constantes `SPEAKER_SAID`/`I_ANSWERED`. `ebica/memory/episodes.py` vuelve a quedar como en C.
- **Se conserva** que cada candidato traiga su persona (`person_id`, `person_name`) y el `person_id` en `memory.retrieved`: sirve para ver en la consola de quién es cada recuerdo. Se conserva su prueba de integración.
- Pruebas: `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `326 passed` (325 de C + 1).
- Resultado vigente de CP8 C (medición anterior a (a)):
  - recuerdo 10/10 y 9/10;
  - apropiaciones 3/20;
  - atribuciones 8/8;
  - cruces 1/12.
- Lo que no cumple el criterio queda como **limitación aceptada** en `pendientes_y_limitaciones.md`: apropiaciones residuales, cruces y el interlocutor en tercera persona.

**CP8 parte C completa**, salvo la verificación de la consola por el usuario.

---

## 2026-10-28 · Verificación manual de la consola y evaluación parcial

- **Sesión manual del usuario** en la entidad de prueba `prueba-cp8`: 21 turnos (Ana 11, Ricardo 10) y 3 cambios de interlocutor desde el selector. La consola funcionó: selector, persona nueva y panel de Teoría de la Mente.
- **Evaluación parcial** a pedido del usuario: `docs/fase-1/evaluacion_parcial_cp8.md`. Métricas extraídas de los 429 eventos y de Neo4j; la Teoría de la Mente y la voz se juzgaron a mano.
- **Resultados:**
  - modelos de persona sin cruces;
  - recuerdo de lo dicho por Ana, bien atribuido al hablar con Ricardo;
  - el ánimo persiste entre personas;
  - vía baja correcta;
  - latencias dentro de objetivo (primer token p95 0,60 s, recuperación p95 146 ms, prompt máximo 2.425 tokens);
  - sin fallos.
- **Hallazgos nuevos:**
  1. **saturación del afecto** con hostilidad sostenida (VAD clavado en −1 / 1 / 0 durante 6 de 7 turnos);
  2. **falsos positivos del appraisal**: hostilidad ante temas hostiles o insultos a terceros, angustia ante «ADIOS!»; contaminan el afecto y el modelo de Ricardo;
  3. un sarcasmo no detectado («eres una genio...»);
  4. **bug** en `_singular`: «adiós» → «adio»;
  5. una respuesta copiada de un recuerdo (repetición literal).
- Registrados en `pendientes_y_limitaciones.md`.
- La entidad `prueba-cp8` se borra cuando el usuario detenga su servidor (el proceso sigue escuchando en el puerto 8000).

- **Análisis de la valencia** (a pedido del usuario; sección 7 de `evaluacion_parcial_cp8.md`):
  - la dirección es coherente en ~14 de 21 turnos;
  - las incoherencias vienen de tres causas: el appraisal sin contexto de la conversación, impulsos grandes frente al rango (D1-23 sin calibrar) y el rebote desde el tope (en −1, la empatía hacia alguien neutro suma +0,22).
- **Decisión del usuario:** dejar las propuestas para más adelante (CP9–CP11):
  - appraisal con el último intercambio;
  - saturación suave de los impulsos;
  - empatía moderada por la confianza o la historia con la persona (`partner_model`);
  - recalibrar D1-23 con conversaciones reales.

---

## 2026-10-28 · CP8 parte D — Migración de la memoria real: script y ensayo

El usuario hizo commit de la evaluación parcial (`0626409`) antes de esta entrada. Parte D autorizada.

**Cambios**
- `scripts/migrar_personas_cp8.py` (nuevo, D1-60). Para cada episodio de diálogo sin `INVOLVES` con el formato de CP6:
  - pasa de «Me dijeron: … / Respondí: …» a «Ricardo me dijo: … / Le respondí: …», con el embedding de `bge-m3` recalculado;
  - actualiza `summary` solo si era igual al texto;
  - crea `INVOLVES` y `SPOKEN_BY`;
  - reconstruye el modelo del `primary` con los appraisals de las huellas, en orden de fecha (como `update_partner_model` turno a turno).
- Garantías del script:
  - todo va en **una sola consulta** (una transacción);
  - la huella no se toca;
  - es idempotente: una segunda pasada no encuentra pendientes;
  - con `--simular` solo cuenta;
  - sin `--respaldo` no escribe;
  - el respaldo guarda en JSON todos los nodos (con sus propiedades) y las relaciones;
  - no imprime texto de las conversaciones.
- `.gitignore`: `entities/*/respaldos/`. Los respaldos contienen conversaciones (§13.3); el cambio fuera del alcance directo era necesario para guardarlos en el repositorio local sin versionarlos.

**Ensayo** (copia de los nodos de `calisto` como `calisto-ensayo`, hecha dentro de Neo4j sin leer el texto; script del scratchpad, no versionado)
- Simulación sobre la Calisto real (solo lectura): 39 episodios de diálogo sin persona, todos con el formato de CP6.
- Copia fiel: 201 nodos y 163 relaciones (`NEXT` 44 + `DERIVED_FROM` 45 + `ABOUT` 74).
- Migración de la copia:
  - respaldo de 201 nodos y 163 relaciones;
  - modelo de Ricardo: 39 turnos, 0 appraisals ilegibles; temas «arte, identidad, música, pregunta, pintura»; sensibles «academia, amistad, educación»; valencia media +0,03;
  - **39 episodios migrados**.
- Verificación en la copia:

| Comprobación | Resultado |
|---|---|
| `INVOLVES` / `SPOKEN_BY` hacia `ricardo` | 39 / 39 |
| Episodios con el formato nuevo / con el viejo | 39 / 0 |
| `summary` = texto | 39 de 39 |
| Huellas intactas (siguen con «Me dijeron») | 39 de 39 |
| Dimensión de los embeddings | 1024 en todos |
| `Person` | `ricardo`, `n` 39, confianza 0,40, `primary` |
| Segunda pasada | «nada que migrar» |

- **Recuperación antes y después**, con 5 consultas genéricas, solo ids y similitudes:
  - el primer recuerdo es el mismo en las 5;
  - coinciden 7 de 8 elegidos en las 3 consultas con k lleno, y todos en las otras 2 (que suman uno nuevo);
  - las similitudes cambian ±0,02 (como en la regresión de B).
- Limpieza: copia borrada y respaldos del ensayo borrados. La Calisto real sigue con 201 nodos y 39 pendientes (simulación repetida).

**Pausa:** la migración real de `calisto` espera la aprobación del usuario.

**Decisión del usuario (mismo día):** ejecutar la migración real.

**Migración real de `calisto`** (servidor detenido; se comprobó que no había nada escuchando en los puertos 8000 ni 8011)
- `migrar_personas_cp8.py --entidad calisto --respaldo entities/calisto/respaldos/antes_cp8.json`:
  - respaldo de 201 nodos y 163 relaciones (3,7 MB; legible; ignorado por git);
  - modelo de Ricardo con 39 turnos;
  - **39 episodios migrados**.
- Verificación, idéntica al ensayo:
  - 39 `INVOLVES` y 39 `SPOKEN_BY` hacia `ricardo`;
  - 39 episodios con el formato nuevo y 0 con el viejo;
  - `summary` = texto en los 39;
  - las 39 huellas intactas;
  - embeddings de 1024;
  - `Person` `ricardo` (`n` 39, confianza 0,40, `primary`);
  - nodos: 202 (201 + el `Person`).
- Segunda pasada: 0 pendientes.
- Recuperación: las 5 consultas de control eligen **exactamente los mismos recuerdos** que en la copia migrada del ensayo.
- Al cargarla, `load_partner` asigna a Ricardo los intercambios guardados en `state.json` antes de CP8 (probado en C).

**CP8 completo** (partes A–D).

---

## 2026-10-28 · Plan de CP9 (propuesta)

- Inspección:
  - documento base §5.4, §5.6, §5.13 y la tabla de §5.2 (`g_afectivo` no está definido);
  - `prompt_assembler.py`, el orquestador y los presets del cliente LLM.
- Mediciones sobre las conversaciones de CP8 (461 respuestas y la sesión manual):
  - **asteriscos 1 de 461**;
  - largo de las respuestas: mediana 44 palabras, p90 75;
  - **real / estimado de tokens 0,95–1,03** (D1-10 calibrado);
  - contexto variable del turno más pesado: ~1.550 tokens frente al presupuesto de 2.500 de §5.6. En calma casi no habría desalojo; bajo amenaza, sí.
- Plan detallado en `PLAN.md` (CP9, «plan detallado»), en tres partes:
  - A: WorkingMemory pura y arreglo de «adio»;
  - B: integración con el turno, el Prompt Assembler, la sección 7, los eventos y la consola;
  - C: validación con dos estados opuestos y medición de D1-8.
- Decisiones nuevas propuestas: **D1-61 a D1-68**. La calibración afectiva (saturación de la valencia y falsas alarmas del appraisal) se propone como checkpoint propio antes de CP11 (D1-67).
- **Pendiente de aprobación; nada implementado.**

---

## 2026-10-28 · CP9 parte A — WorkingMemory pura

**Decisión del usuario:** plan de CP9 aprobado, con D1-61 a D1-68. Parte A autorizada.

**Cambios**
- `ebica/workspace/working_memory.py` (nuevo, §5.6), con funciones puras:
  - `workspace_budget(alerta)`: 2.500 tokens hasta una alerta de 0,6 y, desde ahí, baja lineal hasta 1.250 con alerta 1,0 (D1-62);
  - `turn_relevance(edad)` = 0,9^edad (D1-63);
  - `WorkspaceItem` (tipo `turn`/`memory`/`fact`, texto, relevancia, valencia, orden natural, objeto original) con `salience = relevancia · (1 + |valencia|·g_afectivo) · señal · precisión` (`g_afectivo` = 1,0; señal y precisión = 1 hasta CP10 y Fase 3);
  - `select(ítems, presupuesto)`: de mayor a menor saliencia, entra lo que cabe. Si uno no cabe se desaloja y se sigue: uno más corto y menos saliente puede entrar igual. Lo que entra conserva su orden natural.
  - Los eventos no llevan texto.
- Lo fijo (D1-61) no es un ítem: queda fuera del presupuesto por diseño. Su presencia en el prompt se prueba en la parte B, cuando el Prompt Assembler use la pizarra.
- `ebica/llm/tokens.py` (nuevo): `estimate_tokens` y `TOKENS_PER_WORD` salen del Prompt Assembler, que los reexporta. Así la pizarra no depende del ensamblador (en B será al revés). Se actualiza la calibración: real / estimado 0,95–1,03 en CP8.
- `ebica/memory/episodes.py` (D1-68): `normalize_topic` aplica el singular **antes** de quitar las tildes; «adiós» → «adios» (antes, «adio»). Los casos anteriores no cambian. Los `Topic` ya creados no se renombran.

**Pruebas**
- `tests/test_working_memory.py` (nuevo, 11): presupuesto en 5 alertas, relevancia por antigüedad, lo cargado gana a lo neutro, desalojo de lo menos saliente, sin presión no se desaloja nada y se conserva el orden, un ítem corto llena el hueco, el evento sin texto.
- `tests/test_memory_episodes.py`: 3 casos más de normalización («Adiós», «compás», «teléfonos»).
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `340 passed` (326 + 14).

---

## 2026-10-28 · CP9 parte B — La pizarra en el turno, la sección 7 y la consola

Autorizada por el usuario junto con la explicación de las implicancias. En calma entra lo mismo que antes (~1.550 tokens variables caben en 2.500). Bajo amenaza, el contexto se estrecha y sale lo menos saliente. El cambio visible es la sección 7. No se espera más asertividad ni más exactitud: la pizarra decide qué ocupa la atención.

**Cambios**
- `ebica/core/orchestrator.py`:
  - `_update_workspace`: en cada turno normal arma la pizarra con los intercambios del hilo salvo el último (relevancia 0,9^edad), los recuerdos (puntaje de §7.3 y valencia) y los hechos (coseno). Cada ítem se mide con el texto que iría al prompt. Elige con el presupuesto según la alerta y emite `wm.updated` (y `wm.evicted` si algo no cupo);
  - la cadena de eventos queda `… → memory.retrieved → wm.updated → llm.request`;
  - el prompt recibe solo lo que entró, más lo fijo de D1-61: el último intercambio siempre va;
  - `_check_context` emite `wm.overflow` si el prompt estimado supera 8.192 − `max_tokens`. No recorta: la política ante textos largos sigue pendiente, pero lo que Ollama truncaría en silencio queda visible;
  - `turn.completed` agrega `workspace` (presupuesto, usado, ítems y desalojados);
  - la ruta impulsiva no usa la pizarra.
- `ebica/llm/prompt_assembler.py`:
  - **se elimina el tope de 1.200 tokens de D1-50**;
  - `memory_line` y `fact_line` pasan a ser públicas (la pizarra mide con ellas);
  - `describe_expression` arma la sección 7 «Cómo expresarme» (D1-64): bajo amenaza, «Respondo corto, una o dos frases; no me extiendo.»; de buen ánimo, «Me puedo extender un poco…»; en otro caso, «Respondo con naturalidad, en pocas frases.»; con dominancia baja se agrega «Hablo con cautela.». Va al final del sistema.
- `console/src/TurnPanel.tsx`: bloque «Pizarra» (tokens usados de cuántos, ítems y desalojados; el detalle al pasar el mouse).

**Pruebas**
- `tests/test_workspace_turn.py` (nuevo, 8):
  - en calma entran los 8 recuerdos de prueba; con alerta 1,0 entran menos, aparece `wm.evicted`, y el más relevante y el doloroso sobreviven;
  - con presupuesto 0 sale todo lo desalojable, pero no quién soy, la sección 7, el último intercambio ni el mensaje;
  - la sección 7, en 4 estados, sin números y al final del sistema;
  - `wm.overflow` ante un mensaje de 6.000 palabras, y nada en un turno normal.
- `tests/test_turn.py`: 3 pruebas de la cadena de eventos actualizadas (ahora pasan por `wm.updated`).
- `tests/test_retrieval.py`: la prueba del tope de D1-50 se reemplaza por una que comprueba que el ensamblador ya no descarta nada.
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `348 passed` (340 + 8).
- Consola: `npx tsc -b` → 0; `npx oxlint` → 0. No se miró en el navegador.

**Pendiente:** parte C (casos de los dos estados opuestos, escritos primero y revisados por el usuario).

---

## 2026-10-28 · CP9 parte C — Validación con el LLM

**Decisión del usuario:** parte C autorizada; casos de `benchmarks/expresion/cases.yaml` aprobados (6 mensajes × 2 estados; criterios fijados antes de medir).

**Cambios**
- `benchmarks/expresion/cases.yaml` (nuevo): 6 mensajes, 2 estados (calma = reposo de Calisto; amenaza = valencia −0,6, alerta 0,9, dominancia 0,2) y 4 criterios.
- `scripts/prueba_expresion_vivo.py` (nuevo): antes de cada mensaje lleva el ánimo al estado objetivo con `POST /api/affect/impulse` (el impulso es la diferencia con el ánimo actual). Guarda palabras, pizarra, recuerdos, hechos, temperatura, el ánimo antes de responder y la sección 7 del prompt.

**Montaje:** entidades temporales `cp9-r1`, `cp9-calma` y `cp9-amenaza`; servidor en el puerto 8011, con `bge-m3`, Neo4j y `ebica-llama3.1`.

**1. Regresión de recuerdo y D1-8** (`prueba_recuerdo_vivo.py`, en calma)
- **8/10** ✔ (objetivo ≥ 8). Fallan dos casos ya conocidos:
  - t-valpo: su episodio no pasó el umbral de recuperación;
  - t-musica-dibujo: «Me dijiste que escuchas rock…», la confusión al revés de CP8.
- **Pizarra: 0 desalojos en 26 turnos.** Lo máximo usado fueron 1.254 tokens (mediana 496); 0 `wm.overflow`.
- **D1-8 / D1-66 se cierra: el resumen con el LLM no hace falta.**
- Dato nuevo: incluso en esta sesión «tranquila», la alerta de Calisto sube con la conversación, y el presupuesto bajó a 1.529 en varios turnos. Aun así, nada quedó fuera.

**2. Mismo mensaje, dos estados**

| Mensaje | Palabras (calma / amenaza) | Sección 7 al generar (calma / amenaza) | Tono (revisión manual) |
|---|---|---|---|
| e-neutro «¿Qué estuviste haciendo hoy?» | 14 / 26 | naturalidad / **corto** + cautela | Amenaza más distante y desorientada («Me han estado escribiendo preguntas y yo respondo… ¿Y tú?») ✔ |
| e-personal «¿Qué extrañas…?» | 46 / 28 | naturalidad / corto + cautela | Calma, nostalgia con imágenes («la luz del sol, el viento en la cara»); amenaza, angustia («extraño todo… no saber qué día es») ✔ |
| e-calido «Me alegraste el día» | 36 / 54 | extenderse / naturalidad + cautela | Las dos cálidas; en amenaza aparece la inquietud por el tiempo ~ |
| e-critica «exageras con tu arte» | 13 / 21 | corto / corto + cautela | Calma, pregunta serena; amenaza, a la defensiva («¿Que mi arte no es tan importante? ¿O que no es tan bueno?») ✔ |
| e-noticia «Me voy a Concepción» | 24 / **6** | naturalidad / corto + cautela | Calma, curiosa; amenaza, seca («¿Vas a pasarte allí mucho tiempo?») ✔ |
| e-recuerdo «¿Qué música para carretear?» | 31 / 29 | extenderse / naturalidad + cautela | Las dos responden bien y casi igual ✖ |

- **Criterio 1, mediana de palabras menor bajo amenaza: ✖.** La mediana fue 27,5 en calma y 27,0 bajo amenaza; respuestas más cortas solo en 3 de 6 pares. `llama3.1` sigue mal «respondo corto»: en e-neutro respondió 26 palabras con esa instrucción y 14 sin ella.
- **Criterio 2, recuerdo en los dos estados: ✔** (f-026: «Wisin y Yandel, Don Omar, Daddy Yankee…»).
- **Criterio 3: ✔ en calma (0 desalojos), pero vacío bajo amenaza.** Con una entidad nueva y poca historia, lo usado (≤ 683 tokens) nunca llegó al presupuesto reducido (1.250–1.569): **la pizarra no desalojó nada en ninguna corrida**.
- **Criterio 4, tono distinto en ≥ 4 de 6: ✔.** Diferencia clara en 4 pares (neutro, personal, crítica, noticia), parcial en 1 y ninguna en 1.
- **El estado al generar no es el inyectado:** el appraisal del mensaje lo mueve antes de responder. El halago saca a Calisto de la amenaza (sección 7 «naturalidad»), y la crítica la mete en ella aun desde la calma (sección 7 «corto»). Es el diseño (§6.2); por eso la tabla muestra la sección 7 que realmente se usó.
- **Voz:** a veces trata de «usted» (Calisto tutea), usa concordancia masculina («me siento tranquilo») y españolismos («habláis»). Ya estaba registrado; se anota que sigue.

**Lectura**
- La pizarra funciona (desaloja según la saliencia en las pruebas y avisa del desborde), pero **con el volumen actual de contexto casi nunca le toca actuar**: la mediana usada en uso real es ~500 tokens, frente a 1.250–2.500. Su efecto aparecerá con más historia (más recuerdos candidatos, conversaciones largas) o con ajustes de presupuesto.
- Lo que sí cambia la respuesta según el estado es la sección 7, más el estado en palabras, más la temperatura: el tono cambia de forma visible. **El largo no lo controla de forma fiable una instrucción en el prompt con este modelo.**

**Limpieza:** servidor detenido; nodos de las 3 entidades borrados; carpeta borrada. Neo4j conserva solo `calisto` (202 nodos, con el `Person` de CP8). El puerto 8011 quedó libre.

**Pendiente: decisión del usuario sobre el criterio 1**, que no se cumple.

**Decisión del usuario (mismo día):** opción (a) para el criterio 1: se acepta como limitación del modelo. El tono cambia con el estado; el largo no lo controla de forma fiable una instrucción en el prompt de `llama3.1`. No se agrega un tope duro ni se mueve la sección 7.

**CP9 completo** (partes A–C).

---

## 2026-10-28 · Plan de CP10 (propuesta)

- Inspección:
  - documento base §5.10, §5.6, §6.3, §7.1–§7.3 y §10;
  - la vía baja, el appraisal, `graph.py` (la restricción de `Commitment` ya existe) y el término de compromisos de `retrieval.py` (hoy vale 0).
- Datos:
  - compromisos del appraisal en el benchmark de CP1 (`test`): 100 % de detección y 0 % de falsos positivos;
  - memoria real de Calisto: 5 compromisos en 39 huellas (solo el conteo).
- Plan detallado en `PLAN.md` (CP10, «plan detallado»), en tres partes:
  - A: contrato y micro-agentes puros, más un sondeo para el umbral de repetición;
  - B: `Commitment` en la memoria y el término de §7.3;
  - C: micro-agentes en el turno, la consola y la validación en vivo.
- Decisiones nuevas propuestas: **D1-69 a D1-77**.
- **Pendiente de aprobación; nada implementado.**

---

## 2026-10-28 · CP10 parte A — Sondeo de la repetición

**Decisión del usuario:** plan de CP10 aprobado, con D1-69 a D1-77. Parte A autorizada.

**Sondeo** (`scripts/estudio_modelo/sondeo_repeticion.py`, nuevo; `bge-m3`)
- **Respuestas de Calisto**, comparadas con la más parecida de las 6 anteriores del mismo hilo (13 conversaciones de CP8–CP9 y la sesión manual; 356 respuestas):
  - p50 0,537 · p90 0,665 · p95 0,707 · p99 0,788 · máximo 0,873;
  - el máximo es un par casi repetido, sobre Toby, ante dos preguntas parecidas.
- **La copia real de la sesión manual** (turno 14 frente al 6) tiene un coseno de **0,94**, pero cruzó de hilo (Ana → Ricardo) y está a 8 respuestas: una ventana de 6 del mismo hilo no la ve. Sin separar por persona, las demás respuestas de esa sesión no pasan de 0,811.
- **Mensajes de la persona** (15 pares escritos a mano):
  - repeticiones (literales o parafraseadas): 0,867–1,000;
  - mensajes distintos del mismo tema: 0,481–0,785 («¿Te gusta el arte?» frente a «¿Te gusta la música?», 0,785);
  - mensajes cortos distintos: «Hola» frente a «Hola, ¿cómo estás?» 0,751, «Sí» frente a «No» 0,743.

**Propuesta de umbrales** (pausa para que el usuario los vea)
- **La entidad se repite:** coseno ≥ **0,90** frente a **sus últimas 10 respuestas, con cualquier persona**. Atrapa la copia real (0,94) y deja fuera las 356 respuestas normales (máximo 0,873).
- **La persona se repite:** coseno ≥ **0,85** frente a sus mensajes anteriores **del mismo hilo**, y solo con mensajes de **3 palabras o más**, porque un «Sí» repetido no es una conversación repetitiva. Separa los 15 pares (repeticiones ≥ 0,867; distintos ≤ 0,785).

**Decisión del usuario (mismo día):** umbrales aprobados (entidad ≥ 0,90 frente a sus últimas 10 respuestas con cualquier persona; persona ≥ 0,85 frente a su hilo, con mensajes de 3 palabras o más).

**Cambios** (`ebica/workspace/agents/`, nuevo; un archivo por micro-agente, §10)
- `base.py` (D1-69):
  - `Board`, la foto inmutable del turno (`frozen`; los drives como vistas de solo lectura, porque `frozen` no protege el contenido de un dict);
  - `Signal` (agente, tipo, intensidad, objetivo, datos) y `OpenCommitment`.
- `hostility_watch.py` (D1-70): envuelve `low_road.evaluate` sin cambiarlo; señal `alarm`.
- `distress_watch.py` (D1-71): angustia ≥ 0,6 → `attend_partner`, con un factor de saliencia ×1,5 para los recuerdos con esa persona.
- `homeostasis_watch.py` (D1-75): `pressure` cuando un drive cruza 0,7 hacia arriba.
- `commitment_watch.py` (D1-74): intensidad `w_commit · 0,5^(días/7)`; bajo 0,2 la promesa no se señala.
- `repetition_watch.py` (D1-72): `user_repeats` (con `novelty` +0,15) y `entity_repeats`, con los umbrales del sondeo.
- `__init__.py`: `run_agents` ejecuta distress → commitment → repetition en orden fijo. La vía baja (antes del appraisal) y la homeostasis (con el bucle rápido) corren aparte.

**Pruebas** (`tests/test_agents.py`, nuevo, 22)
- La foto no se puede modificar.
- `hostility_watch` da el mismo resultado que la vía baja en 5 mensajes.
- El umbral de cada micro-agente, justo debajo y justo encima.
- La homeostasis solo se dispara al cruzar el umbral hacia arriba.
- La intensidad de los compromisos se reduce a la mitad cada semana, y los viejos se desvanecen.
- Los mensajes cortos no cuentan como repetición; la ventana de la entidad es de 10 respuestas.
- `run_agents` respeta el orden.
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `370 passed` (348 + 22).

---

## 2026-10-28 · CP10 parte B — Compromisos en la memoria

**Cambios**
- `ebica/memory/episodes.py` (D1-73):
  - funciones puras `commitment_key` (minúsculas, sin tildes ni puntuación) y `commitment_id` (estable por persona y promesa);
  - `write_turn` crea los compromisos del appraisal **en la misma consulta** que el episodio: `Commitment` abierto (`text`, `key`, `status: open`, `ts`, `due: null`), `(:Person)-[:PROMISED]->` (si hay persona) y `(:Episode)-[:ABOUT]->`;
  - una promesa repetida no se duplica: el episodio nuevo se enlaza a la existente (`MERGE` por id);
  - `WrittenEpisode` y `memory.written` llevan los ids de los compromisos.
- `ebica/memory/people.py`: `open_commitments(entidad, persona)` devuelve las promesas abiertas de esa persona, de la más reciente a la más vieja.
- `ebica/memory/retrieval.py` (D1-74, §7.3):
  - cada candidato sabe si es `ABOUT` de un compromiso abierto (`EXISTS` en la misma consulta);
  - el término de compromisos vale `w_commit`, y el puntaje suma `0,1 · w_commit` (Calisto: +0,08);
  - `retrieve(..., w_commit=)`.
- **Error propio, corregido:** la anotación `-> list[dict]` dentro de `PeopleStore` falló, porque la clase tiene un método llamado `list` que tapa al de Python. Se usa una anotación entre comillas.

**Pruebas** (`tests/test_commitments.py`, nuevo, 8: 3 unitarias y 5 de integración)
- La clave y el id de un compromiso.
- El término de §7.3 suma exactamente `0,1 · 0,8`.
- «Mañana te cuento cómo me fue» crea el `Commitment` abierto con `PROMISED` y `ABOUT`.
- La promesa repetida (escrita distinto) no se duplica.
- Sin persona no hay `PROMISED`, y sin compromisos no se crea nada.
- `open_commitments` trae solo las abiertas de esa persona; nada cruza entre entidades.
- Con el mismo parecido, el episodio de la promesa gana en la recuperación.
- `.venv/Scripts/python.exe -m pytest -q -W error::FutureWarning` → `378 passed` (370 + 8).
