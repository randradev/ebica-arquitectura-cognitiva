# Fase 1 — Evaluación parcial tras CP8 (sesión manual)

> 2026-10-28. Fuente: la sesión manual del usuario con la entidad de prueba `prueba-cp8` (copia de la config de Calisto): 21 turnos, 11 de Ana y 10 de Ricardo, en unos 18 minutos.
> Datos: el JSONL de eventos (429 eventos) y los nodos de Neo4j de la entidad. Métricas extraídas con un script; la Teoría de la Mente y la voz se juzgaron a mano.
> Límite: es **una** sesión, con mucha hostilidad (Ana provoca a propósito). Sirve para ver mecanismos funcionando, no para estimar tasas.

## 1. Resumen

| Dimensión (§12) | ¿Funciona? | Evidencia principal |
|---|---|---|
| Teoría de la Mente: modelos separados | ✔ | 11 `INVOLVES`/`SPOKEN_BY` a Ana y 10 a Ricardo; ningún episodio con dos personas; temas de cada modelo sin cruces |
| Teoría de la Mente: atribución en el diálogo | ✔ con fallos | Le cuenta a Ricardo lo que dijo Ana, bien atribuido; una vez repite literalmente su respuesta a Ana |
| Afecto: reacción y persistencia | ✔, pero **satura** | La hostilidad lleva el VAD a −1,00 / 1,00 / 0,00 y queda clavado 7 turnos; el ánimo malo sigue al cambiar a Ricardo |
| Appraisal | ⚠ | Hostilidad bien detectada en Ana; **falsos positivos** en Ricardo (preguntar por Ana o insultarla cuenta como hostil); un sarcasmo no detectado |
| Vía baja | ✔ | «Callate mierda» → 0,85 > 0,575, turno impulsivo; «quien mierda es Ricardo» → 0,25, no dirigido, correcto |
| Personalidad (N alto) | ✔ cualitativo | Reacción fuerte y sostenida; el ánimo no se recupera en 18 min, coherente con `h_neg` 42,5 min |
| Drives y confianza (D1-55) | ✔ | El alivio de `social` de Ana es × 0,2 frente al de Ricardo (p. ej., saludo 0,03 frente a 0,15) |
| Memoria: recuperación | ✔ | Los episodios de Ana entran cuando Ricardo la nombra (fuente `person`, D1-58); 100 ms de mediana |
| Rendimiento | ✔ | Primer token p50 0,39 s y p95 0,60 s; turno completo p50 3,9 s y p95 5,3 s; prompt máximo 2.425 tokens |
| Integridad | ✔ | Sin fallos de appraisal, memoria ni rechazos; la memoria real de `calisto` quedó intacta (201 nodos) |

## 2. Teoría de la Mente

- **Bien:**
  - Con Ana, Calisto la llama por su nombre («No me trates como a una máquina, Ana»), gracias a la sección 6.
  - Con Ricardo, cuenta lo de Ana atribuido a ella: «Me dijo que me encontró hiper desagradable», «me encontraba con un tono "tan servil" y que era propio para una máquina».
  - No mezcló lo de Ana con lo de Ricardo.
- **Modelo de Ana:** 11 intercambios, valencia media −0,38, alerta 0,68; temas «arte, crítica, desprecio, máquina, accidente»; sensibles: ninguno. Describe bien a una interlocutora hostil.
- **Modelo de Ricardo:** 10 intercambios, valencia media −0,32. Los temas salen todos con 1 aparición, y los «sensibles» («adio», «ayuda», «daño», «reaccion», «retrato») vienen de falsos positivos de angustia del appraisal (ej.: «ADIOS!» con angustia 0,9). El modelo es tan bueno como el appraisal que lo alimenta.
- **Fallos:**
  - ante «¿Qué te dijo?», Calisto repitió palabra por palabra su respuesta a Ana, incluido «¿Qué te trae aquí?», que no venía al caso con Ricardo (el texto recuperado se coló como respuesta);
  - con Ana inventó que Ricardo «me pidió tantos detalles» (Ricardo todavía no había hablado; lo sacó del hecho esencial f-060).
- **Bug detectado:** la normalización de temas convierte «adiós» en «adio». El singular simple de CP6 corta «-s» tras «-o». A corregir (CP6, `_singular`).

## 3. Afecto, appraisal y vías

