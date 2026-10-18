# OpenAvisio

An open-source AI health assistant for caregivers — family members, nurses, and anyone responsible for another person's care. OpenAvisio helps caregivers understand, manage, and act on a patient's health records through a conversational AI interface. The document vault, Processing Pipeline, and structured clinical data exist to ground the AI Health Assistant in accurate, patient-specific data.

## Language

### System

**Organization**:
The entity that runs an OpenAvisio Deployment. Always exactly one per Deployment — a care home, a clinic, a household, or an individual in a homelab setup.
_Avoid_: tenant, instance, workspace

**Deployment**:
A complete running OpenAvisio stack (frontend, backend, AI service, database) serving exactly one Organization. Deployments are fully isolated from each other; there is no multi-tenancy. In user-facing UI text, "server" is acceptable ("connect to your server") — the canonical term applies to code, docs, and design discussions.
_Avoid_: instance, installation, server (in domain language)

### People

**Patient**:
The person whose health data is stored. A Patient is not a system login — they are the subject of all clinical data (observations, conditions, medications, documents, etc.).
_Avoid_: subject, record owner, health record

**User**:
A person with a system login. A User manages one or more Patient records. A User and a Patient can be the same physical person (self-management).
_Avoid_: account, member, actor

**Coordinator**:
A system role. A Coordinator can onboard new Patients and assign access to other Users. One person can be both a Coordinator and a Caregiver for the same Patient.
_Avoid_: manager, staff manager, system manager

**Household Manager**:
The one User who manages a household Organization: its members, invitations, name, mails and audit log. Whoever sets up the household is it until they hand it to another member. In code the role is `admin`; the UI never calls it that (ADR 052).
_Avoid_: admin, owner, account holder (in a household)

**Caregiver**:
A person responsible for a specific Patient's day-to-day care. Caregiver is a patient-level relationship, not a system role — any User can be a Caregiver for a Patient regardless of their system role. Covers family members, nurses, paid carers, legal guardians, and anyone else in a Patient's care circle. A legal relationship (power of attorney, guardianship) is a flag on the Caregiver's access grant (`is_legal_representative`), recorded for compliance, not a separate access path (ADR 027).
_Avoid_: family member, nurse, caretaker, responsible person, representative

**Group**:
An optional, named set of Patients whose access is managed together. A Coordinator can add Users to a Group to grant them access to all Patients in it at once. Groups are a convenience shortcut — they generate access grants in bulk but do not add a separate access tier. Most homelab deployments don't need Groups; they are mainly useful in care homes or clinics managing many Patients.
_Avoid_: family, family group, care circle, ward

### Compliance

**Erasure**:
A GDPR Article 17 right-to-erasure action. Two variants:

- **Patient Erasure** — triggered by any holder of an admin-level PatientAccess grant on the Patient. Cascade hard-deletes all clinical data (Diagnoses, Medications, Measurements, Lab Results, Incidents, Expenses, Events, Health Logs, Carer Updates, History Facts, Intake Forms, Documents + storage files, Document embeddings, Recommendations, AI Health Assistant messages), all access records (Caregiver links, PatientAccess grants, pending invites), all Shares and Share declines for that Patient, all external Document Share Links and their items (including the Handouts frozen into them), the Emergency Plan and the Care Notes, all Calendar Feeds (an outliving feed would be a working PHI URL for an erased person), and all prior AuditLog entries for that Patient's data (including external share-link access logs). A single tombstone AuditLog entry is written recording that erasure occurred. Immediate and irreversible. (Files a Purpose Manager already downloaded and forwarded externally are outside OpenAvisio's reach.)

- **User Erasure** — triggered by an admin or the User themselves. Anonymises all PII fields on the User record and hard-deletes login credentials (PasskeyCredentials), access grants (GroupMemberships, PatientAccess) and their Calendar Feeds, which ride on that access. Blocked while the User is the last admin-level grant holder of any Patient — grant someone else admin level or erase those Patients first. A tombstone AuditLog entry is written and existing AuditLog entries for that User have `user_name` scrubbed to `[erased]`.

_Avoid_: deletion, account deletion, data removal, right to be forgotten

### Licensing

