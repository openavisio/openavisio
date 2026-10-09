from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, resolve_patient_access
from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.group import Group, GroupMembership
from app.models.patient import Patient
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_user(db: AsyncSession, email: str, role: str = "user") -> User:
    user = User(email=email, hashed_password=hash_password("Password1!"), role=role, is_active=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _create_patient(db: AsyncSession, owner: User) -> Patient:
    p = Patient(created_by=owner.id, given_name="Test", family_name="Patient")
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=owner.id, access_level="admin",
                         granted_by_user_id=owner.id, granted_at=datetime.now(UTC)))
    await db.commit()
    return p


async def _create_group_membership(
    db: AsyncSession,
    patient: Patient,
    user: User,
    role: str,
) -> None:
    group = Group(name="Test Group", owner_id=user.id)
    db.add(group)
    await db.flush()

    patient.group_id = group.id
    await db.flush()

    mem = GroupMembership(
        group_id=group.id,
        user_id=user.id,
        role=role,
        status="active",
        invited_at=datetime.now(UTC),
        accepted_at=datetime.now(UTC),
    )
    db.add(mem)
    await db.commit()
    await db.refresh(patient)


async def _create_access_grant(
    db: AsyncSession,
    patient: Patient,
    user: User,
    level: str = "view",
    expires_at: datetime | None = None,
) -> PatientAccess:
    grant = PatientAccess(
        patient_id=patient.id,
        user_id=user.id,
        access_level=level,
        granted_by_user_id=patient.created_by,
        granted_at=datetime.now(UTC),
        expires_at=expires_at,
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    return grant


# ---------------------------------------------------------------------------
# Admin role
# ---------------------------------------------------------------------------

async def test_admin_role_has_no_blanket_access(db: AsyncSession):
    # ADR 025: the admin role administers the system, not patient records
    admin = await _create_user(db, "admin_acc@test.com", role="admin")
    owner = await _create_user(db, "owner_acc@test.com", role="admin")
    patient = await _create_patient(db, owner)

    level = await resolve_patient_access(patient.id, admin, db)
    assert level is None


# ---------------------------------------------------------------------------
# Patient ownership
# ---------------------------------------------------------------------------

async def test_patient_owner_returns_admin_level(db: AsyncSession):
    owner = await _create_user(db, "owner_own@test.com", role="user")
    patient = await _create_patient(db, owner)

    level = await resolve_patient_access(patient.id, owner, db)
    assert level == AccessLevel.admin


# ---------------------------------------------------------------------------
# Group membership role mapping
# ---------------------------------------------------------------------------

async def test_group_membership_viewer_returns_view(db: AsyncSession):
    owner = await _create_user(db, "owner_gmv@test.com", role="admin")
    member = await _create_user(db, "member_gmv@test.com", role="user")
    patient = await _create_patient(db, owner)
    await _create_group_membership(db, patient, member, role="viewer")

    level = await resolve_patient_access(patient.id, member, db)
    assert level == AccessLevel.view


async def test_group_membership_editor_returns_contribute(db: AsyncSession):
    owner = await _create_user(db, "owner_gme@test.com", role="admin")
    member = await _create_user(db, "member_gme@test.com", role="user")
    patient = await _create_patient(db, owner)
    await _create_group_membership(db, patient, member, role="editor")

    level = await resolve_patient_access(patient.id, member, db)
    assert level == AccessLevel.contribute


async def test_group_membership_admin_returns_full(db: AsyncSession):
    owner = await _create_user(db, "owner_gma@test.com", role="admin")
    member = await _create_user(db, "member_gma@test.com", role="user")
    patient = await _create_patient(db, owner)
    await _create_group_membership(db, patient, member, role="admin")

    level = await resolve_patient_access(patient.id, member, db)
    assert level == AccessLevel.full


async def test_group_membership_owner_returns_admin(db: AsyncSession):
    owner = await _create_user(db, "owner_gmo@test.com", role="admin")
    member = await _create_user(db, "member_gmo@test.com", role="user")
    patient = await _create_patient(db, owner)
    await _create_group_membership(db, patient, member, role="owner")

    level = await resolve_patient_access(patient.id, member, db)
    assert level == AccessLevel.admin


# ---------------------------------------------------------------------------
# Direct PatientAccess grants
# ---------------------------------------------------------------------------

async def test_direct_grant_view_returns_view(db: AsyncSession):
    owner = await _create_user(db, "owner_dgv@test.com", role="admin")
    grantee = await _create_user(db, "grantee_dgv@test.com", role="user")
    patient = await _create_patient(db, owner)
    await _create_access_grant(db, patient, grantee, level="view")

    level = await resolve_patient_access(patient.id, grantee, db)
    assert level == AccessLevel.view


async def test_direct_grant_contribute_returns_contribute(db: AsyncSession):
    owner = await _create_user(db, "owner_dgc@test.com", role="admin")
    grantee = await _create_user(db, "grantee_dgc@test.com", role="user")
    patient = await _create_patient(db, owner)
    await _create_access_grant(db, patient, grantee, level="contribute")

    level = await resolve_patient_access(patient.id, grantee, db)
    assert level == AccessLevel.contribute


async def test_direct_grant_full_returns_full(db: AsyncSession):
    owner = await _create_user(db, "owner_dgf@test.com", role="admin")
    grantee = await _create_user(db, "grantee_dgf@test.com", role="user")
    patient = await _create_patient(db, owner)
    await _create_access_grant(db, patient, grantee, level="full")

    level = await resolve_patient_access(patient.id, grantee, db)
    assert level == AccessLevel.full


async def test_expired_grant_returns_none(db: AsyncSession):
    owner = await _create_user(db, "owner_exp@test.com", role="admin")
    grantee = await _create_user(db, "grantee_exp@test.com", role="user")
    patient = await _create_patient(db, owner)
    await _create_access_grant(
        db, patient, grantee,
        level="view",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    level = await resolve_patient_access(patient.id, grantee, db)
    assert level is None


# ---------------------------------------------------------------------------
# No access
# ---------------------------------------------------------------------------

async def test_no_access_returns_none(db: AsyncSession):
    owner = await _create_user(db, "owner_none@test.com", role="admin")
    stranger = await _create_user(db, "stranger_none@test.com", role="user")
    patient = await _create_patient(db, owner)

    level = await resolve_patient_access(patient.id, stranger, db)
    assert level is None
