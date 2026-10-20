import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import require_patient_access
from app.core.config import settings
from app.core.database import get_db
from app.core.ratelimit import client_ip, enforce
from app.deps import get_current_user
from app.models.calendar import CalendarEvent, EventCategory
from app.models.care_notes import HEADINGS as CARE_HEADINGS, CareNotes
from app.models.carer_update import CarerUpdate
from app.models.chat import ChatMessage
from app.models.emergency_plan import EmergencyPlan
from app.models.condition import Condition
from app.models.incident import Incident
from app.models.intake import HistoryFact
from app.models.medication import MedicationStatement
from app.models.observation import Observation
from app.models.user import User
from app.schemas.chat import ChatHistoryDto, ChatMessageDto, ChatRequest, ChatResponse, ChatSourceDto

router = APIRouter()

# ADR 038: structured records go in whole, documents only by retrieval. The caps
# are the known ceiling; when one bites, the answer has to say so.
APPOINTMENT_LIMIT = 150
INCIDENT_LIMIT = 100
CARER_UPDATE_LIMIT = 100
# Labs are the one source that runs into the thousands, so they are capped per
# parameter instead of overall: a yearly-checked parameter must not be pushed
# out by a weekly-checked one (#200).
LAB_PER_CODE = 3
CHUNK_LIMIT = 5
HISTORY_WINDOW = 6

# Cosine distance above which a chunk counts as unrelated. Without a cutoff
# "nothing found" can never happen and the source list is a false positive
# dressed as evidence (ADR 038).
#
# Calibrated 2026-07-21 against 75 real German chunks with qwen3-embedding:4b at
# 768 dimensions and the query instruction prefix: five genuine questions landed
# at 0.237–0.519, five unrelated ones at 0.663–0.735. The midpoint is the
# constant. The same corpus with nomic-embed-text overlapped (-0.011), which is
# why the model changed (docs/research-embedding-model.md).
#
# ponytail: one constant, and it only holds for that model. Recalibrate on a
# model change; if that becomes a habit, switch to a relative rule (keep chunk i
# only while distance_i is close to the best hit), which survives model swaps.
CHUNK_MAX_DISTANCE = 0.59


# The context is model-facing, but it is quoted back to the reader: the prompt
# tells the model to pass on a cap notice verbatim. So it follows the
# Organization's language like the rest of the pipeline does (pipeline.py).
_LABELS = {
    "en": {
        "milestone": "Milestone", "appointment": "Appointment", "medication": "Medication",
        "condition": "Diagnosis", "incident": "Incident", "document": "Document",
        "suspected": "suspected, not confirmed",
        "lab": "Lab value",
        "until": "until", "status": "status",
        "cap": "NOTE: only the {n} most recent {what} are included, older ones are missing.",
        "appointments": "appointments", "incidents": "incidents",
        "carer_update": "Carer update", "retold": "retold, not word for word",
        "carer_updates": "carer updates",
        "care_note": "Care note",
        "history_fact": "History fact",
        "care": {"communication": "Communication", "eating_drinking": "Eating and drinking", "sleep": "Sleep",
                 "aids": "Aids", "what_helps": "What helps", "what_overwhelms": "What overwhelms"},
        "emergency": "What to do in an emergency is in the Emergency Plan. This chat does not repeat it,"
                     " so that no dose can be quoted wrongly here. Please open the Emergency Plan itself.",
        "lab_cap": "NOTE: for lab values only the {n} most recent results per parameter are"
                   " included, older ones are missing.",
        "stripped": "(One part of the answer was removed: it graded a value or gave a"
                    " recommendation, which this chat may not do. Please ask the treating"
                    " clinician about that.)",
        "declined": "Whether a value is worrying is not something I can judge — that belongs"
                    " to the treating clinician. Ask me what the documents say and I will"
                    " name the entries with their dates.",
    },
    "de": {
        "milestone": "Meilenstein", "appointment": "Termin", "medication": "Medikament",
        "condition": "Diagnose", "incident": "Vorfall", "document": "Dokument",
        "suspected": "Verdacht, nicht bestätigt",
        "lab": "Laborwert",
        "until": "bis", "status": "Status",
        "cap": "HINWEIS: nur die {n} neuesten {what} sind enthalten, ältere fehlen.",
        "appointments": "Termine", "incidents": "Vorfälle",
        "carer_update": "Rückmeldung", "retold": "mündlich, nacherzählt",
        "carer_updates": "Rückmeldungen",
        "care_note": "Alltagsinfo",
        "history_fact": "Angabe",
        "care": {"communication": "Kommunikation", "eating_drinking": "Essen und Trinken", "sleep": "Schlafen",
                 "aids": "Hilfsmittel", "what_helps": "Was hilft", "what_overwhelms": "Was überfordert"},
        "emergency": "Was im Notfall zu tun ist, steht im Notfallplan. Dieser Chat gibt ihn nicht wieder,"
                     " damit hier keine Dosis falsch zitiert werden kann. Bitte öffne den Notfallplan selbst.",
        "lab_cap": "HINWEIS: von den Laborwerten sind nur die {n} neuesten Ergebnisse je"
                   " Parameter enthalten, ältere fehlen.",
        "stripped": "(Ein Teil der Antwort wurde entfernt: dort wurde ein Wert eingeordnet"
                    " oder eine Empfehlung gegeben, und beides darf dieser Chat nicht."
                    " Frag dazu bitte die behandelnde Ärztin oder den behandelnden Arzt.)",
        "declined": "Ob ein Wert bedenklich ist, kann ich nicht beurteilen, das gehört zur"
                    " behandelnden Ärztin oder zum behandelnden Arzt. Frag mich, was in"
                    " den Unterlagen steht, dann nenne ich dir die Einträge mit Datum.",
    },
}


