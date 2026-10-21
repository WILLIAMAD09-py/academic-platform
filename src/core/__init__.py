"""Núcleo compartido de la plataforma de automatización académica.

Reúne las piezas reutilizables por todos los módulos: configuración, acceso a
datos, logging, errores, auditoría, cola de trabajos y utilidades de
documentos. No debe importar nada de `modules`.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
