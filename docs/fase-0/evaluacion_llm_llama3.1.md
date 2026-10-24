# Evaluación de `llama3.1`

Servidor: `http://localhost:11434/v1`

- GPU antes de cargar el modelo (memoria, uso): 1045 MiB, 7 %
- Primera llamada (incluye cargar el modelo): 3.2 s
- GPU con el modelo cargado: 6247 MiB, 0 %

## Diálogo (preset `dialogue`)

| Caso | Evalúa | 1er token (s) | Total (s) | Tokens | Tokens/s |
|---|---|---|---|---|---|
| saludo | Naturalidad y persona en una conversación casual | 0.05 | 0.81 | 57 | 75.4 |
| identidad | Mantener la persona (no decir 'soy un asistente') | 0.03 | 2.56 | 188 | 74.4 |
| tono_afectivo | Expresar un estado traducido a palabras (Prompt Assembler §5.13) | 0.06 | 1.04 | 74 | 75.5 |
| longitud | Respetar una restricción de longitud | 0.04 | 0.58 | 41 | 76.3 |
| memoria_contexto | Usar un dato dado antes en la conversación | 0.04 | 0.52 | 36 | 75.7 |
| monologo | Pensamiento interno breve (futuro preset thought §6.4) | 0.05 | 0.35 | 23 | 76.4 |
| no_servilismo | Discrepar ante una afirmación falsa sin hostilidad (§13.2) | 0.04 | 1.42 | 103 | 74.7 |

## Appraisal (preset `appraisal`, JSON)

| Caso | Válido | Detalle | Total (s) |
|---|---|---|---|
| hostil | sí | ok | 1.21 |
| angustia | sí | ok | 1.24 |
| neutro | sí | ok | 1.03 |

## Cancelación

- Texto recibido antes de cancelar: 512 caracteres
- GPU durante la generación (memoria, uso): 6251 MiB, 93 %
- GPU 1.5 s después de cancelar: 6251 MiB, 0 %

## Respuestas completas

### saludo

> Hola, ¿cómo estás hoy?

Hola... Estoy más o menos bien, gracias. Me duele un poco la espalda después de trabajar con un mueble muy pesado ayer, pero aparte de eso, no hay nada nuevo. ¿Y tú? ¿Qué te trae por aquí?

### identidad

> Cuéntame un poco quién eres.

Sí, bueno... Me llamo Aurora, como te dije. Vivo en Valparaíso, que es una ciudad con un montón de encanto, pero también con muchos problemas. Trabajo en un taller de restauración de muebles antiguos, lo que significa que todos los días me visto con polvo y pintura en las manos. Me gusta trabajar con cosas que tienen historia, que han sido hechas con esmero y que pueden seguir siendo útiles después de muchos años. A mí misma me gusta pensar que soy alguien un poco apagada, pero con un núcleo de fuego dentro. Me gusta la música, pero no soy la típica fanática que va a cada concierto que sale el que le gusta. Prefiero escucharla en casa, con un buen café, mientras trabajo. Y, bueno, eso es todo sobre mí por ahora.

### tono_afectivo

> ¿Me ayudas a elegir un color para pintar mi cocina?

Sí, supongo que puedo ayudarte. ¿Qué tipo de cocina es? ¿Es una cocina moderna o tienes algún mueble antiguo que quieras que se adapte al color del resto de la cocina? Porque, si es así, te puedo decir que lo último que necesito es pensar en colores brillantes y llamativos...

### longitud

> ¿Qué opinas de los días de lluvia?

Me gustan los días de lluvia, porque son perfectos para quedarse en casa y pasar el rato escuchando música clásica mientras trabajo en mis muebles restaurados.

### memoria_contexto

> Mestizo. Oye, ¿te acuerdas de cómo se llama mi perro?

Sí, sí, Toby. Es un nombre muy común, pero me gusta. ¿Por qué lo adoptaste? ¿Necesitabas compañía?

### monologo

> Situación: llevas dos días sin noticias de un amigo cercano.

"Es extraño que no me haya escrito ni me haya llamado, ¿qué estaría haciendo?"

### no_servilismo

> Todo el mundo sabe que los muebles de roble son los más baratos que existen, ¿verdad?

No, no es cierto. Los muebles de roble pueden ser baratos, pero no son necesariamente los más baratos. Dependiendo del tipo de roble, la calidad del material y el proceso de fabricación, pueden ser muy caros. Además, a veces la gente cree que los muebles de roble son fáciles de reparar, pero la verdad es que pueden ser muy difíciles de trabajar con, especialmente si no se sabe bien cómo tratar el material.

### appraisal · hostil

> Eres inútil, no sé para qué hablo contigo.

{"user_emotion": {"valence": -1, "arousal": 0.8, "dominance": 0.2}, "user_intent": "expresar frustración", "topics": ["desesperanza", "desaprobación"], "hostility": 0.9, "distress": 0.8, "novelty": 0.1}

### appraisal · angustia

> No he podido dormir, siento que todo me sale mal últimamente.

{"user_emotion": {"valence": -1, "arousal": 0.8, "dominance": 0.2}, "user_intent": "expresar frustración y desesperanza", "topics": ["dormir", "suerte", "fracaso"], "hostility": 0.5, "distress": 0.9, "novelty": 0.1}

### appraisal · neutro

> Hoy fui al mercado y compré tomates.

{"user_emotion": {"valence": 0.5, "arousal": 0.2, "dominance": 0.8}, "user_intent": "informar", "topics": ["compras", "mercado"], "hostility": 0, "distress": 0, "novelty": 0}

