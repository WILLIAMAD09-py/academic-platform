# ADR-0003: Núcleo sin estado global — configuración inmutable e inyección de dependencias

**Status:** Proposed
**Date:** 2026-10-21
**Deciders:** Responsable técnico del proyecto (pendiente de firma)

## Context

La sección 2 del prompt exige que el núcleo sea **modular, testeable y sin estado global mutable**, y
que la configuración se lea de variables de entorno (con `.env` opcional) sin valores escritos en el
código. Además, el proyecto debe poder probarse en SQLite y ejecutarse en PostgreSQL sin cambios, y
el prompt prohíbe Redis, Celery y abstracciones distribuidas.

En el paso 2 se construye el núcleo `src/core/`, del que dependen todos los pasos posteriores: modelos
de dominio, pipeline de exámenes, generación de claves y exportación a DOCX/PDF. Hay tres recursos
que ese núcleo necesita:

1. **Configuración** (URL de base de datos, niveles de log, rangos de negocio, directorio de salida).
2. **Base de datos** (engine asíncrono y fábrica de sesiones).
3. **Servicios sustituibles**: ejecutor de trabajos (`JobRunner`) y bitácora de auditoría (`AuditLog`).

Los dos últimos existen ya como interfaces en el prompt (sección 3: "El procesamiento asíncrono de
exámenes se ejecuta mediante una cola de trabajos (Celery o RQ) o de forma síncrona en un proceso
separado" y sección 15: "Auditoría: cada acción relevante genera un evento de auditoría"), pero en
esta fase no hay infraestructura de cola ni de almacén persistente de auditoría.

Restricciones que gobiernan la decisión:

1. Cero estado global mutable en el núcleo (regla literal de `AGENTS.md`).
2. mypy **estricto** sobre `src/`.
3. Cobertura ≥ 85 % (`fail_under = 85`).
4. Sin singletons, sin variables de módulo mutables, sin "cargar todo al importar el módulo".
5. La aplicación debe poder construirse en una prueba con una configuración distinta (SQLite en
   memoria) sin tocar variables de entorno globales.

## Decision

**El núcleo se construye como objetos explícitos que se inyectan, con la configuración como valor
inmutable y el estado de la aplicación en `app.state`.**

- `Settings` es una `BaseSettings` de Pydantic con `frozen=True`: no se puede mutar en runtime. Se
  valida al arrancar (URL de base de datos con driver asíncrono admitido, nivel de log válido,
  `app_env` dentro de un `Literal`, rangos de negocio no invertidos).
- `Database` encapsula `AsyncEngine` + `async_sessionmaker` y se crea **una vez por aplicación**. Vive
  en `app.state.database`; la dependencia `get_session(request)` lo obtiene de ahí, de modo que una
  prueba puede inyectar cualquier base de datos sin tocar el código de servicio.
- `JobRunner` y `AuditLog` se definen como `Protocol` (interfaces estructurales). La implementación
  actual (`InlineJobRunner`, `InMemoryAuditLog`) se instancia y se inyecta; cuando llegue Celery o una
  tabla de auditoría, solo cambia la implementación, no las interfaces ni el código que las usa.
- El ciclo de vida de los recursos (abrir/cerrar el engine) se resuelve en el `lifespan` de FastAPI.
- El identificador de correlación `request_id` **no** es estado global: viaja en `contextvars`
  (ver ADR-0004), que son seguras con `asyncio` porque cada tarea hereda el contexto de su padre.

## Options Considered

### Option A: Objetos explícitos con configuración inmutable (elegida)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Media — un constructor por recurso, sin ceremonia |
| Cost | Nulo — solo biblioteca estándar y Pydantic |
| Scalability | Alta — cada aplicación tiene sus propios recursos; permite varios procesos |
| Team familiarity | Alta — patrón estándar de FastAPI (`app.state` + dependencias) |
| mypy estricto | Buena — `Protocol` con tipos explícitos; `Settings` tipado por Pydantic |
| Testabilidad | Alta — cada prueba construye su propio `Settings`/`Database` |

**Pros:** cumple literalmente la regla de "sin estado global mutable"; el fallo de configuración se
detecta al arrancar y no en la primera petición; las pruebas son deterministas y paralelizables;
cambiar la implementación de `JobRunner` o `AuditLog` no toca a los servicios que los usan.

**Cons:** hay que pasar (o registrar en `app.state`) lo que antes era "global"; `app.state` es un
espacio con tipado débil, que hay que cubrir con pruebas.

### Option B: Módulos con estado a nivel de módulo (singles)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Baja — `from core.db import session` y listo |
| Cost | Nulo |
| Scalability | Baja — el estado es compartido por todo el proceso |
| Team familiarity | Alta — habitual en scripts, poco habitual en servicios |
| mypy estricto | Regular — variables de módulo mutables se escapan del control de tipos |
| Testabilidad | Mala — el estado de una prueba se filtra a la siguiente |

**Pros:** código más corto en los servicios.

**Cons:** viola la restricción explícita del prompt; dos pruebas que usen bases distintas se
contaminan; no se puede ejecutar la aplicación con dos configuraciones en el mismo proceso (tests
paralelos, `TestClient` anidados).

### Option C: Contenedor de dependencias (inyector tipo FastAPI Depends global o puntero de servicio)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Alta — hay que resolver ciclos, vida útil y scopes |
| Cost | Nulo (implementación propia) o bajo (librería externa) |
| Scalability | Media — más indirección que recursos |
| Team familiarity | Media — útil en proyectos grandes, superfluous aquí |
| mypy estricto | Regular — los contenedores genéricos complican el tipado estricto |
| Testabilidad | Buena, pero con más maquinaria |

**Pros:** desacopla la construcción de la resolución; muy útil si el grafo crece mucho.

**Cons:** el grafo del núcleo es pequeño (configuración, engine, dos interfaces); un contenedor
introduciría un framework propio que hay que mantener sin problema real que resuelva.

### Option D: Variables de entorno leídas bajo demanda (sin `Settings`)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Baja |
| Cost | Nulo |
| Scalability | Media |
| Team familiarity | Alta |
| mypy estricto | Mala — `os.environ` devuelve `str`; cada valor necesita parseo y validación a mano |
| Testabilidad | Regular — depende de mutar `os.environ` |

**Pros:** sin clases de configuración.

**Cons:** sin validación centralizada: los errores aparecen tarde y en lugares lejanos; se pierde la
inmutabilidad y la tipificación de la configuración.

## Trade-off Analysis

La tensión central es entre **comodidad** y **control**. La opción B es la más cómoda de escribir y la
peor encaja con las restricciones: el prompt pide precisamente que el núcleo sea sustituible y
testeable. La opción A paga un coste pequeño (un constructor más, `app.state`) a cambio de detectar
configuraciones inválidas en el arranque y de permitir pruebas aisladas.

La opción C se descarta por sobreingeniería: las piezas inyectadas son pocas y sus dependencias son
lineales, sin ciclos. La opción D se descarta porque `Settings` con Pydantic v2 da validación, tipos y
documentación de forma gratuita, y `pydantic-settings` ya está en el stack fijo.

## Consequences

- El núcleo no tiene variables de módulo mutables: `Settings` es inmutable y los recursos viven en
  `app.state` o se inyectan como argumentos.
- Los errores de configuración (URL síncrona, nivel de log inválido, rangos invertidos) se detectan
  al arrancar la aplicación, con un mensaje legible.
- `get_session(request)` desacopla los repositorios del motor: el mismo código corre en SQLite y
  PostgreSQL, y las pruebas usan una base en memoria con `StaticPool`.
- `JobRunner` y `AuditLog` son interfaces: la llegada de Celery (paso 8) o de una tabla de auditoría
  (paso 4+) es un cambio de implementación, no de arquitectura.
- Coste a vigilar: `app.state` no está tipado; el contrato `app.state.database` / `app.state.settings`
  queda cubierto por pruebas, no por el compilador.
- `Settings` es reentrante pero `configure_logging` reconfigura el logger raíz: por eso se invoca una
  sola vez al construir la aplicación y el test que lo verifica exige idempotencia.

## Action Items

1. [x] Definir `Settings` inmutable con validadores de URL de base de datos, nivel de log, entorno y
      rangos de negocio (paso 2).
2. [x] Crear `Database` (engine + `async_sessionmaker`) y la dependencia `get_session` sobre
      `app.state.database` (paso 2).
3. [x] Definir `JobRunner` y `AuditLog` como `Protocol` con implementaciones inline/en memoria
      (paso 2).
4. [ ] Registrar `JobRunner` y `AuditLog` en `app.state` y exponerlos por dependencia de FastAPI
      cuando existan servicios que los necesiten (paso 8).
5. [ ] Sustituir `InMemoryAuditLog` por un repositorio sobre la tabla de auditoría (paso 4+).
6. [ ] Añadir una prueba de contrato que verifique que `InlineJobRunner` y el futuro `CeleryJobRunner`
      cumplen el mismo `Protocol`.
