# Expenses are a first-class entity, and extracted amounts are proposals that must be confirmed

OpenAvisio's users are Caregivers, not billers. A family member or nurse pays for care aids, prescription co-payments, therapy, and travel, then applies to the Krankenkasse/Pflegekasse for reimbursement or claims the unreimbursed remainder on a tax return. Both need one thing: a structured list of amounts with dates and categories, and a total. This ADR records how that list is modelled.

It is explicitly not insurer integration. OpenAvisio prepares an overview the Caregiver submits through the insurer's own channel; it does not transmit anything into GKV infrastructure (no § 302 / § 105, no IK-Nummer, no KIM/TI). A Caregiver is a data subject, not a certified Leistungserbringer, so that channel is not theirs to use. Direct submission is deferred until there are paying customers and the resources to do it properly (adjacent to #203).

## The decision

An **Expense** is its own table, one row per amount, many per Patient. It carries an amount (Numeric, never float), a date, a coarse fixed category, an optional note, an optional link to a source Document, an optional link to a Correspondent (the payee), and an optional `reimbursed_amount`. It is either entered manually or proposed by the Processing Pipeline from an invoice Document.

Extracted amounts arrive as `status="proposed"` and **do not count** toward any total or CSV export until a User confirms them. Manually entered Expenses are `confirmed` on creation.

## Rejected alternatives

- **A projection over Documents (no entity).** Store the amount in the Document's `extraction_json` and derive the overview by listing invoice Documents. The lazier option, and it was the recommendation going in. Rejected because real care costs do not all have an uploaded invoice (cash payments, mileage) and one invoice can carry several separately categorised costs, neither of which a one-amount-per-Document projection can hold. The Caregiver needs to add and edit costs directly, which is an entity, not a view.
- **Auto-confirmed extraction.** Have the pipeline write a finished Expense straight from the OCR'd amount. Rejected because money out of OCR is unreliable (comma vs point, Zwischensumme vs Gesamtbetrag vs Eigenanteil), and a wrong number that silently enters a tax or insurance total is a real harm. Confirmation is the money-correctness gate, mirroring how proposed Events already require acceptance.

## Consequences

- Extracted amounts are editable and linked to their source Document; nothing is trusted blindly. The `proposed` -> `confirmed` step is that check.
- The open (deductible) remainder is `amount - reimbursed_amount`. A single nullable field covers open (null), partial, and full reimbursement, so no status enum is needed for it.
- Patient Erasure cascades Expenses (they are Patient PHI-adjacent financial data). See ADR 017.
- Expenses are not mapped into the FHIR export; they are financial, not clinical FHIR resources.
- Category is a small fixed vocabulary (care aid, medication co-payment, therapy, assistive device, travel, other) plus a free note. Enough to group and sum for an application, cheap to maintain.
- Amounts are EUR-only, matching the German care-cost use case. A currency column is the upgrade path if non-EUR receipts ever appear.

See also ADR 017 (Patient Erasure cascade), the Expense entry in CONTEXT.md, and #218.
