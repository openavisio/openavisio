"""One-off: merge the duplicate conditions and medications verify piled up (#129).

Every verified document re-added its diagnoses, so a patient with eight letters
naming the same condition ends up with eight rows. New uploads no longer do this
— this cleans up what is already there.

Only EXACT duplicates after normalising case and whitespace. Spelling variants
("Dup15q Syndrom" vs "15q11-q13 Mikroduplikationssyndrom", "Ataxie" vs "Leichte
Ataxie") are left alone: judging those to be the same condition is a medical
decision, not a string operation (#113). They need a human.

    docker compose exec -T backend uv run python -m app.scripts.dedupe_clinical          # dry run
    docker compose exec -T backend uv run python -m app.scripts.dedupe_clinical --apply
"""

import asyncio
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.condition import Condition
from app.models.medication import MedicationStatement
from app.models.patient import Patient


def _norm(name: str) -> str:
    return " ".join((name or "").strip().lower().rstrip(":.").split())


def _score(c: Condition) -> tuple:
    """Which row to keep: the one carrying the most information."""
    return (
        c.onset_date_time is not None,
        c.severity is not None,
        c.code is not None,
        c.document_reference_id is not None,
        str(c.created_at),  # oldest wins ties — it is the first record of the diagnosis
    )


async def main(apply: bool) -> None:
    async with AsyncSessionLocal() as db:
        patients = (await db.execute(select(Patient).where(Patient.is_deleted == False))).scalars().all()  # noqa: E712

        total_removed = 0
        for p in patients:
            rows = (await db.execute(
                select(Condition).where(
                    Condition.patient_id == p.id,
                    Condition.is_deleted == False,  # noqa: E712
                )
            )).scalars().all()

            groups: dict[str, list[Condition]] = {}
            for c in rows:
                groups.setdefault(_norm(c.code_display), []).append(c)

            dupes = {k: v for k, v in groups.items() if len(v) > 1}
            if not dupes:
                continue

            print(f"\n{p.given_name} {p.family_name}: {len(rows)} Diagnosen, {len(dupes)} davon mehrfach")
            for key, group in sorted(dupes.items()):
                group.sort(key=_score, reverse=True)
                keep, drop = group[0], group[1:]
                print(f"  {keep.code_display!r}: {len(group)}x -> behalte 1, entferne {len(drop)}")
                for c in drop:
                    if apply:
                        c.is_deleted = True
                    total_removed += 1

        # Medications are a COURSE, not a state: same drug at a different dose is a
        # dose change, not a duplicate. Only fold rows that are identical in name AND
        # dosage AND period — those carry no information the other does not.
        for p in patients:
            meds = (await db.execute(
                select(MedicationStatement).where(
                    MedicationStatement.patient_id == p.id,
                    MedicationStatement.is_deleted == False,  # noqa: E712
                )
            )).scalars().all()

            mgroups: dict[tuple, list[MedicationStatement]] = {}
            for m in meds:
                mgroups.setdefault(
                    (_norm(m.medication_display), _norm(m.dosage_text or ""),
                     m.effective_start or "", m.effective_end or ""),
                    [],
                ).append(m)

            mdupes = {k: v for k, v in mgroups.items() if len(v) > 1}
            if not mdupes:
                continue

            print(f"\n{p.given_name} {p.family_name}: {len(meds)} Medikamente, {len(mdupes)} davon mehrfach")
            for key, group in sorted(mdupes.items()):
                group.sort(key=lambda m: str(m.created_at))
                keep, drop = group[0], group[1:]
                print(f"  {keep.medication_display!r} ({keep.dosage_text or 'ohne Dosierung'}): "
                      f"{len(group)}x -> behalte 1, entferne {len(drop)}")
                for m in drop:
                    if apply:
                        m.is_deleted = True
                    total_removed += 1

        if apply:
            await db.commit()
            print(f"\n{total_removed} Dubletten entfernt.")
        else:
            print(f"\nProbelauf: {total_removed} Dubletten würden entfernt. Mit --apply ausführen.")


if __name__ == "__main__":
    asyncio.run(main(apply="--apply" in sys.argv))
