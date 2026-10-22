# ASSUMPTIONS — Fase 1

Suposiciones tomadas sobre los puntos ambiguos del prompt de la fase (`docs/PROMPT_FASE1.md`).
Estado: `Propuestas` — pendiente de confirmación del docente / responsable técnico.

Las suposiciones 1–12 reproducen literalmente la **sección 13** del prompt. Las suposiciones 13+ son
añadidos de implementación derivados de la lectura del prompt y de los ADR de `docs/ADR/`.

---

## 1. Suposiciones del prompt (sección 13)

### A1 — Alcance de la aleatorización
La aleatorización es **por sección**, nunca entre secciones. Solo un `SECTION_GROUP` definido por el
docente permite mover secciones como bloque.

### A2 — Banderas por pregunta
`shuffle_question` y `shuffle_options` son booleanos por pregunta, ambos `true` por defecto.

### A3 — Grupos de estímulo y grupos de sección
Un `QUESTION_GROUP` (grupo de estímulo compartido) se mueve como bloque y solo intercambia con grupos
del **mismo tamaño** dentro de la misma sección. El docente puede además agrupar secciones
(`SECTION_GROUP`), que se mueven como bloque según la sección 10 del prompt.

### A4 — `exam_code` y letra de clave
`exam_code` (exactamente 5 dígitos) es único por examen y **compartido por todas las claves** de ese
examen. La letra de la clave (`key_letter`: A, B, C…) es un identificador distinto y adicional.

### A5 — Número de incisos
Cada pregunta tiene entre **2 y `max_options`** incisos, con `max_options = 4` por defecto. Las
letras válidas son `a`–`e`; la `e` solo se usa si `max_options` se sube a 5.
**Pendiente de confirmar:** el docente dijo "4 máximo" y también "la E si se puede usar"; el sistema lo
deja configurable por entorno.

### A5b — Incisos bloqueados
Un inciso con `locked = true` conserva siempre su letra original (ejemplo: "Ninguna de las anteriores"
fijo en `d`).

### A6 — Letra correcta distinta entre claves
Por defecto `require_distinct_correct_letter = true`: la letra correcta de una pregunta debe diferir
entre claves. Si la pregunta tiene menos de 2 posiciones posibles, se emite advertencia y se continúa.

### A7 — Comportamiento por defecto
Por defecto cambian de lugar tanto las preguntas como sus incisos
(`shuffle_question = true`, `shuffle_options = true`, `require_distinct_question_order = true`).

### A8 — Edición de un examen procesado
Editar un examen procesado reinicia el pipeline y regenera los documentos. Las claves **conservan su
seed**; solo se regeneran si el docente lo pide explícitamente (`POST /exams/{id}/keys`).

### A9 — Autonomía de la IA y reversibilidad
La IA aplica sus correcciones por su cuenta, con aviso al docente. El docente puede deshacerlas, y en
ese caso la corrección pasa a **propuesta** que puede aceptar o rechazar. Esto incluye los cambios de
respuesta correcta (`correct_answer_changed = true`).

### A10 — Verdadero/falso y completar espacios
Se capturan como opción múltiple (incisos "Verdadero" / "Falso"). La hoja de respuestas usa letras `a`–`e`.

### A11 — Logos y firmas
Viven en la plantilla, no en el código. El docente elige entre formato predeterminado (`DEFAULT`) o
plantilla propia (`CUSTOM`).

### A12 — Contenido del resumen de hoja de respuestas
Contiene **solo el texto del enunciado** de la pregunta: sin imágenes, sin tablas, sin código.

### A13 — Modelo de IA local, sin servicios externos
El modelo de revisión de preguntas **lo entrena y lo aporta el usuario** y se conecta por adaptador
local (`nlp_adapter.py`). La aplicación —incluidos el `StubReviewer` y el adaptador— **no llama a
ninguna API externa de modelos de IA** (OpenAI, Anthropic, Google u otras) y no depende de ningún
servicio de IA externo.

En el repositorio se verifica de forma automática con `tests/unit/test_no_external_ai_apis.py`, que
prohíbe importar SDK de inferencia externa y referencia a sus endpoints.

