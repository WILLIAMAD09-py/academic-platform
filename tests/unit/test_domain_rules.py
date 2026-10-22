"""Pruebas de las reglas de negocio del examen (`domain.rules`)."""

from __future__ import annotations

from dataclasses import replace

from core.config import Settings
from modules.exams.domain.models import (
    BlockKind,
    Exam,
    QuestionType,
    Section,
)
from modules.exams.domain.rules import (
    RuleLimits,
    detect_duplicate_stems,
    detect_natural_order,
    detect_option_references,
    validate_blocks,
    validate_exam,
    validate_exam_code,
    validate_header_fields,
    validate_question_count,
    validate_questions,
    validate_sections,
)
from tests.builders import make_block, make_exam, make_option, make_question, make_section

LIMITS = RuleLimits()


def codigos(issues: list) -> list[str]:
    """Extrae los códigos de las incidencias para comparar de forma legible."""
    return [issue.code for issue in issues]


# --- Código de examen -------------------------------------------------------


def test_el_codigo_de_examen_debe_tener_cinco_digitos() -> None:
    assert codigos(validate_exam_code("1234")) == ["EXAM_CODE_FORMAT"]
    assert codigos(validate_exam_code("21643a")) == ["EXAM_CODE_FORMAT"]
    assert codigos(validate_exam_code("")) == ["EXAM_CODE_FORMAT"]
    assert validate_exam_code("21643") == []


def test_el_codigo_de_examen_debe_ser_unico() -> None:
    assert codigos(validate_exam_code("21643", existing_codes={"21643"})) == ["EXAM_CODE_DUPLICATE"]
    assert validate_exam_code("21643", existing_codes={"99999"}) == []


# --- Número de preguntas -----------------------------------------------------


def test_el_numero_de_preguntas_respeta_el_rango_configurado() -> None:
    assert codigos(validate_question_count(10, LIMITS)) == ["QUESTION_COUNT_MIN"]
    assert codigos(validate_question_count(60, LIMITS)) == ["QUESTION_COUNT_MAX"]
    assert validate_question_count(25, LIMITS) == []
    assert validate_question_count(50, LIMITS) == []


# --- Cabecera ----------------------------------------------------------------


def test_los_campos_obligatorios_de_la_cabecera_se_validan() -> None:
    exam = replace(make_exam(), title="  ", course_code="", period="", learning_unit="")

    errores = [issue for issue in validate_header_fields(exam) if issue.severity.value == "error"]
    avisos = [issue for issue in validate_header_fields(exam) if issue.severity.value == "warning"]

    assert codigos(errores) == [
        "HEADER_TITLE_REQUIRED",
        "HEADER_PERIOD_REQUIRED",
        "HEADER_LEARNING_UNIT_REQUIRED",
    ]
    assert codigos(avisos) == ["HEADER_COURSE_MISSING"]


def test_el_codigo_de_materia_vacio_es_un_aviso_y_no_un_error() -> None:
    """El prompt solo exige título, periodo y unidad (sección 6.12)."""
    exam = replace(make_exam(), course_code="")

    resultado = validate_exam(exam, LIMITS)

    assert "HEADER_COURSE_MISSING" in resultado.warning_codes
    assert "HEADER_COURSE_MISSING" not in resultado.error_codes
    assert resultado.is_valid


def test_una_cabecera_completa_no_produce_incidencias() -> None:
    assert validate_header_fields(make_exam()) == []


# --- Secciones ---------------------------------------------------------------


def test_un_examen_necesita_al_menos_una_seccion() -> None:
    exam = replace(make_exam(), sections=())

    assert codigos(validate_sections(exam)) == ["SECTION_COUNT_MIN"]


def test_cada_pregunta_debe_pertenecer_a_una_seccion_existente() -> None:
    exam = replace(make_exam(question_count=1), questions=(make_question(1, section_id="sec9"),))

    assert codigos(validate_sections(exam)) == ["QUESTION_UNKNOWN_SECTION"]


def test_las_posiciones_de_seccion_deben_ser_unicas_y_positivas() -> None:
    secciones = (make_section(1), make_section(1))
    exam = replace(make_exam(), sections=secciones)

    assert "SECTION_POSITION_DUPLICATED" in codigos(validate_sections(exam))

    negativa = replace(make_exam(), sections=(replace(make_section(1), position=0),))
    assert "SECTION_POSITION_INVALID" in codigos(validate_sections(negativa))


