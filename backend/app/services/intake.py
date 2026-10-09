"""Intake Form (ADR 047): answered from the record, then History Facts, then a cited
Document passage; whatever is left is the Caregiver's. Judgement questions are never
answered, whatever the model returned (the aiservice guarantees it, so does this)."""

import json
import uuid
from datetime import UTC, date, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.encryption import decrypt_document, decrypt_str, encrypt_str
from app.core.patient_keys import get_patient_kek
from app.core.storage import get_storage
from app.models.einstufung import Einstufung
from app.models.intake import HistoryFact, IntakeForm
from app.models.patient import Patient
from app.routers import chat
from app.workers.pipeline import _get_ai_model

AGINGS = ("lasting", "changeable", "visit_only")
PASSAGES_PER_QUESTION = 2

# where the record line's entry can be changed, for the offer after a correction
_SEGMENTS = {
    "medication": "medications", "condition": "conditions", "milestone": "calendar", "appointment": "calendar",
    "lab": "lab-results", "care_note": "care-notes", "carer_update": "carer-updates",
}


def _today() -> str:
    return date.today().isoformat()


async def _ai(path: str, payload: dict) -> dict:
    # a long form through a ~27B model can run minutes, like extraction (ADR 028)
    async with httpx.AsyncClient(timeout=600, headers=settings.ai_service_headers) as client:
        resp = await client.post(f"{settings.ai_service_url}{path}", json=payload)
        resp.raise_for_status()
        return resp.json()


async def _ocr(form: IntakeForm, data: bytes) -> str:
    async with httpx.AsyncClient(timeout=600, headers=settings.ai_service_headers) as client:
        resp = await client.post(f"{settings.ai_service_url}/ocr", files={
            "file": (form.file_name or "form", data, form.content_type or "application/octet-stream")})
        resp.raise_for_status()
        return resp.json().get("text", "")


async def record_entries(patient_id: uuid.UUID, db: AsyncSession, lang: str) -> list[dict]:
    """The record as numbered entries: {id, text, segment, fact}. The same lines the chat
    reads, plus who the Patient is and their Einstufungen, which a form asks for."""
    L = chat._LABELS[lang]
    by_label = {v: k for k, v in L.items() if isinstance(v, str)}
    lines: list[tuple[str, str | None, HistoryFact | None]] = []

    p = (await db.execute(select(Patient).where(Patient.id == patient_id))).scalar_one()
    lines.append((chat._line("Patient", p.birth_date, f"{p.given_name} {p.family_name}", p.gender), None, None))
    for e in (await db.execute(select(Einstufung).where(
            Einstufung.patient_id == patient_id, Einstufung.is_deleted == False)  # noqa: E712
            .order_by(Einstufung.valid_from.desc().nullslast()))).scalars().all():
        lines.append((chat._line("Einstufung", e.valid_from, f"Pflegegrad {e.pflegegrad}" if e.pflegegrad else None,
                                 e.authority, f"{L['until']} {e.valid_until}" if e.valid_until else None),
                      "einstufung", None))

    record, _ = await chat._structured_context(patient_id, db, lang)
    for line in record:
        kind = by_label.get(line.split(" | ", 1)[0])
        # cap notices are no entries; History Facts follow with their ids
        if " | " in line and kind != "history_fact":
            lines.append((line, _SEGMENTS.get(kind), None))
    for f in await chat._history_facts(patient_id, db):
        lines.append((chat._fact_line(f, lang), None, f))
    return [{"id": f"E{i}", "text": t, "segment": s, "fact": f} for i, (t, s, f) in enumerate(lines, 1)]


def _item(q: dict) -> dict:
    return {"text": q["text"], "section": q.get("section"), "kind": q.get("kind"), "aging": q.get("aging"),
            "answer": None, "origin": None, "sources": [], "related": [], "fact_id": None,
            "document": None, "passage": None, "confirmed": True, "record_corrected": False}


async def build_sheet(patient_id: uuid.UUID, questions: list[dict], db: AsyncSession, lang: str,
                      model: str | None) -> list[dict]:
    items = [_item(q) for q in questions]
    for it in items:
        if it["kind"] != "fact":  # in doubt a judgement (GLOSSARY)
            it["kind"] = "judgement"
        if it["aging"] not in AGINGS:
            it["aging"] = "changeable"
    if not items:
        return items

    entries = await record_entries(patient_id, db, lang)
    by_id = {e["id"]: e for e in entries}
    answers = (await _ai("/intake/answer", {
        "questions": [{"text": it["text"], "kind": it["kind"]} for it in items],
        "context": [{"id": e["id"], "text": e["text"]} for e in entries],
        "model": model, "language": lang,
    }))["answers"]
    for it, a in zip(items, answers):
        it["related"] = [by_id[r]["text"] for r in a.get("related") or [] if r in by_id]
        sources = [by_id[s] for s in a.get("sources") or [] if s in by_id]
        if it["kind"] != "fact" or not a.get("answer") or not sources:
            continue
        facts = [s["fact"] for s in sources if s["fact"]]
        it["answer"] = a["answer"]
        it["sources"] = [{"text": s["text"], "segment": s["segment"]} for s in sources]
        if len(facts) == len(sources):
            it["origin"] = "history"
            # one fact behind it: correcting the answer is that fact's new answer
            it["fact_id"] = str(facts[0].id) if len(facts) == 1 else None
            # a changeable fact counts only once a Caregiver confirms it again
            it["confirmed"] = all(f.aging == "lasting" for f in facts)
        else:
            it["origin"] = "record"

    await _document_answers(patient_id, [it for it in items if it["kind"] == "fact" and not it["answer"]],
                            db, lang, model)
    return items


