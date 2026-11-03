# An Incident records what happened, not a seizure diary

Incidents existed in the backend with about twenty fields (severity, status, location, weather, temperature, humidity, pollen, air quality, activity, hours since the last meal, sleep the night before, trigger, symptoms, outcome, reported to a provider), but no page to record one (#434). Dedicated seizure apps exist and families use different ones. Terms are in `GLOSSARY.md` under "Incident".

## The decision

**OpenAvisio is not a seizure diary.** An Incident is what happened, so that everyone who cares for the Patient, the grandmother, the Kita and the parents, sees the same: a seizure at 07:40, three minutes, Buccolam given. A family that keeps a detailed seizure diary keeps it in its own app.

**The record holds what the form asks, nothing more.** Type from a fixed list (seizure, fall, allergic reaction, other), an optional name in the family's words with the names used before suggested, the time as local wall time, an optional duration, what was done, and a note. Every other field is gone. Their free text moved into the note when the columns were dropped. Weather, pollen, sleep and meals were the raw material for a correlation that `docs/regulatory-positioning.md` rules out (#119); severity was a judgement without a scale.

**One tap first, the details later.** "Incident now" on the Incidents page and on the Patient's overview records the current time and the type used last, then opens the entry. There is no stopwatch; the phone has one, and a timer in the app would pull alarms after it.

**A rescue Dose is recorded from the Incident.** The Emergency Plan's medications are offered first (ADR 060). Deleting an Incident keeps its Doses and drops only the link: they were given, possibly by someone else.

**Who entered it, or an admin, changes it**, with an audit entry, as for a Dose. Deleting is a soft delete.

**Counts, no curves.** The page shows per type the number in the last 3 and 12 months, the same as the doctor Handout. A curve over time is the first step to "it is getting worse", which is an assessment.

## Alternatives, and why not

- **Leave Incidents out entirely.** A rescue Dose would stand without its occasion, and a fall at the Kita would be written nowhere.
- **Import from seizure apps instead of a form.** Every source is a project of its own (#244); it can still feed the same Incidents later.
- **Keep the context fields in the API.** Unused fields invite someone to build the pollen chart on them.

## Consequences

- The unused list endpoints (`/incidents/summary`, `/by-date`, `/by-type`) are gone; the page computes its counts from the list.
- An Incident's PUT replaces the whole record, so a field can be emptied again.
- Chat, Handout and calendar show the type in the reader's language when no own name is given.
