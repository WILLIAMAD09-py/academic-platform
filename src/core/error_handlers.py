"""Traducción de los errores de la aplicación a respuestas HTTP.

Esta módulo pertenece a la **capa de presentación**: es el único punto donde
las excepciones controladas de `core.errors` se convierten en el envelope de
error que consume el frontend.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from core.errors import AppError, InternalError
from core.logging import get_context

logger = logging.getLogger("core.errors")


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
