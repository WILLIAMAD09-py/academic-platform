"""Pruebas de pureza del dominio de exámenes.

El dominio es la capa más interna: no conoce FastAPI, SQLAlchemy ni la
persistencia. Estas pruebas son la barrera que impide que esa frontera se
diluya por accidente.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DOMINIO = RAIZ / "src" / "modules" / "exams" / "domain"

#: Módulos que el dominio no puede importar en ningún caso.
MODULOS_PROHIBIDOS = {
    "alembic",
    "docx",
    "fastapi",
    "httpx",
    "openai",
    "anthropic",
    "pydantic",
    "pydantic_settings",
    "requests",
    "sqlalchemy",
    "starlette",
}

#: Paquetes del propio proyecto que el dominio no puede depender.
PREFIJOS_PROHIBIDOS = (
    "modules.exams.api",
    "modules.exams.application",
    "modules.exams.infrastructure",
)


def archivos_del_dominio() -> list[Path]:
    return sorted(DOMINIO.glob("*.py"))


def imports_de(ruta: Path) -> list[str]:
    """Devuelve los módulos importados por un archivo (rutas absolutas)."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    modulos: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            modulos.append(nodo.module)
    return modulos


def test_el_dominio_tiene_modulos() -> None:
    assert archivos_del_dominio(), "el paquete de dominio está vacío"


@pytest.mark.parametrize("ruta", archivos_del_dominio(), ids=lambda ruta: ruta.name)
def test_el_dominio_no_importa_frameworks_ni_persistencia(ruta: Path) -> None:
    for modulo in imports_de(ruta):
        raiz = modulo.split(".")[0]
        assert raiz not in MODULOS_PROHIBIDOS, f"{ruta.name} importa {modulo}"
        assert not modulo.startswith(PREFIJOS_PROHIBIDOS), f"{ruta.name} importa {modulo}"


def test_importar_el_dominio_no_carga_fastapi() -> None:
    """El dominio puede importarse en un proceso sin web cargada."""
    codigo = (
        "import sys; import modules.exams.domain; "
        "cargados = [m for m in sys.modules if m.split('.')[0] in "
        "{'fastapi', 'sqlalchemy', 'pydantic', 'starlette'}]; "
        "assert not cargados, cargados"
    )
    entorno = {**os.environ, "PYTHONPATH": str(RAIZ / "src")}

    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        env=entorno,
        check=False,
    )

    assert resultado.returncode == 0, resultado.stderr
