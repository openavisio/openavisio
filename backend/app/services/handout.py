"""Handout (ADR 048): a fixed variant of the record, only confirmed entries, verbatim."""

import uuid
from collections import Counter
from datetime import date, timedelta
from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar import CalendarEvent, EventCategory
from app.models.care_notes import HEADINGS as CARE_HEADINGS, CareNotes
from app.models.carer_update import CarerUpdate
from app.models.development import LABELS as DEV_LABELS, Ability, TestAttempt, no_longer
from app.models.dose import Dose
from app.models.condition import Condition
from app.models.document import DocumentReference
from app.models.einstufung import Einstufung
from app.models.emergency_plan import EmergencyPlan
from app.models.incident import TYPE_LABELS, Incident
from app.models.medication import MedicationStatement
from app.models.observation import Observation
from app.models.patient import Patient
from app.routers.emergency_plan import plan_to_dto
from app.routers.medications import med_is_active

PLAN = ["emergency_plan", "emergency_contacts", "emergency_notes", "emergency_documents"]
CARE = [f"care_{h}" for h in CARE_HEADINGS]

# section -> preselected in the preview
VARIANTS = {
    "doctors": dict.fromkeys(["allergies", "diagnoses_active", "diagnoses_resolved", "medications", "weight",
                              "incidents", "lab_results", "events", "correspondents", "documents"], True)
    | {"carer_updates": False, "rescue_doses": False, "abilities": False, "test_attempts": False},  # ADR 049, 060, 063: only the period the User picks
    "emergency": dict.fromkeys(["allergies", "weight", "diagnoses_active", "medications", *PLAN, "correspondents"], True),
    "steckbrief": {"allergies": True, "diagnoses_active": False, "medications": True,
                   **dict.fromkeys(PLAN + CARE, True)},
    "authorities": dict.fromkeys(["allergies", "diagnoses_active", "diagnoses_resolved", "medications", "incidents_12m",
                                  "events", "einstufungen", "correspondents", "documents"], True)
    | {"carer_updates": False, "abilities": False, "test_attempts": False},
}
ONE_PAGE = {"emergency"}

LABELS = {
    "de": {
        "title": {"doctors": "Infoblatt für Ärzte", "emergency": "Infoblatt für den Notfall", "steckbrief": "Steckbrief", "authorities": "Infoblatt für Ämter und Kassen"},
        "incidents_12m": "Vorfälle der letzten 12 Monate (Anzahl)", "einstufungen": "Einstufungen (Pflegegrad)",
        "born": "geb.", "as_of": "Stand", "suspected": "Verdacht",
        "medication_deleted": "Medikament nicht mehr in der Akte", "medication_stopped": "Medikament abgesetzt",
        "emergency_plan": "Notfallplan", "emergency_contacts": "Notfallkontakte", "emergency_notes": "Hinweise",
        "emergency_documents": "Notfallpläne von Ärzten und Kliniken",
        "care_communication": "Kommunikation", "care_eating_drinking": "Essen und Trinken", "care_sleep": "Schlafen",
        "care_aids": "Hilfsmittel", "care_what_helps": "Was hilft", "care_what_overwhelms": "Was überfordert",
        "allergies": "Allergien", "diagnoses_active": "Diagnosen", "diagnoses_resolved": "Abgeheilte Diagnosen",
        "medications": "Aktuelle Medikamente", "weight": "Aktuelles Gewicht",
        "incidents": "Vorfälle der letzten 3 Monate (Anzahl)", "lab_results": "Letzte Laborwerte",
        "events": "Termine, Klinikaufenthalte und Therapien (12 Monate)",
        "correspondents": "Behandelnde Ärzte und Einrichtungen", "documents": "Dokumente (12 Monate)",
        "carer_updates": "Rückmeldungen von Betreuenden", "retold": "mündlich, nacherzählt",
        "rescue_doses": "Gaben von Notfallmedikamenten",
        "abilities": "Fähigkeiten, wie beobachtet", "test_attempts": "Testversuche",
        "footer": "Aus OpenAvisio, nur von der Familie bestätigte Einträge, so wie erfasst.",
    },
    "en": {
        "title": {"doctors": "Handout for doctors", "emergency": "Emergency handout", "steckbrief": "Handout for carers", "authorities": "Handout for authorities and insurers"},
        "incidents_12m": "Incidents in the last 12 months (count)", "einstufungen": "Care assessments (Pflegegrad)",
        "born": "born", "as_of": "As of", "suspected": "suspected",
        "medication_deleted": "medication no longer in the record", "medication_stopped": "medication stopped",
        "emergency_plan": "Emergency plan", "emergency_contacts": "Emergency contacts", "emergency_notes": "Notes",
        "emergency_documents": "Emergency plans from doctors and clinics",
        "care_communication": "Communication", "care_eating_drinking": "Eating and drinking", "care_sleep": "Sleep",
        "care_aids": "Aids", "care_what_helps": "What helps", "care_what_overwhelms": "What overwhelms",
        "allergies": "Allergies", "diagnoses_active": "Diagnoses", "diagnoses_resolved": "Resolved diagnoses",
        "medications": "Current medications", "weight": "Current weight",
        "incidents": "Incidents in the last 3 months (count)", "lab_results": "Latest lab results",
        "events": "Appointments, hospital stays and therapies (12 months)",
        "correspondents": "Treating doctors and facilities", "documents": "Documents (12 months)",
        "carer_updates": "Updates from carers", "retold": "retold, not word for word",
        "rescue_doses": "Doses of rescue medications",
        "abilities": "Abilities, as observed", "test_attempts": "Test attempts",
        "footer": "From OpenAvisio, only entries the family confirmed, as recorded.",
    },
}


