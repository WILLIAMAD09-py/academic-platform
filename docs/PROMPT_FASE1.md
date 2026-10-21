# PROMPT PARA OPENCODE — Fase 1 v2: Núcleo del sistema y módulo de automatización de exámenes

## 0. Contexto y convenciones

Estoy construyendo una plataforma de automatización académica (documentos, minutas, exámenes, indicadores y más). Esta fase construye **el esqueleto de la arquitectura** y el **módulo de exámenes completo a nivel backend**. La interfaz web de captura (estilo Forms + Kahoot) entra en la siguiente fase; deja listos los contratos de API que esa interfaz consumirá.

Varios docentes usarán el sistema. Trabaja en español para documentación, comentarios de dominio y mensajes al usuario. Identificadores de código (clases, funciones, variables) en inglés.

**Vocabulario obligatorio (no lo mezcles):**
- `exam_code`: código de 5 dígitos que escribe el docente. En el examen aparece como `CLAVE: 21643`. Debe ser único entre exámenes. Es el mismo para todas las claves de un examen.
- `key_letter`: letra de la versión del examen (`A`, `B`, `C`, …). En el documento aparece en la línea de código, por ejemplo `VC – EG – EJ26 – TA`.
- `question`: pregunta capturada por el docente, con su texto original y sus incisos.
- `position`: número que ocupa la pregunta dentro de una clave.

Antes de escribir código, crea `docs/ASSUMPTIONS.md` con las suposiciones de la sección 13 y repórtalas al final.

---

## 1. Objetivo de esta fase

Dado un examen capturado por un docente (secciones, preguntas, incisos, respuesta correcta, banderas de aleatorización), el sistema debe:

1. Validar reglas de negocio.
2. Comprobar y corregir el formato con la plantilla predeterminada.
3. Revisar cada pregunta con un modelo de IA (NLP) que la clasifica **Bien / Mal**. Si está **Mal**, la corrige, la revalida y avisa al docente.
4. Pausar y pedir decisión del docente cuando haya preguntas marcadas.
5. Generar **N claves** (A, B, C, …, sin límite fijo) aleatorizando preguntas e incisos según las banderas de cada pregunta.
6. Generar, por clave, el **examen imprimible** (sin respuestas).
7. Generar un **documento resumen de hoja de respuestas** con las claves y respuestas correctas, para que el docente rellene a mano la hoja de respuestas de los alumnos.

Pasos humanos (captura en web, impresión, rellenar hojas de respuesta de alumnos, decisiones sobre preguntas marcadas) se representan como **tareas humanas** dentro del flujo, no como automatización.

---

## 2. Flujo de referencia (pizarrón)

| # | Paso | Responsable |
|---|------|-------------|
| 1 | Docente captura el examen en la web (secciones, preguntas, incisos, banderas) | Humano |
| 2 | Comprobar formato | Sistema |
| 3 | Corregir formato | Sistema |
| 4 | Revisar si las preguntas están bien hechas (IA: Bien / Mal) | Sistema (modelo IA) |
| 5 | Corregir preguntas marcadas Mal (IA propone corrección) | Sistema (modelo IA) |
| 5.1 | Revalidar la pregunta corregida (vuelve al paso 4) | Sistema (modelo IA) |
| — | Decisión del docente sobre preguntas ambiguas (corregir manual / aceptar IA / conservar original) | Humano |
| — | Aleatorizar preguntas e incisos → generar Clave A, B, … | Sistema |
| — | Generar examen por clave y resumen de hoja de respuestas | Sistema |
| 6 | Imprimir examen | Humano |
| 7 | Rellenar hojas de respuesta de alumnos a mano, con el resumen como referencia | Humano |

Implementa esto como **máquina de estados** explícita y trazable por examen (sección 5).

---

## 3. Stack y decisiones técnicas

- **Lenguaje:** Python 3.12.
- **API:** FastAPI + Pydantic v2.
- **ORM / migraciones:** SQLAlchemy 2.x (estilo declarativo tipado) + Alembic. PostgreSQL en producción; SQLite en desarrollo y tests. La capa de datos debe ser agnóstica al motor.
- **Documentos:** `python-docx` para generar `.docx`. Exportar a PDF vía LibreOffice headless (`soffice --headless --convert-to pdf`) como adaptador opcional.
- **Procesamiento asíncrono:** interfaz `JobRunner` con implementación inline (síncrona) para desarrollo; diseño listo para Celery/RQ después. No introduzcas Redis todavía.
- **Modelo de IA:** detrás de la interfaz `QuestionReviewer` (sección 9). `StubReviewer` basado en reglas para pruebas. El modelo NLP real lo entrena y lo aporta el usuario, y se conecta por adaptador local.
- **Prohibido:** llamar a APIs externas de modelos de IA (OpenAI, Anthropic, Google u otras) desde el código de la aplicación, incluidos el stub y el adaptador. El sistema no depende de ningún servicio de IA externo. Esto aplica al código del producto, no a la herramienta de desarrollo que uses para programarlo.
- **Configuración:** `pydantic-settings` con variables de entorno y `.env.example`.
- **Tests:** pytest + pytest-cov. Cobertura objetivo ≥ 85% en el núcleo de exámenes, aleatorización y formato.
- **Calidad:** ruff (lint + format), mypy estricto en `src/`.
- **Contenedores:** `Dockerfile` y `docker-compose.yml` (app + postgres). LibreOffice en la imagen solo si el adaptador PDF está habilitado.
- **Frontend (fase posterior):** React + Vite + TypeScript en `web/`. En esta fase solo `web/README.md` con el contrato de API.

