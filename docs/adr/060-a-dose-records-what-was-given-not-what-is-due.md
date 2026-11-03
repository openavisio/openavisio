# A Dose records what was given, not what is due

When someone steps in for a day, the first question is whether the morning medication was already given. A Medication in OpenAvisio is the plan (drug, dosage, period); the Health Log carries one yes/no for the Patient's own medication compliance. Nothing records "Keppra at 08:00, given by Oma". Prompted by #368. Terms are in `GLOSSARY.md` under "Dose".

## The decision

**A Dose is its own record on a Medication, not part of the Health Log.** The Health Log is the Patient's self-report for a day; a Dose is a carer's act at a time. Both stay: a teenager who takes their own pills still reports compliance in the Health Log.

**It records what happened and judges nothing.** The Medications page shows per Medication the Doses of today, and a history below. It never shows a Dose as due, open or missed. That needs target times read out of a dosage text such as "1-0-1" and a gap judged as a fault, which is an assessment the record does not make (`docs/regulatory-positioning.md`). For the same reason there are no reminders; a phone alarm does that already.

**Recording is one tap, and catching up is a period.** "Given" on a Medication records now, by me, the dose of the plan; time, amount, giver and a note can be changed before saving. Doses forgotten over several days are entered as a Medication, a date range and one or more times per day; the resulting list is shown and single Doses can be dropped before it is saved.

**Who gave it is a User or free text; who entered it is always kept.** The giver defaults to the signed-in User; otherwise a name as free text, like the person on a Carer Update (ADR 049), because the Kita and the grandmother have no accounts. Contribute access is needed to record one. Only whoever entered a Dose, or an admin of the Patient, may change or remove it; removing is a soft delete.

**A rescue Dose may point at its Incident.** When a seizure is recorded and Buccolam was given, the Dose points at that Incident and the Incident lists it. The Incident's free-text actions stay.

**The chat quotes, the doctor Handout lists rescue Doses.** The AI Health Assistant may quote Doses with time and giver, never whether one is missing. The doctor Handout may include, for a period the User picks, the Doses of rescue medications: those the Emergency Plan points at or that point at an Incident. The emergency and day-to-day Handouts never include Doses, since a printed list of today's Doses is stale at once.

## Alternatives, and why not

- **A list of Doses inside the Health Log entry.** Ties a Dose to a day instead of a time and mixes the Patient's report with the carers' acts.
- **Fixed times per Medication with open and missed Doses.** More useful at the bedside, but it is the assessment above and a step towards a medical device.
- **A table of rows for catching up.** More flexible, but most catching up is the same Dose at the same times on several days.

## Consequences

- A Patient Erasure deletes the Doses with the rest of the clinical data.
- The time is stored as local wall time, like an Incident's `occurred_at`; there is no time zone to get wrong between a carer's phone and the server.