La herramienta de desarrollo (OpenCode) usa su propio modelo para programar; eso no forma parte del
producto y no aparece en el código de la aplicación.

---

## 14. Suposiciones añadidas de implementación

### A14 — El paquete del núcleo compartido se llama `core`, no `platform`
El prompt (sección 4) y `AGENTS.md` ubican el núcleo compartido en `src/platform/`. **Ese nombre no es
importable**: `platform` es un módulo de la biblioteca estándar de Python y, tanto en instalación
editable como en instalación normal, la stdlib tiene prioridad sobre `site-packages`, por lo que
`import platform` resuelve al módulo de la stdlib y `src/platform/` queda inaccesible.

Verificado empíricamente en este repositorio (instalación editable con setuptools): `import platform`
devuelve `C:\...\Python312\Lib\platform.py` y el paquete propio no es alcanzable.

**Decisión:** el directorio del núcleo es `src/core/` (importable como `core`), y `src/modules/exams/`
se mantiene tal como lo define el prompt. El nombre `platform` queda reservado por la stdlib.

**Pendiente de confirmar:** si se prefiere `src/core/`, `src/shared/` u otro nombre, se ajusta el árbol
y `AGENTS.md` en un solo commit. El impacto es cosmético (imports), no arquitectónico.

### A15 — Los modelos del dominio no son modelos de ORM
`domain/models.py` define el modelo de negocio en dataclasses puras (sin dependencias de SQLAlchemy).
Los modelos de persistencia viven aparte en `infrastructure/orm.py` y se traducen con mappers
explícitos. Esto es lo que permite que la capa de datos sea **agnóstica al motor** (requisito de las
secciones 3 y 4 del prompt) y que `domain` no dependa de infraestructura.

### A16 — `ExamKey.key_letter` admite `A`–`Z`; más de 26 claves es error explícito
El prompt fija letras `A`–`Z` y obliga a fallar explícitamente si se piden más de 26 claves.

### A17 — El `seed` de las claves se deriva de `exam_id` + `version`
Valor por defecto determinista (sección 10). `POST /exams/{id}/keys` permite pasar un `seed` explícito.
Al reeditar el examen cambia la `version` y, por tanto, el seed derivado; el `seed` explícito de una
regeneración prevalece.

### A18 — `exam_code` es una cadena, no un entero
Se persiste y transporta como texto de 5 dígitos (`"21643"`) para preservar los ceros a la izquierda.
La unicidad se garantiza con un índice único en base de datos además de la validación de aplicación.

### A19 — El pipeline es síncrono en esta fase
`JobRunner` tiene una implementación `inline` (síncrona) para desarrollo y tests. La interfaz queda
preparada para Celery/RQ (sección 3), pero **no** se introduce Redis ni Celery.

### A20 — Docker verificado en la máquina de desarrollo (con una limitación)
Docker Desktop 4.96.0 quedó instalado y operativo (backend WSL2, motor 29.9.1) y el stack se verificó de
punta a punta:

- `docker compose build` construye la imagen `academic-platform:0.1.0` sin errores.
- `docker compose up -d db` levanta PostgreSQL 16.15 y el healthcheck pasa a `healthy`.
- `docker compose up -d` levanta también `app`, que pasa a `healthy` y responde `GET /health` con
  `200 {"status":"ok","version":"0.1.0"}`.
- Desde la imagen de la app se abre una conexión real a PostgreSQL por la red de compose.
- `docker compose --profile test run --rm tests` ejecuta la suite completa dentro del contenedor
  (35 tests, cobertura 100 %).
- El servicio `app` arranca y sale con `Exited (3)`: `Could not import module "core.app"`. Es el
  comportamiento esperado, no un fallo de la imagen (ver A23).

Limitación: en Windows 11 *Home* el único backend Linux disponible es WSL2, que exige las funciones
opcionales `Microsoft-Windows-Subsystem-Linux` y `VirtualMachinePlatform` (habilitadas con DISM) y una
aplicación WSL (`Microsoft.WSL` 2.7.13). Docker Desktop requiere que el usuario acepte su acuerdo de
licencia en el primer arranque gráfico.