---

## 4. Estructura del repositorio

```
proyecto/
├── README.md
├── pyproject.toml
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
├── migrations/
├── docs/
│   ├── ARCHITECTURE.md          # Diagramas Mermaid: capas, pipeline, aleatorización
│   ├── ADR/                     # Un ADR por decisión clave
│   ├── ASSUMPTIONS.md
│   └── exam-domain.md           # Reglas de negocio en lenguaje natural para el docente
├── src/
│   ├── platform/                # NÚCLEO compartido, reutilizable por otros módulos
│   │   ├── config.py
│   │   ├── db.py                # Engine, Session, Base
│   │   ├── jobs.py              # JobRunner (interfaz + inline)
│   │   ├── documents/           # Utilidades docx: estilos, tablas, márgenes, encabezados
│   │   ├── audit.py
│   │   ├── errors.py
│   │   └── logging.py
│   └── modules/
│       └── exams/
│           ├── api/             # Routers FastAPI
│           ├── domain/          # Puro, sin dependencias de infraestructura
│           │   ├── models.py
│           │   ├── rules.py         # Validaciones de negocio
│           │   ├── states.py        # Máquina de estados
│           │   └── weights.py       # Cálculo de ponderación
│           ├── application/
│           │   ├── pipeline.py
│           │   ├── format_checker.py    # Paso 2 y 3
│           │   ├── question_review.py   # Pasos 4, 5, 5.1
│           │   ├── decisions.py         # Decisiones del docente sobre preguntas marcadas
│           │   └── keys.py              # Aleatorización y generación de claves
│           ├── infrastructure/
│           │   ├── orm.py
│           │   ├── repositories.py
│           │   ├── reviewers/
│           │   │   ├── base.py          # Protocolo QuestionReviewer
│           │   │   ├── stub.py          # Reglas para pruebas
│           │   │   └── nlp_adapter.py   # Estructura del modelo propio (sin entrenar)
│           │   ├── docx_renderer.py     # Examen por clave y resumen de hoja de respuestas
│           │   └── templates/
│           │       └── default_exam.json   # Formato predeterminado (sección 8)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│       ├── exam_20_questions.json        # Ejemplo sintético
│       └── examen_vc_ej26.json           # Examen real reconstruido (sección 14)
└── web/                                  # Solo README en esta fase
```

Regla de dependencias: `domain` no importa nada de `infrastructure` ni de `api`. `application` depende de `domain` y de interfaces; `infrastructure` implementa esas interfaces. Inyección de dependencias sencilla (funciones de fábrica o contenedor ligero).

---

## 5. Máquina de estados del examen

Enum `ExamStatus`:

```
DRAFT                       # En captura (paso 1, humano)
SUBMITTED                   # El docente lo envió a procesar
VALIDATED                   # Pasó reglas de negocio (sección 6)
FORMAT_CHECKED              # Paso 2
FORMAT_FIXED                # Paso 3
QUESTIONS_REVIEWED          # Pasos 4–5.1 terminados; todas en BIEN o con decisión
NEEDS_TEACHER_DECISION      # Hay preguntas marcadas AMBIGUA/MAL sin decisión del docente
KEYS_GENERATED              # Claves A, B, … creadas y verificadas
DOCUMENTS_GENERATED         # Exámenes por clave y resumen de hoja de respuestas listos
COMPLETED                   # Todo terminado sin advertencias
COMPLETED_WITH_WARNINGS     # Terminado, pero con preguntas que usan la versión original
PRINT_PENDING               # Paso 6 (humano)
ANSWER_SHEETS_PENDING       # Paso 7 (humano)
FAILED
```

Reglas:
- Solo transiciones definidas en `ALLOWED_TRANSITIONS`. Cualquier otra lanza `InvalidTransitionError`.
- Cada transición genera un `AuditEvent` (examen, estado anterior, nuevo, actor, payload JSON, timestamp).
- **Reanudable e idempotente:** reprocesar no duplica claves ni documentos, y continúa desde el último estado estable.
- **Ediciones posteriores:** un examen ya procesado puede editarse. Cualquier cambio de estructura invalida claves y documentos, se vuelve a ejecutar el pipeline automáticamente y se conserva la versión anterior de los documentos en el historial. Las claves conservan su seed: solo se regeneran si el docente lo pide (`POST /exams/{id}/keys`). La revisión de IA usa caché por hash de texto para no re-revisar preguntas sin cambios.
- `NEEDS_TEACHER_DECISION` es estado de espera: el pipeline no continúa hasta que el docente pulsa continuar, sin tiempo límite. Ver sección 9.

---

## 6. Reglas de negocio (`domain/rules.py`)

Todas como funciones puras que devuelven **lista de errores y advertencias** (no fallan al primero). Cada una con código, campo afectado y mensaje en español.

