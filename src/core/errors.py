"""Errores de la aplicación y su traducción a respuestas HTTP.

La jerarquía de errores es **agnóstica de la capa de presentación**: los
servicios y repositorios lanzan estas excepciones, y es la capa HTTP la que las
traduce al envelope de error que consume el frontend.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from core.logging import get_context

logger = logging.getLogger("core.errors")


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


def error_envelope(error: AppError) -> dict[str, Any]:
    """Envoltura estándar de error, con el `request_id` de correlación."""
    return {"error": error.to_payload(), "request_id": get_context()["request_id"]}


def register_exception_handlers(app: FastAPI) -> None:
    """Registra los manejadores de error de la aplicación."""

    @app.exception_handler(AppError)
    async def _maneja_app_error(request: Request, exc: Exception) -> JSONResponse:
        error = exc if isinstance(exc, AppError) else AppError(str(exc))
        logger.info(
            "error.aplicacion",
            extra={"error_code": error.code, "path": request.url.path},
        )
        return JSONResponse(status_code=error.status_code, content=error_envelope(error))

    @app.exception_handler(SQLAlchemyError)
    async def _maneja_error_de_base_de_datos(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "error.base_de_datos",
            extra={"path": request.url.path},
        )
        error = InternalError("Error interno del servidor")
        return JSONResponse(status_code=error.status_code, content=error_envelope(error))

    @app.exception_handler(Exception)
    async def _maneja_error_inesperado(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "error.no_controlado",
            extra={"path": request.url.path, "error_type": type(exc).__name__},
        )
        error = InternalError("Error interno del servidor")
        return JSONResponse(status_code=error.status_code, content=error_envelope(error))
