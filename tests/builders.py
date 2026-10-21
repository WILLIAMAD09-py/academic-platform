"""Constructores de objetos de dominio para las pruebas.

Ayudan a mantener las pruebas legibles: en lugar de construir a mano un
examen con 25 preguntas, cada prueba declara solo lo que le importa
(por ejemplo, una pregunta con el inciso de la opción "e").
"""

from __future__ import annotations

from typing import Any

from modules.exams.domain.models import (
    Block,
    BlockKind,
    Exam,
    ExamStatus,
    Option,
    Question,
    QuestionType,
    Section,
)

_ROMANOS = (
    "I",
    "II",
    "III",
    "IV",
    "V",
    "VI",
    "VII",
    "VIII",
    "IX",
    "X",
    "XI",
    "XII",
    "XIII",
    "XIV",
    "XV",
    "XVI",
    "XVII",
    "XVIII",
    "XIX",
    "XX",
)

#: Letras de inciso admitidas por el dominio (A-E).
LETRAS = ("a", "b", "c", "d", "e")


def make_option(
    question_id: str,
    index: int,
    *,
    is_correct: bool = False,
    text: str | None = None,
    label: str | None = None,
    locked: bool = False,
) -> Option:
    """Construye un inciso con letra, texto y marca de respuesta correcta."""
    letra = label if label is not None else LETRAS[index]
    contenido = text if text is not None else f"Texto del inciso {letra}"
    return Option(
        id=f"{question_id}-o{index + 1}",
        label=letra,
        text_original=contenido,
        text_current=contenido,
        is_correct=is_correct,
        position_original=index + 1,
        locked=locked,
    )


def make_question(
    index: int,
    *,
    section_id: str = "sec1",
    option_count: int = 4,
    correct_label: str = "a",
    stem: str | None = None,
    question_type: QuestionType = QuestionType.MULTIPLE_CHOICE,
    shuffle_question: bool = True,
    shuffle_options: bool = True,
) -> Question:
    """Construye una pregunta con sus incisos y una única respuesta correcta."""
    question_id = f"q{index:03d}"
    enunciado = stem if stem is not None else f"Enunciado de la pregunta {index}"
    opciones = tuple(
        make_option(question_id, posicion, is_correct=(LETRAS[posicion] == correct_label))
        for posicion in range(option_count)
    )
    return Question(
        id=question_id,
        section_id=section_id,
        position_original=index,
        stem_original=enunciado,
        stem_current=enunciado,
        options=opciones,
        question_type=question_type,
        shuffle_question=shuffle_question,
        shuffle_options=shuffle_options,
    )


def make_section(index: int, *, exam_id: str = "exam-1", title: str | None = None) -> Section:
    """Construye una sección numerada (la posición define el orden)."""
    return Section(
        id=f"sec{index}",
        exam_id=exam_id,
        position=index,
        roman_numeral=_ROMANOS[index - 1] if index <= len(_ROMANOS) else str(index),
        title=title if title is not None else f"Sección {index}",
        instructions="Responda todas las preguntas.",
    )


def make_block(
    block_id: str,
    kind: BlockKind,
    member_ids: tuple[str, ...],
    *,
    exam_id: str = "exam-1",
) -> Block:
    """Construye un bloque de preguntas o de secciones."""
    return Block(
        id=block_id,
        exam_id=exam_id,
        kind=kind,
        name=f"Bloque {block_id}",
        member_ids=member_ids,
        created_by="teacher-1",
    )


def make_exam(*, question_count: int = 25, section_count: int = 1, **overrides: Any) -> Exam:
    """Construye un examen válido por defecto, con los ajustes indicados."""
    secciones = tuple(make_section(indice + 1) for indice in range(section_count))
    preguntas = tuple(
        make_question(indice + 1, section_id=secciones[indice % section_count].id)
        for indice in range(question_count)
    )
    base: dict[str, Any] = {
        "id": "exam-1",
        "exam_code": "21643",
        "title": "Examen de prueba",
        "course_code": "MAT-101",
        "period": "2026-1",
        "learning_unit": "Unidad 1: Álgebra",
        "teacher_id": "teacher-1",
        "status": ExamStatus.DRAFT,
        "sections": secciones,
        "questions": preguntas,
    }
    base.update(overrides)
    return Exam(**base)