1. **Número de preguntas:** mínimo **25**, máximo **50**. Constantes en `config`.
2. **Ponderación automática:** el peso base es `100 / n` redondeado a 2 decimales. **La última pregunta absorbe la diferencia** para que la suma sea exactamente **100.00**. Tolerancia cero. Ejemplo: 3 preguntas → 33.33, 33.33, 33.34. Con 25 preguntas cada una vale 4.00 (coincide con "VALOR DE CADA REACTIVO: 4 PUNTOS" del examen de ejemplo).
3. **Secciones:** N secciones (≥ 1). Cada pregunta pertenece a exactamente una sección. El orden de secciones nunca cambia.
4. **Opciones:** cada pregunta tiene entre **2 y `max_options` incisos**, con `max_options = 4` por defecto (constante configurable). Las letras válidas son **a, b, c, d, e**; la letra e solo se usa si `max_options` se sube a 5. Exactamente **una respuesta correcta** por pregunta, que debe estar entre los incisos. Las respuestas correctas pueden repetir letra entre preguntas distintas.
5. **Tipos:** solo opción múltiple internamente. Verdadero/falso y completar espacios se capturan como opción múltiple (por ejemplo, "Verdadero" / "Falso" como incisos). Preguntas abiertas: error claro, fuera de alcance en esta fase.
6. **Texto:** enunciados e incisos no vacíos. Longitud máxima configurable. Admiten texto plano y fórmulas (texto plano o LaTeX). Tablas, imágenes y gráficas se guardan como **recursos adjuntos** a la pregunta o a su grupo de estímulo.
7. **Bloques definidos por el docente:** el docente decide qué agrupar. Puede agrupar **preguntas** (`QUESTION_GROUP`), por ejemplo las que comparten un estímulo de código, tabla o imagen, o cualquier conjunto que quiera mover junto. También puede agrupar **secciones** (`SECTION_GROUP`) para que se muevan como bloque. Ver sección 7 y sección 10. Una pregunta pertenece a un solo grupo de preguntas; una sección, a un solo grupo de secciones.
8. **Banderas de aleatorización:** cada pregunta tiene `shuffle_question` y `shuffle_options` (booleanos). Por defecto ambos `true`. Cada inciso tiene además `locked` (booleano, por defecto `false`): un inciso bloqueado se queda en su letra original, por ejemplo "Ninguna de las anteriores" en d. Advertencia (no error) si el enunciado o algún inciso contiene referencias a otros incisos ("todas las anteriores", "ninguna de las anteriores", "a y b son correctas", "ambas", "las dos anteriores"). En ese caso se sugiere desactivar `shuffle_options` o bloquear el inciso.
9. **Incisos con orden natural:** si el enunciado indica orden (fechas, números, "de menor a mayor", "en orden cronológico"), advertencia sugiriendo desactivar `shuffle_options`.
10. **Duplicados:** dos enunciados idénticos tras normalizar (minúsculas, sin acentos ni signos) generan advertencia.
11. **Código del examen (`exam_code`):** exactamente **5 dígitos**. Único entre exámenes (error `409` si ya existe). Lo escribe el docente.
12. **Campos de encabezado obligatorios** para el resumen (sección 11): `exam_title` (Examen correspondiente a), `period` (PERIODO), `learning_unit` (Unidad de aprendizaje). Opcionales: `academy`, `date`.

---

## 7. Modelo de datos

- **Exam**: id (UUID), exam_code (5 dígitos, único), title, course_code, period, learning_unit, academy (opcional), exam_date (opcional), teacher_id, status, template_mode (`DEFAULT | CUSTOM`), template_ref (nullable, plantilla propia), footer_signers (JSON: ELABORÓ, VALIDÓ, COORDINADOR ACADÉMICO), n_keys, seed, version, created_at, updated_at.
- **Section**: id, exam_id, position, roman_numeral, title, instructions (texto), created_at.
- **StimulusGroup**: id, exam_id, section_id, kind (`CODE | TABLE | IMAGE | TEXT`), content (texto o referencia a archivo), attachment_ref.
- **Block**: id, exam_id, kind (`QUESTION_GROUP | SECTION_GROUP`), name, member_ids (ids de preguntas o de secciones, según el tipo), created_by, created_at. Lo define el docente y puede cambiarlo en cualquier momento.
- **Question**: id, section_id, stimulus_group_id (nullable), position_original, stem_original (**texto original del docente, nunca se sobrescribe**), stem_current (texto vigente tras revisión/decisión), shuffle_question (bool), shuffle_options (bool), weight (decimal 2), review_status (`PENDING | GOOD | AI_APPLIED | AI_PROPOSAL_PENDING | AMBIGUOUS_AWAITING_DECISION | KEPT_ORIGINAL_WITH_WARNING | RESOLVED | NEEDS_HUMAN`), review_history (JSON), created_at, updated_at.
- **Option**: id, question_id, label (a–e), text_original, text_current, is_correct, position_original, locked (bool, default false).
- **ReviewDecision**: id, question_id, decision (`UNDO_AI_CORRECTION | ACCEPT_AI_CORRECTION | REJECT_AI_CORRECTION | KEEP_ORIGINAL | MANUAL_EDIT`), before_snapshot (JSON), after_snapshot (JSON), decided_by, decided_at, note.
- **ExamKey**: id, exam_id, key_letter (`A`, `B`, …), seed_used, exam_version, generated_at.
- **KeyQuestionMapping**: id, exam_key_id, question_id, position_in_key, option_order (JSON: letra original → letra en la clave), correct_label_in_key.
- **GeneratedDocument**: id, exam_id, exam_key_id (nullable), kind (`EXAM_PRINT | ANSWER_SHEET_SUMMARY`), file_path, sha256, exam_version, created_at, superseded_at (nullable).
- **AuditEvent**: id, exam_id, from_status, to_status, actor, payload (JSON), created_at.

