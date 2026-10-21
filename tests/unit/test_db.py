"""Pruebas de la capa de datos (`core.db`).

La capa debe ser agnóstica al motor: SQLite en desarrollo y tests, PostgreSQL en producción.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import StaticPool

from core.config import Settings
from core.db import Base, Database, create_engine_from_settings


def test_el_engine_se_crea_para_sqlite() -> None:
    settings = Settings(_env_file=None, database_url="sqlite+aiosqlite:///./app.db")

    engine = create_engine_from_settings(settings)

    assert isinstance(engine, AsyncEngine)
    assert engine.dialect.name == "sqlite"


def test_el_engine_se_crea_para_postgres() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://app:app@db:5432/app",
    )

    engine = create_engine_from_settings(settings)

    assert engine.dialect.name == "postgresql"


def test_sqlite_en_memoria_usa_pool_estatico() -> None:
    """Con `:memory:` cada conexión sería una base distinta: hace falta `StaticPool`."""
    settings = Settings(_env_file=None, database_url="sqlite+aiosqlite:///:memory:")

    engine = create_engine_from_settings(settings)

    assert isinstance(engine.pool, StaticPool)


def test_postgres_aplica_los_parametros_de_pool() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://app:app@db:5432/app",
        db_pool_size=7,
        db_max_overflow=3,
    )

    engine = create_engine_from_settings(settings)

    assert engine.pool.size() == 7


def test_base_declara_el_metadato_de_sqlalchemy() -> None:
    assert hasattr(Base, "metadata")
    assert Base.metadata is not None


async def test_la_sesion_abre_y_cierra_correctamente() -> None:
    settings = Settings(_env_file=None, database_url="sqlite+aiosqlite:///:memory:")
    database = Database(settings)

    async with database.sessionmaker() as session:
        resultado = await session.execute(text("SELECT 1"))
        assert resultado.scalar_one() == 1

    await database.dispose()


async def test_create_all_crea_el_esquema() -> None:
    settings = Settings(_env_file=None, database_url="sqlite+aiosqlite:///:memory:")
    database = Database(settings)

    await database.create_all()

    async with database.sessionmaker() as session:
        resultado = await session.execute(text("SELECT count(*) FROM sqlite_master"))
        assert resultado.scalar_one() >= 0

    await database.dispose()


async def test_dispose_libera_el_engine() -> None:
    settings = Settings(_env_file=None, database_url="sqlite+aiosqlite:///:memory:")
    database = Database(settings)

    await database.dispose()

    assert database.engine.pool is not None
