"""#69: canonical code + reference-range parsing on manual observation create."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User


async def _setup(db: AsyncSession):
    u = User(email="lab@t.com", hashed_password=hash_password("Pass1!"), role="user",
             is_active=True, first_name="T", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    p = Patient(given_name="Emma", family_name="Test", birth_date="2015-04-02", created_by=u.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=u.id, access_level="admin", granted_at=datetime.now(UTC)))
    await db.commit()
    return u, p


async def _auth(client: AsyncClient) -> dict:
    r = await client.post("/api/auth/login", json={"email": "lab@t.com", "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_manual_create_assigns_canonical_code_and_parses_range(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    obs = (await client.post(f"/api/patients/{p.id}/observations", json={
        "category": "lab", "code_display": "Hämoglobin", "value_quantity": 12.1,
        "value_unit": "g/dL", "reference_range": "13.5-17.2", "effective_date_time": "2026-07-01",
    }, headers=h)).json()

    assert obs["code"] == "hemoglobin"          # aliased to canonical slug
    assert obs["ref_low"] == 13.5               # parsed from the raw range
    assert obs["ref_high"] == 17.2              # value 12.1 < ref_low → out-of-range (low), computed in UI


async def test_delete_document_cascades_to_its_observations(client: AsyncClient, db: AsyncSession):
    from app.models.document import DocumentReference
    from app.models.observation import Observation

    u, p = await _setup(db)
    h = await _auth(client)
    doc = DocumentReference(patient_id=p.id, owner_id=u.id, file_name="lab.pdf")
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    extracted = Observation(patient_id=p.id, owner_id=u.id, document_reference_id=doc.id,
                            category="lab", code_display="Leukozyten", value_quantity=9.5)
    manual = Observation(patient_id=p.id, owner_id=u.id, category="lab",
                         code_display="Manual", value_quantity=1.0)  # no document → must survive
    db.add_all([extracted, manual])
    await db.commit()

    r = await client.delete(f"/api/documents/{doc.id}", headers=h)
    assert r.status_code == 204

    rows = (await client.get(f"/api/patients/{p.id}/observations", params={"category": "lab"}, headers=h)).json()
    displays = [o["code_display"] for o in rows]
    assert "Leukozyten" not in displays   # extracted value removed with the document
    assert "Manual" in displays           # manual entry untouched


async def test_duplicate_upload_blocked(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)

    def file():
        return {"file": ("report.pdf", b"%PDF-1.4 duplicate test", "application/pdf")}

    r1 = await client.post(f"/api/patients/{p.id}/documents/upload", files=file(), headers=h)
    assert r1.status_code == 201
    r2 = await client.post(f"/api/patients/{p.id}/documents/upload", files=file(), headers=h)
    assert r2.status_code == 409

    # deleting the first lets the same file be uploaded again
    doc_id = r1.json()["id"]
    assert (await client.delete(f"/api/documents/{doc_id}", headers=h)).status_code == 204
    r3 = await client.post(f"/api/patients/{p.id}/documents/upload", files=file(), headers=h)
    assert r3.status_code == 201


async def test_canonical_panel_from_analyte(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    # no panel given — resolved from the analyte's canonical vocabulary (ADR 029)
    obs = (await client.post(f"/api/patients/{p.id}/observations", json={
        "category": "lab", "code_display": "Kreatinin", "value_quantity": 0.9, "value_unit": "mg/dl",
    }, headers=h)).json()
    assert obs["code"] == "creatinine"
    assert obs["panel"] == "Klinische Chemie"


async def test_unknown_param_keeps_null_code(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    obs = (await client.post(f"/api/patients/{p.id}/observations", json={
        "category": "lab", "code_display": "Irgendein Speziallabor XYZ", "value_quantity": 30.0, "value_unit": "ng/mL",
    }, headers=h)).json()

    assert obs["code"] is None                  # not in the vocabulary → grouped by display name
