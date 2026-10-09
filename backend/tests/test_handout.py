"""The doctor Handout (ADR 048): only confirmed entries, as recorded, suspected stays
marked, and the User may leave out single entries.
"""

from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.patient_keys import ensure_patient_kek
from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.calendar import CalendarEvent
from app.models.condition import Condition
from app.models.document import DocumentReference
from app.models.incident import Incident
from app.models.medication import MedicationStatement
from app.models.observation import Observation
from app.models.patient import Patient
from app.models.user import User
from app.services.handout import render_html

TODAY = date.today()


def _ago(days: int) -> str:
    return (TODAY - timedelta(days=days)).isoformat()


async def _setup(db: AsyncSession, email="infoblatt@t.com"):
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
    await db.commit()
    await ensure_patient_kek(db, p.id)
    await db.commit()
    return u, p


async def _auth(client: AsyncClient, email="infoblatt@t.com") -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _record(db, u, p):
    """A small record: confirmed entries of every doctor section, plus an unconfirmed
    proposal tied to a Document nobody has verified yet."""
    verified = DocumentReference(patient_id=p.id, owner_id=u.id, description="Arztbrief Neuropädiatrie",
                                 issued_date=TODAY - timedelta(days=30), detected_provider="Uniklinik",
                                 verification_status="verified")
    pending = DocumentReference(patient_id=p.id, owner_id=u.id, description="Unread letter",
                                issued_date=TODAY - timedelta(days=5), verification_status="extracted",
                                detected_provider="Provider read by the model",
                                extraction_json={"diagnoses": [{"name": "Proposed in extraction"}]})
    db.add_all([verified, pending])
    await db.commit()
    own = dict(patient_id=p.id, owner_id=u.id)
    db.add_all([
        Condition(**own, code_display="Fokale Epilepsie", clinical_status="active", document_reference_id=verified.id),
        Condition(**own, code_display="Rett-Syndrom", clinical_status="active", verification_status="provisional"),
        Condition(**own, code_display="Penicillin", clinical_status="active", category="allergy"),
        Condition(**own, code_display="Bronchitis", clinical_status="resolved"),
        Condition(**own, code_display="Marked obsolete", clinical_status="inactive"),
        Condition(**own, code_display="Refuted", clinical_status="active", verification_status="refuted"),
        Condition(**own, code_display="Unconfirmed proposal", clinical_status="active", document_reference_id=pending.id),
        MedicationStatement(**own, medication_display="Levetiracetam", dosage_text="2x 250 mg"),
        MedicationStatement(**own, medication_display="Old drug", status="stopped"),
        Observation(**own, code="body-weight", code_display="Gewicht", category="measurement",
                    value_quantity=18.0, value_unit="kg", effective_date_time=_ago(100)),
        Observation(**own, code="body-weight", code_display="Gewicht", category="measurement",
                    value_quantity=18.4, value_unit="kg", effective_date_time=_ago(10)),
        Observation(**own, code="hb", code_display="Hämoglobin", category="lab",
                    value_quantity=11.0, value_unit="g/dl", effective_date_time=_ago(200)),
        Observation(**own, code="hb", code_display="Hämoglobin", category="lab",
                    value_quantity=12.5, value_unit="g/dl", reference_range="11-14", effective_date_time=_ago(20)),
        Incident(**own, incident_type="seizure", incident_type_display="Anfall", occurred_at=_ago(3)),
        Incident(**own, incident_type="seizure", incident_type_display="Anfall", occurred_at=_ago(40)),
        Incident(**own, incident_type="seizure", incident_type_display="Anfall", occurred_at=_ago(200)),
        CalendarEvent(**own, title="EEG", start_at=_ago(60), provider="Uniklinik"),
        CalendarEvent(**own, title="Cancelled visit", start_at=_ago(30), status="cancelled"),
        CalendarEvent(**own, title="Long ago", start_at=_ago(500)),
        CalendarEvent(**own, title="Next visit", start_at=(TODAY + timedelta(days=10)).isoformat()),
    ])
    await db.commit()
    return verified, pending


def _texts(body, key):
    return [e["text"] for s in body["sections"] if s["key"] == key for e in s["entries"]]


