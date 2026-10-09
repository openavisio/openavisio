"""Chat context assembly and the aiservice payload (ADR 038, #201)."""

from datetime import UTC, datetime

import httpx
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.calendar import CalendarEvent
from app.models.condition import Condition
from app.models.incident import Incident
from app.models.medication import MedicationStatement
from app.models.observation import Observation
from app.models.patient import Patient
from app.models.user import User
from app.routers import chat as chat_router


async def _setup(client: AsyncClient, db: AsyncSession, email: str):
    u = User(email=email, hashed_password=hash_password("Pass1!"), role="user", is_active=True,
             first_name="T", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    p = Patient(given_name="Emma", family_name="Test", birth_date="2024-01-15", created_by=u.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=u.id, access_level="admin",
                         granted_by_user_id=u.id, granted_at=datetime.now(UTC)))
    await db.commit()
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    return p, u, {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _set_org_language(db: AsyncSession, lang: str):
    from app.models.organization import Organization
    org = (await db.execute(select(Organization))).scalars().first()
    if org is None:
        db.add(Organization(name="Test", default_language=lang))
    else:
        org.default_language = lang
    await db.commit()


async def test_context_labels_follow_the_organization_language(client, db):
    """The labels went into the model context hardcoded German while
    Organization.default_language defaults to en, and the cap notice is quoted
    back to the reader by the prompt."""
    patient, user, _ = await _setup(client, db, "lang@test.com")
    db.add(CalendarEvent(patient_id=patient.id, owner_id=user.id, title="First steps",
                         category="milestone", start_at="2025-06-01"))
    await db.commit()

    await _set_org_language(db, "en")
    lines, _ = await chat_router._structured_context(patient.id, db, await chat_router._org_language(db))
    assert any(ln.startswith("Milestone |") for ln in lines), lines

    await _set_org_language(db, "de")
    lines, _ = await chat_router._structured_context(patient.id, db, await chat_router._org_language(db))
    assert any(ln.startswith("Meilenstein |") for ln in lines), lines


async def test_structured_context_lists_every_source_and_caps_the_long_ones(client, db):
    patient, user, _ = await _setup(client, db, "ctx1@test.com")
    db.add(CalendarEvent(patient_id=patient.id, owner_id=user.id, title="Freies Laufen",
                         category="milestone", developmental_domain="motor", start_at="2025-06-01"))
    for i in range(chat_router.APPOINTMENT_LIMIT + 5):
        db.add(CalendarEvent(patient_id=patient.id, owner_id=user.id, title=f"Termin {i}",
                             category="appointment", provider="Dr. Meier",
                             start_at=f"2025-01-{i % 28 + 1:02d}"))
    db.add(MedicationStatement(patient_id=patient.id, owner_id=user.id,
                               medication_display="Levetiracetam", effective_start="2024-02-03"))
    db.add(Condition(patient_id=patient.id, owner_id=user.id, code_display="Epilepsie",
                     onset_date_time="2024-01-05"))
    db.add(Incident(patient_id=patient.id, owner_id=user.id, incident_type="seizure",
                    severity="mild", occurred_at="2025-03-09"))
    await db.commit()

    await _set_org_language(db, "de")
    lines, months = await chat_router._structured_context(patient.id, db, "de")

    text = "\n".join(lines)
    assert "Meilenstein | 2025-06-01 | Freies Laufen" in text
    assert "Medikament | 2024-02-03 | Levetiracetam" in text
    assert "Diagnose | 2024-01-05 | Epilepsie" in text
    assert "Vorfall | 2025-03-09 | seizure" in text
    # capped, and the cap is disclosed so the answer can say so
    assert len([ln for ln in lines if ln.startswith("Termin |")]) == chat_router.APPOINTMENT_LIMIT
    assert any("HINWEIS" in ln and "Termine" in ln for ln in lines)
    # only months that really hold entries get linked
    assert months == ["2025-01", "2025-03", "2025-06"]


async def test_lab_values_are_capped_per_parameter_not_overall(client, db):
    """Thousands of rows do not fit the context, but a rarely-measured parameter
    must not be pushed out by a weekly-measured one (#200)."""
    patient, user, _ = await _setup(client, db, "ctx4@test.com")
    for i in range(chat_router.LAB_PER_CODE + 4):
        db.add(Observation(patient_id=patient.id, owner_id=user.id, code="VPA",
                           code_display="Valproat", value_quantity=60 + i, value_unit="mg/l",
                           ref_low=50, ref_high=100, effective_date_time=f"2025-0{i + 1}-01"))
    db.add(Observation(patient_id=patient.id, owner_id=user.id, code="TSH", code_display="TSH",
                       value_quantity=2.5, value_unit="mU/l", effective_date_time="2023-01-01"))
    await db.commit()

    lines, months = await chat_router._structured_context(patient.id, db, "de")

    vpa = [ln for ln in lines if "Valproat" in ln]
    assert len(vpa) == chat_router.LAB_PER_CODE, vpa
    # no reference range: value plus range on one line invites the judgement the
    # chat may not make (#113)
    assert vpa[0] == "Laborwert | 2025-07-01 | Valproat | 66 mg/l"
    # the rare parameter survives, and the cap is disclosed
    assert any("TSH | 2.5 mU/l" in ln for ln in lines), lines
    assert any("HINWEIS" in ln and "Laborwerten" in ln for ln in lines)
    # labs are not calendar entries, so they link no months
    assert months == []


async def test_aiservice_payload_matches_its_schema(client, db, monkeypatch):
    """The field was `context` while aiservice demanded `context_chunks`: every
    answer was a 422 and the user only ever saw "AI service unavailable" (#201)."""
    patient, _, headers = await _setup(client, db, "ctx2@test.com")
    sent: dict = {}

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
                sent.update(json)
            return _Resp(json or {})

    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    r = await client.post(f"/api/patients/{patient.id}/chat", json={"question": "Wann war der letzte Termin?"},
                          headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["answer"] == "Ich sehe folgende Einträge."
    assert set(sent) == {"question", "context_chunks", "history", "model"}
    assert isinstance(sent["context_chunks"], list)


async def test_an_outage_is_a_503_and_writes_nothing(client, db, monkeypatch):
    """"AI service unavailable." used to be stored as an assistant message under
    the patient KEK — an outage written into the record as if it were said."""
    patient, _, headers = await _setup(client, db, "ctx3@test.com")

    class _Dead:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            raise OSError("connection refused")

    monkeypatch.setattr(httpx, "AsyncClient", _Dead)

    r = await client.post(f"/api/patients/{patient.id}/chat", json={"question": "Wann?"}, headers=headers)
    assert r.status_code == 503, r.text

    h = await client.get(f"/api/patients/{patient.id}/chat/history", headers=headers)
    assert h.json()["messages"] == []


def test_judgement_is_stripped_from_the_answer():
    """The model ignores the no-judgement rule on the question a caregiver asks
    first. These are its real answers from the test server (#208)."""
    from app.routers.chat import _strip_judgement

    verdict = (
        "Laut dem vorliegenden Laborbefund liegt der Referenzbereich bei 200-445.\n"
        "- **13.01.2026:** 294 → ✅ im Normbereich\n"
        "- **31.03.2023:** 477 → ⚠️ leicht oberhalb des Referenzbereichs\n"
        "**Fazit:** Die aktuellen Werte sind völlig in Ordnung."
    )
    out = _strip_judgement(verdict, "de")
    for gone in ("Referenzbereich", "Normbereich", "in Ordnung", "✅", "⚠️"):
        assert gone not in out, out
    assert "beurteilen" in out  # nothing survived, so it declines

    advice = (
        "Die Werte wurden am 09.12.2025 (40 mg/l) und am 13.01.2026 (41 mg/l) bestimmt.\n"
        "Beide Werte liegen unter dem therapeutischen Zielbereich von 50-100 mg/l.\n"
        "Empfehlung: Eine Dosisanpassung wäre sinnvoll."
    )  # the listing line survives, the two verdict lines do not
    out = _strip_judgement(advice, "de")
    assert "09.12.2025 (40 mg/l)" in out  # the listing survives
    assert "Dosisanpassung" not in out and "therapeutischen Zielbereich" not in out
    assert "entfernt" in out  # and the reader is told why

    # a heading is not left standing over the paragraph that went with it
    orphan = "Werte:\n- 22.06.2026: 316 G/l\n\n**Bewertung:**\nAlle Werte sind normal."
    out = _strip_judgement(orphan, "de")
    assert "Bewertung" not in out and "316 G/l" in out, out

    plain = "Laut den vorliegenden Unterlagen wird Ergenyl seit dem 11.07.2026 verabreicht."
    assert _strip_judgement(plain, "de") == plain
