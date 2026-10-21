"""Pruebas del punto de entrada de la CLI (`modules.exams.cli`).

La CLI completa llega en el paso 11; aquí se comprueba que el comando de
consola `exams-cli` (declarado en `pyproject.toml`) **existe** y explica con
claridad que todavía no está implementada, en lugar de fallar con un
`ImportError` incomprensible.
"""

from __future__ import annotations

import pytest

from modules.exams.cli import main


def test_la_cli_pendiente_explica_el_siguiente_paso(capsys: pytest.CaptureFixture[str]) -> None:
    codigo = main([])

    capturado = capsys.readouterr()

    assert codigo == 1
    assert "paso 11" in capturado.err
    assert "python -m modules.exams.cli process" in capturado.err


def test_la_cli_pendiente_informa_de_los_argumentos_recibidos(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["process", "--file", "examen.json"])

    capturado = capsys.readouterr()

    assert "process" in capturado.err
