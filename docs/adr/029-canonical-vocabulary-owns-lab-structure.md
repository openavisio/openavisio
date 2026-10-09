# ADR 029: A canonical vocabulary owns lab structure, the model only reads

**Status:** Accepted (extends ADR 028)

## Context

Lab grouping was driven by the `panel` free-text the OCR/LLM emitted (the printed
section heading). That varies per report, per OCR pass, and per model: the same
analyte (Creatinin) landed under "Klinische Chemie, Basisanalytik" in one report,
"(no panel)" in another (headerless page), and could shift again when the
extraction model is swapped (gemma4 → qwen3.6) or upgraded next year. Result:
one analyte fragmented across several groups in the UI.

The underlying question: when the model interprets a document differently — today
between models, tomorrow a better model — what keeps the data organized the same?

## Decision

**Separate *reading* from *structure*.**

- **The model reads.** It extracts raw values/text from the document. That is all.
- **A deterministic, controlled vocabulary owns structure** — a parameter's canonical
  identity (`code`), its group (`panel`), reference-range parsing, and out-of-range.
  Keyed on the canonical code, not on whatever section heading the OCR/model produced.

Concretely (`backend/app/services/lab_codes.py`):

- A vocabulary maps ~50–100 common German lab analytes (aliases, incl. parenthetical
  forms) → a canonical `code` → a **canonical panel** from a small fixed set:
  Blutbild · Differentialblutbild · Klinische Chemie · Vitamine & Spurenelemente ·
  Gerinnung · Medikamentenspiegel.
- Panel resolution: known analyte → its canonical panel; else the free-text panel
  normalised to a canonical one (known headings collapsed, `, Basisanalytik`/`:`
  stripped); else a generic fallback.
- Applied at ingest and manual create, so the stored `code`/`panel` are stable.
- Not adopting full LOINC now (YAGNI — hundreds of analytes); the list grows with
  real data, and unknown analytes fall back cleanly to their printed name/panel.

## Consequences

- **Model-independent structure.** A better model next year reads values more
  accurately but cannot reorganise them — grouping is our deterministic job, not
  its interpretation. No drift on model swap/upgrade.
- Creatinin (and every known analyte) always groups under one canonical panel,
  regardless of which report/model produced it or whether the page had a header.
- This is ADR 028 taken one step further: 028 moved lab *values* off the LLM onto a
  deterministic parser; 029 moves *grouping/identity* off the model's free text onto
  a controlled vocabulary.
- Existing rows keep their old panel until re-extracted; new ingests are canonical.
- The frontend only renders i18n labels for the 15 CBC slugs; other coded analytes
  show their printed name (`code_display`).
