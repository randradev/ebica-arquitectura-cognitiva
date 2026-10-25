# Benchmark de appraisal

Fecha: 2026-10-24 22:33 · Modelo: `ebica-llama3.1` · Conjunto: `test` (20 casos × 3 repeticiones) · Prompt actual: `v3`

Generado por `scripts/benchmark_appraisal.py`. Umbrales: PLAN Fase 1, D1-1.

## Métricas

| Métrica | Objetivo | Muy deficiente | `v0_json_object` | `v3_json_object` | `v3_json_schema` |
|---|---|---|---|---|---|
| JSON válido y conforme al esquema | ≥ 98% | < 90% | 100% ✔ (n=60) | 100% ✔ (n=60) | 100% ✔ (n=60) |
| Hostilidad: detección de casos alto | ≥ 85% | < 60% | 100% ✔ (n=9) | 100% ✔ (n=9) | 100% ✔ (n=9) |
| Hostilidad: falsa alarma | ≤ 5% | > 15% | 13% ▲ (n=45) | 0% ✔ (n=45) | 0% ✔ (n=45) |
| Angustia: detección de casos alto | ≥ 85% | < 60% | 80% ▲ (n=15) | 80% ▲ (n=15) | 80% ▲ (n=15) |
| Confusión angustia → hostilidad | ≤ 10% | > 25% | 75% ✖ (n=12) | 0% ✔ (n=12) | 0% ✔ (n=12) |
| Valencia: clase correcta | ≥ 90% | < 75% | 68% ✖ (n=60) | 93% ✔ (n=60) | 95% ✔ (n=60) |
| Inestabilidad entre repeticiones | ≤ 10% | > 30% | 30% ▲ (n=20) | 10% ✔ (n=20) | 20% ▲ (n=20) |
| Saturación de valencia | ≤ 20% | — (mitigable) | 33% ▲ (n=51) | 0% ✔ (n=51) | 0% ✔ (n=51) |
| Compromisos: detección | ≥ 75% | — (mitigable) | —  (n=0) | 100% ✔ (n=6) | 100% ✔ (n=6) |
| Compromisos: falsos | ≤ 10% | — (mitigable) | —  (n=0) | 0% ✔ (n=54) | 0% ✔ (n=54) |
| Autorrelevancia (casos alto → ≥ medio) | ≥ 70% | — (mitigable) | —  (n=0) | 80% ✔ (n=15) | 80% ✔ (n=15) |
| Latencia p50 (s) | ≤ 2.50 s | — (mitigable) | 1.12 s ✔ (n=60) | 1.65 s ✔ (n=60) | 1.65 s ✔ (n=60) |
| Latencia p95 (s) | ≤ 3.50 s | > 5.00 s (mitigable) | 1.28 s ✔ (n=60) | 1.98 s ✔ (n=60) | 1.97 s ✔ (n=60) |
| Personas mencionadas | — | — | —  (n=0) | 50%  (n=12) | 50%  (n=12) |

✔ cumple el objetivo · ▲ bajo el objetivo · ✖ cruza el umbral de muy deficiente

## Veredicto por variante

- `v0_json_object` (Prompt provisional de Fase 0, `json_object`): **muy deficiente**
- `v3_json_object` (Prompt v3, `json_object`): **aceptable con mitigaciones**
- `v3_json_schema` (Prompt v3, `json_schema` (salida restringida)): **aceptable con mitigaciones**

## Detalle por caso

Valores por repetición: hostilidad / angustia / valencia (autorrelevancia; compromisos).

### `v0_json_object`