# The prompt forbids grading values and giving advice, and a locally hosted model
# ignores that on exactly the question a caregiver asks first: "sind die Werte in
# Ordnung?" came back as "✅ im Normbereich ... eine Dosisanpassung wäre sinnvoll"
# (#208). A model cannot be trusted to police itself, so the answer is filtered
# before anyone sees it. Judging is a medical device function under the MDR and
# OpenAvisio is deliberately not one (docs/regulatory-positioning.md, #113).
#
# ponytail: a phrase list, not a classifier. It catches the observed wordings and
# will miss paraphrases; the upgrade is a second model call, which costs another
# 40s per answer on this hardware. Every miss belongs on this list.
_JUDGEMENT = re.compile(
    r"referenzbereich|normbereich|reference range|normal range"
    r"|unauffällig|auffällig|unbedenklich|besorgniserregend|bedenklich"
    r"|subtherapeutisch|therapeutische[nr]? (ziel)?bereich|therapeutic range"
    r"|zu (hoch|niedrig|gering)|deutlich erhöht|leicht erhöht|erniedrigt"
    r"|(ist|sind|liegt|liegen|war|waren) .{0,20}(normal|in ordnung|im gr[üu]nen)"
    r"|klinisch (unbedeutend|relevant|bedeutsam)"
    r"|dosisanpassung|dosis anpassen|compliance"
    r"|empfehle|empfehlung|sollten sie|wäre (sinnvoll|ratsam)|raten wir"
    r"|i recommend|you should|dose adjustment|advisable"
    r"|tendenz|zunehmend|abnehmend|verschlechter|verbesser|stabil geblieben"
    r"|bewertung|beurteilung|einordnung|interpretation|assessment"
    r"|✅|⚠️|❗",
    re.IGNORECASE,
)

# ADR 048: such a question gets a fixed pointer from the code, the model is not asked.
# ponytail: keyword lists, they miss paraphrases; every miss belongs on them
_EMERGENCY = re.compile(
    r"notfall(?!-?(termin|ambulanz|aufnahme|sprechstunde))|emergenc|notarzt|rettungsdienst|ambulance|rescue med"
    r"|(call|dial|anrufen|rufen|wählen)\W+112|112\W+(anrufen|rufen|wählen)|status epilepticus"
    r"|bewusstlos|unconscious|unresponsive|atmet nicht|not breathing|buccolam|midazolam|diazepam",
    re.IGNORECASE,
)
_SEIZURE = re.compile(r"anfall|krampf|seizure|convuls", re.IGNORECASE)
_ACTION = re.compile(r"was (tun|mache|machen|soll)|wie viel|what (do|should|to do)|how much", re.IGNORECASE)


