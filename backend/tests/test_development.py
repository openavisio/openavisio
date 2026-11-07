"""ADR 063: Abilities are observed, never assessed; Test Attempts record how a test went."""

import importlib.util
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.development import Ability, AbilityObservation, TestAttempt
from app.models.document import DocumentReference
from app.routers import chat as chat_router
from tests.test_carer_updates import _auth, _correspondent, _setup
from tests.test_doses import _med, _member

OBS = {"ability_name": "Socken anziehen", "domain": "daily_living", "observed_on": "2026-03", "place": "home",
       "works": True, "with_help": False}


async def test_observations_join_one_ability_and_who_may_change_them(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db, "dev@t.com")
    await _member(db, p, "oma@t.com", "contribute")
    await _member(db, p, "opa@t.com", "view")
    admin, oma, opa = await _auth(client, "dev@t.com"), await _auth(client, "oma@t.com"), await _auth(client, "opa@t.com")
    url = f"/api/patients/{p.id}/ability-observations"

    assert (await client.post(url, headers=opa, json=OBS)).status_code == 404
    assert (await client.post(url, headers=oma, json={**OBS, "observed_on": "2026-13"})).status_code == 422
    assert (await client.post(url, headers=oma, json={**OBS, "observed_on": "2026-02-30"})).status_code == 422
    assert (await client.post(url, headers=oma, json={**OBS, "ability_name": "  "})).status_code == 422
    first = (await client.post(url, headers=oma, json=OBS)).json()
    # same name in other case and spacing: the same Ability; the domain of a later entry does not rename it
    later = (await client.post(url, headers=admin, json={**OBS, "ability_name": "socken  ANZIEHEN", "domain": "motor",
                                                          "observed_on": "2026-06-12", "works": False})).json()
    assert later["ability_id"] == first["ability_id"]

    listed = (await client.get(f"/api/patients/{p.id}/abilities", headers=opa)).json()
    assert len(listed) == 1 and listed[0]["name"] == "Socken anziehen" and listed[0]["domain"] == "daily_living"
    assert [o["observed_on"] for o in listed[0]["observations"]] == ["2026-03", "2026-06-12"]
    assert [o["no_longer"] for o in listed[0]["observations"]] == [False, True]
    assert not any(o["can_edit"] for o in listed[0]["observations"])

    assert (await client.put(f"/api/ability-observations/{later['id']}", headers=oma, json=OBS)).status_code == 403
    assert (await client.delete(f"/api/ability-observations/{later['id']}", headers=oma)).status_code == 403
    r = await client.put(f"/api/ability-observations/{first['id']}", headers=oma, json={**OBS, "note": " nur zuhause "})
    assert r.status_code == 200 and r.json()["note"] == "nur zuhause"
    assert (await client.delete(f"/api/ability-observations/{first['id']}", headers=admin)).status_code == 204
    actions = (await db.execute(select(AuditLog.action).where(AuditLog.entity_type == "AbilityObservation"))).scalars().all()
    assert sorted(actions) == ["deleted", "updated"]


async def test_an_ability_lives_through_its_observations(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db, "dev2@t.com")
    h = await _auth(client, "dev2@t.com")
    url = f"/api/patients/{p.id}/ability-observations"
    walk = (await client.post(url, headers=h, json={**OBS, "ability_name": "Laufen", "domain": "motor"})).json()
    socks = (await client.post(url, headers=h, json=OBS)).json()

    # renaming onto another Ability's name would merge two histories silently
    r = await client.put(f"/api/abilities/{walk['ability_id']}", headers=h, json={"name": "socken anziehen", "domain": None})
    assert r.status_code == 409
    r = await client.put(f"/api/abilities/{walk['ability_id']}", headers=h, json={"name": "Frei laufen", "domain": "motor"})
    assert r.status_code == 200 and r.json()["name"] == "Frei laufen"

    # moving its only Observation to another name leaves the Ability with nothing to say
    await client.put(f"/api/ability-observations/{walk['id']}", headers=h, json=OBS)
    names = [a["name"] for a in (await client.get(f"/api/patients/{p.id}/abilities", headers=h)).json()]
    assert names == ["Socken anziehen"]
    await client.delete(f"/api/ability-observations/{walk['id']}", headers=h)
    await client.delete(f"/api/ability-observations/{socks['id']}", headers=h)
    assert (await client.get(f"/api/patients/{p.id}/abilities", headers=h)).json() == []


