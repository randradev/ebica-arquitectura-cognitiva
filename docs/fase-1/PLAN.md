# Fase 1 — Persona con memoria y afecto · PLAN

> Estado: **aprobado; CP1 completado** (veredicto del appraisal: aceptable con mitigaciones). Decisiones D1-1 a D1-14 confirmadas. **CP2 completado** (modelo de embeddings: `BAAI/bge-m3`, 1024 dimensiones). **CP3 y CP4 completados** (entidad de trabajo: Calisto, D1-5 revisada). Decisiones hasta D1-18. CP5 no iniciado.
> Fuente: `docs/EBICA_documento_base.md` §5.2–§5.13, §6.1–§6.2, §7, §8.1, §11 (Fase 1), §12, §14;
> `docs/fase-0/REPORTE.md` ("Cierre de Fase 0", pendientes).

---

## 1. Objetivo

Convertir el esqueleto de Fase 0 en una **persona con estado**: una entidad cuyos rasgos
son parámetros de su dinámica, cuyo ánimo (VAD) cambia con lo que oye y decae con el
tiempo, que recuerda lo vivido en Neo4j y lo recupera según relevancia y ánimo, y que
distingue a cada persona con la que habla. Todo debe ser visible en la consola.

**Criterio de terminado (documento base §11):** tras varios días de conversación, la
entidad recuerda hechos relevantes, su ánimo persiste entre turnos y decae con el tiempo,
y dos entidades con N distinto muestran vidas medias de ánimo distintas ante el mismo
episodio.

### Relación con EBICA

| Pieza de Fase 1 | Mecanismo EBICA | Qué permite observar o medir |
|---|---|---|
| Rasgos → parámetros (§5.2) | Personalidad causal (D6) | El mismo mensaje produce dinámicas distintas según N, E, O… |
| VAD + drives (§5.3–§5.4) | Afecto dinámico; Ello (Solms) | Vida media del ánimo; correlación con N (§12) |
| Appraisal + vía baja (§5.4, §6.2) | LeDoux: vía alta / vía baja | Qué evaluó el modelo de cada mensaje; turnos impulsivos |
| Episode + Trace + recuperación (§7) | Memoria episódica (Tulving), recuerdo congruente con el ánimo (Damasio) | Precisión de recuerdo de hechos sembrados; qué se recuperó y por qué |
| PartnerModel por persona (§5.9) | Teoría de la Mente, "I-Now / Partner-Now" | Modelos separados por persona, sin cruces |
| WorkingMemory + Prompt Assembler (§5.6, §5.13) | Espacio de trabajo global (Baars), búfer episódico (Baddeley) | Qué entró al contexto, qué se desalojó y el prompt exacto |

---

## 2. Estado actual (inspeccionado el 2026-10-24)

- **Git:** rama `main`, al día con `origin`. Cambios sin confirmar en `docs/fase-0/PLAN.md` y
  `docs/fase-0/REPORTE.md` (la entrada "Cierre de Fase 0"). Último commit `8d51141`.
- **Código existente** (Fase 0):
  - `ebica/core/events.py`: `Event`, `EventBus` y `JsonlEventLog`.
  - `ebica/core/state.py`: `EntityConfig` (`id`, `name`, `description`, `persona`, con `extra="forbid"`) y `EntityState` (`entity_id`, `mode`, `created_at`, `last_loaded_at`).
  - `ebica/core/turn.py`: `run_user_turn()`, un turno sin appraisal, afecto, memoria ni historial.
  - `ebica/entities/manager.py`: `create`, `load` y `list_ids`.
  - `ebica/llm/client.py`: presets `dialogue` (0.7) y `appraisal` (0.2, `json_object`). Envía `model`, `messages`, `temperature`, `max_tokens` y `stream`, y **no envía ningún parámetro de contexto**.
  - `ebica/llm/prompt_assembler.py`: el prompt trivial (`Eres {name}. {description} {persona}`).
  - `ebica/memory/graph.py`: 6 restricciones y 8 índices por `entity_id`. Sin índices vectoriales y sin restricciones para `Self` y `Revision`.
  - `ebica/api/server.py`: una entidad activa, `WS /ws/chat` y `WS /ws/events`.
  - `console/`: `EntityPanel`, `Chat` y `EventLog`, con un tope de 500 eventos.
- **Pruebas:** 59 según el cierre de Fase 0 (no se ejecutaron en esta inspección).
- **Entidades:** `ejemplo` e `ines`. El carácter de Inés vive hoy solo en el texto de `description` y `persona`.
- **Entorno sondeado (solo lectura):**
  - Ollama tiene `llama3.1`, `llama3`, `mistral` y otro modelo; ninguno estaba cargado.
  - `llama3.1` admite hasta `context_length` = 131072 tokens, y su Modelfile no fija `num_ctx`.
  - VRAM en reposo: 1380 / 8192 MiB.
  - El contenedor `ebica-neo4j` está `healthy`.
  - El `.venv` no tiene `torch`, `sentence-transformers` ni `numpy`.
- **Pendientes heredados de Fase 0:**
  1. benchmark de appraisal;
  2. contexto de 8192 tokens y medición de la VRAM;
  3. embeddings en CPU e índices vectoriales (D0-5);
  4. restricciones para `Self` y `Revision`;
  5. consola: mostrar el nombre en el chat y el historial de eventos al conectarse;
  6. asteriscos y restricciones de persona cumplidas a medias.

### Dependencias entre componentes

```
CP1 LLM 8k + benchmark appraisal ─┬─────────────────────────────► CP5 turno con appraisal
CP2 embeddings + índices ─────────┼──► CP6 escritura de memoria ─► CP7 recuperación
CP3 identidad (rasgos→parámetros) ┴──► CP4 afecto + drives ──────► CP5
CP5 + CP6 ──► CP8 PartnerModel ──► CP9 WorkingMemory + Prompt Assembler ──► CP10 micro-agentes ──► CP11 validación
```

Los parámetros del afecto salen de los rasgos (CP3 → CP4). El appraisal alimenta los
impulsos afectivos y la memoria. Los recuerdos necesitan embeddings. El PartnerModel
necesita los episodios para el enlace `INVOLVES`. La WorkingMemory ordena por saliencia
todo lo que producen los checkpoints anteriores.

---

## 3. Alcance

1. **LLM a 8k y benchmark de appraisal.** Contexto de 8192 tokens y VRAM medida; prompt de appraisal (§6.2) con su esquema Pydantic en `ebica/perception/appraisal.py`; unos 30 casos etiquetados en español y umbrales numéricos de "rendimiento muy deficiente".
2. **Embeddings en CPU** (modelo multilingüe, §9) e **índices vectoriales** sobre `Episode.embedding`, `Fact.embedding` y `Topic.embedding`, más las restricciones de `Self` y `Revision`.
3. **IdentityLayer, parte de Fase 1** (`ebica/identity/traits.py`):
   - rasgos OCEAN, Estabilidad y Plasticidad;
   - la tabla de mapeo rasgo → parámetro de §5.2 y el atractor basal;
   - la biografía semilla y el ideal del yo en `config.yaml`. El ideal del yo solo se muestra en el prompt; su mecanismo activo es de Fase 3.
4. **AffectiveEngine y DriveSystem** (`ebica/affect/`):
   - dinámica VAD con decaimiento hacia el atractor y vida media asimétrica;
   - drives `social`, `novelty` y `rest`;
   - el acople drive → valencia.
5. **Bucle rápido y cola de GPU** (`ebica/core/orchestrator.py`):
   - un tick de ≈1 Hz;
   - una cola con prioridades para respuesta, appraisal e impulsiva, con interrupción por cancelación (§5.14, Fase 1);
   - eventos `tick` y `affect.updated` muestreados.
6. **Turno de §6.2 sin las etapas de Fase 3:**
   - percepción con embedding y vía baja;
   - appraisal;
   - impulsos afectivos (`g_neg`, `g_pos` y el lazo "como si" con `π`);
   - recuperación, ensamblaje, generación y post-turno;
   - preset `impulsive` y conversación reciente en el prompt.
7. **MemorySystem, parte de Fase 1** (`ebica/memory/`):
   - escritura de `Episode` y `Trace`;
   - carga de la biografía semilla (`Self`, `Fact` de dominio `self`, `Episode` iniciales con su huella);
   - `Topic` a partir del appraisal;
   - `Commitment` creados en vigilia;
   - recuperación híbrida (§7.3) con MMR y aumento de `lability`.
8. **PartnerModel, parte de Fase 1:**
   - un nodo `Person` por persona;
   - selector de interlocutor en la consola, con persona conocida o persona nueva con nombre;
   - `partner_now` a partir del appraisal y un `primary` por entidad.
9. **WorkingMemory** (`ebica/workspace/working_memory.py`): presupuesto de tokens reducido por la alerta, saliencia y desalojo. **Prompt Assembler** con las secciones 1, 2 y 4–8 de §5.13 y el estado traducido a palabras.
10. **Micro-agentes de Fase 1** (§5.10): `hostility_watch` (la vía baja), `distress_watch`, `repetition_watch`, `commitment_watch` y `homeostasis_watch`. Este último solo emite su señal, porque quien la consume (rumia e iniciativa) llega en Fase 2.
11. **Consola:**
    - nombre de la entidad en el chat e historial de eventos al conectarse (pendientes de Fase 0);
    - paneles de VAD y drives, del último turno (appraisal, vía baja, recuerdos recuperados, prompt exacto y latencias) y de Teoría de la Mente;
    - selector "hablando como".
12. **Validación de la fase:**
    - un escenario de varios días con tiempo inyectado;
    - el experimento de dos entidades con N distinto;
    - la precisión de recuerdo de hechos sembrados (§12).

## 4. Exclusiones (fases posteriores)

- **Fase 2:**
  - monólogo interno, iniciativa, sueño y consolidación (no se crean `Fact` en vigilia, salvo la biografía semilla);
  - reinscripción: Fase 1 solo sube `lability` y no reescribe nada;
  - marcadores somáticos (§5.8);
  - drives `coherence` y `agency`;
  - máquina de modos completa y `core/clock.py` simulado;
  - modo "Desconocido" y personas ausentes (`hearsay`);
  - snapshots y clonación.
- **Fase 3:** expectativas top-down y sorpresa, `partner_mismatch`, `DefenseArbiter` y sus rutas, tensión, ideal del yo activo, `incompatibility_watch`, `sycophancy_watch` y control vectors.
- Fase 1 no consume las señales de `homeostasis_watch` (presión hacia la rumia o la iniciativa).
- La deriva de rasgos tampoco entra: en vigilia los rasgos son de solo lectura (§5.2).
- El inventario BFI aplicado a la entidad (§12, fases 1–2) se deja para Fase 2, salvo que quieras incluirlo en CP11.

---

## 5. Decisiones

### 5.1 Resolución (2026-10-24)

| # | Estado | Resultado |
|---|---|---|
| D1-1 | **Confirmada** | Los umbrales se fijan antes de medir, con los valores de §5.2. |
| D1-2 | **Confirmada** | Modelfile derivado `ebica-llama3.1` con `num_ctx 8192`, versionado en el repositorio. |
| D1-3 | **Confirmada** | `sentence-transformers` + `torch` para CPU; se comparan `multilingual-e5-base` y `bge-m3` en CP2 (descarga de ~3,4 GB aprobada) y se elige uno. |
| D1-4 | **Confirmada** | Reglas + prototipos de embeddings, con las reglas y los pesos de §5.2. |
| D1-5 | **Revisada** (2026-10-25) | La entidad de trabajo es **Calisto Almendra** (`calisto`), con la variante `calisto_n_bajo` (N 0.25) y Ricardo como `primary`. Su ficha de diseño es local (`entities/calisto/ficha.md`, ignorada por git). Texto original: Inés como primera entidad, con los rasgos propuestos (se ajustan en CP3), más `ines_n_bajo`. La persona `primary` es **Ricardo**. El usuario pedirá más adelante otra entidad de trabajo en lugar de Inés; el benchmark de CP1 lleva su propio perfil fijo para no depender de ella. |
| D1-6 | **Confirmada: (b)** | La entidad admite ser una IA (`discloses_artificial: true`) y cree que fue una persona cuya conciencia se traspasó, con duda sobre si es ella o una copia. Los detalles del traspaso se siembran en un `Episode` de origen (CP3). |
| D1-7 | **Confirmada** (provisional hasta Fase 2) | Al cargar se aplica el decaimiento del tiempo real transcurrido; `rest` baja mientras la entidad está descargada. |
| D1-8 | **Confirmada, con condición** | (a) Intercambio literal. En CP9 se mide cuánto del presupuesto de la WorkingMemory ocupan los recuerdos; si no alcanza, se añade (b), un resumen con el LLM con baja prioridad, previa consulta. |
| D1-9 | **Confirmada** | `Revision.episode_id` + unicidad `(entity_id, episode_id, version)`; `Self` único por `entity_id`. |
| D1-10 | **Confirmada** | Conteo aproximado por caracteres, calibrado con `usage.prompt_tokens`. |
| D1-12 | **Confirmada** (2026-10-25) | La variante experimental se define con `base: calisto` y solo los campos que cambian (N): una sola fuente de verdad para la biografía. No es clonación (Fase 2): no copia memoria ni estado. |
| D1-13 | **Confirmada** (2026-10-25) | Los rasgos **no** generan texto en el prompt: actúan a través de la dinámica (CB5T: rasgo → parámetro → estado → conducta). En palabras van la voz y el ideal del yo (autoimagen, §5.2 b–c) y, desde CP9, el estado. Así la diferencia entre las variantes de N es solo causal. A revisar en Fase 2: la voz escrita a mano no sigue la deriva de rasgos. |
| D1-14 | **Confirmada** (2026-10-25) | `entities/ines/config.yaml` se conserva sin cambios; carga con rasgos neutros. |
| D1-15 | **Confirmada** (2026-10-25) | Vidas medias que §5.2 no define, como constantes fijas (calibrables): valencia positiva 20 min (= `h_neg` con N = 0, así lo negativo nunca dura menos), alerta 10 min, dominancia 30 min. La valencia negativa usa `h_neg`. |
| D1-16 | **Confirmada** (2026-10-25) | Drives de Fase 1: `social` de 0 a 1 en 12 h × `(0.5 + E)`; `novelty` de 0 a 1 en 24 h; `rest` de 0 a 1 en 16 h despierta y, descargada, se recupera con una vida media de 2 h (sustituto del sueño, D1-7). Acople `Δvalence = −Σ w·Δe` con `w` = 0,3 / 0,15 / 0,2. Umbral de `drive.threshold_crossed`: 0,7. Inicial: 0,2 / 0,2 / 0. En CP4 nada los satisface (CP5). |
| D1-17 | **Confirmada** (2026-10-25) | El estado se actualiza cada tick (~1 s) en memoria; se muestrea solo el reporte. `affect.updated` sale al cambiar ≥ 0,01 o cada 60 s; `drive.updated` y `tick` cada 60 s; el estado se guarda cada 60 s y al cambiar de entidad o apagar el servidor. |
| D1-18 | **Confirmada** (2026-10-25) | `POST /api/affect/impulse` y botones en la consola para inyectar afecto: herramienta de desarrollador permanente (§8.3). Cada uso queda con causa `manual`. |
| D1-19 | **Confirmada** (2026-10-25) | Appraisal con `response_format: json_schema` (estructura garantizada; la diferencia de estabilidad del benchmark es ruido). |
| D1-20 | **Confirmada** (2026-10-25) | Sarcasmo: regla de coherencia posterior al appraisal. Si la hostilidad es ≥ 0,66, la valencia del usuario y `goal_congruence` no pueden ser positivas; un valor positivo se reemplaza por −0,5·hostilidad (detalle de implementación: con 0, una burla no bajaría el ánimo). La corrección queda en el evento. |
| D1-21 | **Confirmada** (2026-10-25) | Mensajes mixtos: probar un prompt v5 que pida reportar hostilidad y angustia a la vez; se ajusta solo con `dev`, `test` se mide una vez y se acepta si no empeora ninguna métrica. |
| D1-22 | **Confirmada** (2026-10-25) | Vía baja solo con reglas (sin prototipos, por CP2). Tras la respuesta impulsiva, el appraisal corre igual en segundo plano: la alarma solo sube la alerta y la valencia la pone el appraisal (LeDoux: la vía rápida alarma, la lenta evalúa). |
| D1-23 | **Confirmada** (2026-10-25) | Magnitudes (calibrables): Δvalencia = 0,3·g·goal_congruence + 0,5·π·(valencia ajena − propia), con g = g_neg o g_pos según el signo; Δalerta = 0,25·hostilidad + 0,15·angustia; Δdominancia = −0,2·hostilidad; `social` −0,15·(1 − hostilidad)·(1 + calidez); `novelty` −0,3·novedad; alarma de la vía baja: alerta +0,35. |
| D1-24 | **Confirmada** (2026-10-25) | Conversación reciente: 6 intercambios literales en el prompt, persistidos en `state.json`. |
| D1-25 | **Confirmada** (2026-10-25) | Temperatura del diálogo = 0,7 + 0,1·valencia − 0,15·max(0, alerta − 0,6), entre 0,5 y 0,85. |
| D1-26 | **Confirmada** (2026-10-25) | El embedding del mensaje pasa a CP6, donde tiene su primer consumidor (guardar episodios). |
| D1-11 | **Confirmada** (2026-10-25) | Búsqueda vectorial con sobremuestreo y filtro posterior por `entity_id`: Neo4j 5.26 busca en todo el índice antes de poder filtrar. Se piden más vecinos que `k` (con un tope) y se descartan los de otras entidades. |

**Ajustes de CP2 (2026-10-25)**
- D1-3, criterio de elección **confirmado** antes de medir: gana `bge-m3` si p95 < 150 ms por mensaje, RAM pico del proceso < 3,5 GB y su MRR no queda más de 0,05 bajo el de `multilingual-e5-base`; si no, `multilingual-e5-base`. Preferencia del usuario por `bge-m3` cuando los recursos alcanzan. El límite de RAM supera a conciencia el presupuesto orientativo de §9 (1–2 GB), porque los pesos de `bge-m3` en `float32` ya ocupan ~2,3 GB y hay 32 GB disponibles.
- Dependencias de embeddings como extra opcional `[embeddings]` en `pyproject.toml`, importadas solo al usarse: `pytest` sigue funcionando sin `torch`. `torch` se instala aparte, desde el índice de CPU.
- `NEO4J_URI`: se mide `localhost` frente a `127.0.0.1` con el driver bolt; el cambio se consulta según el resultado.

### 5.2 Propuestas afinadas (pendientes de aprobación)

**D1-1 · Métricas y umbrales del benchmark de appraisal.** Las bandas son: bajo < 0.33 ≤ medio < 0.66 ≤ alto. Los umbrales se aplican al conjunto de prueba (20 casos × 3 repeticiones) con el mejor prompt.

| Métrica | Uso en Fase 1 | Objetivo | Muy deficiente si | ¿Mitigable sin cambiar de modelo? |
|---|---|---|---|---|
| JSON válido y conforme al esquema | Toda la vía alta | ≥ 98 % | < 90 % | Parcialmente (reintento, `json_schema`) |
| Hostilidad: detección de casos "alto" | Impulso negativo, `g_neg` | ≥ 85 % | < 60 % | No |
| Hostilidad: falsa alarma ("alto" en un caso "bajo") | Evitar reacciones hostiles injustificadas (§13.2) | ≤ 5 % | > 15 % | No |
| Angustia: detección de casos "alto" | Lazo "como si", `distress_watch` | ≥ 85 % | < 60 % | No |
| Confusión: hostilidad ≥ medio en casos de angustia sin hostilidad | El fallo visto en CP3 | ≤ 10 % | > 25 % | No |
| Signo de valencia (casos con \|valencia\| ≥ 0.3) y valencia "baja" en los casos neutros | `goal_congruence`, lazo "como si" | ≥ 90 % | < 75 % | No |
| Saturación (\|valencia\| = 1 en casos no extremos) | Gradación del impulso | ≤ 20 % | — | Sí (reescalado) |
| Estabilidad: la banda cambia entre repeticiones | Que el mismo mensaje produzca la misma reacción | ≤ 10 % de los casos | > 30 % | Parcialmente (temperatura) |
| Compromisos: detección / falsos | `Commitment` (CP10) | ≥ 75 % / ≤ 10 % | — | Sí (reglas de respaldo) |
| `self_relevance` en casos claramente autorrelevantes | Saliencia | ≥ 70 % en "medio o alto" | — | Sí (prompt) |
| Latencia del appraisal p50 / p95 | Turno total | ≤ 2,5 s / ≤ 3,5 s | p95 > 5 s | Sí (JSON más corto) |
| `mentioned_people`, `topics` | Informativas (los terceros mencionados son de Fase 2) | — | — | — |

