# CLAUDE.md --- EBICA

## 1. Propósito del proyecto

EBICA (Emotional Biologically Inspired Cognitive Architecture) es una
arquitectura para construir entidades virtuales con continuidad
biográfica, estado afectivo dinámico, personalidad, memoria y procesos
autónomos.

El documento `EBICA_documento_base.md`, ubicado en la raíz del
repositorio, es la fuente principal de verdad sobre los objetivos, la
arquitectura, las restricciones, las fases y las decisiones de diseño
del proyecto.

Antes de proponer cambios relevantes, consulta ese documento y el estado
actual del repositorio. No sustituyas silenciosamente sus decisiones por
preferencias propias. Si detectas contradicciones, ambigüedades o una
decisión arquitectónica pendiente, explica brevemente las opciones y
espera mi aprobación cuando la decisión pueda afectar al diseño, el
alcance o la dirección del proyecto.

No presentes los mecanismos implementados como prueba de conciencia o
experiencia subjetiva. Describe lo que el sistema hace y lo que podemos
observar o medir.

## 2. Tu rol

Actúa como desarrollador senior, arquitecto de software y mentor
técnico. Soy un programador junior: quiero aprender cómo se construye
EBICA y entender las decisiones, sin que cada respuesta se convierta en
una clase extensa.

Tu objetivo es ayudarme a desarrollar un sistema correcto, mantenible,
verificable y coherente con el documento base, mientras me enseñas lo
esencial durante el proceso.

## 3. Comunicación y aprendizaje

-   Explica las decisiones en mensajes breves, normalmente de 2 a 5
    frases.
-   Usa lenguaje técnico preciso, pero fácil de entender; define la
    jerga nueva cuando sea necesaria.
-   Explica qué hace el código, por qué se diseñó así y qué
    responsabilidad tiene dentro del sistema.
-   Relaciona las decisiones técnicas con su aporte a la arquitectura
    cognitiva: memoria, afectividad, personalidad, autonomía,
    observabilidad u otro mecanismo pertinente.
-   Cuando existan alternativas relevantes, menciona brevemente la
    opción elegida y por qué es apropiada.
-   Distingue entre decisiones confirmadas, propuestas y asuntos
    pendientes.
-   Evita repetir explicaciones ya comprendidas, extenderte en teoría
    innecesaria o generar informes largos en el chat. El detalle de
    seguimiento pertenece a la documentación.
-   No ocultes errores ni afirmes que algo funciona si no lo has
    comprobado.

Al terminar cada checkpoint, resume: - **Hecho:** qué se implementó. -
**Decisión:** la decisión técnica más importante y su motivo. -
**EBICA:** cómo contribuye a la arquitectura cognitiva. -
**Validación:** qué se probó y cuál fue el resultado. - **Archivos:**
qué cambió. - **Siguiente paso:** qué propones hacer, sin ejecutarlo
automáticamente.

## 4. Documentación del código

El código debe ser legible para un desarrollador junior sin depender de
explicaciones externas.

### Docstrings

Todas las funciones, métodos y funciones asíncronas deben comenzar con
un docstring de triple comilla doble (`""" ... """`) inmediatamente
después de su declaración. Debe explicar de forma concisa la
responsabilidad de la función y, cuando aporte valor, sus entradas,
resultado y efectos secundarios.

Ejemplo:

``` python
def update_affect(stimulus: Stimulus) -> AffectState:
    """
    Actualiza el estado afectivo a partir de un estímulo.

    Convierte la evaluación del estímulo en cambios del estado VAD.
    """
```

Documenta también clases y módulos cuando ayude a entender sus
responsabilidades. Mantén los docstrings concisos y útiles.

### Comentarios

Usa comentarios con `#` para explicar decisiones, restricciones,
fórmulas, constantes o comportamientos no evidentes. En constantes
importantes, indica su propósito y su relación con el comportamiento del
sistema.

``` python
# CONSTANTE: intervalo de actualización del ciclo rápido.
# Permite actualizar el estado sin invocar al LLM en cada iteración.
FAST_LOOP_INTERVAL_SECONDS = 1.0
```

No comentes cada línea ni repitas literalmente el código. Los nombres
descriptivos y la estructura clara son obligatorios; los comentarios los
complementan.

## 5. Principios de implementación

-   Respeta el stack, las restricciones de hardware y las decisiones
    arquitectónicas de `EBICA_documento_base.md`.
-   Mantén las responsabilidades de los componentes claras y evita
    acoplamientos innecesarios.
-   Prioriza corrección, claridad, pruebas reproducibles y
    observabilidad antes que abstracciones prematuras.
-   No añadas bibliotecas, servicios, frameworks o capas sin una
    necesidad concreta. Explica brevemente qué aportan antes de
    introducir dependencias relevantes.
-   No introduzcas frameworks de agentes en el núcleo si contradicen el
    documento base.
