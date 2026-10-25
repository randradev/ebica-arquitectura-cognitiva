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
