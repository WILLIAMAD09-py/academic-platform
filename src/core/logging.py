"""Logging estructurado del núcleo.

El requisito no funcional (sección 15 del prompt) pide logging estructurado en
JSON con `exam_id`, `exam_code` y `request_id` en cada línea.

Esos tres campos viajan en *contextvars*, no en los argumentos del logger, para
que cualquier capa (API, pipeline, repositorios) pueda añadir contexto sin
tener que arrastrarlo por todas las firmas. Los contextvars son seguros con
`asyncio`: cada tarea hijo hereda el contexto de su padre.

Ver `docs/ADR/0004-logging-estructurado-contextvars.md`.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from core.config import Settings

#: Contexto de correlación que se inyecta en cada línea de log.
_EXAM_ID: ContextVar[str | None] = ContextVar("exam_id", default=None)
_EXAM_CODE: ContextVar[str | None] = ContextVar("exam_code", default=None)
_REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)

_CONTEXT_VARS: dict[str, ContextVar[str | None]] = {
    "exam_id": _EXAM_ID,
    "exam_code": _EXAM_CODE,
    "request_id": _REQUEST_ID,
}

#: Atributos estándar de `logging.LogRecord`; el resto se considera campo extra.
_RESERVED_RECORD_FIELDS: frozenset[str] = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


def get_context() -> dict[str, str | None]:
    """Devuelve el contexto de correlación vigente."""
    return {nombre: variable.get() for nombre, variable in _CONTEXT_VARS.items()}


def set_context(**values: str | None) -> None:
    """Fija valores del contexto de correlación.

    Solo se tocan los campos indicados; el resto conserva su valor.
    """
    for nombre, valor in values.items():
        variable = _CONTEXT_VARS.get(nombre)
        if variable is None:
            raise KeyError(f"campo de contexto desconocido: {nombre!r}")
        variable.set(valor)


def clear_context() -> None:
    """Vacía el contexto de correlación."""
    for variable in _CONTEXT_VARS.values():
        variable.set(None)


@contextmanager
def context_scope(**values: str | None) -> Iterator[None]:
    """Aplica un contexto temporal y lo restaura al salir (también ante excepción).

    Permite anidar contextos: al salir, se restaura exactamente el valor que
    había antes, no `None`.
    """
    tokens: list[tuple[ContextVar[str | None], Token[str | None]]] = []
    for nombre, valor in values.items():
        variable = _CONTEXT_VARS.get(nombre)
        if variable is None:
            raise KeyError(f"campo de contexto desconocido: {nombre!r}")
        tokens.append((variable, variable.set(valor)))
    try:
        yield
    finally:
        for variable, token in reversed(tokens):
            variable.reset(token)


def extra_fields(record: logging.LogRecord) -> Mapping[str, Any]:
    """Campos propios del registro (los que no son estándar de `logging`)."""
    return {
        clave: valor
        for clave, valor in record.__dict__.items()
        if clave not in _RESERVED_RECORD_FIELDS and not clave.startswith("_")
    }


class JsonFormatter(logging.Formatter):
    """Formatea cada registro como una línea JSON con el contexto de correlación."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(get_context())
        payload.update(extra_fields(record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class HumanFormatter(logging.Formatter):
    """Formato legible para desarrollo local, con el contexto entre corchetes."""

    def __init__(self) -> None:
        super().__init__(fmt="%(asctime)s %(levelname)-8s %(name)s %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        partes = [f"{nombre}={valor}" for nombre, valor in get_context().items() if valor]
        if not partes:
            return base
        return f"{base} [{' '.join(partes)}]"


def configure_logging(settings: Settings) -> None:
    """Configura el logging raíz según la configuración de la aplicación.

    Es idempotente: llamarla dos veces no duplica manejadores.
    """
    raiz = logging.getLogger()
    for manejador in list(raiz.handlers):
        raiz.removeHandler(manejador)

    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(JsonFormatter() if settings.log_json else HumanFormatter())
    raiz.addHandler(manejador)
    raiz.setLevel(settings.log_level)

    # Uvicorn trae sus propios manejadores: se quitan para que sus líneas
    # pasen por el mismo formateador estructurado.
    for nombre in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(nombre)
        logger.handlers = []
        logger.propagate = True