async def test_a_test_attempt_reads_the_medications_of_its_day(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db, "dev3@t.com")
    h = await _auth(client, "dev3@t.com")
    spz = await _correspondent(db, "SPZ Schwäbisch Hall")
    await _med(db, u, p, name="Keppra", effective_start="2025-01-10")
    await _med(db, u, p, name="Frisium", effective_start="2025-03-01", effective_end="2025-05-31")
    await _med(db, u, p, name="Ospolot", effective_start="2026-01-01")
    _, other = await _setup(db, "dev3b@t.com")
    foreign = DocumentReference(patient_id=other.id, owner_id=u.id, file_name="x.pdf")
    db.add(foreign)
    await db.commit()

    body = {"test_name": "SON-R 2-8", "attempted_on": "2025-05", "correspondent_id": str(spz.id), "setting": "clinic",
            "duration_minutes": 20, "outcome": "stopped", "reason": "Prüfungsstress, nach 20 Minuten abgebrochen"}
    url = f"/api/patients/{p.id}/test-attempts"
    assert (await client.post(url, headers=h, json={**body, "outcome": "iq_70"})).status_code == 422
    assert (await client.post(url, headers=h, json={**body, "document_id": str(foreign.id)})).status_code == 422
    t = (await client.post(url, headers=h, json=body)).json()
    assert t["medications"] == ["Frisium", "Keppra"] and t["correspondent_name"] == "SPZ Schwäbisch Hall"
    assert "score" not in t

    r = await client.put(f"/api/test-attempts/{t['id']}", headers=h, json={**body, "attempted_on": "2026-02-03"})
    assert r.json()["medications"] == ["Keppra", "Ospolot"]
    assert (await client.delete(f"/api/test-attempts/{t['id']}", headers=h)).status_code == 204
    assert (await client.get(url, headers=h)).json() == []


async def test_the_chat_quotes_observations_and_test_attempts(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db, "dev4@t.com")
    h = await _auth(client, "dev4@t.com")
    url = f"/api/patients/{p.id}/ability-observations"
    await client.post(url, headers=h, json=OBS)
    await client.post(url, headers=h, json={**OBS, "observed_on": "2026-06", "works": False, "place": "kita_school"})
    await client.post(f"/api/patients/{p.id}/test-attempts", headers=h,
                      json={"test_name": "SON-R 2-8", "attempted_on": "2025-05", "outcome": "refused"})
    lines, _ = await chat_router._structured_context(p.id, db, "de")
    assert "Fähigkeit | 2026-06 | Socken anziehen | klappt nicht mehr | allein | Kita/Schule | Alltag" in lines
    assert "Fähigkeit | 2026-03 | Socken anziehen | klappt | allein | zuhause | Alltag" in lines
    assert "Testversuch | 2025-05 | SON-R 2-8 | verweigert" in lines


async def test_patient_erasure_deletes_abilities_and_test_attempts(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db, "dev5@t.com")
    h = await _auth(client, "dev5@t.com")
    await client.post(f"/api/patients/{p.id}/ability-observations", headers=h, json=OBS)
    await client.post(f"/api/patients/{p.id}/test-attempts", headers=h,
                      json={"test_name": "Bayley-III", "attempted_on": "2024-09", "outcome": "completed"})

    from app.services.erasure import erase_patient
    await erase_patient(p.id, u, db)
    await db.commit()
    for model in (Ability, AbilityObservation, TestAttempt):
        assert (await db.execute(select(model).where(model.patient_id == p.id))).first() is None


