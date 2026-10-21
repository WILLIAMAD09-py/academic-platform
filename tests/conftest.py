"""Configuración compartida de pytest.

Añade ``src`` al ``sys.path`` para que la suite pueda ejecutarse incluso sin
haber instalado el paquete en modo editable. Si el paquete está instalado, la
ruta ya está presente y esto es un no-op.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"

if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Convierte "no se recolectó ningún test" en salida exitosa.

    Sin este hook, pytest termina con código 5 (``NO_TESTS_COLLECTED``) cuando
    el repositorio todavía no tiene pruebas, lo que hace que un ``pytest`` en
    verde sobre un proyecto vacío se vea como error en CI. El objetivo es que
    ``pytest`` pase siempre que no haya tests que fallen.
    """
    if exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK
