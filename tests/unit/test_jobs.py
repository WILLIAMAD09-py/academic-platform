"""Pruebas del ejecutor de trabajos (`core.jobs`).

El `JobRunner` es la costura donde más adelante entrará Celery o RQ (sección 3 del prompt).
Hoy solo existe la implementación inline: misma ejecución, sin cola.
"""

from __future__ import annotations

import pytest

from core.jobs import InlineJobRunner, JobRunner, JobStatus


async def _trabajo_ok() -> str:
    return "resultado"


async def _trabajo_falla() -> None:
    raise RuntimeError("fallo intentional")


async def test_el_trabajo_termina_en_estado_exitoso() -> None:
    runner = InlineJobRunner()

    job = await runner.run(_trabajo_ok, name="proceso")

    assert job.status is JobStatus.SUCCEEDED
    assert job.result == "resultado"
    assert job.error is None
    assert job.name == "proceso"
    assert job.started_at is not None
    assert job.finished_at is not None


async def test_el_trabajo_fallido_se_registra_y_el_error_se_propaga() -> None:
    runner = InlineJobRunner()

    with pytest.raises(RuntimeError, match="fallo intentional"):
        await runner.run(_trabajo_falla, name="proceso-roto")

    (job,) = runner.jobs
    assert job.status is JobStatus.FAILED
    assert job.error is not None
    assert "fallo intentional" in job.error


async def test_los_argumentos_llegan_al_trabajo() -> None:
    async def sumar(a: int, b: int = 0) -> int:
        return a + b

    runner = InlineJobRunner()

    job = await runner.run(sumar, name="suma", a=2, b=3)

    assert job.result == 5


async def test_los_trabajos_se_pueden_consultar_por_identificador() -> None:
    runner = InlineJobRunner(job_id_factory=lambda: "job-fijo")

    job = await runner.run(_trabajo_ok)

    registrado = runner.get("job-fijo")
    assert registrado is not None
    assert registrado.id == job.id
    assert runner.get("no-existe") is None


async def test_el_identificador_se_puede_inyectar_para_pruebas() -> None:
    runner = InlineJobRunner(job_id_factory=lambda: "abc-123")

    job = await runner.run(_trabajo_ok)

    assert job.id == "abc-123"


def test_el_runner_inline_cumple_el_protocolo() -> None:
    """La interfaz no depende de la implementación: sustituirla por Celery no cambia `application`."""
    runner: JobRunner = InlineJobRunner()

    assert isinstance(runner, JobRunner)