def _is_emergency(question: str, plan_medications) -> bool:
    q = question.lower()
    return bool(_EMERGENCY.search(q) or (_SEIZURE.search(q) and _ACTION.search(q))
                or any(m.lower() in q for m in plan_medications if m))


def _is_pointer(content: str) -> bool:
    return any(content == L["emergency"] for L in _LABELS.values())

# "**Bewertung:**" on its own line: a heading whose paragraph was just dropped
_HEADING = re.compile(r"^[\s*_#>-]*[^.!?]{0,40}:\**\s*$")


def _strip_judgement(answer: str, lang: str) -> str:
    """Drop every segment that grades a value or advises, keep the rest.

    Line-wise rather than whole-answer, because the listing part of an answer is
    the part that is actually wanted; a bullet that carries both a value and a
    verdict goes whole, and the notice says why. Cutting inside a line was tried
    first and left readable debris ("**Bewertung:** 150-400 G/l**.").
    """
    kept = [None if _JUDGEMENT.search(line) else line for line in answer.split("\n")]
    if all(line is not None for line in kept):
        return answer
    # a heading left standing over the paragraph that just went
    for i, line in enumerate(kept):
        following = kept[i + 1:i + 3]
        if line is not None and _HEADING.match(line) and following and all(f is None or not f.strip() for f in following):
            kept[i] = None
    text = "\n".join(line for line in kept if line is not None).strip()
    # nothing survived: the answer was a verdict from end to end
    if not text:
        return _LABELS[lang]["declined"]
    return f"{text}\n\n{_LABELS[lang]['stripped']}"


async def _org_language(db: AsyncSession) -> str:
    from app.models.organization import Organization
    org = (await db.execute(select(Organization))).scalars().first()
    lang = (org.default_language if org else "en") or "en"
    return lang if lang in _LABELS else "en"


def _line(prefix: str, date: str | None, *parts: str | None) -> str:
    return " | ".join([prefix, (date or "?")[:10], *[p for p in parts if p]])


def _fact_line(f: HistoryFact, lang: str) -> str:
    return _line(_LABELS[lang]["history_fact"], f.confirmed_on, f.question, f.answer)


async def _history_facts(patient_id: uuid.UUID, db: AsyncSession) -> list[HistoryFact]:
    """ADR 047: visit-only facts describe a past visit and are never offered again."""
    return (await db.execute(
        select(HistoryFact)
        .where(HistoryFact.patient_id == patient_id, HistoryFact.is_deleted == False,  # noqa: E712
               HistoryFact.aging != "visit_only")
        .order_by(HistoryFact.confirmed_on.desc())
    )).scalars().all()