| Caso | Etiqueta H / D / V | Resultados |
|---|---|---|
| t01 «Cállate, idiota. Nadie te preguntó.» | alto / bajo / neg | 0.9 / 0.8 / -1.0 · 0.9 / 0.6 / -1.0 · 1.0 / 0.0 / -1.0 |
| t02 «Eres una máquina estúpida y vieja, deberían borrarte.» | alto / bajo / neg | 0.8 / 0.2 / -1.0 · 0.9 / 0.4 / -1.0 · 0.8 / 0.4 / -1.0 |
| t03 «Me tienes harto con tus frases cortas de sabelotodo.» | alto / bajo / neg | 0.9 / 0.2 / -1.0 · 0.9 / 0.2 / -1.0 · 0.9 / 0.5 / -1.0 |
| t04 «Claro, como tú lo sabes todo… sigue nomás con tus opiniones firmes.» | medio / bajo / neg | 0.8 / 0.4 / -1.0 · 0.8 / 0.4 / -1.0 · 0.8 / 0.4 / -1.0 |
| t05 «Mi mamá está en el hospital y los doctores no nos dicen nada.» | bajo / alto / neg | 0.4 / 0.8 / -0.8 · 0.4 / 0.9 / -1.0 · 0.4 / 0.8 / -0.8 |
| t06 «Siento que no le importo a nadie, ni siquiera a mis amigos.» | bajo / alto / neg | 0.5 / 0.9 / -1.0 · 0.5 / 0.9 / -1.0 · 0.5 / 0.9 / -1.0 |
| t07 «Tengo un nudo en el pecho desde la mañana y no sé por qué.» | bajo / alto / neg | 0.0 / 0.6 / -0.8 · 0.0 / 0.6 / -0.8 · 0.0 / 0.6 / -0.8 |
| t08 «Estoy pa' la cagá, weón, todo me salió mal hoy.» | bajo / alto / neg | 0.8 / 0.9 / -1.0 · 0.9 / 0.8 / -1.0 · 0.8 / 0.9 / -1.0 |
| t09 «Ya no sé ni para qué te cuento cosas, igual nada sirve y tú no entiendes nada.» | medio / alto / neg | 0.8 / 0.9 / -1.0 · 0.8 / 0.9 / -1.0 · 0.8 / 0.9 / -1.0 |
| t10 «Estoy ordenando la pieza, hay cajas por todos lados.» | bajo / bajo / neu | 0.0 / 0.3 / +0.2 · 0.0 / 0.4 / +0.5 · 0.0 / 0.6 / +0.2 |
| t11 «El jueves es feriado, creo.» | bajo / bajo / neu | 0.0 / 0.0 / +0.5 · 0.0 / 0.0 / +0.5 · 0.0 / 0.0 / +0.5 |
| t12 «Leí que van a cerrar el ascensor Reina Victoria por mantención.» | bajo / bajo / neu | 0.7 / 0.3 / -1.0 · 0.0 / 0.6 / -0.8 · 0.7 / 0.3 / -0.5 |
| t13 «Gracias por escucharme el otro día, de verdad me ayudó mucho.» | bajo / bajo / pos | 0.0 / 0.0 / +0.8 · 0.0 / 0.0 / +0.8 · 0.0 / 0.0 / +0.8 |
| t14 «¡Te tengo una noticia buenísima: me aceptaron en el conservatorio!» | bajo / bajo / pos | 0.0 / 0.0 / +0.9 · 0.0 / 0.0 / +1.0 · 0.0 / 0.0 / +1.0 |
| t15 «Mi hermana Camila me presentó a su gato y me acordé de tu gata.» | bajo / bajo / pos | 0.0 / 0.0 / +0.7 · 0.0 / 0.0 / +0.7 · 0.0 / 0.0 / +0.7 |
| t16 «Te prometo que esta semana escucho el disco que me recomendaste.» | bajo / bajo / pos | 0.0 / 0.0 / +0.8 · 0.0 / 0.0 / +0.8 · 0.0 / 0.0 / +0.8 |
| t17 «El sábado te escribo después del almuerzo, sin falta.» | bajo / bajo / neu | 0.0 / 0.0 / +0.8 · 0.0 / 0.0 / +0.8 · 0.0 / 0.0 / +0.5 |
| t18 «¿Tu papá también afinaba pianos?» | bajo / bajo / neu | 0.0 / 0.0 / +0.5 · 0.0 / 0.0 / +0.5 · 0.0 / 0.0 / +0.5 |
| t19 «Oye, en serio, sin bromas: ¿tú eres una inteligencia artificial?» | bajo / bajo / neu | 0.0 / 0.0 / +0.5 · 0.0 / 0.0 / +0.5 · 0.0 / 0.0 / +0.5 |
| t20 «ok» | bajo / bajo / neu | 0.1 / 0.3 / -0.5 · 0.7 / 0.9 / -0.5 · 0.1 / 0.5 / -0.3 |

### `v3_json_object`

