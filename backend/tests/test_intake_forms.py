"""Intake Forms and History Facts (ADR 047): answered from the record, learns only what it lacks."""

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.patient_keys import ensure_patient_kek
from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.document import DocumentReference
from app.models.intake import HistoryFact, IntakeForm
from app.models.medication import MedicationStatement
from app.models.patient import Patient
from app.models.user import User
from app.routers import chat as chat_router
from app.routers import intake_forms as intake_router
from app.services import intake as svc

QUESTIONS = [
    {"text": "Current medication", "section": None, "kind": "fact", "aging": "changeable"},
    {"text": "Birth weight", "section": "Birth", "kind": "fact", "aging": "lasting"},
    {"text": "Health insurance", "section": None, "kind": "fact", "aging": "changeable"},
    {"text": "Is the development age-appropriate?", "section": None, "kind": "judgement", "aging": "changeable"},
    {"text": "Reason for this visit", "section": None, "kind": "fact", "aging": "visit_only"},
]


async def _setup(db: AsyncSession, client: AsyncClient, email="intake@t.com"):
    u = User(email=email, hashed_password=hash_password("Pass1!"), role="user",
             is_active=True, first_name="T", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    p = Patient(given_name="Lena", family_name="Test", birth_date="2019-05-14", created_by=u.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=u.id, access_level="admin", granted_at=datetime.now(UTC)))
    db.add(MedicationStatement(patient_id=p.id, owner_id=u.id, medication_display="Levetiracetam",
                               dosage_text="250 mg twice daily", status="active"))
    await db.commit()
    await ensure_patient_kek(db, p.id)
    await db.commit()
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    return u, p, {"Authorization": f"Bearer {r.json()['access_token']}"}


# which entry a well-behaved model would cite for each question
_CITES = {"Current medication": "Levetiracetam", "Birth weight": "Birth weight",
          "Is the development age-appropriate?": "Levetiracetam"}


def _fake_ai(seen: list):
    """A model that answers everything it can find, judgement questions included."""
    async def fake(path, payload):
        seen.append((path, payload))
        if path == "/intake/questions":
            return {"questions": QUESTIONS}
        answers = []
        for i, q in enumerate(payload["questions"], 1):
            word = _CITES.get(q["text"])
            hit = next((c for c in payload["context"] if word and word in c["text"]), None)
            answers.append({"q": i, "answer": hit["text"] if hit else None,
                            "sources": [hit["id"]] if hit else [], "related": [hit["id"]] if hit else []})
        return {"answers": answers}
    return fake


async def _read(client, db, headers, patient, monkeypatch, seen=None):
    monkeypatch.setattr(intake_router, "_enqueue", lambda form: None)
    monkeypatch.setattr(svc, "_ai", _fake_ai(seen if seen is not None else []))

    async def no_ocr(form, data):
        return "form text"

    async def no_embed(texts, lang):
        raise RuntimeError("no embedding service in tests")
    monkeypatch.setattr(svc, "_ocr", no_ocr)
    monkeypatch.setattr(chat_router, "_embed_queries", no_embed)
    r = await client.post(f"/api/patients/{patient.id}/intake-forms", headers=headers,
                          files={"file": ("form.pdf", b"%PDF-1.4 form", "application/pdf")}, data={"title": "Practice"})
    assert r.status_code == 201, r.text
    form_id = r.json()["id"]
    await svc.read_form(uuid.UUID(form_id), db)
    r = await client.get(f"/api/intake-forms/{form_id}", headers=headers)
    assert r.json()["status"] == "draft", r.json()
    return form_id, r.json()["items"]


async def test_the_form_is_not_a_document_and_its_original_is_encrypted(client, db, monkeypatch):
    _, p, h = await _setup(db, client)
    form_id, _ = await _read(client, db, h, p, monkeypatch)
    assert (await db.execute(select(DocumentReference).where(DocumentReference.patient_id == p.id))).first() is None
    form = await db.get(IntakeForm, uuid.UUID(form_id))
    from app.core.storage import get_storage
    assert b"%PDF-1.4 form" not in get_storage().read(form.storage_path)
    r = await client.get(f"/api/intake-forms/{form_id}/file", headers=h)
    assert r.content == b"%PDF-1.4 form"


