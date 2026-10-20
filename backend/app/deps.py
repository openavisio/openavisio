"""FastAPI dependency injection."""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole

bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") == "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id), User.is_deleted == False))  # noqa: E712
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user


def require_role(*roles: UserRole):
    async def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        return user

    return dep


require_admin = require_role(UserRole.admin)


async def operator_only() -> None:
    """The routes behind it belong to whoever runs the instance. On a hosted Deployment that is
    the operator, not the customer, so nobody who logs in may use them."""
    if settings.hosted:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Managed by the operator of this instance")
require_manager = require_role(UserRole.admin, UserRole.manager)


def patient_access_dep(minimum: AccessLevel = AccessLevel.view):
    async def dep(
        patient_id: uuid.UUID,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        await require_patient_access(patient_id, user, db, minimum)
        return user

    return dep
