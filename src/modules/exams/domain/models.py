"""Modelo de dominio del módulo de exámenes.

Objetos **inmutables** (dataclasses `frozen`) que representan el examen y sus
partes: secciones, preguntas, incisos, bloques y grupos de enunciado.

El módulo es **puro**: no depende de FastAPI, SQLAlchemy ni de la capa de
persistencia. Traducir filas de base de datos a estos objetos (y al revés) es
responsabilidad de `modules.exams.infrastructure`.

El modelo distingue siempre la **versión original** del docente
(`*_original`) de la **versión actual** (`*_current`): el pipeline de IA puede
reescribir enunciados e incisos, pero el original se conserva para poder
auditar los cambios y regenerar documentos.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import uuid4

from modules.exams.domain.states import ExamStatus, assert_transition

#: Letras de inciso admitidas por el dominio (A-E).
LETRAS_INCISO: tuple[str, ...] = ("a", "b", "c", "d", "e")


class QuestionType(StrEnum):
    """Tipo de pregunta capturado por el docente.

    Solo la opción múltiple se genera como tal; verdadero/falso y completar
    espacios se capturan también como opción múltiple. La pregunta abierta
    no es generable y se reporta como error.
    """

    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    FILL_BLANKS = "fill_blanks"
    OPEN = "open"


class ReviewStatus(StrEnum):
    """Resultado de la revisión automática de una pregunta."""

    PENDING = "pending"
    PASSED = "passed"
    REJECTED = "rejected"


class ReviewLabel(StrEnum):
    """Etiqueta de la revisión de una pregunta (BIEN / MAL)."""

    BIEN = "bien"
    MAL = "mal"


class ReviewReason(StrEnum):
    """Motivo por el que una pregunta se marca como `MAL`."""

    AMBIGUOUS = "ambigua"
    INCOMPLETE = "incompleta"
    INCORRECT = "incorrecta"
    DUPLICATED = "duplicada"
    OUT_OF_RANGE = "fuera_de_rango"
    REFERENCES_OTHER_OPTIONS = "referencia_otros_incisos"


class DecisionType(StrEnum):
    """Decisión humana sobre una pregunta dudosa."""

    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"


class BlockKind(StrEnum):
    """Naturaleza de un bloque de examen."""

    QUESTION_GROUP = "question_group"
    SECTION_GROUP = "section_group"


class StimulusKind(StrEnum):
    """Naturaleza del contenido compartido por un grupo de preguntas."""

    CODE = "code"
    TABLE = "table"
    IMAGE = "image"
    TEXT = "text"


class TemplateMode(StrEnum):
    """Origen de la plantilla usada para generar los documentos."""

    DEFAULT = "DEFAULT"
    CUSTOM = "CUSTOM"


class DocumentKind(StrEnum):
    """Tipo de documento generado a partir de un examen."""

    EXAM = "exam"
    EXAM_KEY = "exam_key"
    ANSWER_SHEET = "answer_sheet"


@dataclass(frozen=True, slots=True)
class Option:
    """Inciso de una pregunta."""

    id: str
    label: str
    text_original: str
    text_current: str
    is_correct: bool
    position_original: int
    locked: bool = False

    @property
    def text(self) -> str:
        """Texto vigente del inciso."""
        return self.text_current


@dataclass(frozen=True, slots=True)
class ReviewAttempt:
    """Intento de revisión automática sobre una pregunta."""

    attempt: int
    reasons: tuple[ReviewReason, ...] = ()
    stem_before: str = ""
    stem_after: str = ""
    correct_label_before: str | None = None
    correct_label_after: str | None = None
    applied: bool = True
    note: str | None = None


@dataclass(frozen=True, slots=True)
class Question:
    """Pregunta de examen con sus incisos y su historial de revisión."""

    id: str
    section_id: str
    position_original: int = 0
    stem_original: str = ""
    stem_current: str = ""
    stem_rewritten: bool = False
    question_type: QuestionType = QuestionType.MULTIPLE_CHOICE
    shuffle_question: bool = True
    shuffle_options: bool = True
    weight: Decimal = Decimal("0.00")
    review_status: ReviewStatus = ReviewStatus.PENDING
    options: tuple[Option, ...] = ()
    review_history: tuple[ReviewAttempt, ...] = ()

    @property
    def stem(self) -> str:
        """Enunciado vigente."""
        return self.stem_current

    @property
    def correct_option(self) -> Option | None:
        """Inciso marcado como correcto, si lo hay."""
        for opcion in self.options:
            if opcion.is_correct:
                return opcion
        return None

    @property
    def correct_label(self) -> str | None:
        """Letra del inciso correcto, si lo hay."""
        opcion = self.correct_option
        return opcion.label if opcion is not None else None


@dataclass(frozen=True, slots=True)
class Section:
    """Sección del examen.

    `position` define el orden: **nunca cambia**, ni siquiera al reordenar
    preguntas o al regenerar documentos.
    """

    id: str
    exam_id: str
    position: int
    roman_numeral: str = ""
    title: str = ""
    instructions: str = ""


@dataclass(frozen=True, slots=True)
class StimulusGroup:
    """Grupo de enunciado compartido (código, tabla, imagen o texto)."""

    id: str
    exam_id: str
    section_id: str
    kind: StimulusKind
    content: str = ""
    attachment_ref: str | None = None


@dataclass(frozen=True, slots=True)
class Block:
    """Bloque de preguntas o de secciones.

    Un bloque agrupa elementos que se barajan y reordenan juntos. Un elemento
    no puede pertenecer a dos bloques del mismo tipo.
    """

    id: str
    exam_id: str
    kind: BlockKind
    name: str = ""
    member_ids: tuple[str, ...] = ()
    created_by: str = ""
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    """Decisión humana sobre una pregunta que requería intervención."""

    id: str
    question_id: str
    decision: DecisionType
    before_snapshot: Mapping[str, Any] = field(default_factory=dict)
    after_snapshot: Mapping[str, Any] = field(default_factory=dict)
    decided_by: str = ""
    decided_at: datetime | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ExamKey:
    """Clave de respuestas generada para un examen."""

    id: str
    exam_id: str
    key_letter: str
    seed_used: int = 0
    exam_version: int = 1
    generated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class KeyQuestionMapping:
    """Correspondencia entre una pregunta del examen y su posición en la clave."""

    id: str
    exam_key_id: str
    question_id: str
    position_in_key: int
    option_order: Mapping[str, str] = field(default_factory=dict)
    correct_label_in_key: str = ""


@dataclass(frozen=True, slots=True)
class GeneratedDocument:
    """Documento generado (examen, clave o hoja de respuestas)."""

    id: str
    exam_id: str
    kind: DocumentKind
    file_path: str
    sha256: str = ""
    exam_key_id: str | None = None
    exam_version: int = 1
    created_at: datetime | None = None
    superseded_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ExamAuditEvent:
    """Evento de auditoría del ciclo de vida de un examen.

    Se llama `ExamAuditEvent` y no `AuditEvent` para no chocar con el
    `AuditEvent` genérico del núcleo (`core.audit`).
    """

    id: str
    exam_id: str
    to_status: ExamStatus
    from_status: ExamStatus | None = None
    actor: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class Transition:
    """Resultado de aplicar una transición: el examen nuevo y su evento."""

    exam: Exam
    event: ExamAuditEvent


@dataclass(frozen=True, slots=True)
class Exam:
    """Agregado raíz del módulo de exámenes.

    Contiene la cabecera del examen y sus colecciones (secciones, preguntas,
    bloques y grupos de enunciado). Es inmutable: cualquier cambio produce una
    copia nueva, lo que evita estados compartidos entre capas.
    """

    id: str
    exam_code: str
    title: str
    course_code: str
    period: str
    learning_unit: str
    teacher_id: str
    academy: str | None = None
    exam_date: date | None = None
    status: ExamStatus = ExamStatus.DRAFT
    template_mode: TemplateMode = TemplateMode.DEFAULT
    template_ref: str | None = None
    footer_signers: Mapping[str, str] = field(default_factory=dict)
    n_keys: int = 2
    seed: int = 0
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None
    sections: tuple[Section, ...] = ()
    questions: tuple[Question, ...] = ()
    blocks: tuple[Block, ...] = ()
    stimulus_groups: tuple[StimulusGroup, ...] = ()

    # --- Lectura de relaciones ---

    def question(self, question_id: str) -> Question | None:
        """Pregunta por identificador, si existe."""
        for pregunta in self.questions:
            if pregunta.id == question_id:
                return pregunta
        return None

    def section(self, section_id: str) -> Section | None:
        """Sección por identificador, si existe."""
        for seccion in self.sections:
            if seccion.id == section_id:
                return seccion
        return None

    def questions_of_section(self, section_id: str) -> tuple[Question, ...]:
        """Preguntas que pertenecen a una sección."""
        return tuple(pregunta for pregunta in self.questions if pregunta.section_id == section_id)

    def block_of_question(self, question_id: str) -> Block | None:
        """Bloque de preguntas que contiene la pregunta, si lo hay."""
        for bloque in self.blocks:
            if bloque.kind is not BlockKind.QUESTION_GROUP:
                continue
            if question_id in bloque.member_ids:
                return bloque
        return None

    def block_of_section(self, section_id: str) -> Block | None:
        """Bloque de secciones que contiene la sección, si lo hay."""
        for bloque in self.blocks:
            if bloque.kind is not BlockKind.SECTION_GROUP:
                continue
            if section_id in bloque.member_ids:
                return bloque
        return None

    # --- Transiciones ---

    def transition_to(
        self,
        target: ExamStatus,
        *,
        actor: str,
        payload: Mapping[str, Any] | None = None,
        now: datetime | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> Transition:
        """Aplica una transición de estado y devuelve el nuevo examen.

        La transición debe estar permitida por el grafo de estados; en caso
        contrario lanza `InvalidTransitionError` (409 en la capa HTTP). El
        examen original no se modifica: se devuelve una copia con el nuevo
        estado y el evento de auditoría correspondiente.
        """
        assert_transition(self.status, target)

        momento = now if now is not None else datetime.now(UTC)
        generador = id_factory if id_factory is not None else (lambda: uuid4().hex)

        evento = ExamAuditEvent(
            id=generador(),
            exam_id=self.id,
            from_status=self.status,
            to_status=target,
            actor=actor,
            payload=dict(payload or {}),
            created_at=momento,
        )
        examen = replace(self, status=target, updated_at=momento)

        return Transition(exam=examen, event=evento)
