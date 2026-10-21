# ADR-0004: Logging estructurado con `contextvars`

**Status:** Proposed
**Date:** 2026-10-21
**Deciders:** Responsable técnico del proyecto (pendiente de firma)

## Context

La sección 15 del prompt exige: *"Logging estructurado en JSON con `exam_id`, `exam_code` y `request_id`
en cada línea"*. Además, la sección 16 pide que el pipeline de un examen sea reanudable y trazable, y
la sección 15 exige además un registro de auditoría por acción relevante.

El problema: esos tres identificadores deben estar disponibles en **cualquier** capa (API, pipeline,
repositorios, adaptadores de documentos) sin que cada función tenga que recibirlos como argumentos. Si
se pasan como parámetros, las firmas se ensucian y es fácil que se pierdan; si se guardan en variables
de módulo, se rompe la regla de "sin estado global mutable" y, peor, en `asyncio` dos peticiones
concurrentes se pisarían el contexto.

Restricciones que gobiernan la decisión:

1. Las tres claves (`exam_id`, `exam_code`, `request_id`) deben aparecer en **todas** las líneas, aunque
   su valor sea `null`.
2. El formato de producción es JSON por línea; en desarrollo se quiere un formato legible.
3. Sin dependencias externas de logging (`structlog`, etc.): el stack es fijo y minimalista.
4. `asyncio` es obligatorio (todo el camino de la API es async).
5. Cobertura ≥ 85 % y mypy estricto.

## Decision

**El contexto de correlación viaja en `contextvars` de la biblioteca estándar, y el formateador JSON
lo inyecta en cada registro en el momento de formatearlo.**

- Tres `ContextVar`: `exam_id`, `exam_code`, `request_id`, con valor por defecto `None`.
- `context_scope(**campos)` es un *context manager* que fija los valores y los restaura al salir
  (también ante excepción), de modo que los contextos anidados se comportan correctamente.
- `get_context()` devuelve el contexto vigente; `set_context()` / `clear_context()` permiten ajuste
  manual.
- `JsonFormatter` (formato de producción) construye la línea con `timestamp`, `level`, `logger`,
  `message`, **los tres campos de contexto** y los campos extra (`extra={...}`), serializada con
  `json.dumps(..., ensure_ascii=False)`.
- `HumanFormatter` (desarrollo) mantiene el formato legible y añade el contexto entre corchetes.
- `configure_logging(settings)` es **idempotente**: quita los manejadores previos del logger raíz y
  añade uno solo, con el nivel y el formato de la configuración. También desactiva los manejadores
  propios de Uvicorn para que sus líneas pasar por el mismo formateador.
- El middleware de correlación de la API abre un `context_scope` con el `request_id` (de la cabecera
  `X-Request-ID` o uno nuevo) y lo devuelve en la misma cabecera de respuesta.

Por qué `contextvars` y no otras opciones: cada tarea de `asyncio` hereda una **copia** del contexto de
su padre, y los cambios dentro de una tarea no se ven en las tareas hermanas. Eso es exactamente la
semántica que se necesita: dos peticiones concurrentes con distinto `request_id` no se interfieren,
y el valor se restaura solo al terminar la tarea.

## Options Considered

### Option A: `contextvars` (elegida)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Baja — parte de la biblioteca estándar |
| Cost | Nulo |
| Scalability | Alta — contexto por tarea, sin contención ni bloqueo |
| Team familiarity | Media — conocido, pero poco usado fuera de Starlette/Django |
| mypy estricto | Buena — `ContextVar[str | None]` está tipado |
| Testabilidad | Alta — el contexto se puede fijar y leer sin tocar el sistema de logs |

**Pros:** sin dependencias; correcto con `asyncio` por diseño; no es estado global mutable (el valor
se hereda por tarea, no se comparte); restoration automática con `Token.reset`.

**Cons:** el valor solo se propaga si el código se ejecuta dentro de la tarea que lo fijó (por ejemplo,
en un hilo se pierde: de ahí el cuidado con `run_in_threadpool`); requiere discipline explícita para
no "filtrar" un contexto a una tarea programada.

