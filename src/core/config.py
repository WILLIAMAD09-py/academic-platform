"""Configuración del núcleo, leída del entorno.

Una única fuente de verdad para la aplicación. Los valores vienen de variables de
entorno (y opcionalmente de un `.env`), nunca de valores escritos en el código.

La instancia es **inmutable**: el núcleo no puede mutar la configuración en
tiempo de ejecución (regla de `AGENTS.md`: sin estado global mutable).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "test", "production"]

#: Drivers admitidos por el engine **asíncrono**. Un URL síncrono (por ejemplo
#: `postgresql://`) fallaría en tiempo de ejecución con un error poco claro, así
#: que se rechaza al arrancar.
ALLOWED_ASYNC_DRIVERS: tuple[str, ...] = ("sqlite+aiosqlite", "postgresql+psycopg")

#: Niveles de log aceptados.
ALLOWED_LOG_LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

_URL_PATTERN = re.compile(r"^(?P<scheme>[a-zA-Z0-9+]+)://(?P<rest>.+)$")


class Settings(BaseSettings):
    """Configuración completa de la aplicación."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    # --- Entorno ---
    app_env: AppEnv = "development"
    app_debug: bool = False

    # --- Base de datos ---
    database_url: str = "sqlite+aiosqlite:///./app.db"
    database_url_sync: str = "sqlite:///./app.db"
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # --- Logging ---
    log_level: str = "INFO"
    log_json: bool = True

    # --- Reglas de negocio de exámenes ---
    exams_min_questions: int = 25
    exams_max_questions: int = 50
    exams_max_options: int = 4
    exams_max_text_length: int = 2000
    exams_min_options: int = 2
    exams_max_review_attempts: int = 3

    # --- Aleatorización ---
    keys_min_count: int = 2
    keys_max_count: int = 26
    keys_require_distinct_question_order: bool = True
    keys_require_distinct_correct_letter: bool = True
    keys_min_position_shift: int = 0
    keys_max_sampling_attempts: int = 1000

    # --- Documentos ---
    docs_output_dir: Path = Path("./output")
    docs_template_mode: str = "DEFAULT"
    pdf_adapter_enabled: bool = False
    soffice_binary: str = "soffice"
    pdf_convert_timeout_seconds: int = 120

    # --- API ---
    api_title: str = "Plataforma de Automatización Académica"
    api_prefix: str = "/api/v1"
    # Orígenes permitidos por CORS. `*` solo tiene sentido en desarrollo y sin
    # credenciales: con cookies o cabeceras de autorización el navegador
    # rechaza la respuesta.
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # --- Validadores ---

    @field_validator("database_url")
    @classmethod
    def _validar_database_url(cls, value: str) -> str:
        """Rechaza URLs sin esquema o con un driver no asíncrono."""
        coincidencia = _URL_PATTERN.match(value)
        if coincidencia is None:
            raise ValueError(
                "DATABASE_URL debe tener el formato 'motor+driver://servidor/...' "
                f"(valor recibido: {value!r})"
            )
        esquema = coincidencia.group("scheme")
        if esquema not in ALLOWED_ASYNC_DRIVERS:
            permitidos = ", ".join(ALLOWED_ASYNC_DRIVERS)
            raise ValueError(
                f"driver no soportado para el engine asíncrono: {esquema!r}. "
                f"Se admiten: {permitidos}."
            )
        return value

    @field_validator("database_url_sync")
    @classmethod
    def _validar_database_url_sync(cls, value: str) -> str:
        """El URL síncrono (Alembic, scripts) solo necesita un esquema válido."""
        if _URL_PATTERN.match(value) is None:
            raise ValueError(
                "DATABASE_URL_SYNC debe tener el formato 'motor+driver://servidor/...' "
                f"(valor recibido: {value!r})"
            )
        return value

    @field_validator("log_level")
    @classmethod
    def _normalizar_log_level(cls, value: str) -> str:
        nivel = value.strip().upper()
        if nivel not in ALLOWED_LOG_LEVELS:
            permitidos = ", ".join(ALLOWED_LOG_LEVELS)
            raise ValueError(f"nivel de log no soportado: {value!r}. Se admiten: {permitidos}.")
        return nivel

    @model_validator(mode="after")
    def _validar_rangos(self) -> Settings:
        """Los rangos de negocio no pueden estar invertidos."""
        if self.exams_min_questions > self.exams_max_questions:
            raise ValueError(
                "exams_min_questions no puede ser mayor que exams_max_questions "
                f"({self.exams_min_questions} > {self.exams_max_questions})"
            )
        if self.exams_min_options > self.exams_max_options:
            raise ValueError(
                "exams_min_options no puede ser mayor que exams_max_options "
                f"({self.exams_min_options} > {self.exams_max_options})"
            )
        if self.keys_min_count > self.keys_max_count:
            raise ValueError(
                "keys_min_count no puede ser mayor que keys_max_count "
                f"({self.keys_min_count} > {self.keys_max_count})"
            )
        return self

    # --- Ayudantes de lectura ---

    @property
    def is_sqlite(self) -> bool:
        """`True` si la base de datos configurada es SQLite."""
        return self.database_url.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        """`True` si la base de datos configurada es PostgreSQL."""
        return self.database_url.startswith("postgresql")

    @property
    def dialect(self) -> str:
        """Nombre corto del motor: `sqlite` o `postgresql`."""
        return "sqlite" if self.is_sqlite else "postgresql"
