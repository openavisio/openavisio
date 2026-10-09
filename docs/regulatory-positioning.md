# OpenAvisio - Regulatory positioning

*Positioning summary for funding reviewers and partners. **Not legal advice** -
a formal regulatory/legal assessment is recommended before any market or medical
claims. This documents our current stance and the open questions a reviewer will
ask. Checked against the code on 18 Sep 2026; where a claim is about the
software's behaviour it names the ADR or issue that enforces it, because a
guardrail that lives only in a document is worse than none.*

## Short version

OpenAvisio is an **information-management and decision-support tool for
caregivers**, not a medical device. It **organises, transcribes and retrieves a
patient's own existing records** and surfaces information the patient's own
clinicians already produced. It does **not** diagnose, treat, monitor, predict,
or generate new medical advice.

## Medical Device (EU MDR 2017/745)

The MDR treats software as a medical device when it has a medical *purpose*
(diagnosis, prevention, monitoring, prediction, treatment). Our position:

- **In scope of "not a medical device":** OCR/transcription of documents,
  structuring and search of the patient's own data, plain-language summaries of
  what a document says, and surfacing recommendations **that the treating
  clinician wrote** (we extract and display them - we do not author medical
  recommendations).
- **What we deliberately avoid** (would risk MDSW classification): generating
  diagnoses, therapy suggestions, dosage advice, risk scores, alerts on clinical
  values, or any output a user would rely on for a medical decision that the
  software itself produced.
