# ADR-0005: Máquina de estados explícita del examen

**Status:** Proposed
**Date:** 2026-10-21
**Deciders:** Responsable técnico del proyecto (pendiente de firma)

## Context

El prompt de la fase (sección 5) define el ciclo de vida de un examen como una secuencia de estados
(`DRAFT → SUBMITTED → VALIDATED → FORMAT_CHECKED → FORMAT_FIXED → QUESTIONS_REVIEWED →
KEYS_GENERATED → DOCUMENTS_GENERATED → COMPLETED`) con dos desvíos: `NEEDS_TEACHER_DECISION` (el
revisor automático no puede decidir) y `FAILED` (la revisión encuentra problemas que impiden
continuar). La sección 16 añade que el pipeline debe poder **reanudar** un examen pausado.

El problema: el pipeline de la sección 16 tiene muchas etapas encadenadas (validación → formato →
revisión → claves → documentos) y las ejecuta en segundo plano, con reintentos y reanudación. Si el
estado del examen vive implícitamente en el código (un `if` aquí, un `return` allá), cada etapa nueva
tiene que reimplementar "qué se puede hacer a continuación", y una reanudación a mitad de camino puede
dejar el examen en un estado inconsistente.

Restricciones que gobiernan la decisión:

1. Los estados y sus nombres son parte del contrato de la fase: no se pueden renombrar.
2. Una transición no permitida debe fallar con un error claro (409), no con un estado corrupto.
3. Cada cambio de estado debe quedar auditado (quién, cuándo, desde qué estado).
4. El dominio no puede depender de FastAPI ni de SQLAlchemy.
5. Cobertura ≥ 85 % y mypy estricto; la lógica de estados debe ser trivial de probar.

## Decision

**El ciclo de vida se modela como una máquina de estados explícita, en el dominio, con un grafo de
transiciones declarado como dato.**

- `ExamStatus` (enum `StrEnum`) declara los 14 estados de la fase. El valor del enum es el texto
  exacto que se persiste y que viaja por la API, de modo que no hay tabla de equivalencias.
- `ALLOWED_TRANSITIONS` es un `Mapping` inmutable (`MappingProxyType`) de estado a `frozenset` de
  estados alcanzables. Es **dato**, no código: se puede inspeccionar, serializar y comparar en un test.
- `can_transition(actual, destino)` consulta el grafo; `assert_transition(actual, destino)` lanza
  `InvalidTransitionError` si la transición no está permitida.
- `Exam.transition_to(destino, actor=..., payload=..., now=..., id_factory=...)` aplica la transición y
  devuelve un `Transition(exam, event)`: una **copia** del examen con el nuevo estado y el evento de
  auditoría. El examen original no se modifica (el modelo es inmutable), lo que evita estados
  compartidos entre capas y hace que la operación sea trivial de probar.
- `InvalidTransitionError` hereda de `core.errors.InvalidStateError`, por lo que la capa HTTP la
  traduce a **409 Conflict** con el código `invalid_transition` sin traducción adicional.
- La auditoría del cambio de estado la produce el propio dominio (`ExamAuditEvent`), de modo que no
  se puede cambiar de estado sin dejar rastro.

Por qué el grafo es *dato* y no una jerarquía de clases (`State` con métodos `can_transition`): el
número de estados es fijo y pequeño, y un mapa se lee de un vistazo, se cubre con un test de tabla y
permite generar documentación o un diagrama sin código adicional.

Por qué el estado vive en el agregado (`Exam.status`) y no en una tabla aparte: el examen **es** la
entidad que avanza; un estado externo exigiría transacciones distribuidas entre el estado y el
examen, y el prompt exige que el pipeline sea reanudable, no que el estado sobreviva a la base de
datos.

## Options Considered

### Option A: máquina de estados explícita en el dominio (elegida)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Baja — un enum, un mapa y tres funciones |
| Cost | Nulo |
| Scalability | Alta — el grafo no crece con el tráfico |
| Team familiarity | Alta — se lee como una tabla |
| mypy estricto | Buena — tipos explícitos en todo el grafo |
| Testability | **Alta** — se prueban aristas permitidas y prohibidas sin tocar la base de datos |

**Pros:** las reglas de "qué se puede hacer a continuación" están escritas una sola vez; una transición
inválida falla antes de tocar la base de datos; el modelo es auditable por construcción.

**Cons:** hay que mantener el mapa al añadir estados; no hay "transiciones dynamics" (p. ej. permitir
un salto según el resultado del pipeline) salvo que se modelen como estados intermedios, que es justo
lo que hacen `FORMAT_FIXED` y `QUESTIONS_REVIEWED`.

### Option B: cada etapa del pipeline decide si puede continuar

| Dimension | Assessment |
|-----------|------------|
| Complexity | Media — cada etapa conoce el estado y su regla |
| Cost | Nulo |
| Scalability | Alta |
| Team familiarity | Alta |
| mypy estricto | Buena |
| Testability | Baja — hay que probar cada etapa con su estado previo |

