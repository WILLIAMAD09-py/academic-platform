# Plataforma de Automatización Académica

Backend (Fase 1) de una plataforma para automatizar la generación de documentos académicos: exámenes
imprimibles, claves aleatorizadas y resumen de hoja de respuestas.

- Especificación de la fase: [`docs/PROMPT_FASE1.md`](docs/PROMPT_FASE1.md)
- Reglas permanentes del proyecto: [`AGENTS.md`](.opencode/skills/AGENTS.md)
- Suposiciones: [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md)
- Decisiones de arquitectura: [`docs/ADR/`](docs/ADR/)

> **Estado:** Fase 1 en curso. El paso 1 (scaffolding) está completo; los pasos 2–12 están pendientes.

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

> Hasta el paso 2 el servicio `app` sale con `Exited (3)` y el error
> `Could not import module "core.app"`: el punto de entrada `core.app:app` se crea en el paso 2.
> La imagen, la red y la conexión con PostgreSQL ya están verificadas. Ver `docs/ASSUMPTIONS.md` (A20, A23).

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