**License**:
A signed entitlement file that determines which Tier an Organization operates under. Uploaded by an admin via the admin UI. Absence of a License means the Organization operates under the Personal tier defaults.
_Avoid_: license key, activation key, serial number

**Tier**:
The operating mode of an Organization — either Personal (default, no License required, AGPL, limited to 10 Patients and 3 Users) or Commercial (requires a valid License). A Tier says which terms apply, **not how large the Deployment may be**: the limits of a Commercial Organization are the numbers written in its License file (ADR 043), so there are as many sizes as there are issued Licenses. A commercial License that has expired but is within a 30-day grace period still grants its own limits. After the grace period, the Organization falls back to Personal limits.
_Avoid_: plan, edition, subscription. A **Plan** is what a customer bought and lives in avisiohub, not here; OpenAvisio only ever sees the numbers.

**Subscription**:
The contract to operate a hosted Deployment, held in avisiohub. It decides whether the Deployment runs at all, and it is deliberately **not** the same thing as a License: a License lifts software limits, a Subscription is payment. A self-hoster has a License and no Subscription, a hosted individual has a Subscription and a small License, a Selbsthilfegruppe has both. Nothing in OpenAvisio reads or knows about a Subscription — non-payment stops a Deployment, it does not degrade one.
_Avoid_: plan, membership, licence (as a synonym)

### AI & Processing

**Processing Pipeline**:
The automated AI workflow that runs when a Document is uploaded. Produces a Summary, Recommendations, and extracted clinical data (Diagnoses, Medications, Measurements, Lab Results) which go directly into the Patient's record. Also proposes Events for appointments and dates found in the Document (past and future) — these require User acceptance before appearing on the health timeline. From invoices and receipts it also proposes Expenses (see Expense), which likewise require User confirmation before they count.
_Avoid_: AI pipeline, extraction pipeline, OCR pipeline

**Summary**:
A human-readable overview of a Document produced by the Processing Pipeline.
_Avoid_: abstract, description, overview

**Recommendation**:
An extracted next step or follow-up found in a Document — e.g. "return in three months", "take medication daily". Produced by the Processing Pipeline.
_Avoid_: suggestion, finding, action item

**AI Health Assistant**:
A conversational interface that answers questions about a Patient's health records using AI. Searches across all clinical data and Documents to generate answers.
_Avoid_: chat, RAG chat, AI assistant, health bot

### Clinical data

**Document**:
An uploaded medical file (PDF, image, scan). The source of truth from which clinical data is extracted. Processed through the AI pipeline to produce structured clinical data. Key metadata: `issued_date` (the date printed on the document, populated by the Processing Pipeline, overridable by the User) and `correspondent` (the issuing entity — see Correspondent).
_Avoid_: DocumentReference, record, file, attachment

**Correspondent**:
The named entity that issued or sent a Document — a hospital, clinic, lab, GP practice, or insurer. It is also who a Carer Update comes from, such as a Kita, a school or a respite carer. Correspondents are reusable across Documents and Carer Updates within an Organization (not free-text per entry), so a Kita's development report and its day-to-day updates sit under the same name. A Correspondent is only a name, with no kind. A Document may have at most one Correspondent; a Carer Update has exactly one.
_Avoid_: sender, provider, issuer, source

**Diagnosis**:
A medical condition or disease attributed to a Patient. Extracted from Documents or entered manually.

Only a condition a Document states of the Patient becomes a Diagnosis. A relative's condition (family history), a ruled-out one, and a question on a form all name a condition without stating it, and none of them becomes one. A **suspected** Diagnosis ("V.a.", "Verdacht auf") does become one, marked as suspected: to a family the suspicion is often the reason for the next appointment, so it must not vanish, and it must not read like a diagnosis a clinician made. A later Document stating the condition removes the mark; a later suspicion never puts it back on a stated Diagnosis.
_Avoid_: Condition, problem, issue

**Medication**:
A drug or treatment a Patient is taking or has taken, including dosage and period. Medications can be entered manually or extracted by the Processing Pipeline.
_Avoid_: MedicationStatement, drug, prescription

**Measurement**:
A physical metric recorded for a Patient over time — weight, height, blood pressure, temperature, oxygen saturation, etc. Used to track growth and physical development as well as health trends.
_Avoid_: Observation, vital sign, vital