**Pros:** cada etapa es autonomous y legible.
**Cons:** la regla de transiciones queda duplicada en N sitios; una reanudación a mitad de pipeline
puede dejar el examen en un estado que ninguna etapa reconoce; imposible garantizar que "el estado
nunca se corrompe" sin un inventario de reglas.

### Option C: motor de workflow externo (Celery, Temporal, Airflow)

| Dimension | Assessment |
|-----------|------------|
| Complexity | **Alta** — infraestructura, despliegue, estado externo |
| Cost | Alto — servicios nuevos, operación |
| Scalability | Muy alta |
| Team familiarity | Media |
| mypy estricto | Irrelevante |
| Testability | Media — el estado vive fuera del proceso |

**Pros:** reanudación y reintentos resueltos por la plataforma.
**Cons:** el prompt fija el stack (sin Celery) y pide el pipeline reanudable *dentro* de la aplicación;
el estado del examen dejaría de estar en la misma transacción que los datos del examen, lo que
introduce un problema de consistencia distribuida que la fase no pide.

### Option D: máquina de estados como librería (transitions, stateful, etc.)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Media — dependencia y API externa |
| Cost | Bajo — dependencia externa |
| Scalability | Alta |
| Team familiarity | Media — hay que aprender la API |
| mypy estricto | Regular — la mayoría de estas librerías no están tipadas |
| Testability | Media — el grafo se declara en una forma propia de la librería |

**Pros:** gratis (barreras, callbacks, diagramas).
**Cons:** el prompt fija las dependencias del proyecto; y el grafo de esta fase es lo bastante pequeño
como para que la librería aporte más complejidad que valor.

## Trade-off Analysis

El criterio decisivo es la **garantía de integridad del estado**: si el pipeline se reanuda, falla o se
reintenta, el examen no puede quedar en un estado imposible de alcanzar. Una tabla de transiciones
declarada en el dominio hace esa garantía explícita y verificable con tests (permitidas vs.
prohibidas), mientras que las opciones B y C la dejan implícita en el flujo de control. La opción D
sería equivalente en capacidad, pero el prompt fija el stack y aquí el grafo es de 14 estados: la
librería no compensa.

El precio es explícito: **añadir un estado obliga a actualizar el grafo y sus tests**, y el
mantenimiento del mapa es manual. Se asume como parte del coste de la máquina: si en el futuro el
número de estados creciera mucho (o hubiera transiciones condicionales complejas), la opción D
volvería a ser candidata (ver "Qué revisaría").

## Consequences

- `Exam.transition_to` es la **única** vía para cambiar de estado; devuelve copia + evento, nunca
  muta.
- Una transición inválida lanza `InvalidTransitionError` → **409** con el detalle
  `{"current": ..., "target": ...}`; el pipeline la traduce en un fallo recuperable, no en un estado
  corrupto.
- Todo cambio de estado deja un `ExamAuditEvent` (actor, momento, estado origen y destino, payload).
- El grafo es **reiniciable**: desde un examen procesado (`KEYS_GENERATED`, `DOCUMENTS_GENERATED`,
  `COMPLETED`, `COMPLETED_WITH_WARNINGS`, `PRINT_PENDING`, `ANSWER_SHEETS_PENDING`) se puede volver a
  `DRAFT` para reprocesarlo tras una edición, tal y como describe la sección 16 del prompt.
- `NEEDS_TEACHER_DECISION` es un estado de espera, no un error: de ahí solo se sale hacia
  `QUESTIONS_REVIEWED` (el docente aprueba) o `FAILED` (rechaza).
- Tests de tabla (`tests/unit/test_domain_states.py`) comprueban aristas permitidas y prohibidas: un
  cambio en el grafo que rompa una expectativa falla la suite.

## Action Items

1. [x] Definir `ExamStatus` y el grafo `ALLOWED_TRANSITIONS` (paso 3).
2. [x] Implementar `can_transition` / `assert_transition` y `InvalidTransitionError` (paso 3).
3. [x] Implementar `Exam.transition_to` con evento de auditoría (paso 3).
4. [x] Tests de tabla de transiciones permitidas y prohibidas (paso 3).
5. [ ] Persistir `status` y `version` del examen y reconstruir el agregado al reanudar (paso 4).
6. [ ] Enganchar las transiciones del pipeline de la sección 16 (paso 6).
7. [ ] Añadir la decisión del docente sobre `NEEDS_TEACHER_DECISION` en la API (paso 9).

## Qué revisaría

- Si el pipeline necesitara **transiciones condicionales** (p. ej. saltar a `COMPLETED_WITH_WARNINGS`
  según el resultado de la revisión), lo modelaría con estados intermedios explícitos antes que con
  reglas condicionales en el grafo.
- Si el número de estados creciera de forma significativa, reevaluaría una librería de máquina de
  estados o la generación del grafo a partir de un diagrama (por ejemplo, desde un `.mmd` versionado).