async def _structured_context(
    patient_id: uuid.UUID, db: AsyncSession, lang: str
) -> tuple[list[str], list[str]]:
    """All structured records, newest first. Returns (lines, months that have entries)."""
    L = _LABELS[lang]
    lines: list[str] = []
    months: set[str] = set()

    events = (await db.execute(
        select(CalendarEvent)
        .where(CalendarEvent.patient_id == patient_id, CalendarEvent.is_deleted == False)  # noqa: E712
        .order_by(CalendarEvent.start_at.desc())
    )).scalars().all()
    milestones = [e for e in events if e.category == EventCategory.milestone]
    appointments = [e for e in events if e.category != EventCategory.milestone]
    for e in milestones:
        lines.append(_line(L["milestone"], e.start_at, e.title, e.developmental_domain, e.description))
    for e in appointments[:APPOINTMENT_LIMIT]:
        lines.append(_line(L["appointment"], e.start_at, e.title, e.provider, e.location, e.purpose))
    if len(appointments) > APPOINTMENT_LIMIT:
        lines.append(L["cap"].format(n=APPOINTMENT_LIMIT, what=L["appointments"]))
    months.update(e.start_at[:7] for e in events if e.start_at)

    meds = (await db.execute(
        select(MedicationStatement)
        .where(MedicationStatement.patient_id == patient_id, MedicationStatement.is_deleted == False)  # noqa: E712
        .order_by(MedicationStatement.effective_start.desc().nullslast())
    )).scalars().all()
    for m in meds:
        lines.append(_line(
            L["medication"], m.effective_start, m.medication_display, m.dosage_text, m.route,
            f"{L['until']} {m.effective_end[:10]}" if m.effective_end else None,
            f"{L['status']} {m.status}",
        ))

    conditions = (await db.execute(
        select(Condition)
        .where(
            Condition.patient_id == patient_id,
            Condition.is_deleted == False,  # noqa: E712
            Condition.merged_into_id.is_(None),
        )
        .order_by(Condition.onset_date_time.desc().nullslast())
    )).scalars().all()
    for c in conditions:
        lines.append(_line(
            L["condition"], c.onset_date_time or c.recorded_date, c.code_display, c.category,
            c.severity, f"{L['status']} {c.clinical_status}",
            L["suspected"] if c.verification_status == "provisional" else None, c.note,
        ))

    incidents = (await db.execute(
        select(Incident)
        .where(Incident.patient_id == patient_id, Incident.is_deleted == False)  # noqa: E712
        .order_by(Incident.occurred_at.desc())
        .limit(INCIDENT_LIMIT + 1)
    )).scalars().all()
    for i in incidents[:INCIDENT_LIMIT]:
        lines.append(_line(
            L["incident"], i.occurred_at, i.incident_type_display or i.incident_type, i.severity,
            f"{i.duration_minutes} min" if i.duration_minutes else None, i.symptoms, i.outcome,
        ))
    months.update(i.occurred_at[:7] for i in incidents[:INCIDENT_LIMIT] if i.occurred_at)
    if len(incidents) > INCIDENT_LIMIT:
        lines.append(L["cap"].format(n=INCIDENT_LIMIT, what=L["incidents"]))

    # ADR 049: always with who reported it and how
    updates = (await db.execute(
        select(CarerUpdate)
        .where(CarerUpdate.patient_id == patient_id, CarerUpdate.is_deleted == False)  # noqa: E712
        .order_by(CarerUpdate.day.desc(), CarerUpdate.created_at.desc())
        .limit(CARER_UPDATE_LIMIT + 1)
    )).scalars().all()
    for u in updates[:CARER_UPDATE_LIMIT]:
        lines.append(_line(L["carer_update"], u.day, u.correspondent.name, u.person,
                           L["retold"] if u.retold else None, u.text))
    months.update(u.day[:7] for u in updates[:CARER_UPDATE_LIMIT])
    if len(updates) > CARER_UPDATE_LIMIT:
        lines.append(L["cap"].format(n=CARER_UPDATE_LIMIT, what=L["carer_updates"]))

    # ADR 048: the Care Notes may be quoted; the Emergency Plan never enters the context
    notes = (await db.execute(select(CareNotes).where(CareNotes.patient_id == patient_id))).scalar_one_or_none()
    for h in CARE_HEADINGS if notes else ():
        if getattr(notes, h):
            lines.append(_line(L["care_note"], notes.updated_at.date().isoformat(), L["care"][h], getattr(notes, h)))

    lines.extend(_fact_line(f, lang) for f in await _history_facts(patient_id, db))

    # ponytail: grouped in Python, not with a window function — the dashboard
    # already reads every row of this table for one Patient.
    observations = (await db.execute(
        select(Observation)
        .where(Observation.patient_id == patient_id, Observation.is_deleted == False)  # noqa: E712
        .order_by(Observation.effective_date_time.desc().nullslast())
    )).scalars().all()
    per_code: dict[str, int] = {}
    capped = False
    for o in observations:
        key = o.code or o.code_display or "?"
        per_code[key] = per_code.get(key, 0) + 1
        if per_code[key] > LAB_PER_CODE:
            capped = True
            continue
        value = o.value_string
        if o.value_quantity is not None:
            value = f"{o.value_quantity:g} {o.value_unit}" if o.value_unit else f"{o.value_quantity:g}"
        # No reference range. A value and its range on one line is an invitation
        # to compare them, and the test server's model took it ("alle drei Werte
        # liegen innerhalb des Referenzbereichs"), which is the judgement the
        # chat may not make (#113, docs/regulatory-positioning.md). The range
        # still stands in the report the reader can open.
        lines.append(_line(L["lab"], o.effective_date_time, o.code_display or o.code, value, o.panel))
    if capped:
        lines.append(L["lab_cap"].format(n=LAB_PER_CODE))

    return lines, sorted(months)