async def test_the_doctor_handout_holds_the_confirmed_record(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    await _record(db, u, p)

    r = await client.get(f"/api/patients/{p.id}/handouts/doctors", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["patient"] == {"name": "Lena Test", "birth_date": "2019-05-14"}
    assert _texts(body, "allergies") == ["Penicillin"]
    assert sorted(_texts(body, "diagnoses_active")) == ["Fokale Epilepsie", "Rett-Syndrom"]
    assert _texts(body, "diagnoses_resolved") == ["Bronchitis"]
    assert _texts(body, "medications") == ["Levetiracetam"]
    assert _texts(body, "weight") == ["18.4 kg"]
    assert _texts(body, "lab_results") == ["Hämoglobin"]
    assert _texts(body, "incidents") == ["Anfall"]
    incidents = next(s for s in body["sections"] if s["key"] == "incidents")["entries"]
    assert incidents[0]["detail"] == "2×"  # the one 200 days ago is outside 3 months
    assert _texts(body, "events") == ["EEG"]  # past 12 months only
    assert _texts(body, "documents") == ["Arztbrief Neuropädiatrie"]


async def test_an_unconfirmed_proposal_never_reaches_the_handout(client: AsyncClient, db: AsyncSession):
    """Neither the entry tied to an unverified Document nor that Document itself."""
    u, p = await _setup(db)
    h = await _auth(client)
    await _record(db, u, p)
    body = (await client.get(f"/api/patients/{p.id}/handouts/doctors", headers=h)).json()
    everything = str(body)
    for text in ("Unconfirmed proposal", "Unread letter", "Proposed in extraction", "Provider read by the model"):
        assert text not in everything


async def test_a_documents_sender_is_only_ever_the_assigned_correspondent(client: AsyncClient, db: AsyncSession):
    """detected_provider is read by the model and never confirmed."""
    u, p = await _setup(db)
    h = await _auth(client)
    await _record(db, u, p)
    body = (await client.get(f"/api/patients/{p.id}/handouts/doctors", headers=h)).json()
    doc = next(s for s in body["sections"] if s["key"] == "documents")["entries"][0]
    assert doc["detail"] is None and "Uniklinik" not in str(doc)


async def test_obsolete_refuted_and_cancelled_entries_stay_out(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    await _record(db, u, p)
    everything = str((await client.get(f"/api/patients/{p.id}/handouts/doctors", headers=h)).json())
    for text in ("Marked obsolete", "Refuted", "Cancelled visit"):
        assert text not in everything


async def test_every_doctor_section_but_the_carer_updates_is_preselected(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    body = (await client.get(f"/api/patients/{p.id}/handouts/doctors", headers=h)).json()
    assert {s["key"] for s in body["sections"] if not s["preselected"]} == {"carer_updates"}  # ADR 049


async def test_a_suspected_diagnosis_stays_marked(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    await _record(db, u, p)
    body = (await client.get(f"/api/patients/{p.id}/handouts/doctors", headers=h)).json()
    dx = {e["text"]: e for s in body["sections"] if s["key"] == "diagnoses_active" for e in s["entries"]}
    assert dx["Rett-Syndrom"]["suspected"] is True
    assert dx["Fokale Epilepsie"]["suspected"] is False
    html = render_html(body, "de")
    assert "Rett-Syndrom" in html and "Verdacht" in html


async def test_the_pdf_leaves_out_what_the_user_excluded(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    await _record(db, u, p)
    body = (await client.get(f"/api/patients/{p.id}/handouts/doctors", headers=h)).json()
    bronchitis = next(e["id"] for s in body["sections"] for e in s["entries"] if e["text"] == "Bronchitis")

    r = await client.post(f"/api/patients/{p.id}/handouts/doctors/pdf", headers=h,
                          json={"exclude": [bronchitis], "lang": "en"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_only_headings_are_translated():
    body = {"variant": "doctors", "patient": {"name": "Lena Test", "birth_date": "2019-05-14"},
            "sections": [{"key": "diagnoses_active", "entries": [
                {"id": "x", "text": "Fokale Epilepsie", "detail": None, "date": None, "suspected": False}]}]}
    de, en = render_html(body, "de"), render_html(body, "en")
    assert "Diagnosen" in de and "Diagnoses" in en
    assert "Fokale Epilepsie" in de and "Fokale Epilepsie" in en
    assert "14.05.2019" in de and "2019-05-14" in en


def test_excluded_entries_are_dropped_and_empty_sections_vanish():
    body = {"variant": "doctors", "patient": {"name": "Lena Test", "birth_date": None},
            "sections": [{"key": "diagnoses_resolved", "entries": [
                {"id": "x", "text": "Bronchitis", "detail": None, "date": None, "suspected": False}]}]}
    html = render_html(body, "de", exclude={"x"})
    assert "Bronchitis" not in html and "Abgeheilt" not in html


async def test_without_access_there_is_no_handout(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    await _setup(db, email="stranger3@t.com")
    h = await _auth(client, email="stranger3@t.com")
    assert (await client.get(f"/api/patients/{p.id}/handouts/doctors", headers=h)).status_code in (403, 404)
    r = await client.post(f"/api/patients/{p.id}/handouts/doctors/pdf", headers=h, json={"exclude": [], "lang": "de"})
    assert r.status_code in (403, 404)


async def test_an_unknown_variant_is_not_found(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    assert (await client.get(f"/api/patients/{p.id}/handouts/nonsense", headers=h)).status_code == 404


def test_a_free_text_date_cannot_inject_html():
    body = {"variant": "doctors", "patient": {"name": "Lena Test", "birth_date": "<b>x</b>"},
            "sections": [{"key": "events", "entries": [
                {"id": "x", "text": "EEG", "detail": None, "date": '<img src="http://192.0.2.1/x">', "suspected": False}]}]}
    html = render_html(body, "de")
    assert "<img" not in html and "<b>x</b>" not in html


def test_the_pdf_renderer_fetches_nothing():
    from app.services.handout import _no_fetch
    import pytest
    with pytest.raises(ValueError):
        _no_fetch("http://192.0.2.1/x")
