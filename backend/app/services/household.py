"""The one Household Manager of a household (ADR 052)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.organization import Organization
from app.models.user import User, UserRole


async def transfer_manager(db: AsyncSession, to: User, by_name: str, by_id: uuid.UUID | None = None) -> User:
    """Swap the roles in one commit, so a household never has zero or two managers. Returns the old one."""
    if not await db.scalar(select(Organization.is_household)):
        raise ValueError("Only a household has a Household Manager.")
    managers = (await db.execute(select(User).where(
        User.role == UserRole.admin, User.is_active == True, User.is_deleted == False))).scalars().all()  # noqa: E712
    if len(managers) != 1:
        raise ValueError(f"Expected one Household Manager, found {len(managers)}.")
    old = managers[0]
    if to.id == old.id or not to.is_active or to.is_deleted:
        raise ValueError("Pick another active member.")
    old.role, to.role = UserRole.user, UserRole.admin
    db.add(AuditLog(timestamp=datetime.now(UTC), user_id=by_id, user_name=by_name, entity_type="User",
                    entity_id=str(to.id), action="manager_transferred", changes={"from": old.email, "to": to.email}))
    await db.commit()
    return old
