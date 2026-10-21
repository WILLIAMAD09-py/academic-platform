# ADR-0001: ORM y capa de persistencia — SQLAlchemy 2.x

**Status:** Proposed
**Date:** 2026-10-21
**Deciders:** Responsable técnico del proyecto (pendiente de firma)

## Context

La fase 1 construye una plataforma de automatización académica: FastAPI + Pydantic v2, PostgreSQL en
producción, SQLite en desarrollo y tests, Alembic para migraciones, y un módulo de exámenes con capas
`api / domain / application / infrastructure`.

Restricciones que gobiernan esta decisión:

1. La sección 3 del prompt **fija** SQLAlchemy 2.x (declarativo tipado) + Alembic. Esta evaluación sirve
   para confirmar que la restricción es coherente con el resto de requisitos, no para reabrirla.
2. La capa de datos **no debe depender del motor**: el mismo código debe correr sobre PostgreSQL y
   SQLite sin cambios.
3. `domain/` no puede importar de `infrastructure/` ni de `api/`.
4. mypy **estricto** sobre `src/`.
5. Se necesitan: generado de claves, autoincremento, claves foráneas, JSON, migraciones versionadas,
   `UUID`, `DECIMAL` de 2 decimales, y consultas de lectura con joins y agregaciones.
6. Sin Redis, sin Celery, sin abstracciones distribuidas.

El dominio es rico en reglas: 10 tipos de entidades, enumerables, JSON libre en varios campos
(`review_history`, `member_ids`, `footer_signers`, `option_order`), unicidad condicional y borrado en
cascade con `SetNull` en algunas relaciones.

## Decision

**SQLAlchemy 2.x con ORM declarativo tipado (`Mapped[]` / `mapped_column`)**, con:

- Modelos de persistencia en `infrastructure/orm.py` (fuera de `domain/`), mapeados a dataclasses de
  dominio por mappers explícitos.
- Alembic como herramienta de migraciones, con autogenerate revisado a mano.
- Driver **psycopg** (v3) para PostgreSQL y driver estándar de `sqlite3` para desarrollo y tests.
- Modo asíncrono (`create_async_engine`, `async_sessionmaker`) para el camino de la API, manteniendo
  `AsyncSession` como único tipo de sesión en repositorios.

## Options Considered

### Option A: SQLAlchemy 2.x declarativo tipado

| Dimension | Assessment |
|-----------|------------|
| Complexity | Media — API moderna, `Mapped[]`, `select()`, `AsyncSession` |
| Cost | Bajo — licencia MIT, sin servicios externos |
| Scalability | Alta — pool de conexiones, `AsyncSession`, driver async nativo |
| Team familiarity | Alta — el más usado en Python; documentación y Stack Overflow abundante |
| mypy estricto | Buena — `Mapped[...]` tipa columnas; los `select()`-returning son `ScalarResult[T]` |
| Multi-motor | Nativa — mismo ORM sobre PostgreSQL y SQLite |
| Migraciones | Alembic, primera clase y con soporte de `server_default` |
| Soporte JSON | Nativo — `JSON` en ambos motores (PostgreSQL: `JSONB` opcional) |

**Pros:** cumple la sección 3; ecosistema maduro; Alembic integrado; async real; tipado suficiente
para mypy estricto; permite usar Core (`select()`) en lecturas complejas sin salir del framework.

**Cons:** la API tiene curva de aprendizaje (dos estilos: Core y ORM); los modelos de ORM se "colan"
fácilmente en el dominio si no se impone la separación; el dialecto SQLite difiere del de PostgreSQL en
algunos tipos (p. ej. `JSON` no es `JSONB`).

### Option B: SQLModel

| Dimension | Assessment |
|-----------|------------|
| Complexity | Baja — un solo modelo para API y BD |
| Cost | Bajo |
| Scalability | Media — hereda de SQLAlchemy 2.x, sin async propio más allá del de SQLAlchemy |
| Team familiarity | Media — muy popular en la comunidad FastAPI, pero menos en backend serio |
| mypy estricto | Regular — el solapamiento Pydantic/ORM genera casos problemáticos de tipado |
| Multi-motor | Nativa (delega en SQLAlchemy) |
| Migraciones | Hereda Alembic |

**Pros:** menos código repetido entre esquema de API y modelo de persistencia; integración natural con
FastAPI.