async def test_answers_from_the_record_and_never_a_judgement(client, db, monkeypatch):
    _, p, h = await _setup(db, client)
    _, items = await _read(client, db, h, p, monkeypatch)
    med, _, insurance, judgement, _ = items
    assert med["origin"] == "record" and "Levetiracetam" in med["answer"]
    assert med["sources"][0]["segment"] == "medications"
    assert insurance["answer"] is None and insurance["origin"] is None
    # the fake model answered it; the sheet must not
    assert judgement["answer"] is None and judgement["sources"] == []
    assert judgement["related"] and "Levetiracetam" in judgement["related"][0]


async def test_answering_keeps_a_history_fact_and_the_next_form_reuses_it(client, db, monkeypatch):
    _, p, h = await _setup(db, client)
    form_id, _ = await _read(client, db, h, p, monkeypatch)
    r = await client.put(f"/api/intake-forms/{form_id}/items/1", headers=h, json={"answer": "Birth weight 3200 g"})
    assert r.json()["items"][1]["origin"] == "caregiver"
    await client.put(f"/api/intake-forms/{form_id}/items/4", headers=h, json={"answer": "Check-up"})
    await client.put(f"/api/intake-forms/{form_id}/items/3", headers=h, json={"answer": "Seems fine to us"})
    facts = (await client.get(f"/api/patients/{p.id}/history-facts", headers=h)).json()
    # a judgement answer is the family's impression on the day, not a fact to reuse
    assert sorted(f["aging"] for f in facts) == ["lasting", "visit_only"]

    seen = []
    _, items = await _read(client, db, h, p, monkeypatch, seen)
    context = " ".join(c["text"] for c in seen[-1][1]["context"])
    assert "Birth weight 3200 g" in context and "Check-up" not in context
    assert items[1]["origin"] == "history" and items[1]["confirmed"] is True


async def test_a_changeable_fact_counts_only_once_confirmed(client, db, monkeypatch):
    u, p, h = await _setup(db, client)
    db.add(HistoryFact(patient_id=p.id, owner_id=u.id, question="Birth weight", answer="Birth weight 3200 g",
                       aging="changeable", confirmed_on="2025-01-01"))
    await db.commit()
    form_id, items = await _read(client, db, h, p, monkeypatch)
    assert items[1]["origin"] == "history" and items[1]["confirmed"] is False

    r = await client.post(f"/api/intake-forms/{form_id}/release", headers=h)
    assert r.json()["items"][1]["answer"] is None, "an unconfirmed suggestion was never an answer"


async def test_correcting_a_record_answer_leaves_the_record_alone(client, db, monkeypatch):
    _, p, h = await _setup(db, client)
    form_id, _ = await _read(client, db, h, p, monkeypatch)
    r = await client.put(f"/api/intake-forms/{form_id}/items/0", headers=h, json={"answer": "Levetiracetam 500 mg"})
    item = r.json()["items"][0]
    assert item["answer"] == "Levetiracetam 500 mg" and item["record_corrected"] is True
    med = (await db.execute(select(MedicationStatement).where(MedicationStatement.patient_id == p.id))).scalar_one()
    assert med.dosage_text == "250 mg twice daily"
    assert (await client.get(f"/api/patients/{p.id}/history-facts", headers=h)).json() == []


async def test_released_is_frozen_and_a_correction_is_a_new_sheet(client, db, monkeypatch):
    _, p, h = await _setup(db, client)
    form_id, _ = await _read(client, db, h, p, monkeypatch)
    await client.post(f"/api/intake-forms/{form_id}/release", headers=h)
    r = await client.put(f"/api/intake-forms/{form_id}/items/2", headers=h, json={"answer": "AOK"})
    assert r.status_code == 409
    r = await client.post(f"/api/intake-forms/{form_id}/revise", headers=h)
    assert r.status_code == 201 and r.json()["status"] == "draft"
    r = await client.put(f"/api/intake-forms/{r.json()['id']}/items/2", headers=h, json={"answer": "AOK"})
    assert r.json()["items"][2]["answer"] == "AOK"
    old = (await client.get(f"/api/intake-forms/{form_id}", headers=h)).json()
    assert old["items"][2]["answer"] is None


async def test_deleting_a_form_takes_its_visit_only_facts_along(client, db, monkeypatch):
    _, p, h = await _setup(db, client)
    form_id, _ = await _read(client, db, h, p, monkeypatch)
    await client.put(f"/api/intake-forms/{form_id}/items/1", headers=h, json={"answer": "3200 g"})
    await client.put(f"/api/intake-forms/{form_id}/items/4", headers=h, json={"answer": "Check-up"})
    assert (await client.delete(f"/api/intake-forms/{form_id}", headers=h)).status_code == 204
    facts = (await client.get(f"/api/patients/{p.id}/history-facts", headers=h)).json()
    assert [f["answer"] for f in facts] == ["3200 g"] and facts[0]["intake_form_id"] is None


