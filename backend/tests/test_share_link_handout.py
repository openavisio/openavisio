"""A Handout in a Document Share Link (ADR 048): frozen at creation, dated, carried
like the Documents, ended by revocation, erased with the link.
"""

from datetime import date

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.condition import Condition
from app.models.share_link import DocumentShareLinkHandout, DocumentShareLinkItem
from app.services.erasure import erase_patient
from tests.test_document_share_links import _auth, _document, _grant, _patient, _token_of, _user


def _link(patient_id, h, client, **handout):
    body = {"document_ids": [], "expiry_days": 30,
            "handout": {"variant": "doctors", "exclude": [], "lang": "de", **handout}}
    return client.post(f"/api/patients/{patient_id}/share-links", json=body, headers=h)


async def test_a_link_can_carry_a_handout_alone(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "ho1@t.com")
    patient = await _patient(db, owner)
    await _document(db, patient, owner)  # gives the patient a KEK
    h = await _auth(client, "ho1@t.com")

    r = await _link(patient.id, h, client)
    assert r.status_code == 201, r.text
    assert r.json()["handout"]["variant"] == "doctors"
    token = _token_of(r.json()["url"])

    view = (await client.get(f"/api/public/document-shares/{token}")).json()
    assert view["documents"] == []
    assert view["handout"]["variant"] == "doctors"
    assert view["handout"]["created_at"][:10] == date.today().isoformat()
    f = await client.get(f"/api/public/document-shares/{token}/handout/file")
    assert f.status_code == 200 and f.content.startswith(b"%PDF")
    assert f.headers["content-type"] == "application/pdf"


async def test_the_handout_is_frozen_at_creation(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "ho2@t.com")
    patient = await _patient(db, owner)
    await _document(db, patient, owner)
    h = await _auth(client, "ho2@t.com")
    token = _token_of((await _link(patient.id, h, client)).json()["url"])
    before = (await client.get(f"/api/public/document-shares/{token}/handout/file")).content

    db.add(Condition(patient_id=patient.id, owner_id=owner.id, code_display="Confirmed tomorrow"))
    await db.commit()

    after = (await client.get(f"/api/public/document-shares/{token}/handout/file")).content
    assert before == after


async def test_the_handout_is_stored_encrypted(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "ho3@t.com")
    patient = await _patient(db, owner)
    await _document(db, patient, owner)
    h = await _auth(client, "ho3@t.com")
    await _link(patient.id, h, client)
    row = (await db.execute(select(DocumentShareLinkHandout))).scalars().one()
    assert not row.pdf.startswith(b"%PDF") and row.encrypted_dek


async def test_documents_the_emergency_plan_points_at_go_along(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "ho4@t.com")
    patient = await _patient(db, owner)
    clinic_plan = await _document(db, patient, owner, name="notfallplan-klinik.pdf")
    other = await _document(db, patient, owner, name="other.pdf")
    h = await _auth(client, "ho4@t.com")
    await client.put(f"/api/patients/{patient.id}/emergency-plan", headers=h, json={
        "situations": [], "contacts": [], "notes": None, "document_ids": [str(clinic_plan.id), str(other.id)]})

    r = await _link(patient.id, h, client, variant="emergency", exclude=[f"plan-document:{other.id}"])
    assert r.status_code == 201, r.text
    assert [d["document_id"] for d in r.json()["documents"]] == [str(clinic_plan.id)]


async def test_staff_cannot_add_a_handout(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "ho5@t.com")
    mgr = await _user(db, "ho5m@t.com", role="manager")
    patient = await _patient(db, owner)
    await _grant(db, patient, mgr, "full")
    h = await _auth(client, "ho5m@t.com")
    assert (await _link(patient.id, h, client)).status_code == 403


async def test_an_unknown_variant_is_refused(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "ho6@t.com")
    patient = await _patient(db, owner)
    h = await _auth(client, "ho6@t.com")
    assert (await _link(patient.id, h, client, variant="nonsense")).status_code == 422


async def test_revoking_ends_access_and_access_is_audited(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "ho7@t.com")
    patient = await _patient(db, owner)
    await _document(db, patient, owner)
    h = await _auth(client, "ho7@t.com")
    r = (await _link(patient.id, h, client)).json()
    token = _token_of(r["url"])

    await client.get(f"/api/public/document-shares/{token}/handout/file?download=true")
    rows = (await db.execute(select(AuditLog).where(AuditLog.action == "accessed"))).scalars().all()
    assert [e.changes["event"] for e in rows] == ["handout_download"]

    await client.post(f"/api/patients/{patient.id}/share-links/{r['id']}/revoke", headers=h)
    assert (await client.get(f"/api/public/document-shares/{token}/handout/file")).status_code == 410


async def test_patient_erasure_deletes_frozen_handouts(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "ho8@t.com")
    patient = await _patient(db, owner)
    await _document(db, patient, owner)
    h = await _auth(client, "ho8@t.com")
    await _link(patient.id, h, client)
    await erase_patient(patient.id, owner, db)
    await db.commit()
    assert (await db.execute(select(DocumentShareLinkHandout))).first() is None
    assert (await db.execute(select(DocumentShareLinkItem))).first() is None