Detalles del `Dockerfile` que el test de humo destapó y que se corrigieron:

- La imagen se divide en etapas `runtime` y `test`. La etapa por defecto de `docker build` es la
  **última** del fichero, así que `docker-compose.yml` declara `target: runtime` de forma explícita
  para el servicio `app`; sin eso, el servicio ejecutaba `pytest` en vez de `uvicorn`.
- `ENV PYTHONPATH=/app/src` hace que el volumen `.:/app/src` sea efectivo: sin él, el paquete
  instalado en `site-packages` tenía prioridad y las pruebas montadas en caliente no se aplicaban.
- `.dockerignore` evita que `.venv`, `.git` y `node_modules` entren en el contexto de build.

### A21 — `libreoffice` (exportador PDF) es un adaptador opcional
No se instala ni se invoca en tests. La interfaz queda definida y la implementación real se deja para
una fase posterior, con el adaptador PDF deshabilitado por defecto.

### A22 — El `JobRunner` inline es `awaitable`, aunque el prompt lo llame "síncrono"
La sección 3 pide una "implementación inline (síncrona)" del `JobRunner`. Como la persistencia es
asíncrona (`AsyncSession`, ver ADR-0001), un ejecutor puramente síncrono no podría invocar los casos de
uso sin bloquear el event loop.

Interpretación aplicada: "inline (síncrono)" se interpreta como **ejecución en el mismo proceso, sin
cola ni worker externo** (en contraposición a Celery/RQ). La interfaz será un `Protocol` con un método
`async`, y la implementación `InlineJobRunner` ejecutará el caso de uso en el proceso actual, de forma
`awaitable`. Sustituirla por una implementación Celery/RQ no cambia `application`, porque el pipeline
solo depende del `Protocol`.

### A23 — `core.app:app` (punto de entrada de la imagen) se crea en el paso 2
El `Dockerfile` arranca `uvicorn core.app:app`. Ese módulo es la fábrica de la aplicación FastAPI
(configuración, logging estructurado y montaje de routers) y se crea en el paso 2 (núcleo compartido),
de modo que la imagen sea coherente aunque los routers de exámenes lleguen en el paso 10.

Desvío menor introducido en el paso 1: para que el `HEALTHCHECK` del contenedor y el test de humo
pudieran verificarse de extremo a extremo, se creó una versión **mínima** de `core/app.py` (fábrica
`create_app()` y ruta `GET /health`). El paso 2 amplía ese módulo con configuración, logging, base de
datos y montaje de routers; no hay conflicto, solo se extiende.

### A24 — La versión de la API sale de `core.__version__`, no de una variable de entorno
El prompt no define una variable de entorno para la versión. Se usa `core.__version__` como única
fuente de verdad: la usa FastAPI en el `openapi.json` y la devuelve `/health`. Por eso `API_VERSION`
se retiró de `.env.example` en el paso 2 (mantener dos fuentes de verdad obligaría a sincronizarlas).

### A25 — El `DATABASE_URL` de la aplicación debe ser **asíncrono**
La capa de datos usa `AsyncSession`, por lo que el URL principal (`DATABASE_URL`) exige un driver
asíncrono: `sqlite+aiosqlite` o `postgresql+psycopg`. Un URL síncrono (`postgresql://`) es un error de
configuración y se rechaza **al arrancar**, con un mensaje explícito, en lugar de fallar en la primera
petición. El URL síncrono (`DATABASE_URL_SYNC`) queda para Alembic y los scripts de línea de comandos.

### A26 — La bitácora de auditoría del paso 2 es en memoria
`AuditLog` es una interfaz (`Protocol`) y la implementación actual (`InMemoryAuditLog`) guarda los
eventos en memoria del proceso. Es suficiente para el núcleo y para las pruebas, pero **no** es
persistente: al reiniciar el proceso se pierde el historial. Cuando exista la tabla de auditoría del
modelo de datos (paso 4), el repositorio sobre esa tabla sustituirá a `InMemoryAuditLog` sin tocar los
servicios (ver ADR-0003).