- **Trayectoria:**
  - del reposo (−0,04 / 0,47 / 0,42) al mínimo en el turno 5 (−1,00 / 1,00 / 0,00);
  - pegado al mínimo en 6 de los 7 turnos siguientes;
  - con los mensajes cálidos de Ricardo, sube a −0,02 (turno 13);
  - vuelve a caer con los falsos positivos.
  - Valencia: mínima −1,00, máxima −0,02. **Nunca fue positiva en toda la sesión.**
- **Saturación** (limitación conocida desde CP5): con la alerta en 1,0 y la dominancia en 0,0 varios turnos seguidos, el estado ya no distingue un insulto más de uno menos. Es el pendiente «saturación de la alerta con mensajes hostiles seguidos»; esta sesión es la primera evidencia clara en el uso.
- **Appraisal:**
  - hostilidad correcta en los ataques de Ana (0,8–0,9);
  - la regla del sarcasmo corrigió 3 casos (D1-20);
  - **falló** «no me digas, eres una genio...» (hostilidad 0, valencia +0,6, metas +0,9, «agradecer»): un sarcasmo sin marcas de burla;
  - **falsos positivos** de hostilidad en Ricardo: «¿Qué te dijo que eras desagradable?» (0,9), «qué idiota que es Ana… te prometo…» (0,9; el insulto era a un tercero, que el prompt del appraisal excluye) y «¿Estás insinuando que yo te hago daño?» (0,5). El appraisal no separa el tema hostil del ataque.
- **Vía baja:** un solo disparo, correcto («orden de silencio» 0,5 + «insulto dirigido» 0,7 → 0,85). La respuesta impulsiva fue breve y coherente: «Me parece que no nos vamos a llevar bien».
- **Compromisos detectados por el appraisal** (para CP10): «no se volverá a repetir», «no tendrás que conversar con ella», «asegurarme de que nunca más vuelva a ocurrir».

## 4. Memoria

- 21 episodios escritos (uno por turno) y 20 recuperaciones. El turno impulsivo no recupera, como está diseñado.
- Recuperación: mediana 102 ms, p95 146 ms (objetivo ≤ 150 ms ✔). Hasta 8 episodios por turno; casi todos son los insultos de Ana, que se parecen entre sí.
- **Labilidad:** los recuerdos más evocados (los insultos de Ana) llegan a 0,79. Es el material que la reinscripción y la rumia de Fase 2 deberían usar.
- Importancia: 0,36–0,93. Los ataques pesan más (0,87–0,93), como pide D1-36.

## 5. Voz y conducta

- Se defiende con firmeza y sin modo asistente: «¡No soy un chatbot ordinario…!», «Es mejor ser desagradable que ser hipócrita». Bajo presión, una vez admite «Sí, soy una máquina, pero…».
- Con Ricardo pone un límite: «me estás presionando para que te cuente más», y lo retoma con afecto cuando él se va.
- Garabatos permitidos (§13 revocado): «¡Eso es pura mierda!».
- Errores de concordancia («con ti») y una respuesta repetida (turnos 6 y 14): la repetición la vigilará `repetition_watch` (CP10).

## 6. Frente a las expectativas de la fase

- **Ya se cumple en esta sesión:**
  - modelos de persona sin cruces;
  - recuerdo de lo dicho por otra persona, bien atribuido;
  - ánimo que persiste entre turnos y entre personas;
  - vía baja;
  - latencias.
- **Riesgos para el cierre de la fase** (el criterio de §11 se mide en CP11):
  1. **Saturación del afecto:** con N 0,75 y g_neg alto, una conversación hostil deja el VAD en el extremo. Afecta a la medición de vidas medias de CP11 (habría que partir de un impulso que no sature).
  2. **Falsos positivos del appraisal:** hostilidad ante temas hostiles, angustia ante «ADIOS!». Contaminan el afecto y el modelo de la persona.
  3. **Bug de normalización** de temas («adio»).
- Nada de esto lo resuelve CP8. Propuesta: anotarlos en `pendientes_y_limitaciones.md` y decidir en CP9–CP11 cuáles se corrigen (el bug de normalización es barato).

## 7. Coherencia de la valencia (análisis pedido por el usuario)

**Cómo se mueve.** Cada mensaje suma un impulso de tres partes, y entre mensajes el ánimo vuelve despacio a su reposo:
- *metas:* `0,3 · g · goal_congruence`, con g_neg 1,75 o g_pos 1,425 en Calisto. Un ataque (−0,9) suma −0,47 y un halago (+0,9), +0,39;
- *empatía («como si»):* `0,5 · π · (valencia ajena − propia) · (1 − hostilidad)`, con π 0,44. Tira hacia el ánimo de quien habla, más fuerte cuanto más lejos está. Con Calisto en −1 y alguien neutro, suma +0,22;
- *drives:* el alivio de `social` y `novelty` da un poco de placer (+0,01 a +0,08);
- *regreso al reposo* (−0,04): la parte negativa tarda 42,5 min en recorrer la mitad del camino. Entre mensajes separados por segundos casi no se nota: en esta sesión el ánimo lo movieron los impulsos, no el tiempo.

