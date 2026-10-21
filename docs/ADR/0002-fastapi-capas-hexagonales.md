# ADR-0002: FastAPI + capas hexagonales ligeras

**Status:** Proposed
**Date:** 2026-10-21
**Deciders:** Responsable técnico del proyecto (pendiente de firma)

## Context

La fase 1 debe entregar un backend completo (módulo de exámenes) y, en la fase siguiente, una interfaz
web de captura estilo Forms + Kahoot que consumirá la API.

Restricciones:

1. Python 3.12, FastAPI, Pydantic v2.
2. Estructura de capas `api / domain / application / infrastructure`, con la regla de que `domain` **no**
   importa de `infrastructure` ni de `api`.
3. Sin Redis, Celery, autenticación compleja ni multi-tenant en esta etapa: solo puntos de extensión.
4. El motor de aleatorización y el motor de formato son **el corazón del sistema** y deben poder
   probarse de forma aislada, sin base de datos ni FastAPI.
5. La interfaz web de la fase 2 debe consumir un contrato de API estable, definido ahora.
6. mypy estricto en `src/`.

## Decision

**FastAPI con arquitectura hexagonal ligera**, organizada en capas dentro de un único paquete de
módulo (`src/modules/exams/`), con estas reglas:

- `domain/` — modelos de negocio, reglas puras, máquina de estados, ponderación. **Cero** imports de
  `infrastructure` y `api`. Solo biblioteca estándar y Pydantic (para DTOs de entrada/salida del
  revisor).
- `application/` — orquestación de casos de uso. Importa `domain` y **protocolos** (interfaces)
  definidos en `application` o `domain`; nunca importa implementaciones concretas.
- `infrastructure/` — implementa esos protocolos: ORM, repositorios, revisores, renderizador DOCX.
- `api/` — routers FastAPI. Traduce HTTP a casos de uso y devuelve respuestas; no contiene reglas de
  negocio.
- **Inyección de dependencias por funciones de fábrica** (`build_review_service(...)`,
  `get_session(...)`), sin contenedor externo.

Regla de dependencia (verificada por un test de arquitectura en el paso 3):

```
api  →  application  →  domain
infrastructure  →  application (implementa protocolos)
domain  →  (nada del proyecto)
```

## Options Considered

### Option A: FastAPI + capas hexagonales ligeras (elegida)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Media — 4 capas por módulo + 1 núcleo compartido |
| Cost | Bajo — solo dependencias ya fijadas en la sección 3 |
| Scalability | Alta — stateless, con `JobRunner` como punto de extensión a Celery |
| Team familiarity | Alta — convención widespread en Python backend |
| Testabilidad | Excelente — el dominio se prueba sin FastAPI ni BD |
| Contrato para la fase 2 | Directo — OpenAPI generado desde los routers |

**Pros:** satisface la estructura exacta de la sección 4; el motor de aleatorización (núcleo del
sistema) queda puro y testeable; la separación `domain`/`application`/`infrastructure` impide que la
lógica de negocio se mezcle con el acceso a datos; OpenAPI sale gratis de FastAPI; la interfaz web de
la fase 2 tiene contrato desde el día uno.

**Cons:** más archivos y más indirección que un monolito por capas técnicas; riesgo de sobre-ingeniería
en un módulo que aún es pequeño; las dependencias deben inyectarse "a mano" (sin contenedor).

### Option B: FastAPI con capas técnicas (routers → services → CRUD)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Baja — 3 carpetas planas |
| Cost | Bajo |
| Testabilidad | Media — los servicios mixed con ORM |
| Contrato para la fase 2 | Directo |