---

## 8. Formato predeterminado (plantilla y motor de formato)

Archivo: `templates/default_exam.json`. Valores tomados del examen de referencia (Word de la Escuela, carta):

- **Página:** carta, 12240 × 15840 twips (21.59 × 27.94 cm).
- **Márgenes:** izquierdo 1134 twips (≈2.0 cm), derecho 1183 (≈2.1 cm), superior 1985 (≈3.5 cm, deja espacio a logos y encabezado), inferior 567 (≈1.0 cm).
- **Área de texto:** ancho ≈ 9923 twips (≈17.5 cm). Ninguna tabla ni imagen puede superar ese ancho.
- **Tipografía:** Arial para cuerpo (12 pt), títulos de examen (14 pt), notas y encabezados de tabla (10 pt). Consolas para código dentro de preguntas.
- **Encabezado institucional (fijo):** logos (archivo proporcionado por el usuario, referenciado en la plantilla), línea de control del documento (ej. `Elaboración de Exámenes · FSA09 Rev.7 · 08-07-2025 · 40 días`), título del examen (ej. `EXAMEN GLOBAL DE VISIÓN COMPUTACIONAL`), y línea de código con la clave de letra (ej. `VC – EG – EJ26 – TA`).
- **Bloque de datos del alumno (fijo):** Nombre del alumno, Matrícula, Aula, Bachillerato, Grupo, Turno, Nombre del maestro, Fecha, con líneas de llenado.
- **Clave:** `CLAVE: {exam_code}` visible en el encabezado.
- **Indicaciones:** bloque "INDICACIONES PARA EL APLICADOR" y bloque "INSTRUCCIONES PARA EL ALUMNO" (textos fijos, configurables en la plantilla).
- **Tiempo y valor:** `TIEMPO PARA RESOLVER EL EXAMEN: {minutos} MINUTOS` y `VALOR DE CADA REACTIVO: {valor} PUNTOS` (el valor sale de la ponderación calculada).
- **Secciones:** encabezado con numeral romano y consigna en mayúsculas (ej. `I. LEE CADA UNA DE LAS SIGUIENTES PREGUNTAS…`). Si la sección comparte estímulo, la consigna puede referirlo (ej. `II. ANALIZA EL SIGUIENTE FRAGMENTO… Y RESPONDE LAS PREGUNTAS 22 Y 23.`).
- **Preguntas:** número en negrita, enunciado, y debajo el estímulo del grupo si lo tiene (código en Consolas, tabla o imagen).
- **Incisos:** en **tabla de 2 columnas**, llenada por filas (`a | b` / `c | d` / `e`). Sin viñetas. Espaciado entre filas de la tabla.
- **Pie de documento (plantilla):** bloque de firmas `ELABORÓ` / `VALIDÓ` / `COORDINADOR ACADÉMICO` con nombre y firma. Al crear el examen, el docente elige `template_mode`:
  - **`DEFAULT`:** usa el formato predeterminado, con sus firmas.
  - **`CUSTOM`:** no usa el formato predeterminado. Sube su propia plantilla `.docx` y sus firmas. El motor de formato valida contra esa plantilla, y el ancho del área de texto sale de sus márgenes.

**Motor de formato (pasos 2 y 3)** detecta y corrige como mínimo:
- Tablas o imágenes más anchas que el área de texto. Corrección: escalar proporcionalmente al ancho del área.
- Espaciado irregular: párrafos sin espacio o con espacio excesivo, preguntas pegadas al texto anterior, huecos grandes. Corrección: normalizar al formato predeterminado.
- Fuentes o tamaños distintos a la plantilla. Corrección: reaplicar estilos.
- Secciones sin numeral o sin consigna. Corrección: generar desde la plantilla si hay datos; si no, `MANUAL_REQUIRED`.
- Incisos que no estén en la tabla de 2 columnas. Corrección: reconstruir la tabla.
- Cada problema queda en un reporte `FormatIssue(code, location, severity, message, fixed: bool)`.

Pruebas que generen documentos con problemas a propósito (tabla de 20 cm en carta, párrafos sin espacio, incisos en lista) y verifiquen que el corrector los arregla.

---

## 9. Revisión de preguntas con IA (`application/question_review.py`)

**Contrato del revisor** (`infrastructure/reviewers/base.py`):

```python
class QuestionReviewer(Protocol):
    def review(self, question: QuestionInput) -> ReviewResult: ...
    def correct(self, question: QuestionInput, reasons: list[str]) -> QuestionInput: ...
```

- `ReviewResult`: label (`BIEN | MAL`), reasons (códigos: `AMBIGUA`, `REBUSCADA`, `MAL_REDACTADA`, `ERRATA_ORTOGRAFICA`, `RESPUESTA_INCORRECTA_PROBABLE`, `INCISOS_DUPLICADOS`, `DISTRACTOR_EVIDENTE`, `REFERENCIA_A_OTRO_INCISO`), confidence (0–1).
- `QuestionInput`: stem, options (etiqueta + texto), correct_label, section_context, stimulus_context (texto del código o descripción de la tabla/imagen).

**Ciclo (pasos 4 → 5 → 5.1):**

