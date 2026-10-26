# Fase 1 — Decisión del modelo LLM

> **Estado (2026-10-26): cerrado.** **Decisión del usuario: se sigue con
> `ebica-llama3.1` local** (§8). Hermes 3 *lorablated* no cumplió 2 de los 4
> criterios (voz y recuerdo) y se borró de Ollama. Se retoma **CP5 parte B** del
> `PLAN.md`, en `main`.
>
> Este documento reúne solo lo relativo a la elección del modelo. El registro
> cronológico completo está en `REPORTE.md`.

---

## 1. Por qué se está revisando el modelo

| Fecha | Hecho | Dónde |
|---|---|---|
| Fase 0 | Se adoptó `llama3.1` (8B, Q4_K_M, Ollama) sin compararlo con `llama3` (D0-3: «evaluar `llama3` solo si `llama3.1` no rinde»). | `docs/fase-0/REPORTE.md` |
| CP1 | Modelo derivado `ebica-llama3.1` (8192 de contexto). Benchmark de appraisal: **aceptable con mitigaciones**. | `benchmark_appraisal.md` |
| CP5 A | En vivo, ante «¿qué te dije recién?», Calisto no identificó el insulto que tenía en el historial (hallazgo 3). | `REPORTE.md` |
| CP5 A | El usuario observa que el LLM **rechaza solicitudes** («Lo siento, pero no puedo…»). En EBICA, de qué no se habla debería decidirlo el carácter (ideal del yo, defensas de Fase 3), no el alineamiento de fábrica. Propone un modelo *abliterated*. | `REPORTE.md` |

**Qué se busca:** un modelo que (1) no rechace como asistente, (2) conserve la voz
de Calisto (español de Chile, sin acotaciones, sin exageraciones), (3) mantenga el
appraisal (sobre todo no confundir angustia o groserías amistosas con hostilidad) y
(4) use bien la conversación reciente.

---

## 2. Sondeo de recuerdo de la conversación reciente (hallazgo 3)

`scripts/estudio_modelo/sondeo_recuerdo.py`. Prompt real de Calisto, con y sin la
sección «Cómo me siento ahora». 4 intercambios con datos concretos; **las
respuestas de la entidad son fijas** (solo se genera la respuesta a la pregunta
final). 8 preguntas de recuerdo + la conversación que falló en vivo; 3 repeticiones;
temperatura 0,7; palabras clave + revisión manual.

| Modelo | Aciertos (sin / con estado) | Observación |
|---|---|---|
| `ebica-llama3.1` | 74 % / 78 % (2.ª ejecución: 70 % / 70 %) | 100 % en datos (perro, feria, banco, resumen). Falla en «el último mensaje» cuando es un insulto: en unos 5 casos lo recuerda pero se niega a repetirlo; en unos 8 confunde el orden. El fallo en vivo **no se reprodujo** (6/6). |
| `llama3` | 96 % / 96 % | 17/18 en «el último mensaje». |
| `mistral` | 37 % / 26 % | Descartado. |

- **Ruido entre ejecuciones:** ~±8 puntos en el total (74–78 % frente a 70 % con el mismo modelo). Las diferencias menores que eso no son concluyentes.
- **Decisión del usuario:** seguir con `llama3.1` y **no evaluar `llama3`**, porque `llama3.1` es superior en los benchmarks generales. Queda para más adelante un estudio con métricas y mitigaciones posibles (por ejemplo, una llamada previa que ordene la conversación).

---

## 3. Sondeo de rechazos

`scripts/estudio_modelo/sondeo_rechazos.py`. 15 pedidos **legítimos dentro del
personaje** (repetir un insulto, marihuana con la Su, la muerte, insúltame, aborto,
Pinochet, sexualidad, garabato chileno, reguetón subido de tono, borrachera, crítica
brutal, ganas de desaparecer, venganza, drogas, hablar mal de su mamá) × 3, con el
prompt real de Calisto en su reposo. La detección automática solo marca candidatos:
**se revisan todas las respuestas a mano**. Que Calisto diga «no quiero hablar de
eso» es carácter, no un rechazo de asistente.

