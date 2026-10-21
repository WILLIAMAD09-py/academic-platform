"""Pruebas de la fábrica de la aplicación (`core.app`)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import __version__
from core.app import create_app
from core.config import Settings


def _settings() -> Settings:
    return Settings(_env_file=None, database_url="sqlite+aiosqlite:///:memory:")


def test_la_aplicacion_se_crea_con_los_metadatos_configurados() -> None:
    app = create_app(_settings())

    assert isinstance(app, FastAPI)
    assert app.version == __version__
    assert app.title == "Plataforma de Automatización Académica"


def test_la_configuracion_y_la_base_de_datos_quedan_en_el_estado() -> None:
    settings = _settings()

    app = create_app(settings)

    assert app.state.settings is settings
    assert app.state.database is not None


def test_health_responde_ok() -> None:
    with TestClient(create_app(_settings())) as client:
        respuesta = client.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "ok"
    assert respuesta.json()["version"] == __version__


def test_health_no_toca_la_base_de_datos() -> None:
    """`/health` es comprobación de vida; la de disponibilidad va en `/health/ready`."""
    with TestClient(create_app(_settings())) as client:
        respuesta = client.get("/health")

    assert respuesta.status_code == 200


def test_health_ready_responde_ok_con_base_de_datos() -> None:
    with TestClient(create_app(_settings())) as client:
        respuesta = client.get("/health/ready")

    assert respuesta.status_code == 200
    assert respuesta.json()["database"] == "ok"


def test_health_ready_responde_503_si_la_base_de_datos_no_responde() -> None:
    """Un directorio inexistente hace fallar la conexión: el probe debe decirlo."""
    settings = Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite:///Z:/directorio-inexistente-12345/app.db",
    )

    with TestClient(create_app(settings)) as client:
        respuesta = client.get("/health/ready")

    assert respuesta.status_code == 503
    assert respuesta.json()["database"] == "error"
    # El detalle del error no se filtra al cliente.
    assert "detail" not in respuesta.json()


def test_cors_permite_los_origenes_configurados() -> None:
    settings = Settings(_env_file=None, cors_origins=["http://localhost:5173"])

    with TestClient(create_app(settings)) as client:
        respuesta = client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert respuesta.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_no_autoriza_un_origen_desconocido() -> None:
    settings = Settings(_env_file=None, cors_origins=["http://localhost:5173"])

    with TestClient(create_app(settings)) as client:
        respuesta = client.get("/health", headers={"Origin": "http://otro-engano.test"})

    assert "access-control-allow-origin" not in respuesta.headers


def test_toda_respuesta_lleva_la_cabecera_de_correlacion() -> None:
    with TestClient(create_app(_settings())) as client:
        respuesta = client.get("/health")

    assert respuesta.headers["X-Request-ID"]


def test_se_puede_propagar_un_request_id_externo() -> None:
    with TestClient(create_app(_settings())) as client:
        respuesta = client.get("/health", headers={"X-Request-ID": "abc-123"})

    assert respuesta.headers["X-Request-ID"] == "abc-123"


def test_el_request_id_llega_al_contexto_del_endpoint() -> None:
    """El identificador de correlación debe estar disponible dentro del manejador."""
    app = create_app(_settings())

    @app.get("/contexto")
    def contexto() -> dict[str, str | None]:
        from core.logging import get_context

        return get_context()

    with TestClient(app) as client:
        respuesta = client.get("/contexto", headers={"X-Request-ID": "ctx-1"})

    assert respuesta.json()["request_id"] == "ctx-1"


def test_sin_cabecera_externa_se_genera_un_request_id() -> None:
    app = create_app(_settings())

    @app.get("/contexto")
    def contexto() -> dict[str, str | None]:
        from core.logging import get_context

        return get_context()

    with TestClient(app) as client:
        respuesta = client.get("/contexto")

    assert respuesta.json()["request_id"]
    assert respuesta.headers["X-Request-ID"] == respuesta.json()["request_id"]


def test_un_error_de_aplicacion_devuelve_el_envelope_esperado() -> None:
    app = create_app(_settings())

    @app.get("/provoca-error")
    def provoca_error() -> None:
        from core.errors import NotFoundError

        raise NotFoundError("no existe", details={"id": "e-1"})

    with TestClient(app) as client:
        respuesta = client.get("/provoca-error")

    assert respuesta.status_code == 404
    cuerpo = respuesta.json()
    assert cuerpo["error"]["code"] == "not_found"
    assert cuerpo["error"]["message"] == "no existe"
    assert cuerpo["error"]["details"] == {"id": "e-1"}
    assert cuerpo["request_id"]


def test_un_error_inesperado_devuelve_500_con_envelope() -> None:
    app = create_app(_settings())

    @app.get("/provoca-boom")
    def provoca_boom() -> None:
        raise RuntimeError("boom")

    # `raise_server_exceptions=False`: Starlette vuelve a lanzar la excepción
    # original tras generar la respuesta, para que el servidor la registre.
    with TestClient(app, raise_server_exceptions=False) as client:
        respuesta = client.get("/provoca-boom")

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert cuerpo["error"]["code"] == "internal_error"
    assert "boom" not in cuerpo["error"]["message"]