async def test_milestones_move_to_abilities_without_loss(db: AsyncSession):
    path = next(Path(__file__).parent.parent.glob("alembic/versions/b4w5x6y7z8a9_*.py"))
    spec = importlib.util.spec_from_file_location("abilities_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    u, p = await _setup(db, "dev6@t.com")
    doc = DocumentReference(patient_id=p.id, owner_id=u.id, file_name="spz.pdf")
    db.add(doc)
    await db.commit()
    # the model no longer has the column the migration reads; put it back for this transaction only
    await db.execute(text("ALTER TABLE calendar_events ADD COLUMN developmental_domain varchar(20)"))
    for title, start, domain, desc, doc_id, deleted in [
        ("Erste Schritte", "2021-03-14", "motor", "zu Papa im Wohnzimmer", None, False),
        ("Erstes Wort", "2022-01-02T10:00", "speech", None, doc.id, False),
        ("erste  schritte", "2021-04-01", "motor", None, None, False),
        ("Gelöscht", "2020-01-01", None, None, None, True),
    ]:
        await db.execute(text(
            "INSERT INTO calendar_events (id, owner_id, patient_id, title, description, start_at, all_day, source, status, "
            "category, developmental_domain, document_reference_id, reminder_stage, is_deleted) VALUES (gen_random_uuid(), "
            ":u, :p, :t, :d, :s, true, 'manual', 'scheduled', 'milestone', :dom, :doc, 0, :del)"),
            {"u": u.id, "p": p.id, "t": title, "d": desc, "s": start, "dom": domain, "doc": doc_id, "del": deleted})
    await db.execute(text(
        "INSERT INTO calendar_events (id, owner_id, patient_id, title, start_at, all_day, source, status, category, "
        "reminder_stage, is_deleted) VALUES (gen_random_uuid(), :u, :p, 'Neurologie', '2026-12-01', false, 'manual', "
        "'scheduled', 'appointment', 0, false)"), {"u": u.id, "p": p.id})

    await (await db.connection()).run_sync(migration.move_milestones)

    abilities = {a.name: a for a in (await db.execute(select(Ability).where(Ability.patient_id == p.id))).scalars().all()}
    assert set(abilities) == {"Erste Schritte", "Erstes Wort"}
    assert abilities["Erste Schritte"].domain == "motor" and abilities["Erstes Wort"].domain == "communication"
    obs = (await db.execute(select(AbilityObservation).where(AbilityObservation.patient_id == p.id)
                            .order_by(AbilityObservation.observed_on))).scalars().all()
    assert [(o.observed_on, o.works, o.note, o.source) for o in obs] == [
        ("2021-03-14", True, "zu Papa im Wohnzimmer", "family"),
        ("2021-04-01", True, None, "family"),
        ("2022-01-02", True, None, "document"),
    ]
    assert obs[2].document_id == doc.id and all(o.owner_id == u.id for o in obs)
    left = (await db.execute(text("SELECT category FROM calendar_events WHERE patient_id = :p"), {"p": p.id})).scalars().all()
    assert left == ["appointment"]


async def test_doctor_and_authority_handouts_offer_observations_by_period(client: AsyncClient, db: AsyncSession):
    from app.services.handout import render_html
    u, p = await _setup(db, "dev7@t.com")
    h = await _auth(client, "dev7@t.com")
    await client.post(f"/api/patients/{p.id}/ability-observations", headers=h, json=OBS)
    await client.post(f"/api/patients/{p.id}/ability-observations", headers=h,
                      json={**OBS, "observed_on": "2026-06", "works": False, "note": "nur mit Erinnerung"})
    await client.post(f"/api/patients/{p.id}/test-attempts", headers=h, json={
        "test_name": "SON-R 2-8", "attempted_on": "2025-05", "outcome": "stopped", "reason": "Prüfungsstress",
        "duration_minutes": 20})

    for variant in ("doctors", "authorities"):
        data = (await client.get(f"/api/patients/{p.id}/handouts/{variant}", headers=h)).json()
        sections = {s["key"]: s for s in data["sections"]}
        assert not sections["abilities"]["preselected"] and not sections["test_attempts"]["preselected"]
    assert [(e["date"], e["labels"], e["detail"]) for e in sections["abilities"]["entries"]] == [
        ("2026-06", ["no_longer", "alone", "home"], "nur mit Erinnerung"), ("2026-03", ["works", "alone", "home"], None)]
    assert sections["test_attempts"]["entries"][0]["labels"] == ["stopped"]
    html = render_html(data, "de")
    assert "klappt nicht mehr, allein, zuhause" in html and "06/2026" in html and "Prüfungsstress, 20 min" in html

    for variant in ("emergency", "steckbrief"):
        keys = [s["key"] for s in (await client.get(f"/api/patients/{p.id}/handouts/{variant}", headers=h)).json()["sections"]]
        assert "abilities" not in keys and "test_attempts" not in keys