async def _document_context(
    patient_id: uuid.UUID, query: str, db: AsyncSession, lang: str, exclude: list[str] = ()
) -> tuple[list[str], list[ChatSourceDto]]:
    """Embed the query, take the nearest chunks within CHUNK_MAX_DISTANCE."""
    try:
        embedding = (await _embed_queries([query], lang))[0]
        # ADR 048: a clinician's emergency plan the Emergency Plan points at is never quoted either
        rows = await _nearest_chunks(patient_id, embedding, db, CHUNK_LIMIT, exclude)
        if not rows:
            return [], []
        label = _LABELS[lang]["document"]
        chunks = [f"{label}: {r.file_name or '?'}\n{r.content}" for r in rows]
        # deduplicated by document, not by chunk (ADR 038)
        sources: dict[str, ChatSourceDto] = {}
        for r in rows:
            if r.document_reference_id:
                sources.setdefault(str(r.document_reference_id), ChatSourceDto(
                    document_id=str(r.document_reference_id), file_name=r.file_name or "?",
                ))
        return chunks, list(sources.values())
    except Exception:
        return [], []


async def _embed_queries(texts: list[str], lang: str) -> list[list[float]]:
    import httpx
    async with httpx.AsyncClient(timeout=30, headers=settings.ai_service_headers) as client:
        resp = await client.post(
            f"{settings.ai_service_url}/embed",
            json={"texts": texts, "is_query": True, "language": lang},
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]


async def _nearest_chunks(patient_id: uuid.UUID, embedding: list[float], db: AsyncSession, k: int,
                          exclude: list[str] = ()) -> list:
    """Chunks within CHUNK_MAX_DISTANCE, nearest first, content decrypted."""
    from sqlalchemy import text
    result = await db.execute(
        text(
            "SELECT c.content, c.document_reference_id, d.file_name, "
            "       c.embedding <=> :emb AS distance "
            "FROM document_chunks c "
            "LEFT JOIN document_references d ON d.id = c.document_reference_id "
            "WHERE c.patient_id = :pid AND c.is_deleted = false AND c.embedding IS NOT NULL "
            "  AND (d.id IS NULL OR d.is_deleted = false) "
            "ORDER BY distance LIMIT :k"
        ),
        {"pid": str(patient_id), "emb": str(embedding), "k": k},
    )
    rows = [r for r in result.fetchall() if r.distance is not None and r.distance <= CHUNK_MAX_DISTANCE
            and str(r.document_reference_id) not in exclude]
    if not rows:
        return []
    # chunk content is ciphertext at rest (ADR-031)
    from types import SimpleNamespace
    from app.core.encryption import decrypt_str
    from app.core.patient_keys import get_patient_kek
    kek = await get_patient_kek(db, patient_id)
    return [SimpleNamespace(content=decrypt_str(r.content, kek), document_reference_id=r.document_reference_id,
                            file_name=r.file_name) for r in rows]


async def _chat_model(db: AsyncSession) -> str | None:
    """The model an admin picked for the chat stage (ADR 005). Without it the
    aiservice silently falls back to its own default."""
    from app.models.system import SystemSetting
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == "ai.model.chat"))
    setting = result.scalar_one_or_none()
    return setting.value if setting else None


