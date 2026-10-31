"""ADR 058: letterhead variants of one Correspondent become one Correspondent in one decision."""

from sqlalchemy import select

from app.models.correspondent import Correspondent
from app.models.document import DocumentReference
from app.models.organization import Organization
from tests.test_condition_sources import _auth, _doc, _setup
from tests.test_proposal_review import _fake_group

DIAK = "DIAK Klinikum Landkreis Schwäbisch Hall gGmbH"


async def _letters(db, u, p):
    db.add(Organization(name="Haushalt"))
    docs = []
    for name, sender in (("a.pdf", DIAK), ("b.pdf", DIAK), ("c.pdf", "Diakonie-Klinikum Schwäbisch Hall gGmbH"),
                         ("d.pdf", "AOK Baden-Württemberg")):
        d = await _doc(db, u, p, name, "2025-01-01")
        d.detected_provider = sender
        docs.append(d)
    await db.commit()
    return docs


async def test_two_spellings_get_one_new_correspondent_and_leave_the_review(client, db, monkeypatch):
    u, p = await _setup(db)
    h = await _auth(client)
    a, b, c, aok = await _letters(db, u, p)
    calls = []
    _fake_group(monkeypatch, [[DIAK, "Diakonie-Klinikum Schwäbisch Hall gGmbH"], ["AOK Baden-Württemberg"]], calls)

    r = (await client.get(f"/api/patients/{p.id}/proposals/correspondents", headers=h)).json()
    assert calls[0]["kind"] == "correspondent"
    diak = r["groups"][0]
    assert diak["record"] is None and diak["suggested_name"] == "Diakonie-Klinikum Schwäbisch Hall gGmbH"  # the shortest
    ids = [i for s in diak["spellings"] for i in s["document_ids"]]
    assert sorted(ids) == sorted(str(d.id) for d in (a, b, c))

    assert (await client.post(f"/api/patients/{p.id}/proposals/correspondents/decide", headers=h, json={
        "document_ids": ids, "name": "DIAK Klinikum Schwäbisch Hall"})).status_code == 204
    corr = (await db.execute(select(Correspondent))).scalars().all()
    assert [x.name for x in corr] == ["DIAK Klinikum Schwäbisch Hall"]
    assigned = {d.id: d.correspondent_id for d in (await db.execute(select(DocumentReference))).scalars()}
    assert assigned[a.id] == assigned[b.id] == assigned[c.id] == corr[0].id and assigned[aok.id] is None

    r = (await client.get(f"/api/patients/{p.id}/proposals/correspondents", headers=h)).json()
    assert [g["suggested_name"] for g in r["groups"]] == ["AOK Baden-Württemberg"]


async def test_an_existing_correspondent_is_reused_not_duplicated(client, db, monkeypatch):
    u, p = await _setup(db)
    h = await _auth(client)
    *_, aok = await _letters(db, u, p)
    org = (await db.execute(select(Organization))).scalar_one()
    db.add(Correspondent(name="AOK Baden-Württemberg", organization_id=org.id))
    await db.commit()
    _fake_group(monkeypatch, [[DIAK, "Diakonie-Klinikum Schwäbisch Hall gGmbH"], ["AOK Baden-Württemberg"]])
    r = (await client.get(f"/api/patients/{p.id}/proposals/correspondents", headers=h)).json()
    g = next(x for x in r["groups"] if x["record"])
    await client.post(f"/api/patients/{p.id}/proposals/correspondents/decide", headers=h, json={
        "document_ids": g["spellings"][0]["document_ids"], "name": g["record"]["name"],
        "correspondent_id": g["record"]["id"]})
    assert len((await db.execute(select(Correspondent))).scalars().all()) == 1
    await db.refresh(aok)
    assert aok.correspondent_id is not None
