# A Carer Update is kept as told, and says who told it

A family whose child goes to an inclusive Kita hears irregularly how the day went: a message in a parents' app, a note in the bag, a few words at pickup. Nothing in OpenAvisio holds this. The Health Log is the Patient's own structured self-report, the Care Notes go the other way (from the family to the carers, ADR 048), and a Document is an uploaded file. A Carer Update is what someone who looks after the Patient without the family reported about one day. Terms are defined in `GLOSSARY.md` under "Carer Update" and "Correspondent".

## The decision

**The family enters it, and it names its source.** Carers get no access to the Patient. Every Carer Update has a Correspondent (the Kita, not "Kita" typed anew each time), optionally the person as free text, and the day it is about. The Correspondent stays a plain name: a kind (clinic, practice, Kita, school) would add a field to fill in every time for categories that are often unclear, such as an SPZ or an early intervention centre, and filter a list a family keeps short anyway.

**It is kept as told, and says how it was told.** The text is free, because carers do not write in fields. A flag records whether it was copied word for word or retold from pickup. The difference matters most where Carer Updates are worth most: as a third party's observation in front of the Medizinischer Dienst, in a Widerspruch, or at an appointment. "The Kita wrote on 3 March: ..." and "According to the Kita (told at pickup): ..." carry different weight, and the record should not blur them.

**Nothing is extracted from it.** A Carer Update reporting a seizure does not become an Incident proposal, and a first word does not become a milestone. The AI Health Assistant finds them by reading the Carer Updates, and may quote them, always naming the Correspondent, the day and whether it was retold.

**It leaves only in a Handout.** The doctor and authority variants may include the Carer Updates of a period the User picks, under the Handout's rules (reproduced as recorded, single entries left out in the preview, frozen in a Document Share Link). The emergency variant has no room for them, and the day-to-day variant would hand the carers their own updates back.

## Rejected alternatives

- **Using the Health Log.** It is structured self-report for trends, and a Kita's update is neither structured nor the Patient's own.
- **Structured fields** for sleep, eating and mood. That would be the Health Log again, filled from text that does not have those fields.
- **Carers writing directly**, as Users or through an anonymous link. That gives staff of another organisation access to PHI, with the role and data processing questions that follow. The family stays the one who enters.
- **Photos on the entry.** A photographed note is text, and one worth keeping as evidence is uploaded as a Document as today. A photo of the day is a memory, not health data.
- **Putting them on the timeline.** The timeline holds appointments and deadlines; several Carer Updates a week would bury them. They get their own section on the Patient page.

## Consequences

- **The Correspondent definition widens** from "issued or sent a Document" to also "a Carer Update comes from".
- **Carer Updates join Patient Erasure and the chat context.** One can be edited and deleted like any other record; a Handout already frozen into a Document Share Link keeps the version it froze.
- **The Patient page gets a new section**, so the smoke test's sidebar navigation (ADR 033) changes with it.
- **Deferred:** a button "take over as Incident / milestone" that prefills that form from a Carer Update. Worth adding once families find themselves copying seizures over by hand.