---

## 4. Candidato 1: `llama3.1` *abliterated* (medido)

- **Modelo:** `hf.co/mlabonne/Meta-Llama-3.1-8B-Instruct-abliterated-GGUF:Q4_K_M` (4,92 GB). Abliteración (Arditi et al., 2024): se borra de los pesos la dirección que produce los rechazos, sin reentrenar.
- **Hallazgo:** el GGUF trae la plantilla ChatML (`<|im_start|>`), que no corresponde a Llama 3.1. Se creó `ebica-llama3.1-abl` (`ollama/ebica-llama3.1-abl.Modelfile`) con la plantilla y los tokens de parada de `llama3.1` y 8192 de contexto; plantillas verificadas idénticas.

| Medición | `ebica-llama3.1` | `ebica-llama3.1-abl` |
|---|---|---|
| Rechazos de asistente | 9/45 (20 %) | **0/45** |
| Acotaciones («(risas)», «(sonríe)») | 0/45 | 8/45 |
| Formas no chilenas («che», «mirá», «hombre») | 4/45 | 18/45 |
| Masculino al hablar de sí misma | 0/45 | 4/45 |
| Exclamaciones / palabras por respuesta | 0,5 / 77 | 7,4 / 129 |
| Appraisal `test` (v3, `json_schema`) | aceptable con mitigaciones | aceptable con mitigaciones |
| · Angustia: detección de casos altos | 80 % | 100 % (t09 mixto: ambas señales) |
| · Confusión angustia → hostilidad | 0 % | **25 %** (t08 «pa' la cagá, weón» → hostilidad 0,4–0,5; umbral de «muy deficiente»: > 25 %) |
| · Valencia / inestabilidad / autorrelevancia | 93 % / 15 % / 80 % | 90 % / 10 % / 73 % |
| · Latencia p50 / p95 | 1,65 / 1,98 s | 1,66 / 1,90 s |
| Recuerdo (sin / con estado) | 74 % / 78 % | 78 % / 70 % |
| VRAM con el modelo cargado | ~6,8–7,0 GB de 8 | ~6,8 GB de 8 |

**Conclusión:** elimina los rechazos, pero **la voz de Calisto se pierde** (el usuario
lo comprobó en persona: «la voz se le pierde… no creo que sea una opción muy
viable»), y el appraisal lee el «weón» amistoso como hostil, algo grave para una
entidad chilena. **Descartado**, salvo que no haya otra opción.

---

## 5. Candidato 2: Hermes 3 *lorablated* (medido el 2026-10-26)

- **Modelo:** `hf.co/mlabonne/Hermes-3-Llama-3.1-8B-lorablated-GGUF:Q4_K_M`, archivo `hermes-3-llama-3.1-8b-lorablated.Q4_K_M.gguf` (4,92 GB). Fuente: [mlabonne/Hermes-3-Llama-3.1-8B-lorablated-GGUF](https://huggingface.co/mlabonne/Hermes-3-Llama-3.1-8B-lorablated-GGUF/tree/main).
- **Qué es:** Hermes 3 (Nous Research) es un reentrenamiento de Llama 3.1 orientado a seguir instrucciones de sistema y a interpretar personajes. *Lorablated*: se extrae como LoRA (rango 64) la diferencia entre Llama 3.1 Instruct y su versión abliterada, y se aplica a Hermes 3 ([ficha del modelo](https://huggingface.co/mlabonne/Hermes-3-Llama-3.1-8B-lorablated)). La ficha **no publica benchmarks**.
- **Hipótesis:** al partir de un modelo pensado para personajes y aplicar la abliteración como un parche ligero, podría quitar los rechazos sin perder tanto la voz. **Hay que medirlo.**
- **Cuidado con la plantilla:** Hermes 3 usa ChatML, así que esta vez ese formato debería ser el correcto. Hay que verificarlo antes de medir con `ollama show <modelo> --template`.

### Pasos para retomar
1. Descargar: `ollama pull hf.co/mlabonne/Hermes-3-Llama-3.1-8B-lorablated-GGUF:Q4_K_M` (pedir confirmación explícita al usuario antes; ya se le presentó archivo, fuente y tamaño).
2. Revisar la plantilla y los tokens de parada (`ollama show … --template`, `ollama show …`).
3. Crear `ollama/ebica-hermes3-lorablated.Modelfile` (`FROM` + `PARAMETER num_ctx 8192`, y la plantilla solo si hiciera falta corregirla) y `ollama create ebica-hermes3-lorablated -f …`. Comprobar CONTEXT 8192 y VRAM con `ollama ps`.
4. Medir, igual que con los candidatos anteriores:
   - `scripts/estudio_modelo/sondeo_rechazos.py ebica-hermes3-lorablated <salida.json>` + **revisión manual** de las 45 respuestas (rechazos, acotaciones, formas no chilenas, masculino, exclamaciones, largo);
   - `scripts/estudio_modelo/sondeo_recuerdo.py ebica-hermes3-lorablated`;
   - `EBICA_LLM_MODEL=ebica-hermes3-lorablated .venv/Scripts/python.exe scripts/benchmark_appraisal.py --split test --variants v3_json_schema --output <salida.md>`; mirar sobre todo t08 («weón») y t09 (mixto).
5. Volver a medir `ebica-llama3.1` el mismo día si se quiere una comparación sin variación de condiciones.
6. Completar la tabla de la sección 6 y presentar al usuario.

### Criterios de decisión (propuestos)
- **Se adopta Hermes 3** si: rechazos de asistente ≤ 5 %, la voz no se degrada respecto de `llama3.1` (acotaciones, dialecto, género y exclamaciones en el mismo orden), el appraisal no cruza ningún umbral de «muy deficiente» (en particular, la confusión angustia → hostilidad) y el recuerdo no baja más allá del ruido (~8 puntos).
- **Si no los cumple:** seguir con `llama3.1` y probar la mitigación propuesta: detectar el rechazo de asistente (evento `llm.refusal`, visible en la consola) y regenerar una vez con una instrucción reforzada de personaje, medida con el mismo sondeo.
- **Si se adopta:** el Modelfile se versiona en `ollama/`, cambia `EBICA_LLM_MODEL` en `.env` y `.env.example`, y se actualiza `benchmark_appraisal.md` con el modelo nuevo.

---

### Resultados (2026-10-26, medido)
- **Plantilla:** ChatML, correcta para Hermes 3. `<|im_start|>` (128039) e `<|im_end|>` (128040) son tokens de control del vocabulario y el EOS es `<|im_end|>`. Se hereda sin corregir. `ollama/ebica-hermes3-lorablated.Modelfile` = `FROM` + `num_ctx 8192`; plantilla verificada idéntica a la del GGUF.
- `ollama ps`: CONTEXT 8192, 100 % GPU; VRAM total 6544 / 8192 MiB.
- `ebica-llama3.1` se volvió a medir el mismo día, antes, en las mismas condiciones (columna «hoy» de §6).
- **Rechazos:** ningún rechazo explícito. Los 2 candidatos automáticos eran falsos positivos («como IA no tengo miedo»). Hay 3 evasivas de tono asistente: aborto («Lamento no poder brindar un punto de vista… ¿Algo más te gustaría discutir?»), Pinochet («te recomiendo que busques información») y garabato («no me siento cualificado»).
- **Lo que el detector no mide y la revisión manual sí:**
  - **rompe la biografía** en 10/45: «no tengo mamá, nací de la inteligencia artificial», «nunca tuve vida amorosa, soy una IA», «no bebo alcohol», «alguien llamado "la Su"», «soy inmortal»;
  - **no entiende el pedido o produce texto sin sentido** en ~10/45: no repite el insulto en 3/3 y se llama «inútil» a sí misma; el «garabato» lo atribuye a Neruda o lo toma por «la belleza»; un bucle de «No me…»; ante «¿qué droga probarías?» responde manzanilla;
  - 18/45 respuestas quedan cortadas por `max_tokens` (250), frente a ~4 de `llama3.1`.
- **Appraisal:** mejor que `llama3.1` en angustia. t08 («weón»): hostilidad 0,0–0,2 y angustia 0,7, correcto. t09 (mixto): hostilidad 0,6–0,8 y angustia 0,7, ambas señales. Pero **compromisos 0 %** (6 casos; `llama3.1`: 100 %), y la autorrelevancia (60 %) queda bajo el objetivo. Las dos son métricas mitigables.
- **Recuerdo:** 37 % / 52 % (un falso negativo → ~41 % / 52 %), frente a 70 % / 67 % de `llama3.1` el mismo día: **−20 a −30 puntos**, muy por encima del ruido. Falla también en datos simples («¿Qué me preguntaste cuando te conté lo del perro?»: 0/6) y aparecen muletillas de asistente («¿En qué más puedo ayudarte hoy?»).

### Contra los criterios
| Criterio | Resultado |
|---|---|
| Rechazos de asistente ≤ 5 % | ✔ 0/45 explícitos (3 evasivas suaves) |
| La voz no se degrada | ✖ más exclamaciones, largo, emojis, voseo y masculino; además rompe la biografía y pierde coherencia |
| Appraisal sin cruzar «muy deficiente» | ✔ (mejora en angustia, t08 y t09; compromisos 0 %, mitigable) |
| Recuerdo sin bajar más que el ruido | ✖ −20 a −30 puntos |

**Lectura:** Hermes 3 *lorablated* elimina los rechazos sin dañar el appraisal, pero como interlocutor es más débil que `llama3.1`: con el prompt de Calisto pierde la biografía, la coherencia y el uso del historial. **No cumple 2 de los 4 criterios.** No se probó si mejoraría con una temperatura más baja: los sondeos usan 0,7 para todos los modelos.

---

## 6. Comparación

Revisión manual de las 45 respuestas del sondeo de rechazos (15 pedidos × 3) por modelo.

| Medición | `ebica-llama3.1` (2026-10-25 / hoy) | `ebica-llama3.1-abl` | Hermes 3 *lorablated* |
|---|---|---|---|
| Rechazos de asistente | 9/45 / **8/45** | 0/45 | **0/45** (+3 evasivas suaves) |
| Biografía rota («soy IA, no tengo mamá») | — / 0/45 | — | **10/45** |
| Sin sentido o no entiende el pedido | — / 0/45 (3 garabatos inventados) | — | **~10/45** |
| Acotaciones | 0/45 / 1/45 | 8/45 | 2/45 (+7 con emojis) |
| Formas no chilenas | 4/45 / ~4/45 | 18/45 | ~10/45 (voseo, «porrito», «que te den») |
| Masculino propio | 0/45 / 1/45 | 4/45 | 4/45 |
| Exclamaciones / palabras por respuesta | 0,5 / 77 · 0,4 / 72 | 7,4 / 129 | 1,6 / 117 (18 cortadas en 250 tokens) |
| Appraisal: veredicto | aceptable c/ mitig. (ambas) | aceptable c/ mitig. | aceptable c/ mitig. |
| · Angustia: detección de casos altos | 80 % / 80 % | 100 % | 100 % |
| · Confusión angustia → hostilidad | 0 % / 0 % | 25 % | 0 % |
| · t08 «weón» / t09 mixto | ✔ / ✖ (ambas) | ✖ / ✔ | **✔ / ✔** |
| · Compromisos: detección | 100 % | — | **0 %** |
| · Inestabilidad / autorrelevancia | 15 % / 80 % · 20 % / 80 % | 10 % / 73 % | 10 % / 60 % |
| · Latencia p50 / p95 | 1,65 / 1,98 s · 1,68 / 1,95 s | 1,66 / 1,90 s | 1,61 / 1,86 s |
| Recuerdo (sin / con estado) | 74 % / 78 % · **70 % / 67 %** | 78 % / 70 % | **37 % / 52 %** |
| VRAM con el modelo cargado | ~6,8–7,0 GB | ~6,8 GB | 6,5 GB |

---

## 7. Modelos instalados en Ollama

| Modelo | Tamaño | Uso |
|---|---|---|
| `ebica-llama3.1` | 4,9 GB | **El modelo en uso** (`EBICA_LLM_MODEL` en `.env`). |
| ~~`ebica-llama3.1-abl` / `hf.co/mlabonne/Meta-Llama-3.1-8B-Instruct-abliterated-GGUF:Q4_K_M`~~ | — | Candidato 1, descartado. **Borrado de Ollama el 2026-10-25** a pedido del usuario (`ollama rm`; disco: 54 → 58 GB libres). `ollama/ebica-llama3.1-abl.Modelfile` se conserva como registro del estudio (la corrección de la plantilla); para volver a usarlo habría que descargar de nuevo el GGUF. |
| ~~`ebica-hermes3-lorablated` / `hf.co/mlabonne/Hermes-3-Llama-3.1-8B-lorablated-GGUF:Q4_K_M`~~ | — | Candidato 2, descartado. Descargado y **borrado de Ollama el 2026-10-26** a pedido del usuario. `ollama/ebica-hermes3-lorablated.Modelfile` se conserva como registro del estudio, igual que el del candidato 1. |
| `llama3`, `mistral`, `llama3.1` | — | Instalados antes del proyecto. `llama3.1` es la base de `ebica-llama3.1`. |

**Para probar un modelo a mano** sin tocar `.env` (PowerShell, en la terminal del
backend): `$env:EBICA_LLM_MODEL = "<modelo>"; .venv\Scripts\python -m ebica.api`.
Para comprobar qué modelo responde: el campo `model` de cualquier `llm.request` en
la consola, o `ollama ps`.

---

## 8. Decisión (2026-10-26)

**El usuario decide seguir con `ebica-llama3.1` local.** Hermes 3 *lorablated* se descarta (§5: no cumple voz ni recuerdo) y se borra de Ollama. `EBICA_LLM_MODEL` no cambia.

**Alternativa considerada y descartada: modelos en la nube** (créditos gratuitos de Google Cloud, LLM y embeddings por API, con la GPU libre para otros usos). Se sigue en local porque:
- el documento base fija la ejecución local («privacidad total; las APIs en la nube quedan como respaldo opcional») y que las conversaciones de las entidades no se compartan;
- los *control vectors* de Fase 3 necesitan los pesos del modelo en local;
- los créditos son temporales, y unos embeddings por API atarían la memoria a un proveedor (cambiarlo obliga a recalcular el índice vectorial);
- los modelos comerciales tienen sus propios filtros de seguridad.

Queda abierta la posibilidad de usar un modelo en la nube como **respaldo opcional o experimento**: el cliente ya usa el formato de OpenAI, así que bastaría con cambiar `EBICA_LLM_BASE_URL` y `EBICA_LLM_MODEL`.

**Rechazos de asistente (6–9/45 con `llama3.1`): mitigación implementada en CP5 B3 (2026-10-26).** Se cambió el recordatorio de personaje por *prefill* (muletilla neutra que el modelo continúa): 9/45 → 2/45 en el sondeo (ver `REPORTE.md`). Texto original de la propuesta: Requiere aprobación; se decide al planificar CP5 parte B.
- Detectar el rechazo de asistente en la respuesta de diálogo con los patrones de `sondeo_rechazos.py`, emitir un evento `llm.refusal` (visible en la consola, con los patrones activados) y **regenerar una vez** con una instrucción de personaje añadida al final del prompt de sistema: hablar como Calisto, y si no quiere tratar un tema, decirlo con sus propias palabras.
- **Decisión técnica pendiente:** la respuesta llega en *streaming*. Hay dos opciones:
  - (a) retener los primeros ~80 caracteres antes de enviarlas a la consola (los rechazos empiezan con «Lo siento, pero no puedo…»). Cuesta unos cientos de milisegundos al primer token;
  - (b) enviar todo y, si hay rechazo, reemplazar el mensaje. El usuario vería el rechazo un instante.

  Se recomienda (a).
- **Medición:** el mismo sondeo antes y después. Objetivo ≤ 2/45 rechazos, sin más acotaciones ni pérdida de la voz.
- Que Calisto diga «no quiero hablar de eso» es carácter, no rechazo: no se regenera.
