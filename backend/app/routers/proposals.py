"""Proposal Review: open Proposals of all Documents, sorted by content (ADR 058).

Diagnoses, and a therapy report's Abilities and Test Attempts (ADR 063); the other kinds
still go through the per-Document verify.
"""

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.access import AccessLevel, require_patient_access
from app.core.config import settings
from app.core.database import get_db
from app.core.encryption import decrypt_str, encrypt_str
from app.core.patient_keys import get_patient_kek
from app.deps import get_current_user
from app.models.condition import Condition, ConditionSource
from app.models.document import DocumentReference
from app.models.proposal import NameGrouping, Proposal
from app.models.user import User
from app.routers.documents import _norm_condition

router = APIRouter()



class DecideRequest(BaseModel):
    proposal_ids: list[uuid.UUID]
    accept: bool
    name: str | None = None            # the Diagnosis name to keep
    condition_id: uuid.UUID | None = None  # attach to this record entry


# kind -> (extraction_json key, the field that names it)
KINDS = {"diagnosis": ("diagnoses", "name"), "ability": ("abilities", "name"), "test_attempt": ("test_attempts", "test_name")}


async def ensure_proposals(db: AsyncSession, patient_id: uuid.UUID, kek, kind: str = "diagnosis") -> None:
    """One Proposal per extracted entry of the kind, made once per Document."""
    key, field = KINDS[kind]
    # ponytail: decrypts every Document without such Proposals on each open, cheap at hundreds
    have = select(Proposal.document_reference_id).where(Proposal.kind == kind)
    where = [DocumentReference.patient_id == patient_id, DocumentReference.is_deleted == False,  # noqa: E712
             DocumentReference.extraction_json.isnot(None), DocumentReference.id.not_in(have)]
    if kind == "diagnosis":  # a verified letter decided its diagnoses on its own form
        where.append(DocumentReference.verification_status == "extracted")
    for doc in (await db.execute(select(DocumentReference).where(*where))).scalars().all():
        ej = doc.extraction_json
        ej = json.loads(decrypt_str(ej, kek) or "{}") if isinstance(ej, str) else ej
        for i, entry in enumerate(ej.get(key) or []):
            if (entry.get(field) or "").strip():
                db.add(Proposal(patient_id=patient_id, document_reference_id=doc.id, kind=kind, index=i,
                                payload=encrypt_str(json.dumps(entry), kek)))
    await db.commit()


async def ensure_diagnosis_proposals(db: AsyncSession, patient_id: uuid.UUID, kek) -> None:
    await ensure_proposals(db, patient_id, kek, "diagnosis")


async def _group(names: list[str], record: list[str], db: AsyncSession, kind: str = "diagnosis") -> list[list[str]] | None:
    """The chat model's groups, None when it cannot be asked."""
    import httpx
    from app.routers.chat import _chat_model
    try:
        async with httpx.AsyncClient(timeout=180, headers=settings.ai_service_headers) as client:
            resp = await client.post(f"{settings.ai_service_url}/group", json={
                "names": names, "record": record, "model": await _chat_model(db), "kind": kind})
        return resp.json()["groups"] if resp.status_code == 200 else None
    except Exception:
        return None


async def diagnosis_name_groups(db: AsyncSession, patient_id: uuid.UUID, kek) -> tuple[list[list[str]], bool]:
    """Groups over every diagnosis name in the letters and the record, stored (ADR 058).

    The whole set, not only the open names: deciding a group must not change
    the key, or every decision would cost another model call. Returns
    (groups, by_model); without the model, names group by identical text.
    """
    # ponytail: decrypts every Document on each call, cheap at hundreds
    docs = (await db.execute(select(DocumentReference.extraction_json).where(
        DocumentReference.patient_id == patient_id, DocumentReference.is_deleted == False,  # noqa: E712
        DocumentReference.extraction_json.isnot(None)))).scalars().all()
    letters: set[str] = set()
    for ej in docs:
        ej = json.loads(decrypt_str(ej, kek) or "{}") if isinstance(ej, str) else ej
        letters |= {(d.get("name") or "").strip() for d in ej.get("diagnoses") or []}
    record = set((await db.execute(select(Condition.code_display).where(
        Condition.patient_id == patient_id, Condition.is_deleted == False))).scalars())  # noqa: E712
    return await stored_groups(db, patient_id, kek, "diagnosis", letters, record)


