"""
Audit log writer — call write_audit() from any API endpoint to persist
an immutable audit record. Fire-and-forget: never raises, never blocks.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def write_audit(
    db: AsyncSession,
    action: str,
    resource_type: str,
    *,
    user_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
    audit_status: str = "success",
) -> None:
    """Write a single audit log entry. Silently swallows errors."""
    try:
        log = AuditLog(
            action=action,
            resource_type=resource_type,
            user_id=user_id,
            organization_id=organization_id,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            log_metadata=metadata or {},
            status=audit_status,
        )
        db.add(log)
        # No flush — the caller's transaction commits it together with the main operation
    except Exception:
        pass  # audit failure must never break the primary request
