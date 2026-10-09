import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.deps import get_current_user
from app.models.correspondent import Correspondent
from app.models.organization import Organization
from app.models.user import User
from app.schemas.document import CorrespondentDto

router = APIRouter()


class CreateCorrespondentRequest(BaseModel):
    name: str


class UpdateCorrespondentRequest(BaseModel):
    name: str


async def _get_org_id(db: AsyncSession) -> uuid.UUID:
    org = (await db.execute(select(Organization))).scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=503, detail="Organization not initialized.")
    return org.id


@router.get("/correspondents", response_model=list[CorrespondentDto])
async def list_correspondents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Correspondent)
        .where(Correspondent.is_deleted == False)  # noqa: E712
        .order_by(Correspondent.name)
    )).scalars().all()
    return rows


@router.post("/correspondents", response_model=CorrespondentDto, status_code=201)
async def create_correspondent(
    body: CreateCorrespondentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_id = await _get_org_id(db)
    c = Correspondent(name=body.name.strip(), organization_id=org_id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@router.patch("/correspondents/{correspondent_id}", response_model=CorrespondentDto)
async def update_correspondent(
    correspondent_id: uuid.UUID,
    body: UpdateCorrespondentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    c = (await db.execute(
        select(Correspondent).where(Correspondent.id == correspondent_id, Correspondent.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404)
    c.name = body.name.strip()
    await db.commit()
    await db.refresh(c)
    return c


@router.delete("/correspondents/{correspondent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_correspondent(
    correspondent_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    c = (await db.execute(
        select(Correspondent).where(Correspondent.id == correspondent_id, Correspondent.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404)
    c.is_deleted = True
    await db.commit()
