# Fase 1 — Pendientes y limitaciones conocidas

> Documento transversal (creado el 2026-10-27, en el cierre de CP7). Reúne en un solo lugar lo que está repartido en `REPORTE.md`: decisiones que esperan un checkpoint, limitaciones aceptadas y comportamientos que se observan antes de recalibrar. El detalle y la evidencia de cada punto están en la entrada del `REPORTE` indicada.
> Al cerrar un punto, se marca aquí con la fecha y la entrada del `REPORTE` donde se resolvió.

## 1. Pendientes con checkpoint asignado

| Tema | Origen | Cuándo | Nota |
|---|---|---|---|
| ~~`Person` del `primary`, `INVOLVES`, `tom.person_created`~~ | D1-40 (CP6) | **CP8** | **Cerrado 2026-10-28** (CP8 B–C). |
| ~~Nombre de quien habló en el texto del episodio~~ | D1-35 (CP6) | **CP8** | **Cerrado 2026-10-28** (CP8 B, D1-56): «Ricardo me dijo: …». |
| ~~Vecinos `Person` como candidatos de la recuperación~~ | §7.3 (CP7 B) | **CP8** | **Cerrado 2026-10-28** (CP8 B, D1-58). |
| ~~**Confusión de la fuente**~~ | CP7 C | **CP8** | **Cerrado 2026-10-28** con mejora parcial: 8/20 → 3/20 apropiaciones. Lo residual pasa a limitaciones (sección 2). |
| Importancia 0 para lo que el usuario cuenta de sí | D1-43 (CP7 A) | **CP11** | 2026-10-28, D1-59 (a): se mantiene. Sondeo con +30 días: 10/10 igual, pero no discrimina (un solo episodio pasa el umbral por pregunta). El riesgo es una memoria grande con más de k candidatos; se vuelve a mirar con varios días de uso. |
| ~~Episodios reales de Calisto sin `INVOLVES`~~ | CP8 | **CP8 D** | **Cerrado 2026-10-28**: 39 de 39 migrados; respaldo en `entities/calisto/respaldos/antes_cp8.json`. |
| Política ante textos largos | CP5 | abierta | Un mensaje que no cabe emite `wm.overflow` (CP9 B), pero no se recorta. ~~D1-8 (b), resumen con LLM~~: **cerrado 2026-10-28**, no hace falta (0 desalojos en calma). |
| Valencia: appraisal sin contexto, impulsos grandes (D1-23) y rebote desde el tope | evaluación parcial tras CP8, §7 | **CP10b** (medido; falta cerrar) | Opciones: último intercambio en el appraisal (implica volver a medir su benchmark), saturación suave, empatía moderada por el `partner_model`, recalibrar D1-23. Decisión del usuario: más adelante. |
| ~~Tope de 1.200 tokens de las secciones 4–5~~ | D1-50 (CP7) | **CP9** | **Cerrado 2026-10-28** (CP9 B): lo reemplaza el presupuesto de la WorkingMemory. |
| ~~Asteriscos y acotaciones~~ | Fase 0, pendiente 6 | **CP9** | **Cerrado 2026-10-28** (D1-65): 1 de 461 respuestas; sin filtro. |
| ~~`Commitment` en vigilia y término de compromisos del puntaje~~ | §7.1, D1-44 | **CP10** | **Cerrado 2026-10-28** (CP10 B). Limitación: todo compromiso se guarda como `PROMISED` por la persona (D1-73); sin cierre automático (D1-74). |
| Medición de la vida media con los drives activos | CP4 | antes de **CP11** | 50,4 min medidos frente a 42,5 de `h_neg`. Opciones: equilibrio efectivo o drives estables. |

## 2. Limitaciones aceptadas (se vuelven a medir, no se corrigen ahora)