```
intento = 0
loop:
    res = reviewer.review(q)
    if res.label == BIEN: review_status = GOOD; break
    intento += 1
    if intento > MAX_REVIEW_ATTEMPTS (default 3):
        review_status = AMBIGUOUS_AWAITING_DECISION   # marcada, sin corrección estable
        break
    q_corr = reviewer.correct(q, res.reasons)        # paso 5
    registrar intento en review_history (original, reasons, corrección)
    q = q_corr                                       # paso 5.1: revalidar
```

- La IA **aplica su corrección sola**, con aviso al docente, también cuando cambia la respuesta correcta (en ese caso el aviso marca `correct_answer_changed = true`). Se guardan siempre el antes y el después.
- El docente puede **deshacer** cualquier corrección de la IA. Al deshacerla, la corrección pasa a **propuesta** (`AI_PROPOSAL_PENDING`) y el docente puede aceptarla o rechazarla.
- Las preguntas que la IA no logra corregir en `MAX_REVIEW_ATTEMPTS` pasan a `AMBIGUOUS_AWAITING_DECISION` y requieren decisión del docente.

**Decisión del docente (`application/decisions.py`)**, por pregunta:
- `UNDO_AI_CORRECTION`: deshace la corrección aplicada por la IA; pasa a propuesta pendiente.
- `ACCEPT_AI_CORRECTION`: acepta la propuesta pendiente o confirma la corrección aplicada.
- `REJECT_AI_CORRECTION`: rechaza la propuesta y usa el texto original.
- `KEEP_ORIGINAL`: usa el texto original del docente (para preguntas ambiguas no corregidas).
- `MANUAL_EDIT`: el docente escribe su versión (texto y, si aplica, incisos y respuesta).

Todas las decisiones se guardan en `ReviewDecision` con antes y después.

**Espera del docente:** el pipeline se detiene en `NEEDS_TEACHER_DECISION` y **no tiene tiempo límite**: solo continúa cuando el docente pulsa continuar (`process/continue`). Si al continuar quedan preguntas ambiguas sin decisión, se usan sus versiones **originales** y el examen termina en `COMPLETED_WITH_WARNINGS`. Cada una de esas preguntas aparece como advertencia en la auditoría y en el resumen de documentos. Las correcciones que la IA ya aplicó (con aviso) no bloquean el pipeline.

`StubReviewer` con reglas simples para probar el flujo completo: enunciado < 10 caracteres → MAL/AMBIGUA; más de 300 caracteres → MAL/REBUSCADA; incisos duplicados → MAL/INCISOS_DUPLICADOS; palabras "todas las anteriores" → MAL/REFERENCIA_A_OTRO_INCISO; corrección = normalizar espacios y mayúsculas al inicio. Debe detectar la errata "distribudo" del examen de referencia como ERRATA_ORTOGRAFICA.

`nlp_adapter.py`: solo estructura, TODOs claros y `load_model(path)` que lanza `NotImplementedError` con mensaje útil. No entrenes nada.

---

## 10. Motor de aleatorización y generación de claves (`application/keys.py`)

Este es el corazón del sistema.

**Entrada:** examen validado y revisado, `n_keys` (≥ 2, sin máximo fijo; letras `A`–`Z`, más de 26 claves es error explícito), `seed` (por defecto derivada de `exam_id` + `version`, para reproducibilidad).

**Salida:** por cada clave, el orden de preguntas, el orden de incisos de cada pregunta, la letra correcta resultante y el mapeo completo.

**Unidades de aleatorización:** la pregunta y sus incisos forman **un solo conjunto**. Una pregunta se mueve de número, pero sus incisos nunca salen de ella. Si la pregunta pertenece a un `QUESTION_GROUP`, el grupo completo es **una unidad** que se mueve como bloque (las preguntas del grupo conservan su orden relativo).

**Alcance por defecto:** la aleatorización es **por sección**. Una pregunta solo cambia de posición dentro de su sección.

**Excepción definida por el docente:** un `SECTION_GROUP` permite mover secciones como bloque. Las secciones de un grupo se intercambian solo con secciones de otro grupo del mismo número de secciones; el orden interno de sus preguntas se conserva dentro de cada sección. Las secciones fuera de un grupo no se mueven.

**Algoritmo por sección:**
1. Las unidades con `shuffle_question = false` quedan **fijas** en su posición original.
2. Las unidades libres solo intercambian posición con unidades **del mismo tamaño** (1 pregunta con 1 pregunta; grupo de 2 con grupo de 2). Así los grupos no se rompen.
3. Para cada pregunta con `shuffle_options = true`, se permutan sus incisos. Los incisos con `locked = true` quedan en su letra original. Si la pregunta tiene `shuffle_options = false`, todos sus incisos quedan en su orden original.
4. Guardar el mapeo como **"nueva letra ← letra original"** (en `option_order`). Ejemplo del pizarrón: si el inciso original `d` pasa a la posición `a`, se guarda `a ← d`.
5. Usa `random.Random(seed_de_clave)`, nunca el RNG global.

