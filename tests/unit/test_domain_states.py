"""Pruebas de la máquina de estados del examen (`domain.states`)."""

from __future__ import annotations

import pytest

from modules.exams.domain.states import (
    ALLOWED_TRANSITIONS,
    ExamStatus,
    InvalidTransitionError,
    allowed_transitions,
    assert_transition,
    can_transition,
    is_final,
    is_waiting_teacher,
)


def test_todos_los_estados_declaran_al_menos_una_salida() -> None:
    for estado in ExamStatus:
        assert estado in ALLOWED_TRANSITIONS
        assert allowed_transitions(estado), f"{estado} no declara transiciones de salida"


@pytest.mark.parametrize(
    ("origen", "destino"),
    [
        (ExamStatus.DRAFT, ExamStatus.SUBMITTED),
        (ExamStatus.SUBMITTED, ExamStatus.VALIDATED),
        (ExamStatus.SUBMITTED, ExamStatus.FAILED),
        (ExamStatus.VALIDATED, ExamStatus.FORMAT_CHECKED),
        (ExamStatus.VALIDATED, ExamStatus.FAILED),
        (ExamStatus.FORMAT_CHECKED, ExamStatus.FORMAT_FIXED),
        (ExamStatus.FORMAT_CHECKED, ExamStatus.FAILED),
        (ExamStatus.FORMAT_FIXED, ExamStatus.QUESTIONS_REVIEWED),
        (ExamStatus.FORMAT_FIXED, ExamStatus.NEEDS_TEACHER_DECISION),
        (ExamStatus.FORMAT_FIXED, ExamStatus.FAILED),
        (ExamStatus.QUESTIONS_REVIEWED, ExamStatus.KEYS_GENERATED),
        (ExamStatus.NEEDS_TEACHER_DECISION, ExamStatus.QUESTIONS_REVIEWED),
        (ExamStatus.KEYS_GENERATED, ExamStatus.DOCUMENTS_GENERATED),
        (ExamStatus.DOCUMENTS_GENERATED, ExamStatus.COMPLETED),
        (ExamStatus.DOCUMENTS_GENERATED, ExamStatus.COMPLETED_WITH_WARNINGS),
        (ExamStatus.COMPLETED, ExamStatus.PRINT_PENDING),
        (ExamStatus.COMPLETED_WITH_WARNINGS, ExamStatus.PRINT_PENDING),
        (ExamStatus.PRINT_PENDING, ExamStatus.ANSWER_SHEETS_PENDING),
        (ExamStatus.ANSWER_SHEETS_PENDING, ExamStatus.COMPLETED),
        (ExamStatus.FAILED, ExamStatus.DRAFT),
        (ExamStatus.FAILED, ExamStatus.SUBMITTED),
        (ExamStatus.COMPLETED, ExamStatus.DRAFT),
        (ExamStatus.KEYS_GENERATED, ExamStatus.DRAFT),
        (ExamStatus.DOCUMENTS_GENERATED, ExamStatus.DRAFT),
    ],
)
def test_transiciones_permitidas(origen: ExamStatus, destino: ExamStatus) -> None:
    assert can_transition(origen, destino)
    assert_transition(origen, destino)


@pytest.mark.parametrize(
    ("origen", "destino"),
    [
        (ExamStatus.DRAFT, ExamStatus.VALIDATED),
        (ExamStatus.DRAFT, ExamStatus.COMPLETED),
        (ExamStatus.SUBMITTED, ExamStatus.KEYS_GENERATED),
        (ExamStatus.VALIDATED, ExamStatus.SUBMITTED),
        (ExamStatus.FORMAT_FIXED, ExamStatus.COMPLETED),
        (ExamStatus.NEEDS_TEACHER_DECISION, ExamStatus.KEYS_GENERATED),
        (ExamStatus.QUESTIONS_REVIEWED, ExamStatus.DOCUMENTS_GENERATED),
        (ExamStatus.COMPLETED, ExamStatus.ANSWER_SHEETS_PENDING),
        (ExamStatus.ANSWER_SHEETS_PENDING, ExamStatus.SUBMITTED),
    ],
)
def test_transiciones_prohibidas(origen: ExamStatus, destino: ExamStatus) -> None:
    assert not can_transition(origen, destino)

    with pytest.raises(InvalidTransitionError) as info:
        assert_transition(origen, destino)

    assert info.value.current is origen
    assert info.value.target is destino


def test_la_transicion_invalida_es_un_error_409_con_detalle() -> None:
    with pytest.raises(InvalidTransitionError) as info:
        assert_transition(ExamStatus.DRAFT, ExamStatus.COMPLETED)

    error = info.value
    assert error.status_code == 409
    assert error.code == "invalid_transition"
    assert error.details == {"current": "DRAFT", "target": "COMPLETED"}
    assert "DRAFT" in error.message


def test_los_estados_finales_son_completado_y_completado_con_avisos() -> None:
    assert is_final(ExamStatus.COMPLETED)
    assert is_final(ExamStatus.COMPLETED_WITH_WARNINGS)
    assert not is_final(ExamStatus.DRAFT)
    assert not is_final(ExamStatus.FAILED)


def test_solo_un_estado_espera_decision_del_docente() -> None:
    assert is_waiting_teacher(ExamStatus.NEEDS_TEACHER_DECISION)
    assert not is_waiting_teacher(ExamStatus.QUESTIONS_REVIEWED)
    assert not is_waiting_teacher(ExamStatus.DRAFT)


def test_el_ciclo_completo_puede_reprocesarse_tras_editar() -> None:
    """Un examen completado vuelve a DRAFT para poder reenviarse."""
    assert can_transition(ExamStatus.COMPLETED, ExamStatus.DRAFT)
    assert can_transition(ExamStatus.DRAFT, ExamStatus.SUBMITTED)
    assert can_transition(ExamStatus.SUBMITTED, ExamStatus.VALIDATED)