# --- Bloques -----------------------------------------------------------------


def test_un_bloque_sin_miembros_es_un_aviso() -> None:
    exam = replace(make_exam(), blocks=(make_block("blk-1", BlockKind.QUESTION_GROUP, ()),))

    incidencias = validate_blocks(exam)

    assert codigos(incidencias) == ["BLOCK_EMPTY"]
    assert incidencias[0].severity.value == "warning"


def test_un_bloque_no_puede_referenciar_miembros_inexistentes() -> None:
    exam = replace(
        make_exam(),
        blocks=(make_block("blk-1", BlockKind.QUESTION_GROUP, ("q999",)),),
    )

    assert codigos(validate_blocks(exam)) == ["BLOCK_MEMBER_UNKNOWN"]


def test_un_bloque_de_preguntas_no_puede_contener_secciones() -> None:
    exam = replace(
        make_exam(),
        blocks=(make_block("blk-1", BlockKind.QUESTION_GROUP, ("sec1",)),),
    )

    assert codigos(validate_blocks(exam)) == ["BLOCK_MEMBER_KIND_MISMATCH"]


def test_un_bloque_de_secciones_no_puede_contener_preguntas() -> None:
    exam = replace(
        make_exam(),
        blocks=(make_block("blk-1", BlockKind.SECTION_GROUP, ("q001",)),),
    )

    assert codigos(validate_blocks(exam)) == ["BLOCK_MEMBER_KIND_MISMATCH"]


def test_un_bloque_de_secciones_no_puede_referenciar_secciones_inexistentes() -> None:
    exam = replace(
        make_exam(),
        blocks=(make_block("blk-1", BlockKind.SECTION_GROUP, ("sec9",)),),
    )

    assert codigos(validate_blocks(exam)) == ["BLOCK_MEMBER_UNKNOWN"]


def test_una_pregunta_no_puede_estar_en_dos_bloques() -> None:
    bloques = (
        make_block("blk-1", BlockKind.QUESTION_GROUP, ("q001",)),
        make_block("blk-2", BlockKind.QUESTION_GROUP, ("q001",)),
    )
    exam = replace(make_exam(), blocks=bloques)

    incidencias = validate_blocks(exam)

    assert codigos(incidencias) == ["BLOCK_QUESTION_IN_TWO_GROUPS"]
    assert incidencias[0].location == "q001"


def test_una_seccion_no_puede_estar_en_dos_bloques() -> None:
    bloques = (
        make_block("blk-1", BlockKind.SECTION_GROUP, ("sec1",)),
        make_block("blk-2", BlockKind.SECTION_GROUP, ("sec1",)),
    )
    exam = replace(make_exam(), blocks=bloques)

    assert codigos(validate_blocks(exam)) == ["BLOCK_SECTION_IN_TWO_GROUPS"]


# --- Preguntas e incisos -----------------------------------------------------


def test_cada_pregunta_necesita_al_menos_dos_incisos() -> None:
    exam = replace(make_exam(question_count=1), questions=(make_question(1, option_count=1),))

    assert "OPTION_COUNT_MIN" in codigos(validate_questions(exam, LIMITS))


def test_cada_pregunta_admite_como_maximo_cuatro_incisos_por_defecto() -> None:
    exam = replace(make_exam(question_count=1), questions=(make_question(1, option_count=5),))

    assert "OPTION_COUNT_MAX" in codigos(validate_questions(exam, LIMITS))


def test_la_letra_e_solo_es_valida_con_cinco_incisos_permitidos() -> None:
    examen_con_e = replace(
        make_exam(question_count=1),
        questions=(make_question(1, option_count=5, correct_label="e"),),
    )

    assert "OPTION_LABEL_NOT_ALLOWED" in codigos(validate_questions(examen_con_e, LIMITS))

    limites_con_e = RuleLimits(max_options=5)
    assert validate_questions(examen_con_e, limites_con_e) == []


