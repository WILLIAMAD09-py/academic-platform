"""Punto de entrada de la CLI de exámenes.

La CLI completa llega en el paso 11 de la Fase 1 (entregable 8 del prompt):

    python -m modules.exams.cli process --file tests/fixtures/examen_vc_ej26.json \
        --keys 2 --out ./output

Hasta entonces, este módulo existe para que el comando de consola `exams-cli`
(declarado en `pyproject.toml`) no quede apuntando a un módulo inexistente: si
se invoca, explica qué falta y con qué comando se ejecutará.
"""

from __future__ import annotations

import sys

MENSAGE_PENDIENTE = (
    "La CLI de exámenes se completa en el paso 11 de la Fase 1.\n"
    "Cuando exista, se ejecutará con:\n"
    "    python -m modules.exams.cli process --file <examen.json> --keys 2 --out ./output"
)


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de la consola `exams-cli`.

    Returns:
        Código de salida: 1 hasta que la CLI esté implementada.
    """
    argumentos = list(sys.argv[1:] if argv is None else argv)

    print(MENSAGE_PENDIENTE, file=sys.stderr)
    if argumentos:
        print(f"Argumentos recibidos (ignorados): {argumentos}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