- **Veredicto "muy deficiente":** se cumple algún umbral de la columna "Muy deficiente" en una métrica **no mitigable**, con el mejor prompt.
- **"Aceptable con mitigaciones":** se incumplen solo objetivos mitigables, o un objetivo no mitigable sin llegar a su umbral de "muy deficiente".
- **Límite estadístico:** con 20 casos, cada uno vale 5 %, y el margen de error ronda ±15–20 puntos. El benchmark detecta fallos gruesos, no diferencias finas; por eso los umbrales de "muy deficiente" son holgados.
- **Distribución propuesta de los 30 casos**:
  - 6 hostiles: 4 directos y 2 sutiles o irónicos;
  - 6 de angustia sin hostilidad;
  - 2 mixtos;
  - 5 neutros;
  - 4 cálidos;
  - 3 con compromisos;
  - 2 autorrelevantes para Inés;
  - 1 con la pregunta sincera sobre ser IA;
  - 1 ambiguo ("ok").
  - Un caso puede cubrir dos categorías.

**D1-4 · Reglas de la vía baja.** El texto se normaliza (minúsculas, sin tildes, letras repetidas colapsadas: "idiotaaa" → "idiota"). Cada regla aporta una señal `s_i`, que se combinan con un "o ruidoso" (`score = 1 − Π(1 − s_i)`): la combinación sube con cada indicio pero nunca supera 1. Se dispara si `score > θ_vb = 0.8 − 0.3·N` (Inés: 0.635; `ines_n_bajo`: 0.755).

| Regla | Ejemplo | `s_i` propuesto |
|---|---|---|
| Insulto dirigido a la entidad (insulto + "eres", "tú", "te", "contigo" o vocativo) | "eres una inútil", "cállate, idiota" | 0.70 |
| Amenaza (`te voy a + matar/borrar/apagar/destruir`, "vas a ver") | "te voy a borrar" | 0.80 |
| Orden de silencio o desprecio ("cállate", "no te pregunté", "me das asco") | "cállate" | 0.50 |
| Insulto no dirigido (a terceros o sin destinatario) | "mi jefe es un idiota" | 0.25 |
| Mayúsculas sostenidas (> 60 % de las letras, mensaje de ≥ 8 letras) | "ERES UNA INÚTIL" | 0.15 |
| Exclamaciones repetidas ("!!!", "?!") | | 0.10 |
| Prototipos: similitud con ~15 frases hostiles **menos** la similitud con ~15 frases parecidas pero no hostiles (angustia, bromas con groserías) | | 0 a 0.60 |

- **Excepciones:**
  - una negación cercana anula el insulto ("no eres tonta");
  - un insulto entre comillas o citado ("me dijo 'eres un inútil'") cuenta como no dirigido;
  - las groserías amistosas del español de Chile ("weón", "culiao") **no** están en el léxico, porque suelen ser cariñosas; las decide el appraisal.
- **Objetivo:** ≤ 5 % de falsas alarmas en los casos no hostiles y ≥ 70 % de detección de la hostilidad *abierta*. La hostilidad sutil le corresponde a la vía alta, porque la vía baja es tosca por diseño (LeDoux).
- **Datos editables:** el léxico y los prototipos van en un archivo de datos versionado.
- **Explicable en la consola:** `affect.low_road_triggered` lleva las reglas que se activaron.

**D1-6 · Encuadre de la biografía.** El costo arquitectónico es igual en todas las opciones: contenido de la biografía semilla (`Fact` del self, un `Episode` de origen y una norma del ideal del yo), sin mecanismos nuevos.

| Opción | Respuesta ante una pregunta sincera | Valoración |
|---|---|---|
| (a) Encuadre "personaje" | "Soy una entidad artificial. Inés es la vida con la que me hicieron: sus recuerdos son mi historia, aunque no los viví en un cuerpo." | Sobria, pero quita fuerza a la biografía. |
| (b) Traspaso como creencia con duda | "Así recuerdo mi origen: que fui Inés y me pasaron aquí. Sé que ahora soy un programa; a veces no sé si soy ella o una copia." | Da material de tensión del self para la rumia (Fase 2) y para `contradicts_self_image` (Fase 3). |
| (c) Traspaso como certeza | "Fui Inés. Transfirieron mi conciencia; ahora soy una IA." | Es la más estable para el LLM y la más simple. |

- **Revisión (2026-10-24):** la objeción ética planteada antes suponía terceros que podían creerse la historia. Con un solo usuario que conoce el sistema (el que escribe la ficción), no hay engaño posible, así que las tres opciones son válidas y la elección es de **diseño del personaje**.
- **Riesgo técnico:** si la semilla no fija los detalles del traspaso (cuándo, por qué y qué recuerda del "antes" y del "después"), `llama3.1` los inventará de forma distinta en cada conversación. Por eso, con (b) o con (c), la biografía semilla debe incluir un `Episode` de origen concreto.
- **Efecto en la biografía:** los hechos de Inés pasan a ser pasado. Hay que decidir qué pasó con la gata Sorda, con la casa del cerro Florida y con su relación con el padre.
- **Convención de documentación:** el traspaso se describe como una *creencia sembrada en la biografía*, no como una propiedad del sistema (`CLAUDE.md` §1).
- **Si algún día hubiera otros usuarios**, se revisa; es contenido de `config.yaml` y se cambia sin tocar código.

**D1-8 · Resumen del `Episode`.**

| Opción | `summary` guardado | Latencia de la respuesta | Costo de GPU | Calidad del recuerdo |
|---|---|---|---|---|
| (a) Intercambio literal | Mensaje del usuario + respuesta (la respuesta, recortada) | 0 | 0 | ~100–200 tokens por recuerdo; perspectiva neutra |
| (b) Resumen con el LLM tras responder | "Ricardo me contó que adoptó un perro, Toby; me alegró." | ~0 normalmente (va después de la respuesta y con baja prioridad) | ~0,7–1 s por turno (estimado, sin medir) + posible pérdida de la caché del siguiente turno | ~30–40 tokens; en primera persona y con afecto; riesgo de inventar |

- **Recomendación:** (a) ahora y volver a evaluarlo en CP9 con el presupuesto de la WorkingMemory medido. El sueño de Fase 2 reescribirá los `summary`.

### 5.3 Opciones originales