def test_una_letra_de_inciso_invalida_se_reporta() -> None:
    pregunta = replace(
        make_question(1),
        options=(make_option("q001", 0, label="z"), make_option("q001", 1)),
    )
    exam = replace(make_exam(question_count=1), questions=(pregunta,))

    assert "OPTION_LABEL_INVALID" in codigos(validate_questions(exam, LIMITS))


def test_no_puede_haber_dos_incisos_con_la_misma_letra() -> None:
    pregunta = replace(
        make_question(1),
        options=(make_option("q001", 0, label="a"), make_option("q001", 1, label="a")),
    )
    exam = replace(make_exam(question_count=1), questions=(pregunta,))

    assert "OPTION_LABEL_DUPLICATED" in codigos(validate_questions(exam, LIMITS))


def test_cada_pregunta_necesita_exactamente_un_inciso_correcto() -> None:
    sin_correcta = replace(
        make_question(1),
        options=(make_option("q001", 0, is_correct=False), make_option("q001", 1)),
    )
    exam = replace(make_exam(question_count=1), questions=(sin_correcta,))

    assert "OPTION_CORRECT_COUNT" in codigos(validate_questions(exam, LIMITS))

    dos_correctas = replace(
        make_question(1),
        options=(
            make_option("q001", 0, is_correct=True),
            make_option("q001", 1, is_correct=True),
        ),
    )
    exam_dos = replace(make_exam(question_count=1), questions=(dos_correctas,))

    assert "OPTION_CORRECT_COUNT" in codigos(validate_questions(exam_dos, LIMITS))


def test_el_enunciado_y_los_incisos_no_pueden_estar_vacios() -> None:
    pregunta = replace(
        make_question(1, stem="   "),
        options=(make_option("q001", 0, text=""), make_option("q001", 1)),
    )
    exam = replace(make_exam(question_count=1), questions=(pregunta,))

    incidencias = codigos(validate_questions(exam, LIMITS))

    assert "STEM_TEXT_EMPTY" in incidencias
    assert "OPTION_TEXT_EMPTY" in incidencias


def test_los_textos_no_superan_el_limite_de_caracteres() -> None:
    pregunta = replace(make_question(1, stem="x" * 50), options=())
    exam = replace(make_exam(question_count=1), questions=(pregunta,))
    limites = RuleLimits(max_text_length=10)

    assert "TEXT_TOO_LONG" in codigos(validate_questions(exam, limites))


def test_el_texto_de_un_inciso_tampoco_supera_el_limite_de_caracteres() -> None:
    pregunta = replace(
        make_question(1),
        options=(make_option("q001", 0, text="y" * 50), make_option("q001", 1)),
    )
    exam = replace(make_exam(question_count=1), questions=(pregunta,))
    limites = RuleLimits(max_text_length=10)

    assert "TEXT_TOO_LONG" in codigos(validate_questions(exam, limites))


def test_una_pregunta_abierta_produce_un_error_claro() -> None:
    exam = replace(
        make_exam(question_count=1),
        questions=(make_question(1, question_type=QuestionType.OPEN),),
    )

    assert "QUESTION_TYPE_UNSUPPORTED" in codigos(validate_questions(exam, LIMITS))


# --- Avisos ------------------------------------------------------------------


def test_se_avisa_cuando_el_enunciado_referencia_otros_incisos() -> None:
    exam = replace(
        make_exam(question_count=1),
        questions=(
            make_question(
                1,
                stem="Señale la opción correcta. Todas las anteriores son falsas.",
            ),
        ),
    )

    incidencias = detect_option_references(exam)

    assert codigos(incidencias) == ["OPTION_REFERENCE_WARNING"]
    assert incidencias[0].severity.value == "warning"


def test_se_avisa_cuando_el_enunciado_exige_un_orden_natural() -> None:
    exam = replace(
        make_exam(question_count=1),
        questions=(make_question(1, stem="Ordene las fechas de menor a mayor."),),
    )

    assert codigos(detect_natural_order(exam)) == ["NATURAL_ORDER_WARNING"]


def test_se_avisa_cuando_existen_enunciados_duplicados() -> None:
    exam = replace(
        make_exam(question_count=2),
        questions=(
            make_question(1, stem="¿Cuánto es 2 + 2?"),
            make_question(2, stem="¿Cuánto es  2+2 ?"),
        ),
    )

    incidencias = detect_duplicate_stems(exam)

    assert codigos(incidencias) == ["DUPLICATE_STEM_WARNING"]
    assert incidencias[0].location == "q001"


