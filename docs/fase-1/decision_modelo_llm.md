# Fase 1 — Decisión del modelo LLM

> **Estado (2026-10-25): en curso**, en la rama `f1-test-abliterated`. Se va a evaluar
> **Hermes 3 *lorablated*** (pendiente de descarga, aprobada en principio por el
> usuario). Con los resultados, el usuario decide entre ese modelo y el `llama3.1`
> actual (no abliterado). Después se retoma **CP5 parte B** del `PLAN.md`.
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

## 5. Candidato 2: Hermes 3 *lorablated* (pendiente)

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

## 6. Comparación (a completar)

| Medición | `ebica-llama3.1` | `ebica-llama3.1-abl` | Hermes 3 *lorablated* |
|---|---|---|---|
| Rechazos de asistente | 9/45 | 0/45 | — |
| Acotaciones | 0/45 | 8/45 | — |
| Formas no chilenas | 4/45 | 18/45 | — |
| Masculino propio | 0/45 | 4/45 | — |
| Exclamaciones / palabras | 0,5 / 77 | 7,4 / 129 | — |
| Appraisal: veredicto | aceptable c/ mitig. | aceptable c/ mitig. | — |
| · Confusión angustia → hostilidad | 0 % | 25 % | — |
| · t08 «weón» / t09 mixto | ✔ / ✖ | ✖ / ✔ | — |
| Recuerdo (sin / con estado) | 70–78 % | 70–78 % | — |

---

## 7. Modelos instalados en Ollama

| Modelo | Tamaño | Uso |
|---|---|---|
| `ebica-llama3.1` | 4,9 GB | **El modelo en uso** (`EBICA_LLM_MODEL` en `.env`). |
| `ebica-llama3.1-abl` / `hf.co/mlabonne/Meta-Llama-3.1-8B-Instruct-abliterated-GGUF:Q4_K_M` | 4,9 GB (las capas se comparten) | Candidato 1, descartado salvo que no haya otra opción. Pendiente: decidir si se borra. |
| `llama3`, `mistral`, `llama3.1` | — | Instalados antes del proyecto. `llama3.1` es la base de `ebica-llama3.1`. |

**Para probar un modelo a mano** sin tocar `.env` (PowerShell, en la terminal del
backend): `$env:EBICA_LLM_MODEL = "<modelo>"; .venv\Scripts\python -m ebica.api`.
Para comprobar qué modelo responde: el campo `model` de cualquier `llm.request` en
la consola, o `ollama ps`.