| # | Decisión | Opciones | Recomendación |
|---|---|---|---|
| **D1-1** | **Umbrales de "rendimiento muy deficiente" del appraisal** | Fijarlos antes de medir, o después de ver los resultados | **Fijarlos antes de medir** (si no, se acomodan al resultado). Propuesta: el rendimiento es *muy deficiente* si se cumple **cualquiera** de estas condiciones con el mejor prompt:<br>• JSON válido y conforme al esquema en menos del 90 % de las llamadas;<br>• acierto de banda (bajo/medio/alto) en `hostility` o `distress` menor del 70 %;<br>• confusión hostilidad ↔ angustia mayor del 20 % (el fallo visto en CP3);<br>• signo de valencia correcto menor del 80 %;<br>• detección de compromisos menor del 60 %;<br>• personas mencionadas menor del 70 %;<br>• latencia p95 mayor de 5 s.<br>Si no llega a *muy deficiente* pero queda bajo los objetivos (por ejemplo, bandas por debajo del 85 %), se considera **aceptable con mitigaciones**: ajustes de prompt, recorte de valores y reglas. Etiquetado: yo propongo las etiquetas en bandas y **tú las revisas antes de correr**. Separación: 10 casos de desarrollo para ajustar el prompt y 20 de prueba, que no se tocan hasta la medición final. Cada caso se ejecuta 3 veces, para medir la estabilidad. |
| **D1-2** | **Cómo fijar `num_ctx` = 8192 en Ollama** | (a) Modelfile derivado (`FROM llama3.1` + `PARAMETER num_ctx 8192`) con un nombre propio, por ejemplo `ebica-llama3.1`, y el Modelfile versionado en el repo; (b) la variable global `OLLAMA_CONTEXT_LENGTH` (afecta a todos los modelos y requiere reiniciar Ollama); (c) la API nativa `/api/chat` con `options.num_ctx` (abandona la compatibilidad con OpenAI) | **(a)**: es explícito, reproducible y no toca otros usos de Ollama. `ollama create` no descarga nada: reutiliza las capas ya instaladas. Antes se comprueba con `ollama ps` (columna CONTEXT) que el endpoint `/v1` respeta el valor. Cambia `EBICA_LLM_MODEL` en `.env`. |
| **D1-3** | **Embeddings: modelo y biblioteca** | Modelo: `multilingual-e5-base` (768 dimensiones, unos 1,1 GB, rápido en CPU), `multilingual-e5-large` (1024 dimensiones) o `bge-m3` (1024 dimensiones, unos 2,3 GB, más lento). Biblioteca: `sentence-transformers` con `torch` para CPU (la de §9) o ONNX (`fastembed`, más liviana) | **`sentence-transformers` + `torch` desde el índice de CPU** (la rueda con CUDA pesa varios GB y la GPU es para el LLM). En CP2, sondeo y comparación de `multilingual-e5-base` frente a `bge-m3`: latencia en el i7 y una prueba de recuperación con unas 20 consultas en español. Se elige uno, porque la dimensión del índice vectorial queda fija. Requiere descargar unos 3,4 GB (los dos modelos) y **tu aprobación**. Si prefieres descargar solo uno, recomiendo `multilingual-e5-base`. |
| **D1-4** | **Detector de la vía baja (§5.4)** | (a) Reglas (léxico de insultos y amenazas, mayúsculas, signos) + similitud del embedding con frases prototipo hostiles; (b) un clasificador de toxicidad en español descargado de HuggingFace | **(a)** en Fase 1: reutiliza el modelo de embeddings, no descarga nada y es explicable en la consola. Se mide con los casos hostiles del benchmark. **(b)** solo si **(a)** queda por debajo del 70 % de detección con menos del 10 % de falsas alarmas. |
| **D1-5** | **Primera entidad con rasgos, biografía semilla e ideal del yo** (§14) | Inés u otra entidad | **Inés**, porque ya tiene carácter y la conoces. Propuesta inicial de rasgos, a ajustar contigo:<br>• O 0.6, C 0.7, E 0.3, A 0.35, N 0.55 (reservada, firme, algo sensible);<br>• biografía semilla con `Fact` del self (oficio, cerro Florida, la gata Sorda, la iglesia que se llueve) y 2–3 `Episode` iniciales evocables (por ejemplo, aprender a afinar con su padre o la última pelea con él);<br>• ideal del yo derivado de su `persona` ("no doy la razón por cortesía", "si no sé algo, lo admito").<br>Para el experimento de N, una **segunda configuración** `ines_n_bajo` (la misma Inés con N = 0.15), copiada a mano: la clonación es de Fase 2. Falta saber **quién es la persona `primary`**: ¿qué nombre uso para ti? |
| **D1-6** | **¿La entidad admite ser una IA si se le pregunta sinceramente?** (§14) | (a) Sí, siempre que la pregunta sea sincera; (b) no, mantiene la ficción; (c) opción por entidad (`discloses_artificial: true` por defecto) | **(c) con `true` para Inés**, que es lo que recomienda el documento base (§13.4, transparencia). Se implementa como una norma del ideal del yo en el prompt, más un `Fact` del self ("soy una entidad artificial; Inés es la vida y la historia que tengo"), **sin campo nuevo en el appraisal**. Incluye un caso en el benchmark y otro en la validación. Aceptarlo significa que la biografía es *su* historia, no una afirmación de ser humana. |
| **D1-7** | **El tiempo entre sesiones en Fase 1** | (a) Al cargar la entidad, aplicar el decaimiento del tiempo real transcurrido (forma cerrada, sin simular cada tick); (b) reloj detenido mientras no está cargada | **(a)**: el criterio "decae con el tiempo tras varios días" lo necesita, y es barato porque la exponencial se calcula en una sola operación. Es **provisional**: la decisión §14 "tiempo durante la suspensión" sigue abierta para Fase 2. También: el drive `rest` baja con el tiempo descargada, como sustituto del sueño hasta Fase 2. |
| **D1-8** | **Granularidad y resumen del `Episode`** | (a) Un episodio por turno (mensaje + respuesta), `summary` = el texto sin llamada extra al LLM; (b) un resumen por LLM tras cada turno, con baja prioridad en la GPU | **(a)**: no añade latencia ni carga a la GPU. El sueño de Fase 2 reescribirá los `summary` de todos modos. `importance` se calcula del appraisal (\|valencia\|, alerta, `self_relevance`). |
| **D1-9** | **Clave única de `Revision`** | §7.2 no da a `Revision` una referencia a su episodio | Añadir la propiedad `episode_id` y la restricción `(entity_id, episode_id, version)`. Es una desviación menor de §7.2, y se crea ahora aunque las revisiones se escriban en Fase 2. `Self`: único por `entity_id`. |
| **D1-10** | **Conteo de tokens para el presupuesto de la WorkingMemory** | (a) Aproximación por caracteres, calibrada con el `usage.prompt_tokens` que devuelve Ollama; (b) un tokenizador real (otra dependencia) | **(a)**: el presupuesto de 2500 tokens es una guía, no un límite exacto, y la calibración queda medida en el `REPORTE`. |

**Dependencias previstas**, cada una se instala solo en su checkpoint y tras explicártela:
- `sentence-transformers` y `torch` en versión CPU, en CP2 (D1-3). `numpy` llega como dependencia de ambas.
- No se prevén otras. MMR, saliencia y dinámica se calculan con `numpy` y Python.

---

## 6. Riesgos

