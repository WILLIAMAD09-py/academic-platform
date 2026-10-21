"""Pruebas de la jerarquía de errores (`core.errors`)."""

from __future__ import annotations

import pytest

from core.errors import (
    AppError,
    ConflictError,
    InvalidStateError,
    NotFoundError,
    ValidationFailedError,
)


def test_un_error_de_aplicacion_conserva_codigo_y_detalles() -> None:
    error = AppError("fallo general", details={"campo": "exam_code"})

    payload = error.to_payload()

    assert payload["code"] == "app_error"
    assert payload["message"] == "fallo general"
    assert payload["details"] == {"campo": "exam_code"}


@pytest.mark.parametrize(
    ("error_class", "status_esperado", "code_esperado"),
    [
        (NotFoundError, 404, "not_found"),
        (ConflictError, 409, "conflict"),
        (ValidationFailedError, 422, "validation_failed"),
        (InvalidStateError, 409, "invalid_state"),
    ],
)
def test_cada_error_tiene_su_codigo_http(
    error_class: type[AppError], status_esperado: int, code_esperado: str
) -> None:
    error = error_class("mensaje")

    assert error.status_code == status_esperado
    assert error.code == code_esperado


def test_los_detalles_son_opcionales() -> None:
    error = NotFoundError("no existe")

    assert error.to_payload()["details"] == {}


def test_los_errores_son_excepciones_de_python() -> None:
    with pytest.raises(AppError) as info:
        raise ConflictError("duplicado", details={"exam_code": "21643"})

    assert isinstance(info.value, AppError)
    assert info.value.status_code == 409
