"""Pruebas de humo del scaffolding (paso 1).

Verifican que el esqueleto del repositorio es importable y que se respetan las
restricciones estructurales acordadas en `docs/ASSUMPTIONS.md`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"


def test_core_package_is_importable() -> None:
    import core

    assert core.__name__ == "core"


@pytest.mark.parametrize(
    "module_name",
    [
        "modules",
        "modules.exams",
        "modules.exams.api",
        "modules.exams.domain",
        "modules.exams.application",
        "modules.exams.infrastructure",
        "modules.exams.infrastructure.reviewers",
    ],
)
def test_exams_layers_are_importable(module_name: str) -> None:
    import importlib

    assert importlib.import_module(module_name).__name__ == module_name


def test_expected_source_layout_exists() -> None:
    expected = [
        SRC / "core",
        SRC / "modules" / "exams" / "api",
        SRC / "modules" / "exams" / "domain",
        SRC / "modules" / "exams" / "application",
        SRC / "modules" / "exams" / "infrastructure",
    ]

    missing = [str(path) for path in expected if not path.is_dir()]

    assert missing == []


def test_source_does_not_import_stdlib_platform() -> None:
    """`platform` es un módulo de la stdlib: importarlo desde `src` lo rompe.

    Ver `docs/ASSUMPTIONS.md` A14. Si alguien reintroduce el nombre, la
    utilidad de diagnóstico se vuelve un error críptico en tiempo de ejecución.
    """
    offenders: list[str] = []

    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name == "platform" or name.startswith("platform.") for name in names):
                offenders.append(f"{path.relative_to(SRC.parent)}:{node.lineno}")

    assert offenders == [], f"imports prohibidos de `platform`: {offenders}"
