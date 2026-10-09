import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user, require_manager
from app.models.access import PatientAccess, PatientCaregiverInvite
from app.models.group import Group, GroupMembership
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.system import UserInvitation
from app.models.user import User

router = APIRouter()


class DirectoryUserDto(BaseModel):
    email: str
    name: str | None = None


@router.get("/users/directory", response_model=list[DirectoryUserDto])
async def user_directory(user: User = Depends(require_manager), db: AsyncSession = Depends(get_db)):
    """Active users, for the access-grant picker (staff only)."""
    rows = (await db.execute(
        select(User).where(User.is_active == True, User.is_deleted == False)  # noqa: E712
    )).scalars().all()
    return [
        DirectoryUserDto(email=u.email, name=" ".join(filter(None, [u.first_name, u.last_name])) or None)
        for u in rows
    ]


class GrantAccessRequest(BaseModel):
    email: EmailStr
    access_level: str = "view"
    expires_at: datetime | None = None
    purpose: str | None = None
    relationship: str | None = None
    is_legal_representative: bool = False


class UpdateAccessRequest(BaseModel):
    access_level: str | None = None
    expires_at: datetime | None = None
    purpose: str | None = None
    relationship: str | None = None
    is_legal_representative: bool | None = None


class CaregiverDto(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    source: str  # "direct" | "group"
    access_level: str | None = None
    granted_at: datetime | None = None
    expires_at: datetime | None = None
    purpose: str | None = None
    relationship: str | None = None
    is_legal_representative: bool = False
    group_id: uuid.UUID | None = None
    group_name: str | None = None
    group_role: str | None = None



async def _other_admin_grant_exists(db: AsyncSession, patient_id: uuid.UUID, grant_id: uuid.UUID) -> bool:
    row = await db.execute(
        select(PatientAccess.id).where(
            PatientAccess.patient_id == patient_id,
            PatientAccess.id != grant_id,
            PatientAccess.access_level == "admin",
            PatientAccess.revoked_at == None,  # noqa: E711
            PatientAccess.is_deleted == False,  # noqa: E712
        )
    )
    return row.first() is not None


@router.get("/patients/{patient_id}/access", response_model=list[CaregiverDto])
async def list_access_grants(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.full)

    # Direct grants
    direct_rows = (await db.execute(
        select(PatientAccess, User.email)
        .join(User, User.id == PatientAccess.user_id)
        .where(
            PatientAccess.patient_id == patient_id,
            PatientAccess.revoked_at == None,  # noqa: E711
            PatientAccess.is_deleted == False,  # noqa: E712
        )
    )).all()

    caregivers: list[CaregiverDto] = [
        CaregiverDto(
            id=g.id,
            user_id=g.user_id,
            user_email=email,
            source="direct",
            access_level=g.access_level,
            granted_at=g.granted_at,
            expires_at=g.expires_at,
            purpose=g.purpose,
            relationship=g.relationship,
            is_legal_representative=g.is_legal_representative,
        )
        for g, email in direct_rows
    ]

    # Group-derived: find the patient's group and include all active members
    patient = (await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()

    if patient and patient.group_id:
        group = (await db.execute(
            select(Group).where(Group.id == patient.group_id, Group.is_deleted == False)  # noqa: E712
        )).scalar_one_or_none()

        if group:
            group_rows = (await db.execute(
                select(GroupMembership, User.email)
                .join(User, User.id == GroupMembership.user_id)
                .where(
                    GroupMembership.group_id == group.id,
                    GroupMembership.status == "active",
                    GroupMembership.is_deleted == False,  # noqa: E712
                )
            )).all()

            direct_user_ids = {g.user_id for g, _ in direct_rows}
            for mem, email in group_rows:
                if mem.user_id not in direct_user_ids:
                    caregivers.append(CaregiverDto(
                        id=mem.id,
                        user_id=mem.user_id,
                        user_email=email,
                        source="group",
                        group_id=group.id,
                        group_name=group.name,
                        group_role=mem.role,
                    ))

    return caregivers


@router.post("/patients/{patient_id}/access", response_model=CaregiverDto, status_code=201)
async def grant_access(
    patient_id: uuid.UUID,
    body: GrantAccessRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    minimum = AccessLevel.admin if body.access_level == "admin" else AccessLevel.full
    await require_patient_access(patient_id, user, db, minimum)

    valid_levels = ("view", "contribute", "full", "admin")
    if body.access_level not in valid_levels:
        raise HTTPException(status_code=400, detail=f"Invalid access level. Choose from: {', '.join(valid_levels)}")

    target = (await db.execute(select(User).where(User.email == body.email, User.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not target:
        raise HTTPException(status_code=404, detail=f"No user found with email: {body.email}")

    # Check for existing active grant
    existing = (await db.execute(
        select(PatientAccess).where(
            PatientAccess.patient_id == patient_id,
            PatientAccess.user_id == target.id,
            PatientAccess.revoked_at == None,  # noqa: E711
            PatientAccess.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="This user already has an active access grant.")

    grant = PatientAccess(
        patient_id=patient_id,
        user_id=target.id,
        access_level=body.access_level,
        granted_by_user_id=user.id,
        granted_at=datetime.now(UTC),
        expires_at=body.expires_at,
        purpose=body.purpose,
        relationship=body.relationship,
        is_legal_representative=body.is_legal_representative,
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)

    from app.services.email import send_caregiver_added_notification
    background_tasks.add_task(send_caregiver_added_notification, str(patient_id), str(target.id))

    return CaregiverDto(
        id=grant.id,
        user_id=grant.user_id,
        user_email=target.email,
        source="direct",
        access_level=grant.access_level,
        granted_at=grant.granted_at,
        expires_at=grant.expires_at,
        purpose=grant.purpose,
        relationship=grant.relationship,
        is_legal_representative=grant.is_legal_representative,
    )


@router.patch("/access/{grant_id}")
async def update_access(
    grant_id: uuid.UUID,
    body: UpdateAccessRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    grant = (await db.execute(
        select(PatientAccess).where(PatientAccess.id == grant_id, PatientAccess.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not grant:
        raise HTTPException(status_code=404)
    await require_patient_access(grant.patient_id, user, db, AccessLevel.full)
    if "access_level" in body.model_fields_set and body.access_level:
        if body.access_level not in ("view", "contribute", "full", "admin"):
            raise HTTPException(status_code=400, detail="Invalid access level.")
        if body.access_level == "admin":
            await require_patient_access(grant.patient_id, user, db, AccessLevel.admin)
        if grant.access_level == "admin" and body.access_level != "admin" \
                and not await _other_admin_grant_exists(db, grant.patient_id, grant.id):
            raise HTTPException(status_code=409, detail="Cannot downgrade the last admin-level grant of a patient.")
        grant.access_level = body.access_level
    if "expires_at" in body.model_fields_set:
        grant.expires_at = body.expires_at
    if "purpose" in body.model_fields_set:
        grant.purpose = body.purpose
    if "relationship" in body.model_fields_set:
        grant.relationship = body.relationship
    if body.is_legal_representative is not None:
        grant.is_legal_representative = body.is_legal_representative
    await db.commit()
    return {"ok": True}


@router.delete("/access/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_access(
    grant_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    grant = (await db.execute(
        select(PatientAccess).where(PatientAccess.id == grant_id, PatientAccess.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not grant:
        raise HTTPException(status_code=404)
    await require_patient_access(grant.patient_id, user, db, AccessLevel.full)
    if grant.access_level == "admin" and not await _other_admin_grant_exists(db, grant.patient_id, grant.id):
        raise HTTPException(status_code=409, detail="Cannot revoke the last admin-level grant of a patient.")
    grant.revoked_at = datetime.now(UTC)
    await db.commit()


# ── Caregiver invite ─────────────────────────────────────────────────────────

class CaregiverInviteRequest(BaseModel):
    email: EmailStr | None = None
    access_level: str = "view"


class CaregiverInviteResult(BaseModel):
    token: str
    invite_url: str
    registration_url: str | None = None


class CaregiverInviteInfo(BaseModel):
    patient_given_name: str
    patient_family_name: str
    org_name: str
    access_level: str


@router.post("/patients/{patient_id}/caregiver-invite", response_model=CaregiverInviteResult, status_code=201)
async def create_caregiver_invite(
    patient_id: uuid.UUID,
    body: CaregiverInviteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    minimum = AccessLevel.admin if body.access_level == "admin" else AccessLevel.full
    await require_patient_access(patient_id, user, db, minimum)

    valid_levels = ("view", "contribute", "full", "admin")
    if body.access_level not in valid_levels:
        raise HTTPException(status_code=400, detail=f"Invalid access level. Choose from: {', '.join(valid_levels)}")

    token = secrets.token_urlsafe(32)
    invite = PatientCaregiverInvite(
        patient_id=patient_id,
        invited_email=body.email,
        access_level=body.access_level,
        invited_by_user_id=user.id,
        token=token,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(invite)

    registration_url: str | None = None
    if body.email:
        existing_user = (await db.execute(
            select(User).where(User.email == body.email, User.is_deleted == False)  # noqa: E712
        )).scalar_one_or_none()
        if not existing_user:
            sys_token = secrets.token_urlsafe(32)
            sys_invite = UserInvitation(
                email=body.email,
                token=sys_token,
                expires_at=datetime.now(UTC) + timedelta(days=7),
                created_by_user_id=user.id,
            )
            db.add(sys_invite)
            registration_url = f"/register?token={sys_token}"

    await db.commit()
    return CaregiverInviteResult(
        token=token,
        invite_url=f"/patients/invite?token={token}",
        registration_url=registration_url,
    )


@router.get("/patients/caregiver-invite/info", response_model=CaregiverInviteInfo)
async def get_caregiver_invite_info(token: str, db: AsyncSession = Depends(get_db)):
    invite = (await db.execute(
        select(PatientCaregiverInvite).where(PatientCaregiverInvite.token == token)
    )).scalar_one_or_none()
    if not invite or invite.is_used or invite.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=400, detail="Invalid or expired invite token")

    patient = (await db.execute(
        select(Patient).where(Patient.id == invite.patient_id, Patient.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404)

    org = (await db.execute(select(Organization))).scalar_one_or_none()
    org_name = org.name if org else "OpenAvisio"

    return CaregiverInviteInfo(
        patient_given_name=patient.given_name,
        patient_family_name=patient.family_name,
        org_name=org_name,
        access_level=invite.access_level,
    )


@router.post("/patients/caregiver-invite/accept")
async def accept_caregiver_invite(
    token: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    invite = (await db.execute(
        select(PatientCaregiverInvite).where(PatientCaregiverInvite.token == token)
    )).scalar_one_or_none()
    if not invite or invite.is_used or invite.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=400, detail="Invalid or expired invite token")

    if invite.invited_email and invite.invited_email.lower() != user.email.lower():
        raise HTTPException(status_code=403, detail="Invite was issued to a different email")

    existing = (await db.execute(
        select(PatientAccess).where(
            PatientAccess.patient_id == invite.patient_id,
            PatientAccess.user_id == user.id,
            PatientAccess.revoked_at == None,  # noqa: E711
            PatientAccess.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not existing:
        grant = PatientAccess(
            patient_id=invite.patient_id,
            user_id=user.id,
            access_level=invite.access_level,
            granted_by_user_id=invite.invited_by_user_id,
            granted_at=datetime.now(UTC),
        )
        db.add(grant)

    invite.is_used = True
    await db.commit()
    return {"patient_id": str(invite.patient_id)}