- **Guardrails in product & copy** (as they ACTUALLY exist, #117):
  - The chat system prompt forbids assessment outright: no "is this value
    normal/worrying", no ranking by urgency, no diagnosis, prognosis, dosage or
    recommendation of its own, no "you should see a doctor". It may quote a
    recommendation **a clinician wrote**, attributed. Asked to judge, it declines
    and points to the treating clinician.
  - Every chat answer carries a disclaimer **in the API response**, so no client
    can quietly drop it. Until #117 this document claimed such a disclaimer
    existed while the code had none — a guardrail that lives only in a document
    is worse than none, because it makes us believe we are covered.
  - The chat is in the app again since ADR 038/039, on the same terms: the
    answer is grounded in the Patient's own structured records plus retrieved
    document passages, the agent loop runs in the backend where the system
    prompt cannot be altered by a client, and the disclaimer travels in the API
    response (`schemas/chat.py`), so no client can drop it.
  - Every screen that shows extracted data (summaries, lab values, diagnoses,
    medications) states that it was read out by OCR and a language model, that
    both make mistakes, and that the original document is what counts.
  - Every extracted Diagnosis cites the passage it came from (#133), so a
    caregiver can check the source rather than trust the extraction. The
    extraction prompt may only record a diagnosis that is **named in the
    document**, never one inferred from a lab value (`04e743f`); severity is
    transcribed, never assigned (#118).

## Precedent: the abnormal-value chips (2026-07, #113)

The documents list briefly surfaced lab values outside their reference range:
it scored them by deviation, **picked the four worst**, and showed those as
red/amber chips. Removed — not because comparing numbers is forbidden, but
because selecting a subset and highlighting it is emphasis the software itself
authors. Nothing in the document says "these four matter most".

**What stays, deliberately:** the lab pages colour a value that falls outside
the range **printed on that same report** (#69). The lab flags those values
itself ("H"/"L"); showing that faithfully is presentation, not a new claim.
Removing it was proposed and rejected — it is established, useful behaviour and
the call is not ours to make unilaterally.

**Open question for the regulatory advisor** (do not decide this in a PR):
where the line sits between *reproducing* a document's own out-of-range marking
and *authoring* an assessment. Working rule until then:

- Do **not add** new features that select, rank, or warn on clinical values.
- Do **not remove** existing behaviour on an engineer's own reading of the MDR.

## Two later features, and where they stopped (2026-07, ADR 041 and 042)

Both touch money and deadlines, which is where a caregiver would most like the
software to tell them what to do, and both were built to stop short of that.

- **Widerspruch Deadline** (ADR 041): the software computes the last date on
  which a Kassenbescheid can be objected to, from the decision date and the
  period printed in the Rechtsbehelfsbelehrung. It labels the date as its own
  arithmetic, proposes it for confirmation rather than asserting it, and says
  nothing about whether objecting is advisable. Whether the decision is good or
  bad news is not judged: a Pflegegrad granted below the one applied for is
  printed as an approval, and only the family knows the difference.
- **Einstufung / Pflegegrad** (ADR 042): the software records the grade, the
  points and the module scores and shows where the points sit between the
  statutory thresholds. It states **no benefit amounts and no entitlements**.
  Those change by statute and depend on circumstances the record cannot see,
  and a wrong figure costs the family money.

The pattern is the same as for the chips: reproduce what a document says,
compute only what is arithmetic, and stop before anything a family would act on
as advice.

## The Intake Form (ADR 047)

The Intake Form turns the pattern outward: its answer sheet goes to a doctor,
who reads it as the family's own account. So the software prefills only
questions of fact, each with its source, and leaves every question that asks for
a judgement ("is the development age-appropriate?") to the Caregiver, however
clearly the record seems to answer it. A derived judgement would reach the
doctor disguised as the parents' impression, and on paper nothing shows where it
came from. The relevant facts may be shown beside such a question, verbatim, as
a reminder. Nothing leaves before a Caregiver has reviewed and released the
sheet. The rule is enforced in code twice, in the aiservice and again in the
backend: a judgement question leaves unanswered whatever the model returned, and
a fact answer only with a source that was offered to the model.

**Open question for a formal assessment:** where exactly the line sits for the
AI assistant's summarisation/answering. This is the one area to validate with a
regulatory advisor; the mitigations above are designed to stay on the
non-device side.

## DiGA (Digitale Gesundheitsanwendung, §33a SGB V)

- DiGA reimbursement requires being a **low-risk medical device** (roughly class
  I / IIa) listed by BfArM. Since we position OpenAvisio as **not** a medical
  device, DiGA is **not** a current path.
- It remains a **possible future option** *if* a specifically scoped, clearly
  medical feature were built and deliberately taken through MDR + BfArM. Out of
  scope for now; noted so reviewers know we've considered it.

## GDPR / data protection

- Health data is a **special category** (Art. 9 GDPR). OpenAvisio is
  **GDPR-native by design**: lawful-basis tracking, consent-based sharing,
  Article 17 erasure cascades, per-patient envelope encryption with
  crypto-shredding (ADR-031), retention purge, and full audit logging.
- **Self-hosting model:** the operator (a household or a care organisation) is
  typically the data **controller**; OpenAvisio is the software they run. This
  keeps data under the user's control and simplifies the processor/controller
  story compared with a cloud SaaS.
- **Hosted model:** where the project operates a Deployment for a family, the
  project is a **processor** under an AVV, one isolated Deployment per customer
  with its own keys and backups (avisiohub ADR 0007), and the operator holds no
  account inside it. The DPIA (`docs/dpia.md`), the Art. 30 record
  (`docs/ropa.md`) and the AVV template (`docs/avv-vorlage.md`) name the AI
  sub-processor for that case and say precisely what reaches it, including that
  hosted vision OCR receives the page images, not only text.
- **Research and registry sharing** is a first-class concept, not an export
  button: a Sharing Purpose carries per-document consent, an identified or
  pseudonymous mode, revocation and an audit trail (ADR 020, `GLOSSARY.md`
  "Data sharing"). Nothing leaves a record without the caregiver choosing the
  document and consenting to that specific purpose.

## EU AI Act

- If OpenAvisio is **not** a medical device, it is unlikely to fall in the
  AI Act's **high-risk** category (which centres on AI as a safety component of
  regulated products). It would then sit under **transparency obligations** for
  AI systems - clearly disclosing to users that they are interacting with an AI
  assistant, which we do.
- If the product were ever repositioned as a medical device, high-risk
  obligations would need re-evaluation.

## Summary for reviewers

- **Not a medical device / not a DiGA** as currently scoped - an assistive,
  document-grounded information tool.
- **Privacy is a feature, not an afterthought** - GDPR-native, self-hostable,
  data under the user's control.
- **Clear guardrails** keep the AI on the "understand your own records" side of
  the line, with disclaimers and citations.
- A **formal regulatory review** is planned as the product matures (budgeted
  under legal/data-protection).