def _entry(id_, text, detail=None, when=None, suspected=False, retold=False, items=(), labels=()) -> dict:
    # labels: DEV_LABELS keys, worded in the reader's language when shown
    return {"id": id_, "text": text, "detail": detail, "date": when, "suspected": suspected, "retold": retold,
            "items": list(items), "labels": list(labels)}


def _num(v: float) -> str:
    return f"{v:g}"


def _dose(m) -> str | None:
    amount = m.dosage_text or (f"{_num(m.dose_quantity)} {m.dose_unit or ''}".strip() if m.dose_quantity else None)
    return " ".join(filter(None, [amount, m.route])) or None


def _step(s) -> dict:
    m = s.medication
    if s.medication_id and (not m or not m.is_active):
        return {"text": s.text, "flag": "medication_stopped" if m else "medication_deleted"}
    if m:
        return {"text": f"{s.text}: {', '.join(filter(None, [m.medication_display, _dose(m)]))}", "flag": None}
    return {"text": s.text, "flag": None}


async def build(patient_id: uuid.UUID, variant: str, db: AsyncSession) -> dict:
    today = date.today()
    year_ago, quarter_ago = (today - timedelta(days=365)).isoformat(), (today - timedelta(days=91)).isoformat()

    async def rows(model, *where):
        q = select(model).where(model.patient_id == patient_id, model.is_deleted == False, *where)  # noqa: E712
        return (await db.execute(q)).scalars().all()

    patient = (await db.execute(select(Patient).where(Patient.id == patient_id))).scalar_one()
    docs = await rows(DocumentReference)
    verified = {d.id for d in docs if d.verification_status == "verified"}

    def confirmed(r) -> bool:
        return r.document_reference_id is None or r.document_reference_id in verified

    conds = [c for c in await rows(Condition)
             if confirmed(c) and c.verification_status not in ("refuted", "entered-in-error")]
    meds = [m for m in await rows(MedicationStatement) if confirmed(m) and med_is_active(m)]
    obs = sorted((o for o in await rows(Observation) if confirmed(o)), key=lambda o: o.effective_date_time or "", reverse=True)
    latest = {}
    for o in obs:
        latest.setdefault("weight" if o.code == "body-weight" else (o.category, o.code or o.code_display), o)

    def value(o):
        v = _num(o.value_quantity) if o.value_quantity is not None else (o.value_string or "")
        return f"{v} {o.value_unit or ''}".strip()

    def dx(c):
        return _entry(f"condition:{c.id}", c.code_display, c.note, c.onset_date_time, c.verification_status == "provisional")

    year_incidents = await rows(Incident, Incident.occurred_at >= year_ago)
    incidents = Counter(i.incident_type_display or i.incident_type for i in year_incidents if i.occurred_at >= quarter_ago)
    incidents_12m = Counter(i.incident_type_display or i.incident_type for i in year_incidents)
    events = await rows(CalendarEvent, CalendarEvent.category == EventCategory.appointment, CalendarEvent.status != "cancelled",
                        CalendarEvent.start_at >= year_ago, CalendarEvent.start_at < (today + timedelta(days=1)).isoformat())
    recent_docs = sorted((d for d in docs if d.id in verified and d.issued_date and d.issued_date >= today - timedelta(days=365)),
                         key=lambda d: d.issued_date, reverse=True)
    correspondents = {d.correspondent.id: d.correspondent.name for d in docs if d.id in verified and d.correspondent}

    plan_row = (await db.execute(select(EmergencyPlan).where(EmergencyPlan.patient_id == patient_id))).scalar_one_or_none()
    # ADR 060: a rescue medication is one the Emergency Plan points at, or a Dose given during an Incident
    rescue = {str(st.get("medication_id")) for sit in (plan_row.situations if plan_row else []) for st in sit.get("steps", [])}
    med_names = {m.id: m.medication_display for m in await rows(MedicationStatement)}
    rescue_doses = sorted((d for d in await rows(Dose) if d.medication_id in med_names
                           and (str(d.medication_id) in rescue or d.incident_id)), key=lambda d: d.given_at, reverse=True)

    # ADR 063: single Observations as recorded, never summed up
    observed = []
    for a in await rows(Ability):
        lapsed = no_longer(a.observations)
        observed += [_entry(f"ability_observation:{o.id}", a.name, ": ".join(filter(None, [o.sender(), o.note])) or None,
                            o.observed_on, labels=filter(None, [
            "no_longer" if o.id in lapsed else "works" if o.works else "fails", "with_help" if o.with_help else "alone",
            o.place, o.source if o.source != "family" else None]))
            for o in a.observations if o.document_id is None or o.document_id in verified]
    attempts = [_entry(f"test_attempt:{t.id}", t.test_name, ", ".join(filter(None, [
        t.reason, t.correspondent and t.correspondent.name, t.duration_minutes and f"{t.duration_minutes} min"])) or None,
        t.attempted_on, labels=filter(None, [t.outcome, t.setting])) for t in await rows(TestAttempt)]

    sections = {
        "abilities": sorted(observed, key=lambda e: e["date"], reverse=True),
        "test_attempts": sorted(attempts, key=lambda e: e["date"], reverse=True),
        "allergies": [dx(c) for c in conds if c.category == "allergy"],
        "diagnoses_active": [dx(c) for c in conds if c.category != "allergy" and c.clinical_status == "active"],
        "diagnoses_resolved": [dx(c) for c in conds if c.category != "allergy" and c.clinical_status in ("resolved", "remission")],
        "medications": [_entry(f"medication:{m.id}", m.medication_display, _dose(m)) for m in meds],
        "weight": [_entry(f"observation:{o.id}", value(o), None, o.effective_date_time)
                   for key, o in latest.items() if key == "weight"],
        "incidents": [_entry(f"incident:{t}", t, f"{n}×") for t, n in sorted(incidents.items())],
        "incidents_12m": [_entry(f"incident:{t}", t, f"{n}×") for t, n in sorted(incidents_12m.items())],
        # ADR 042: grade and date as recorded, never what it pays out
        "einstufungen": [_entry(f"einstufung:{e.id}", f"Pflegegrad {e.pflegegrad}",
                                ", ".join(filter(None, [e.authority, e.file_reference])) or None, e.valid_from)
                         for e in sorted((e for e in await rows(Einstufung) if confirmed(e) and e.pflegegrad),
                                         key=lambda e: e.valid_from or "", reverse=True)],
        "lab_results": [_entry(f"observation:{o.id}", o.code_display or o.code,
                               " ".join(filter(None, [value(o), f"({o.reference_range})" if o.reference_range else None])),
                               o.effective_date_time)
                        for key, o in latest.items() if key != "weight" and key[0] == "lab"],
        "events": [_entry(f"event:{e.id}", e.title, e.provider, e.start_at)
                   for e in sorted(events, key=lambda e: e.start_at, reverse=True)],
        "correspondents": [_entry(f"correspondent:{cid}", name) for cid, name in sorted(correspondents.items(), key=lambda x: x[1])],
        "documents": [_entry(f"document:{d.id}", d.description or d.file_name,
                             d.correspondent and d.correspondent.name, d.issued_date.isoformat())
                      for d in recent_docs],
        "carer_updates": [_entry(f"carer_update:{u.id}", ", ".join(filter(None, [u.correspondent.name, u.person])),
                                 u.text, u.day, retold=u.retold)
                          for u in sorted(await rows(CarerUpdate), key=lambda u: u.day, reverse=True)],
        "rescue_doses": [_entry(f"dose:{d.id}", med_names[d.medication_id],
                                ", ".join(filter(None, [d.given_at[11:16], d.amount])), d.given_at[:10])
                         for d in rescue_doses],
    }
    plan = await plan_to_dto(plan_row, db) if plan_row else None
    notes = (await db.execute(select(CareNotes).where(CareNotes.patient_id == patient_id))).scalar_one_or_none()
    if plan:
        sections |= {
            "emergency_plan": [_entry(f"situation:{i}", s.trigger, items=[_step(st) for st in s.steps])
                               for i, s in enumerate(plan.situations)],
            "emergency_contacts": [_entry(f"contact:{i}", c.name, " ".join(filter(None, [c.role, c.phone])) or None)
                                   for i, c in enumerate(plan.contacts)],
            "emergency_notes": [_entry("plan-notes", plan.notes)] if plan.notes else [],
            # the model reads issued_date; only a verified Document's date counts as confirmed
            "emergency_documents": [_entry(f"plan-document:{d.id}", d.description or d.file_name,
                                           d.correspondent and d.correspondent.name,
                                           d.issued_date and d.id in verified and d.issued_date.isoformat())
                                    for d in plan.documents],
        }
    sections |= {f"care_{h}": [_entry(f"care:{h}", getattr(notes, h))] if notes and getattr(notes, h) else []
                 for h in CARE_HEADINGS}
    wanted = VARIANTS[variant]
    return {
        "variant": variant,
        "missing": [k for k, part in (("emergency_plan", PLAN), ("care_notes", CARE))
                    if part[0] in wanted and not any(sections.get(s) for s in part)],
        "patient": {"name": f"{patient.given_name} {patient.family_name}", "birth_date": patient.birth_date and str(patient.birth_date)},
        "sections": [{"key": k, "preselected": pre, "entries": sections.get(k, [])} for k, pre in wanted.items()],
    }


