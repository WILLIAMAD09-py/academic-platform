"""Vocabulario y grafo de transiciones del ciclo de vida de un examen.

Este módulo es **puro** (solo biblioteca estándar y `core.errors`): define los
estados posibles y las transiciones permitidas entre ellos.

La aplicación de una transición sobre un examen concreto vive en
`domain.models` (método `Exam.transition_to`), para no crear una dependencia
cíclica entre el modelo y el grafo de estados.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from core.errors import InvalidStateError


class ExamStatus(StrEnum):
    """Estados del examen a lo largo del pipeline de generación.

    El ciclo normal es:

    ``DRAFT → SUBMITTED → VALIDATED → FORMAT_CHECKED → FORMAT_FIXED →
    QUESTIONS_REVIEWED → KEYS_GENERATED → DOCUMENTS_GENERATED → COMPLETED``

    con dos desvíos: ``NEEDS_TEACHER_DECISION`` (cuando el revisor automático
    no puede decidir) y ``FAILED`` (cuando la revisión encuentra problemas que
    impiden continuar).
    """

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    VALIDATED = "VALIDATED"
    FORMAT_CHECKED = "FORMAT_CHECKED"
    FORMAT_FIXED = "FORMAT_FIXED"
    QUESTIONS_REVIEWED = "QUESTIONS_REVIEWED"
    NEEDS_TEACHER_DECISION = "NEEDS_TEACHER_DECISION"
    KEYS_GENERATED = "KEYS_GENERATED"
    DOCUMENTS_GENERATED = "DOCUMENTS_GENERATED"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    PRINT_PENDING = "PRINT_PENDING"
    ANSWER_SHEETS_PENDING = "ANSWER_SHEETS_PENDING"
    FAILED = "FAILED"


class InvalidTransitionError(InvalidStateError):
    """Se intentó una transición no permitida por la máquina de estados.

    Hereda de `core.errors.InvalidStateError`, por lo que la capa HTTP la
    traduce automáticamente a **409 Conflict** con el código `invalid_transition`.
    """

    code = "invalid_transition"
    status_code = 409

    def __init__(self, current: ExamStatus, target: ExamStatus) -> None:
        super().__init__(
            f"No se permite pasar de {current.value} a {target.value}",
            details={"current": current.value, "target": target.value},
        )
        self.current = current
        self.target = target


#: Transiciones permitidas por el grafo de estados.
ALLOWED_TRANSITIONS: Mapping[ExamStatus, frozenset[ExamStatus]] = MappingProxyType(
    {
        ExamStatus.DRAFT: frozenset({ExamStatus.SUBMITTED}),
        ExamStatus.SUBMITTED: frozenset({ExamStatus.VALIDATED, ExamStatus.FAILED}),
        ExamStatus.VALIDATED: frozenset({ExamStatus.FORMAT_CHECKED, ExamStatus.FAILED}),
        ExamStatus.FORMAT_CHECKED: frozenset({ExamStatus.FORMAT_FIXED, ExamStatus.FAILED}),
        ExamStatus.FORMAT_FIXED: frozenset(
            {
                ExamStatus.QUESTIONS_REVIEWED,
                ExamStatus.NEEDS_TEACHER_DECISION,
                ExamStatus.FAILED,
            }
        ),
        ExamStatus.QUESTIONS_REVIEWED: frozenset({ExamStatus.KEYS_GENERATED, ExamStatus.FAILED}),
        ExamStatus.NEEDS_TEACHER_DECISION: frozenset(
            {ExamStatus.QUESTIONS_REVIEWED, ExamStatus.FAILED}
        ),
        ExamStatus.KEYS_GENERATED: frozenset(
            {ExamStatus.DOCUMENTS_GENERATED, ExamStatus.FAILED, ExamStatus.DRAFT}
        ),
        ExamStatus.DOCUMENTS_GENERATED: frozenset(
            {
                ExamStatus.COMPLETED,
                ExamStatus.COMPLETED_WITH_WARNINGS,
                ExamStatus.FAILED,
                ExamStatus.DRAFT,
            }
        ),
        ExamStatus.COMPLETED: frozenset({ExamStatus.PRINT_PENDING, ExamStatus.DRAFT}),
        ExamStatus.COMPLETED_WITH_WARNINGS: frozenset({ExamStatus.PRINT_PENDING, ExamStatus.DRAFT}),
        ExamStatus.PRINT_PENDING: frozenset({ExamStatus.ANSWER_SHEETS_PENDING, ExamStatus.DRAFT}),
        ExamStatus.ANSWER_SHEETS_PENDING: frozenset({ExamStatus.COMPLETED, ExamStatus.DRAFT}),
        ExamStatus.FAILED: frozenset({ExamStatus.DRAFT, ExamStatus.SUBMITTED}),
    }
)

#: Estados en los que el examen ya está entregado y no admite más trabajo.
ESTADOS_FINALES = frozenset({ExamStatus.COMPLETED, ExamStatus.COMPLETED_WITH_WARNINGS})


def allowed_transitions(status: ExamStatus) -> frozenset[ExamStatus]:
    """Estados alcanzables desde `status`."""
    return ALLOWED_TRANSITIONS.get(status, frozenset())


def can_transition(current: ExamStatus, target: ExamStatus) -> bool:
    """Indica si la transición `current → target` está permitida."""
    return target in allowed_transitions(current)


def assert_transition(current: ExamStatus, target: ExamStatus) -> None:
    """Valida la transición; lanza `InvalidTransitionError` si no está permitida."""
    if not can_transition(current, target):
        raise InvalidTransitionError(current, target)


def is_final(status: ExamStatus) -> bool:
    """`True` si el examen ya está completado."""
    return status in ESTADOS_FINALES


def is_waiting_teacher(status: ExamStatus) -> bool:
    """`True` si el examen está a la espera de una decisión del docente."""
    return status is ExamStatus.NEEDS_TEACHER_DECISION