### A27 — El contexto de correlación no se propaga a hilos
`contextvars` viaja con la tarea de `asyncio`, pero no con los hilos que ejecuta `run_in_threadpool`.
El pipeline del paso 6 deberá abrir su propio `context_scope` por examen (ver ADR-0004); mientras
tanto, el middleware de la API cubre el ciclo de vida de una petición.

Consecuencia visible: las líneas de *access log* de Uvicorn se emiten fuera del `context_scope` del
middleware (las registra el servidor, no la aplicación), así que llegan con `request_id: null`. Los
logs de la propia aplicación (los que interesan para trazar un examen) sí llevan el identificador.

### A28 — `core.errors` queda puro y los manejadores HTTP se separan
En el paso 2, `core/errors.py` contenía las excepciones **y** su traducción a respuestas HTTP (FastAPI
y SQLAlchemy incluidos). Eso impedía que el dominio heredara de `InvalidStateError` sin arrastrar la
capa web en su grafo de imports. En el paso 3 el módulo se parte en dos:

- `core/errors.py`: solo la jerarquía de excepciones (biblioteca estándar).
- `core/error_handlers.py`: `error_envelope()` y `register_exception_handlers()` (capa de presentación).

Consecuencia: `modules.exams.domain` puede depender de `core.errors` sin depender de FastAPI, y el
dominio hereda la taxonomía de errores del núcleo (un `InvalidTransitionError` sale como 409 sin
traducción adicional).

### A29 — El dominio no lee la configuración; recibe los límites como datos
Las reglas de negocio necesitan límites (mínimo y máximo de preguntas, máximo de incisos, longitud
máxima de texto). El dominio no puede leer `Settings` (eso lo ata al entorno y lo hace no determinista
en las pruebas), así que los recibe en una estructura inmutable `RuleLimits`, que la capa de
aplicación construye a partir de `core.config.Settings`.

Sus valores por defecto coinciden con los de la configuración (25–50 preguntas, 2–4 incisos, 2000
caracteres) y hay un test que verifica la sincronía, de modo que un cambio en uno rompe la suite si el
otro no se actualiza.

### A30 — Las reglas devuelven incidencias con código estable y dos niveles
Cada regla es una función pura que devuelve `ValidationIssue(code, field, message, severity,
location)`. Los códigos son estables (`EXAM_CODE_FORMAT`, `OPTION_CORRECT_COUNT`, `BLOCK_EMPTY`...) y
se usan como contrato para la API y los tests, no como texto libre.

El prompt no distingue entre "error" y "aviso" en las reglas, pero sí lo hace en el resultado del
pipeline (`COMPLETED` frente a `COMPLETED_WITH_WARNINGS`, sección 5). Por eso las reglas devuelven dos
niveles: **error** (impide continuar) y **aviso** (no bloquea, pero el pipeline puede acabarse en
`COMPLETED_WITH_WARNINGS`).

**Pendiente de confirmar:** qué reglas son error y cuáles aviso. Hoy son error las estructurales
(cantidad de preguntas, incisos, secciones, bloques, cabecera, código) y aviso las tres heurísticas
(referencias a otros incisos, orden natural y enunciados duplicados).

### A31 — La unicidad del `exam_code` la comprueba la aplicación, no el dominio
El prompt pide que el `exam_code` sea único y que la duplicación sea un 409. El dominio no tiene
acceso a la base de datos, así que `validate_exam_code` recibe el conjunto de códigos ya existentes y
compara. La aplicación (paso 4/9) lo alimentará con una consulta a la tabla de exámenes; además, la
base de datos impose la restricción única como segunda barrera.

### A32 — La detección de referencias a otros incisos es por frases, y puede dar falsos positivos
Las heurísticas de "orden natural" y "referencia a otros incisos" del prompt están expresadas en
lenguaje natural ("todas las anteriores", "ninguna de las anteriores", "a y b son correctas", "ambas",
"las dos anteriores", "de menor a mayor", "en orden cronológico", "fechas", "números"). Se detectan
sobre el texto normalizado (minúsculas, sin acentos, sin puntuación) y producen un **aviso**, nunca un
error: el sistema no puede saber con certeza si "ambas" es una referencia a incisos o parte de otro
enunciado.

