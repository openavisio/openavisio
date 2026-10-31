"""ADR 058: diagnoses of all open Documents, grouped, decided once."""

import httpx
from sqlalchemy import select

from app.models.condition import Condition, ConditionSource
from app.models.proposal import Proposal
from tests.test_condition_sources import _auth, _doc, _setup

RECORD = "15q11-q13 Mikroduplikationssyndrom"


def _fake_group(monkeypatch, groups, calls=None):
    class _Resp:
        status_code = 200 if groups is not None else 500

        def json(self):
            return {"groups": groups}

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, **kw):
            assert url.endswith("/group")
            if calls is not None:
                calls.append(json)
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)


async def _letters(db, u, p):
    a = await _doc(db, u, p, "spz.pdf", "2025-03-01")
    b = await _doc(db, u, p, "ulm.pdf", "2026-02-01")
    a.extraction_json = {"diagnoses": [{"name": "Dup15q-Syndrom"}]}
    b.extraction_json = {"diagnoses": [{"name": "Dup15q syndrome"}, {"name": "Ataxie", "verification_status": "provisional"}]}
    old = await _doc(db, u, p, "tuebingen.pdf", "2024-01-01")
    old.verification_status = "verified"
    cond = Condition(patient_id=p.id, owner_id=u.id, code_display=RECORD, document_reference_id=old.id)
    cond.sources.append(ConditionSource(document_reference_id=old.id))
    db.add(cond)
    await db.commit()
    return a, b, old, cond


async def test_spellings_join_the_record_entry_in_one_decision(client, db, monkeypatch):
    u, p = await _setup(db)
    h = await _auth(client)
    a, b, old, cond = await _letters(db, u, p)
    _fake_group(monkeypatch, [[RECORD, "Dup15q-Syndrom", "Dup15q syndrome"], ["Ataxie"]])

    r = (await client.get(f"/api/patients/{p.id}/proposals/diagnoses", headers=h)).json()
    assert r["grouped_by_model"] is True
    dup = r["groups"][0]
    assert dup["record"]["name"] == RECORD and dup["suggested_name"] == RECORD
    assert {s["name"] for s in dup["spellings"]} == {"Dup15q-Syndrom", "Dup15q syndrome"}
    assert r["groups"][1]["spellings"][0]["provisional"] is True

    ids = [i for s in dup["spellings"] for i in s["proposal_ids"]]
    assert (await client.post(f"/api/patients/{p.id}/proposals/diagnoses/decide", headers=h, json={
        "proposal_ids": ids, "accept": True, "condition_id": dup["record"]["id"], "name": RECORD})).status_code == 204
    sources = set((await db.execute(select(ConditionSource.document_reference_id).where(
        ConditionSource.condition_id == cond.id))).scalars())
    assert sources == {old.id, a.id, b.id}
    assert len((await db.execute(select(Condition).where(Condition.is_deleted == False))).scalars().all()) == 1  # noqa: E712

    r = (await client.get(f"/api/patients/{p.id}/proposals/diagnoses", headers=h)).json()
    assert [s["name"] for g in r["groups"] for s in g["spellings"]] == ["Ataxie"]

    # the per-Document form no longer asks for it, and verifying the form keeps the citation
    detail = (await client.get(f"/api/documents/{b.id}/detail", headers=h)).json()
    assert [d["name"] for d in detail["extraction_json"]["diagnoses"]] == ["Ataxie"]
    assert (await client.post(f"/api/documents/{b.id}/verify", headers=h, json={"diagnoses": []})).status_code == 200
    assert b.id in set((await db.execute(select(ConditionSource.document_reference_id).where(
        ConditionSource.condition_id == cond.id))).scalars())
    statuses = {pr.index: pr.status for pr in (await db.execute(select(Proposal).where(
        Proposal.document_reference_id == b.id))).scalars()}
    assert statuses == {0: "accepted", 1: "rejected"}