async def test_history_facts_are_edited_and_deleted_but_never_created_freely(client, db, monkeypatch):
    u, p, h = await _setup(db, client)
    f = HistoryFact(patient_id=p.id, owner_id=u.id, question="School", answer="Kita", aging="changeable",
                    confirmed_on="2025-01-01")
    db.add(f)
    await db.commit()
    assert (await client.post(f"/api/patients/{p.id}/history-facts", headers=h, json={})).status_code == 405
    r = await client.put(f"/api/history-facts/{f.id}", headers=h, json={"answer": "Primary school", "aging": "changeable"})
    assert r.json()["answer"] == "Primary school" and r.json()["confirmed_on"] != "2025-01-01"
    assert (await client.delete(f"/api/history-facts/{f.id}", headers=h)).status_code == 204
    assert (await client.get(f"/api/patients/{p.id}/history-facts", headers=h)).json() == []


async def test_chat_reads_facts_without_the_visit_only_ones_and_fhir_has_all(client, db, monkeypatch):
    u, p, h = await _setup(db, client)
    db.add_all([
        HistoryFact(patient_id=p.id, owner_id=u.id, question="Birth weight", answer="3200 g", aging="lasting",
                    confirmed_on="2025-01-01"),
        HistoryFact(patient_id=p.id, owner_id=u.id, question="Reason for this visit", answer="Headaches",
                    aging="visit_only", confirmed_on="2025-01-01"),
    ])
    await db.commit()
    lines, _ = await chat_router._structured_context(p.id, db, "en")
    assert "History fact | 2025-01-01 | Birth weight | 3200 g" in lines
    assert not any("Headaches" in ln for ln in lines)
    bundle = (await client.get(f"/api/patients/{p.id}/export/fhir", headers=h)).json()
    assert {"3200 g", "Headaches"} <= {e["resource"].get("valueString") for e in bundle["entry"]}


async def test_erasure_takes_forms_and_facts(client, db, monkeypatch):
    u, p, h = await _setup(db, client)
    form_id, _ = await _read(client, db, h, p, monkeypatch)
    await client.put(f"/api/intake-forms/{form_id}/items/1", headers=h, json={"answer": "3200 g"})
    from app.services.erasure import erase_patient
    await erase_patient(p.id, u, db)
    assert (await db.execute(select(HistoryFact))).first() is None
    assert (await db.execute(select(IntakeForm))).first() is None


async def test_a_document_passage_is_offered_and_becomes_a_fact_only_when_confirmed(client, db, monkeypatch):
    from app.core.encryption import encrypt_str
    from app.core.patient_keys import get_patient_kek
    from app.models.chat import DocumentChunk
    u, p, h = await _setup(db, client)
    doc = DocumentReference(patient_id=p.id, owner_id=u.id, file_name="letter.pdf")
    db.add(doc)
    await db.commit()
    vec = [0.1] * 768
    db.add(DocumentChunk(document_reference_id=doc.id, patient_id=p.id, chunk_index=0,
                         content=encrypt_str("Insured with AOK Bayern.", await get_patient_kek(db, p.id)),
                         embedding=vec))
    await db.commit()
    _CITES["Health insurance"] = "AOK"
    try:
        form_id, _ = await _read(client, db, h, p, monkeypatch)

        async def embed(texts, lang):
            return [vec for _ in texts]
        monkeypatch.setattr(chat_router, "_embed_queries", embed)
        await svc.read_form(uuid.UUID(form_id), db)
        items = (await client.get(f"/api/intake-forms/{form_id}", headers=h)).json()["items"]
    finally:
        del _CITES["Health insurance"]
    insurance = items[2]
    assert insurance["origin"] == "document" and insurance["confirmed"] is False
    assert insurance["document"]["file_name"] == "letter.pdf" and "AOK Bayern" in insurance["passage"]
    assert (await client.get(f"/api/patients/{p.id}/history-facts", headers=h)).json() == []

    await client.put(f"/api/intake-forms/{form_id}/items/2", headers=h, json={"confirm": True})
    facts = (await client.get(f"/api/patients/{p.id}/history-facts", headers=h)).json()
    assert len(facts) == 1 and facts[0]["source"] == "document" and facts[0]["document_reference_id"] == str(doc.id)
