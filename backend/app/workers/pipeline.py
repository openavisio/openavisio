"""4-stage document processing pipeline: OCR → Classify → Extract → Embed."""

import asyncio
import logging
import uuid

import httpx

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _get_doc(doc_id: str):
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.document import DocumentReference

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(DocumentReference).where(DocumentReference.id == uuid.UUID(doc_id)))
        return result.scalar_one_or_none()


async def _get_org_language() -> str:
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.organization import Organization

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Organization))
        org = result.scalar_one_or_none()
        return org.default_language if org else "en"


async def _get_ai_model(stage: str) -> str | None:
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.system import SystemSetting

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == f"ai.model.{stage}"))
        setting = result.scalar_one_or_none()
        return setting.value if setting else None


async def _update_doc(doc_id: str, **kwargs):
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.document import DocumentReference

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(DocumentReference).where(DocumentReference.id == uuid.UUID(doc_id)))
        doc = result.scalar_one_or_none()
        if doc:
            for k, v in kwargs.items():
                setattr(doc, k, v)
            await db.commit()


async def _patient_kek(patient_id) -> bytes:
    from app.core.database import AsyncSessionLocal
    from app.core.patient_keys import get_patient_kek
    async with AsyncSessionLocal() as db:
        return await get_patient_kek(db, patient_id)


async def _decrypt_file(storage_path: str, encrypted_dek: bytes | None, kek: bytes) -> bytes:
    from app.core.encryption import decrypt_document
    from app.core.storage import get_storage
    data = get_storage().read(storage_path)
    return decrypt_document(data, encrypted_dek, kek)


@celery_app.task(bind=True, autoretry_for=(Exception,), max_retries=2, default_retry_delay=30)
def ocr_stage(self, doc_id: str):
    from app.core.config import settings

    async def _run_ocr():
        doc = await _get_doc(doc_id)
        if not doc or not doc.storage_path:
            return
        # Clear any error from a previous run, else a stale message survives a
        # successful re-run and the UI keeps showing "failed".
        await _update_doc(doc_id, processing_status="ocr_processing", pipeline_stage="ocr", processing_error=None)
        try:
            from app.core.encryption import encrypt_str
            kek = await _patient_kek(doc.patient_id)
            file_data = await _decrypt_file(doc.storage_path, doc.encrypted_dek, kek)
            # vision OCR runs one model call per page — generous timeout for multi-page scans (ADR 028)
            async with httpx.AsyncClient(timeout=600, headers=settings.ai_service_headers) as client:
                resp = await client.post(
                    f"{settings.ai_service_url}/ocr",
                    files={"file": (doc.file_name or "file", file_data, doc.content_type or "application/octet-stream")},
                )
                if resp.status_code == 200:
                    result = resp.json()
                    text = result.get("text", "")
                    confidence = result.get("confidence", 0.0)
                    await _update_doc(doc_id, extracted_text=encrypt_str(text, kek), ocr_confidence=confidence, processing_status="ocr_done", pipeline_stage="ocr")
                    classification_stage.delay(doc_id)
                else:
                    await _update_doc(doc_id, processing_status="failed", processing_error=f"OCR failed: {resp.status_code}")
        except Exception as e:
            await _update_doc(doc_id, processing_status="failed", processing_error=(str(e) or type(e).__name__))
            raise

    _run(_run_ocr())


@celery_app.task(bind=True, autoretry_for=(Exception,), max_retries=2, default_retry_delay=30)
def classification_stage(self, doc_id: str):
    from app.core.config import settings

    async def _run_classify():
        doc = await _get_doc(doc_id)
        if not doc or not doc.extracted_text:
            return
        await _update_doc(doc_id, processing_status="classifying", pipeline_stage="classification")
        try:
            from app.core.encryption import decrypt_str
            plain = decrypt_str(doc.extracted_text, await _patient_kek(doc.patient_id))
            classify_model, language = await asyncio.gather(_get_ai_model("classify"), _get_org_language())
            async with httpx.AsyncClient(timeout=300, headers=settings.ai_service_headers) as client:
                resp = await client.post(
                    f"{settings.ai_service_url}/classify",
                    json={"text": plain, "model": classify_model, "language": language},
                )
                if resp.status_code == 200:
                    result = resp.json()
                    await _update_doc(
                        doc_id,
                        document_classification=result.get("document_type"),
                        detected_provider=result.get("provider"),
                        processing_status="classified",
                        pipeline_stage="classification",
                    )
                    extraction_stage.delay(doc_id)
                else:
                    await _update_doc(doc_id, processing_status="failed", processing_error=f"Classification failed: {resp.status_code}")
        except Exception as e:
            await _update_doc(doc_id, processing_status="failed", processing_error=(str(e) or type(e).__name__))
            raise

    _run(_run_classify())


