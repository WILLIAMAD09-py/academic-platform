"""Reglas de negocio del examen.

Cada regla es una **función pura** que recibe el agregado y devuelve
incidencias (`ValidationIssue`); ninguna modifica el examen. `validate_exam`
las agrega y produce un `RuleResult` con dos niveles:

- **errores**: impiden continuar con el pipeline (cantidad de preguntas fuera
  de rango, incisos incorrectos, código duplicado...).
- **avisos**: no bloquean, pero el pipeline puede_usarlos para decidir si el
  examen termina en `COMPLETED` o en `COMPLETED_WITH_WARNINGS` (por ejemplo,
  un enunciado que depende del orden de los incisos).

Los límites (`RuleLimits`) son los mismos que expone la configuración de la
aplicación; la capa de aplicación los construye a partir de `core.config`.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass
from enum import StrEnum

from modules.exams.domain.models import BlockKind, Exam, Question, QuestionType

#: Letras de inciso admitidas por el dominio (A-E).
LETRAS_INCISO: tuple[str, ...] = ("a", "b", "c", "d", "e")

#: Patrón del código de examen: exactamente cinco dígitos.
PATRON_CODIGO = re.compile(r"[0-9]{5}")

#: Incidencias que la API debe traducir a **409 Conflict** (no a 422): el
#: `exam_code` duplicado choca con un recurso existente, no con el formato de
#: los datos (prompt, secciones 6.11 y 12).
CONFLICT_CODES: frozenset[str] = frozenset({"EXAM_CODE_DUPLICATE"})


class Severity(StrEnum):
    """Gravedad de una incidencia."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Incidencia detectada por una regla.

    Attributes:
        code: Código estable de la incidencia (por ejemplo `OPTION_CORRECT_COUNT`).
        field: Campo afectado, con una ruta legible.
        message: Explicación en lenguaje natural.
        severity: Error o aviso.
        location: Identificador del elemento concreto (pregunta, sección...).
    """

    code: str
    field: str
    message: str
    severity: Severity = Severity.ERROR
    location: str | None = None


@dataclass(frozen=True, slots=True)
class RuleResult:
    """Resultado de validar un examen: errores y avisos."""

    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        """`True` si no hay errores (los avisos no invalidan)."""
        return not self.errors

    @property
    def issues(self) -> tuple[ValidationIssue, ...]:
        """Todas las incidencias, errores primero."""
        return (*self.errors, *self.warnings)

    @property
    def error_codes(self) -> tuple[str, ...]:
        """Códigos de los errores."""
        return tuple(issue.code for issue in self.errors)

    @property
    def warning_codes(self) -> tuple[str, ...]:
        """Códigos de los avisos."""
        return tuple(issue.code for issue in self.warnings)

    @property
    def conflict_codes(self) -> tuple[str, ...]:
        """Códigos de error que la API traduce a 409 (conflicto), no a 422."""
        return tuple(issue.code for issue in self.errors if issue.code in CONFLICT_CODES)

    @property
    def has_conflicts(self) -> bool:
        """`True` si alguna incidencia debe responderse con 409."""
        return bool(self.conflict_codes)


@dataclass(frozen=True, slots=True)
class RuleLimits:
    """Límites de negocio aplicados a un examen.

    Sus valores por defecto coinciden con los de `core.config.Settings`; la
    capa de aplicación construye esta estructura a partir de la configuración
    real, de modo que el dominio no depende del entorno.
    """

    min_questions: int = 25
    max_questions: int = 50
    min_options: int = 2
    max_options: int = 4
    max_text_length: int = 2000


# --- Utilidades de texto -----------------------------------------------------


def normalize_text(value: str) -> str:
    """Normaliza un texto para comparaciones.

    Minúsculas, sin acentos, sin signos de puntuación y con espacios
    colapsados: "  ¿Cuánto es  2+2? " y "¿cuánto es 2 + 2" quedan iguales.
    """
    texto = unicodedata.normalize("NFKD", value.lower())
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split())


#: Fórmulas que hacen depender un inciso del resto de incisos.
PATRONES_REFERENCIA: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\btodas\s+las\s+anteriores\b"), "todas las anteriores"),
    (re.compile(r"\bninguna\s+de\s+las\s+anteriores\b"), "ninguna de las anteriores"),
    (re.compile(r"\ba\s+y\s+b\b"), "a y b"),
    (re.compile(r"\bambas\b"), "ambas"),
    (re.compile(r"\blas\s+dos\s+anteriores\b"), "las dos anteriores"),
)

#: Fórmulas que indican un orden natural de las respuestas.
PATRONES_ORDEN_NATURAL: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bde\s+menor\s+a\s+mayor\b"), "de menor a mayor"),
    (re.compile(r"\bde\s+mayor\s+a\s+menor\b"), "de mayor a menor"),
    (re.compile(r"\ben\s+orden\s+cronologico\b"), "en orden cronológico"),
    (re.compile(r"\borden\s+cronologico\b"), "orden cronológico"),
    (re.compile(r"\bfechas?\b"), "fechas"),
    (re.compile(r"\bnumeros\b"), "números"),
)


# --- Reglas de la cabecera ----------------------------------------------------


def validate_exam_code(
    exam_code: str, existing_codes: Collection[str] = ()
) -> list[ValidationIssue]:
    """El código de examen tiene cinco dígitos y es único."""
    incidencias: list[ValidationIssue] = []

    if PATRON_CODIGO.fullmatch(exam_code) is None:
        incidencias.append(
            ValidationIssue(
                code="EXAM_CODE_FORMAT",
                field="exam_code",
                message=(
                    f"El código de examen '{exam_code}' no es válido: "
                    "debe tener exactamente cinco dígitos."
                ),
            )
        )

    if exam_code in existing_codes:
        incidencias.append(
            ValidationIssue(
                code="EXAM_CODE_DUPLICATE",
                field="exam_code",
                message=f"Ya existe un examen con el código '{exam_code}'.",
            )
        )

    return incidencias


def validate_question_count(
    question_count: int, limits: RuleLimits = RuleLimits()
) -> list[ValidationIssue]:
    """La cantidad de preguntas está dentro del rango configurado."""
    incidencias: list[ValidationIssue] = []

    if question_count < limits.min_questions:
        incidencias.append(
            ValidationIssue(
                code="QUESTION_COUNT_MIN",
                field="questions",
                message=(
                    f"El examen tiene {question_count} preguntas y el mínimo es "
                    f"{limits.min_questions}."
                ),
            )
        )
    elif question_count > limits.max_questions:
        incidencias.append(
            ValidationIssue(
                code="QUESTION_COUNT_MAX",
                field="questions",
                message=(
                    f"El examen tiene {question_count} preguntas y el máximo es "
                    f"{limits.max_questions}."
                ),
            )
        )

    return incidencias


def validate_header_fields(exam: Exam) -> list[ValidationIssue]:
    """La cabecera del examen tiene los campos obligatorios.

    Obligatorios (prompt, sección 6.12): título, periodo y unidad de
    aprendizaje. `course_code` forma parte del modelo del examen (sección 7)
    pero **no** figura entre los campos obligatorios del resumen: si falta, se
    avisa en lugar de bloquear.
    """
    obligatorios = (
        ("title", "HEADER_TITLE_REQUIRED", "título"),
        ("period", "HEADER_PERIOD_REQUIRED", "periodo"),
        ("learning_unit", "HEADER_LEARNING_UNIT_REQUIRED", "unidad de aprendizaje"),
    )

    incidencias: list[ValidationIssue] = []
    for atributo, codigo, etiqueta in obligatorios:
        valor = getattr(exam, atributo)
        if not str(valor).strip():
            incidencias.append(
                ValidationIssue(
                    code=codigo,
                    field=atributo,
                    message=f"El {etiqueta} del examen es obligatorio.",
                )
            )

    if not str(exam.course_code).strip():
        incidencias.append(
            ValidationIssue(
                code="HEADER_COURSE_MISSING",
                field="course_code",
                message=(
                    "El código de materia del examen está vacío: revísalo antes "
                    "de generar los documentos."
                ),
                severity=Severity.WARNING,
            )
        )

    return incidencias


# --- Reglas de estructura -----------------------------------------------------


def validate_sections(exam: Exam) -> list[ValidationIssue]:
    """Hay secciones válidas y cada pregunta pertenece a una de ellas."""
    incidencias: list[ValidationIssue] = []

    if not exam.sections:
        incidencias.append(
            ValidationIssue(
                code="SECTION_COUNT_MIN",
                field="sections",
                message="El examen debe tener al menos una sección.",
            )
        )
        return incidencias

    posiciones: set[int] = set()
    for seccion in exam.sections:
        if seccion.position < 1:
            incidencias.append(
                ValidationIssue(
                    code="SECTION_POSITION_INVALID",
                    field="sections",
                    message=(
                        f"La sección {seccion.id} tiene una posición inválida "
                        f"({seccion.position}): debe ser mayor que cero."
                    ),
                    location=seccion.id,
                )
            )
        elif seccion.position in posiciones:
            incidencias.append(
                ValidationIssue(
                    code="SECTION_POSITION_DUPLICATED",
                    field="sections",
                    message=(
                        f"Dos secciones comparten la posición {seccion.position}: "
                        "el orden de las secciones debe ser único."
                    ),
                    location=seccion.id,
                )
            )
        else:
            posiciones.add(seccion.position)

    ids_seccion = {seccion.id for seccion in exam.sections}
    for pregunta in exam.questions:
        if pregunta.section_id not in ids_seccion:
            incidencias.append(
                ValidationIssue(
                    code="QUESTION_UNKNOWN_SECTION",
                    field="questions",
                    message=(
                        f"La pregunta {pregunta.id} apunta a la sección "
                        f"'{pregunta.section_id}', que no existe."
                    ),
                    location=pregunta.id,
                )
            )

    return incidencias


def validate_blocks(exam: Exam) -> list[ValidationIssue]:
    """Los bloques no se solapan, no referencian elementos inexistentes y
    sus miembros son del tipo que corresponde."""
    incidencias: list[ValidationIssue] = []

    ids_pregunta = {pregunta.id for pregunta in exam.questions}
    ids_seccion = {seccion.id for seccion in exam.sections}

    bloques_pregunta: dict[str, list[str]] = {}
    bloques_seccion: dict[str, list[str]] = {}

    for bloque in exam.blocks:
        if not bloque.member_ids:
            incidencias.append(
                ValidationIssue(
                    code="BLOCK_EMPTY",
                    field="blocks",
                    message=f"El bloque {bloque.id} no contiene elementos.",
                    severity=Severity.WARNING,
                    location=bloque.id,
                )
            )

        for miembro in bloque.member_ids:
            if bloque.kind is BlockKind.QUESTION_GROUP:
                if miembro in ids_seccion:
                    incidencias.append(
                        ValidationIssue(
                            code="BLOCK_MEMBER_KIND_MISMATCH",
                            field="blocks",
                            message=(
                                f"El bloque {bloque.id} es de preguntas pero "
                                f"'{miembro}' es una sección."
                            ),
                            location=bloque.id,
                        )
                    )
                elif miembro not in ids_pregunta:
                    incidencias.append(
                        ValidationIssue(
                            code="BLOCK_MEMBER_UNKNOWN",
                            field="blocks",
                            message=(
                                f"El bloque {bloque.id} referencia la pregunta "
                                f"'{miembro}', que no existe."
                            ),
                            location=bloque.id,
                        )
                    )
                else:
                    bloques_pregunta.setdefault(miembro, []).append(bloque.id)
            else:
                if miembro in ids_pregunta:
                    incidencias.append(
                        ValidationIssue(
                            code="BLOCK_MEMBER_KIND_MISMATCH",
                            field="blocks",
                            message=(
                                f"El bloque {bloque.id} es de secciones pero "
                                f"'{miembro}' es una pregunta."
                            ),
                            location=bloque.id,
                        )
                    )
                elif miembro not in ids_seccion:
                    incidencias.append(
                        ValidationIssue(
                            code="BLOCK_MEMBER_UNKNOWN",
                            field="blocks",
                            message=(
                                f"El bloque {bloque.id} referencia la sección "
                                f"'{miembro}', que no existe."
                            ),
                            location=bloque.id,
                        )
                    )
                else:
                    bloques_seccion.setdefault(miembro, []).append(bloque.id)

    for pregunta_id, bloques in bloques_pregunta.items():
        if len(bloques) > 1:
            incidencias.append(
                ValidationIssue(
                    code="BLOCK_QUESTION_IN_TWO_GROUPS",
                    field="blocks",
                    message=(
                        f"La pregunta {pregunta_id} pertenece a varios bloques "
                        f"({', '.join(sorted(bloques))}): un elemento no puede "
                        "estar en dos bloques del mismo tipo."
                    ),
                    location=pregunta_id,
                )
            )

    for seccion_id, bloques in bloques_seccion.items():
        if len(bloques) > 1:
            incidencias.append(
                ValidationIssue(
                    code="BLOCK_SECTION_IN_TWO_GROUPS",
                    field="blocks",
                    message=(
                        f"La sección {seccion_id} pertenece a varios bloques "
                        f"({', '.join(sorted(bloques))}): un elemento no puede "
                        "estar en dos bloques del mismo tipo."
                    ),
                    location=seccion_id,
                )
            )

    return incidencias


# --- Reglas de las preguntas --------------------------------------------------


def _validar_pregunta(pregunta: Question, limits: RuleLimits) -> list[ValidationIssue]:
    """Reglas que aplican a una pregunta y a sus incisos."""
    incidencias: list[ValidationIssue] = []
    identificador = pregunta.id

    if pregunta.question_type is QuestionType.OPEN:
        incidencias.append(
            ValidationIssue(
                code="QUESTION_TYPE_UNSUPPORTED",
                field="questions",
                message=(
                    f"La pregunta {identificador} es abierta: solo se admiten "
                    "preguntas de opción múltiple."
                ),
                location=identificador,
            )
        )

    cantidad = len(pregunta.options)
    if cantidad < limits.min_options:
        incidencias.append(
            ValidationIssue(
                code="OPTION_COUNT_MIN",
                field="options",
                message=(
                    f"La pregunta {identificador} tiene {cantidad} incisos y el "
                    f"mínimo es {limits.min_options}."
                ),
                location=identificador,
            )
        )
    elif cantidad > limits.max_options:
        incidencias.append(
            ValidationIssue(
                code="OPTION_COUNT_MAX",
                field="options",
                message=(
                    f"La pregunta {identificador} tiene {cantidad} incisos y el "
                    f"máximo es {limits.max_options}."
                ),
                location=identificador,
            )
        )

    etiquetas: set[str] = set()
    for opcion in pregunta.options:
        if opcion.label not in LETRAS_INCISO:
            incidencias.append(
                ValidationIssue(
                    code="OPTION_LABEL_INVALID",
                    field=f"options[{opcion.label}]",
                    message=(
                        f"El inciso '{opcion.label}' de la pregunta {identificador} "
                        f"no es válido: se admiten {', '.join(LETRAS_INCISO)}."
                    ),
                    location=identificador,
                )
            )
        elif opcion.label == "e" and limits.max_options < len(LETRAS_INCISO):
            incidencias.append(
                ValidationIssue(
                    code="OPTION_LABEL_NOT_ALLOWED",
                    field=f"options[{opcion.label}]",
                    message=(
                        f"El inciso 'e' de la pregunta {identificador} solo es "
                        f"válido si se permiten {len(LETRAS_INCISO)} incisos."
                    ),
                    location=identificador,
                )
            )

        if opcion.label in etiquetas:
            incidencias.append(
                ValidationIssue(
                    code="OPTION_LABEL_DUPLICATED",
                    field=f"options[{opcion.label}]",
                    message=(
                        f"La pregunta {identificador} repite la letra "
                        f"'{opcion.label}' en dos incisos."
                    ),
                    location=identificador,
                )
            )
        etiquetas.add(opcion.label)

    correctos = [opcion for opcion in pregunta.options if opcion.is_correct]
    if len(correctos) != 1:
        incidencias.append(
            ValidationIssue(
                code="OPTION_CORRECT_COUNT",
                field="options",
                message=(
                    f"La pregunta {identificador} tiene {len(correctos)} incisos "
                    "correctos: debe tener exactamente uno."
                ),
                location=identificador,
            )
        )

    if not pregunta.stem_current.strip():
        incidencias.append(
            ValidationIssue(
                code="STEM_TEXT_EMPTY",
                field="stem",
                message=f"El enunciado de la pregunta {identificador} está vacío.",
                location=identificador,
            )
        )
    elif len(pregunta.stem_current) > limits.max_text_length:
        incidencias.append(
            ValidationIssue(
                code="TEXT_TOO_LONG",
                field="stem",
                message=(
                    f"El enunciado de la pregunta {identificador} supera los "
                    f"{limits.max_text_length} caracteres."
                ),
                location=identificador,
            )
        )

    for opcion in pregunta.options:
        if not opcion.text_current.strip():
            incidencias.append(
                ValidationIssue(
                    code="OPTION_TEXT_EMPTY",
                    field=f"options[{opcion.label}]",
                    message=(
                        f"El inciso '{opcion.label}' de la pregunta {identificador} está vacío."
                    ),
                    location=identificador,
                )
            )
        elif len(opcion.text_current) > limits.max_text_length:
            incidencias.append(
                ValidationIssue(
                    code="TEXT_TOO_LONG",
                    field=f"options[{opcion.label}]",
                    message=(
                        f"El inciso '{opcion.label}' de la pregunta {identificador} "
                        f"supera los {limits.max_text_length} caracteres."
                    ),
                    location=identificador,
                )
            )

    return incidencias


def validate_questions(exam: Exam, limits: RuleLimits = RuleLimits()) -> list[ValidationIssue]:
    """Cada pregunta tiene incisos válidos y una única respuesta correcta."""
    incidencias: list[ValidationIssue] = []
    for pregunta in exam.questions:
        incidencias.extend(_validar_pregunta(pregunta, limits))
    return incidencias


# --- Avisos -------------------------------------------------------------------


def detect_option_references(exam: Exam) -> list[ValidationIssue]:
    """Avisa si algún enunciado o inciso depende del orden de las opciones.

    Barajar los incisos rompería la pregunta: lo más seguro es desactivar
    `shuffle_options` en esa pregunta.
    """
    incidencias: list[ValidationIssue] = []

    for pregunta in exam.questions:
        textos = [pregunta.stem_current] + [opcion.text_current for opcion in pregunta.options]
        for texto in textos:
            normalizado = normalize_text(texto)
            for patron, etiqueta in PATRONES_REFERENCIA:
                if patron.search(normalizado) is not None:
                    incidencias.append(
                        ValidationIssue(
                            code="OPTION_REFERENCE_WARNING",
                            field="questions",
                            message=(
                                f"La pregunta {pregunta.id} contiene la referencia "
                                f"'{etiqueta}': se sugiere desactivar "
                                "`shuffle_options` o bloquear ese inciso."
                            ),
                            severity=Severity.WARNING,
                            location=pregunta.id,
                        )
                    )
                    break

    return incidencias


def detect_natural_order(exam: Exam) -> list[ValidationIssue]:
    """Avisa si algún enunciado exige un orden natural de las respuestas."""
    incidencias: list[ValidationIssue] = []

    for pregunta in exam.questions:
        normalizado = normalize_text(pregunta.stem_current)
        for patron, etiqueta in PATRONES_ORDEN_NATURAL:
            if patron.search(normalizado) is not None:
                incidencias.append(
                    ValidationIssue(
                        code="NATURAL_ORDER_WARNING",
                        field="questions",
                        message=(
                            f"La pregunta {pregunta.id} exige un orden natural "
                            f"('{etiqueta}'): se sugiere desactivar `shuffle_options`."
                        ),
                        severity=Severity.WARNING,
                        location=pregunta.id,
                    )
                )
                break

    return incidencias


def detect_duplicate_stems(exam: Exam) -> list[ValidationIssue]:
    """Avisa si dos preguntas tienen el mismo enunciado."""
    incidencias: list[ValidationIssue] = []

    por_normalizado: dict[str, list[str]] = {}
    for pregunta in exam.questions:
        clave = normalize_text(pregunta.stem_current)
        if not clave:
            continue
        por_normalizado.setdefault(clave, []).append(pregunta.id)

    for identificadores in por_normalizado.values():
        if len(identificadores) < 2:
            continue
        incidencias.append(
            ValidationIssue(
                code="DUPLICATE_STEM_WARNING",
                field="questions",
                message=(
                    "Las preguntas "
                    + ", ".join(sorted(identificadores))
                    + " comparten el mismo enunciado."
                ),
                severity=Severity.WARNING,
                location=sorted(identificadores)[0],
            )
        )

    return incidencias


# --- Agregación ---------------------------------------------------------------


def _separar(
    incidencias: list[ValidationIssue],
) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    """Separa las incidencias en errores y avisos según su gravedad."""
    errores = [issue for issue in incidencias if issue.severity is Severity.ERROR]
    avisos = [issue for issue in incidencias if issue.severity is not Severity.ERROR]
    return errores, avisos


def validate_exam(
    exam: Exam,
    limits: RuleLimits = RuleLimits(),
    existing_codes: Collection[str] = (),
) -> RuleResult:
    """Valida un examen completo y agrega errores y avisos.

    Cada regla se ejecuta siempre **completa** (no se corta en el primer
    fallo): el docente recibe la lista entera de lo que hay que corregir.

    Args:
        exam: Examen a validar.
        limits: Límites de negocio aplicables.
        existing_codes: Códigos de examen ya registrados (para la unicidad).

    Returns:
        `RuleResult` con los errores y los avisos detectados.
    """
    incidencias: list[ValidationIssue] = []

    incidencias.extend(validate_exam_code(exam.exam_code, existing_codes))
    incidencias.extend(validate_question_count(len(exam.questions), limits))
    incidencias.extend(validate_header_fields(exam))
    incidencias.extend(validate_sections(exam))
    incidencias.extend(validate_blocks(exam))
    incidencias.extend(validate_questions(exam, limits))

    incidencias.extend(detect_option_references(exam))
    incidencias.extend(detect_natural_order(exam))
    incidencias.extend(detect_duplicate_stems(exam))

    errores, avisos = _separar(incidencias)

    return RuleResult(errors=tuple(errores), warnings=tuple(avisos))
