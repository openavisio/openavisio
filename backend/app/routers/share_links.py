"""External document share links — see docs/adr/021-external-document-share-links.md.

Two sides:
- Caregivers (owner / legal rep / non-staff with access) create and manage links
  on the Patient side. Staff (admin/manager) without owner/rep standing are refused.
- External specialists open the anonymous, token-only public endpoints (no auth).
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.encryption import decrypt_document, encrypt_document
from app.core.storage import get_storage
from app.deps import get_current_user
from app.models.audit import AuditLog
from app.models.document import DocumentReference
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.share_link import DocumentShareLink, DocumentShareLinkHandout, DocumentShareLinkItem, ShareLinkStatus
from app.models.user import User
from app.schemas.share_link import (
    PublicShareDocumentDto,
    PublicShareLinkDto,
    PublicSharePatientDto,
    ShareLinkAddDocumentsRequest,
    ShareLinkCreatedDto,
    ShareLinkCreateRequest,
    ShareLinkDocumentDto,
    ShareLinkDto,
    ShareLinkHandoutDto,
)
from app.services import handout as handouts
from app.services.share_link import (
    generate_token,
    hash_token,
    link_status,
    log_share_access,
    require_share_management,
)

router = APIRouter()

_PUBLIC_HEADERS = {
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
    "Cache-Control": "no-store",
}


# --- helpers -----------------------------------------------------------------

def _audit(db: AsyncSession, user: User, action: str, link_id, changes: dict | None = None) -> None:
    name = " ".join(filter(None, [user.first_name, user.last_name])) or user.email
    db.add(AuditLog(
        timestamp=datetime.now(UTC),
        user_id=user.id,
        user_name=name,
        entity_type="DocumentShareLink",
        entity_id=str(link_id),
        action=action,
        changes=changes,
    ))


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


async def _link_documents(link_id: uuid.UUID, db: AsyncSession) -> list[DocumentReference]:
    result = await db.execute(
        select(DocumentReference)
        .join(DocumentShareLinkItem, DocumentShareLinkItem.document_id == DocumentReference.id)
        .where(
            DocumentShareLinkItem.share_link_id == link_id,
            DocumentReference.is_deleted == False,  # noqa: E712
        )
        .order_by(DocumentReference.issued_date.desc().nullslast(), DocumentReference.created_at.desc())
    )
    return list(result.scalars().all())


async def _link_handout(link_id: uuid.UUID, db: AsyncSession) -> DocumentShareLinkHandout | None:
    return (await db.execute(
        select(DocumentShareLinkHandout).where(DocumentShareLinkHandout.share_link_id == link_id)
    )).scalar_one_or_none()


async def _access_stats(link_id: uuid.UUID, db: AsyncSession) -> tuple[int, datetime | None]:
    row = (await db.execute(
        select(func.count(), func.max(AuditLog.timestamp)).where(
            AuditLog.entity_type == "DocumentShareLink",
            AuditLog.entity_id == str(link_id),
            AuditLog.action == "accessed",
        )
    )).one()
    return int(row[0] or 0), row[1]


async def _link_dto(link: DocumentShareLink, db: AsyncSession, now: datetime) -> ShareLinkDto:
    docs = await _link_documents(link.id, db)
    count, last = await _access_stats(link.id, db)
    frozen = await _link_handout(link.id, db)
    return ShareLinkDto(
        handout=ShareLinkHandoutDto.model_validate(frozen) if frozen else None,
        id=link.id,
        status=link_status(link, now),
        expires_at=link.expires_at,
        created_at=link.created_at,
        created_by_user_id=link.created_by_user_id,
        created_legal=link.created_legal,
        revoked_at=link.revoked_at,
        documents=[
            ShareLinkDocumentDto(document_id=d.id, file_name=d.file_name, content_type=d.content_type, size=d.size)
            for d in docs
        ],
        access_count=count,
        last_accessed_at=last,
    )


async def _validate_patient_documents(
    patient_id: uuid.UUID, document_ids: list[uuid.UUID], db: AsyncSession
) -> list[uuid.UUID]:
    """Return the subset of document_ids that belong to the patient and exist."""
    if not document_ids:
        return []
    result = await db.execute(
        select(DocumentReference.id).where(
            DocumentReference.id.in_(document_ids),
            DocumentReference.patient_id == patient_id,
            DocumentReference.is_deleted == False,  # noqa: E712
        )
    )
    return [row[0] for row in result.all()]


async def _get_managed_link(link_id: uuid.UUID, patient_id: uuid.UUID, db: AsyncSession) -> DocumentShareLink:
    result = await db.execute(
        select(DocumentShareLink).where(
            DocumentShareLink.id == link_id,
            DocumentShareLink.patient_id == patient_id,
            DocumentShareLink.is_deleted == False,  # noqa: E712
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return link


# --- Caregiver management side -----------------------------------------------

@router.post("/patients/{patient_id}/share-links", response_model=ShareLinkCreatedDto, status_code=201)
async def create_share_link(
    patient_id: uuid.UUID,
    body: ShareLinkCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    created_legal = await require_share_management(patient_id, user, db)

    patient = (await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    valid_ids = await _validate_patient_documents(patient_id, body.document_ids, db)
    pdf = None
    if body.handout:
        # ADR 048: frozen as previewed, and a Document the Emergency Plan points at goes along
        exclude = set(body.handout.exclude)
        data = await handouts.build(patient_id, body.handout.variant, db)
        plan_docs = [uuid.UUID(e["id"].split(":", 1)[1]) for s in data["sections"] if s["key"] == "emergency_documents"
                     for e in s["entries"] if e["id"] not in exclude]
        valid_ids += [d for d in await _validate_patient_documents(patient_id, plan_docs, db) if d not in valid_ids]
        pdf = handouts.render_pdf(data, body.handout.lang, exclude)
    if not valid_ids and pdf is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid documents selected.")

    token, token_hash = generate_token()
    now = datetime.now(UTC)
    link = DocumentShareLink(
        patient_id=patient_id,
        token_hash=token_hash,
        status=ShareLinkStatus.active,
        expires_at=now + timedelta(days=body.expiry_days),
        created_by_user_id=user.id,
        created_legal=created_legal,
    )
    db.add(link)
    await db.flush()
    for doc_id in valid_ids:
        db.add(DocumentShareLinkItem(share_link_id=link.id, document_id=doc_id, patient_id=patient_id))
    if pdf is not None:
        from app.core.patient_keys import ensure_patient_kek
        ciphertext, wrapped = encrypt_document(pdf, await ensure_patient_kek(db, patient_id))
        db.add(DocumentShareLinkHandout(share_link_id=link.id, patient_id=patient_id, variant=body.handout.variant,
                                        lang=body.handout.lang, pdf=ciphertext, encrypted_dek=wrapped))
    _audit(db, user, "created", link.id, {"documents": [str(d) for d in valid_ids], "expiry_days": body.expiry_days,
                                          "handout": body.handout.variant if body.handout else None})
    await db.commit()
    await db.refresh(link)

    base = settings.app_url.rstrip("/") if settings.app_url else ""
    dto = await _link_dto(link, db, now)
    return ShareLinkCreatedDto(**dto.model_dump(), url=f"{base}/share/{token}")


@router.get("/patients/{patient_id}/share-links", response_model=list[ShareLinkDto])
async def list_share_links(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_share_management(patient_id, user, db)
    now = datetime.now(UTC)
    result = await db.execute(
        select(DocumentShareLink)
        .where(DocumentShareLink.patient_id == patient_id, DocumentShareLink.is_deleted == False)  # noqa: E712
        .order_by(DocumentShareLink.created_at.desc())
    )
    return [await _link_dto(link, db, now) for link in result.scalars().all()]


@router.post("/patients/{patient_id}/share-links/{link_id}/documents", response_model=ShareLinkDto)
async def add_documents(
    patient_id: uuid.UUID,
    link_id: uuid.UUID,
    body: ShareLinkAddDocumentsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_share_management(patient_id, user, db)
    link = await _get_managed_link(link_id, patient_id, db)
    now = datetime.now(UTC)
    if link_status(link, now) != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot add documents to an inactive link.")

    valid_ids = await _validate_patient_documents(patient_id, body.document_ids, db)
    existing = {
        row[0] for row in (await db.execute(
            select(DocumentShareLinkItem.document_id).where(DocumentShareLinkItem.share_link_id == link_id)
        )).all()
    }
    added = [d for d in valid_ids if d not in existing]
    if not added:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No new valid documents to add.")

    for doc_id in added:
        db.add(DocumentShareLinkItem(share_link_id=link_id, document_id=doc_id, patient_id=patient_id))
    _audit(db, user, "updated", link_id, {"added_documents": [str(d) for d in added]})
    await db.commit()
    return await _link_dto(link, db, now)


@router.post("/patients/{patient_id}/share-links/{link_id}/revoke", response_model=ShareLinkDto)
async def revoke_share_link(
    patient_id: uuid.UUID,
    link_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_share_management(patient_id, user, db)
    link = await _get_managed_link(link_id, patient_id, db)
    now = datetime.now(UTC)
    if link.status == ShareLinkStatus.active:
        link.status = ShareLinkStatus.revoked
        link.revoked_at = now
        _audit(db, user, "updated", link_id, {"status": {"new": "revoked"}})
        await db.commit()
        await db.refresh(link)
    return await _link_dto(link, db, now)


# --- Public (external recipient) side — no authentication --------------------

async def _resolve_public_link(token: str, db: AsyncSession) -> DocumentShareLink:
    """Look up an active link by token. 404 unknown, 410 expired/revoked."""
    result = await db.execute(
        select(DocumentShareLink).where(
            DocumentShareLink.token_hash == hash_token(token),
            DocumentShareLink.is_deleted == False,  # noqa: E712
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    st = link_status(link, datetime.now(UTC))
    if st == "expired":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This share link has expired.")
    if st == "revoked":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This share link has been revoked.")
    return link


@router.get("/public/document-shares/{token}", response_model=PublicShareLinkDto)
async def public_view_share(token: str, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    link = await _resolve_public_link(token, db)

    patient = (await db.execute(
        select(Patient).where(Patient.id == link.patient_id, Patient.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    docs = await _link_documents(link.id, db)
    frozen = await _link_handout(link.id, db)
    if not patient or not (docs or frozen):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="The shared documents are no longer available.")

    org = (await db.execute(select(Organization))).scalar_one_or_none()

    await log_share_access(db, link.id, None, "open", _client_ip(request), request.headers.get("user-agent"))
    await db.commit()

    # extraction_json is ciphertext at rest (ADR-031) — decrypt for the public view
    import json
    from app.core.encryption import decrypt_str
    from app.core.patient_keys import get_patient_kek
    kek = await get_patient_kek(db, link.patient_id)

    def _extraction(d):
        ej = d.extraction_json
        if isinstance(ej, str):
            dec = decrypt_str(ej, kek)
            return json.loads(dec) if dec else None
        return ej

    response.headers.update(_PUBLIC_HEADERS)
    return PublicShareLinkDto(
        patient=PublicSharePatientDto(
            given_name=patient.given_name, family_name=patient.family_name, birth_date=patient.birth_date
        ),
        org_name=org.name if org else "OpenAvisio",
        expires_at=link.expires_at,
        documents=[
            PublicShareDocumentDto(
                id=d.id,
                file_name=d.file_name,
                content_type=d.content_type,
                size=d.size,
                type=d.type,
                issued_date=d.issued_date.isoformat() if d.issued_date else None,
                extraction=_extraction(d),
            )
            for d in docs
        ],
        handout=ShareLinkHandoutDto.model_validate(frozen) if frozen else None,
    )


@router.get("/public/document-shares/{token}/handout/file")
async def public_download_share_handout(
    token: str,
    request: Request,
    download: bool = False,
    db: AsyncSession = Depends(get_db),
):
    link = await _resolve_public_link(token, db)
    frozen = await _link_handout(link.id, db)
    if not frozen:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    from app.core.patient_keys import get_patient_kek
    data = decrypt_document(frozen.pdf, frozen.encrypted_dek, await get_patient_kek(db, frozen.patient_id))

    event = "handout_download" if download else "handout_view"
    await log_share_access(db, link.id, None, event, _client_ip(request), request.headers.get("user-agent"))
    await db.commit()

    disposition = "attachment" if download else "inline"
    filename = f"handout-{frozen.variant}-{frozen.created_at.date().isoformat()}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={**_PUBLIC_HEADERS, "Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.get("/public/document-shares/{token}/documents/{document_id}/file")
async def public_download_share_file(
    token: str,
    document_id: uuid.UUID,
    request: Request,
    download: bool = False,
    db: AsyncSession = Depends(get_db),
):
    link = await _resolve_public_link(token, db)

    row = (await db.execute(
        select(DocumentReference)
        .join(DocumentShareLinkItem, DocumentShareLinkItem.document_id == DocumentReference.id)
        .where(
            DocumentShareLinkItem.share_link_id == link.id,
            DocumentReference.id == document_id,
            DocumentReference.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    from app.core.patient_keys import get_patient_kek
    kek = await get_patient_kek(db, row.patient_id)
    data = get_storage().read(row.storage_path)
    data = decrypt_document(data, row.encrypted_dek, kek)

    event = "download" if download else "view"
    await log_share_access(db, link.id, document_id, event, _client_ip(request), request.headers.get("user-agent"))
    await db.commit()

    disposition = "attachment" if download else "inline"
    filename = row.file_name or str(row.id)
    return Response(
        content=data,
        media_type=row.content_type or "application/octet-stream",
        headers={**_PUBLIC_HEADERS, "Content-Disposition": f'{disposition}; filename="{filename}"'},
    )
