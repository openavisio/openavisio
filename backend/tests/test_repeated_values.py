"""ADR 058: a later letter repeating a value or a dose adds no row."""

from sqlalchemy import select

from app.models.medication import MedicationStatement
from app.models.observation import Observation
from tests.test_condition_sources import _auth, _doc, _setup


async def _rows(db, model, patient_id):
    return list((await db.execute(select(model).where(
        model.patient_id == patient_id, model.is_deleted == False))).scalars())  # noqa: E712


async def test_a_quoted_score_merges_and_a_new_value_does_not(client, db):
    u, p = await _setup(db)
    h = await _auth(client)
    spz, ulm = await _doc(db, u, p, "spz.pdf", "2025-08-18"), await _doc(db, u, p, "ulm.pdf", "2026-03-02")
    score = {"type": "ADOS-2 Gesamtwert", "value": "22", "date": "2025-08-18"}
    await client.post(f"/api/documents/{spz.id}/verify", json={"observations": [score]}, headers=h)
    await client.post(f"/api/documents/{ulm.id}/verify", headers=h, json={"observations": [
        score, {**score, "value": "19"}, {**score, "date": None}]})
    got = sorted((o.effective_date_time, o.value_quantity) for o in await _rows(db, Observation, p.id))
    # the quote merges; another value on the same date and the same value on another date stay
    assert got == [("2025-08-18", 19.0), ("2025-08-18", 22.0), ("2026-03-02", 22.0)]


async def test_a_dose_written_differently_or_left_out_is_no_new_course(client, db):
    u, p = await _setup(db)
    h = await _auth(client)
    a, b = await _doc(db, u, p, "a.pdf", "2025-01-10"), await _doc(db, u, p, "b.pdf", "2026-01-10")
    await client.post(f"/api/documents/{a.id}/verify", json={"medications": [
        {"name": "Slenyto", "dosage": "5mg 0-0-1"}]}, headers=h)
    await client.post(f"/api/documents/{b.id}/verify", json={"medications": [
        {"name": "Slenyto", "dosage": "5 mg 0 - 0 - 1"}, {"name": "slenyto"},
        {"name": "Slenyto", "dosage": "10 mg 0-0-1"}]}, headers=h)
    got = sorted((m.dosage_text, m.effective_start) for m in await _rows(db, MedicationStatement, p.id))
    assert got == [("10 mg 0-0-1", "2026-01-10"), ("5mg 0-0-1", "2025-01-10")]
