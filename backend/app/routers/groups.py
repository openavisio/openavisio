import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user, require_manager
from app.models.group import Group, GroupInviteToken, GroupMembership
from app.models.patient import Patient
from app.models.user import User
from app.schemas.group import (
    AssignPatientToGroupRequest,
    GroupCreateRequest,
    GroupDto,
    GroupInviteInfoDto,
    GroupInviteRequest,
    GroupInviteResult,
    GroupMemberDto,
    GroupPatientDto,
    GroupUpdateRequest,
    UpdateMemberRoleRequest,
)

router = APIRouter()

_GROUP_MANAGERS = ("owner", "manager")


async def _member_group(group_id: uuid.UUID, user: User, db: AsyncSession, roles: tuple[str, ...] | None = None):
    """(group, caller's role), if the caller is an active member (with one of `roles`); 404 otherwise. ADR 025."""
    row = (await db.execute(
        select(Group, GroupMembership.role)
        .join(GroupMembership, GroupMembership.group_id == Group.id)
        .where(
            Group.id == group_id,
            Group.is_deleted == False,  # noqa: E712
            GroupMembership.user_id == user.id,
            GroupMembership.status == "active",
            GroupMembership.is_deleted == False,  # noqa: E712
        )
    )).first()
    if not row or (roles and row.role not in roles):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return row.Group, row.role


@router.get("/groups", response_model=list[GroupDto])
async def list_groups(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Group).where(Group.is_deleted == False))  # noqa: E712
    all_g = result.scalars().all()
    mine = []
    for g in all_g:
        if g.owner_id == user.id:
            mine.append(g)
            continue
        mem = await db.execute(select(GroupMembership).where(
            GroupMembership.group_id == g.id,
            GroupMembership.user_id == user.id,
            GroupMembership.status == "active",
        ))
        if mem.scalar_one_or_none():
            mine.append(g)
    return mine


@router.post("/groups", response_model=GroupDto, status_code=status.HTTP_201_CREATED)
async def create_group(body: GroupCreateRequest, user: User = Depends(require_manager), db: AsyncSession = Depends(get_db)):
    group = Group(name=body.name, owner_id=user.id)
    db.add(group)
    await db.flush()
    mem = GroupMembership(group_id=group.id, user_id=user.id, role="owner", status="active", invited_at=datetime.now(UTC), accepted_at=datetime.now(UTC))
    db.add(mem)
    await db.commit()
    await db.refresh(group)
    return group


@router.get("/groups/{group_id}", response_model=GroupDto)
async def get_group(group_id: uuid.UUID, user: User = Depends(require_manager), db: AsyncSession = Depends(get_db)):
    group, _ = await _member_group(group_id, user, db)
    return group


@router.put("/groups/{group_id}", response_model=GroupDto)
async def update_group(group_id: uuid.UUID, body: GroupUpdateRequest, user: User = Depends(require_manager), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Group).where(Group.id == group_id, Group.is_deleted == False))  # noqa: E712
    group = result.scalar_one_or_none()
    if not group or group.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    group.name = body.name
    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: uuid.UUID, user: User = Depends(require_manager), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Group).where(Group.id == group_id, Group.is_deleted == False))  # noqa: E712
    group = result.scalar_one_or_none()
    if not group or group.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    group.is_deleted = True
    await db.commit()


@router.get("/groups/{group_id}/members", response_model=list[GroupMemberDto])
async def list_members(group_id: uuid.UUID, user: User = Depends(require_manager), db: AsyncSession = Depends(get_db)):
    await _member_group(group_id, user, db)
    rows = (await db.execute(
        select(GroupMembership, User.email)
        .join(User, User.id == GroupMembership.user_id)
        .where(
            GroupMembership.group_id == group_id,
            GroupMembership.is_deleted == False,  # noqa: E712
        )
    )).all()
    return [
        GroupMemberDto(
            id=m.id, group_id=m.group_id, user_id=m.user_id, user_email=email,
            role=m.role, status=m.status, invited_at=m.invited_at, accepted_at=m.accepted_at,
        )
        for m, email in rows
    ]


