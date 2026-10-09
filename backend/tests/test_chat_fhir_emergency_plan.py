"""Care Notes and the Emergency Plan in the chat and the FHIR export (ADR 048)."""

import httpx
from httpx import AsyncClient

from app.models.medication import MedicationStatement
from app.routers import chat as chat_router
from tests.test_chat_context import _set_org_language, _setup

PLAN = {
    "situations": [{"trigger": "Seizure longer than 3 minutes", "steps": [
        {"text": "Give rescue medication XYZ-STEP", "medication_id": None}]}],
    "contacts": [{"name": "Dr. Weber"}],
    "notes": "PLAN-NOTE-MARKER",
    "document_ids": [],
}


def _fake_aiservice(monkeypatch, sent: dict, *, forbid_chat=False):
    class _Resp:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            if "texts" in self._payload:
                return {"embeddings": [[0.0] * 768]}
            return {"answer": "Ich sehe folgende Einträge."}

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, **kw):
            if url.endswith("/chat"):
                assert not forbid_chat, "the model must not be asked"
                sent.update(json)
            return _Resp(json or {})

    monkeypatch.setattr(httpx, "AsyncClient", _Client)


async def test_care_notes_are_in_the_context_with_their_heading(client: AsyncClient, db):
    patient, _, h = await _setup(client, db, "care-ctx@test.com")
    await client.put(f"/api/patients/{patient.id}/care-notes", headers=h, json={"sleep": "Night light on"})
    await _set_org_language(db, "de")
    lines, _ = await chat_router._structured_context(patient.id, db, "de")
    assert any(ln.startswith("Alltagsinfo |") and "Schlafen" in ln and "Night light on" in ln for ln in lines), lines


async def test_the_emergency_plan_never_enters_the_context(client: AsyncClient, db, monkeypatch):
    patient, _, h = await _setup(client, db, "plan-ctx@test.com")
    await client.put(f"/api/patients/{patient.id}/emergency-plan", headers=h, json=PLAN)
    sent: dict = {}
    _fake_aiservice(monkeypatch, sent)
    r = await client.post(f"/api/patients/{patient.id}/chat", headers=h, json={"question": "Wann war der letzte Termin?"})
    assert r.status_code == 200, r.text
    context = "\n".join(sent["context_chunks"])
    assert "XYZ-STEP" not in context and "PLAN-NOTE-MARKER" not in context
    assert r.json()["emergency_plan"] is False


async def test_an_emergency_question_gets_the_fixed_pointer_not_the_model(client: AsyncClient, db, monkeypatch):
    """A misquoted dose in a chat answer is the one mistake that must not happen."""
    patient, _, h = await _setup(client, db, "plan-q@test.com")
    await _set_org_language(db, "de")
    _fake_aiservice(monkeypatch, {}, forbid_chat=True)
    for question in ("Was mache ich im Notfall?", "Wie viel Notfallmedikament geben wir?", "What is the emergency plan?"):
        r = await client.post(f"/api/patients/{patient.id}/chat", headers=h, json={"question": question})
        assert r.status_code == 200, r.text
        assert r.json()["emergency_plan"] is True
        assert r.json()["answer"] == chat_router._LABELS["de"]["emergency"]
    history = (await client.get(f"/api/patients/{patient.id}/chat/history", headers=h)).json()["messages"]
    assert history[-1]["content"] == chat_router._LABELS["de"]["emergency"]