@celery_app.task(bind=True, autoretry_for=(Exception,), max_retries=2, default_retry_delay=30)
def extraction_stage(self, doc_id: str):
    from app.core.config import settings
    import json

    async def _run_extract():
        doc = await _get_doc(doc_id)
        if not doc or not doc.extracted_text:
            return
        # clear a stale error from a failed earlier run — a completed doc must not wear it (like ocr_stage does)
        await _update_doc(doc_id, processing_status="extracting", pipeline_stage="extraction", processing_error=None)
        try:
            from app.core.encryption import decrypt_str, encrypt_str
            kek = await _patient_kek(doc.patient_id)
            plain = decrypt_str(doc.extracted_text, kek)
            extract_model, language = await asyncio.gather(_get_ai_model("extract"), _get_org_language())
            # large multi-page HTML tables through a ~26B model can run minutes (ADR 028)
            async with httpx.AsyncClient(timeout=600, headers=settings.ai_service_headers) as client:
                resp = await client.post(
                    f"{settings.ai_service_url}/extract-entities",
                    json={"text": plain, "document_type": doc.document_classification, "model": extract_model, "language": language},
                )
                if resp.status_code == 200 and resp.json().get("error"):
                    # the aiservice reports a failed extraction as 200 with an error; it is not a result
                    error = resp.json()["error"]
                    logger.warning("Extraction of document %s failed: %s", doc_id, error)
                    await _update_doc(doc_id, processing_status="failed", processing_error=error)
                elif resp.status_code == 200:
                    extraction = resp.json()
                    entities = extraction.get("entities") or extraction
                    issued_date = None
                    # the model's date lives inside entities, not at the response top level
                    raw_date = entities.get("document_date") or entities.get("date")
                    if raw_date:
                        try:
                            from datetime import date as _date
                            issued_date = _date.fromisoformat(str(raw_date)[:10])
                        except (ValueError, TypeError):
                            pass
                    # A Kassenbescheid carries no end date, only a decision date and a
                    # period; the Widerspruchsfrist is computed here so the verification
                    # screen can show it and the User can correct it (ADR 041). The
                    # arithmetic lives in the backend, never in the model or the browser.
                    decision = entities.get("decision")
                    if isinstance(decision, dict) and not decision.get("deadline_date"):
                        from app.services.deadlines import parse_iso_date, widerspruch_deadline
                        decided_on = parse_iso_date(decision.get("decision_date"))
                        months = decision.get("deadline_months")
                        months = months if isinstance(months, int) and 1 <= months <= 12 else 1
                        if decided_on:
                            decision["deadline_date"] = widerspruch_deadline(decided_on, months).isoformat()
                            decision["deadline_months"] = months

                    update_kwargs = dict(
                        extraction_json=encrypt_str(json.dumps(entities), kek),
                        processing_status="extracted",
                        verification_status="extracted",
                        pipeline_stage="extraction",
                    )
                    if issued_date:
                        update_kwargs["issued_date"] = issued_date
                    # the model names the issuing practice/lab; it was only ever
                    # buried in the JSON, leaving detected_provider empty
                    provider = (entities.get("provider") or "").strip()
                    if provider:
                        update_kwargs["detected_provider"] = provider[:255]
                    await _update_doc(doc_id, **update_kwargs)
                    embedding_stage.delay(doc_id)
                else:
                    await _update_doc(doc_id, processing_status="failed", processing_error=f"Extraction failed: {resp.status_code}")
        except Exception as e:
            await _update_doc(doc_id, processing_status="failed", processing_error=(str(e) or type(e).__name__))
            raise

    _run(_run_extract())


@celery_app.task(bind=True, autoretry_for=(Exception,), max_retries=2, default_retry_delay=30)
def embedding_stage(self, doc_id: str):
    from app.core.config import settings

    async def _run_embed():
        doc = await _get_doc(doc_id)
        if not doc or not doc.extracted_text:
            return
        await _update_doc(doc_id, processing_status="embedding", pipeline_stage="embedding", processing_error=None)
        try:
            from app.core.encryption import decrypt_str, encrypt_str
            kek = await _patient_kek(doc.patient_id)
            # Chunk text
            chunks = _chunk_text(decrypt_str(doc.extracted_text, kek))
            if not chunks:
                await _update_doc(doc_id, processing_status="completed", pipeline_stage="done")
                from app.services.email import send_document_processed_notification
                await send_document_processed_notification(doc_id)
                return

            async with httpx.AsyncClient(timeout=60, headers=settings.ai_service_headers) as client:
                resp = await client.post(f"{settings.ai_service_url}/embed", json={"texts": chunks})
                if resp.status_code != 200:
                    await _update_doc(doc_id, processing_status="failed", processing_error="Embedding failed")
                    return
                embeddings = resp.json()["embeddings"]

            from sqlalchemy import select
            from app.core.database import AsyncSessionLocal
            from app.models.chat import DocumentChunk
            async with AsyncSessionLocal() as db:
                # Delete old chunks
                existing = await db.execute(select(DocumentChunk).where(DocumentChunk.document_reference_id == uuid.UUID(doc_id)))
                for chunk in existing.scalars().all():
                    await db.delete(chunk)
                for i, (text, emb) in enumerate(zip(chunks, embeddings)):
                    db.add(DocumentChunk(
                        document_reference_id=uuid.UUID(doc_id),
                        patient_id=doc.patient_id,
                        chunk_index=i,
                        content=encrypt_str(text, kek),
                        embedding=emb,
                    ))
                await db.commit()
            await _update_doc(doc_id, processing_status="completed", pipeline_stage="done")
            from app.services.email import send_document_processed_notification
            await send_document_processed_notification(doc_id)
        except Exception as e:
            await _update_doc(doc_id, processing_status="failed", processing_error=(str(e) or type(e).__name__))
            raise

    _run(_run_embed())


@celery_app.task
def intake_form_stage(form_id: str):
    """ADR 047. Not a Document stage: the form is read for its questions only."""
    async def _read():
        from app.core.database import AsyncSessionLocal
        from app.services.intake import read_form
        async with AsyncSessionLocal() as db:
            await read_form(uuid.UUID(form_id), db)

    _run(_read())


def _chunk_text(text: str, max_tokens: int = 500, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + max_tokens])
        chunks.append(chunk)
        i += max_tokens - overlap
    return [c for c in chunks if c.strip()]
