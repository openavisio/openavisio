# ADR 028: Structured vision extraction for lab tables, not flat-text OCR

**Status:** Accepted

## Context

The document pipeline is OCR → flat text → text-LLM extraction (`backend/app/workers/pipeline.py`: ocr → classify → extract-entities). The OCR stage runs GLM-OCR in `Text Recognition:` mode, which returns **flat text**. For a multi-column lab table that destroys column alignment before the extraction LLM ever runs.

Real failure (doc `bf538900`, MVZ Labor 7-page Befundbericht, patient upload July 2026):

- The **Ergebnis (result) column is grey-shaded** on page 1. GLM-OCR dropped it. The OCR text for Hämoglobin read `10.7 - 13.9 g/dl` — reference range only, no result. The LLM then took `10.7` (the lower reference bound) as the value; the true value `14.1` was never in the text. Same for Leukozyten (`9.50` lost, garbage `2.2` emitted).
- Where the result column was **not** shaded (page 2 Klinische Chemie), OCR kept it and extraction was correct (Kalium 4.8, Glucose 50, Vitamin D 57.1) — proving the LLM is not hallucinating; the OCR text is lossy.
- The LLM also extracted only ~6 of ~50 rows — the prompt asks for a "summary", so it cherry-picks instead of transcribing. Historical Kumulativbefund columns (pages 4–7) add further confusion.

GLM-OCR scores high on OmniDocBench composite (94.62), so the fix is not "a bigger model" — it is the **architecture** (flat text) plus **shading** plus a **summarizing prompt**. For medical data a wrong value is worse than a missing one.

## Decision

**1. Image → structured extraction for lab/results documents.** The vision model emits structured rows (`{parameter, value, unit, reference_range}`) directly from the page image, preserving column alignment, instead of OCR→flat-text→re-parse. Free-text documents keep the existing text path.

**2. Model, two tiers, routed on quality not layout.**
- **Primary (OCR box, RTX 3090, via vLLM):** **dots.ocr** — 1.7B, ~3.5 GB, table-parsing SOTA, outputs structured markdown/JSON. Replaces GLM-OCR for structured docs. dots.ocr does its own layout segmentation (table / text / figure), so there is **no separate layout classifier and no per-layout model router** — one parser covers tables, prose, and forms.
- **Heavy fallback (future RTX PRO 6000, via vLLM):** **Qwen3-VL-32B** for blurry/photographed or low-confidence pages — a reasoning VLM recovers degraded digits from context where a pixel parser can't.

**Routing (quality escalation, not a layout taxonomy):** run dots.ocr on every page; escalate a page to the Qwen3-VL fallback only when it is **blurry** (variance-of-Laplacian below threshold) **or** dots.ocr returns **low confidence / an empty table**. A cheap deterministic `analyze_page()` (Pillow-only: sharpness, table-ratio via projection profile, dark-pixel ratio) produces the blur/quality signal before the model runs. The failure axis that needs a different model is image *quality*, not layout — layout is dots.ocr's job.

**3. Image preprocessing** before the model: grayscale + contrast/threshold (de-shade the highlighted cells) + deskew. Helps every model, cheap. Keep a calibration knob — real photos vary.

**4. Prompt hardening** (structured extraction): transcribe **every** row of every results table; only the current/most-recent result column (ignore cumulative history); **never use a reference range as the value — omit the row if no result is legible.**

**5. Verify UI** surfaces out-of-range and low-confidence rows so the human catches misses before Confirm & Save. Extraction stays deterministic (temperature 0).

## Consequences

- Column alignment is preserved by construction; the shaded-column class of error goes away.
- Less VRAM than a large generalist, and the 3090 stays the OCR-only box (ADR context from the GPU-topology discussion).
- Two model paths to serve and route between (primary + degraded-input fallback) — routing on OCR confidence.
- Ties to #69: extraction now actually fills `panel` / `reference_range` / per-row values that #69's schema added.
- GLM-OCR is retired for structured docs; the `Text Recognition:` flat-text mode remains only as a last-resort fallback.
