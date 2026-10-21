"""Cálculo de la ponderación (peso) de las preguntas de un examen.

Todos los pesos suman **exactamente** 100,00: la base se redondea a dos
decimales y la **última pregunta absorbe la diferencia** de redondeo, de
modo que la suma nunca se desvía por errores de coma flotante.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

#: Valor total que suman los pesos de un examen.
TOTAL_WEIGHT = Decimal("100.00")

#: Precisión (decimales) de cada peso.
WEIGHT_PRECISION = Decimal("0.01")


def calculate_weights(count: int) -> tuple[Decimal, ...]:
    """Reparte el total en `count` pesos de dos decimales.

    Args:
        count: Número de preguntas a ponderar (debe ser mayor que cero).

    Returns:
        Tuple con un peso por pregunta, cuya suma es exactamente 100,00.

    Raises:
        ValueError: Si `count` es menor que 1.
    """
    if count < 1:
        raise ValueError("La cantidad de preguntas a ponderar debe ser al menos 1")

    base = (TOTAL_WEIGHT / count).quantize(WEIGHT_PRECISION, rounding=ROUND_HALF_UP)

    pesos: list[Decimal] = [base] * (count - 1)
    pesos.append(TOTAL_WEIGHT - sum(pesos, Decimal("0.00")))

    return tuple(pesos)


def assign_weights(question_ids: Sequence[str]) -> dict[str, Decimal]:
    """Asigna un peso a cada pregunta, conservando el orden indicado.

    Args:
        question_ids: Identificadores de las preguntas, en orden de aparición.

    Returns:
        Diccionario `id de pregunta -> peso`.

    Raises:
        ValueError: Si la lista de preguntas está vacía.
    """
    if len(question_ids) == 0:
        raise ValueError("No se pueden ponderar exámenes sin preguntas")

    return dict(zip(question_ids, calculate_weights(len(question_ids)), strict=True))


def total_weight(weights: Sequence[Decimal]) -> Decimal:
    """Suma de un conjunto de pesos."""
    return sum(weights, Decimal("0.00"))
