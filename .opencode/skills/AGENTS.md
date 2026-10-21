# AGENTS.md — Reglas del proyecto

Plataforma de automatización académica (documentos, minutas, exámenes, indicadores). Este archivo contiene reglas permanentes. La tarea de cada fase está en `docs/PROMPT_FASE1.md` (o el archivo de la fase vigente).

## Idioma

- Documentación, comentarios de dominio y mensajes al usuario: **español**.
- Identificadores de código (clases, funciones, variables, archivos): **inglés**.
- Términos de dominio que no deben traducirse: `exam_code`, `key_letter`, `position`, `stimulus_group`, `Block`, `shuffle_question`, `shuffle_options`, `locked`.

## Stack

- Python 3.12, FastAPI, Pydantic v2.
- SQLAlchemy 2.x (declarativo tipado) + Alembic. PostgreSQL en producción, SQLite en desarrollo y tests. La capa de datos no debe depender del motor.
- `python-docx` para `.docx`. PDF vía LibreOffice headless, como adaptador opcional.
- `pydantic-settings` para configuración por variables de entorno.
- pytest + pytest-cov (cobertura ≥ 85% en núcleo de exámenes, aleatorización y formato).
- ruff (lint y format), mypy estricto en `src/`.
- No usar Redis, Celery, autenticación compleja ni multi-tenant en esta etapa. Solo dejar puntos de extensión.

## Modelo de IA

- El modelo de revisión de preguntas lo entrena y lo aporta el usuario. Se conecta por adaptador local (`nlp_adapter.py`).
- Prohibido llamar a APIs externas de modelos de IA (OpenAI, Anthropic, Google u otras) desde el código de la aplicación, incluidos el stub y el adaptador.
- La herramienta de desarrollo (OpenCode) usa su propio modelo para programar. Eso no forma parte del producto y no debe aparecer en su código.

## Estructura

- `src/platform/`: núcleo compartido (config, db, jobs, audit, errors, logging, documents).
- `src/modules/exams/`: módulo de exámenes, con capas `api/`, `domain/`, `application/`, `infrastructure/`.
- `domain/` no importa de `infrastructure/` ni de `api/`.
- `application/` depende de `domain/` y de interfaces. `infrastructure/` implementa esas interfaces.
- No dupliques lógica entre `application/` e `infrastructure/`.
- `web/` solo tiene `README.md` en esta etapa.

## Reglas de código

- Sin estado global mutable en el núcleo.
- Aleatorización: usar `random.Random(seed)` por clave. Nunca el RNG global.
- Toda generación de claves pasa por `verify_keys` antes de persistir.
- Nunca sobrescribir el texto original del docente. Guardar el original y el vigente por separado.
- Los documentos generados pasan por el verificador de formato antes de considerarse terminados.
- Validación de entrada con Pydantic. Límites de tamaño de texto. Nombres de archivo generados por el sistema, nunca tomados del usuario.
- Logs estructurados (JSON) con `exam_id`, `exam_code` y `request_id`.

## Reglas de trabajo

- Antes de implementar, revisa el paso correspondiente del orden de trabajo de la fase.
- Si una regla del prompt no se puede cumplir, repórtalo. No la cambies en silencio.
- Las decisiones de diseño no triviales se documentan como ADR en `docs/ADR/`.
- Las suposiciones que tomes sobre puntos ambiguos van a `docs/ASSUMPTIONS.md`.
- Al terminar cada paso, da un resumen corto: qué se hizo, qué pruebas pasan y qué queda pendiente. Espera confirmación antes del siguiente paso.
- No marques un paso como terminado con pruebas fallando.

## Skills disponibles

- **architecture**: para cada decisión técnica relevante (ADR con trade-offs).
- **system-design**: para diseño de componentes y del pipeline.
- **testing-strategy**: para definir pruebas antes de implementar.
- **code-review**: para revisar cada paso antes de darlo por terminado.

## Comandos

- Instalar dependencias: `pip install -e ".[dev]"`
- Tests: `pytest --cov=src`
- Lint y formato: `ruff check . && ruff format --check .`
- Tipos: `mypy src`
- Levantar entorno: `docker compose up`

Ajusta los comandos cuando el `pyproject.toml` exista.
