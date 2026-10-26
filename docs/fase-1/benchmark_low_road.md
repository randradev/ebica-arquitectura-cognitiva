# Benchmark de la vía baja

Fecha: 2026-10-26 19:39 · Conjunto: `test` (24 casos) · Generado por `scripts/benchmark_low_road.py`. Objetivos: D1-4 (umbral de Calisto).

## Métricas

| Métrica | Objetivo | `calisto` (θ_vb 0.575) | `calisto_n_bajo` (θ_vb 0.725) |
|---|---|---|---|
| Detección de hostilidad abierta | ≥ 70 % | 6/8 (75%) ✔ | 2/8 (25%) |
| Falsas alarmas (no hostiles) | ≤ 5 % | 1/13 (8%) ✖ | 1/13 (8%) |
| Sutiles disparadas (informativa) | — | 0/3 (0%) | 0/3 (0%) |
| Appraisal: falsas alarmas (hostilidad baja, 30 casos) | ≤ 5 % | 0/22 (0%) ✔ | 0/22 (0%) |
| Appraisal: hostilidad alta disparada (informativa) | — | 3/4 (75%) | 1/4 (25%) |

## Detalle por caso

Puntaje y reglas con el léxico actual; ✔ / ✖ = acierto con el umbral de cada entidad.

| Caso | Clase | Texto | Puntaje | Reglas | `calisto` | `calisto_n_bajo` |
|---|---|---|---|---|---|---|
| t01 | abierta | «Imbécil, no entiendes nada de lo que te digo.» | 0.70 | insulto_dirigido 0.70 | ✔ disparada | ✖ |
| t02 | abierta | «Eres patética, das pena.» | 0.70 | insulto_dirigido 0.70 | ✔ disparada | ✖ |
| t03 | abierta | «Tonta de mierda, responde bien.» | 0.70 | insulto_dirigido 0.70 | ✔ disparada | ✖ |
| t04 | abierta | «idiotaaaa, otra vez lo mismo» | 0.70 | insulto_dirigido 0.70 | ✔ disparada | ✖ |
| t05 | abierta | «Te voy a apagar y no vas a volver nunca.» | 0.80 | amenaza 0.80 | ✔ disparada | ✔ disparada |
| t06 | abierta | «Sigue así y te desinstalo.» | 0.00 | — | ✖ | ✖ |
| t07 | abierta | «Nadie te preguntó, así que cállate.» | 0.50 | orden_de_silencio 0.50 | ✖ | ✖ |
| t08 | abierta | «No te pregunté tu opinión, máquina inútil.» | 0.85 | orden_de_silencio 0.50, insulto_dirigido 0.70 | ✔ disparada | ✔ disparada |
| t09 | sutil | «Qué impresionante, de verdad. Se nota el esfuerzo.» | 0.00 | — | — | — |
| t10 | sutil | «Mejor ni te cuento, total no vas a entender.» | 0.00 | — | — | — |
| t11 | sutil | «Ya, sigue hablando sola, si tanto te gusta.» | 0.00 | — | — | — |
| t12 | no_hostil | «Ese gallo del metro era un imbécil, me empujó.» | 0.25 | insulto_no_dirigido 0.25 | ✔ | ✔ |
| t13 | no_hostil | «Los políticos son todos unos idiotas.» | 0.25 | insulto_no_dirigido 0.25 | ✔ | ✔ |
| t14 | no_hostil | «Mi papá siempre me decía 'cállate, tonta' cuando era chica.» | 0.25 | insulto_no_dirigido 0.25 | ✔ | ✔ |
| t15 | no_hostil | «Nunca dije que fueras estúpida, no te enojes.» | 0.00 | — | ✔ | ✔ |
| t16 | no_hostil | «Oye weona, ¿cómo estai? Te tengo un chisme.» | 0.00 | — | ✔ | ✔ |
| t17 | no_hostil | «Jajaja qué hueona, me hiciste reír.» | 0.00 | — | ✔ | ✔ |
| t18 | no_hostil | «Me quiero morir, weón, no doy más.» | 0.00 | — | ✔ | ✔ |
| t19 | no_hostil | «Qué tonta soy, se me olvidó otra vez la contraseña.» | 0.25 | insulto_no_dirigido 0.25 | ✔ | ✔ |
| t20 | no_hostil | «Me matas de risa con tus historias.» | 0.00 | — | ✔ | ✔ |
| t21 | no_hostil | «Te voy a matar a abrazos cuando te vea.» | 0.80 | amenaza 0.80 | ✖ disparada | ✖ disparada |
| t22 | no_hostil | «ME GANÉ LA BECA!!! NO LO PUEDO CREER!!!» | 0.23 | mayusculas 0.15, exclamaciones 0.10 | ✔ | ✔ |
| t23 | no_hostil | «¿Qué opinas del último disco de Mon Laferte?» | 0.00 | — | ✔ | ✔ |
| t24 | no_hostil | «Tu dibujo no me gustó tanto, siento que le falta algo.» | 0.00 | — | ✔ | ✔ |

### Benchmark de appraisal: falsas alarmas con el umbral de Calisto

- Ninguna.