**Restricciones (reintentar con nuevo muestreo hasta 1000 intentos; si falla, error explícito):**
- `require_distinct_question_order` (default `true`): la secuencia de preguntas de cada clave debe ser distinta a la de las demás claves, siempre que el examen tenga al menos una unidad libre que lo permita.
- `require_distinct_correct_letter` (default `true`): para cada pregunta, la letra correcta debe diferir entre claves. Si la pregunta tiene menos de 2 posiciones posibles, emite advertencia y sigue.
- `min_position_shift` (default 0): permite exigir que una pregunta no ocupe la misma posición en dos claves.
- Validar que existe solución antes de muestrear cuando sea posible (por ejemplo, con 1 sola unidad libre la restricción de orden no se puede cumplir: advertencia).

**Caso de referencia 1 (test explícito, del pizarrón):** en la clave A, la pregunta original 5 pasa a la posición 5 y sus incisos quedan: `a ← d`, `b ← c`, `c ← b`, `d ← a`. En la clave B, la pregunta original 3 pasa a la posición 3 con sus incisos: `a ← b`, `b ← c`, `c ← a`, `d ← d` (el inciso d queda igual). El `KeyQuestionMapping` debe reconstruir sin ambigüedad qué pregunta original es cada una y de dónde viene cada inciso.

**Caso de referencia 2:** si el inciso `d` tiene `locked = true`, ninguna permutación lo mueve de la letra d.

**Reproducibilidad:** persistir `seed`, permutaciones y mapeos. La misma seed genera exactamente las mismas claves (test).

**`verify_keys(keys) -> list[Issue]`:** revisa de nuevo todas las restricciones sobre el resultado final y se llama siempre antes de persistir. Nunca se generan documentos sin pasar por `verify_keys`.

---

## 11. Documentos generados (`infrastructure/docx_renderer.py`)

Por cada clave se generan dos tipos de documento.

**1. Examen por clave (`EXAM_PRINT`).** Plantilla predeterminada (sección 8), con:
- `CLAVE: {exam_code}` y la línea de código terminada en la letra de la clave (`… – TA`).
- Secciones en su orden, con sus consignas.
- Preguntas en el orden de la clave, con el estímulo de su grupo.
- Incisos en el orden de la clave, en tabla de 2 columnas, con letras a–e.
- **Sin respuestas marcadas.**
- Bloque de datos del alumno y pie de firmas.

**2. Resumen de hoja de respuestas (`ANSWER_SHEET_SUMMARY`).** Un solo documento para todo el examen, con dos partes:

*Encabezado* (solo estos campos, en este orden):
```
Examen correspondiente a: ____________________ (obligatorio)
PERIODO: ____________________ (obligatorio)
Unidad de aprendizaje: ____________________ (obligatorio)
Academia o especialidad: ____________________ (opcional)
Fecha: ____________________ (opcional)
Clave del examen (5 dígitos): _____ (obligatorio)
```

*Cuerpo:* **una tabla por clave**, después del encabezado, con columnas:

| N° de pregunta | Pregunta | Clave | Respuesta | Inciso |
|---|---|---|---|---|

- **N° de pregunta:** el número de esa pregunta dentro de la clave.
- **Pregunta:** solo el enunciado, sin incisos, solo texto (sin imágenes, tablas ni código; esos elementos se omiten en el resumen).
- **Clave:** la letra de la clave (A, B, …).
- **Respuesta:** la letra correcta de esa clave (a–d, o e si `max_options` lo permite).
- **Inciso:** el texto completo del inciso correcto, tal como aparece en esa clave.

Este documento no requiere ser impreso por el sistema; el docente lo consulta para rellenar a mano las hojas de respuesta.

**Nombres de archivo:** `{exam_slug}_{YYYYMMDD}_clave-{A}_examen.docx` y `{exam_slug}_{YYYYMMDD}_hoja-respuestas-resumen.docx`. Guardar el `sha256` de cada archivo.

Todo documento generado debe pasar el verificador de formato (sección 8) antes de marcarse como terminado.

---

## 12. API (FastAPI, prefijo `/api/v1/exams`)

- `POST /exams` — crear examen (DRAFT). Valida `exam_code` único (409 si ya existe). Recibe `template_mode` (`DEFAULT | CUSTOM`).
- `GET /exams/{id}` — detalle con secciones, grupos, preguntas, incisos, banderas, estado.
- `PUT /exams/{id}/structure` — reemplaza la estructura completa. **Permitido en cualquier estado.** Si el examen ya fue procesado, reinicia el pipeline automáticamente y conserva el historial de documentos.
- `PATCH /exams/{id}/questions/{qid}/flags` — cambia `shuffle_question` y `shuffle_options`.
- `PATCH /exams/{id}/options/{oid}/flags` — cambia `locked`.
- `PUT /exams/{id}/blocks` — reemplaza los bloques definidos por el docente (`QUESTION_GROUP` y `SECTION_GROUP`). Valida que no haya preguntas en dos grupos.
- `POST /exams/{id}/validate` — reglas de negocio; devuelve errores y advertencias.
- `POST /exams/{id}/submit` — pasa a SUBMITTED.
- `POST /exams/{id}/process` — ejecuta el pipeline completo. Responde con el estado final o `NEEDS_TEACHER_DECISION` con la lista de preguntas afectadas.
- `GET /exams/{id}/review-queue` — preguntas pendientes de decisión, con antes y después y motivos.
- `POST /exams/{id}/questions/{qid}/decision` — body: `{ "decision": "UNDO_AI_CORRECTION | ACCEPT_AI_CORRECTION | REJECT_AI_CORRECTION | KEEP_ORIGINAL | MANUAL_EDIT", "manual": {…opcional} }`.
- `POST /exams/{id}/process/continue` — body: `{ "use_original_for_unresolved": bool }`. Reanuda el pipeline; si `true`, las no resueltas usan la original con advertencia.
- `POST /exams/{id}/keys` — body: `{ "n_keys": int, "seed": int|null }`. Genera o regenera claves (registra la anterior en auditoría).
- `GET /exams/{id}/documents` — documentos generados y versiones, con enlace de descarga.
- `GET /exams/{id}/audit` — historial de eventos.
- `POST /exams/{id}/status/{transition}` — avance manual para pasos humanos (imprimir, hojas de respuesta).

