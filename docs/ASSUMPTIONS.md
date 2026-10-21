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

### A20 — Docker no es verificable en este entorno
`docker` no está instalado en la máquina de desarrollo. `Dockerfile` y `docker-compose.yml` se escriben
en el paso 1 como exige la sección 4, pero **no se pueden construir ni ejecutar** aquí; se reportan como
entregables no verificados.

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
