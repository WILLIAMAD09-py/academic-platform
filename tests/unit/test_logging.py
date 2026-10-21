"""Pruebas del logging estructurado (`core.logging`)."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from core.config import Settings
from core.logging import (
    JsonFormatter,
    clear_context,
    configure_logging,
    context_scope,
    get_context,
    set_context,
)


def _emit(settings: Settings, message: str = "mensaje de prueba", **extra: Any) -> dict[str, Any]:
    """Configura el logging, emite una línea y devuelve el JSON resultante."""
    configure_logging(settings)
    logger = logging.getLogger("core.prueba")
    records: list[logging.LogRecord] = []

    class _Captura(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    captura = _Captura()
    captura.setFormatter(JsonFormatter())
    logger.handlers = [captura]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)

    logger.info(message, extra=extra)
    assert len(records) == 1
    return json.loads(captura.format(records[0]))


def test_la_linea_json_lleva_los_campos_obligatorios() -> None:
    """El requisito no funcional pide exam_id, exam_code y request_id en cada línea."""
    payload = _emit(Settings(_env_file=None))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "core.prueba"
    assert payload["message"] == "mensaje de prueba"
    for campo in ("exam_id", "exam_code", "request_id"):
        assert campo in payload
        assert payload[campo] is None


def test_el_contexto_de_examen_aparece_en_la_linea() -> None:
    with context_scope(exam_id="e-1", exam_code="21643", request_id="r-9"):
        payload = _emit(Settings(_env_file=None))

    assert payload["exam_id"] == "e-1"
    assert payload["exam_code"] == "21643"
    assert payload["request_id"] == "r-9"


def test_los_campos_extra_se_incorporan_al_json() -> None:
    payload = _emit(Settings(_env_file=None), exam_code="21643", duration_ms=12)

    assert payload["exam_code"] == "21643"
    assert payload["duration_ms"] == 12


def test_el_contexto_se_limpia_al_salir_del_bloque() -> None:
    with context_scope(exam_id="e-1", request_id="r-9"):
        pass

    contexto = get_context()

    assert contexto["exam_id"] is None
    assert contexto["request_id"] is None


def test_se_puede_fijar_y_limpiar_el_contexto_a_mano() -> None:
    set_context(request_id="r-1", exam_code="21643")
    try:
        assert get_context()["request_id"] == "r-1"
        assert get_context()["exam_code"] == "21643"
    finally:
        clear_context()

    assert get_context() == {"exam_id": None, "exam_code": None, "request_id": None}


def test_un_campo_de_contexto_desconocido_falla() -> None:
    with pytest.raises(KeyError):
        set_context(campo_inexistente="x")  # type: ignore[call-arg]


def test_un_campo_de_contexto_desconocido_falla_en_el_scope() -> None:
    with pytest.raises(KeyError), context_scope(campo_inexistente="x"):  # type: ignore[call-arg]
        pass


def test_el_contexto_anidado_restaura_el_valor_externo() -> None:
    with context_scope(request_id="r-externo"):
        with context_scope(request_id="r-interno"):
            assert get_context()["request_id"] == "r-interno"
        assert get_context()["request_id"] == "r-externo"


def test_configure_logging_es_idempotente() -> None:
    settings = Settings(_env_file=None)

    configure_logging(settings)
    configure_logging(settings)

    raiz = logging.getLogger()
    assert len(raiz.handlers) == 1


def test_configure_logging_respeta_el_nivel() -> None:
    settings = Settings(_env_file=None, log_level="WARNING")

    configure_logging(settings)

    assert logging.getLogger().level == logging.WARNING


def test_el_formato_legible_incluye_el_contexto() -> None:
    settings = Settings(_env_file=None, log_json=False)

    configure_logging(settings)
    raiz = logging.getLogger()
    formato = raiz.handlers[0].formatter
    assert formato is not None

    registro = logging.LogRecord(
        name="core.prueba",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="mensaje legible",
        args=(),
        exc_info=None,
    )
    linea = formato.format(registro)

    assert "mensaje legible" in linea
    assert "INFO" in linea