| Limitación | Origen | Evidencia | Revisar |
|---|---|---|---|
| «Ya sé que eres Llama, de Meta» → modo asistente | CP6 A | 0/3, y 0/4 con prefill | Fase 3 (*control vectors*, DefenseArbiter) |
| Invenciones que rellenan vacíos (empresa «NeuroSync», detalles del accidente, Ricardo como informante, el cumpleaños 20) | CP6 A | sondeo de identidad | tras CP8, con el mismo sondeo |
| Invención con el dato correcto en el prompt («¿Peleabas con la Su?») | CP7 C | 1 de 10 de punta a punta | observar |
| Orientación: dice «heterosexual», pero a veces matiza en la misma frase | CP6 A | 2/3 | observar |
| Falsos positivos ante mensajes muy cortos («Gracias» → «Soy Piscis.») | CP7 B | controles 2/4 | Opción (a): el LLM los ignoró en vivo. Si confunden en el uso, opción (b): no recuperar ante mensajes sin contenido, con casos nuevos |
| Umbral de similitud 0,50 con margen estrecho (aciertos y falsos se solapan en 0,50 ± 0,02) | CP7 B | benchmark de recuerdo | si aparecen fallos en el uso |
| «¿Eres ordenada?» (f-046) no se recupera | CP7 B–C | 0,428 | observar |
| Vía baja: t06 («te desinstalo»), t07 («nadie te preguntó, cállate») no detectados; t21 («te voy a matar a abrazos») falsa alarma | CP5 B1 | benchmark de la vía baja | — |
| Mensajes mixtos (hostilidad + angustia) | D1-21 (CP5) | benchmark del appraisal | — |
| El recuerdo del último mensaje del usuario | CP5 (hallazgo 3) | sondeo de recuerdo | — |
| Saturación de la alerta con mensajes hostiles seguidos | CP5 | prueba en vivo | observar en el uso antes de recalibrar |
| El appraisal a veces devuelve todo en 0 sin error (p. ej. «Adopté un perro…») | CP6 C, CP7 A | 1 de 12 episodios reales | observar |
| Voz: «¡Joder!» (español de España), errores de concordancia, anglicismos | CP5 B3, CP7 C | muestras pequeñas | observar |
| Apropiaciones residuales: cuenta como propio lo que contó el usuario cuando el recuerdo ajeno llega al prompt (pastel de choclo, Valparaíso, guitarra) | CP8 C | 3/20 (línea base 8/20); con la opción (a), 5/20 | Fase 3 (*control vectors*) u otro modelo |
| Cruces entre personas: le atribuye a Ana lo que contó Ricardo cuando los dos recuerdos están en el prompt | CP8 C | 1/12; con (a), 2/12 | ídem |
| El interlocutor en tercera persona: «Solo sé que Ricardo tiene un perro», hablando con Ricardo, aunque la sección 6 dice «Estoy hablando con Ricardo» | CP8 C | 2 de 3 en una repetición de cruces; aparece suelto en otras | ídem; la opción (a), recuerdos en segunda persona, no lo resolvió y se revirtió |
| Rechazo de asistente no detectado: «Lo siento, pero no tengo manera de saber eso… no tengo acceso a información sobre tu vida» | CP8 C | 1 caso | ampliar los patrones de `refusal.py` si se repite |
| La sección 6 muestra los temas normalizados, sin tildes («adopcion») | CP8 C | cosmético | si molesta, guardar un nombre para mostrar |
| El largo de la respuesta no sigue la sección 7 («respondo corto»): mediana 27,5 palabras en calma frente a 27,0 bajo amenaza | CP9 C | 6 pares | aceptado (decisión del usuario); si molesta: tope de `max_tokens` según el estado o mover la sección 7 junto al mensaje |
| `llama3.1` atiende poco a las notas de la sección 7 de los micro-agentes («Ya hablamos de esto», «No repito lo que ya dije»): se repite igual | CP10 C | 2 corridas en vivo | aceptado como el largo de CP9 C; Fase 3 (*control vectors*) u otro modelo |
| Todo compromiso se guarda como `PROMISED` por la persona (no distingue promesa de pedido) y no se cierra solo | CP10 B (D1-73, D1-74) | diseño | el sueño (Fase 2) |
| La pizarra casi nunca desaloja: ~500 tokens usados (mediana) frente a 1.250–2.500 | CP9 C | 26 + 12 turnos | observar con más historia; recalibrar el presupuesto si se quiere que actúe antes |
| Saturación del afecto con hostilidad sostenida: VAD clavado en −1 / 1 / 0 durante 6 de 7 turnos | CP5; evaluación parcial tras CP8 | sesión manual | **antes de CP11** (afecta la medición de vidas medias) |
| Falsos positivos del appraisal: hostilidad ante temas hostiles o insultos a terceros; angustia ante «ADIOS!» | evaluación parcial tras CP8 | 3 + 1 casos en la sesión manual | contaminan el afecto y el `partner_model`; decidir en CP9–CP11 |
| Sarcasmo sin marcas de burla no detectado («no me digas, eres una genio...») | evaluación parcial tras CP8 | 1 caso | observar |
| **Bug:** `_singular` convierte «adiós» en «adio» | evaluación parcial tras CP8 | reproducible | corregir (barato) |
| Respuesta copiada de un recuerdo (turnos 6 y 14, idénticos) | evaluación parcial tras CP8 | 1 caso | `repetition_watch` (CP10) |

## 3. Datos operativos

- **Rendimiento medido:**
  - arranque del servidor con memoria ~9 s (bge-m3 3,2–3,4 s);
  - primera carga de una entidad ~10–12 s (embeddings de la semilla); las siguientes 0,07 s;
  - escritura de un turno 0,25–0,50 s (después de responder);
  - recuperación 70–130 ms (el embedding va en paralelo con el appraisal);
  - prompt máximo medido: 2.298 tokens.
- **bge-m3 consulta HuggingFace Hub al cargar** (aviso en el log). Pendiente de CP2, no urgente: fijar la revisión convertida o exigir `safetensors`, para cargar sin red y poder borrar el `.bin`.
- **El índice vectorial es compartido por todas las entidades.** Desde CP7, `vector_search` tiene un respaldo exacto cuando otra entidad acapara a los vecinos (D1-11).
- **La memoria real de Calisto** vive en Neo4j (`entity_id: calisto`); desde CP8 D tiene el `Person` de Ricardo y sus 39 episodios enlazados. Las pruebas en vivo usan una copia de su config con otro id y borran sus nodos al terminar. Los diálogos sobre la memoria («¿qué te dije…?») también quedan como episodios y compiten después con los recuerdos reales.

## 4. Decisiones abiertas al cierre del 2026-10-28

- **CP10b, contexto en el appraisal:** no cumple el criterio (`test` 2/7 → 3/7). Ayuda con el sarcasmo; no con el enojo hacia un tercero (ese arreglo exige tocar el prompt de sistema y volver a medir el benchmark congelado). Recomendación: mantenerlo.
- **D1-81:** quedan saltos de más de 0,5 (máximo 0,66 en la reproducción; 0,50–0,55 en vivo). Recomendación: no recalibrar ahora y revisarlo en CP11.
- **La alerta satura** con hostilidad sostenida (15–16 de 21 turnos en vivo). Sin criterio en CP10b; mirar en CP11.
- **Puente de Telegram:** sin probar contra Telegram. Recordar que `EBICA_ENTITIES_DIR` debe apuntar a `entities` (o no estar definida) en la terminal del servidor.