async def test_a_rejected_group_writes_nothing_and_an_outage_groups_by_text(client, db, monkeypatch):
    u, p = await _setup(db)
    h = await _auth(client)
    await _letters(db, u, p)
    _fake_group(monkeypatch, None)

    r = (await client.get(f"/api/patients/{p.id}/proposals/diagnoses", headers=h)).json()
    assert r["grouped_by_model"] is False
    assert sorted(len(g["spellings"]) for g in r["groups"]) == [1, 1, 1]  # no text match among the three
    ataxie = next(g for g in r["groups"] if g["spellings"][0]["name"] == "Ataxie")
    await client.post(f"/api/patients/{p.id}/proposals/diagnoses/decide", headers=h, json={
        "proposal_ids": ataxie["spellings"][0]["proposal_ids"], "accept": False})
    names = {c.code_display for c in (await db.execute(select(Condition))).scalars()}
    assert names == {RECORD}
    # deciding it twice is refused, not silently repeated
    r = await client.post(f"/api/patients/{p.id}/proposals/diagnoses/decide", headers=h, json={
        "proposal_ids": ataxie["spellings"][0]["proposal_ids"], "accept": True})
    assert r.status_code == 409


async def test_a_new_group_takes_the_newest_spelling_and_stays_suspected_only_if_all_are(client, db, monkeypatch):
    u, p = await _setup(db)
    h = await _auth(client)
    await _letters(db, u, p)
    _fake_group(monkeypatch, [[RECORD], ["Dup15q-Syndrom"], ["Dup15q syndrome"], ["Ataxie"]])
    r = (await client.get(f"/api/patients/{p.id}/proposals/diagnoses", headers=h)).json()
    ataxie = next(g for g in r["groups"] if g["suggested_name"] == "Ataxie")
    assert ataxie["record"] is None
    await client.post(f"/api/patients/{p.id}/proposals/diagnoses/decide", headers=h, json={
        "proposal_ids": ataxie["spellings"][0]["proposal_ids"], "accept": True, "name": "Ataxie"})
    cond = (await db.execute(select(Condition).where(Condition.code_display == "Ataxie"))).scalar_one()
    assert cond.verification_status == "provisional"


async def test_a_decision_does_not_regroup_but_a_new_letter_does(client, db, monkeypatch):
    """The grouping is stored over all names; deciding must not cost another model call."""
    u, p = await _setup(db)
    h = await _auth(client)
    await _letters(db, u, p)
    calls = []
    _fake_group(monkeypatch, [[RECORD, "Dup15q-Syndrom", "Dup15q syndrome"], ["Ataxie"]], calls)
    r = (await client.get(f"/api/patients/{p.id}/proposals/diagnoses", headers=h)).json()
    assert sorted(calls[0]["record"] + calls[0]["names"]) == sorted([RECORD, "Dup15q-Syndrom", "Dup15q syndrome", "Ataxie"])
    ids = [i for s in r["groups"][0]["spellings"] for i in s["proposal_ids"]]
    await client.post(f"/api/patients/{p.id}/proposals/diagnoses/decide", headers=h, json={
        "proposal_ids": ids, "accept": True, "condition_id": r["groups"][0]["record"]["id"], "name": RECORD})
    await client.get(f"/api/patients/{p.id}/proposals/diagnoses", headers=h)
    assert len(calls) == 1

    c = await _doc(db, u, p, "neu.pdf", "2026-05-01")
    c.extraction_json = {"diagnoses": [{"name": "Epilepsie"}]}
    await db.commit()
    await client.get(f"/api/patients/{p.id}/proposals/diagnoses", headers=h)
    assert len(calls) == 2 and "Epilepsie" in calls[1]["names"]


async def test_the_list_counts_undecided_diagnoses_per_letter(client, db, monkeypatch):
    u, p = await _setup(db)
    h = await _auth(client)
    a, b, old, _ = await _letters(db, u, p)
    count = lambda docs: {d["id"]: d["open_diagnoses"] for d in docs}  # noqa: E731
    before = count((await client.get(f"/api/patients/{p.id}/documents", headers=h)).json())
    assert (before[str(a.id)], before[str(b.id)], before[str(old.id)]) == (1, 2, 0)  # from the letters, no review yet

    _fake_group(monkeypatch, [[RECORD, "Dup15q-Syndrom", "Dup15q syndrome"], ["Ataxie"]])
    r = (await client.get(f"/api/patients/{p.id}/proposals/diagnoses", headers=h)).json()
    ids = [i for s in r["groups"][0]["spellings"] for i in s["proposal_ids"]]
    await client.post(f"/api/patients/{p.id}/proposals/diagnoses/decide", headers=h, json={
        "proposal_ids": ids, "accept": True, "condition_id": r["groups"][0]["record"]["id"], "name": RECORD})
    after = count((await client.get(f"/api/patients/{p.id}/documents", headers=h)).json())
    assert (after[str(a.id)], after[str(b.id)]) == (0, 1)