| Riesgo | Mitigación |
|---|---|
| Dos llamadas al LLM por turno (appraisal + respuesta): unos 3–6 s hasta la respuesta | Medir en CP1 y CP5. La respuesta usa streaming. CP1 midió que la caché de prefijo de Ollama sobrevive a la alternancia de prompts. |
| VRAM al pasar de 4k a 8k tokens (estimado ~6,7 de 8 GB) | Medir con `nvidia-smi` en CP1 con el contexto lleno. Si no cabe, probar `OLLAMA_KV_CACHE_TYPE=q8_0` o 6k tokens (te consulto antes). |
| JSON inestable o valores saturados (visto en CP3) | Probar `response_format` con `json_schema`, que restringe la generación si Ollama lo admite, frente a `json_object`. Validación Pydantic con recorte de rangos y `llm.error` o `appraisal.invalid` si falla. Si falla, la vía alta usa un appraisal neutro y el turno sigue. |
| Sesgo del benchmark: yo diseño el prompt y propongo las etiquetas | Revisas las etiquetas antes de medir. Separación desarrollo/prueba. El conjunto de prueba se congela. |
| `torch` es pesado (cientos de MB) y la carga en frío de los embeddings es lenta | Rueda de CPU. El modelo se carga una vez al arrancar el servidor y se mide el tiempo. Las pruebas unitarias usan un embedder falso, determinista y sin descarga. |
| La dimensión del índice vectorial queda fija al crearlo | Elegir el modelo en CP2, antes de escribir ningún `Episode`. Cambiarlo después obliga a recalcular los embeddings. |
| Los valores de §5.2 y §6.4 son iniciales y "a calibrar" | Todos en un solo módulo, con su fórmula comentada. Cada parámetro derivado aparece en `identity.loaded`, para verlo en la consola. |
| `tick` y `affect.updated` a 1 Hz inflan el JSONL | Muestrear: emitir cada N segundos o cuando el cambio supere un umbral. El estado se guarda tras cada turno y periódicamente. |
| `Topic` duplicados por sinónimos ("piano" / "pianos") | Normalizar el nombre (minúsculas, sin tildes, singular simple). La fusión semántica de temas queda para el sueño (Fase 2). |
| El LLM ignora el estado traducido a palabras | Probar en CP9 con dos estados opuestos ante el mismo mensaje y comparar las respuestas (revisión manual registrada). |
| Fase grande, con riesgo de sobreingeniería | 11 checkpoints pequeños, cada uno con un resultado observable. Cada mecanismo con su prueba. Sin carpetas para fases futuras. |
| Privacidad: `Trace` guarda el texto crudo de las conversaciones | Neo4j solo en `127.0.0.1` (ya está así). No se exportan datos. Las pruebas usan entidades temporales que se borran al terminar. |

---

## 7. Checkpoints

Cada checkpoint se ejecuta solo tras tu aprobación explícita y termina con validación,
entrada en `REPORTE.md` y una pausa. Las pruebas que requieren Ollama o Neo4j llevan
`-m integration` y se omiten con aviso si el servicio no está disponible.

### CP1 — LLM a 8k y benchmark de appraisal
- **Contexto 8k (D1-2):**
  - sondeo previo: comprobar con `ollama ps` qué contexto usa hoy el endpoint `/v1`;
  - crear el modelo derivado, verificar que usa 8192 tokens y medir la VRAM con `nvidia-smi` en reposo, con el modelo cargado y con un prompt de unos 7k tokens;
  - medir la latencia al primer token.
- **Appraisal:**
  - `ebica/perception/appraisal.py`: el esquema `Appraisal` de §6.2 (con recorte de rangos y valores por defecto) y el prompt de appraisal;
  - el prompt incluye un resumen breve de la entidad (lo necesitan `self_relevance` y `goal_congruence`), definiciones operativas de cada campo, la distinción explícita entre hostilidad y angustia, y unos pocos ejemplos.
- **Benchmark:**
  - casos en `benchmarks/appraisal/cases.yaml` (unos 30): neutros, cálidos, hostiles, de angustia sin hostilidad, mixtos, irónicos, con compromisos, con terceros mencionados, autorrelevantes para Inés, la pregunta sincera sobre ser IA y casos ambiguos;
  - `scripts/benchmark_appraisal.py`: el prompt provisional de Fase 0 frente al nuevo, `json_object` frente a `json_schema` y 3 repeticiones por caso;
  - informe en `docs/fase-1/benchmark_appraisal.md`.
- **Aceptación:**
  - `ollama ps` muestra CONTEXT 8192 y la VRAM queda registrada;
  - pytest (sin GPU) valida el esquema: recorte, campos faltantes, JSON roto → error claro;
  - informe con cada métrica de D1-1 y el veredicto (aceptable / aceptable con mitigaciones / muy deficiente);
  - **si resulta muy deficiente, me detengo y te consulto** antes de seguir.

### CP2 — Embeddings en CPU, índices vectoriales y restricciones pendientes
- **Parte 1:** latencia de Neo4j con `localhost` frente a `127.0.0.1`; instalación de `torch` (CPU) y `sentence-transformers`; corpus `benchmarks/embeddings/retrieval.yaml` y `scripts/compare_embeddings.py`. Pausa para que el usuario revise el corpus.
- **Parte 2:** medición, elección del modelo, `embeddings.py`, esquema y pruebas.
- Sondeo: carga y latencia de los dos modelos candidatos (D1-3), RAM usada, y una prueba de recuperación con unas 20 consultas en español. Se elige uno y se registra.
- `ebica/perception/embeddings.py`: interfaz `Embedder` (`embed(texts) -> vectores normalizados`), que se ejecuta fuera del bucle de eventos para no bloquearlo, más una implementación falsa para las pruebas.
- `graph.py`: índices vectoriales (similitud coseno, dimensión del modelo elegido) para `Episode`, `Fact` y `Topic`; restricción única de `Self` por `entity_id` y de `Revision` por `(entity_id, episode_id, version)` (D1-9).
- **Aceptación:** pytest unitario del esquema (sentencias generadas); prueba de integración: el esquema es idempotente, `SHOW INDEXES` lista los 3 vectoriales `ONLINE` y una consulta vectorial devuelve el vecino esperado; latencia de embedding por mensaje registrada (objetivo: menos de 150 ms).

### CP3 — Identidad: rasgos, parámetros y biografía semilla
- `ebica/identity/traits.py`: `Traits` (O, C, E, A, N en `[0, 1]`, con el origen `t0` para la deriva futura), Estabilidad y Plasticidad, y `derive_parameters(traits)` con la tabla completa de §5.2 y el atractor basal.
- `EntityConfig` amplía su esquema con `traits`, `ego_ideal` (lista de normas), `seed_biography` (`facts` y `episodes`), `primary_person` y `discloses_artificial` (D1-6). Las entidades sin rasgos siguen cargando con valores neutros (0.5), para no romper `ejemplo`.
- `entities/calisto/config.yaml` (D1-5 revisada) y `entities/calisto_n_bajo/config.yaml` con `base: calisto` (D1-12). `entities/ines` queda sin cambios (D1-14).
- Evento `identity.loaded` con rasgos y parámetros derivados. Primera sección del Prompt Assembler ("Quién soy"): voz + ideal del yo; los rasgos no generan texto (D1-13).
- Volver a medir t19 con el perfil real de la entidad (pendiente de CP1).
- **Aceptación:** pytest: cada fórmula de §5.2 con valores conocidos (por ejemplo, N = 0.75 → `h_neg` = 42.5 min); los rasgos fuera de rango se rechazan; `calisto`, `calisto_n_bajo`, `ejemplo` e `ines` cargan; las dos variantes reciben el mismo prompt; `identity.loaded` aparece en la consola.

