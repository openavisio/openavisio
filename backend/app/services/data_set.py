"""The rows a Data Set Sharing Purpose asks for, and its CSV (ADR 064)."""

import csv
import io
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.development import Ability, AbilityObservation, TestAttempt
from app.models.patient import Patient
from app.models.sharing import DataSet, SharingPurpose

COLUMNS = {
    DataSet.test_attempts: ["test", "date", "age_months", "setting", "duration_minutes", "outcome", "reason"],
    DataSet.ability_observations: [
        "ability", "domain", "date", "age_months", "place", "works", "with_help", "note", "source",
    ],
}


def age_months(birth_date: str | None, on: str) -> int | None:
    """Whole months between birth and a YYYY-MM or YYYY-MM-DD date; a month-only date ignores the day."""
    if not birth_date or len(birth_date) < 10:
        return None
    by, bm, bd = int(birth_date[:4]), int(birth_date[5:7]), int(birth_date[8:10])
    y, m = int(on[:4]), int(on[5:7])
    months = (y - by) * 12 + (m - bm)
    if len(on) == 10 and int(on[8:10]) < bd:
        months -= 1
    return months if months >= 0 else None


def _since_ok(on: str, since: str | None) -> bool:
    # a month-only date counts if its month is the since month or later
    return since is None or on >= since[: len(on)]


async def matching_rows(db: AsyncSession, purpose: SharingPurpose, patient: Patient) -> list[dict]:
    """Every row of this Patient the Data Set covers, as {"id", "values"}."""
    if purpose.data_set == DataSet.test_attempts:
        res = await db.execute(
            select(TestAttempt).where(TestAttempt.patient_id == patient.id, TestAttempt.is_deleted == False)  # noqa: E712
            .order_by(TestAttempt.attempted_on)
        )
        return [
            {"id": t.id, "values": {
                "test": t.test_name, "date": t.attempted_on, "age_months": age_months(patient.birth_date, t.attempted_on),
                "setting": t.setting, "duration_minutes": t.duration_minutes, "outcome": t.outcome, "reason": t.reason,
            }}
            for t in res.scalars() if _since_ok(t.attempted_on, purpose.data_set_since)
        ]
    if purpose.data_set == DataSet.ability_observations:
        q = (
            select(AbilityObservation, Ability).join(Ability, Ability.id == AbilityObservation.ability_id)
            .where(
                AbilityObservation.patient_id == patient.id,
                AbilityObservation.is_deleted == False,  # noqa: E712
                Ability.is_deleted == False,  # noqa: E712
            )
            .order_by(Ability.name, AbilityObservation.observed_on)
        )
        if purpose.data_set_domain:
            q = q.where(Ability.domain == purpose.data_set_domain)
        res = await db.execute(q)
        return [
            {"id": o.id, "values": {
                "ability": a.name, "domain": a.domain, "date": o.observed_on,
                "age_months": age_months(patient.birth_date, o.observed_on), "place": o.place,
                "works": o.works, "with_help": o.with_help, "note": o.note, "source": o.source,
            }}
            for o, a in res.all() if _since_ok(o.observed_on, purpose.data_set_since)
        ]
    return []


def _cell(v) -> str:
    if v is True:
        return "yes"
    if v is False:
        return "no"
    if v is None:
        return ""
    v = str(v)
    # free text must not run as a spreadsheet formula
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


def to_csv(data_set: str, labelled: list[tuple[str, list[dict]]]) -> bytes:
    """One CSV across all Patients: UTF-8 with BOM and semicolons, so Excel opens it on a double click."""
    cols = COLUMNS[DataSet(data_set)]
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["patient", *cols])
    for label, rows in labelled:
        for r in rows:
            w.writerow([_cell(label), *(_cell(r.get(c)) for c in cols)])
    return ("\ufeff" + buf.getvalue()).encode()