**Lab Result**:
An outcome from a clinical test performed on a sample — blood test, urine test, biopsy, etc. Reported by a lab or extracted from a Document.
_Avoid_: Observation, test result, lab value

**Incident**:
An adverse event involving a Patient — a seizure, fall, allergic reaction, or other notable occurrence. Includes context such as suspected triggers and correlated Medications. The date of the earliest Incident of a given type is its _onset_ — no separate field is needed; onset is derived by querying the first recorded Incident.
_Avoid_: event, episode, adverse event

**Event**:
A single entry on a Patient's health timeline — an appointment, hospital stay, therapy session, medication plan record, or any other health-related occurrence past or future. Events can be linked to Documents. Events found by the Processing Pipeline are proposals: they appear on the timeline only once the User verifies the Document they came from, and are editable at that point.

An Event is _scheduled_ until someone closes it as _done_ or _cancelled_. The distinction is kept because the two are different facts, not two ways of saying "over": a Widerspruch Deadline closed as done means the objection was raised, closed as cancelled means it was deliberately let lapse. Closing an Event also ends its reminders.

Event categories include **deadline**: a dated obligation with a consequence for missing it, currently only the Widerspruch Deadline (see Widerspruch). A deadline is not an appointment — it has no time of day and no place, it is a last date, and it is announced further ahead than an appointment is.

Event categories also include **milestone**: a developmental achievement (first word, first steps, first solid food, toilet training, etc.), recorded with the date it happened and never compared against expected age ranges: that comparison is an assessment of development the software would be authoring. Milestones are specific to pediatric and developmental contexts and carry a developmental domain (motor, speech, cognitive, social). Do not use milestone for adverse medical firsts — those are Incidents.
_Avoid_: CalendarEvent, appointment, entry, item

**Health Log**:
A Patient's self-reported daily record — mood, pain level, sleep, bowel movement, medication compliance, and other subjective observations. Structured for trend tracking, not free-form journaling.
_Avoid_: DiaryEntry, diary, journal, daily log

**Carer Update**:
What someone who looks after a Patient without the family reported about one day: a Kita, later a school, respite care, a personal assistant, a therapist after a session. A User enters it, since the carers have no access: the Correspondent it came from, optionally the person as free text ("Frau M., key worker"), the day it is about (today unless changed), the text as free text, and whether it was copied word for word from what the carer wrote or retold from what they said at pickup. No structured fields and no photos; a formal report (development report, Förderplan) is a Document. Nothing is extracted from it. The AI Health Assistant may quote it, always naming the Correspondent, the day and whether it was retold, and never as its own assessment. The doctor and authority Handouts may include the Carer Updates of a period the User picks; the emergency and day-to-day Handouts never do. UI term in German: "Rückmeldung".
_Avoid_: Kita note, observation, report (a report is a Document), Care Notes (those go the other way, from the family to the carers)

#### Anamnesis

**Intake Form**:
The medical history questionnaire a practice, clinic or rehab facility has a Caregiver fill in before a first visit. Uploaded as a photo of the paper form or a PDF sent ahead, through its own entry point: an ordinary upload never becomes an Intake Form. The uploaded original is kept with the Intake Form, because it is the only record of exactly what was asked, but it is **not a Document**: it says nothing about the Patient, so it is not listed with the Documents, not run through the clinical extraction, not searched by the AI Health Assistant and not searched for answers. A blank form is a list of conditions phrased as questions, and any of those paths would take "Asthma? yes / no" for a statement about the Patient. It is deleted with the Intake Form. OpenAvisio answers it from the Patient's record and gives back an answer sheet in the form's own order, to copy from, hand in, or type into a practice portal. Questions the record cannot answer are put to the Caregiver, and the answers are kept as History Facts, so the next Intake Form asks only what no earlier one did.

OpenAvisio prefills only questions of fact (birth weight, when walking started, current medication). A question asking for a judgement ("is your child's development age-appropriate?", "have the seizures got worse?") is left to the Caregiver, however clearly the record seems to answer it: the doctor reads the sheet as the family's own account, and a judgement the software derived would reach them disguised as one. Beside such a question the relevant facts from the record may be shown verbatim as a reminder. In doubt, a question counts as a judgement.

