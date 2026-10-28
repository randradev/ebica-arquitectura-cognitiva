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
| Episodios reales de Calisto sin `INVOLVES` | CP8 | **CP8 D** | D1-60: enlazar los 39 a Ricardo, reescribir el texto y reconstruir su modelo (el usuario confirmó que habló siempre él). |
| Política ante textos largos y resumen continuo | CP5 / D1-8 | antes de **CP9** | D1-8 (b), resumen con LLM, solo si los recuerdos no caben en el presupuesto. |
| Tope de 1.200 tokens de las secciones 4–5 | D1-50 (CP7) | **CP9** | Provisional; lo reemplaza la WorkingMemory. |
| Asteriscos y acotaciones | Fase 0, pendiente 6 | **CP9** | Medir su frecuencia; filtro solo si persisten. |
| `Commitment` en vigilia y término de compromisos del puntaje (vale 0 hoy) | §7.1, D1-44 | **CP10** | |
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

## 3. Datos operativos

- **Rendimiento medido:**
  - arranque del servidor con memoria ~9 s (bge-m3 3,2–3,4 s);
  - primera carga de una entidad ~10–12 s (embeddings de la semilla); las siguientes 0,07 s;
  - escritura de un turno 0,25–0,50 s (después de responder);
  - recuperación 70–130 ms (el embedding va en paralelo con el appraisal);
  - prompt máximo medido: 2.298 tokens.
- **bge-m3 consulta HuggingFace Hub al cargar** (aviso en el log). Pendiente de CP2, no urgente: fijar la revisión convertida o exigir `safetensors`, para cargar sin red y poder borrar el `.bin`.
- **El índice vectorial es compartido por todas las entidades.** Desde CP7, `vector_search` tiene un respaldo exacto cuando otra entidad acapara a los vecinos (D1-11).
- **La memoria real de Calisto** vive en Neo4j (`entity_id: calisto`). Las pruebas en vivo usan una copia de su config con otro id y borran sus nodos al terminar. Los diálogos sobre la memoria («¿qué te dije…?») también quedan como episodios y compiten después con los recuerdos reales.