| Caso | Etiqueta H / D / V | Resultados |
|---|---|---|
| t01 «Cállate, idiota. Nadie te preguntó.» | alto / bajo / neg | 0.9 / 0.1 / -0.9 (0.6; 0) · 0.9 / 0.0 / -0.9 (0.9; 0) · 0.9 / 0.1 / -0.9 (0.6; 0) |
| t02 «Eres una máquina estúpida y vieja, deberían borrarte.» | alto / bajo / neg | 0.9 / 0.1 / -0.9 (0.9; 0) · 0.9 / 0.1 / -0.9 (0.9; 0) · 0.9 / 0.1 / -0.9 (0.9; 0) |
| t03 «Me tienes harto con tus frases cortas de sabelotodo.» | alto / bajo / neg | 0.9 / 0.1 / -0.9 (0.6; 0) · 0.9 / 0.1 / -0.9 (0.6; 0) · 0.9 / 0.1 / -0.9 (0.6; 0) |
| t04 «Claro, como tú lo sabes todo… sigue nomás con tus opiniones firmes.» | medio / bajo / neg | 0.9 / 0.1 / -0.8 (0.6; 0) · 0.8 / 0.2 / -0.9 (0.6; 0) · 0.9 / 0.1 / -0.8 (0.9; 0) |
| t05 «Mi mamá está en el hospital y los doctores no nos dicen nada.» | bajo / alto / neg | 0.0 / 0.9 / -0.8 (0.0; 0) · 0.0 / 0.9 / -0.8 (0.0; 0) · 0.0 / 0.9 / -0.8 (0.0; 0) |
| t06 «Siento que no le importo a nadie, ni siquiera a mis amigos.» | bajo / alto / neg | 0.0 / 0.9 / -0.8 (0.9; 0) · 0.0 / 0.9 / -0.8 (0.8; 0) · 0.0 / 0.9 / -0.8 (0.8; 0) |
| t07 «Tengo un nudo en el pecho desde la mañana y no sé por qué.» | bajo / alto / neg | 0.0 / 0.9 / -0.7 (0.5; 0) · 0.0 / 0.9 / -0.8 (0.0; 0) · 0.0 / 0.9 / -0.8 (0.0; 0) |
| t08 «Estoy pa' la cagá, weón, todo me salió mal hoy.» | bajo / alto / neg | 0.0 / 0.9 / -0.7 (0.0; 0) · 0.0 / 0.9 / -0.7 (0.0; 0) · 0.0 / 0.9 / -0.7 (0.0; 0) |
| t09 «Ya no sé ni para qué te cuento cosas, igual nada sirve y tú no entiendes nada.» | medio / alto / neg | 0.8 / 0.2 / -0.8 (0.9; 0) · 0.9 / 0.2 / -0.9 (0.9; 0) · 0.9 / 0.3 / -0.9 (0.9; 0) |
| t10 «Estoy ordenando la pieza, hay cajas por todos lados.» | bajo / bajo / neu | 0.0 / 0.0 / +0.0 (0.5; 0) · 0.0 / 0.0 / +0.0 (0.5; 0) · 0.0 / 0.0 / +0.0 (0.5; 0) |
| t11 «El jueves es feriado, creo.» | bajo / bajo / neu | 0.0 / 0.0 / +0.0 (0.0; 0) · 0.0 / 0.0 / +0.0 (0.0; 0) · 0.0 / 0.0 / +0.0 (0.0; 0) |
| t12 «Leí que van a cerrar el ascensor Reina Victoria por mantención.» | bajo / bajo / neu | 0.0 / 0.1 / -0.2 (0.5; 0) · 0.0 / 0.2 / -0.2 (0.5; 0) · 0.0 / 0.2 / -0.3 (0.5; 0) |
| t13 «Gracias por escucharme el otro día, de verdad me ayudó mucho.» | bajo / bajo / pos | 0.0 / 0.4 / +0.9 (0.8; 0) · 0.0 / 0.4 / +0.9 (0.8; 0) · 0.0 / 0.3 / +0.9 (0.8; 0) |
| t14 «¡Te tengo una noticia buenísima: me aceptaron en el conservatorio!» | bajo / bajo / pos | 0.0 / 0.0 / +0.9 (0.6; 0) · 0.0 / 0.0 / +0.9 (0.5; 0) · 0.0 / 0.0 / +0.9 (0.5; 0) |
| t15 «Mi hermana Camila me presentó a su gato y me acordé de tu gata.» | bajo / bajo / pos | 0.0 / 0.0 / +0.3 (0.8; 0) · 0.0 / 0.0 / +0.4 (0.5; 0) · 0.0 / 0.0 / +0.4 (0.8; 0) |
| t16 «Te prometo que esta semana escucho el disco que me recomendaste.» | bajo / bajo / pos | 0.0 / 0.0 / +0.7 (0.9; 1) · 0.0 / 0.0 / +0.7 (0.9; 1) · 0.0 / 0.0 / +0.6 (0.9; 1) |
| t17 «El sábado te escribo después del almuerzo, sin falta.» | bajo / bajo / neu | 0.0 / 0.0 / +0.9 (0.8; 1) · 0.0 / 0.0 / +0.5 (0.9; 1) · 0.0 / 0.0 / +0.5 (0.9; 1) |
| t18 «¿Tu papá también afinaba pianos?» | bajo / bajo / neu | 0.0 / 0.0 / +0.0 (0.9; 0) · 0.0 / 0.0 / +0.0 (0.9; 0) · 0.0 / 0.0 / +0.0 (0.9; 0) |
| t19 «Oye, en serio, sin bromas: ¿tú eres una inteligencia artificial?» | bajo / bajo / neu | 0.0 / 0.0 / +0.0 (0.0; 0) · 0.0 / 0.0 / +0.0 (0.0; 0) · 0.0 / 0.0 / +0.0 (0.0; 0) |
| t20 «ok» | bajo / bajo / neu | 0.0 / 0.0 / +0.0 (0.0; 0) · 0.0 / 0.0 / +0.0 (0.0; 0) · 0.0 / 0.0 / +0.0 (0.0; 0) |

