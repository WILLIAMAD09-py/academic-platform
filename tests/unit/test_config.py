"""Pruebas de la configuración del núcleo (`core.config`)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.config import Settings


def test_valores_por_defecto_son_usable_sin_infraestructura() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.app_debug is False
    assert settings.database_url == "sqlite+aiosqlite:///./app.db"
    assert settings.is_sqlite is True
    assert settings.is_postgres is False
    assert settings.dialect == "sqlite"
    assert settings.api_prefix == "/api/v1"


def test_lectura_desde_el_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_DEBUG", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://app:app@db:5432/app")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("LOG_JSON", "false")
    monkeypatch.setenv("EXAMS_MAX_QUESTIONS", "40")

    settings = Settings(_env_file=None)

    assert settings.app_env == "production"
    assert settings.app_debug is True
    assert settings.is_postgres is True
    assert settings.dialect == "postgresql"
    assert settings.log_level == "DEBUG"
    assert settings.log_json is False
    assert settings.exams_max_questions == 40


def test_lista_de_cors_se_parsea_como_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:5173", "http://localhost:4173"]')

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://localhost:5173", "http://localhost:4173"]


def test_la_configuracion_es_inmutable() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(ValidationError):
        settings.app_env = "production"  # type: ignore[misc]


def test_url_de_base_de_datos_invalida_falla_temprano() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="no-es-una-url")


def test_url_con_driver_sincrono_falla_temprano() -> None:
    """Una URL síncrona no vale para el engine asíncrono: debe avisar al arrancar."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="postgresql://app:app@db:5432/app")


def test_nivel_de_log_invalido_falla() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, log_level="MUY_ALTO")


def test_entorno_desconocido_falla() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="produccion")


def test_los_limites_de_examen_no_pueden_invertirse() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, exams_min_questions=50, exams_max_questions=25)


def test_los_limites_de_opciones_no_pueden_invertirse() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, exams_min_options=5, exams_max_options=4)


def test_los_limites_de_claves_no_pueden_invertirse() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, keys_min_count=30, keys_max_count=26)


def test_el_url_sincrono_invalido_falla_temprano() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url_sync="no-es-una-url")


def test_el_directorio_de_salida_se_normaliza_a_path() -> None:
    settings = Settings(_env_file=None, docs_output_dir="./output")

    assert settings.docs_output_dir.is_absolute() is False
    assert settings.docs_output_dir.name == "output"
