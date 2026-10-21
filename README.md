# Plataforma de Automatización Académica

Backend (Fase 1) de una plataforma para automatizar la generación de documentos académicos: exámenes
imprimibles, claves aleatorizadas y resumen de hoja de respuestas.

- Especificación de la fase: [`docs/PROMPT_FASE1.md`](docs/PROMPT_FASE1.md)
- Reglas permanentes del proyecto: [`AGENTS.md`](.opencode/skills/AGENTS.md)
- Suposiciones: [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md)
- Decisiones de arquitectura: [`docs/ADR/`](docs/ADR/)

> **Estado:** Fase 1 en curso. Los pasos 1 (scaffolding) y 2 (núcleo `src/core/`) están completos; los
> pasos 3–12 están pendientes.

## Stack

Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.x + Alembic · PostgreSQL (prod) / SQLite (dev y
tests) · `python-docx` · pytest · ruff · mypy estricto.

## Instalación

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
```

## Variables de entorno

Copia `.env.example` a `.env` y ajústalo. Los valores por defecto apuntan a SQLite, de modo que el
proyecto arranca sin infraestructura externa.

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

## Comandos

| Tarea | Comando |
|-------|---------|
| Tests | `pytest --cov=src` |
| Lint y formato | `ruff check . && ruff format --check .` |
| Tipos | `mypy src` |
| Formatear | `ruff format .` |
| Entorno con Docker | `docker compose up` |
| API (local) | `uvicorn core.app:app --reload` |

## Docker

`docker compose` levanta **dos servicios** en una red privada:

| Servicio | Imagen | Qué hace | Puerto |
|----------|--------|----------|--------|
| `db` | `postgres:16-alpine` | Base de datos de desarrollo. Datos persistidos en el volumen `pgdata`. Healthcheck con `pg_isready`. | `5432` |
| `app` | `academic-platform:0.1.0` (se construye desde el `Dockerfile`) | La API FastAPI con `uvicorn core.app:app`. | `8000` |

El `app` espera a que `db` esté `healthy` antes de arrancar (`depends_on: condition: service_healthy`).
Los volúmenes `./src`, `./migrations` y `./output` se montan dentro del contenedor, de modo que el
código se recarga sin reconstruir la imagen.

```bash
docker compose build        # Construye la imagen de la aplicación
docker compose up -d        # Levanta db + app en segundo plano
docker compose ps           # Estado y healthchecks
docker compose logs -f app  # Logs de la API
docker compose down         # Apaga el stack (conserva los datos)
docker compose down -v      # Apaga el stack y borra el volumen de PostgreSQL
```

La API responde `GET http://localhost:8000/health` con `200 {"status":"ok","version":"0.1.0"}` y
`GET http://localhost:8000/health/ready` con `200 {"status":"ok","database":"ok"}` (consulta la base de
datos; responde `503` si no está disponible). El esquema OpenAPI está en `http://localhost:8000/docs`.

Para ejecutar la suite de tests **dentro del contenedor** (etapa `test` del `Dockerfile`, con las
dependencias de desarrollo):

```bash
docker compose --profile test run --rm tests
```

> Hasta el paso 2 el servicio `app` expone únicamente las rutas de salud. El montaje de los routers de
> exámenes se incorpora en el paso 10. Ver `docs/ASSUMPTIONS.md` (A20, A23).

## Núcleo (`src/core/`)

| Módulo | Responsabilidad |
|--------|-----------------|
| `core/config.py` | `Settings` (Pydantic v2, inmutable) leída del entorno, con validación temprana del URL de base de datos, del nivel de log y de los rangos de negocio. |
| `core/logging.py` | Logging estructurado en JSON con `exam_id`, `exam_code` y `request_id` en cada línea, propagados con `contextvars`. |
| `core/errors.py` | Jerarquía de errores (`NotFoundError`, `ConflictError`, `InvalidStateError`, `ValidationFailedError`, `ExternalServiceError`) y su envelope JSON. |
| `core/db.py` | Engine asíncrono agnóstico al motor (SQLite / PostgreSQL), `Base` declarativa, sesiones y dependencia `get_session`. |
| `core/jobs.py` | Interfaz `JobRunner` (`Protocol`) e implementación `InlineJobRunner`, lista para sustituirse por Celery/RQ. |
| `core/audit.py` | Interfaz `AuditLog` (`Protocol`) e implementación `InMemoryAuditLog`. |
| `core/app.py` | Fábrica de la aplicación: logging, base de datos, middleware de correlación, manejadores de error y punto de extensión de routers. |

Decisiones que lo gobiernan: [ADR-0003](docs/ADR/0003-nucleo-sin-estado-global.md) (núcleo sin estado
global) y [ADR-0004](docs/ADR/0004-logging-estructurado-contextvars.md) (logging con `contextvars`).

## Ejecución del examen de ejemplo

Disponible a partir del paso 11:

```bash
python -m modules.exams.cli process --file tests/fixtures/examen_vc_ej26.json --keys 2 --out ./output
```

## Estructura

```
src/
├── core/                 # Núcleo compartido (config, db, jobs, audit, errors, logging, documents)
└── modules/
    └── exams/            # Módulo de exámenes
        ├── api/          # Routers FastAPI
        ├── domain/       # Puro: modelos, reglas, estados, ponderación
        ├── application/  # Casos de uso: pipeline, formato, revisión, claves
        └── infrastructure/  # ORM, repositorios, revisores, renderizador DOCX
tests/
├── unit/
├── integration/
└── fixtures/
web/                      # Frontend (fase 2). Solo README con el contrato de API.
docs/                     # Prompt de fase, ADR, supuestos, arquitectura
```

**Regla de dependencias:** `domain` no importa de `infrastructure` ni de `api`; `application` depende de
`domain` y de interfaces; `infrastructure` implementa esas interfaces. Verificado por test de
arquitectura.

## Nota sobre el nombre del núcleo

El prompt de fase y `AGENTS.md` nombran el núcleo compartido `src/platform/`. Ese nombre **no es
importable**: `platform` es un módulo de la stdlib de Python que tiene prioridad sobre `site-packages`.
El directorio real es `src/core/`. Ver `docs/ASSUMPTIONS.md` (A14).
