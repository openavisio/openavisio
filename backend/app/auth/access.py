"""Patient row-level access control — mirrors C# PatientAccessService."""

import uuid
from datetime import UTC, datetime
from enum import IntEnum

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import PatientAccess
from app.models.group import GroupMembership
from app.models.patient import Patient
from app.models.user import User


class AccessLevel(IntEnum):
    view = 1
    contribute = 2
    full = 3
    admin = 4


_LEVEL_MAP = {
    "view": AccessLevel.view,
    "contribute": AccessLevel.contribute,
    "full": AccessLevel.full,
    "admin": AccessLevel.admin,
}

_FAMILY_ROLE_LEVEL = {
    "viewer": AccessLevel.view,
    "editor": AccessLevel.contribute,
    "admin": AccessLevel.full,
    "owner": AccessLevel.admin,
}


async def resolve_patient_access(
    patient_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> AccessLevel | None:
    """Return the effective access level, or None. No role or creator bypass (ADR 025/026)."""
    # Group membership
    result = await db.execute(
        select(GroupMembership).join(Patient, Patient.group_id == GroupMembership.group_id).where(
            Patient.id == patient_id,
            GroupMembership.user_id == user.id,
            GroupMembership.status == "active",
            GroupMembership.is_deleted == False,  # noqa: E712
        )
    )
    membership = result.scalar_one_or_none()
    if membership:
        return _FAMILY_ROLE_LEVEL.get(membership.role, AccessLevel.view)

    # Direct grant
    now = datetime.now(UTC)
    result = await db.execute(
        select(PatientAccess).where(
            PatientAccess.patient_id == patient_id,
            PatientAccess.user_id == user.id,
            PatientAccess.revoked_at == None,  # noqa: E711
        )
    )
    grant = result.scalar_one_or_none()
    if grant:
        if grant.expires_at and grant.expires_at < now:
            return None
        return _LEVEL_MAP.get(grant.access_level, AccessLevel.view)

    return None


async def require_patient_access(
    patient_id: uuid.UUID,
    user: User,
    db: AsyncSession,
    minimum: AccessLevel = AccessLevel.view,
) -> None:
    level = await resolve_patient_access(patient_id, user, db)
    if level is None or level < minimum:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
