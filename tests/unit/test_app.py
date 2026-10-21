"""Pruebas de la fábrica de la aplicación y de la ruta de salud."""

from __future__ import annotations

from fastapi.testclient import TestClient

from core import __version__
from core.app import create_app


def test_health_responde_ok() -> None:
    """La ruta de salud devuelve 200 y el estado esperado."""
    with TestClient(create_app()) as client:
        respuesta = client.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok", "version": __version__}


def test_health_esta_en_openapi() -> None:
    """La ruta de salud queda documentada en el esquema de OpenAPI."""
    with TestClient(create_app()) as client:
        esquema = client.get("/openapi.json").json()

    assert "/health" in esquema["paths"]


def test_app_expone_metadatos() -> None:
    """La aplicación declara título y versión."""
    app = create_app()

    assert app.version == __version__
    assert app.title == "Plataforma de Automatización Académica"