@router.post("/groups/{group_id}/members/invite", response_model=GroupInviteResult, status_code=status.HTTP_201_CREATED)
async def invite_member(group_id: uuid.UUID, body: GroupInviteRequest, user: User = Depends(require_manager), db: AsyncSession = Depends(get_db)):
    _, my_role = await _member_group(group_id, user, db, _GROUP_MANAGERS)
    if body.role == "owner" and my_role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an owner can grant or change the owner role")
    token = secrets.token_urlsafe(32)
    invite = GroupInviteToken(group_id=group_id, email=body.email, role=body.role, token=token, expires_at=datetime.now(UTC) + timedelta(days=7))
    db.add(invite)
    await db.commit()
    return GroupInviteResult(token=token, invite_url=f"/group/accept-invite?token={token}")


@router.get("/groups/invite/info", response_model=GroupInviteInfoDto)
async def get_invite_info(token: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    invite = (await db.execute(select(GroupInviteToken).where(GroupInviteToken.token == token))).scalar_one_or_none()
    if not invite or invite.is_used or invite.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
    group = (await db.execute(select(Group).where(Group.id == invite.group_id))).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return GroupInviteInfoDto(group_id=group.id, group_name=group.name)


@router.post("/groups/invite/accept")
async def accept_invite(token: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    invite = (await db.execute(select(GroupInviteToken).where(GroupInviteToken.token == token))).scalar_one_or_none()
    if not invite or invite.is_used or invite.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
    if (invite.email or "").lower() != user.email.lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This invitation was sent to another address")
    existing = (await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id == invite.group_id,
            GroupMembership.user_id == user.id,
            GroupMembership.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not existing:
        mem = GroupMembership(
            group_id=invite.group_id, user_id=user.id, role=invite.role, status="active",
            invited_at=invite.expires_at, accepted_at=datetime.now(UTC),
        )
        db.add(mem)
    invite.is_used = True
    await db.commit()
    return {"group_id": str(invite.group_id)}


@router.delete("/groups/{group_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(group_id: uuid.UUID, membership_id: uuid.UUID, user: User = Depends(require_manager), db: AsyncSession = Depends(get_db)):
    _, my_role = await _member_group(group_id, user, db, _GROUP_MANAGERS)
    result = await db.execute(select(GroupMembership).where(GroupMembership.id == membership_id, GroupMembership.group_id == group_id))
    mem = result.scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if mem.role == "owner" and my_role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an owner can remove an owner")
    mem.is_deleted = True
    await db.commit()


@router.put("/groups/{group_id}/members/{membership_id}/role")
async def update_member_role(group_id: uuid.UUID, membership_id: uuid.UUID, body: UpdateMemberRoleRequest, user: User = Depends(require_manager), db: AsyncSession = Depends(get_db)):
    _, my_role = await _member_group(group_id, user, db, _GROUP_MANAGERS)
    result = await db.execute(select(GroupMembership).where(GroupMembership.id == membership_id, GroupMembership.group_id == group_id))
    mem = result.scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if "owner" in (mem.role, body.role) and my_role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an owner can grant or change the owner role")
    mem.role = body.role
    await db.commit()
    return {"ok": True}


@router.get("/groups/{group_id}/patients", response_model=list[GroupPatientDto])
async def list_group_patients(group_id: uuid.UUID, user: User = Depends(require_manager), db: AsyncSession = Depends(get_db)):
    await _member_group(group_id, user, db)
    result = await db.execute(select(Patient).where(Patient.group_id == group_id, Patient.is_deleted == False))  # noqa: E712
    return result.scalars().all()


@router.post("/patients/{patient_id}/group")
async def assign_patient_to_group(patient_id: uuid.UUID, body: AssignPatientToGroupRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Patient).where(Patient.id == patient_id, Patient.is_deleted == False))  # noqa: E712
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(patient_id, user, db, AccessLevel.admin)
    patient.group_id = body.group_id
    await db.commit()
    return {"ok": True}


@router.delete("/patients/{patient_id}/group", status_code=status.HTTP_204_NO_CONTENT)
async def remove_patient_from_group(patient_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Patient).where(Patient.id == patient_id, Patient.is_deleted == False))  # noqa: E712
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(patient_id, user, db, AccessLevel.admin)
    patient.group_id = None
    await db.commit()
