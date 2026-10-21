"""Cumplimiento de la regla "sin APIs externas de modelos de IA".

Regla de proyecto (`AGENTS.md` → *Modelo de IA*) y del prompt de fase
(sección 3, 13.13 y 19):

    El modelo de revisión lo entrena y lo aporta el usuario; se conecta por
    adaptador local. Está prohibido llamar a APIs externas de modelos de IA
    (OpenAI, Anthropic, Google u otras) desde el código de la aplicación,
    incluidos el stub y el adaptador.

Estas pruebas fallan si alguien introduce un SDK de inferencia externa o una
referencia a sus endpoints. La herramienta de desarrollo (OpenCode) no forma
parte del producto y, por tanto, no aparece aquí.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"

FORBIDDEN_MODULES = frozenset(
    {
        "anthropic",
        "anyscale",
        "azure",
        "cohere",
        "fireworks",
        "google",
        "google.generativeai",
        "groq",
        "litellm",
        "mistralai",
        "openai",
        "replicate",
        "together",
        "vertexai",
    }
)

FORBIDDEN_ENDPOINTS = (
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.cohere.ai",
    "api.mistral.ai",
    "api.groq.com",
    "openrouter.ai",
    "api.together.xyz",
    "api.replicate.com",
)


def _python_sources() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append(node.module)
    return modules


def test_source_tree_is_not_empty() -> None:
    """Evita que la suite pase en verde por una comprobación vacía."""
    assert _python_sources(), "no se encontraron fuentes en src/"


@pytest.mark.parametrize("path", _python_sources(), ids=lambda p: p.name)
def test_no_external_ai_sdk_imports(path: Path) -> None:
    offenders = [
        module for module in _imported_modules(path) if module.split(".")[0] in FORBIDDEN_MODULES
    ]

    assert offenders == [], f"{path.name} importa SDK de IA externa: {offenders}"


@pytest.mark.parametrize("path", _python_sources(), ids=lambda p: p.name)
def test_no_external_ai_endpoints_referenced(path: Path) -> None:
    content = path.read_text(encoding="utf-8").lower()

    offenders = [endpoint for endpoint in FORBIDDEN_ENDPOINTS if endpoint in content]

    assert offenders == [], f"{path.name} referencia endpoints de IA externa: {offenders}"


def test_ai_dependencies_not_declared_in_pyproject() -> None:
    """Los SDK de IA externa tampoco pueden entrar como dependencia del proyecto."""
    pyproject = SRC.parent / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8").lower()

    offenders = [name for name in FORBIDDEN_MODULES if f'"{name}' in content]

    assert offenders == [], f"pyproject.toml declara dependencias de IA externa: {offenders}"
