# A Sharing Purpose may ask for a frozen Data Set

A Dup15q association collecting who was testable, for a registry or a study, wants structured records, not files: all Test Attempts, or the Ability Observations of one domain since a date (ADR 063). Until now a Share pointed at exactly one Document, and ADR 020 deferred structured data. Issue #467. Terms are in `GLOSSARY.md` under "Data sharing".

## The decision

**A Sharing Purpose asks for Documents or for one Data Set, never both.** A Data Set is one kind of record, Test Attempts or Ability Observations, with an optional "since" date and, for Ability Observations, an optional domain. The Purpose Manager sets it when creating the Purpose; it is locked once the first Patient has consented, so what was agreed to cannot change afterwards. A Test Attempt's linked report does not travel with it: whoever wants the reports opens a second Purpose and gets a second consent.

**The Share is a frozen snapshot.** The Caregiver sees every matching row, all ticked, and may untick single rows, as in the Handout preview; the choice is not remembered. Consenting copies the chosen rows as they are. Later edits or deletions in the record do not reach the Share; sharing again replaces the snapshot after the same consent screen. A Patient without a matching row cannot consent to an empty snapshot, because "never tested" and "not entered" would look the same: the request stays open and the Caregiver may decline. As for Documents, the first response clears the nudge and new records raise no new one.

**Fixed columns, no derived judgement.** Test Attempts: Patient (name or pseudonym), test as named, date as recorded, age in months on that day, setting, duration, outcome, reason. Ability Observations: Patient, Ability in the family's words, domain, date, age in months, place, works, with help, note, source (without the Document's name). Never the Correspondent who ran a test, the date of birth, the linked report or the Medications of that day.

**Anonymous stays metadata-only.** Only the name is replaced by the pseudonym. Date, age and free text stay, though together they can narrow a child down; the reason a test ended is the part a registry needs. The consent screen says so.

**One CSV per Purpose.** UTF-8 with BOM, semicolon-separated, one row per record across all consenting Patients. The Purpose Manager sees the consenting Patients with their row count and consent date, and downloads the file. OpenAvisio shows no table and computes no counts across families: that is the association's work. Other formats come when someone asks.

**Everything else is ADR 020.** Who may consent, revocation (future downloads only; a downloaded file cannot be recalled), closing and expiry, no download audit, Patient Erasure. Only Patients in the same Organization can be asked; Patients on individual-user Deployments (ADR 046) are out of reach.

## Alternatives, and why not

- **A Share that grows with new records.** Consent to rows nobody has seen yet.
- **Referencing the records instead of copying them.** Later edits would leave unseen, and deleted rows would vanish silently.
- **Coarsening dates and dropping free text in anonymous mode.** Loses the reason a test was not possible, which is what the registry collects.
- **FHIR.** It exists per Patient in the export; an association counts in a spreadsheet.
- **Any structured data.** Nobody has asked for more than Development; another kind of record is another Data Set kind and its own decision.

## Consequences

- The Share gains a second target; the unique (Purpose, Document) constraint becomes one Share per (Purpose, Patient) for a Data Set Purpose.
- The Share Request for a Data Set Purpose names the Data Set itself, not a free-text kind of file.
