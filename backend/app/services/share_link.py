"""External document share links — token, access rules, and access auditing.

See docs/adr/021-external-document-share-links.md.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import resolve_patient_access
from app.models.audit import AuditLog
from app.models.patient import Patient
from app.models.access import PatientAccess
from app.models.share_link import DocumentShareLink, ShareLinkStatus
from app.models.user import User, UserRole

# Allowed link lifetimes (days). No "never" — GDPR storage limitation.
EXPIRY_CHOICES = {7, 30, 90}
_ACCESS_DEBOUNCE = timedelta(minutes=10)

_STAFF_ROLES = {UserRole.admin, UserRole.manager}


def generate_token() -> tuple[str, str]:
    """Return (plaintext_token, token_hash). Only the hash is ever persisted."""
    token = secrets.token_urlsafe(32)  # 256 bits
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def link_status(link: DocumentShareLink, now: datetime) -> str:
    """Effective status: revoked | expired | active."""
    if link.status == ShareLinkStatus.revoked:
        return "revoked"
    if link.expires_at <= now:
        return "expired"
    return "active"


async def _is_active_rep(patient_id: uuid.UUID, user: User, db: AsyncSession) -> bool:
    row = await db.execute(
        select(PatientAccess).where(
            PatientAccess.patient_id == patient_id,
            PatientAccess.user_id == user.id,
            PatientAccess.is_legal_representative == True,  # noqa: E712
            PatientAccess.revoked_at == None,  # noqa: E711
            PatientAccess.is_deleted == False,  # noqa: E712
        )
    )
    return row.first() is not None


async def require_share_management(patient_id: uuid.UUID, user: User, db: AsyncSession) -> bool:
    """Gate for creating/managing external share links (ADR-021, Regel X + exception).

    Outbound external sharing is a data-subject act, not a staff act:
    - No access at all -> 404.
    - Staff (admin/manager) who are NOT an active legal representative -> 403 (ADR 026).
    - Otherwise allowed.

    Returns ``created_legal`` (whether the user is an active legal representative).
    """
    level = await resolve_patient_access(patient_id, user, db)
    if level is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    is_rep = await _is_active_rep(patient_id, user, db)

    if user.role in _STAFF_ROLES and not is_rep:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="External sharing is reserved for a patient's caregivers or legal representatives, not staff.",
        )
    return is_rep


async def log_share_access(
    db: AsyncSession,
    link_id: uuid.UUID,
    document_id: uuid.UUID | None,
    event: str,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    """Record an anonymous external access, debounced per (link, document, event).

    A PDF viewer issues many range requests; without debouncing the audit log
    would flood. One entry per link+document+event per ~10 minutes.
    """
    now = datetime.now(UTC)
    cutoff = now - _ACCESS_DEBOUNCE
    doc_str = str(document_id) if document_id else None

    recent = await db.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "DocumentShareLink",
            AuditLog.entity_id == str(link_id),
            AuditLog.action == "accessed",
            AuditLog.timestamp >= cutoff,
        )
    )
    for row in recent.scalars():
        ch = row.changes or {}
        if ch.get("document_id") == doc_str and ch.get("event") == event:
            return  # within debounce window — skip

    db.add(AuditLog(
        timestamp=now,
        user_id=None,
        user_name="External via share link",
        entity_type="DocumentShareLink",
        entity_id=str(link_id),
        action="accessed",
        changes={"document_id": doc_str, "event": event},
        ip_address=ip_address,
        user_agent=user_agent,
    ))