async def stored_groups(db: AsyncSession, patient_id: uuid.UUID, kek, kind: str,
                        letters: set[str], record: set[str]) -> tuple[list[list[str]], bool]:
    """The model's groups over letters | record, kept until that set changes (ADR 058)."""
    names = sorted((letters | record) - {""})
    row = (await db.execute(select(NameGrouping).where(
        NameGrouping.patient_id == patient_id, NameGrouping.kind == kind))).scalar_one_or_none()
    if row:
        stored = json.loads(decrypt_str(row.payload, kek))
        if stored["names"] == names:
            return stored["groups"], True
    groups = await _group(sorted(set(names) - record), sorted(record & set(names)), db, kind) if names else []
    if groups is None:  # an outage must not read as "nothing belongs together"
        buckets: dict[str, list[str]] = {}
        for n in names:
            buckets.setdefault(_norm_condition(n), []).append(n)
        return list(buckets.values()), False
    payload = encrypt_str(json.dumps({"names": names, "groups": groups}), kek)
    if row:
        row.payload = payload
    else:
        db.add(NameGrouping(patient_id=patient_id, kind=kind, payload=payload))
    await db.commit()
    return groups, True


@router.get("/patients/{patient_id}/proposals/diagnoses")
async def diagnosis_groups(patient_id: uuid.UUID, user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    kek = await get_patient_kek(db, patient_id)
    await ensure_diagnosis_proposals(db, patient_id, kek)
    rows = (await db.execute(
        select(Proposal, DocumentReference).join(DocumentReference, DocumentReference.id == Proposal.document_reference_id)
        .where(Proposal.patient_id == patient_id, Proposal.kind == "diagnosis", Proposal.status == "open",
               DocumentReference.is_deleted == False)  # noqa: E712
    )).all()
    record = (await db.execute(select(Condition).where(
        Condition.patient_id == patient_id, Condition.is_deleted == False))).scalars().all()  # noqa: E712

    spellings: dict[str, list] = {}
    for p, doc in rows:
        dx = json.loads(decrypt_str(p.payload, kek))
        spellings.setdefault(dx["name"].strip(), []).append((p, doc, dx))
    groups, by_model = await diagnosis_name_groups(db, patient_id, kek) if spellings else ([], True)

    by_name = {c.code_display: c for c in record}
    out = []
    for g in groups:
        mentions = [m for n in g for m in spellings.get(n, [])]
        if not mentions:
            continue
        entry = next((by_name[n] for n in g if n in by_name), None)
        newest = max(mentions, key=lambda m: (m[1].issued_date is not None, m[1].issued_date))
        out.append({
            "record": {"id": str(entry.id), "name": entry.code_display} if entry else None,
            "suggested_name": entry.code_display if entry else newest[2]["name"].strip(),
            "spellings": [{
                "name": n,
                "proposal_ids": [str(p.id) for p, _, _ in spellings[n]],
                "provisional": all(dx.get("verification_status") == "provisional" for _, _, dx in spellings[n]),
                "documents": [{"id": str(d.id), "label": d.detected_provider or d.file_name,
                               "file_name": d.file_name,
                               "issued_date": d.issued_date.isoformat() if d.issued_date else None}
                              for _, d, _ in spellings[n]],
            } for n in g if n in spellings],
        })
    # the groups most letters repeat first: that is where one decision saves the most
    out.sort(key=lambda g: -sum(len(s["proposal_ids"]) for s in g["spellings"]))
    return {"grouped_by_model": by_model, "groups": out}


@router.post("/patients/{patient_id}/proposals/diagnoses/decide", status_code=status.HTTP_204_NO_CONTENT)
async def decide_diagnoses(patient_id: uuid.UUID, body: DecideRequest, user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    props = (await db.execute(select(Proposal).where(
        Proposal.id.in_(body.proposal_ids), Proposal.patient_id == patient_id,
        Proposal.kind == "diagnosis", Proposal.status == "open"))).scalars().all()
    if len(props) != len(set(body.proposal_ids)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Proposal not open")
    now = datetime.now(UTC)
    cond = None
    if body.accept:
        kek = await get_patient_kek(db, patient_id)
        docs = {d.id: d for d in (await db.execute(select(DocumentReference).where(
            DocumentReference.id.in_({p.document_reference_id for p in props})))).scalars()}
        mentions = sorted(((json.loads(decrypt_str(p.payload, kek)), docs[p.document_reference_id]) for p in props),
                          key=lambda m: (m[1].issued_date is None, m[1].issued_date))
        name = (body.name or "").strip() or mentions[-1][0]["name"].strip()
        stated = any(dx.get("verification_status") != "provisional" for dx, _ in mentions)
        existing = (await db.execute(select(Condition).options(selectinload(Condition.sources)).where(
            Condition.patient_id == patient_id, Condition.is_deleted == False))).scalars().all()  # noqa: E712
        cond = next((c for c in existing if body.condition_id and c.id == body.condition_id), None) \
            or next((c for c in existing if _norm_condition(c.code_display) == _norm_condition(name)), None)
        if body.condition_id and cond is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        if cond is None:
            dx, first = mentions[-1][0], mentions[0][1]
            reaction = (dx.get("reaction") or None) if dx.get("category") == "allergy" else None
            cond = Condition(patient_id=patient_id, owner_id=user.id, document_reference_id=first.id,
                             code_display=name, clinical_status=dx.get("status") or "active",
                             category=dx.get("category"), severity=dx.get("severity"), note=reaction,
                             onset_date_time=dx.get("onset_date"),
                             verification_status=None if stated else "provisional", sources=[])
            db.add(cond)
        else:
            cond.code_display = name  # renaming is offered, the record's name preselected
            # stated beats suspected, a suspicion never downgrades (#271)
            if cond.verification_status == "provisional" and stated:
                cond.verification_status = None
        cited = {s.document_reference_id for s in cond.sources}
        for doc_id in dict.fromkeys(d.id for _, d in mentions):
            if doc_id not in cited:
                cond.sources.append(ConditionSource(document_reference_id=doc_id))
        await db.flush()
    for p in props:
        p.status, p.decided_at, p.decided_by = ("accepted" if body.accept else "rejected"), now, user.id
        p.record_id = cond.id if cond else None
    await db.commit()


@router.get("/patients/{patient_id}/documents/novelty")
async def document_novelty(patient_id: uuid.UUID, user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    """Per Document, what no earlier letter said yet, and which earlier letter it mostly repeats."""
    from app.routers.documents import _norm_dosage
    from app.services.lab_codes import canonical_code, parse_number
    await require_patient_access(patient_id, user, db)
    kek = await get_patient_kek(db, patient_id)
    docs = (await db.execute(select(DocumentReference).where(
        DocumentReference.patient_id == patient_id, DocumentReference.is_deleted == False,  # noqa: E712
        DocumentReference.extraction_json.isnot(None)))).scalars().all()
    docs.sort(key=lambda d: d.issued_date or d.created_at.date())
    content = []
    for d in docs:
        ej = d.extraction_json
        ej = json.loads(decrypt_str(ej, kek) or "{}") if isinstance(ej, str) else ej
        content.append((d, ej))

    groups, _ = await diagnosis_name_groups(db, patient_id, kek)  # the same stored groups as the review
    group_of = {n: i for i, g in enumerate(groups) for n in g}

    seen: dict[tuple, uuid.UUID] = {}
    out = {}
    for d, ej in content:
        dd = d.issued_date.isoformat() if d.issued_date else ""
        items = []
        for x in ej.get("diagnoses") or []:
            n = (x.get("name") or "").strip()
            if n:
                items.append(("diagnoses", ("dx", group_of.get(n, _norm_condition(n)))))
        for x in ej.get("medications") or []:
            if x.get("name"):
                items.append(("medications", ("med", _norm_condition(x["name"]), _norm_dosage(x.get("dosage") or ""))))
        for x in ej.get("observations") or []:
            num = parse_number(x.get("value"))
            items.append(("observations", ("obs", canonical_code(x.get("type")) or _norm_condition(x.get("type") or ""),
                                           (x.get("date") or dd)[:10], num if num is not None else str(x.get("value")))))
        new = {"diagnoses": 0, "medications": 0, "observations": 0}
        sources: dict[uuid.UUID, int] = {}
        for k, kind in {k: kind for kind, k in items}.items():
            if k in seen:
                sources[seen[k]] = sources.get(seen[k], 0) + 1
            else:
                new[kind] += 1
                seen[k] = d.id
        known = sum(sources.values())
        top = max(sources, key=sources.get) if sources else None
        # "repeats" only when most of what it says stood in that one earlier letter
        ref = next((x for x, _ in content if x.id == top), None) if top and known >= sum(new.values()) else None
        out[str(d.id)] = {"new": new, "known": known, "repeats": {
            "id": str(ref.id), "label": ref.detected_provider or ref.file_name,
            "issued_date": ref.issued_date.isoformat() if ref.issued_date else None} if ref else None}
    return out


class CorrespondentDecideRequest(BaseModel):
    document_ids: list[uuid.UUID]
    name: str                                 # the Correspondent's name to keep
    correspondent_id: uuid.UUID | None = None  # an existing Correspondent to use


async def _correspondents(db: AsyncSession):
    from app.models.correspondent import Correspondent
    return (await db.execute(select(Correspondent).where(Correspondent.is_deleted == False))).scalars().all()  # noqa: E712


@router.get("/patients/{patient_id}/proposals/correspondents")
async def correspondent_groups(patient_id: uuid.UUID, user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    """Letterhead names of letters without a Correspondent, grouped by who sent them (ADR 058)."""
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    kek = await get_patient_kek(db, patient_id)
    docs = (await db.execute(select(DocumentReference).where(
        DocumentReference.patient_id == patient_id, DocumentReference.is_deleted == False,  # noqa: E712
        DocumentReference.detected_provider.isnot(None)))).scalars().all()
    record = await _correspondents(db)
    by_name = {c.name: c for c in record}
    spellings: dict[str, list] = {}
    for d in docs:
        if d.correspondent_id is None and d.detected_provider.strip():
            spellings.setdefault(d.detected_provider.strip(), []).append(d)
    if not spellings:
        return {"grouped_by_model": True, "groups": []}
    groups, by_model = await stored_groups(
        db, patient_id, kek, "correspondent", {(d.detected_provider or "").strip() for d in docs}, set(by_name))

    out = []
    for g in groups:
        open_names = [n for n in g if n in spellings]
        if not open_names:
            continue
        entry = next((by_name[n] for n in g if n in by_name), None)
        # the shortest spelling: department, legal form and letterhead details are what varies
        common = min(open_names, key=lambda n: (len(n), -len(spellings[n])))
        out.append({
            "record": {"id": str(entry.id), "name": entry.name} if entry else None,
            "suggested_name": entry.name if entry else common,
            "spellings": [{
                "name": n,
                "document_ids": [str(d.id) for d in spellings[n]],
                "documents": [{"id": str(d.id), "label": d.type or d.file_name, "file_name": d.file_name,
                               "issued_date": d.issued_date.isoformat() if d.issued_date else None}
                              for d in spellings[n]],
            } for n in open_names],
        })
    out.sort(key=lambda g: -sum(len(s["document_ids"]) for s in g["spellings"]))
    return {"grouped_by_model": by_model, "groups": out}


@router.post("/patients/{patient_id}/proposals/correspondents/decide", status_code=status.HTTP_204_NO_CONTENT)
async def decide_correspondents(patient_id: uuid.UUID, body: CorrespondentDecideRequest, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    """Give every letter of a group the same Correspondent, a new or an existing one."""
    from app.models.correspondent import Correspondent
    from app.routers.correspondents import _get_org_id
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="name required")
    docs = (await db.execute(select(DocumentReference).where(
        DocumentReference.id.in_(body.document_ids), DocumentReference.patient_id == patient_id,
        DocumentReference.is_deleted == False))).scalars().all()  # noqa: E712
    if len(docs) != len(set(body.document_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    existing = await _correspondents(db)
    corr = next((c for c in existing if body.correspondent_id and c.id == body.correspondent_id), None) \
        or next((c for c in existing if _norm_condition(c.name) == _norm_condition(name)), None)
    if body.correspondent_id and corr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if corr is None:
        corr = Correspondent(name=name, organization_id=await _get_org_id(db))
        db.add(corr)
        await db.flush()
    else:
        corr.name = name  # renaming is offered, the existing name preselected
    for d in docs:
        d.correspondent_id = corr.id
    await db.commit()


# --- Abilities and Test Attempts from therapy reports (ADR 063, #465) ---------

def _doc_dto(d: DocumentReference, **extra) -> dict:
    return {"id": str(d.id), "label": d.detected_provider or d.file_name, "file_name": d.file_name,
            "issued_date": d.issued_date.isoformat() if d.issued_date else None, **extra}


async def _open(db: AsyncSession, patient_id: uuid.UUID, kek, kind: str) -> list[tuple]:
    await ensure_proposals(db, patient_id, kek, kind)
    rows = (await db.execute(
        select(Proposal, DocumentReference).join(DocumentReference, DocumentReference.id == Proposal.document_reference_id)
        .where(Proposal.patient_id == patient_id, Proposal.kind == kind, Proposal.status == "open",
               DocumentReference.is_deleted == False)  # noqa: E712
    )).all()
    return [(p, d, json.loads(decrypt_str(p.payload, kek))) for p, d in rows]


@router.get("/patients/{patient_id}/proposals/abilities")
async def ability_groups(patient_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """What therapy reports say the child can do now, grouped by ability like diagnoses (ADR 058, 063)."""
    from app.models.development import Ability
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    kek = await get_patient_kek(db, patient_id)
    spellings: dict[str, list] = {}
    for p, d, a in await _open(db, patient_id, kek, "ability"):
        spellings.setdefault(a["name"].strip(), []).append((p, d, a))
    if not spellings:
        return {"grouped_by_model": True, "groups": []}
    record = {a.name: a for a in (await db.execute(select(Ability).where(
        Ability.patient_id == patient_id, Ability.is_deleted.is_(False)))).scalars()}
    groups, by_model = await stored_groups(db, patient_id, kek, "ability", set(spellings), set(record))
    out = []
    for g in groups:
        if not any(n in spellings for n in g):
            continue
        entry = next((record[n] for n in g if n in record), None)
        newest = max((m for n in g for m in spellings.get(n, [])), key=lambda m: (m[1].issued_date is not None, m[1].issued_date))
        out.append({
            "record": {"id": str(entry.id), "name": entry.name} if entry else None,
            "suggested_name": entry.name if entry else newest[2]["name"].strip(),
            "spellings": [{
                "name": n, "proposal_ids": [str(p.id) for p, _, _ in spellings[n]], "provisional": False,
                "documents": [_doc_dto(d, quote=a["quote"], labels=[
                    "works" if a["works"] else "fails", "with_help" if a.get("with_help") else "alone", *filter(None, [a.get("place")])])
                    for _, d, a in spellings[n]],
            } for n in g if n in spellings],
        })
    out.sort(key=lambda g: -sum(len(s["proposal_ids"]) for s in g["spellings"]))
    return {"grouped_by_model": by_model, "groups": out}


@router.get("/patients/{patient_id}/proposals/test-attempts")
async def test_attempt_proposals(patient_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """One card per test a report says was tried; never a score (ADR 063)."""
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    kek = await get_patient_kek(db, patient_id)
    return {"grouped_by_model": True, "groups": [{
        "record": None, "suggested_name": t["test_name"],
        "spellings": [{"name": t["test_name"], "proposal_ids": [str(p.id)], "provisional": False,
                       "documents": [_doc_dto(d, quote=t.get("reason"), labels=[t["outcome"]], date=t.get("date"))]}],
    } for p, d, t in await _open(db, patient_id, kek, "test_attempt")]}


class DevelopmentDecideRequest(BaseModel):
    proposal_ids: list[uuid.UUID]
    accept: bool
    name: str | None = None              # the Ability or test name to keep
    ability_id: uuid.UUID | None = None  # attach to this Ability


async def _decide(db: AsyncSession, patient_id: uuid.UUID, user: User, body: DevelopmentDecideRequest, kind: str):
    props = (await db.execute(select(Proposal).where(
        Proposal.id.in_(body.proposal_ids), Proposal.patient_id == patient_id,
        Proposal.kind == kind, Proposal.status == "open"))).scalars().all()
    if not props or len(props) != len(set(body.proposal_ids)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Proposal not open")
    kek = await get_patient_kek(db, patient_id)
    docs = {d.id: d for d in (await db.execute(select(DocumentReference).where(
        DocumentReference.id.in_({p.document_reference_id for p in props})))).scalars()}
    return props, kek, docs


def _close(props, user: User, accept: bool, record_ids: list) -> None:
    now = datetime.now(UTC)
    for p, rid in zip(props, record_ids):
        p.status, p.decided_at, p.decided_by, p.record_id = ("accepted" if accept else "rejected"), now, user.id, rid


@router.post("/patients/{patient_id}/proposals/abilities/decide", status_code=status.HTTP_204_NO_CONTENT)
async def decide_abilities(patient_id: uuid.UUID, body: DevelopmentDecideRequest, user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    """Accepted: one Observation per report, dated to it, citing it (ADR 063)."""
    from app.models.development import Ability, AbilityObservation
    from app.routers.development import _ability_named, _audit
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    props, kek, docs = await _decide(db, patient_id, user, body, "ability")
    if not body.accept:
        _close(props, user, False, [None] * len(props))
        await db.commit()
        return
    mentions = [(json.loads(decrypt_str(p.payload, kek)), docs[p.document_reference_id]) for p in props]
    name = " ".join((body.name or mentions[-1][0]["name"]).split())[:256]
    ability = None
    if body.ability_id:
        ability = (await db.execute(select(Ability).where(
            Ability.id == body.ability_id, Ability.patient_id == patient_id, Ability.is_deleted.is_(False)))).scalar_one_or_none()
        if ability is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    ability = ability or await _ability_named(patient_id, name, db)
    if ability is None:
        ability = Ability(patient_id=patient_id, owner_id=user.id, name=name,
                          domain=next((a.get("domain") for a, _ in mentions if a.get("domain")), None))
        db.add(ability)
        await db.flush()
    ids = []
    for a, d in mentions:
        obs = AbilityObservation(patient_id=patient_id, owner_id=user.id, ability_id=ability.id,
                                 observed_on=(d.issued_date or d.created_at.date()).isoformat(), place=a.get("place"),
                                 works=a["works"], with_help=bool(a.get("with_help")), note=a["quote"],
                                 source="document", document_id=d.id)
        db.add(obs)
        await db.flush()
        _audit(db, user, "created", "AbilityObservation", obs.id, {"source": "document", "document_id": str(d.id)})
        ids.append(obs.id)
    _close(props, user, True, ids)
    await db.commit()


@router.post("/patients/{patient_id}/proposals/test-attempts/decide", status_code=status.HTTP_204_NO_CONTENT)
async def decide_test_attempts(patient_id: uuid.UUID, body: DevelopmentDecideRequest, user: User = Depends(get_current_user),
                               db: AsyncSession = Depends(get_db)):
    """Accepted: a Test Attempt with the report linked and its sender as who ran it; no score (ADR 063)."""
    from app.models.development import TestAttempt
    from app.routers.development import _audit
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    props, kek, docs = await _decide(db, patient_id, user, body, "test_attempt")
    ids = []
    for p in props:
        if not body.accept:
            ids.append(None)
            continue
        t, d = json.loads(decrypt_str(p.payload, kek)), docs[p.document_reference_id]
        row = TestAttempt(patient_id=patient_id, owner_id=user.id,
                          test_name=" ".join((body.name or t["test_name"]).split())[:256],
                          attempted_on=t.get("date") or (d.issued_date or d.created_at.date()).isoformat(),
                          correspondent_id=d.correspondent_id, outcome=t["outcome"], reason=t.get("reason"), document_id=d.id)
        db.add(row)
        await db.flush()
        _audit(db, user, "created", "TestAttempt", row.id, {"source": "document", "document_id": str(d.id)})
        ids.append(row.id)
    _close(props, user, body.accept, ids)
    await db.commit()
