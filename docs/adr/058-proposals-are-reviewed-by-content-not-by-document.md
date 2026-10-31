# Proposals are reviewed by content, not by Document

Verifying works one Document at a time. That fits a family who adds a letter now and then: each new letter meets a record that is already there. It fails the family who uploads years of letters at once. Clinic letters repeat what earlier letters said, so the same Diagnosis comes up in a dozen letters, in three spellings, and has to be decided a dozen times. Measured on 56 real letters of one Patient: "15q11-q13 Mikroduplikationssyndrom", "Dup15q syndrome", "Dup15q-Syndrom" and an OCR "Dnp15q-Syndrom"; "Slenyto 5mg 0-0-1" and "5 mg 0-0-1" as two courses; test scores from 2025 quoted again in a 2026 letter.

Exact matching made each of those a new row (#129, #133). That was deliberate: whether "Ataxie" and "Leichte Ataxie" are one condition is a medical judgement, not a string operation (#113). This ADR keeps the judgement with the User and moves the moment it is made.

## The decision

**One Proposal Review collects the open Proposals of all of a Patient's Documents and sorts them by content.** There is no mode and no threshold: with one new letter it shows that letter's Proposals, with 56 it shows everything at once. Verifying a single Document stays, and both work on the same per-Proposal decisions, each saved as it is made, so a review can take a week. A Document is verified once none of its Proposals is open.

In order:

1. **Document facts first.** A table of every open Document with date, kind and Correspondent, editable in place. Unusual ones come first: no date, a date before birth or in the future, no Correspondent, kind "other". The file name is not a signal; it often comes from another archive. Dates go first because every later step orders by them.
2. **Diagnoses as groups.** The model proposes which names denote the same condition, including spelling variants, other languages, OCR errors and a suspected next to a stated form. Each group lists its spellings with how many letters use each. The User accepts a group or takes a spelling out of it. Entries already in the record take part: a group that contains one attaches the new letters as sources and keeps the record's name, which the User once confirmed; renaming is offered, not preselected. A new group takes the spelling of the newest letter, because clinicians grow more precise over time and the oldest wording is what gets copied forward. Suspected and stated follow the existing rule: stated wins, a suspicion never downgrades.
3. **Medications as courses.** Dosage text is normalised before comparing ("5mg" equals "5 mg", spacing around dashes). Mentions of one drug, ordered by letter date, become a proposed course: the same dose in consecutive letters is one section from its first mention, a changed dose proposes a new section and the end of the previous one. The User confirms each change or discards it (an OCR misreading). A letter that does not mention a drug ends nothing.
4. **Measurements and Lab Results merge without asking** when date, value and parameter are the same: a quoted number is not a new measurement, and confirming forty lab values one by one is the work this review removes. The parameter is the same when the existing lab code mapping says so, otherwise by the grouping of step 2. A different value on the same date stays a second row.
5. **Events by today's date.** An expired deadline is not created. Past appointments form one group, deselected: a letter that booked an appointment does not show it took place. Future appointments and open deadlines are proposed as today.

The grouping runs when the review opens, as one model call over all open names and the record's entries, cached until new Proposals arrive. Run per Document as extraction finishes, the groups would depend on which letter finished first. When the call fails, the review groups by normalised text only and says so, so an outage never reads as "nothing belongs together".

## How the model groups

Measured on the 56 letters with `Qwen/Qwen3.8-27B` at IONOS:

- **Diagnoses, one call that sorts the list into groups**, 55 names in 8 s. It grouped every Dup15q spelling with the record entry, the four autism wordings, and "ADHS" with "Einfache Aufmerksamkeits- und Aktivitätsstörung". It also grouped too eagerly ("Schwere Kommunikationsstörung" under the speech delay, "Leichte Ataxie" under "Ataxie"), which is acceptable only because the User confirms every group.
- **Medications, not that way.** Asked to group brand names with their ingredient, the same model put Atosil with Valproat and Slenyto with Propofol, and with thinking enabled still did so in one of two runs. Asked instead for each name's active ingredient (INN, or null when unsure), it answered identically in three runs in 2 s: Slenyto melatonin, both Valproat spellings valproic acid, Atosil null rather than a guess. Medications are therefore grouped by that ingredient, and a name without one stays alone.

**A confirmed ingredient is stored (#209).** #209 decided that the model does not fill the ingredient from general knowledge, because it is rarely in the letter and would land in the record unseen. Here it is seen: the review shows it as its own editable field ("Slenyto, Wirkstoff: Melatonin"), and confirming the group confirms the ingredient, which is then stored like any other confirmed Proposal. A null stays null; the field is left empty, never guessed. Grouping and naming an ingredient is not medical advice, which is the line the AI must not cross (Martin, 31 Oct 2026). Manual entry and taking an ingredient the letter names itself stay as #209 describes.

## The alternatives, and why not

- **Verify per upload batch with an "accept all".** Saves clicks but still decides the same Diagnosis once per letter.
- **Accept everything as unverified and correct what looks wrong.** Writes the duplicates and the false courses into the record, where they are harder to find than open Proposals.
- **Let the model merge without asking.** Automates the medical judgement #113 keeps with the User.
- **Group by ICD-10 code.** The model assigns the code too, so it only looks more reliable, and a wrong code silently separates what belongs together.

## Consequences

- Grouping is one model call per review, not per Document. On the demo it counts against the visitor's budget like the chat.
- A Proposal becomes something with its own state, not a section of a Document's extraction JSON that is read once at verify time.
- The family adding one letter at a time gets the same help: their new letter is grouped against the record, with the same question "belongs to Muskelhypotonie?".
- OCR errors ("1,5 mg" where the letter may say 0,5) are not solved here; the review makes them visible next to the other mentions, which is where they are easiest to spot.

See also ADR 005 (model choice), #113 (no medical judgement in string matching), #129 and #133 (re-mentions), #209 (active ingredient), #271 (suspected and stated).
