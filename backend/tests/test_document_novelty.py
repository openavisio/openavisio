"""What each letter adds over the earlier ones, and which one it repeats (ADR 058)."""

from tests.test_condition_sources import _auth, _doc, _setup
from tests.test_proposal_review import _fake_group


async def test_a_letter_that_quotes_an_earlier_one_says_nothing_new_and_names_it(client, db, monkeypatch):
    u, p = await _setup(db)
    h = await _auth(client)
    spz = await _doc(db, u, p, "spz.pdf", "2025-03-01")
    ulm = await _doc(db, u, p, "ulm.pdf", "2026-02-01")
    spz.extraction_json = {
        "diagnoses": [{"name": "Dup15q-Syndrom"}],
        "medications": [{"name": "Slenyto", "dosage": "5mg 0-0-1"}],
        "observations": [{"type": "ADOS-2 Gesamtwert", "value": "22", "date": "2025-03-01"}],
    }
    ulm.extraction_json = {
        "diagnoses": [{"name": "Dup15q syndrome"}, {"name": "Ataxie"}],     # a spelling the model groups, and a new one
        "medications": [{"name": "Slenyto", "dosage": "5 mg 0-0-1"}],       # the same dose, written differently
        "observations": [{"type": "ADOS-2 Gesamtwert", "value": "22", "date": "2025-03-01"}],  # quoted
    }
    await db.commit()
    _fake_group(monkeypatch, [["Dup15q-Syndrom", "Dup15q syndrome"], ["Ataxie"]])

    r = (await client.get(f"/api/patients/{p.id}/documents/novelty", headers=h)).json()
    assert r[str(spz.id)] == {"new": {"diagnoses": 1, "medications": 1, "observations": 1}, "known": 0, "repeats": None}
    assert r[str(ulm.id)]["new"] == {"diagnoses": 1, "medications": 0, "observations": 0}
    assert r[str(ulm.id)]["known"] == 3
    assert r[str(ulm.id)]["repeats"]["id"] == str(spz.id)
