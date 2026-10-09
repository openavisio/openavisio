# An Einstufung is a record with history and module scores, and OpenAvisio states no entitlements from it

A Pflegegrad decides what a Patient's care is worth to a Pflegekasse, and a Caregiver has to state it on nearly every form. It is also the single number a family watches for years. This ADR records how it is modelled, and, more importantly, where the feature stops.

Scope is Pflegegrad only. The Grad der Behinderung is the obvious sibling and is deliberately not built alongside it (#233): one is enough to learn from, and a type discriminator carrying exactly one value is scaffolding.

## The decision

**An Einstufung is its own record, one per assessment**, carrying the Pflegegrad it assigned, the total points, the six module scores, the date it takes effect, an optional end date, and the Kassenbescheid it was read from. The current Pflegegrad is the most recent Einstufung. It is created either by hand or as a proposal from the Processing Pipeline, confirmed on the verification screen like everything else extracted.

**The vocabulary separates the record from the level.** An *Einstufung* is the act of grading; a *Pflegegrad* is the level it assigns. Both stay untranslated, like Widerspruch and Kassenbescheid (ADR 041): they are the words printed on the letter the Caregiver is holding.

**The six modules of § 15 SGB XI are six columns**, not a child table and not Observations. They are fixed in law, and a fixed list of six is what columns are for. As Observations they would appear in the Measurements list between weight and head circumference, where they do not belong.

**The model reads the points table, and arithmetic checks it.** Two guards run in the backend: the printed total must map to the printed Pflegegrad through the statutory thresholds, and each module's weighted points must stay under its statutory maximum. If either fails, the module scores are discarded and only the grade and date are kept.

**A befristete Einstufung produces a deadline Event** (ADR 041's machinery, unchanged) with a longer lead than a Widerspruch: 90 and 30 days rather than 14 and 3.

**The app states no entitlements.** It shows where the total sits between the statutory thresholds, and nothing else derived.

## Rejected alternatives

- **A field on the Patient.** The obvious lazy version: `pflegegrad` plus `since`, overwritten on change. Rejected because an upgrade commonly takes effect retroactively to the month of application, so "which grade applied in April" is a question with money attached, and an overwritten field can only answer it from the PDF folder. It is also what a Widerspruch points at: without a record there is nothing to contest but a document.
- **Storing only the grade, not the module scores.** The grade is a number from 1 to 5 that moves every few years; as a history it says almost nothing. The module scores say *where* care need changed, in the very language the Kasse decides in, and they are pure transcription from the letter. This was the maintainer's idea and it is what makes the history worth keeping at all.
- **A deterministic parser for the points table**, as ADR 028 prescribes for lab tables. Rejected as too much machinery for six numbers whose labels are fixed by law. Its motivation is real, though, because a Bescheid often prints both Einzelpunkte and gewichtete Punkte and only the latter sum to the total. That risk is met by the two arithmetic guards instead: picking the wrong column breaks the module maxima immediately. Cheaper than a parser, testable, and it fails visibly rather than silently.
- **Checking the total by re-adding the modules.** Rejected because the weighting has a trap: modules 2 and 3 do not both count, only the higher of the two enters the result. A guard that encodes a rule we understand imperfectly would reject correct data. The two guards above do not need it.
- **Deriving benefits.** "Pflegegrad 2 means €347 Pflegegeld", "GdB 80 means a €1060 tax allowance". Rejected: these change by statute, depend on cases we cannot see (cash versus in-kind, combined, pro rata), and a wrong figure costs the reader money. It would make OpenAvisio a social-law advice service running on stale tables. Same line as the Widerspruch deadline: we show a calculation and its basis, we do not state the legal position.
- **Pointing at the module to argue about.** The weights are law and may be shown as fact; "argue about Selbstversorgung" is advice on how to run an objection. The module history gives a Caregiver the same insight without anyone telling them what to do.
- **A "5 points to Pflegegrad 3" readout.** Rejected as a framing, not as a number. It reads like a target to aim for, when points come from an assessment of actual need. The scale is shown with the thresholds marked and the total placed on it.

## Consequences

- **The reminder lead time is no longer a function of the Event category alone.** A deadline from a Widerspruch and one from an expiring Einstufung are both `deadline` and need different notice.
- **Wiederholungsbegutachtung is not modelled.** The Kasse initiates it; missing it costs nothing but a phone call. Reminders about dates someone else owns are noise, and noise devalues the deadlines that do bite.
- The statutory numbers this leans on (grade thresholds, module weights) are stated in one place in the backend so they can be checked against the law rather than hunted through the code.
- Patient Erasure cascades Einstufungen: they are decisions about a named person's care need.

See also ADR 041 (Widerspruch deadline, whose Kassenbescheid this reads from), ADR 028 and ADR 029 (why tables and vocabulary are the code's job), and #233 for the GdB.