async def test_the_fhir_export_carries_the_plan_as_a_careplan(client: AsyncClient, db):
    patient, user, h = await _setup(client, db, "plan-fhir@test.com")
    med = MedicationStatement(patient_id=patient.id, owner_id=user.id, medication_display="Buccolam")
    db.add(med)
    await db.commit()
    plan = {**PLAN, "situations": [{"trigger": "Seizure longer than 3 minutes", "steps": [
        {"text": "Give rescue medication", "medication_id": str(med.id)}, {"text": "Call 112"}]}]}
    await client.put(f"/api/patients/{patient.id}/emergency-plan", headers=h, json=plan)

    bundle = (await client.get(f"/api/patients/{patient.id}/export/fhir", headers=h)).json()
    care_plans = [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "CarePlan"]
    assert len(care_plans) == 1
    cp = care_plans[0]
    assert cp["status"] == "active" and cp["intent"] == "plan" and cp["subject"]["reference"] == f"urn:uuid:{patient.id}"
    assert cp["activity"][0]["detail"]["description"] == "Seizure longer than 3 minutes: 1. Give rescue medication 2. Call 112"
    assert {"reference": f"urn:uuid:{med.id}"} in cp["supportingInfo"]
    assert any("PLAN-NOTE-MARKER" in n["text"] for n in cp["note"])


def test_the_emergency_keywords_catch_actions_not_history():
    hit = chat_router._is_emergency
    for q in ("Was mache ich im Notfall?", "Was steht im Notfallplan?", "What is the emergency plan?",
              "Was mache ich, wenn sie einen langen Anfall hat?", "What do I do if she has a long seizure?",
              "Wie viel gebe ich bei einem Krampfanfall?", "Soll ich 112 anrufen?", "Sie atmet nicht"):
        assert hit(q, ()), q
    for q in ("Wann war der letzte Anfall?", "Wann war der letzte Notfall-Termin?", "Thrombozyten 112?",
              "Wann war der letzte Termin?"):
        assert not hit(q, ()), q


def test_a_medication_the_plan_points_at_counts_as_an_emergency_question():
    assert chat_router._is_emergency("Wie viel Buccolam geben wir?", ("Buccolam",))
    assert not chat_router._is_emergency("Wann haben wir Levetiracetam angefangen?", ("Buccolam",))


async def test_a_follow_up_after_the_pointer_does_not_carry_the_emergency_question(client: AsyncClient, db, monkeypatch):
    patient, _, h = await _setup(client, db, "plan-follow@test.com")
    sent: dict = {}
    _fake_aiservice(monkeypatch, sent)
    await client.post(f"/api/patients/{patient.id}/chat", headers=h, json={"question": "Was tun im Notfall?"})
    r = await client.post(f"/api/patients/{patient.id}/chat", headers=h, json={"question": "und wie viel davon?"})
    assert r.status_code == 200
    assert all("Notfall" not in m["content"] for m in sent["history"]), sent["history"]


async def test_history_marks_the_pointer_so_the_link_survives_a_reload(client: AsyncClient, db, monkeypatch):
    patient, _, h = await _setup(client, db, "plan-hist@test.com")
    _fake_aiservice(monkeypatch, {}, forbid_chat=True)
    await client.post(f"/api/patients/{patient.id}/chat", headers=h, json={"question": "Was tun im Notfall?"})
    messages = (await client.get(f"/api/patients/{patient.id}/chat/history", headers=h)).json()["messages"]
    assert [m["emergency_plan"] for m in messages] == [False, True]


async def test_the_careplan_only_points_at_what_the_bundle_holds(client: AsyncClient, db):
    patient, user, h = await _setup(client, db, "plan-fhir2@test.com")
    med = MedicationStatement(patient_id=patient.id, owner_id=user.id, medication_display="Gone")
    db.add(med)
    await db.commit()
    await client.put(f"/api/patients/{patient.id}/emergency-plan", headers=h, json={
        "situations": [{"trigger": "x", "steps": [{"text": "y", "medication_id": str(med.id)}]}],
        "contacts": [], "notes": None, "document_ids": []})
    await client.delete(f"/api/medications/{med.id}", headers=h)
    bundle = (await client.get(f"/api/patients/{patient.id}/export/fhir", headers=h)).json()
    cp = next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "CarePlan")
    assert "supportingInfo" not in cp and "note" not in cp
