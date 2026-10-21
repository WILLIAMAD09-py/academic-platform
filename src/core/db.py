"""Capa de datos: engine, sesiones y base declarativa.

La capa es **agnóstica del motor**: SQLite en desarrollo y pruebas, PostgreSQL
en producción. Ningún servicio conoce el motor; todos reciben la sesión desde
la dependencia `get_session`.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from core.config import Settings


class Base(DeclarativeBase):
    """Base declarativa común a todos los modelos (los define el paso 4)."""


def _es_memoria(url: str) -> bool:
    """`True` si el URL apunta a una base SQLite en memoria."""
    return ":memory:" in url or "mode=memory" in url


def create_engine_from_settings(settings: Settings) -> AsyncEngine:
    """Crea el engine asíncrono adecuado al motor configurado.

    SQLite en memoria usa `StaticPool`: con el pool por defecto cada conexión
    abriría una base distinta y los datos se perderían entre sesiones.
    """
    opciones: dict[str, Any] = {"echo": settings.db_echo}

    if settings.is_sqlite:
        if _es_memoria(settings.database_url):
            opciones["poolclass"] = StaticPool
    else:
        opciones["pool_size"] = settings.db_pool_size
        opciones["max_overflow"] = settings.db_max_overflow
        opciones["pool_pre_ping"] = True

    return create_async_engine(settings.database_url, **opciones)


class Database:
    """Agrupa el engine y la fábrica de sesiones de una aplicación."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine = create_engine_from_settings(settings)
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    @property
    def settings(self) -> Settings:
        """Configuración con la que se construyó la base de datos."""
        return self._settings

    @property
    def engine(self) -> AsyncEngine:
        """Engine asíncrono subyacente."""
        return self._engine

    @property
    def sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        """Fábrica de sesiones (una sesión por unidad de trabajo)."""
        return self._sessionmaker

    async def create_all(self) -> None:
        """Crea el esquema a partir de los modelos registrados en `Base`."""
        async with self._engine.begin() as conexion:
            await conexion.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        """Cierra el engine y devuelve sus conexiones al pool."""
        await self._engine.dispose()


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Dependencia de FastAPI: entrega una sesión por petición.

    La sesión se obtiene de `app.state.database`, de modo que la aplicación
    puede probarse con cualquier base de datos sin tocar el código de servicio.
    """
    database: Database = request.app.state.database
    async with database.sessionmaker() as session:
        yield session