The answer sheet is a draft until a Caregiver releases it, and every prefilled answer shows where it came from. It goes to a doctor, so nothing leaves unseen. Correcting an answer that came from the record changes the sheet at once and offers to change the record too; it never changes the record by itself. Correcting a History Fact on the sheet is simply the new History Fact. Once released, the sheet is frozen exactly as handed in and later changes to the record leave it alone, because it answers "what did we tell them?"; a correction after release is a new sheet. The next Intake Form reuses History Facts and the record, never an old sheet. UI term in German: "Anamnesebogen".
_Avoid_: calling the uploaded form a Document, questionnaire (reads like a study, see Sharing Purpose), survey, anamnesis (that is the whole history, not the form), Anamnesebogen outside German UI text

**History Fact**:
One piece of a Patient's history that has no other home in the record: birth weight, a course of pregnancy, epilepsy in an uncle, the school the Patient attends. Anything the record already holds is answered from there and written there instead (a medication is a Medication, an allergy a Diagnosis, a seizure an Incident, a first word a milestone Event), so there is never a second, stale copy of it. A History Fact comes from a Caregiver answering an Intake Form, or from a Document: when no History Fact answers a question, the Document text is searched, and a passage found there is offered with its citation and becomes a History Fact once a Caregiver confirms it. Documents are searched only when a form asks, never mined for History Facts on upload, since every letter retells the history slightly differently. Each History Fact carries the date it was last confirmed, its source, and how it ages:

- _lasting_: true once, true for good. Filled in silently.
- _changeable_: may no longer hold. Offered with the date it was last confirmed and counts as an answer only once a Caregiver confirms it again.
- _visit-only_: the reason for this visit, current complaints, who referred. Kept with the Intake Form it answered, never offered for the next one.

A History Fact keeps its question as it was asked, not as an entry in a fixed list of topics. A new Intake Form is matched to History Facts by meaning, one answer may draw on several of them, and a wrong match is caught because every prefilled answer shows its source.

History Facts can be looked through, corrected and deleted on their own, outside any Intake Form, but they only come into being through one: without the question a form asked, a History Fact has nothing to be found by later.

A History Fact belongs to exactly one Patient, family history included. Siblings in the same Deployment are asked again: family history is relative to the person ("maternal uncle" may be no relative of a half-sibling), and nothing in the model relates one Patient to another.

The AI Health Assistant reads lasting and changeable History Facts with the date they were last confirmed; visit-only ones describe a past visit and stay out, so they are not taken for current complaints.

The AI proposes how a History Fact ages; the Caregiver can change it. See ADR 047. UI term in German: "Angabe".
_Avoid_: answer (an answer belongs to one question on one form, a History Fact outlives the form), anamnesis entry, note

### Finance

**Expense**:
A monetary amount a Caregiver paid or owes for a Patient's care — from an invoice, receipt, or bill — recorded to help with insurance applications (Krankenkasse/Pflegekasse) and tax returns. Each Expense carries an amount, a date, a coarse category (care aid, medication co-payment, therapy, assistive device, travel, other), and an optional reimbursed amount; the still-open remainder is what an insurer has not covered and what may be tax-deductible. An Expense is either entered manually or proposed by the Processing Pipeline from an invoice Document. A proposed Expense does not count toward any total or export until a User confirms it. OpenAvisio only prepares this overview — it does not transmit anything to an insurer.
_Avoid_: cost, bill, invoice (as the entity name), receipt, claim, charge, budget. "Budget" is forward-looking — a limit you set and spend against — while an Expense is money already spent and recorded, so the two are not synonyms; if planning against a limit is ever wanted, it is a second concept beside Expense, not a rename of it. "Kosten" in German UI text has the same problem and reads like accounting; the user-facing term is "Ausgaben".

#### Insurance