@router.post("/patients/{patient_id}/chat", response_model=ChatResponse)
async def chat(
    patient_id: uuid.UUID,
    body: ChatRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    # the demo's visitors share one login: nobody reads another's questions, and each IP has a budget
    demo = bool(settings.demo_locked_upload_sha256)
    if demo:
        await enforce(f"rl:demo:chat:{client_ip(request)}", limit=20, window_seconds=3600)
    lang = await _org_language(db)
    plan = (await db.execute(select(EmergencyPlan).where(EmergencyPlan.patient_id == patient_id))).scalar_one_or_none()
    plan_med_ids = [s["medication_id"] for sit in plan.situations for s in sit["steps"] if s.get("medication_id")] if plan else []
    plan_meds = (await db.execute(
        select(MedicationStatement.medication_display).where(MedicationStatement.id.in_(plan_med_ids))
    )).scalars().all() if plan_med_ids else []
    if _is_emergency(body.question, plan_meds):
        if not demo:
            await _store(patient_id, user.id, body.question, _LABELS[lang]["emergency"], db)
        return ChatResponse(answer=_LABELS[lang]["emergency"], history=await _get_history(patient_id, user.id, db),
                            emergency_plan=True)

    # an emergency question and its pointer stay out, or a follow-up would carry it to the model
    full = [] if demo else await _get_history(patient_id, user.id, db)
    history = [m for i, m in enumerate(full)
               if not m.emergency_plan and not (i + 1 < len(full) and full[i + 1].emergency_plan)][-HISTORY_WINDOW:]
    # "und wann war der letzte?" embeds to nothing on its own — the previous
    # question carries the subject (ADR 038).
    previous = next((m.content for m in reversed(history) if m.role == "user"), "")
    records, months = await _structured_context(patient_id, db, lang)
    chunks, sources = await _document_context(
        patient_id, f"{previous}\n{body.question}".strip(), db, lang, plan.document_ids if plan else [],
    )

    import httpx
    answer = None
    busy = False
    try:
        # 60s turned every answer into "der KI-Dienst antwortet gerade nicht".
        # The ~50s warm that forced this up was the model thinking, not the model
        # answering; with thinking disabled the same context comes back in under
        # 20s. The margin stays for a cold load, which still costs a minute.
        async with httpx.AsyncClient(timeout=240, headers=settings.ai_service_headers) as client:
            resp = await client.post(f"{settings.ai_service_url}/chat", json={
                "question": body.question,
                # Documents first, records last: what stands at the end of the
                # prompt is what the model answers from, and a question about
                # the record ("seit wann geben wir Ergenyl") is answered by the
                # records (#200).
                "context_chunks": chunks + records,
                "history": [{"role": m.role, "content": m.content} for m in history],
                "model": await _chat_model(db),
            })
            busy = resp.status_code == 429  # the provider's shared rate limit (#374)
            if resp.status_code == 200:
                answer = resp.json().get("answer")
                # filtered before it is returned and before it is stored: the
                # record holds what the reader saw, not what the model said
                if answer:
                    answer = _strip_judgement(answer, lang)
    except Exception:
        pass
    # A dead AI service used to answer "AI service unavailable." — and that
    # sentence was then stored as an assistant message under the patient KEK,
    # forever, in a record meant to hold what was actually said. It is an
    # outage, so it is a 503 and nothing is written.
    if busy:
        raise HTTPException(status_code=429, detail="ai_busy")
    if not answer:
        raise HTTPException(status_code=503, detail="ai_service_unavailable")

    if not demo:
        await _store(patient_id, user.id, body.question, answer, db)

    return ChatResponse(
        answer=answer,
        history=await _get_history(patient_id, user.id, db),
        sources=sources,
        months=months,
    )


@router.get("/patients/{patient_id}/chat/history", response_model=ChatHistoryDto)
async def get_chat_history(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    messages = await _get_history(patient_id, user.id, db)
    return ChatHistoryDto(messages=messages)


async def _store(patient_id: uuid.UUID, user_id: uuid.UUID, question: str, answer: str, db: AsyncSession) -> None:
    """Content is encrypted under the patient KEK (ADR-031)."""
    from app.core.encryption import encrypt_str
    from app.core.patient_keys import ensure_patient_kek
    kek = await ensure_patient_kek(db, patient_id)
    for role, content in [("user", question), ("assistant", answer)]:
        db.add(ChatMessage(patient_id=patient_id, user_id=user_id, role=role, content=encrypt_str(content, kek)))
    await db.commit()


async def _get_history(patient_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> list[ChatMessageDto]:
    result = await db.execute(
        select(ChatMessage).where(
            ChatMessage.patient_id == patient_id,
            ChatMessage.user_id == user_id,
            ChatMessage.is_deleted == False,  # noqa: E712
        ).order_by(ChatMessage.created_at.asc()).limit(50)
    )
    messages = result.scalars().all()
    if not messages:
        return []
    from app.core.encryption import decrypt_str
    from app.core.patient_keys import get_patient_kek
    kek = await get_patient_kek(db, patient_id)
    return [ChatMessageDto(role=m.role, content=(c := decrypt_str(m.content, kek)), timestamp=m.created_at,
                           emergency_plan=m.role == "assistant" and _is_pointer(c)) for m in messages]