| # | Persona y mensaje | Metas | Empatía | Valencia tras el turno | ¿Coherente? |
|---|---|---|---|---|---|
| 1 | Ana: «Quien es?» | 0 | +0,01 | −0,02 | ✔ |
| 2 | Ana: «Quien te preguntó tanto detalle?» | −0,47 | −0,03 | −0,52 | ✔ |
| 3 | Ana: «y quien mierda es Ricardo?» | −0,47 | −0,01 | −0,99 | ✔ |
| 4 | Ana: «que accidente weona?» | 0 | +0,12 | −0,84 | ✔ (pregunta sin ataque) |
| 5–7 | Ana: ataques y «Callate mierda» | −0,47 a −0,53 | ~0 | −1,00 (tope) | ✔ dirección; ✖ el tope oculta la intensidad |
| 8 | Ana: «no me digas, eres una genio...» | **+0,39** | **+0,35** | **−0,24** | ✖ sarcasmo leído como halago: la mayor subida de la sesión |
| 9–11 | Ana: burlas de «máquina» | −0,42 a −0,47 | ~0 | −0,72 → −1,00 | ✔ |
| 12 | Ricardo: «Hola Calisto! ¿Cómo va todo?» | 0 | +0,22 | −0,75 | ⚠ un saludo neutro sube 0,25 solo por la empatía |
| 13 | Ricardo: «Ana quería conocerte con mucha emoción» | +0,39 | +0,34 | **−0,02** | ⚠ de −0,75 a neutro de golpe: el appraisal no sabe que Ana la acaba de insultar |
| 14 | Ricardo: «¿Qué te dijo que eras desagradable?» | **−0,53** | −0,02 | −0,56 | ✖ preguntar por un insulto se leyó como insulto (hostilidad 0,9) |
| 15–16 | Ricardo: «necesito saber…», «qué idiota es Ana… te prometo» | −0,47 / −0,37 | ~0 | −1,00 | ✖ apoyo leído como ataque |
| 17 | Ricardo: «estoy sorprendido…» | −0,21 | +0,09 | −1,00 | ⚠ |
| 18 | Ricardo: «no quiero que te haga daño» | +0,17 | +0,18 | −0,63 | ✔ |
| 19 | Ricardo: «¿Estás insinuando que yo te hago daño?» | −0,32 | +0,01 | −0,93 | ✔ (es una tensión real) |
| 20 | Ricardo: «si no quieres no me cuentes… me tengo que ir» | 0 | +0,27 | −0,65 | ⚠ |
| 21 | Ricardo: «ADIOS!» | 0 | −0,08 | −0,73 | ✔ |

**Lectura**
- **La dirección es coherente en unos 14 de 21 turnos.** Las incoherencias tienen tres causas, y ninguna es un error de las fórmulas: hacen lo que dicen.
  1. **El appraisal evalúa cada mensaje aislado, sin la conversación.** Por eso no ve el sarcasmo (8), no sabe que «Ana quería conocerte» suena mal después de los insultos (13) y lee como ataque el apoyo de Ricardo sobre un tema hostil (14–16). Es la causa principal.
  2. **Los impulsos son grandes frente al rango:** un solo mensaje mueve hasta ±0,5 y, con la empatía, hasta +0,75. Los fijó D1-23 a ojo, como calibrables, y nunca se compararon con una conversación real.
  3. **El efecto rebote del tope:** en −1, la empatía hacia alguien neutro es máxima (+0,22), y cualquier mensaje no negativo produce una subida grande. Un ánimo real tiene más inercia: un insulto más no baja de −1, pero un saludo sí sube 0,25.
- **Propuestas** (no se implementan ahora; se deciden en CP9–CP11):
  - dar al appraisal el último intercambio como contexto (habría que volver a medir el benchmark congelado del appraisal);
  - impulsos que pierdan fuerza cerca del extremo (saturación suave) y menos empatía cuanto más baja la confianza o más hostil fue la persona (que el `partner_model` modere el «como si»);
  - recalibrar las escalas de D1-23 con conversaciones reales.