**Kassenbescheid**:
A written decision by a Krankenkasse or Pflegekasse on something a Caregiver applied for — a Kostenübernahme, a Pflegegrad. It is a Document like any other, distinguished by carrying a **Rechtsbehelfsbelehrung**: the formulaic paragraph stating that the decision can be objected to and within what period. That paragraph, not the outcome of the decision, is what OpenAvisio reacts to. Whether a decision is good or bad news is not readable from the letter: a Pflegegrad granted below the one applied for is printed as an approval, and only someone who knows the application can tell the difference.
_Avoid_: rejection letter, denial, Ablehnung (a decision may well be favourable), insurance document (that is the wider category of insurer post)

**Einstufung**:
The grading of a Patient's care need by a Pflegekasse, recorded as one entry per assessment: the Pflegegrad it assigned, the total points, the six module scores the assessment is built from, the date it takes effect, an optional end date, and the Kassenbescheid it came from. A Patient's current Pflegegrad is their most recent Einstufung; the earlier ones are kept because an upgrade often takes effect retroactively, so which grade applied in a given month is a question with money attached. Entered by hand or proposed from a Kassenbescheid and confirmed by a User.

The module scores are the point of keeping the history. A Pflegegrad is one number that moves every few years and says nothing about what changed; the modules say where the care need moved, in the same terms the Pflegekasse decided in.
_Avoid_: Pflegestufe (the pre-2017 term for a different, three-level scheme), care level, Pflegelevel, and Pflegegrad as the name of the record

**Pflegegrad**:
The level a Pflegekasse assigns to a Patient, 1 to 5, following from the total points of an assessment. An attribute of an Einstufung, not a thing of its own: an Einstufung has module scores and a validity, a Pflegegrad is a number. Untranslated in every language, like Widerspruch, because it is the word printed on the letter.

OpenAvisio records what a Pflegegrad is and shows where the points sit between the statutory thresholds. It states no benefit amounts and no entitlements: those change by statute, depend on circumstances not visible in the record, and a wrong figure costs the Caregiver money. See ADR 042.
_Avoid_: care level, grade, Pflegestufe

**Widerspruch**:
A Caregiver's formal objection to a Kassenbescheid, and the **Widerspruch Deadline** is the last date on which it can be raised. The word stays untranslated in English text and UI: "appeal" and "objection" each mean something adjacent, and the Caregiver is looking for the word printed on the letter in front of them.

The Deadline is the point of the concept. It is not printed on the letter — the letter gives a decision date and a period, and the end date follows by calculation, so it is always OpenAvisio's arithmetic and is labelled as such. It surfaces as an Event of category deadline, proposed from the Kassenbescheid and confirmed when the User verifies that Document. Missing it makes the decision final, which is why it is announced twice and well ahead, and why "when in doubt, object early" is part of what is shown: objecting too early costs nothing.

Whether the Widerspruch was actually raised is recorded by closing the Deadline: _done_ means raised, _cancelled_ means deliberately let lapse. There is no separate Widerspruch record, and no state beyond that — OpenAvisio prepares, it does not transmit, so the objection itself is written and sent by the Caregiver, outside the system, and how the Kasse then answers is outside it too. See ADR 041.
_Avoid_: appeal, objection, dispute, complaint, Einspruch (a different procedure, tax law)

## Data sharing