**Pros:** menos ceremonia, Velocity alta al principio.
**Cons:** `services/` acaba importando modelos de ORM, y el dominio queda acoplado a SQLAlchemy
— justo lo que el prompt prohíbe ("la capa de datos no debe depender del motor" y "no dupliques lógica
entre `application` e `infrastructure`"). El prompt fija además la estructura de 4 capas, de modo que
esta opción contradice la sección 4.

### Option C: Django + ORM propio + DRF

| Dimension | Assessment |
|-----------|------------|
| Complexity | Baja-media —ORM, admin, ORM, templating y auth incluidos |
| Cost | Bajo |
| Testabilidad | Buena |
| Contrato para la fase 2 | Medio — DRF genera OpenAPI, pero el esquema es menos controlable |

**Pros:**ORM, admin, auth, migraciones y Background Tasks incluidos; admin útil para el docente.
**Cons:** contradice la sección 3 (FastAPI + Pydantic v2) y la 4 (FastAPI + Pydantic v2); acopla
el dominio a Django; el admin de Django no sustituye la interfaz de captura de la fase 2.

### Option D: Hexagonal estricto con contenedor de inyección (dependency-injector)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Alta |
| Cost | Bajo |
| Testabilidad | Excelente |
| Overhead | Alto para el tamaño actual |

**Pros:** bindings declarativos, singletons, scopes por petición; muy explícito.
**Cons:** `dependency-injector` no soporta bien async en su versión actual; añade una dependencia
externa y un modelo mental que el equipo tendrá que aprender; para 2 módulos y ~10 casos de uso es
sobre-ingeniería. Se descarta ahora y puede reintroducirse más adelante sin cambiar las capas.

## Trade-off Analysis

La decisión real no es FastAPI vs. otro framework (la sección 3 lo fija), sino **cuánta disciplina
arquitectural** imponer a un sistema cuyo núcleo es un algoritmo determinista de aleatorización con
reglas de negocio densas.

- El coste de las 4 capas es visible en el número de archivos y en el mapping manual.
- La contrapartida es que el motor de aleatorización, el verificador de formato y el ciclo de revisión
  con IA se prueban como funciones puras, sin mocks de FastAPI ni de base de datos.
- El riesgo de la alternativa (capas técnicas) es material y silencioso: en cuanto el primer servicio
  hace `select(...)` sobre un modelo ORM, el dominio deja de ser agnóstico al motor y la regla de
  dependencias de la sección 4 queda violada sin que nadie lo note.

Se elige el sobre-ingeniero controlado: hexagonal ligero con inyección por funciones de fábrica.

## Consequences

- **Máspliers**: se puede testear `verify_keys`, `compute_weights` y las reglas sin fixtures pesadas.
- **Coste de escritura**: cada caso de uso necesita un mapper o un repositorio. Se acepta: es
  exactamente el punto que evita duplicar lógica entre `application` e `infrastructure`.
- **Contrato de API definido en la fase 1** y reutilizable por `web/` en la fase 2.
- **Punto de extensión a Celery**: `JobRunner` (núcleo) se implementa en `infrastructure`; cambiar la
  implementación no toca `application`.
- **Verificable**: un test de arquitectura comprueba que `domain` no importa de `infrastructure` ni de
  `api` (se implementa en el paso 3, con el núcleo y el dominio).

## Action Items

1. [ ] Definir los protocolos (`QuestionReviewer`, `JobRunner`, `DocumentRenderer`, repositorios) en
      `application`/`domain` y sus implementaciones en `infrastructure` (pasos 2, 5, 7, 8).
2. [ ] Añadir test de arquitectura que analice los imports de `src/modules/exams/domain/` (paso 3).
3. [ ] Centralizar la construcción de dependencias en `src/modules/exams/infrastructure/container.py`
      (funciones de fábrica), sin variables globales mutables (paso 4).
4. [ ] Publicar `web/README.md` con el contrato de la API al cierre del paso 10.

## Notas de implementación

- La regla de dependencias se comprueba con un test que recorre los `import` de los módulos de `domain/`
  y falla si aparece `infrastructure`, `api`, `sqlalchemy` o `fastapi`.
- `domain/` puede usar `dataclasses`, `enum`, `datetime`, `decimal` y `pydantic` (para los DTOs del
  contrato `QuestionReviewer`), pero no `sqlalchemy` ni `fastapi`.