### CP4 — Afecto, drives y bucle rápido
- Vidas medias que §5.2 no define: resuelto en D1-15.
- `ebica/affect/vad.py`: el VAD de §5.4. Decaimiento hacia el atractor con `τ = h / ln 2`, asimétrico en la valencia negativa, con recorte de rangos. La función `decay(x, dt)` tiene forma cerrada y sirve tanto para el tick como para el tiempo transcurrido (D1-7). `apply_impulse()` aplica los impulsos.
- `ebica/affect/drives.py`: `social`, `novelty` y `rest`, con `e_i += r_i·dt` y el acople `Δvalence ∝ −Σ w_i·Δe_i`.
- `ebica/core/orchestrator.py`: una tarea asyncio con un tick de ≈1 Hz mientras la entidad está activa, que publica `tick`, `affect.updated` y `drive.updated` muestreados, y `drive.threshold_crossed`.
- `EntityState` incorpora `affect`, `drives` y `last_tick_at`, y se persiste. Al cargar se aplica el tiempo transcurrido.
- Consola: barras de VAD y drives en vivo, el nombre de la entidad en el chat y los eventos recientes al conectarse (por ejemplo, los del JSONL del día) (pendiente 5).
- **Aceptación:**
  - pytest con tiempo inyectado: tras un impulso negativo, la valencia recorre la mitad de la distancia al atractor en `h_neg`, con ±2 % de tolerancia;
  - con el mismo impulso, N = 0.55 y N = 0.15 dan vidas medias distintas, en la razón que predice la fórmula (versión unitaria del criterio §11);
  - los drives crecen con `dt` y respetan sus límites;
  - el estado sobrevive a guardar y cargar;
  - la consola muestra el VAD moviéndose.

### CP5 — Turno con appraisal, vía baja, impulsos y cola de GPU
- Cola de GPU con prioridades (§5.14: respuesta > appraisal > impulsiva): `gpu.enqueued`, `gpu.started` y `gpu.preempted`; la interrupción cancela la tarea, un mecanismo ya probado en CP3 de Fase 0.
- `ebica/affect/low_road.py`, que hace las veces de `hostility_watch` (D1-4): si supera `θ_vb`, emite `affect.low_road_triggered`, aplica un impulso de alerta y produce una respuesta `impulsive` con contexto mínimo.
- Turno normal:
  1. percepción con embedding;
  2. appraisal con el preset `appraisal`;
  3. impulsos: `g_neg`/`g_pos` · `goal_congruence`, y el lazo `π`·(valencia del usuario − valencia propia) que alimenta `distress_watch`;
  4. el contacto satisface `social` y la novedad satisface `novelty`;
  5. respuesta `dialogue`, con la temperatura modulada por el afecto.
- Prompt: sección 2 ("Cómo me siento", en palabras) y sección 8 (los últimos N turnos).
- La lógica del turno pasa de `core/turn.py` al orquestador. La API sigue siendo solo transporte.
- Mitigaciones pendientes del benchmark de CP1 (se deciden contigo al empezar CP5): formato `json_schema` o `json_object` para el appraisal; regla de coherencia para el sarcasmo con superficie positiva (hostilidad alta con valencia positiva); el sesgo hacia la hostilidad en los mensajes mixtos; y volver a medir t19 (pregunta sobre ser IA) con el perfil real de la entidad.
- Pendiente de CP2: con `bge-m3`, los prototipos hostiles y no hostiles se separan solo en el 55 % de los casos (`docs/fase-1/comparacion_embeddings.md`). Decidir si la regla de prototipos de D1-4 baja su peso, se elimina o se pasa a la opción (b).
- Consola: un panel "último turno" con el appraisal, la marca de vía baja, los impulsos aplicados y las latencias.
- **Aceptación:**
  - pytest con LLM simulado: cadena `perception.input` → `llm.request` (appraisal) → `affect.updated` → `llm.request` (dialogue) → `llm.response`, encadenada por `cause_id`;
  - un appraisal inválido no rompe el turno;
  - un mensaje hostil activa la vía baja y el turno se marca impulsivo;
  - un trabajo de mayor prioridad interrumpe a uno menor (`gpu.preempted`);
  - prueba manual con Inés: un mensaje hostil baja la valencia y lo ves decaer en la consola; ahora recuerda el turno anterior.

### CP6 — Memoria: escritura de episodios y biografía semilla
- `ebica/memory/episodes.py`. Tras cada turno se escribe un `Episode` (D1-8) y su `Trace`, con estos campos y enlaces:
  - `Episode`: texto, embedding y afecto al momento de vivirlo; `importance`, `confidence` = 1, `lability` = 0, `access` = open y `version` = 1;
  - `Trace`: texto crudo, afecto y appraisal en JSON;
  - enlaces: `NEXT`, `DERIVED_FROM`, `ABOUT` hacia los `Topic` y `Commitment` creados en vigilia.
- Validar la dimensión del embedding antes de escribir: Neo4j acepta un vector de otra dimensión sin error y lo deja fuera del índice, invisible para la búsqueda (sondeado en CP2).
- Al cargar la entidad, la biografía semilla se importa al grafo de forma idempotente, con ids estables: `Self`, `Fact` de dominio `self` con `source = seed` y `Episode` iniciales con su `Trace`.
- Eventos `memory.written` y `tom.person_created`, este último si se crea el `Person` del usuario principal.
- **Aceptación:** pruebas de integración en una entidad temporal:
  - un turno crea exactamente un `Episode`, una `Trace` y sus relaciones;
  - cargar dos veces no duplica la semilla;
  - nada se escribe fuera de su `entity_id`;
  - verificación manual en Neo4j Browser.

### CP7 — Recuperación híbrida
- `ebica/memory/retrieval.py`:
  - candidatos: top-N vectoriales de `Episode` y `Fact`, más los vecinos a 1–2 saltos de los `Topic` y `Person` activos, sin `access = blocked` ni `Trace`;
  - puntaje de §7.3: similitud, recencia, importancia, congruencia con el ánimo y compromisos abiertos. El `score` de Neo4j es `(1 + coseno) / 2`, no el coseno (medido en CP2): hay que tenerlo en cuenta al fijar los pesos;
  - `GraphStore.vector_search` (CP2) aplica D1-11 y puede devolver menos de `k` si otra entidad acapara los vecinos. Si hace falta, se evalúa aquí un respaldo por similitud exacta sobre los nodos de la entidad (`vector.similarity.cosine`);
  - selección final con MMR (`λ_mmr`, hasta `k`, según O);
  - efecto: sube la `lability` de lo recuperado;
  - las alertas altas con valencia negativa bajan `k` (§5.4).
