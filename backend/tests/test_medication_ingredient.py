"""#209: the ingredient is stored, so the chat finds a brand by its substance."""

from sqlalchemy import select

from app.models.medication import MedicationStatement
from app.routers import chat as chat_router
from tests.test_condition_sources import _auth, _doc, _setup


async def test_chat_context_names_brand_and_ingredient(client, db):
    u, p = await _setup(db)
    db.add(MedicationStatement(patient_id=p.id, owner_id=u.id, medication_display="Ergenyl",
                               ingredient="Valproinsäure", effective_start="2026-07-11", dosage_text="1-0-1-0 ml"))
    db.add(MedicationStatement(patient_id=p.id, owner_id=u.id, medication_display="Slenyto", effective_start="2026-01-01"))
    await db.commit()
    text = "\n".join((await chat_router._structured_context(p.id, db, "de"))[0])
    assert "Medikament | 2026-07-11 | Ergenyl (Valproinsäure) | 1-0-1-0 ml" in text
    assert "Medikament | 2026-01-01 | Slenyto |" in text


async def test_ingredient_is_kept_on_verify_and_editable(client, db):
    u, p = await _setup(db)
    h = await _auth(client)
    d = await _doc(db, u, p, "a.pdf", "2026-07-11")
    await client.post(f"/api/documents/{d.id}/verify", headers=h, json={"medications": [
        {"name": "Ergenyl", "ingredient": "Valproinsäure", "dosage": "300 mg"}, {"name": "Slenyto"}]})
    rows = {m.medication_display: m for m in (await db.execute(
        select(MedicationStatement).where(MedicationStatement.patient_id == p.id))).scalars()}
    assert rows["Ergenyl"].ingredient == "Valproinsäure" and rows["Slenyto"].ingredient is None

    r = await client.put(f"/api/medications/{rows['Slenyto'].id}", headers=h, json={"ingredient": "Melatonin"})
    assert r.status_code == 200 and r.json()["ingredient"] == "Melatonin", r.text
