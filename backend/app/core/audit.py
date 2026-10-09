"""SQLAlchemy event-based audit logging."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import event, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.base import BaseModel

_SKIP_TYPES = {"AuditLog", "SystemSetting"}
_SKIP_ATTRS = {"hashed_password", "failed_login_attempts", "locked_until"}


def _entity_type(instance) -> str:
    return type(instance).__name__


def _entity_id(instance) -> str | None:
    pk = inspect(instance).identity
    return str(pk[0]) if pk else None


def _changed_attrs(instance) -> dict:
    changes = {}
    state = inspect(instance)
    for attr in state.attrs:
        hist = attr.history
        if hist.has_changes() and attr.key not in _SKIP_ATTRS:
            old = hist.deleted[0] if hist.deleted else None
            new = hist.added[0] if hist.added else None
            if old != new:
                changes[attr.key] = {"old": str(old) if old is not None else None, "new": str(new) if new is not None else None}
    return changes


async def _write_audit(session: AsyncSession, action: str, entity_type: str, entity_id: str | None, changes: dict | None, user_id: uuid.UUID | None, user_name: str | None) -> None:
    log = AuditLog(
        timestamp=datetime.now(UTC),
        user_id=user_id,
        user_name=user_name,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changes=changes,
    )
    session.add(log)


def setup_audit_listeners(session_factory) -> None:
    """Wire up SQLAlchemy session events for audit logging."""
    # Audit is written inline in services via the audit_event helper for now.
    # Full automatic interception can be added here if desired.
    pass