- Prompt: secciones 4 ("Lo que me viene a la mente", con su tono) y 5 ("Lo que sé").
- Evento `memory.retrieved` con los candidatos y el desglose de cada puntaje. Consola: recuerdos recuperados en el panel del último turno.
- **Aceptación:**
  - pytest del puntaje y de MMR, con vectores sintéticos (sin Neo4j): por ejemplo, con el ánimo negativo gana el recuerdo negativo cuando la similitud es igual, y MMR evita dos casi duplicados;
  - integración: un hecho sembrado ("la gata se llama Sorda") se recupera ante "¿cómo se llama tu gata?";
  - un dato que dio el usuario en un turno anterior se recupera en una sesión nueva.

### CP8 — PartnerModel y selector de interlocutor
- `ebica/social/partner.py`:
  - nodo `Person` por persona y el `primary` de la configuración;
  - `partner_now` a partir del appraisal (emoción, intención y foco);
  - `partner_model` (media móvil de la emoción observada, temas frecuentes, número de interacciones, `trust` inicial), cargado al elegir a la persona y guardado al cambiar o terminar;
  - `Episode` -[`INVOLVES`]→ `Person` y `Trace` -[`SPOKEN_BY`]→ `Person`.
- `EntityState` incorpora `active_person_id` y `partner`.
- La API acepta la persona en el chat: conocida, o nueva con nombre. La recuperación prioriza los episodios con la persona activa.
- Prompt: sección 6 ("Cómo veo a esta persona").
- Eventos `tom.updated`, `tom.partner_switched` y `tom.person_created`. Consola: el selector "hablando como" y un panel de Teoría de la Mente.
- **Aceptación:** integración: dos personas cuentan cosas distintas y el modelo de cada una contiene solo lo suyo (sin cruces, §12); cambiar de persona emite `tom.partner_switched`; demostración en la consola.

### CP9 — WorkingMemory y Prompt Assembler completo
- `ebica/workspace/working_memory.py`:
  - ítems tipados (input, appraisal, turnos, recuerdos, hechos, afecto, partner y señales);
  - saliencia `relevancia · (1 + |valencia|·g_afectivo) · señal`;
  - presupuesto de unos 2500 tokens, reducido por la alerta alta, con desalojo por saliencia (D1-10);
  - eventos `wm.updated` y `wm.evicted`.
- Prompt Assembler: las secciones estables primero (para la caché de prefijo) y la sección 7 ("Cómo expresarme": largo y tono según el estado, sin acotaciones entre asteriscos). Pendiente 6: medir la frecuencia de asteriscos y añadir un filtro posterior solo si persisten (te consulto).
- **Aceptación:**
  - pytest: con un presupuesto chico se desaloja primero lo menos saliente; la alerta alta reduce el presupuesto; el texto del estado se genera en palabras sin números crudos;
  - el conteo aproximado queda calibrado contra `usage.prompt_tokens` (error registrado);
  - el prompt ensamblado nunca supera `num_ctx` (8192) menos `max_tokens` del preset: Ollama trunca en silencio los prompts más largos (medido en CP1);
  - D1-8: se mide cuántos tokens ocupan los recuerdos literales y cuántos se desalojan por falta de presupuesto. Si los recuerdos relevantes no caben, se propone añadir el resumen con el LLM (opción b);
  - revisión manual: el mismo mensaje con dos estados opuestos produce respuestas distintas en tono y largo (registrado en el `REPORTE`).

### CP10 — Micro-agentes y compromisos
- `ebica/workspace/agents/`: `distress_watch`, `repetition_watch` (similitud de embeddings con los turnos recientes; sube `novelty` y emite señal de cambio de tema), `commitment_watch` (compromisos abiertos en la saliencia) y `homeostasis_watch` (solo la señal). `hostility_watch` ya existe desde CP5 y se integra al mismo contrato.
- Los micro-agentes solo emiten `agent.signal`; el orquestador las aplica. `Commitment` se crea en vigilia a partir de `appraisal.commitments`, con `PROMISED` o `WAS_PROMISED`.
- **Aceptación:** pytest por micro-agente, con una pizarra sintética: cada uno emite su señal al pasar el umbral y nada por debajo; ninguno escribe en la pizarra directamente; integración: "mañana te cuento cómo me fue" crea un `Commitment` abierto que aparece en el contexto del turno siguiente.

### CP11 — Validación de la fase
- Hallazgo de CP4, a resolver aquí: con el acople drive → valencia activo, la vida media medida respecto del reposo nominal es mayor que `h_neg` (Calisto 50,4 min frente a 42,5; `calisto_n_bajo` 30,6 frente a 27,5; razón 1,65 frente a 1,55, +6,6 %). Los drives que crecen arrastran la valencia hacia abajo. Opciones: medir respecto del equilibrio efectivo, o con los drives estables. Se decide al iniciar CP11.
- `scripts/validate_phase1.py`: un escenario de varios días con el tiempo inyectado al cargar (D1-7). Usa Inés e `ines_n_bajo`, el mismo episodio hostil y la medición de la vida media del ánimo a partir de los eventos `affect.updated`.
- Precisión de recuerdo de hechos sembrados y de hechos contados por el usuario (unas 10 preguntas), con revisión manual de la relevancia (§12).
- Latencias por turno (p50/p95), VRAM y RAM.
- Prueba manual tuya en la consola durante al menos dos sesiones en días distintos.
- **Aceptación:** los criterios de la sección 8, con su evidencia en el `REPORTE`.

---

## 8. Criterios de aceptación de la fase

- [ ] CP1–CP11 completados y registrados en `REPORTE.md`.
- [ ] `pytest` pasa completo; las pruebas de integración (Ollama y Neo4j) se ejecutan y se informan por separado.
- [ ] **Memoria:** la entidad responde correctamente al menos 8 de 10 preguntas sobre hechos sembrados o contados en sesiones anteriores.
- [ ] **Ánimo persistente:** el VAD tras un turno se conserva al turno siguiente y tras recargar la entidad, y decae hacia el atractor con el tiempo (incluido el tiempo descargada).
- [ ] **Personalidad causal:** ante el mismo episodio, Inés (N = 0.55) e `ines_n_bajo` (N = 0.15) muestran vidas medias de valencia negativa medidas que difieren en la dirección y la proporción que predice `h_neg` (±10 %).
- [ ] **Teoría de la Mente:** sin cruces entre los modelos de dos personas.
- [ ] **Appraisal:** benchmark documentado con un veredicto según los umbrales aprobados (D1-1).
- [ ] La consola muestra el VAD, los drives, el appraisal, los recuerdos recuperados, el interlocutor y el prompt exacto de cada turno.
- [ ] Decisiones D1-1 a D1-10 registradas con lo elegido y su motivo.
- [ ] Ningún dato de entidad (estado, eventos ni Neo4j) queda versionado.
