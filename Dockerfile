# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Dependencias del sistema. `libreoffice` se añade solo si se habilita el
# adaptador de exportación a PDF (ver docs/ASSUMPTIONS.md A20).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip install .

# `alembic.ini` y las migraciones generadas se incorporan en el paso 4
# (primera migración Alembic); por eso aquí solo se copia el directorio.
COPY migrations ./migrations

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "core.app:app", "--host", "0.0.0.0", "--port", "8000"]

# --- Etapa de tests -------------------------------------------------------
# Variante con las dependencias de desarrollo para ejecutar la suite dentro
# del contenedor: `docker compose --profile test run --rm tests`.
#
# Ojo: la etapa por defecto de `docker build` es la ULTIMA del fichero. Si esta
# etapa se quedara al final, `docker compose build` construiria la imagen de
# tests para el servicio `app`. Por eso se declara explicitamente `target` en
# `docker-compose.yml` y la etapa de runtime se llama `runtime`.
FROM runtime AS test

COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests

RUN pip install ".[dev]"

# El contenedor de tests no levanta servidor: el healthcheck no aplica.
HEALTHCHECK NONE

CMD ["python", "-m", "pytest", "--cov=src", "-q"]
