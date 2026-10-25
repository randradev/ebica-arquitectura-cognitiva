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