Consecuencia asumida: puede haber falsos positivos (por ejemplo, "ambas personas"). El aviso pide
desactivar `shuffle_options` en esa pregunta, que es una decisión conservative y reversible.

### A33 — La ponderación reparte 100,00 y la última pregunta absorbe el redondeo
La sección 6 del prompt exige que los pesos sumen el total del examen. Con 25 preguntas, 4,00 cada
una es exacto; con 3, 33,33 + 33,33 + 33,34 también. Se reparte la base redondeada a dos decimales
(`ROUND_HALF_UP`) y **la última pregunta absorbe la diferencia**, de modo que la suma es exactamente
100,00 y nunca hay un residuo por coma flotante.

**Pendiente de confirmar:** si el docente espera ver el peso repartido de forma uniforme (por ejemplo
33,33 / 33,33 / 33,34) o un reparto "bonito" (33,3 / 33,3 / 33,4). Se eligió el primero porque
garantiza la suma exacta.

### A34 — El estado vive en el agregado y el ciclo es reiniciable
`Exam.status` es parte del agregado (ver ADR-0005). Desde un examen ya procesado
(`KEYS_GENERATED`, `DOCUMENTS_GENERATED`, `COMPLETED`, `COMPLETED_WITH_WARNINGS`, `PRINT_PENDING`,
`ANSWER_SHEETS_PENDING`) se puede volver a `DRAFT` para reprocesarlo tras una edición, que es lo que
pide la sección 16 (reanudación y reproceso).

`NEEDS_TEACHER_DECISION` es un estado de **espera**, no de error: de ahí solo se sale hacia
`QUESTIONS_REVIEWED` (el docente aprueba) o `FAILED` (rechaza). El prompt no detalla el flujo de esa
decisión; el paso 9 (API) lo concretará.

### A35 — El modelo de revisión de preguntas se adelanta al dominio
La sección 18 del prompt sitúa la "revisión de preguntas" en un paso posterior, pero el modelo de
datos la incluye (etiqueta BIEN/MAL por pregunta encontrada). En el paso 3 el dominio declara los
vocabularios (`ReviewStatus`, `ReviewLabel` BIEN/MAL, `ReviewReason`, `DecisionType`, `ReviewAttempt`,
`ReviewDecision`) **sin implementar la lógica de revisión**, que corresponde al paso 7.

Los vocabularios son **los del prompt**, no una propuesta propia: `review_status` con los ocho valores
de la sección 7 (`PENDING`, `GOOD`, `AI_APPLIED`, `AI_PROPOSAL_PENDING`, `AMBIGUOUS_AWAITING_DECISION`,
`KEPT_ORIGINAL_WITH_WARNING`, `RESOLVED`, `NEEDS_HUMAN`), `reasons` con los ocho códigos de la sección 9
(`AMBIGUA`, `REBUSCADA`, `MAL_REDACTADA`, `ERRATA_ORTOGRAFICA`, `RESPUESTA_INCORRECTA_PROBABLE`,
`INCISOS_DUPLICADOS`, `DISTRACTOR_EVIDENTE`, `REFERENCIA_A_OTRO_INCISO`) y `decision` con los cinco
valores de las secciones 9 y 12 (`UNDO_AI_CORRECTION`, `ACCEPT_AI_CORRECTION`, `REJECT_AI_CORRECTION`,
`KEEP_ORIGINAL`, `MANUAL_EDIT`). Estos valores viajan en el cuerpo de
`POST /exams/{id}/questions/{qid}/decision`, así que son **contrato de API** y hay un test que los fija.

### A36 — `ExamAuditEvent` (dominio) y `AuditEvent` (núcleo) son cosas distintas
El núcleo define `AuditEvent` (`core.audit`) como el evento genérico de auditoría de la aplicación. El
dominio de exámenes define `ExamAuditEvent`, que además de `from_status`/`to_status` transporta el
estado concreto de la transición. No se fusionan para no acoplar el dominio a la bitácora genérica
(que además hoy es en memoria: ver A26).

