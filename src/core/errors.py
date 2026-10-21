"""Errores controlados de la aplicación.

Este módulo es **puro** (solo biblioteca estándar): define la jerarquía de
excepciones, sin ninguna dependencia de FastAPI, SQLAlchemy o del resto del
núcleo. Así, el dominio de negocio puede heredar de estas clases sin arrastrar
la capa web en su grafo de imports.

La traducción de estas excepciones a respuestas HTTP vive en
`core.error_handlers` (capa de presentación).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class AppError(Exception):
    """Error controlado de la aplicación.

    Attributes:
        message: Mensaje apto para mostrar al usuario final.
        details: Contexto adicional estructurado (nunca datos sensibles).
    """

    code: str = "app_error"
    status_code: int = 500

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = dict(details or {})

    def to_payload(self) -> dict[str, Any]:
        """Representación serializable del error."""
        return {"code": self.code, "message": self.message, "details": self.details}


class NotFoundError(AppError):
    """El recurso solicitado no existe."""

    code = "not_found"
    status_code = 404


class ConflictError(AppError):
    """El recurso ya existe o la operación choca con el estado actual."""

    code = "conflict"
    status_code = 409


class InvalidStateError(AppError):
    """La operación no es válida para el estado actual del recurso."""

    code = "invalid_state"
    status_code = 409


class ValidationFailedError(AppError):
    """Los datos no cumplen las reglas de negocio (no la validación de forma)."""

    code = "validation_failed"
    status_code = 422


class ExternalServiceError(AppError):
    """Un servicio externo falló o respondió de forma inesperada."""

    code = "external_service_error"
    status_code = 502


class InternalError(AppError):
    """Fallo no controlado: el cliente recibe un mensaje genérico, nunca el detalle."""

    code = "internal_error"
    status_code = 500
