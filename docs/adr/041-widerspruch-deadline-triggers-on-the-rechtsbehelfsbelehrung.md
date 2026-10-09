# A Widerspruch deadline is triggered by the Rechtsbehelfsbelehrung, computed in the backend, and confirmed once

A Caregiver who receives a decision letter from a Krankenkasse or Pflegekasse (a denied Kostenübernahme, a Pflegegrad graded below what was applied for) can object, normally within one month. Missing that period makes the decision final, and no later feature repairs it. This ADR records how OpenAvisio surfaces that period.

Scope is deliberately narrow: a **deadline watchdog** and nothing else. Tracking the state of an objection (drafted, sent, answered) and helping compose the objection letter are both wanted later, and both build on this; neither is built now. As with Expenses (ADR 040), OpenAvisio is a preparer, not a transmitter: it never sends anything to a Kasse.

## The decision

**The trigger is the Rechtsbehelfsbelehrung, not a detected rejection.** Any Document carrying the formulaic instruction on legal remedies produces a deadline proposal, whatever the decision was. A new `document_type: insurance_decision` separates such decisions from other insurer post (`insurance_document`).

**The date is computed in backend code, not by the model.** The Processing Pipeline extracts only the decision date and the period stated in the instruction. The end date follows from those deterministically: decision date, plus three days for the statutory service assumption, plus the stated period, rolled forward off weekends and public holidays.

**The result is an Event of category `deadline`**, all-day, carrying the Kasse, the Aktenzeichen, the subject of the decision, and the grounds quoted verbatim and capped at three sentences. There is no Widerspruch table yet.

**It is created when the User verifies the Document** — one gate, like a proposed appointment, not the two-step `proposed` -> `confirmed` path Expenses take.

Two reminders go out instead of the usual one, at 14 and 3 days.

## Rejected alternatives

- **Trigger on a detected rejection.** The intuitive trigger, and wrong: "rejected" is not readable off the letter. The common real case is partial rejection (Pflegegrad 2 granted where 3 was applied for), which is printed as an approval. Whether that is a win or a loss depends on the application, which is not in the document. A model asked to decide this is guessing. The instruction on legal remedies, by contrast, is a recurring formulaic block, far more reliable to detect, and it states the period itself.
- **Let the model compute the end date.** Rejected because date arithmetic is a well-known weak spot of language models, and this particular date carries a deadline that cannot be re-opened. `date + relativedelta(months=1)` is one testable line.
- **Deliberately compute an early date.** Drop the service assumption and the weekend roll so the shown date is always safely before the real one. Rejected: presenting a knowingly wrong date as "the deadline" is a lie the User will eventually catch, and it then discredits the date they do need to trust. The safety margin belongs in the reminder lead time, not in the date.
- **A second confirmation gate, as for Expenses.** Rejected because the failure modes are opposite. An unconfirmed Expense is harmless — it simply does not count. An unconfirmed deadline is the harm itself: the system would know the date, not put it in the calendar, and not remind, because a checkbox is missing. That is precisely the failure this feature exists to prevent.
- **A Widerspruch entity now.** Rejected as scaffolding: in a watchdog nothing writes its lifecycle field, and an unmaintained status field is worse than none. The case-file step adds the table and an additive foreign key from the Event, with no data migration.
- **A link to the affected Expenses.** Rejected on two counts. The letter names an application, not an invoice number, so the mapping would be guessed, and guessed in money. More fundamentally, a rejected Sachleistung the Kasse would have settled directly with the provider never produced an Expense at all, so the link points nowhere in a common case. The open remainder (`amount - reimbursed_amount`) already answers "what did the Kasse not cover".

## Consequences

- **The feature gates itself by language.** The instruction on legal remedies appears only in German letters, so no locale switch or configuration flag is needed for deployments outside Germany.
- **"Widerspruch" stays untranslated**, in the English glossary and the English UI alike. "Appeal" and "objection" both mean something adjacent, and the Caregiver is looking for the word printed on the letter in front of them. Same reasoning as the untranslated `pflegehilfsmittel` expense category.
- **The single reminder timestamp no longer suffices.** Two stages need a counter alongside `reminder_sent_at`, and the reminder lead time becomes a function of the Event category rather than a fixed 24 hours.
- **Re-verifying the Document overwrites a hand-corrected date**, as it already does for every pipeline Event. Left as is: re-verification is a deliberate act on that Document, and the screen that triggers it re-displays the deadline and its derivation, so the loss happens in front of the person causing it and is correctable on the spot.
- **The computation is stated, and labelled as one.** The Event carries its derivation, and the verification screen and reminder mail each carry one sentence: computed, not legal advice, and when in doubt object early or seek advice. Objecting too early costs nothing. One sentence per surface, not a wall of warnings, which only teaches people to ignore all of them.
- **Grounds are quoted, never summarised.** A paraphrase puts words in the Kasse's mouth that someone may then argue against. Same transcription discipline the extraction prompt already applies to a clinician's own wording.

## Addendum, 2026-07-26: the case-file step landed as a status, not a table

The rejected-alternatives section above says a Widerspruch entity would come with the case-file step. It did not. Scoped down to recording *whether* the objection was raised, the lifecycle is a single value, and `CalendarEvent.status` already existed, was already exposed, and was already the field the reminder scan filters on — so a table would have been one column mirroring one column.

Two values carry it, deliberately generic so one vocabulary serves every event category: `done` and `cancelled`, labelled per category in the UI ("Widerspruch eingelegt" / "Kein Widerspruch" at a deadline, done / cancelled at an appointment). Two rather than one, because "I objected" and "I let it lapse on purpose" are different facts and the second is the one nobody remembers a year later.

Setting either also stops the reminders, which is what makes the status worth maintaining at all: a Caregiver who has already objected and still gets "3 days left" stops believing every later reminder too. A status that only tints a view does not get kept up to date; one that ends the nagging does.

The table returns if the lifecycle ever grows fields of its own — a date of dispatch, the Widerspruchsbescheid as a response document, an outcome — and most of all if the Kasse's own three-month response period (§ 88 SGG) is ever tracked, which is the one part of the case file that tells the Caregiver something they cannot know by themselves. Until then it would be scaffolding.

See also ADR 040 (Expenses), ADR 037 (the iCal feed that carries the deadline into a Caregiver's phone calendar), and the Widerspruch entry in CONTEXT.md.
