# A Handout holds only confirmed entries, and travels frozen

Until now nothing a person could read about a Patient left OpenAvisio. Documents could be shared (ADR 020, ADR 021) and the whole record exported as FHIR, which no practice reads, and the PDF export was a stub. A Handout is a printable account of the Patient for one kind of recipient: a doctor, emergency services, an authority or insurer, or the people who look after the Patient day to day. Each recipient gets a fixed variant. Terms are defined in `GLOSSARY.md` under "Handout", "Emergency Plan" and "Care Notes".

## The decision

**A Handout contains only entries a User has confirmed, reproduced as recorded, and no text written by the AI.** Proposals the Processing Pipeline has not had confirmed stay out, and a suspected Diagnosis stays marked as suspected. Every line on the page traces back to an entry a person confirmed, which is what a doctor or the Medizinischer Dienst needs before they rely on it. Because the result is predictable, there is no draft and no release step: the User sees a preview, may leave out single entries, and downloads.

**In a Document Share Link the Handout is frozen as previewed.** It is generated once when the link is created, dated, and never regenerated on access. What the recipient sees is what the family saw. For a current state, the family creates a new link.

**What the record cannot derive is written by the family, not generated.** The Emergency Plan and the Care Notes are authored by a Caregiver. A step in the Emergency Plan that gives a rescue medication points at the Medication, so the dose has one home.

**The AI Health Assistant never restates the Emergency Plan.** Quoting what a person wrote is otherwise allowed in the chat, and the assistant may quote the Care Notes. For the Emergency Plan it answers with a fixed pointer from the code, not from the model.

## Rejected alternatives

- **An AI-written summary paragraph** ("Lena, 6, focal epilepsy since 2023, ..."), kept as a draft until a Caregiver releases it, as the Intake Form answer sheet does (ADR 047). Rejected because the convenience is small and the cost is that every Handout needs a review cycle, and a sentence that went out unread would reach a doctor or an authority as if the family had written it. The answer sheet needs the AI to match free-form questions; a Handout has no such need, since its variants decide what goes in.
- **Including unconfirmed proposals, marked as such.** A mark on paper is easily overlooked, and the recipient cannot tell a misread lab value from a real one.
- **A live link that always shows the current record.** It would send changes the family never saw in the preview, such as a Diagnosis confirmed the day after the link went out. It would also be a second public PHI view with its own security surface beside ADR 021.
- **Letting the assistant quote the Emergency Plan.** A model does not reproduce a quote reliably, and a misquoted dose in an emergency is the one mistake that must not happen. A link to the original costs one tap.
- **Prefilling the Emergency Plan from a clinician's emergency plan Document.** That would put AI-extracted text into the plan. The Emergency Plan points at such a Document instead, and the Handouts name it.

## Consequences

- **The PDF export stub is replaced** by the doctor variant of the Handout. The FHIR export stays the machine-readable export of the whole record and gains the Emergency Plan as a `CarePlan`.
- **A Document Share Link item is no longer always a Document.** It can be a frozen Handout, and a Document the Emergency Plan points at goes along with a Handout that includes it.
- **The Emergency Plan, the Care Notes and the frozen Handouts join Patient Erasure.**
