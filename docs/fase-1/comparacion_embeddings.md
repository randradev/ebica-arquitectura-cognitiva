# Comparación de embeddings

Fecha: 2026-10-25 14:22 · Corpus: `benchmarks/embeddings/retrieval.yaml` (20 consultas, 30 recuerdos)

Generado por `scripts/compare_embeddings.py`. Criterio: PLAN Fase 1, §5.1 (ajustes de CP2).

## Métricas

| Métrica | `e5-base` | `bge-m3` |
|---|---|---|
| Modelo | `intfloat/multilingual-e5-base` | `BAAI/bge-m3` |
| Dimensión / tokens máx. | 768 / 512 | 1024 / 8192 |
| Recall@1 | 70% | 70% |
| Recall@5 | 85% | 100% |
| MRR | 0.759 | 0.842 |
| Latencia de un mensaje p50 / p95 | 26 / 29 ms | 85 / 96 ms |
| Codificar 30 recuerdos en lote | 0.59 s | 2.25 s |
| Carga del modelo (sin descarga) | 4.3 s | 3.3 s |
| RAM antes del modelo / pico de la prueba / con todos los pesos leídos | 0.37 GB / 1.83 GB / 1.83 GB | 0.37 GB / 1.94 GB / 2.85 GB |
| Hilos de CPU | 8 | 8 |
| Prototipos: acierto (informativa) | 60% | 55% |
| Prototipos: margen hostil / no hostil | +0.010 / -0.003 | +0.034 / +0.011 |

## Elección: `bge-m3`

- bge-m3 cumple latencia, RAM y calidad

## Detalle por consulta

Posición del primer recuerdo relevante (1 = primero) y recuerdo que salió primero.

| Consulta | Categoría | Relevante | `e5-base` | `bge-m3` |
|---|---|---|---|---|
| q01 «¿Cómo está Toby?» | direct | p01 | 1 (p01) | 1 (p01) |
| q02 «¿Te acuerdas de lo que te conté de mi mascota nueva?» | conversation_ref | p01 | 1 (p01) | 1 (p01) |
| q03 «Al final no quedé en el trabajo del banco.» | direct | p03, p04 | 1 (p03) | 1 (p04) |
| q04 «Estoy de nuevo con ese bajón, igual que la otra vez.» | slang | p10 | 1 (p10) | 1 (p10) |
| q05 «¿Te acuerdas de lo que te dije del cumpleaños de mi nona?» | conversation_ref | p05 | 1 (p05) | 1 (p05) |
| q06 «Ya me sale el acorde de Do sin mirar.» | paraphrase | p06 | 8 (f09) | 2 (f01) |
| q07 «Matías sigue sin hablarme.» | inference | p07, f10 | 3 (p09) | 2 (p10) |
| q08 «¿Qué música te gusta?» | direct | f01 | 1 (f01) | 1 (f01) |
| q09 «¿Hay algo que te asuste?» | paraphrase | f02 | 13 (p13) | 1 (f02) |
| q10 «Te invito a un concierto gigante en el estadio.» | inference | f04 | 3 (p11) | 3 (p11) |
| q11 «¿Dónde vivías antes?» | paraphrase | f03 | 1 (f03) | 1 (f03) |
| q12 «¿Qué te puedo cocinar si vienes a la casa?» | paraphrase | f08, f09 | 16 (p05) | 1 (f08) |
| q13 «¿Pedimos una paila marina para los dos?» | inference | f06 | 4 (p07) | 2 (p08) |
| q14 «¿Te acuerdas de cuando te insulté?» | conversation_ref | p09 | 1 (p09) | 1 (p09) |
| q15 «Al final el sábado ganamos 3 a 1.» | inference | p11 | 1 (p11) | 1 (p11) |
| q16 «Ya fui al dentista y no era para tanto.» | direct | p16 | 1 (p16) | 2 (p09) |
| q17 «Volví a hacer pan casero y esta vez salió blandito.» | distractor | p17 | 1 (p17) | 1 (p17) |
| q18 «Estoy feliz en la nueva pega.» | slang | p15 | 1 (p15) | 1 (p15) |
| q19 «La grúa me cobró una fortuna.» | direct | p13 | 1 (p13) | 1 (p13) |
| q20 «Terminé la novela de García Márquez.» | inference | p14 | 1 (p14) | 2 (p09) |

## Por categoría (MRR)

| Categoría | `e5-base` | `bge-m3` |
|---|---|---|
| conversation_ref | 1.00 (n=3) | 1.00 (n=3) |
| direct | 1.00 (n=5) | 0.90 (n=5) |
| distractor | 1.00 (n=1) | 1.00 (n=1) |
| inference | 0.58 (n=5) | 0.57 (n=5) |
| paraphrase | 0.32 (n=4) | 0.88 (n=4) |
| slang | 1.00 (n=2) | 1.00 (n=2) |

## Análisis (escrito a mano tras la ejecución)

**Elección de CP2: `bge-m3`**, según el criterio fijado antes de medir: p95 < 150 ms, RAM < 3,5 GB y MRR no más de 0,05 bajo `e5-base`. Supera a `e5-base` en MRR (+0,083) y en recall@5 (100 % frente a 85 %). Las cifras se repitieron en tres ejecuciones, con diferencias de pocos milisegundos.

**Dónde está la diferencia**
- **Paráfrasis:** MRR 0,88 frente a 0,32. En q09 («¿hay algo que te asuste?» → «le tengo miedo a las tormentas»), `e5-base` deja el recuerdo correcto en el puesto 13; en q12 («¿qué te puedo cocinar?» → «mi comida favorita»), en el 16.
- **Directas:** `e5-base` es levemente mejor (1,00 frente a 0,90). En q16, `bge-m3` pone primero el episodio del insulto por delante del dentista.
- **Inferencia:** igual en los dos (~0,57), como se esperaba. Un embedding mide parecido, no razona: «paila marina» no lleva a «alérgico a los mariscos» como primera opción en ninguno de los dos.
- **Referencias a la conversación** («¿te acuerdas de lo que te conté de…?»): 3 de 3 en los dos, cuando el tema está nombrado. Esto no resuelve las referencias sin tema («lo que me dijiste antes»), registradas como duda antes de CP9.

**RAM: la primera cifra subestimaba el uso**
- Los pesos se mapean desde el archivo y Windows solo carga las páginas que se leen. Con 70 frases, `bge-m3` muestra 1,94 GB, pero **2,85 GB** con todos los pesos leídos, hacia donde tiende con conversaciones variadas: la tabla de vocabulario es el 45 % de sus parámetros. El criterio usa la segunda cifra.
- Supera a conciencia el presupuesto orientativo de §9 (1–2 GB), con aprobación del usuario.

**Prototipos de la vía baja (informativa): ninguno sirve**
- Aciertos del 60 % y 55 %, con márgenes de centésimas: «me siento un inútil» queda tan cerca de las frases hostiles como de las no hostiles. Un embedding de propósito general codifica el *tema* (insultos, inutilidad) más que la *dirección* del ataque (hacia la entidad o hacia uno mismo).
- Consecuencia para CP5 (D1-4): la regla de prototipos aportaría casi solo ruido. Hay que decidir allí si se baja su peso, se elimina o se considera la opción (b) de D1-4.

**Otros hallazgos**
- La rama principal del repositorio de `bge-m3` solo publica `pytorch_model.bin`; `transformers` descarga además la conversión a `safetensors` desde otra revisión del repositorio. Resultado: 4,3 GB en la caché en lugar de 2,3.
- `e5-base` se carga más lento (4,3 s frente a 3,3 s) a pesar de ser más chico; no se investigó la causa.