def _date(iso: str | None, lang: str) -> str:
    if not iso:
        return ""
    if len(iso) == 7:  # a month is enough for an Ability Observation (ADR 063)
        return escape(f"{iso[5:]}/{iso[:4]}" if lang == "de" else iso)
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return escape(iso)
    return d.strftime("%d.%m.%Y") if lang == "de" else d.isoformat()


def render_html(handout: dict, lang: str, exclude: set[str] = frozenset(), font_pt: float = 10) -> str:
    L = LABELS[lang]
    p = handout["patient"]
    parts = []
    for s in handout["sections"]:
        items = []
        for e in s["entries"]:
            if e["id"] in exclude:
                continue
            text = TYPE_LABELS[lang].get(e["text"], e["text"]) if e["id"].startswith("incident:") else e["text"]
            bits = [f"<strong>{escape(text or '')}</strong>"]
            if e["suspected"]:
                bits.append(f'<span class="flag">{L["suspected"]}</span>')
            if e.get("retold"):
                bits.append(f'<span class="flag">{L["retold"]}</span>')
            if e.get("labels"):
                bits.append(escape(", ".join(DEV_LABELS[lang][k] for k in e["labels"])))
            if e["detail"]:
                bits.append(escape(e["detail"]))
            if e["date"]:
                bits.append(f'<span class="date">{_date(e["date"], lang)}</span>')
            if e.get("items"):
                bits.append("<ol>" + "".join(
                    f"<li>{escape(i['text'])}" + (f' <span class="flag">{L[i["flag"]]}</span>' if i["flag"] else "") + "</li>"
                    for i in e["items"]) + "</ol>")
            items.append(f"<li>{' '.join(bits)}</li>")
        if items:
            parts.append(f"<h2>{L[s['key']]}</h2><ul>{''.join(items)}</ul>")
    sub = [f"{L['born']} {_date(p['birth_date'], lang)}"] if p["birth_date"] else []
    sub.append(f"{L['as_of']} {_date(date.today().isoformat(), lang)}")
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 18mm; }}
body {{ font-family: sans-serif; font-size: {font_pt}pt; color: #111; }}
h1 {{ font-size: 1.6em; margin: 0; }} .sub {{ color: #555; margin: 2pt 0 10pt; }}
h2 {{ font-size: 1.1em; border-bottom: 1px solid #ccc; margin: 1.2em 0 0.4em; }}
ul {{ margin: 0; padding-left: 14pt; }} li {{ margin: 2pt 0; }}
.flag {{ border: 1px solid #b45309; color: #b45309; border-radius: 3pt; padding: 0 3pt; font-size: 8pt; }}
.date {{ color: #555; }} footer {{ margin-top: 16pt; color: #777; font-size: 8pt; }}
</style></head><body>
<h1>{escape(L['title'][handout['variant']])}: {escape(p['name'])}</h1>
<div class="sub">{' · '.join(sub)}</div>
{''.join(parts)}
<footer>{L['footer']}</footer>
</body></html>"""


def _no_fetch(url, *args, **kwargs):
    raise ValueError(f"Handout PDFs load nothing: {url}")


def render_document(handout: dict, lang: str, exclude: set[str]):
    import weasyprint
    sizes = (10, 9, 8, 7, 6) if handout["variant"] in ONE_PAGE else (10,)
    for pt in sizes:
        doc = weasyprint.HTML(string=render_html(handout, lang, exclude, pt), url_fetcher=_no_fetch).render()
        if len(doc.pages) == 1:
            break
    # ponytail: below 6pt it stays multi-page rather than becoming unreadable
    return doc


def render_pdf(handout: dict, lang: str, exclude: set[str]) -> bytes:
    return render_document(handout, lang, exclude).write_pdf()