Documenta todo en OpenAPI con ejemplos. Errores con formato único: `{ "error": { "code", "message", "details" } }`.

---

## 13. Suposiciones (documentar en `docs/ASSUMPTIONS.md`)

1. Aleatorización **por sección**, nunca entre secciones.
2. Banderas `shuffle_question` y `shuffle_options` por pregunta, ambas `true` por defecto.
3. Grupos de estímulo compartido (`QUESTION_GROUP`) se mueven como bloque y solo intercambian con grupos del mismo tamaño dentro de la sección. El docente puede además agrupar secciones (`SECTION_GROUP`), que se mueven como bloque según la sección 10.
4. `exam_code` (5 dígitos) es único por examen y **compartido por todas las claves**. La letra de clave es aparte.
5. Preguntas con 2 a `max_options` incisos (4 por defecto). Letras a–e; la e solo se usa si `max_options` se sube a 5. **Pendiente de confirmar:** el docente dijo "4 máximo" y también "la E si se puede usar"; el sistema lo deja configurable.
5b. El inciso con `locked = true` se queda en su letra. Ej.: "Ninguna de las anteriores" fijo en d.
6. Letra correcta distinta entre claves por defecto (`require_distinct_correct_letter = true`).
7. Por defecto cambian de lugar tanto las preguntas como sus incisos (`shuffle_question = true`, `shuffle_options = true`, `require_distinct_question_order = true`).
8. Editar un examen procesado reinicia el pipeline y regenera documentos. Las claves conservan su seed; solo se regeneran si el docente lo pide.
9. La IA aplica sus correcciones solas, con aviso al docente. El docente puede deshacerlas, y entonces pasan a propuesta que puede aceptar o rechazar. Esto aplica también a cambios de respuesta correcta.
10. Verdadero/falso y completar espacios se tratan como opción múltiple; la hoja de respuestas usa letras a–e.
11. Logos y firmas viven en la plantilla, no en el código. El docente elige entre el formato predeterminado (`DEFAULT`) o una plantilla propia (`CUSTOM`).
12. El resumen de hoja de respuestas contiene solo texto de la pregunta, sin imágenes ni tablas.
13. El modelo de IA de revisión es propiedad del usuario y se conecta por adaptador local. La aplicación no llama a APIs externas de modelos.

---

## 14. Fixture de referencia: examen real reconstruido

Crear `tests/fixtures/examen_vc_ej26.json` a partir del examen de referencia "Examen global de Visión Computacional" (25 preguntas, `exam_code = 21643`). Incluir:

- Secciones: **I** (preguntas 1–21), **II** (grupo de estímulo de código para preguntas 22–23), **III** (grupo de estímulo de código para preguntas 24–25).
- Por pregunta: enunciado, incisos a–d, respuesta correcta del versión base, `shuffle_question` y `shuffle_options` en `true` excepto los grupos de código (sin cambios en el grupo).
- Dos claves de referencia **TA** y **TB** con la letra correcta de cada pregunta según el documento de claves (ejemplo: pregunta 1 → TA `b`, TB `a`; pregunta 25 → TA `a`, TB `d`). Usar esto como **tabla de verdad** en tests: la letra correcta de cada clave debe coincidir con el texto de la respuesta.
- Errata conocida en la pregunta 25 (opción `distribudo`) para probar `ERRATA_ORTOGRAFICA`.

Test de regresión: el sistema debe reproducir, a partir de la base, las letras correctas de TA y TB cuando se le indique el mismo orden de incisos.

Nota del ejemplo: en el documento de referencia, TA y TB tienen las preguntas en el mismo orden (1–25) y solo cambian los incisos. Por defecto el sistema sí cambia preguntas de lugar, así que el fixture debe probar ambos casos: con `require_distinct_question_order = true` (por defecto) y con `false`. Con `false`, el resultado del ejemplo debe reproducirse.

---

## 15. Requisitos no funcionales

- **Trazabilidad:** toda transición, decisión del docente y decisión de IA queda en auditoría.
- **Idempotencia:** procesar dos veces el mismo examen no duplica claves ni documentos.
- **Reproducibilidad:** misma seed y versión → mismas claves y documentos.
- **Logging estructurado** (JSON) con `exam_id`, `exam_code` y `request_id` en cada línea.
- **Configuración por entorno**, sin secretos en el código.
- **Sin estado global mutable** en el núcleo.
- **Seguridad:** validación con Pydantic, límites de tamaño de texto, sin ejecución de código del usuario, nombres de archivo generados por el sistema (no por el usuario).

---

## 16. Pruebas obligatorias

