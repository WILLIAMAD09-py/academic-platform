"""Pruebas del modelo de dominio del examen (`domain.models`)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from modules.exams.domain.models import (
    BlockKind,
    Exam,
    ExamStatus,
    QuestionType,
    ReviewLabel,
)
from modules.exams.domain.states import InvalidTransitionError
from tests.builders import make_block, make_exam, make_option, make_question, make_section

MOMENTO = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def test_el_examen_expone_sus_relaciones() -> None:
    exam = make_exam(question_count=3, section_count=1)

    assert exam.question("q002") is not None
    assert exam.question("q999") is None
    assert exam.section("sec1") is not None
    assert [pregunta.id for pregunta in exam.questions_of_section("sec1")] == [
        "q001",
        "q002",
        "q003",
    ]
    assert exam.questions_of_section("sec-inexistente") == ()


def test_el_examen_localiza_el_bloque_de_una_pregunta_y_de_una_seccion() -> None:
    bloque_preguntas = make_block("blk-1", BlockKind.QUESTION_GROUP, ("q001", "q002"))
    bloque_secciones = make_block("blk-2", BlockKind.SECTION_GROUP, ("sec1",))
    exam = make_exam(question_count=2, blocks=(bloque_preguntas, bloque_secciones))

    assert exam.block_of_question("q001") is bloque_preguntas
    assert exam.block_of_question("q999") is None
    assert exam.block_of_section("sec1") is bloque_secciones
    assert exam.block_of_section("sec-inexistente") is None


def test_la_pregunta_expone_su_inciso_correcto() -> None:
    pregunta = make_question(1, correct_label="b")

    correcto = pregunta.correct_option

    assert correcto is not None
    assert correcto.label == "b"


def test_los_modelos_del_dominio_son_inmutables() -> None:
    exam = make_exam()

    with pytest.raises(FrozenInstanceError):
        exam.status = ExamStatus.SUBMITTED  # type: ignore[misc]


def test_una_transicion_valida_devuelve_un_examen_nuevo_y_su_evento() -> None:
    exam = make_exam()

    transicion = exam.transition_to(
        ExamStatus.SUBMITTED,
        actor="teacher-1",
        payload={"motivo": "entrega"},
        now=MOMENTO,
        id_factory=lambda: "evento-1",
    )

    assert transicion.exam.status is ExamStatus.SUBMITTED
    assert transicion.exam.id == exam.id
    assert transicion.exam.updated_at == MOMENTO
    assert transicion.exam.questions == exam.questions

    evento = transicion.event
    assert evento.id == "evento-1"
    assert evento.exam_id == exam.id
    assert evento.from_status is ExamStatus.DRAFT
    assert evento.to_status is ExamStatus.SUBMITTED
    assert evento.actor == "teacher-1"
    assert evento.payload == {"motivo": "entrega"}
    assert evento.created_at == MOMENTO


def test_una_transicion_no_altera_el_examen_original() -> None:
    exam = make_exam()

    exam.transition_to(ExamStatus.SUBMITTED, actor="teacher-1", now=MOMENTO)

    assert exam.status is ExamStatus.DRAFT
    assert exam.updated_at is None


def test_una_transicion_invalida_no_modifica_nada() -> None:
    exam = make_exam()

    with pytest.raises(InvalidTransitionError):
        exam.transition_to(ExamStatus.COMPLETED, actor="teacher-1", now=MOMENTO)

    assert exam.status is ExamStatus.DRAFT


def test_el_tipo_de_pregunta_abierta_se_representa_en_el_dominio() -> None:
    pregunta = make_question(1, question_type=QuestionType.OPEN)

    assert pregunta.question_type is QuestionType.OPEN


def test_los_datos_del_examen_se_pueden_derivar_con_replace() -> None:
    exam = make_exam()

    modificado = replace(exam, exam_code="99999")

    assert modificado.exam_code == "99999"
    assert exam.exam_code == "21643"


def test_los_incisos_conservan_orden_y_letra() -> None:
    incisos = (make_option("q001", 0), make_option("q001", 1))

    assert [inciso.label for inciso in incisos] == ["a", "b"]
    assert incisos[0].position_original == 1


def test_el_texto_vigente_es_el_texto_original_hasta_que_se_reescriba() -> None:
    inciso = make_option("q001", 0, text="Texto original")

    assert inciso.text == "Texto original"


def test_el_enunciado_vigente_es_el_original_hasta_que_se_reescriba() -> None:
    pregunta = make_question(1, stem="Enunciado original")

    assert pregunta.stem == "Enunciado original"
    assert pregunta.stem_rewritten is False


def test_una_pregunta_sin_respuesta_correcta_no_tiene_inciso_correcto() -> None:
    pregunta = replace(
        make_question(1),
        options=(make_option("q001", 0, is_correct=False), make_option("q001", 1)),
    )

    assert pregunta.correct_option is None
    assert pregunta.correct_label is None


def test_la_letra_del_inciso_correcto_es_la_etiqueta_correspondiente() -> None:
    assert make_question(1, correct_label="c").correct_label == "c"


def test_una_seccion_inexistente_no_se_encuentra() -> None:
    assert make_exam().section("sec-inexistente") is None


def test_la_seccion_conserva_su_orden_por_posicion() -> None:
    secciones = (make_section(2), make_section(1))

    ordenadas = tuple(sorted(secciones, key=lambda seccion: seccion.position))

    assert [seccion.position for seccion in ordenadas] == [1, 2]
    assert ordenadas[0].roman_numeral == "I"


def test_la_revision_usa_etiquetas_bien_y_mal() -> None:
    assert ReviewLabel.BIEN.value == "bien"
    assert ReviewLabel.MAL.value == "mal"


def test_el_examen_por_defecto_esta_en_borrador() -> None:
    assert make_exam().status is ExamStatus.DRAFT
    assert isinstance(make_exam(), Exam)