async def _document_answers(patient_id: uuid.UUID, open_items: list[dict], db: AsyncSession, lang: str,
                            model: str | None) -> None:
    """Searched when a form asks, never mined on upload; offered, never filled in (ADR 047)."""
    if not open_items:
        return
    try:
        embeddings = await chat._embed_queries([it["text"] for it in open_items], lang)
    except Exception:
        return  # no search is no answer, not a failed form
    passages: dict[tuple, dict] = {}
    for emb in embeddings:
        for r in await chat._nearest_chunks(patient_id, emb, db, PASSAGES_PER_QUESTION):
            passages.setdefault((r.document_reference_id, r.content), {
                "id": f"P{len(passages) + 1}", "text": r.content,
                "document": {"id": str(r.document_reference_id), "file_name": r.file_name or "?"},
            })
    if not passages:
        return
    by_id = {p["id"]: p for p in passages.values()}
    answers = (await _ai("/intake/answer", {
        "questions": [{"text": it["text"], "kind": "fact"} for it in open_items],
        "context": [{"id": p["id"], "text": f"{p['document']['file_name']}: {p['text']}"} for p in passages.values()],
        "model": model, "language": lang,
    }))["answers"]
    for it, a in zip(open_items, answers):
        src = [by_id[s] for s in a.get("sources") or [] if s in by_id]
        if a.get("answer") and src:
            it.update(answer=a["answer"], origin="document", document=src[0]["document"],
                      passage=src[0]["text"], confirmed=False)


async def read_form(form_id: uuid.UUID, db: AsyncSession) -> None:
    form = (await db.execute(select(IntakeForm).where(IntakeForm.id == form_id))).scalar_one_or_none()
    if not form or form.is_deleted:
        return
    try:
        kek = await get_patient_kek(db, form.patient_id)
        data = decrypt_document(get_storage().read(form.storage_path), form.encrypted_dek, kek)
        lang, model = await chat._org_language(db), await _get_ai_model("extract")
        text = await _ocr(form, data)
        questions = (await _ai("/intake/questions", {"text": text, "model": model, "language": lang}))["questions"]
        sheet = await build_sheet(form.patient_id, questions, db, lang, model)
        form.sheet = encrypt_str(json.dumps(sheet), kek)
        form.status, form.processing_error = "draft", None
    except Exception as e:
        await db.rollback()
        form = await db.get(IntakeForm, form_id)
        form.status, form.processing_error = "failed", (str(e) or type(e).__name__)[:1000]
    await db.commit()


def load_sheet(form: IntakeForm, kek: bytes) -> list[dict]:
    return json.loads(decrypt_str(form.sheet, kek)) if form.sheet else []


async def _fact(fact_id: str | None, patient_id: uuid.UUID, db: AsyncSession) -> HistoryFact | None:
    if not fact_id:
        return None
    return (await db.execute(select(HistoryFact).where(
        HistoryFact.id == uuid.UUID(fact_id), HistoryFact.patient_id == patient_id,
        HistoryFact.is_deleted == False))).scalar_one_or_none()  # noqa: E712


async def update_item(form: IntakeForm, item: dict, *, answer: str | None, answer_given: bool,
                      aging: str | None, confirm: bool, owner_id: uuid.UUID, db: AsyncSession) -> None:
    """A Caregiver's answer, correction or confirmation. A record answer corrected changes
    the sheet only: the record is offered, never changed by this (ADR 047)."""
    if aging:
        item["aging"] = aging
    fact = await _fact(item.get("fact_id"), form.patient_id, db)

    if answer_given:
        item["answer"] = (answer or "").strip() or None
        item["confirmed"] = True
        if item["origin"] == "record":
            item["record_corrected"] = True
        if item["kind"] == "fact" and item["answer"] and item["origin"] != "record":
            if fact:
                fact.answer, fact.confirmed_on, fact.source = item["answer"], _today(), "caregiver"
            else:
                fact = HistoryFact(patient_id=form.patient_id, owner_id=owner_id, question=item["text"],
                                   answer=item["answer"], aging=item["aging"], confirmed_on=_today(),
                                   source="caregiver", intake_form_id=form.id)
                db.add(fact)
                await db.flush()
                item["fact_id"] = str(fact.id)
            item["origin"] = "caregiver"
    elif confirm and item["answer"]:
        if fact:
            fact.confirmed_on = _today()
        elif item["origin"] == "document":
            fact = HistoryFact(patient_id=form.patient_id, owner_id=owner_id, question=item["text"],
                               answer=item["answer"], aging=item["aging"], confirmed_on=_today(),
                               source="document", document_reference_id=uuid.UUID(item["document"]["id"]),
                               intake_form_id=form.id)
            db.add(fact)
            await db.flush()
            item["fact_id"] = str(fact.id)
        item["confirmed"] = True

    if fact and aging:
        fact.aging = aging


def release(form: IntakeForm, sheet: list[dict]) -> None:
    """Frozen as handed in. An unconfirmed suggestion was never an answer."""
    for item in sheet:
        if not item["confirmed"]:
            item["answer"] = None
    form.status, form.released_at = "released", datetime.now(UTC)
