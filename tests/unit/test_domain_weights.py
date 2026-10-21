"""Pruebas de la ponderación de preguntas (`domain.weights`)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from modules.exams.domain.weights import (
    TOTAL_WEIGHT,
    assign_weights,
    calculate_weights,
    total_weight,
)


@pytest.mark.parametrize("cantidad", [1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 16, 17, 25, 33, 49, 50])
def test_los_pesos_suman_exactamente_el_total(cantidad: int) -> None:
    pesos = calculate_weights(cantidad)

    assert len(pesos) == cantidad
    assert total_weight(pesos) == Decimal("100.00")
    assert all(peso > 0 for peso in pesos)
    assert all(peso.as_tuple().exponent == -2 for peso in pesos)


def test_el_ultimo_peso_absorbe_el_resto_del_redondeo() -> None:
    pesos = calculate_weights(3)

    assert pesos == (Decimal("33.33"), Decimal("33.33"), Decimal("33.34"))
    assert total_weight(pesos) == Decimal("100.00")


def test_el_reparto_es_equitativo_cuando_el_total_es_exacto() -> None:
    pesos = calculate_weights(25)

    assert pesos == tuple(Decimal("4.00") for _ in range(25))


def test_una_sola_pregunta_valora_el_total() -> None:
    assert calculate_weights(1) == (Decimal("100.00"),)


def test_la_cantidad_debe_ser_positiva() -> None:
    with pytest.raises(ValueError, match="al menos 1"):
        calculate_weights(0)

    with pytest.raises(ValueError, match="sin preguntas"):
        assign_weights([])


def test_asignar_pesos_conserva_el_orden_de_las_preguntas() -> None:
    ids = ["q001", "q002", "q003"]

    pesos = assign_weights(ids)

    assert list(pesos) == ids
    assert pesos["q001"] == Decimal("33.33")
    assert pesos["q003"] == Decimal("33.34")
    assert total_weight(pesos.values()) == TOTAL_WEIGHT
