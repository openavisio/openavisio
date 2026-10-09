# An Intake Form is answered from the record, and learns only what the record lacks

Every new practice, clinic or rehab facility hands a Caregiver the same medical history questionnaire, and families of a chronically ill child fill in their tenth one by hand. OpenAvisio answers an uploaded Intake Form from the Patient's record and gives back an answer sheet in the form's own order. Whatever the record cannot answer is put to the Caregiver once and kept as a History Fact, so the next form asks only what no earlier one did. Terms are defined in `CONTEXT.md` under "Anamnesis".

## The decision

**The record stays the source for everything it already knows.** A question about medication is answered from the Medications, an allergy from the Diagnoses, a seizure from the Incidents, a first word from the milestone Events. Only what has no home becomes a History Fact: a single piece of history with its question as it was asked, the date it was last confirmed, its source, and how it ages (_lasting_, _changeable_, _visit-only_). Matching a new form's questions to History Facts is left to the AI and caught by review, because every prefilled answer shows its source.

**Documents are searched when a form asks, never mined on upload.** When no History Fact answers a question, the Document text is searched the way the AI Health Assistant searches it (ADR 038), and a passage found is offered with its citation. A Caregiver confirming it turns it into a History Fact, so the search happens once per fact.

**Only questions of fact are prefilled.** A question asking for a judgement ("is your child's development age-appropriate?") stays the Caregiver's, however clearly the record seems to answer it. The facts that bear on it may be shown beside it, verbatim.

**The uploaded form is not a Document.** It comes in through its own entry point and is kept with the Intake Form as the record of exactly what was asked, but it is not listed with the Documents, not run through clinical extraction, and not searched by the chat or for answers.

**A released answer sheet is frozen.** Until release it is a draft built from the live record, and correcting an answer from the record offers to change the record without doing so. After release it stays exactly as handed in, since its job is to answer "what did we tell them?".

## Rejected alternatives

- **An answer store.** Keep every question and answer as given, and reuse the nearest earlier answer. Rejected because it makes a second copy of what the record already holds: "current medication" would be answered as of the last form, while the Medications moved on. Two truths, one of them stale, and the stale one goes to a doctor.
- **A structured anamnesis model.** Give birth history, family history, schooling and so on fixed fields, or a fixed catalogue of topics. Rejected because forms vary too much to model in advance, and every new question would need a schema change first. A topic that turns out to be asked on every form is the point at which to promote it to an entity of its own; until then a History Fact holds it.
- **Mining the anamnesis sections of letters on upload.** Every Arztbrief retells the history slightly differently, so mining each one produces duplicates and contradictions that nobody asked for, the same pile-up the Diagnoses had in #129. Searching on demand touches only what a form actually asks, and a human confirms each fact once.
- **Letting the AI answer judgement questions.** Rejected on two grounds that a better model would not fix. The question asks for the family's own impression, which the doctor weighs against their examination; a derived answer reaches them disguised as that impression, and on paper the source is gone. And judging development against norms is an assessment the software would be authoring, the line `docs/regulatory-positioning.md` keeps us behind.
- **Treating the uploaded form as a Document.** A blank form is a list of conditions phrased as questions ("Asthma? yes / no"). As a Document it would be extracted into Diagnoses, retrieved by the chat as evidence, and found as the source of its own answers.
- **Sharing family history between siblings.** Family history is relative to the person, and nothing in the model relates one Patient to another. A History Fact belongs to one Patient, and a sibling's form asks again.

## Consequences

- **The ordinary upload path still needs its own guard.** A questionnaire uploaded by accident through the normal upload, and family history or ruled-out conditions in ordinary letters, can still become Diagnoses. That is #259, independent of this feature.
- **The glossary lost a promise.** Milestones were described as "benchmarked against expected age ranges". Nothing in the code did that, and it would be the kind of assessment ruled out above, so the sentence now says the opposite.
- **History Facts join Patient Erasure, the FHIR export and the chat context**; the chat leaves out _visit-only_ facts, which describe a past visit and would read as current complaints.
