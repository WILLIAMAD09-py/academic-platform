"""Bitácora de auditoría.

Registra las acciones relevantes del dominio (crear un examen, versionarlo,
generar claves, exportar) con el actor y el contexto de correlación.

La interfaz `AuditLog` permite sustituir el almacén en memoria por una tabla
de PostgreSQL en pasos posteriores sin tocar los servicios.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from core.logging import get_context

logger = logging.getLogger("core.audit")


def _ahora() -> datetime:
    """Marca de tiempo actual en UTC, con zona horaria explícita."""
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Acción registrada de forma inmutable."""

    id: str
    action: str
    entity_type: str
    entity_id: str | None
    actor: str
    payload: Mapping[str, Any]
    request_id: str | None
    exam_code: str | None
    created_at: datetime = field(default_factory=_ahora)


class AuditLog(Protocol):
    """Interfaz común de cualquier bitácora de auditoría."""

    async def record(
        self,
        action: str,
        *,
        entity_type: str,
        entity_id: str | None = None,
        actor: str = "system",
        payload: Mapping[str, Any] | None = None,
    ) -> AuditEvent:
        """Registra una acción y devuelve el evento creado."""
        ...

    async def history_for(self, entity_type: str, entity_id: str) -> list[AuditEvent]:
        """Devuelve el historial de una entidad, en orden de registro."""
        ...


class InMemoryAuditLog:
    """Bitácora en memoria (desarrollo, pruebas y base de la futura tabla)."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        """Eventos registrados, en orden de registro."""
        return tuple(self._events)

    async def record(
        self,
        action: str,
        *,
        entity_type: str,
        entity_id: str | None = None,
        actor: str = "system",
        payload: Mapping[str, Any] | None = None,
    ) -> AuditEvent:
        """Registra una acción; hereda `request_id` y `exam_code` del contexto."""
        contexto = get_context()
        evento = AuditEvent(
            id=uuid4().hex,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            payload=dict(payload or {}),
            request_id=contexto["request_id"],
            exam_code=contexto["exam_code"],
        )
        self._events.append(evento)
        logger.info(
            "auditoria.registrada",
            extra={"audit_action": action, "entity_type": entity_type, "entity_id": entity_id},
        )
        return evento

    async def history_for(self, entity_type: str, entity_id: str) -> list[AuditEvent]:
        """Historial de una entidad concreta."""
        return [
            evento
            for evento in self._events
            if evento.entity_type == entity_type and evento.entity_id == entity_id
        ]