### A37 — El dominio no transporta las marcas de tiempo de persistencia
El modelo de datos del prompt (sección 7) incluye `created_at` / `updated_at` en `Section`, `Question`
y `GeneratedDocument`. El dominio **no** las lleva (salvo donde la lógica las necesita: `Exam`,
`Block`, `ExamKey`, `GeneratedDocument` y `ExamAuditEvent`): son responsabilidad de la capa de
persistencia, que las rellena al leer y al escribir. El mapeador del paso 4 (ORM → dominio) las
descarta, y el inverso las escribe.

Motivo: un objeto de dominio con marcas de tiempo heredadas del almacenamiento no se puede comparar de
forma fiable (dos lecturas de la misma fila darían objetos distintos) y no aporta nada a las reglas.

### A38 — `Option.question_id` se deriva del agregado, no se almacena en el objeto
El prompt (sección 7) da a `Option` un `question_id`. En el dominio, los incisos cuelgan de su
pregunta (`Question.options`), así que el identificador de la pregunta se obtiene del padre. La tabla
de la base de datos sí lo tendrá (sección 7) y el mapeador del paso 4 lo ignora al construir el
dominio.

### A39 — `QuestionType` es una comodidad interna para la regla de "preguntas abiertas"
El prompt (sección 6.5) dice que solo se admite opción múltiple y que "verdadero/falso y completar
espacios se capturan como opción múltiple". El dominio declara `QuestionType` con esos cuatro valores
para poder **explicar el error** de una pregunta abierta (`QUESTION_TYPE_UNSUPPORTED`) en lugar de
devolver un error genérico. En la captura (Fase 2) el docente no elige el tipo: se deduce de la
forma de captura.

### A40 — El prompt se contradice en la dirección del mapa `option_order`; se adopta la de la sección 10
La sección 7 dice "option_order (JSON: letra original → letra en la clave)" y la sección 10 dice
"guardar el mapeo como **'nueva letra ← letra original'** (si el inciso original `d` pasa a la posición
`a`, se guarda `a ← d`)". Son direcciones opuestas.

Se adopta la de la **sección 10** (`nueva letra → letra original`) porque es la que acompaña al
ejemplo numérico de la sección 10 y al caso de referencia de la sección 16 ("`a ← d`, `b ← c`"), que
son los que la verificación de claves (`verify_keys`) y los tests de regresión van a comprobar. La
sección 7 es un resumen de una línea y se considera una errata. **Reportado**, como pide la sección 19.

### A41 — `course_code` es un aviso, no un error
La regla 6.12 del prompt enumera los campos de cabecera obligatorios para el resumen: `exam_title`,
`period` y `learning_unit` (opcionales: `academy` y `date`). `course_code` aparece en el modelo de
datos (sección 7) pero **no** entre los obligatorios. Por eso, si falta, se emite el aviso
`HEADER_COURSE_MISSING` y el examen sigue siendo válido: no se bloquea al docente por un campo que el
prompt no exige.

### A42 — Los códigos de regla que deben responder 409 se declaran en el dominio
El prompt pide que el `exam_code` duplicado se responda con **409** (secciones 6.11 y 12) y que el
resto de fallos de validación se traten como errores de validación (422). Para que la capa de aplicación
no tenga que hardcodear la lista, el dominio declara `CONFLICT_CODES` y `RuleResult.conflict_codes` /
`has_conflicts`: la API traduciéndolos a `ConflictError` (409) y el resto a `ValidationFailedError`
(422).

### A43 — Las posiciones de sección deben ser contiguas (1..N)
La regla 6.3 del prompt dice que el orden de las secciones **nunca cambia**, pero no fija cómo se
representa. Se asume que `Section.position` empieza en 1 y es **contigua** para las N secciones
existentes: un hueco (por ejemplo posiciones 1 y 3 sin la 2) se considera un error
(`SECTION_POSITION_NOT_CONTIGUOUS`), porque dejaría el orden indefinido. La comprobación se hace sobre
las posiciones efectivamente presentes, de modo que no choca con `SECTION_POSITION_DUPLICATED`.





