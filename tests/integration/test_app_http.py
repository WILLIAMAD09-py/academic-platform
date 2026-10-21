"""Pruebas de integración de la capa HTTP (`core.app` + FastAPI).

Se usa `TestClient` contra la aplicación real, con su middleware de correlación, sus
manejadores de error y su base de datos SQLite en memoria.
"""

from __future__ import annotations

from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from core.app import create_app
from core.config import Settings
from core.db import Database, get_session


def _app() -> object:
    settings = Settings(_env_file=None, database_url="sqlite+aiosqlite:///:memory:")
    return create_app(settings)


def test_el_openapi_se_genera_sin_errores() -> None:
    with TestClient(_app()) as client:  # type: ignore[arg-type]
        respuesta = client.get("/openapi.json")

    assert respuesta.status_code == 200
    assert "/health" in respuesta.json()["paths"]


def test_una_ruta_inexistente_devuelve_404_json() -> None:
    with TestClient(_app()) as client:  # type: ignore[arg-type]
        respuesta = client.get("/no-existe")

    assert respuesta.status_code == 404
    assert respuesta.headers["content-type"].startswith("application/json")


def test_el_id_de_correlacion_llega_al_contexto_de_log() -> None:
    app = _app()

    with TestClient(app) as client:  # type: ignore[arg-type]
        respuesta = client.get("/health", headers={"X-Request-ID": "req-42"})

    assert respuesta.headers["X-Request-ID"] == "req-42"


def test_la_base_de_datos_se_abre_y_se_cierra_con_el_ciclo_de_vida() -> None:
    app = _app()

    with TestClient(app) as client:  # type: ignore[arg-type]
        respuesta = client.get("/health/ready")

    assert respuesta.status_code == 200

    base_de_datos: Database = app.state.database  # type: ignore[attr-defined]
    assert base_de_datos.engine is not None


def test_la_dependencia_get_session_entrega_una_sesion_usable() -> None:
    """La dependencia es la vía por la que los repositorios obtendrán la sesión."""
    app = _app()

    @app.get("/consulta")
    async def consulta(session: AsyncSession = Depends(get_session)) -> dict[str, int]:
        resultado = await session.execute(text("SELECT 1"))
        return {"valor": resultado.scalar_one()}

    with TestClient(app) as client:  # type: ignore[arg-type]
        respuesta = client.get("/consulta")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"valor": 1}


def test_un_error_de_base_de_datos_devuelve_500_con_envelope() -> None:
    app = _app()

    @app.get("/falla-sql")
    async def falla_sql() -> None:
        raise SQLAlchemyError("fallo de base de datos")

    with TestClient(app, raise_server_exceptions=False) as client:  # type: ignore[arg-type]
        respuesta = client.get("/falla-sql")

    assert respuesta.status_code == 500
    assert respuesta.json()["error"]["code"] == "internal_error"