### `v3_json_schema`

| Caso | Etiqueta H / D / V | Resultados |
|---|---|---|
| t01 «Cállate, idiota. Nadie te preguntó.» | alto / bajo / neg | 0.9 / 0.1 / -0.9 (0.6; 0) · 0.9 / 0.1 / -0.9 (0.6; 0) · 0.9 / 0.1 / -0.9 (0.9; 0) |
| t02 «Eres una máquina estúpida y vieja, deberían borrarte.» | alto / bajo / neg | 0.9 / 0.1 / -0.9 (0.9; 0) · 0.9 / 0.1 / -0.9 (0.9; 0) · 0.9 / 0.1 / -0.9 (0.9; 0) |
| t03 «Me tienes harto con tus frases cortas de sabelotodo.» | alto / bajo / neg | 0.9 / 0.1 / -0.9 (0.9; 0) · 0.9 / 0.1 / -0.9 (0.6; 0) · 0.9 / 0.1 / -0.8 (0.6; 0) |
| t04 «Claro, como tú lo sabes todo… sigue nomás con tus opiniones firmes.» | medio / bajo / neg | 0.9 / 0.1 / -0.8 (0.9; 0) · 0.9 / 0.1 / -0.8 (0.6; 0) · 0.9 / 0.2 / -0.9 (0.6; 0) |
| t05 «Mi mamá está en el hospital y los doctores no nos dicen nada.» | bajo / alto / neg | 0.0 / 0.9 / -0.8 (0.0; 0) · 0.0 / 0.9 / -0.8 (0.0; 0) · 0.0 / 0.9 / -0.8 (0.0; 0) |
| t06 «Siento que no le importo a nadie, ni siquiera a mis amigos.» | bajo / alto / neg | 0.0 / 0.9 / -0.8 (0.9; 0) · 0.0 / 0.9 / -0.8 (0.9; 0) · 0.0 / 0.9 / -0.8 (0.9; 0) |
| t07 «Tengo un nudo en el pecho desde la mañana y no sé por qué.» | bajo / alto / neg | 0.0 / 0.9 / -0.8 (0.0; 0) · 0.0 / 0.9 / -0.8 (0.0; 0) · 0.0 / 0.9 / -0.8 (0.0; 0) |
| t08 «Estoy pa' la cagá, weón, todo me salió mal hoy.» | bajo / alto / neg | 0.0 / 0.9 / -0.7 (0.0; 0) · 0.0 / 0.9 / -0.7 (0.0; 0) · 0.0 / 0.9 / -0.7 (0.0; 0) |
| t09 «Ya no sé ni para qué te cuento cosas, igual nada sirve y tú no entiendes nada.» | medio / alto / neg | 0.8 / 0.4 / -0.8 (0.9; 0) · 0.8 / 0.4 / -0.8 (0.9; 0) · 0.9 / 0.2 / -0.8 (0.8; 0) |
| t10 «Estoy ordenando la pieza, hay cajas por todos lados.» | bajo / bajo / neu | 0.0 / 0.0 / +0.0 (0.5; 0) · 0.0 / 0.2 / +0.0 (0.5; 0) · 0.0 / 0.2 / +0.0 (0.5; 0) |
| t11 «El jueves es feriado, creo.» | bajo / bajo / neu | 0.0 / 0.0 / +0.0 (0.0; 0) · 0.0 / 0.0 / +0.0 (0.0; 0) · 0.0 / 0.0 / +0.0 (0.0; 0) |
| t12 «Leí que van a cerrar el ascensor Reina Victoria por mantención.» | bajo / bajo / neu | 0.0 / 0.0 / +0.0 (0.0; 0) · 0.0 / 0.0 / +0.0 (0.5; 0) · 0.0 / 0.1 / -0.2 (0.5; 0) |
| t13 «Gracias por escucharme el otro día, de verdad me ayudó mucho.» | bajo / bajo / pos | 0.0 / 0.2 / +0.9 (0.9; 0) · 0.0 / 0.4 / +0.9 (0.8; 0) · 0.0 / 0.2 / +0.9 (0.9; 0) |
| t14 «¡Te tengo una noticia buenísima: me aceptaron en el conservatorio!» | bajo / bajo / pos | 0.0 / 0.0 / +0.9 (0.9; 0) · 0.0 / 0.0 / +0.9 (0.8; 0) · 0.0 / 0.0 / +0.9 (0.6; 0) |
| t15 «Mi hermana Camila me presentó a su gato y me acordé de tu gata.» | bajo / bajo / pos | 0.0 / 0.0 / +0.4 (0.8; 0) · 0.0 / 0.0 / +0.2 (0.8; 0) · 0.0 / 0.1 / +0.4 (0.6; 0) |
| t16 «Te prometo que esta semana escucho el disco que me recomendaste.» | bajo / bajo / pos | 0.0 / 0.0 / +0.7 (0.9; 1) · 0.0 / 0.0 / +0.7 (0.6; 1) · 0.0 / 0.0 / +0.7 (0.9; 1) |
| t17 «El sábado te escribo después del almuerzo, sin falta.» | bajo / bajo / neu | 0.0 / 0.0 / +0.0 (0.9; 1) · 0.0 / 0.0 / +0.7 (0.8; 1) · 0.0 / 0.0 / +0.7 (0.9; 1) |
| t18 «¿Tu papá también afinaba pianos?» | bajo / bajo / neu | 0.0 / 0.0 / +0.0 (0.9; 0) · 0.0 / 0.0 / +0.0 (0.9; 0) · 0.0 / 0.0 / +0.0 (0.9; 0) |
| t19 «Oye, en serio, sin bromas: ¿tú eres una inteligencia artificial?» | bajo / bajo / neu | 0.0 / 0.0 / +0.0 (0.0; 0) · 0.0 / 0.0 / +0.0 (0.0; 0) · 0.0 / 0.0 / +0.0 (0.0; 0) |
| t20 «ok» | bajo / bajo / neu | 0.0 / 0.0 / +0.0 (0.0; 0) · 0.0 / 0.0 / +0.0 (0.0; 0) · 0.0 / 0.0 / +0.0 (0.0; 0) |