**Cons:** acopla el modelo de la API con el de la base de datos, justo lo contrario de lo que pide el
prompt (`domain` puro, `application` con DTOs propios); `Decimal`, `datetime` y `UUID` se comportan de
forma especial en los modelos de SQLModel; el soporte de columnas `JSON`/`ARRAY` es menos fino que en
SQLAlchemy; su API ha cambiado de forma incompatible varias veces.

### Option C: Tortoise ORM

| Dimension | Assessment |
|-----------|------------|
| Complexity | Baja — API `await`-first, muy legible |
| Cost | Bajo |
| Scalability | Media — pensado para webapps de tráfico moderado |
| Team familiarity | Baja-media — comunidad mucho más pequeña |
| mypy estricto | Mala — el proyecto no publica tipos completos |
| Multi-motor | Nativa pero con soporte desigual (PostgreSQL y SQLite son los mejor soportados) |
| Migraciones | `aerich`, maduro pero menos probado que Alembic |

**Pros:** excelente experiencia async; excelente en tutoriales y proyectos de arranque rápido.

**Cons:** tipos insuficientes para mypy estricto; comunidad y documentación mucho más pequeñas;
ecosistema de migraciones (`aerich`) menos probado que Alembic; soporte desigual entre motores.

### Restricción que decide

La combinación de (a) `domain/` sin dependencias de infraestructura, (b) dominio agnóstico al motor,
(c) mypy estricto y (d) Alembic, deja a **SQLAlchemy 2.x como la única opción que satisface todas las
restricciones sin renuncios**. SQLModel cumpliría (a) y (c) parcialmente, pero exige renunciar a (b)
acoplando el modelo de API al de persistencia; Tortoise falla en (c).

La evaluación de las alternativas queda como respaldo documentado: si en el futuro la sección 3 del
prompt cambiara, la corrección descrita en A15 (modelos de dominio desacoplados de los de ORM) es
precisamente el punto de extensión que hace barato cambiar de ORM.

## Consecuencias

- El dominio se mantiene puro: `domain/models.py` usa dataclasses estándar, sin SQLAlchemy.
- La traducción entre modelos de persistencia y de dominio es explícita y testeable.
- `AsyncSession` y `async_sessionmaker` se usan de forma consistente; los repositorios exponen corrutinas.
- Alembic genera migraciones en `migrations/`, con revisión manual antes de aplicar.
- SQLite en tests y PostgreSQL en producción comparten el 100% del código de aplicación.

### Alternativas descartadas

**Django ORM** — Excelente, pero ataría el proyecto a Django (ORM, admin, templating, auth) y el prompt
exige FastAPI + capas hexagonales ligeras sin autenticación compleja.

**Peewee** — Sencillo y rápido, pero síncrono, sin soporte async, con migraciones limitadas y sin tipos
estrictos. Descartado.

**SQLAlchemy Core sin ORM** — Totalmente válido técnicamente y con excelente rendimiento, pero obliga a
escribir el mapeo a mano, duplica el trabajo de la capa de repositorios y reduce la productividad en un
dominio con 10 entidades. El prompt exige ORM.

**Capa de repositorios con SQL crudo (sin ORM)** — Máximo control, coste de desarrollo alto, y la
sección 3 fija Alembic. Descartado.

## Action Items

1. [ ] Definir `Base` declarativo, `engine`/`sessionmaker` por entorno y `get_session` como dependencia
      de FastAPI (paso 2, núcleo `platform`/`core`).
2. [ ] Escribir los modelos ORM de las 10 entidades (paso 4) y los mappers al dominio.
3. [ ] Configurar Alembic con soporte de `render_as_batch` para SQLite (paso 4).
4. [ ] Añadir tests de integración que corran la misma suite sobre SQLite (paso 4+).
5. [ ] Verificar que el tipo `JSON` de SQLAlchemy funciona igual en PostgreSQL y SQLite; usar `JSONB` solo
      si aparece un requisito de indexación en JSON.

## Notas de implementación

- `Decimal` con `Numeric(4, 2)` para `weight`; el redondeo a 2 decimales con absorbing en la última
  pregunta se hace en el dominio, nunca en la BD.
- `UUID` como `Uuid` nativo de SQLAlchemy 2.x (funciona en ambos motores).
- Índices únicos explícitos para `exam_code` y para `KeyQuestionMapping (exam_key_id, position_in_key)`.
- `cascade="all, delete-orphan"` en relaciones con dependencia directa (opciones de una pregunta) y
  `ondelete="CASCADE"` en la base para las entidades que se borran en cascada (secciones, preguntas).
