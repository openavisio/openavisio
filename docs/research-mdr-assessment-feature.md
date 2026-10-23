# Research: what it would take to let the AI assess lab values, trends and give recommendations

*Researched 2026-07-21 against primary sources (EUR-Lex consolidated MDR 2017/745 and IVDR 2017/746,
MDCG 2019-11 Rev.1 of 17 June 2025, MDCG 2020-1, MDCG 2025-6, BfArM and DiMDI/BfArM pages, published
notified body fee schedules from TÜV SÜD and BSI, EU AI Act 2024/1689 plus the Digital Omnibus on AI
as adopted in 2026). Context in the repo: `docs/regulatory-positioning.md` (current stance: not a
medical device) and `aiservice/prompts/chat_system.md` (the prompt that refuses every assessment).
**This is not legal advice.** It is a sourced engineering brief; a notified body or a regulatory
lawyer owns the final call, and several of the questions below are genuinely contested.*

Throughout, three things are kept apart on purpose:

- **Law**: what the regulation text says.
- **Practice**: what a notified body or an auditor will expect even where the law is silent.
- **Inference**: my reading, flagged as such.

## 1. Qualification and classification: where does "this potassium is high" land?

### 1.1 Qualification, the first question

A medical device under [MDR Article 2(1)](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02017R0745-20250110)
is "any instrument, apparatus, appliance, **software** ... intended by the manufacturer to be used ...
for one or more of the following specific medical purposes: diagnosis, prevention, monitoring,
prediction, prognosis, treatment or alleviation of disease ...". The hook is **intended purpose**,
defined in Article 2(12) as the use intended "according to the data supplied by the manufacturer on
the label, in the instructions for use or in promotional or sales materials or statements". Claims
made in the README, the website and the UI text are the legal object, not the model weights.