### Option B: Parámetros explícitos en todas las funciones

| Dimension | Assessment |
|-----------|------------|
| Complexity | Alta — todas las firmas crecen |
| Cost | Nulo |
| Scalability | Alta |
| Team familiarity | Alta |
| mypy estricto | Buena |
| Testabilidad | Media — hay que pasar el contexto en cada llamada |

**Pros:** nada implícito; el flujo de datos es visible.
**Cons:** ensucia cada firma, es fácil olvidar un parámetro y rompe la composabilidad del pipeline
(el prompt exige reanudar un examen pausado, con la trazabilidad por examen).

### Option C: `contextvars` + `structlog`

| Dimension | Assessment |
|-----------|------------|
| Complexity | Media — estructurado de verdad, pero otra API que aprender |
| Cost | Bajo — dependencia externa |
| Scalability | Alta |
| Team familiarity | Media |
| mypy estricto | Buena |
| Testabilidad | Alta |

**Pros:** processors, binding y renderizado por entorno ya resueltos.
**Cons:** añade una dependencia al stack (el prompt fija las dependencias); su API cambia entre
versiones mayores; para tres campos de contexto es手臂 pesado.

### Option D: Filtro de logging que lee un `threading.local`

| Dimension | Assessment |
|-----------|------------|
| Complexity | Baja |
| Cost | Nulo |
| Scalability | **Baja — incorrecto con `asyncio`** |
| Team familiarity | Alta |
| mypy estricto | Regular |
| Testabilidad | Regular — el estado persiste entre pruebas |

**Pros:** funcional en código síncrono.
**Cons:** con `asyncio` varias peticiones comparten el hilo: el `request_id` de una se filtraría a
otra. Descartado.

## Trade-off Analysis

El criterio decisivo es la **corrección bajo concurrencia**: la plataforma sirve varios exámenes a la
vez y cada uno necesita su propia trazabilidad. La opción B es correcta pero escala mal en la
complejidad de las firmas; la opción D es incorrecta con `asyncio`; la opción C resuelve más de lo
necesario y añade una dependencia que el prompt no pide. `contextvars` ofrece la semántica correcta
con la biblioteca estándar, y el formateador se mantiene pequeño y explícito.

El precio es que el contexto es **implícito**: hay que recordar abrir un `context_scope` al entrar en
un flujo nuevo (petición HTTP, trabajo en segundo plano, exportación). La mitigación es el middleware
de la API y la verificación de que toda línea JSON incluye los tres campos, aunque sean `null`.

## Consequences

- Cada línea JSON lleva `exam_id`, `exam_code` y `request_id`; los tests lo comprueban como contrato.
- La cabecera `X-Request-ID` permite correlacionar la petición del cliente con los logs del servidor.
- La auditoría hereda `request_id` y `exam_code` del contexto sin que el servicio tenga que pasarlos.
- `configure_logging` es idempotente: llamarla dos veces no duplica líneas.
- Riesgo conocido: el contexto no se propaga automáticamente a hilos; el código que use
  `run_in_threadpool` debe copiar explícitamente el contexto si lo necesita.
- Cuando se añada un planificador de trabajos (paso 8), el trabajo deberá abrir su propio
  `context_scope` con el `exam_id` para no heredar el contexto de la petición que lo encoló.

## Action Items

1. [x] Implementar `core/logging.py` con `contextvars`, `JsonFormatter`, `HumanFormatter` y
      `configure_logging` idempotente (paso 2).
2. [x] Propagar `request_id` en el middleware y devolverlo en `X-Request-ID` (paso 2).
3. [x] Comprobar por contrato que toda línea JSON incluye los tres campos (paso 2).
4. [ ] Propagar el contexto a los hilos cuando el pipeline use `run_in_threadpool` (paso 6).
5. [ ] Abrir un `context_scope` por examen en el pipeline y en el ejecutor de trabajos (paso 6+).
6. [ ] Revisar si conviene `structlog` cuando el número de campos estructurados crezca (paso 8+).
