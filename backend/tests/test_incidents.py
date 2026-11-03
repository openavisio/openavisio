"""ADR 062: an Incident records what happened; only who entered it or an admin changes it."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.dose import Dose
from tests.test_carer_updates import _auth, _setup
from tests.test_doses import _med, _member

BODY = {"incident_type": "seizure", "incident_type_display": "Absence", "occurred_at": "2026-11-03T07:40",
        "duration_minutes": 3, "actions_taken": "Buccolam", "note": None}


async def test_record_list_and_who_may_change_it(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db, "inc@t.com")
    await _member(db, p, "oma@t.com", "contribute")
    await _member(db, p, "opa@t.com", "view")
    admin, oma, opa = (await _auth(client, "inc@t.com"), await _auth(client, "oma@t.com"), await _auth(client, "opa@t.com"))
    url = f"/api/patients/{p.id}/incidents"

    assert (await client.post(url, headers=opa, json=BODY)).status_code == 404
    assert (await client.post(url, headers=oma, json={**BODY, "incident_type": "weather"})).status_code == 422
    assert (await client.post(url, headers=oma, json={**BODY, "occurred_at": "2026-11-03"})).status_code == 422
    mine = (await client.post(url, headers=oma, json=BODY)).json()
    theirs = (await client.post(url, headers=admin, json={**BODY, "occurred_at": "2026-11-03T09:00"})).json()
    assert mine["entered_by"] == "Oma" and mine["can_edit"]

    listed = (await client.get(url, headers=opa)).json()
    assert [i["id"] for i in listed] == [theirs["id"], mine["id"]] and not any(i["can_edit"] for i in listed)

    assert (await client.put(f"/api/incidents/{theirs['id']}", headers=oma, json=BODY)).status_code == 403
    assert (await client.delete(f"/api/incidents/{theirs['id']}", headers=oma)).status_code == 403
    # a full replace: a field can be emptied again
    r = await client.put(f"/api/incidents/{mine['id']}", headers=oma, json={**BODY, "actions_taken": None})
    assert r.status_code == 200 and r.json()["actions_taken"] is None
    assert (await client.delete(f"/api/incidents/{mine['id']}", headers=admin)).status_code == 204
    assert [i["id"] for i in (await client.get(url, headers=opa)).json()] == [theirs["id"]]
    actions = (await db.execute(select(AuditLog.action).where(AuditLog.entity_type == "Incident"))).scalars().all()
    assert sorted(actions) == ["deleted", "updated"]


async def test_deleting_an_incident_keeps_its_doses(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db, "inc2@t.com")
    m = await _med(db, u, p, name="Buccolam")
    h = await _auth(client, "inc2@t.com")
    inc = (await client.post(f"/api/patients/{p.id}/incidents", headers=h, json=BODY)).json()
    dose = (await client.post(f"/api/patients/{p.id}/doses", headers=h, json=[
        {"medication_id": str(m.id), "given_at": "2026-11-03T07:45", "incident_id": inc["id"]}])).json()[0]
    assert [d["id"] for d in (await client.get(f"/api/patients/{p.id}/doses?incident_id={inc['id']}", headers=h)).json()] == [dose["id"]]

    await client.post(f"/api/patients/{p.id}/doses", headers=h, json=[{"medication_id": str(m.id), "given_at": "2026-11-03T12:00"}])
    linked = (await client.get(f"/api/patients/{p.id}/doses?with_incident=true", headers=h)).json()
    assert [d["id"] for d in linked] == [dose["id"]]

    assert (await client.delete(f"/api/incidents/{inc['id']}", headers=h)).status_code == 204
    row = await db.get(Dose, dose["id"])
    await db.refresh(row)
    assert not row.is_deleted and row.incident_id is None
