import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.services import handout

router = APIRouter()


class PdfRequest(BaseModel):
    exclude: list[str] = Field(default_factory=list, max_length=2000)
    lang: Literal["de", "en"] = "de"


async def _build(patient_id, variant, user, db) -> dict:
    if variant not in handout.VARIANTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(patient_id, user, db)
    return await handout.build(patient_id, variant, db)


@router.get("/patients/{patient_id}/handouts/{variant}")
async def preview_handout(
    patient_id: uuid.UUID,
    variant: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _build(patient_id, variant, user, db)


@router.post("/patients/{patient_id}/handouts/{variant}/pdf")
async def download_handout(
    patient_id: uuid.UUID,
    variant: str,
    body: PdfRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pdf = handout.render_pdf(await _build(patient_id, variant, user, db), body.lang, set(body.exclude))
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="handout-{variant}-{date.today().isoformat()}.pdf"'})