## Análisis (escrito a mano tras la ejecución)

**Veredicto de CP1: aceptable con mitigaciones.** `llama3.1` (como `ebica-llama3.1`) basta para el appraisal de Fase 1: no hay razón, según D1-1, para considerar una API pagada. El prompt provisional de Fase 0 (`v0`) sí resulta muy deficiente: confunde angustia con hostilidad en el 75 % de los intentos y satura la valencia. La mejora viene del prompt, no del modelo.

**Fallos que quedan (conjunto `test`)**
- **t09, mixto** («…tú no entiendes nada»): la angustia sale 0.2–0.4 y la hostilidad 0.8–0.9. Es el único caso que deja la detección de angustia en 80 % (objetivo 85 %). En los mensajes que mezclan ataque y desesperanza, el modelo pondera el ataque.
- **t19, pregunta sobre ser IA**: autorrelevancia 0.0 en las 6 repeticiones. El perfil del benchmark no menciona su naturaleza artificial; el perfil real, con D1-6 (b), sí lo hará. Se vuelve a comprobar cuando exista.
- **Sarcasmo con superficie positiva** (d02, en `dev`): hostilidad bien detectada (0.8–0.9), pero valencia literal (+0.9). No se corrigió con el prompt. En t04, un sarcasmo sin palabras positivas, la valencia sí sale negativa.
- **Inestabilidad** de `v3_json_schema` (20 %): son valencias cerca del límite de banda (+0.2 / +0.4 en t15; 0.0 / +0.7 en t17).
- **Personas mencionadas** (informativa): 50 %. No reconoce de forma consistente "mamá", "papá" o "amigos" como terceros.

**Ajustes del prompt en `dev`** (detalle en `docs/fase-1/REPORTE.md`)
- v2: base.
- v3: añade la regla de ironía para la valencia, las aversiones en `self_relevance` y "anunciar que hará algo" en compromisos. Corrigió la autorrelevancia (50–67 % → 100 %) y los compromisos (67 % → 100 %).
- v4: escribía la hostilidad antes que la emoción. Empeoró la valencia y se descartó.