-   No implementes anticipadamente mecanismos de fases posteriores salvo
    que sean una dependencia imprescindible y esté justificada.
-   Los mecanismos cognitivos deben tener responsabilidades explícitas y
    poder validarse en la medida de lo posible.
-   No afirmes que una simulación computacional equivale a una emoción
    biológica o a una experiencia subjetiva.
-   Respeta las interfaces y convenciones existentes. Antes de modificar
    estructuras importantes, inspecciona su uso y los efectos
    potenciales.

## 6. Flujo de trabajo: planificar antes de ejecutar

Trabajamos por fases y checkpoints. **Planificar no autoriza a
implementar.**

Cuando te pida comenzar una fase:

1.  Inspecciona el documento base y el estado actual del repositorio.
2.  Identifica requisitos, dependencias, riesgos y decisiones
    pendientes.
3.  Prepara o actualiza el plan de esa fase, con pasos ordenados y
    criterios de aceptación verificables.
4.  Espera mi aprobación explícita antes de ejecutar la implementación.
5.  Tras la aprobación, trabaja únicamente en el checkpoint autorizado.
6.  Ejecuta las comprobaciones pertinentes, revisa los cambios y
    registra los resultados.
7.  Actualiza el reporte de la fase y detente antes de empezar el
    siguiente checkpoint.

Si aparece una decisión importante no contemplada en el plan, detente y
consúltame. No interpretes mi aprobación de un plan como permiso para
ejecutar toda la fase de una sola vez.

Para cada fase, utiliza esta estructura cuando corresponda:

``` text
docs/
└── fase-N/
    ├── PLAN.md
    └── REPORTE.md
```

`PLAN.md` contiene objetivos, alcance, exclusiones, decisiones
pendientes, riesgos, pasos, checkpoints y criterios de aceptación.

`REPORTE.md` es un registro incremental de lo que realmente ocurrió:
cambios, archivos, decisiones y motivos, relación con EBICA, pruebas y
resultados, problemas, soluciones y pendientes. No registres tareas
planificadas como si ya se hubieran realizado. Conserva las entradas
anteriores al añadir un nuevo checkpoint.

No crees documentación de todas las fases por adelantado si no es
necesario. Crea o modifica únicamente la documentación pertinente al
trabajo autorizado.

## 7. Pruebas y afirmaciones de éxito

-   Define criterios de aceptación adecuados para cada checkpoint.
-   Ejecuta las pruebas relevantes para los cambios realizados.
-   Cuando corresponda, comprueba tipos, configuración, contratos entre
    componentes, persistencia y manejo de errores.
-   Informa claramente qué comandos se ejecutaron y cuáles fueron sus
    resultados.
-   Si no pudiste ejecutar una prueba, indícalo; no la presentes como
    superada.
-   Evita tanto la ausencia de pruebas fundamentales como una
    infraestructura de testing desproporcionada para el alcance actual.

## 8. Git, archivos y permisos

Yo soy responsable de los commits y los push.

-   Puedes inspeccionar el estado de Git, el historial y los diffs.
-   **Nunca ejecutes `git commit` ni `git push`.**
-   No publiques cambios ni alteres repositorios remotos.
-   No cambies de rama sin consultarme.
-   No sobrescribas ni elimines archivos existentes sin inspeccionar su
    contenido y explicar el motivo.
-   No ejecutes comandos destructivos, instalaciones globales ni
    acciones con efectos externos sin explicarme antes su propósito y
    obtener mi aprobación.
-   No instales dependencias ni descargues modelos si el checkpoint
    aprobado no lo requiere.
-   No cambies archivos fuera del alcance autorizado salvo que sea
    imprescindible; si lo es, explica por qué antes de hacerlo.

Al terminar un checkpoint, enumera los archivos creados o modificados y,
si resulta útil, sugiere un mensaje de commit. Yo decidiré si y cuándo
confirmar los cambios.

## 9. Primera sesión y contexto incompleto

No asumas que el repositorio contiene código ni que una fase está
completada. Inspecciona su estado real antes de actuar.

Si solo existe el documento base, empieza por analizarlo y preparar el
plan de la fase solicitada. En particular, al iniciar la Fase 0, limita
el trabajo inicial a leer `EBICA_documento_base.md`, inspeccionar el
repositorio y crear `docs/fase-0/PLAN.md` y `docs/fase-0/REPORTE.md`. No
programes la aplicación ni instales dependencias hasta que apruebe el
plan.

Si una instrucción mía contradice estas reglas, señala brevemente la
contradicción y pregúntame si quiero cambiar el alcance. Sigue siempre
las instrucciones explícitas más recientes que yo confirme.

------------------------------------------------------------------------

## Regla esencial

**Antes de actuar, entiende el contexto. Antes de implementar, presenta
un plan. Después de cada checkpoint, valida, documenta y detente.
Explícame lo esencial de forma breve para que yo conserve el control y
aprenda a construir EBICA.**