**Sharing Purpose**:
A named reason for which a User collects Patient files — typically a research study or registry submission. It owns the Share Requests sent out and the resulting Shares. A single Document can be shared to several Sharing Purposes independently, each with its own consent. It carries an **identification mode** set by the Purpose Manager: _identified_ (the Patient's name is shown alongside each shared file) or _anonymous_ (the Purpose Manager sees only a stable per-Patient pseudonym, never the name). Anonymous is pseudonymity at the metadata level only — file _contents_ are never altered and may still carry identifying information. (Distinct from the FHIR `survey` observation category used in exports, which is unrelated.)
_Avoid_: study, survey, project, campaign, research purpose

**Purpose Manager**:
Any Coordinator or admin acting on a Sharing Purpose. A Sharing Purpose belongs to the Organization, not to one person: any Coordinator/admin can create it, manage it, and download the files shared to it; the creating User is recorded only for accountability, and staff turnover orphans nothing. Managing a Sharing Purpose grants access solely to the files explicitly shared to that Purpose — nothing else in a Patient's record — and is independent of any Caregiver access the same person may hold.
_Avoid_: purpose-owner, requester, collector, study owner, researcher

**Share Request**:
The org-wide ask carried by a Sharing Purpose — "this study wants a kind of data (e.g. EEG)" — surfaced to every Caregiver against each of their Patients. It is _not_ materialised per Patient: a request is the derived "open" state of a Sharing Purpose for a Patient that has no response yet. Only responses are stored (a Share when fulfilled, a decline marker when refused); the Sharing Purpose's activation time records when everyone was asked. The Caregiver decides which Document(s) fulfil it.
_Avoid_: invitation, data request, ask

**Share**:
A consented link between one Document and one Sharing Purpose that lets a Purpose Manager access and download that file. Created when a Caregiver selects a Document and consents in response to a Share Request; the consenting User and time are always recorded. A Share is active or revoked, and its access also ends if the underlying Document is deleted. Closing the Sharing Purpose stops new Shares but leaves existing Shares downloadable. Revocation ends future access in OpenAvisio but cannot recall files a Purpose Manager has already downloaded and forwarded externally.
_Avoid_: grant, data share, file share, access grant

**Document Share Link**:
A time-limited, read-only, anonymous link a Caregiver generates to give an _external_ specialist (a doctor or therapist with no account) access to a chosen set of a Patient's Documents — the outbound counterpart to the inbound Sharing Purpose flow. Whoever holds the link URL can view and download the shared Documents (name, date of birth, and each Document's own summary + extracted data are shown) until it expires (7/30/90 days) or is revoked. Only the token's hash is stored; the link is shown once at creation. Creating one is reserved for a Patient's own Caregivers (active legal representative / non-staff with access) — staff acting only in an admin/manager capacity cannot. Every external access is audit-logged (recipient IP + user-agent); Patient Erasure cascades the links, their items, and those access logs. See ADR-021.
_Avoid_: public link, guest access, external share (as a noun for the Study Share)