def test_los_enunciados_vacios_no_se_comparan_entre_si() -> None:
    exam = replace(
        make_exam(question_count=2),
        questions=(
            make_question(1, stem="   "),
            make_question(2, stem=""),
        ),
    )

    assert detect_duplicate_stems(exam) == []


# --- Agregación --------------------------------------------------------------


def test_un_examen_valido_no_reporta_incidencias() -> None:
    resultado = validate_exam(make_exam(), LIMITS)

    assert resultado.is_valid
    assert resultado.errors == ()
    assert resultado.warnings == ()


def test_la_validacion_agrega_errores_y_avisos() -> None:
    exam = replace(
        make_exam(question_count=1),
        exam_code="123",
        questions=(make_question(1, stem="Todas las anteriores son correctas."),),
    )

    resultado = validate_exam(exam, LIMITS)

    assert not resultado.is_valid
    assert "EXAM_CODE_FORMAT" in resultado.error_codes
    assert "QUESTION_COUNT_MIN" in resultado.error_codes
    assert "OPTION_REFERENCE_WARNING" in resultado.warning_codes
    assert len(resultado.issues) == len(resultado.errors) + len(resultado.warnings)


def test_los_avisos_de_las_reglas_mixtas_no_se_convierten_en_errores() -> None:
    """`validate_blocks` devuelve avisos y errores: cada uno en su lista."""
    exam = replace(
        make_exam(),
        blocks=(
            make_block("blk-1", BlockKind.QUESTION_GROUP, ()),
            make_block("blk-2", BlockKind.QUESTION_GROUP, ("q999",)),
        ),
    )

    resultado = validate_exam(exam, LIMITS)

    assert "BLOCK_EMPTY" in resultado.warning_codes
    assert "BLOCK_EMPTY" not in resultado.error_codes
    assert "BLOCK_MEMBER_UNKNOWN" in resultado.error_codes
    assert len(resultado.issues) == len(resultado.errors) + len(resultado.warnings)


def test_los_codigos_de_examen_existentes_producen_conflicto() -> None:
    resultado = validate_exam(make_exam(), LIMITS, existing_codes={"21643"})

    assert "EXAM_CODE_DUPLICATE" in resultado.error_codes


def test_el_codigo_duplicado_se_marca_como_conflicto_409() -> None:
    """El prompt pide 409 (no 422) cuando el `exam_code` ya existe."""
    resultado = validate_exam(make_exam(), LIMITS, existing_codes={"21643"})

    assert resultado.has_conflicts
    assert resultado.conflict_codes == ("EXAM_CODE_DUPLICATE",)


def test_un_examen_sin_conflictos_no_lo_declara() -> None:
    resultado = validate_exam(make_exam(), LIMITS)

    assert not resultado.has_conflicts
    assert resultado.conflict_codes == ()


def test_los_limites_por_defecto_coinciden_con_la_configuracion() -> None:
    settings = Settings(_env_file=None)
    limites = RuleLimits()

    assert limites.min_questions == settings.exams_min_questions
    assert limites.max_questions == settings.exams_max_questions
    assert limites.min_options == settings.exams_min_options
    assert limites.max_options == settings.exams_max_options
    assert limites.max_text_length == settings.exams_max_text_length


def test_la_validacion_no_modifica_el_examen() -> None:
    exam: Exam = make_exam()

    validate_exam(exam, LIMITS)

    assert exam.status.value == "DRAFT"
    assert exam.questions[0].stem_current == "Enunciado de la pregunta 1"


def test_validate_sections_detecta_posiciones_no_contiguas() -> None:
    seccion_a = Section(id="s1", exam_id="e1", position=1)
    seccion_c = Section(id="s2", exam_id="e1", position=3)
    examen = Exam(
        id="e1",
        exam_code="12345",
        title="T",
        period="2026-1",
        learning_unit="U",
        course_code="VC",
        teacher_id="t1",
    )
    examen = replace(examen, sections=(seccion_a, seccion_c), questions=())

    incidencias = validate_sections(examen)

    assert "SECTION_POSITION_NOT_CONTIGUOUS" in codigos(incidencias)
