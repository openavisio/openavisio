# Models and GPU sizing

Which models to run, what each GPU size costs you in extraction quality, and which
parts of the pipeline a weaker model cannot touch.

The numbers here are measured on 13 real German documents — Arztbriefe, a Pflegegutachten,
a genetics report, insurer letters — through the actual pipeline, at `temperature=0` with
thinking disabled, using `scripts/ab-extract.py`. They are not benchmark scores.

## The short version

| VRAM | Text model | What you get |
|---|---|---|
| **24 GB+** | `qwen3.6:27b-mtp-q4_K_M` (17.8 GB) | the reference configuration |
| **16 GB** | `qwen3:14b` (9.3 GB) | same diagnoses and recommendations, loses appointments |
| **12 GB** | `qwen3:14b`, roles split across two hosts | as above, tighter |
| **8 GB** | not recommended — see below | |

Plus, on any tier: `glm-ocr:Q8_0` (1.6 GB) for vision OCR and `qwen3-embedding:4b`
(2.5 GB) for embeddings. Those two are small and should not be downgraded; see
*What a weaker model cannot break*.

The full working set is about **22 GB** (17.8 + 1.6 + 2.5), which does not fit a 24 GB
card together with context. Either split the roles across two Ollama hosts —
`OLLAMA_URL` for text, `OLLAMA_VISION_URL` and `OLLAMA_EMBED_URL` for the rest — or use
a single 32 GB card, which holds all three at once.

## What each size actually costs

Totals across the same 13 documents:

| | Diagnoses | Medications | Measurements | Appointments | Recommendations | Failures |
|---|---|---|---|---|---|---|
| `qwen3.6:27b` (17.8 GB) | **60** | 7 | 177 | **9** | **32** | 0 |
| `qwen3:14b` (9.3 GB) | **60** | 10 | 165 | 3 | **32** | 0 |
| `qwen3.5:9b` (6.6 GB) | 46 | 9 | 201 | 14 | 29 | 0 |

**Read the failure column first: there is none.** No model errored, on any document. A
model that is too small does not break — it quietly files worse data. Nothing in the
application will tell you, and the numbers above are the only way to see it.

### 14B: as good on diagnoses, unreliable on appointments

`qwen3:14b` matches the 27B on diagnoses (60) and recommendations (32). That is the
useful surprise here: the drop is not gradual with size.

Where it loses is appointments — 3 against 9 — and it loses them in two ways. On three
documents it found none where the 27B found one each. On a Diakonie-Klinikum letter the
27B extracted three appointments with valid dates (SPZ follow-up, school placement,
neuro-orthopaedic clinic) while the 14B extracted one, dated **`2024-11-00`**: a day
zero, which is not a date.

It is also weaker on the longest documents. On a 43k-character genetics report the 27B
found 4 diagnoses to the 14B's 1, and on a 29k-character Pflegegutachten the 27B found 7
measurements to the 14B's none — even though the 14B's 40,960-token context window is
larger than the 32,768 the extraction stage requests, so nothing was truncated.

### 9B: misses diagnoses and invents measurements

`qwen3.5:9b` extracted **2 diagnoses where the 27B extracted 12** from the same AOK
Hilfsmittel application — missing epilepsy, developmental delay, muscular hypotonia,
ataxia, strabismus and more that were in the text.

Worse, its higher measurement count is not better recall. On the genetics report it
returned 22 "measurements" that are sequencing quality metrics: read depth 41.65, bases
in target region 7,068,416, gaps 21,893, percent gaps 0.31 %. Those would appear in the
Patient's Measurements list beside weight and blood pressure. The 27B correctly returned
none.

It also answered in English on German documents despite the language instruction.

**Do not run a 9B-class model for extraction on a real Patient record.** If that is all
the card holds, run the document vault and enter clinical data by hand.

## What a weaker model cannot break

**Lab values.** Documents dominated by lab tables scored identically on all three models
(47, 48 measurements). Those values never reach the model: `parse_lab_tables` reads them
deterministically from the OCR HTML (ADR 028). A weaker model degrades diagnoses,
appointments and recommendations — not lab results.

**Embeddings**, as long as you keep `qwen3-embedding:4b`. It is 2.5 GB and fits
everywhere, so there is no reason to substitute it. If you do substitute it, note that
the pgvector column is `Vector(768)`: a model must be natively 768-dimensional or
Matryoshka-truncatable to that width, or inserts fail. And check that your model has an
entry in `_QUERY_INSTRUCTIONS` (`aiservice/main.py`) — without one, queries go out
without their instruction prefix, retrieval keeps working, and the answers are quietly
worse. The service logs a warning once per unknown model.

Switching the embedding model later invalidates every stored vector, and there is no
re-embedding tool. Choose once.

**Vision OCR**, as long as you keep `glm-ocr:Q8_0`. 1.6 GB, and it was chosen for German
and handwriting specifically.

## Context windows

`aiservice` sets a per-stage context window because Ollama's own default of 4096 would
truncate multi-page documents:

| Stage | Tokens |
|---|---|
| `extract` | 32,768 |
| `chat` | 16,384 |
| `vision`, `classify` | 8,192 |

Override per stage with `OLLAMA_<STAGE>_NUM_CTX`. **A model whose window is smaller than
the stage requests will silently process a truncated document** — the page with the
diagnoses on it simply never existed as far as the pipeline is concerned. Check your
model's context length before lowering these, and prefer a model with headroom: measured
at ~20,600 input tokens for an average document, a 32k window is comfortable and a 16k
one is not.

## Reasoning models: turn thinking off

Every qwen3 model here supports thinking, and the pipeline disables it for extraction,
classification and chat. This is not a tuning preference. Measured on `qwen3.6:27b` with
an identical prompt: **1175 tokens and 20.6s with thinking, 34 tokens and 1.0s without,
byte-identical answer.** On a long document, thinking consumes the context window before
the answer begins and the call returns empty.

If you configure a reasoning model the aiservice does not know about, this still applies —
the `think` flag is passed per call, not per model.

## Reproducing this

```bash
# from a deployment directory, against its own documents (read-only, decrypts
# through the app's code, writes nothing back into any patient record)
python3 scripts/ab-extract.py --from-db --limit 13 \
    --models qwen3.6:27b-mtp-q4_K_M qwen3:14b --language de
```

Results land in `ab-results/<document>/<model>.json` for diffing.

## Caveats

**Counting is not judging.** More extracted diagnoses can mean better recall or
duplication; the 9B's higher measurement count is the clearest case of a bigger number
being worse. The per-document JSONs have to be read, not just tallied.

**Size and generation are entangled here.** `qwen3:14b` is two generations older than
`qwen3.6:27b`, `qwen3.5:9b` one. Qwen ships no mid-size model in the newer generations —
3.5 exists at 9B and 397B, 3.6 starts at 27B — so the comparison cannot be made on size
alone. For choosing what to run this does not matter: you pick what fits your card.

**One corpus, one language.** 13 German documents from one Patient's care history, heavy
on pediatric neurology and insurer correspondence. Another domain may rank these models
differently.
