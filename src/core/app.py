"""Fábrica de la aplicación FastAPI.

Este módulo es el punto de entrada que ejecuta el `Dockerfile`
(`uvicorn core.app:app`) y el que sirve el endpoint `/health` que comprueba el
`HEALTHCHECK` del contenedor.

El núcleo completo (configuración, base de datos, logging estructurado, errores,
trabajos y auditoría) se incorpora en el paso 2. Aquí se deja únicamente la
fábrica y la ruta de salud, que es lo mínimo para que la imagen sea ejecutable
y verificable de extremo a extremo.
"""

from __future__ import annotations

from fastapi import FastAPI

from core import __version__


def create_app() -> FastAPI:
    """Crea la instancia de la aplicación con sus rutas básicas."""
    app = FastAPI(
        title="Plataforma de Automatización Académica",
        version=__version__,
    )

    @app.get("/health", tags=["sistema"], summary="Comprobación de disponibilidad")
    def health() -> dict[str, str]:
        """Responde 200 mientras el proceso sea capaz de atender peticiones."""
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