**Handout**:
A printable account of a Patient, put together from the record for one kind of recipient: a doctor at an appointment, emergency services, an authority or insurer (Medizinischer Dienst, a Widerspruch, an application), or the people who look after the Patient day to day (Kita, school, respite care). Each recipient gets a fixed variant that decides which parts of the record go in. It contains only entries a User has confirmed, reproduced as recorded, with no text written by the AI, and a suspected Diagnosis stays marked as suspected. The day-to-day variant shows no Diagnosis but allergies unless the User picks one, and the emergency variant fits one page. The doctor and authority variants may include the Carer Updates of a period the User picks. If there is no Emergency Plan or no Care Notes yet, the Handout is made without that part, never with a line saying there is none. Before it leaves, the User sees it and may leave out single entries; that choice is not remembered, so the next Handout starts from the variant again and a new Diagnosis is never silently left out or taken along. Anyone with access to the Patient may download one; adding it to a Document Share Link beside the chosen Documents is reserved for whoever may create that link, and the link carries it frozen as previewed, dated, never regenerated. It is in German or English: only the headings and labels are translated, the entries stay as recorded. UI terms in German: "Infoblatt für Ärzte / für den Notfall / für Ämter und Kassen", and "Steckbrief" for the day-to-day carers.
_Avoid_: Summary (that is a Document's), overview, patient profile, record extract, Steckbrief outside that one variant

**Emergency Plan**:
What to do when something goes wrong with a Patient, written by a Caregiver because the record cannot derive it: one per Patient, made of situations (a trigger such as "seizure longer than 3 minutes" and the steps to take), emergency contacts, and free notes. A step that gives a rescue medication points at that Medication instead of restating it, so the dose shown is always the one in the record. It may point at Documents that hold a clinician's own emergency plan; the Handouts name them, and a Document Share Link carrying the Handout carries them too. The emergency and day-to-day Handouts include it. The AI Health Assistant never restates it, not even as a quote: asked what to do in an emergency, it points to the Emergency Plan itself, because a misquoted dose in a chat answer is the one mistake that must not happen there. UI term in German: "Notfallplan".
_Avoid_: seizure plan, action plan, Notfallausweis

**Care Notes**:
How a Patient gets through an ordinary day, written by a Caregiver for the people who look after the Patient without being family or clinicians: communication, eating and drinking, sleep, aids, what helps, what overwhelms. Kept apart from the Emergency Plan so that one stays short enough to read in an emergency. Only the day-to-day Handout (Steckbrief) includes them; the AI Health Assistant may quote them. UI term in German: "Alltagsinfos".
_Avoid_: profile, care plan (that is a nursing term for something else), notes

## Example dialogue

> **Dev:** We need a way for the nurse to see all of Emma's records.
> **Domain expert:** Add her as a Caregiver for that Patient. She'll have access to all clinical data — Diagnoses, Medications, Measurements, Events.
>
> **Dev:** Emma's mum uploaded a neurology report. What happens?
> **Domain expert:** The Processing Pipeline runs — it produces a Summary, any Recommendations, and extracted clinical data. If the report mentions a follow-up appointment, the pipeline proposes an Event. The Caregiver accepts it and it appears on the health timeline.
>
> **Dev:** The care home has 30 residents. Do we grant the night nurse access to each Patient individually?
> **Domain expert:** No — create a Group for the ward, add all Patients to it, then add the nurse. That generates the access grants in bulk.
>
> **Dev:** Emma's grandmother has power of attorney. Does she need a different account type?
> **Domain expert:** No — she's a Caregiver like anyone else. The legal relationship gets recorded as an attribute on her access, but her permissions are the same.
>
> **Dev:** Emma had her first seizure at age 3. How do we record that, and how do we find when it first happened later?
> **Domain expert:** Record it as an Incident. Onset is the date of the earliest seizure Incident — no separate field. Just query the first one.
>
> **Dev:** Emma's mum uploads a letter from the Pflegekasse. They applied for Pflegegrad 3 and got 2. Is that a rejection?
> **Domain expert:** The letter says approval, and nothing in it says otherwise. Don't try to judge the outcome — it carries a Rechtsbehelfsbelehrung, so it's a Kassenbescheid, and that alone gets her the Widerspruch Deadline. Whether she wants to object is hers to decide.
>
> **Dev:** The Bescheid says Pflegegrad 2, 42.5 points. Where does that go, and do we tell her what she gets for it?
> **Domain expert:** It becomes an Einstufung: grade 2, the points, the six module scores, effective from the date on the letter, linked to the Bescheid. Show her where 42.5 sits between the thresholds. Do not tell her what it pays out, that is not ours to state.
>
> **Dev:** The Kasse refused to pay for a wheelchair. Do we link that to the Expense?
> **Domain expert:** There is no Expense. The wheelchair would have been settled between the Kasse and the supplier, so Emma's mum never paid anything to record. That's why a Widerspruch doesn't hang off Expenses.
>
> **Dev:** Emma's mum wants to record when Emma said her first word.
> **Domain expert:** That's a milestone Event — category milestone, domain speech. Not an Incident, not a free-form note.

## Domain term → current code term mapping

The domain vocabulary above is the authoritative language for issues, ADRs, and PR descriptions. The codebase was written before some terms were finalised and uses different names in several places. When reading or modifying code, map as follows:

| Domain term | Code term | Notes |
|---|---|---|
| Group | `Family` / `FamilyMembership` | The domain term was settled after the model was built. A rename is tracked but not yet done. |
| Caregiver | `FamilyMembership` + `PatientAccess` | Family membership is the primary carrier; direct grants via `PatientAccess` cover non-family caregivers. |
| Coordinator | `manager` role | The `admin` role has all Coordinator permissions plus system administration (user management, org settings). Neither role grants any clinical data access — that always requires a PatientAccess grant; creating a Patient auto-creates a revocable admin-level grant for the creator (ADR 025/026). |
| Measurement / Lab Result | `Observation` | Both are stored as `Observation` rows; `category` distinguishes them at query time. |
| Diagnosis | `Condition` | SQLAlchemy model is `Condition`; API path is `/conditions`. |
| Health Log | `DiaryEntry` | SQLAlchemy model is `DiaryEntry`; API path is `/diary`. |
| Event | `CalendarEvent` | SQLAlchemy model is `CalendarEvent`; API path is `/calendar/events`. |

Do not use the code term in new written communication (issues, ADRs, PR descriptions). Do use it when referring to specific files, models, or routes.

