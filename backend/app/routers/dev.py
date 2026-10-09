"""Dev-only endpoints (seeding, reset). Only mounted when ENVIRONMENT=development."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import hash_password
from app.models import Organization, Patient, User, UserRole
from app.models.access import PatientAccess

router = APIRouter()


@router.post("/seed")
async def seed(db: AsyncSession = Depends(get_db)):
    # Ensure org exists
    result = await db.execute(select(Organization))
    if not result.scalar_one_or_none():
        db.add(Organization(name="OpenAvisio"))

    # Admin user
    result = await db.execute(select(User).where(User.email == "admin@openavisio.dev"))
    if not result.scalar_one_or_none():
        admin = User(
            email="admin@openavisio.dev",
            hashed_password=hash_password("Admin123!Admin"),
            first_name="Admin",
            last_name="User",
            role=UserRole.admin,
            is_active=True,
            email_confirmed=True,
        )
        db.add(admin)
        await db.flush()

        # Demo patient
        patient = Patient(
            created_by=admin.id,
            given_name="Demo",
            family_name="Patient",
            gender="unknown",
            active=True,
        )
        db.add(patient)
        await db.flush()
        db.add(PatientAccess(
            patient_id=patient.id, user_id=admin.id, access_level="admin",
            granted_by_user_id=admin.id, granted_at=datetime.now(UTC),
        ))

    await db.commit()
    return {"seeded": True, "admin": "admin@openavisio.dev", "password": "Admin123!Admin"}


@router.post("/reset")
async def reset(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    await db.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    await db.commit()
    return await seed(db)
