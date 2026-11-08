"""#465, ADR 063: a therapy report's Abilities and Test Attempts are Proposals, decided once."""

from sqlalchemy import select

from app.models.development import Ability, AbilityObservation, TestAttempt
from app.models.proposal import Proposal
from app.routers import chat as chat_router
from app.workers import pipeline
from tests.test_condition_sources import _auth, _doc, _setup
from tests.test_carer_updates import _correspondent
from tests.test_proposal_review import _fake_group

SPOON = "Lena isst inzwischen selbstständig mit dem Löffel."


async def _reports(db, u, p):
    spz = await _correspondent(db, "SPZ Schwäbisch Hall")
    a = await _doc(db, u, p, "ergo.pdf", "2026-05-12")
    b = await _doc(db, u, p, "kita.pdf", "2026-06-30")
    a.correspondent_id = spz.id
    a.extraction_json = {"abilities": [
        {"name": "Mit dem Löffel essen", "works": True, "with_help": False, "place": "therapy", "domain": "daily_living",
         "quote": SPOON}],
        "test_attempts": [{"test_name": "SON-R 2-8", "outcome": "stopped", "date": None, "reason": "nach 20 Minuten erschöpft"}]}
    b.extraction_json = {"abilities": [
        {"name": "Isst mit Löffel", "works": False, "with_help": True, "place": "kita_school", "domain": None,
         "quote": "Beim Mittagessen braucht Lena Hilfe mit dem Löffel."}]}
    await db.commit()
    return a, b, spz


async def test_an_ability_from_two_reports_is_one_decision_with_its_sources(client, db, monkeypatch):
    u, p = await _setup(db)
    h = await _auth(client)
    a, b, spz = await _reports(db, u, p)
    _fake_group(monkeypatch, [["Mit dem Löffel essen", "Isst mit Löffel"]])

    groups = (await client.get(f"/api/patients/{p.id}/proposals/abilities", headers=h)).json()["groups"]
    assert len(groups) == 1 and groups[0]["suggested_name"] == "Isst mit Löffel"  # the newest report's wording
    ids = [i for s in groups[0]["spellings"] for i in s["proposal_ids"]]
    assert {tuple(d["labels"]) for s in groups[0]["spellings"] for d in s["documents"]} == {
        ("works", "alone", "therapy"), ("fails", "with_help", "kita_school")}

    # verifying a report on its own form decides its diagnoses, never its Abilities
    await client.post(f"/api/documents/{a.id}/verify", headers=h, json={"diagnoses": []})
    assert (await db.execute(select(Proposal.status).where(Proposal.kind == "ability"))).scalars().all() == ["open", "open"]

    r = await client.post(f"/api/patients/{p.id}/proposals/abilities/decide", headers=h,
                          json={"proposal_ids": ids, "accept": True, "name": "Mit dem Löffel essen"})
    assert r.status_code == 204, r.text
    ability = (await db.execute(select(Ability).where(Ability.patient_id == p.id))).scalar_one()
    assert (ability.name, ability.domain) == ("Mit dem Löffel essen", "daily_living")
    obs = (await db.execute(select(AbilityObservation).where(AbilityObservation.patient_id == p.id)
                            .order_by(AbilityObservation.observed_on))).scalars().all()
    assert [(o.observed_on, o.works, o.place, o.source, o.document_id, o.note) for o in obs] == [
        ("2026-05-12", True, "therapy", "document", a.id, SPOON),
        ("2026-06-30", False, "kita_school", "document", b.id, "Beim Mittagessen braucht Lena Hilfe mit dem Löffel.")]
    assert (await client.post(f"/api/patients/{p.id}/proposals/abilities/decide", headers=h,
                              json={"proposal_ids": ids, "accept": True})).status_code == 409

    lines, _ = await chat_router._structured_context(p.id, db, "de")
    assert any("laut Dokument SPZ Schwäbisch Hall" in line and SPOON in line for line in lines), lines


async def test_a_test_attempt_from_a_report_names_its_sender_and_no_score(client, db, monkeypatch):
    u, p = await _setup(db)
    h = await _auth(client)
    a, _, spz = await _reports(db, u, p)
    cards = (await client.get(f"/api/patients/{p.id}/proposals/test-attempts", headers=h)).json()["groups"]
    assert [c["suggested_name"] for c in cards] == ["SON-R 2-8"]
    ids = cards[0]["spellings"][0]["proposal_ids"]
    assert (await client.post(f"/api/patients/{p.id}/proposals/test-attempts/decide", headers=h,
                              json={"proposal_ids": ids, "accept": True})).status_code == 204
    t = (await db.execute(select(TestAttempt).where(TestAttempt.patient_id == p.id))).scalar_one()
    assert (t.test_name, t.attempted_on, t.outcome, t.correspondent_id, t.document_id) == (
        "SON-R 2-8", "2026-05-12", "stopped", spz.id, a.id)


async def test_a_rejected_ability_leaves_nothing(client, db, monkeypatch):
    u, p = await _setup(db)
    h = await _auth(client)
    await _reports(db, u, p)
    _fake_group(monkeypatch, None)  # the model is down: names group by their text
    groups = (await client.get(f"/api/patients/{p.id}/proposals/abilities", headers=h)).json()
    assert groups["grouped_by_model"] is False and len(groups["groups"]) == 2
    ids = groups["groups"][0]["spellings"][0]["proposal_ids"]
    await client.post(f"/api/patients/{p.id}/proposals/abilities/decide", headers=h, json={"proposal_ids": ids, "accept": False})
    assert (await db.execute(select(AbilityObservation))).first() is None


async def test_only_a_therapy_report_is_read_for_development(db):
    class Doc:
        id, patient_id, document_classification = "d", None, "doctor_letter"

    class Client:
        async def post(self, url, json=None):
            raise AssertionError("a doctor letter's anamnesis is never mined (ADR 063)")

    assert await pipeline._development(Client(), Doc(), "Anamnese: lief mit 18 Monaten frei.", None, "de") == {}
