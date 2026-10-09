"""The Handout for authorities and insurers (ADR 048): the course over time, the
Einstufungen as recorded, never what they pay out.
"""

from datetime import date, timedelta

from httpx import AsyncClient

from app.models.document import DocumentReference
from app.models.einstufung import Einstufung
from app.models.incident import Incident
from app.services.handout import render_html
from tests.test_handout_variants import _auth, _section, _setup


def _ago(days):
    return (date.today() - timedelta(days=days)).isoformat()


async def test_the_authorities_handout_shows_the_course_over_time(client: AsyncClient, db):
    u, p = await _setup(db, email="amt@t.com")
    h = await _auth(client, email="amt@t.com")
    own = dict(patient_id=p.id, owner_id=u.id)
    pending = DocumentReference(**own, description="Unread Bescheid", verification_status="extracted")
    db.add(pending)
    await db.commit()
    db.add_all([
        Einstufung(**own, pflegegrad=2, valid_from="2024-03-01", authority="AOK", file_reference="AZ-1"),
        Einstufung(**own, pflegegrad=3, valid_from="2026-06-01", authority="AOK"),
        Einstufung(**own, pflegegrad=4, valid_from="2026-09-01", source="pipeline", document_reference_id=pending.id),
        Incident(**own, incident_type="seizure", incident_type_display="Anfall", occurred_at=_ago(30)),
        Incident(**own, incident_type="seizure", incident_type_display="Anfall", occurred_at=_ago(300)),
        Incident(**own, incident_type="seizure", incident_type_display="Anfall", occurred_at=_ago(400)),
    ])
    await db.commit()

    body = (await client.get(f"/api/patients/{p.id}/handouts/authorities", headers=h)).json()
    keys = [s["key"] for s in body["sections"]]
    assert {"diagnoses_resolved", "events", "einstufungen", "documents"} <= set(keys)
    assert "weight" not in keys and "lab_results" not in keys
    grades = _section(body, "einstufungen")["entries"]
    assert [(e["text"], e["date"]) for e in grades] == [("Pflegegrad 3", "2026-06-01"), ("Pflegegrad 2", "2024-03-01")]
    assert grades[1]["detail"] == "AOK, AZ-1"
    assert _section(body, "incidents_12m")["entries"][0]["detail"] == "2×"

    html = render_html(body, "de")
    assert "Pflegegrad 3" in html and "€" not in html and "Euro" not in html
