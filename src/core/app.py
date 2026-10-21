"""Fábrica de la aplicación FastAPI.

Aquí se ensamblan las piezas del núcleo: configuración, logging, base de datos,
manejadores de error y el punto de extensión de los routers (paso 10).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import RequestResponseEndpoint

from core import __version__
from core.config import Settings
from core.db import Database
from core.error_handlers import register_exception_handlers
from core.logging import configure_logging, context_scope

logger = logging.getLogger("core.app")

#: Punto de extensión de los routers de negocio (se rellena en el paso 10).
ROUTERS: tuple[APIRouter, ...] = ()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Crea la aplicación lista para servir.

    Args:
        settings: Configuración a usar. Si no se indica, se lee del entorno.
    """
    configuracion = settings if settings is not None else Settings()
    configure_logging(configuracion)
    database = Database(configuracion)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "api.inicio",
            extra={"env": configuracion.app_env, "version": __version__},
        )
        try:
            yield
        finally:
            await database.dispose()
            logger.info("api.fin")

    app = FastAPI(
        title=configuracion.api_title,
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.settings = configuracion
    app.state.database = database

    @app.middleware("http")
    async def correlacion(request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Propaga el identificador de correlación a los logs y a la respuesta."""
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        exam_code = request.headers.get("X-Exam-Code")
        with context_scope(request_id=request_id, exam_code=exam_code):
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/health", tags=["sistema"], summary="Comprobación de vida")
    def health() -> dict[str, str]:
        """El proceso está vivo. No consulta la base de datos."""
        return {
            "status": "ok",
            "version": __version__,
            "env": configuracion.app_env,
        }

    @app.get("/health/ready", tags=["sistema"], summary="Comprobación de disponibilidad")
    async def health_ready() -> JSONResponse:
        """El proceso además puede atender peticiones contra la base de datos."""
        try:
            async with database.sessionmaker() as session:
                await session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            # El detalle del fallo se queda en el log: el cliente solo recibe
            # que la base de datos no está disponible.
            logger.exception("api.base_de_datos_no_disponible")
            return JSONResponse(
                status_code=503,
                content={"status": "unavailable", "database": "error"},
            )
        return JSONResponse(status_code=200, content={"status": "ok", "database": "ok"})

    if configuracion.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(configuracion.cors_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)

    for router in ROUTERS:
        app.include_router(router)

    return app


app = create_app()