[MDCG 2019-11 Rev.1](https://health.ec.europa.eu/document/download/b45335c5-1679-4c71-a91c-fc7a4d37f12b_en?filename=mdcg_2019_11_en.pdf)
(17 June 2025, [update notice](https://health.ec.europa.eu/latest-updates/update-mdcg-2019-11-rev1-qualification-and-classification-software-regulation-eu-2017745-and-2025-06-17_en))
gives the decision steps. Step 3 asks whether the software performs an action on data "beyond
storage, archival, communication, simple search, lossless compression". Step 4 asks whether the
action is "for the benefit of individual patients". Section 3.1 is explicit that "Simple search",
"the retrieval of records by matching record metadata against record search criteria or ... the
retrieval of information", does not qualify, "e.g. library functions", **but**: "software would not
be considered as conducting 'Simple search' if it contributes to achieving a medical purpose. E.g.
User Interface (UI) search feature or a software that performs search using Natural Language
Processing (NLP) where those actions contribute to achieving a medical purpose."

That sentence is new emphasis in Rev.1 and it is aimed squarely at products like this one. RAG over
a patient's own documents is not automatically safe because it is "just retrieval"; it is safe only
as long as the retrieval does not serve a medical purpose. Rev.1 also introduces the term **Medical
Device Artificial Intelligence (MDAI)** and reinforces the **module** concept (see section 7.2).

Saying "this value is elevated", reading a trend, or recommending an action is squarely
"processing, analysing, interpreting" clinical information for the benefit of one patient with a
diagnostic or monitoring purpose. **Inference, but not a close call**: the assessment feature as
described qualifies as device software. The current prompt (`chat_system.md`) refuses exactly the
set of outputs that would trigger it, which is a correct reading.

### 1.2 MDR Rule 11 or IVDR? The lab-value case is probably IVDR

This is the part `docs/regulatory-positioning.md` does not address and it changes the whole route.

[IVDR Article 2(2)](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02017R0746-20250110)
covers "**software** ... intended by the manufacturer to be used in vitro for the examination of
specimens ... solely or principally for the purpose of providing information ... (a) concerning a
physiological or pathological process or state ... (f) to define or monitoring therapeutic
measures." MDCG 2019-11 Rev.1 section 3.4 and its "Expert system" example (Annex I, f.2) close the
gap for software that never touches a specimen itself: "MDSW which is intended to provide
information within the scope of the in vitro diagnostic medical devices definition by capturing and
analysing together one or multiple results obtained for one patient by means of in vitro
examination of body samples (possibly combined with information from medical devices and
non-medical devices)."

So a feature that interprets blood results is IVD MDSW, classified under
[IVDR Annex VIII](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02017R0746-20250110),
not under MDR Rule 11. Two rules decide the class:

| Rule | Text | Effect here |
|---|---|---|
| Rule 4(a) | "Devices intended for self-testing are classified as class C", except pregnancy, fertility, cholesterol, and urine glucose/erythrocytes/leucocytes/bacteria (class B) | "Device for self-testing" is defined in Art. 2(5) as "any device intended by the manufacturer to be used by **lay persons**, including devices used for testing services offered to lay persons by means of information society services". A family caregiver is a lay person (MDR Art. 2(38)) |
| Rule 3(k) | class C for "management of patients suffering from a **life-threatening disease or condition**" | Chronically ill children, e.g. Dup15q, epilepsy, metabolic disease: plausibly in scope |
| Rule 6 | "Devices not covered by the above-mentioned classification rules are classified as class B" | The fallback if neither bites |

**Inference**: an AI that tells a lay caregiver whether their child's lab value is worrying reads as
**class C** under Rule 4(a). Class B is the best case and it still needs a notified body. There is
no self-declaration route out of this, unlike MDR class I.

Cross-check with the MDR side for the non-lab parts of the same feature (trend interpretation on
vitals, symptom questions, "should we go to hospital"): MDR Annex VIII **Rule 11** reads "Software
intended to provide information which is used to take decisions with diagnosis or therapeutic
purposes is classified as class IIa, except if such decisions have an impact that may cause: death
or an irreversible deterioration of a person's state of health, in which case it is in class III;
or a serious deterioration of a person's state of health or a surgical intervention, in which case
it is classified as class IIb." MDCG 2019-11 Rev.1 Table 1 maps this onto the IMDRF grid of
information significance (inform / drive clinical management / treat or diagnose) crossed with
healthcare situation (non-serious / serious / critical). Its own Annex IV example, "a mobile app
intended to analyse a user's heartbeat, detect abnormalities and inform a physician accordingly
should be classified as class IIb per Rule 11(a)", is close to what "flag this value as worrying"
does, and that example still assumes a physician downstream. **Realistic band: IIa if framed as
merely informing, IIb once the output could plausibly delay care in a serious condition.**

Either way, class IIa/IIb MDR or class B/C IVDR, the answer to "what would OpenAvisio need" starts
with a **notified body**. Nothing in either regulation lets a manufacturer self-declare this.

## 2. The conformity assessment route that follows

### 2.1 What the law requires

[MDR Article 10](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02017R0745-20250110)
is the checklist, and it is not optional for any class:

| Obligation | Article | What it means for a one-person project |
|---|---|---|
| Risk management system | Art. 10(2), Annex I §3 | A documented, maintained process, not a risk register in a wiki |
| Clinical evaluation incl. PMCF | Art. 10(3), Art. 61, Annex XIV | See 2.3 |
| Technical documentation | Art. 10(4), Annexes II + III | The single largest writing job |
| QMS covering 13 named areas | Art. 10(9)(a) to (m) | Design control, supplier control, PMS, vigilance, CAPA |
| EU declaration of conformity, CE mark | Art. 10(6), Art. 19, Art. 20 | |
| UDI + registration | Art. 10(7), Art. 27, Art. 29, Art. 31 | Basic UDI-DI, device registration, EUDAMED actor registration |
| Records kept 10 years | Art. 10(8) | Survives the project ending |
| Person Responsible for Regulatory Compliance (PRRC) | Art. 15 | Micro/small enterprises may use an **external** PRRC "permanently and continuously at their disposal" rather than in-house |
| Post-market surveillance system + PMS plan | Art. 83, Art. 84 | |
| PSUR | Art. 86 | class IIa: update "when necessary and at least every two years"; class IIb/III: **at least annually** |
| Vigilance, serious incident reporting | Art. 87 to 89 | Deadlines in days, not weeks |
| Liability cover proportionate to risk class | Art. 10(16) | An actual insurance policy |

Conformity assessment route ([MDR Art. 52](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02017R0745-20250110)):
class IIa needs Annex IX Chapters I and III (QMS assessment plus technical documentation assessment
on a sampling basis), class IIb the same plus assessment of the technical documentation for at
least one representative device. On the IVDR side
([IVDR Art. 48](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02017R0746-20250110)),
class B needs Annex IX with technical documentation assessment on a sampling basis and class C
needs Annex IX including assessment of the technical documentation, with the extra twist that
**for devices for self-testing the notified body examines the design specifically for lay use**.

### 2.2 Standards: what is legally required versus expected in practice

Harmonised standards are voluntary; [MDR Art. 8](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02017R0745-20250110)
only says conformity with them gives a *presumption* of conformity. What is actually harmonised
matters because it decides whether you get that presumption. From the Commission's own
[summary list of harmonised standards for medical devices](https://single-market-economy.ec.europa.eu/single-market/european-standards/harmonised-standards/medical-devices_en)
([PDF, list file dated 20.10.2025](https://single-market-economy.ec.europa.eu/document/download/40f686be-acf4-4a0b-b6d2-20a00f46a8bc_en?filename=SummaryListForLegislation_20.10.2025.pdf)):

| Standard | Harmonised under MDR? | Reality |
|---|---|---|
| EN ISO 13485:2016 (+AC:2018, +A11:2021) | **Yes**, OJ L 1, Decision 2022/6, 05.01.2022 | The only practical way to satisfy Art. 10(9); certification itself is not legally mandatory, an auditable QMS is |
| EN ISO 14971:2019 (+A11:2021) | **Yes**, OJ L 138, Decision 2022/757, 17.05.2022 | Risk management per Annex I §3 |
| EN ISO 14155:2020 | **Yes** (entries dated 2026 in the same list) | Only if you run a clinical investigation |
| **IEC 62304** (software life cycle) | **Not in the list** | Every notified body still expects it. No presumption of conformity, so you must argue GSPR 17 compliance on its terms |
| **IEC 62366-1** (usability engineering) | **Not in the list** | Same. For a lay-user device, usability is where the assessment will hurt most |

So: law requires a QMS, risk management, software life cycle discipline and usability engineering
in substance (Annex I GSPR 17.1, 17.2, 5 and 14 style requirements). Practice requires them in the
shape of 13485 / 14971 / 62304 / 62366-1 documentation, because that is the shape auditors read.
**Inference**: for a solo developer, ISO 13485 certification is not strictly required by MDR text
but is in effect mandatory, because the notified body assesses the QMS anyway and doing it without
a 13485 skeleton costs more, not less.

### 2.3 Clinical evaluation, the part money cannot short-circuit

[MDCG 2020-1](https://health.ec.europa.eu/system/files/2020-09/md_mdcg_2020_1_guidance_clinic_eva_md_software_en_0.pdf)
requires three components of clinical evidence for every MDSW:

1. **Valid clinical association / scientific validity**: that the output "is associated with the
   targeted physiological state or clinical condition", founded on literature, guidelines or own
   studies. For "potassium 5.8 in a child on drug X is worrying", the association is standard
   medicine; this component is the cheap one.
2. **Technical performance / analytical performance**: "the demonstration of the MDSW's ability to
   accurately, reliably and precisely generate the intended output, from the input data". This is
   the killer for an LLM pipeline. The input is OCR of a scanned lab report, and the output is
   generated by a stochastic model whose weights the operator can swap. Demonstrating precision
   means a frozen model, a frozen prompt, a curated ground-truth dataset and measured error rates.
3. **Clinical performance**: "ability to yield clinically relevant output in accordance with the
   intended purpose", evidenced in the target population. MDCG 2020-1 adds that where the output
   "impacts clinical outcomes ... or patient management decisions, then a prospective study may be
   required".

**Inference, and the most important sentence in this section**: the AI part is not the hard part.
A locally hosted open-weight model that the operator may upgrade at will is architecturally
incompatible with "accurately, reliably and precisely" unless the certified module pins the model,
the quantisation, the prompt and the inference stack as part of the device, and treats any change
as a design change under Art. 10(9)(a).
