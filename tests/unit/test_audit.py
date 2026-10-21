"""Pruebas de la bitácora de auditoría (`core.audit`)."""

from __future__ import annotations

from core.audit import InMemoryAuditLog
from core.logging import context_scope


async def test_registra_un_evento_con_sus_campos() -> None:
    auditoria = InMemoryAuditLog()

    evento = await auditoria.record(
        "exam.submitted",
        entity_type="exam",
        entity_id="e-1",
        actor="docente",
        payload={"exam_code": "21643"},
    )

    assert evento.action == "exam.submitted"
    assert evento.entity_type == "exam"
    assert evento.entity_id == "e-1"
    assert evento.actor == "docente"
    assert evento.payload == {"exam_code": "21643"}
    assert evento.id
    assert evento.created_at is not None


async def test_los_eventos_se_conservan_en_orden() -> None:
    auditoria = InMemoryAuditLog()

    await auditoria.record("primero", entity_type="exam", entity_id="e-1")
    await auditoria.record("segundo", entity_type="exam", entity_id="e-1")

    acciones = [evento.action for evento in auditoria.events]

    assert acciones == ["primero", "segundo"]


async def test_se_puede_consultar_el_historial_de_una_entidad() -> None:
    auditoria = InMemoryAuditLog()

    await auditoria.record("a", entity_type="exam", entity_id="e-1")
    await auditoria.record("b", entity_type="exam", entity_id="e-2")
    await auditoria.record("c", entity_type="exam", entity_id="e-1")

    historial = await auditoria.history_for("exam", "e-1")

    assert [evento.action for evento in historial] == ["a", "c"]


async def test_el_evento_hereda_el_request_id_del_contexto() -> None:
    auditoria = InMemoryAuditLog()

    with context_scope(request_id="r-77", exam_code="21643"):
        evento = await auditoria.record("accion", entity_type="exam", entity_id="e-1")

    assert evento.request_id == "r-77"
    assert evento.exam_code == "21643"


async def test_el_actor_por_defecto_es_el_sistema() -> None:
    auditoria = InMemoryAuditLog()

    evento = await auditoria.record("accion", entity_type="exam")

    assert evento.actor == "system"
    assert evento.entity_id is None