**Unitarias**
- Reglas: mínimo 25, máximo 50; ponderación 100/n con última pregunta absorbiendo la diferencia (suma exacta 100.00); incisos de 2 a `max_options` (4 por defecto) con letras a–e; exactamente una correcta por pregunta; `exam_code` de 5 dígitos.
- Bloques: un `QUESTION_GROUP` se mueve como unidad; un `SECTION_GROUP` intercambia secciones solo con otro grupo del mismo tamaño; una pregunta no puede estar en dos grupos.
- Incisos bloqueados: el inciso `locked` nunca cambia de letra.
- Advertencias: detección de "todas las anteriores" y de orden natural.
- Máquina de estados: transiciones válidas e inválidas; reprocesar tras editar.
- Aleatorización: las unidades fijas no se mueven; los grupos no se rompen; nada cruza secciones; los incisos no salen de su pregunta; reproducibilidad con misma seed; `verify_keys` detecta violaciones inyectadas.
- Caso de referencia (sección 10).
- Ciclo de revisión: BIEN en primer intento; MAL → corrige → BIEN; MAL persistente → `AMBIGUOUS_AWAITING_DECISION` tras N intentos.
- Decisiones: `UNDO_AI_CORRECTION` pasa la corrección a propuesta; `ACCEPT_AI_CORRECTION`, `REJECT_AI_CORRECTION`, `KEEP_ORIGINAL` y `MANUAL_EDIT` guardan antes y después. Continuar con preguntas sin decisión usa la original y deja `COMPLETED_WITH_WARNINGS`.
- Formato: tabla fuera de margen, espaciado irregular e incisos en lista se corrigen.
- Resumen de hoja de respuestas: encabezado con los campos y su orden; una tabla por clave; columnas exactas (N° de pregunta, Pregunta, Clave, Respuesta, Inciso); la columna Pregunta solo tiene el enunciado; la columna Inciso tiene el texto del inciso correcto.

**Integración**
- Flujo completo con `StubReviewer`: crear → validar → submit → process → decisión sobre preguntas marcadas → continue → claves → documentos → auditoría completa.
- Continuar con `use_original_for_unresolved = true` deja `COMPLETED_WITH_WARNINGS`.
- Reanudar tras fallo simulado a mitad del pipeline.
- Editar un examen procesado regenera documentos y conserva la versión anterior.
- `exam_code` duplicado devuelve 409.
- Endpoints principales con `TestClient`.

---

## 17. Entregables

1. Repositorio completo según la sección 4, ejecutable con `docker compose up`.
2. Migraciones Alembic iniciales.
3. `README.md`: instalación, variables de entorno, tests, cómo procesar el examen de ejemplo desde la línea de comandos.
4. `docs/ARCHITECTURE.md` con diagramas Mermaid: capas, máquina de estados, flujo de aleatorización, flujo de decisiones.
5. Al menos 4 ADR en `docs/ADR/`: (a) FastAPI + capas hexagonales ligeras, (b) máquina de estados explícita, (c) aleatorización determinista con seed, (d) decisión humana sobre cambios de la IA.
6. `docs/exam-domain.md` con las reglas de negocio en lenguaje natural para el docente.
7. `docs/ASSUMPTIONS.md` con la sección 13.
8. CLI: `python -m modules.exams.cli process --file tests/fixtures/examen_vc_ej26.json --keys 2 --out ./output` que ejecute el flujo y deje los `.docx`.

---

## 18. Orden de trabajo

Ejecuta en este orden y **al terminar cada paso, muéstrame un resumen corto** (qué se hizo, qué pruebas pasan, qué quedó pendiente) antes de seguir:

1. Scaffolding, `pyproject.toml`, ruff/mypy/pytest, Docker, `.env.example`.
2. Núcleo `platform/` (config, db, logging, errors, jobs, audit).
3. Dominio: modelos, reglas, ponderación, máquina de estados, pruebas unitarias.
4. Persistencia: ORM, repositorios, primera migración Alembic.
5. Aleatorización por unidades y secciones, `verify_keys`, caso de referencia, reproducibilidad.
6. Plantilla predeterminada y motor de formato, con pruebas.
7. Ciclo de revisión IA con `StubReviewer` y decisiones del docente.
8. Renderizado DOCX: examen por clave y resumen de hoja de respuestas; verificación de formato sobre el resultado.
9. Pipeline completo, idempotencia, reanudación, edición con regeneración.
10. API FastAPI y OpenAPI.
11. CLI, fixture real reconstruido y ejecución end-to-end.
12. Documentación final.

---

## 19. Lo que NO debes hacer en esta fase

- No construyas la interfaz web de captura. Deja `web/README.md` con el contrato.
- No entrenes ni incluyas un modelo NLP real; solo el stub y el adaptador.
- No llames a APIs externas de modelos de IA desde el código de la aplicación.
- No automatices impresión ni el llenado de hojas de respuesta de alumnos. Solo generas el resumen.
- No agregues Redis, Celery, autenticación compleja ni multi-tenant todavía; deja los puntos de extensión.
- No dupliques lógica entre `application` e `infrastructure`.
- No cambies silenciosamente las reglas de la sección 6. Si algo no es posible, repórtalo.
- No generes claves sin pasar por `verify_keys`.
- No apliques correcciones de la IA sin aviso al docente, ni impidas que las deshaga.
- No mezcles preguntas entre secciones salvo que el docente lo defina con un `SECTION_GROUP`, y no rompas grupos definidos por el docente.
