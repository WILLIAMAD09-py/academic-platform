"""Ejecución de trabajos en segundo plano.

`JobRunner` es la costura donde más adelante entrará una cola real (Celery o
RQ, sección 3 del prompt). La implementación actual es *inline*: ejecuta la
función en el proceso, pero con la misma interfaz, el mismo registro de estado
y la misma trazabilidad.

Ver `docs/ADR/0002-...` y la desviación A22 del `docs/ASSUMPTIONS.md`.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, TypeVar, runtime_checkable
from uuid import uuid4

logger = logging.getLogger("core.jobs")

T = TypeVar("T")


def _ahora() -> datetime:
    """Marca de tiempo actual en UTC, con zona horaria explícita."""
    return datetime.now(UTC)


class JobStatus(StrEnum):
    """Ciclo de vida de un trabajo."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Job[T]:
    """Traza inmutable de una ejecución."""

    id: str
    name: str
    status: JobStatus
    result: T | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=_ahora)
    started_at: datetime | None = None
    finished_at: datetime | None = None


@runtime_checkable
class JobRunner(Protocol):
    """Interfaz común de cualquier ejecutor de trabajos."""

    async def run(
        self,
        func: Callable[..., Awaitable[T]],
        /,
        *,
        name: str = "job",
        **kwargs: Any,
    ) -> Job[T]:
        """Ejecuta `func` y devuelve la traza del trabajo."""
        ...


class InlineJobRunner:
    """Ejecuta los trabajos en el mismo proceso, sin cola.

    Los argumentos se inyectan por nombre (`runner.run(fn, x=1)`), lo que evita
    acoplar la firma del trabajo a la del ejecutor.

    El registro de trabajos vive en memoria del proceso: con una cola real
    (Celery/RQ) el estado pasa a ser externo y este registro desaparece.
    """

    def __init__(self, *, job_id_factory: Callable[[], str] | None = None) -> None:
        self._job_id_factory = (
            job_id_factory if job_id_factory is not None else _nuevo_identificador
        )
        self._jobs: dict[str, Job[Any]] = {}

    @property
    def jobs(self) -> tuple[Job[Any], ...]:
        """Trabajos registrados, en orden de ejecución."""
        return tuple(self._jobs.values())

    def get(self, job_id: str) -> Job[Any] | None:
        """Devuelve el trabajo con ese identificador, si existe."""
        return self._jobs.get(job_id)

    async def run(
        self,
        func: Callable[..., Awaitable[T]],
        /,
        *,
        name: str = "job",
        **kwargs: Any,
    ) -> Job[T]:
        """Ejecuta `func` registrando su estado.

        Si la función falla, el trabajo queda registrado como `failed` y la
        excepción se propaga: el llamador decide qué hacer con el fallo.
        """
        job_id = self._job_id_factory()
        trabajo: Job[Any] = Job(
            id=job_id,
            name=name,
            status=JobStatus.RUNNING,
            started_at=_ahora(),
        )
        self._jobs[job_id] = trabajo

        try:
            resultado = await func(**kwargs)
        except Exception as error:
            fallido = replace(
                trabajo,
                status=JobStatus.FAILED,
                error=f"{type(error).__name__}: {error}",
                finished_at=_ahora(),
            )
            self._jobs[job_id] = fallido
            logger.exception("job.fallido", extra={"job_id": job_id, "job_name": name})
            raise

        completado = replace(
            trabajo,
            status=JobStatus.SUCCEEDED,
            result=resultado,
            finished_at=_ahora(),
        )
        self._jobs[job_id] = completado
        logger.info("job.completado", extra={"job_id": job_id, "job_name": name})
        return completado


def _nuevo_identificador() -> str:
    """Identificador único de trabajo."""
    return uuid4().hex
