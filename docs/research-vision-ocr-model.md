# Research: vision OCR model — keep `qwen3-vl:8b` or move on?

*Researched 2026-07-08 against primary sources (Ollama library pages, HuggingFace model cards,
Z.AI/Qwen/Google release materials, OmniDocBench). Context: vision OCR fallback for scanned German
medical letters and lab reports (`aiservice/vision_ocr.py`, `POST /ocr/vision`), Ollama backend,
24 GB GPU already ~18 GB occupied by the extraction model.*

## 1. The Qwen VL line moved on — Qwen3-VL is last-gen

- Qwen3-VL shipped October–November 2025 with OCR in 32 languages
  ([QwenLM/Qwen3-VL](https://github.com/QwenLM/Qwen3-VL),
  [tech report](https://arxiv.org/abs/2511.21631)). Our documented default `qwen3-vl:8b`
  (6.1 GB, [tags](https://ollama.com/library/qwen3-vl/tags)) is from that generation.
- **Qwen3.5 (~March 2026) replaced the separate -VL line entirely**: it is a *unified*
  vision-language family, early-fusion trained on multimodal tokens, "outperforms Qwen3-VL models
  across … visual understanding benchmarks", supports **201 languages**, in sizes 0.8B/2B/4B/9B/
  27B/35B/122B — all text+image
  ([ollama.com/library/qwen3.5](https://ollama.com/library/qwen3.5)).
- Size-for-size gains are large: **Qwen3.5-9B scores 87.7 on OmniDocBench v1.5** and "beats
  last-gen Qwen3-VL-30B on every vision benchmark at 1/3 the size"
  ([VentureBeat on the release](https://venturebeat.com/technology/alibabas-small-open-source-qwen3-5-9b-beats-openais-gpt-oss-120b-and-can-run));
  even **Qwen3.5-2B (OCRBench 85.4) beats Qwen3-VL-4B (80.8)** at half the size
  ([Qwen 3.5 analysis](https://blog.overshoot.ai/blog/qwen3.5-on-overshoot)).
- Ollama tags: `qwen3.5:9b` 6.6 GB, `qwen3.5:2b` 2.7 GB, `qwen3.5:4b` 3.4 GB.

So the honest status of `qwen3-vl:8b`: not bad, but superseded by its own vendor twice over
(`qwen3.5:9b` is a strict upgrade at the same footprint) — and it isn't even pulled on our host.

## 2. Dedicated OCR models: GLM-OCR is the current king, and we already have it

- **GLM-OCR** (Z.AI, ~Feb 2026, MIT license): **0.9B params**, encoder-decoder (CogViT encoder +
  GLM-0.5B decoder), **94.62 on OmniDocBench v1.5 — #1 overall**, beating Gemini 3 Pro and
  GPT-5.2 ([HF card](https://huggingface.co/zai-org/GLM-OCR),
  [repo](https://github.com/zai-org/GLM-OCR)). Officially supports **8 languages including
  German** (Chinese, English, French, Spanish, Russian, German, Japanese, Korean; strongest on
  zh/en) and explicitly handles **handwriting and noisy scans**
  ([Z.AI docs](https://docs.z.ai/guides/vlm/glm-ocr)). Official Ollama build:
  `glm-ocr:latest` 2.2 GB / `glm-ocr:q8_0` 1.6 GB, 128K context
  ([ollama.com/library/glm-ocr](https://ollama.com/library/glm-ocr)). Throughput ~1.9 PDF
  pages/s (HF card). **Already pulled on our Ollama host (`glm-ocr:Q8_0`).**
- **PaddleOCR-VL-1.6** self-reports 96.33 on OmniDocBench v1.6 — but that's vendor-reported, not
  independently reproduced, and it has no official Ollama build
  ([Instavar leaderboard roundup](https://instavar.com/blog/ai-production-stack/OCR_SOTA_Feb_2026_Open_Document_AI_Leaderboard)).
- **DeepSeek-OCR** (`deepseek-ocr:3b`, 6.7 GB, 8K context) is on Ollama
  ([library page](https://ollama.com/library/deepseek-ocr)) but is optimized for token-efficient
  compression, not peak accuracy (75.7 on olmOCR-bench per Instavar); **DeepSeek-OCR 2**
  ([paper](https://arxiv.org/pdf/2601.20552)) has no official Ollama build yet.
- **Chandra (83.1)** and **olmOCR-2 (82.4)** lead the English-centric olmOCR-bench but are 7–8B
  and slow (1.3–1.8 pages/s) — no accuracy case over GLM-OCR at 8× the size (Instavar).
- Caveat on the benchmark itself: OmniDocBench is considered **saturated** (top models > 94 %,
  1,355 pages, 9 doc types, academic-paper-heavy, little handwriting/forms coverage) — scores
  above ~90 are "edge-case fixing", so private evals on our own documents matter more
  ([LlamaIndex analysis](https://www.llamaindex.ai/blog/omnidocbench-is-saturated-what-s-next-for-ocr-benchmarks)).
  OmniDocBench moved to v1.7 in April 2026.

## 3. Gemma 4 as OCR: real capability, measurably behind dedicated models

- The [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4) confirms 26B A4B
  is fully multimodal (~550M vision encoder) and lists "Document/PDF parsing … OCR (including
  multilingual), handwriting recognition" as supported tasks.
- First-party OmniDocBench 1.5 numbers (**edit distance, lower = better**): 31B **0.131**,
  26B A4B **0.149**, 12B 0.164. Dedicated OCR models sit far below that (GLM-OCR's 94.6 composite
  corresponds to edit distances roughly half those). Gemma 4 is a competent generalist reader,
  not an OCR specialist.
- The consolidation appeal is real though: if `gemma4:26b` wins the extraction A/B
  (docs/research-extraction-model.md), it is *already resident* — vision OCR through it costs
  **zero extra VRAM and zero model swap**, at ~4 B active params per token.

## 4. German + medical fit

- German is officially covered by all three finalists: GLM-OCR (8 official languages), Qwen3.5
  (201 languages), Gemma 4 (140+ languages, multilingual OCR). German is Latin-script, i.e. in
  every model's strongest regime.
- Handwriting (doctor notes): explicitly claimed by GLM-OCR (Z.AI docs) and Gemma 4 (model card);
  Qwen3-VL claims robustness to blur/tilt/rare characters but not handwriting specifically.
- None publish medical-document evals; all claims need checking on our own letters.

## 5. VRAM reality: 24 GB today, 96 GB mid-term

**Today (RTX 3090, 24 GB, ~18 GB taken by extraction):**

| Candidate | Weights | Fits *alongside* extraction? |
|---|---|---|
| `glm-ocr:q8_0` | 1.6 GB | **Yes** (~20 GB total, room for KV) |
| `glm-ocr:latest` (bf16) | 2.2 GB | Yes |
| `qwen3.5:2b` | 2.7 GB | Yes, marginal |
| `qwen3.5:9b` | 6.6 GB | No — forces Ollama model swap per OCR call |
| `qwen3-vl:8b` (current default) | 6.1 GB | No — same swap penalty |
| `gemma4:26b` (consolidated) | 0 extra | Trivially — it *is* the extraction model |

Multi-page scanned PDFs are OCR'd page-by-page (`vision_ocr.py`), so a default that evicts and
reloads an 18 GB model around each OCR batch is a real latency tax. A 1.6 GB resident specialist
avoids it entirely.

**Mid-term (planned RTX PRO 6000 Blackwell, 96 GB):** the constraint inverts — everything below
~70 GB of combined weights coexists with room for long KV caches. Options that open up
(sizes from [ollama.com/library/qwen3.5](https://ollama.com/library/qwen3.5) and
[gemma4 tags](https://ollama.com/library/gemma4/tags)):

| Combo | Weights | Notes |
|---|---|---|
| `gemma4:31b-it-q8_0` (34 GB) + `glm-ocr:latest` (2.2 GB) | ~36 GB | best-quant extraction + specialist OCR, both resident |
| `gemma4:31b-it-q8_0` + `qwen3.5:35b` (24 GB) | ~58 GB | adds a strong general VLM for hard pages/figures |
| `qwen3.5:122b` (81 GB) alone | 81 GB | single unified model for extraction *and* OCR; tight, little KV headroom |

## Recommendation

**(a) Today, on the 24 GB card: change the default `qwen3-vl:8b` → `glm-ocr:q8_0`** (1.6 GB;
`glm-ocr:latest` at 2.2 GB where VRAM allows). It is #1 on OmniDocBench v1.5 (94.62) beating
frontier models, officially supports German and handwriting, is MIT-licensed, and stays resident
next to the 18 GB extraction model with no swap penalty — and it's already pulled on our host.
`qwen3-vl:8b` is superseded within its own vendor line and isn't even installed.

**(b) On the 96 GB Blackwell box: keep `glm-ocr` as the OCR default and pair it with a bigger
resident stack** — `gemma4:31b-it-q8_0` for extraction plus `glm-ocr:latest`, optionally adding
`qwen3.5:35b` as a general-VLM escalation path for pages the specialist garbles (figures,
mixed-layout letters). A specialist OCR model doesn't stop being the right tool because VRAM got
cheap; what the 96 GB buys is *no compromises elsewhere* (q8 extraction, long context, all models
loaded). The one-model alternative — `qwen3.5:122b` (81 GB) doing extraction *and* OCR — is
elegant but leaves <15 GB for KV cache and ties every pipeline stage to one model's failure
modes; only worth it if A/Bs show it beating the specialist stack on our documents.

- **README "Model Options" table:** promote `glm-ocr` to **Default — document image OCR** and
  replace the `qwen3-vl:8b` row with **`qwen3.5:9b`** (6.6 GB, 201 languages, OmniDocBench 87.7)
  as the general-VLM alternative for hosts with spare VRAM; drop `qwen3-vl` from the pull list.
  `aiservice/models.json` already has `glm` and `gemma4` vision patterns; retire the `qwen3-vl`
  pattern in favour of a `qwen3.5` one when the README changes.
- **Integration caveat:** GLM-OCR's Ollama build expects task-style prompts
  (`Text Recognition:` / `Table Recognition:` — [library page](https://ollama.com/library/glm-ocr)),
  not the free-form `VISION_OCR_PROMPT` in `vision_ocr.py`. Verify output quality with the
  current prompt and add a per-model prompt override if transcription degrades.
- **Yes, A/B gemma4-as-OCR alongside:** `/ocr/vision` takes a `model` param, so running the same
  ~10 scanned pages through `glm-ocr:q8_0`, `gemma4:26b`, and (as baseline) `minicpm-v` is a
  20-minute job next to the extraction A/B (`scripts/ab-extract.py`). Expect GLM-OCR to win on
  fidelity per Google's own edit-distance numbers — but if gemma4's transcription is *good
  enough* on our real letters, one-model consolidation is the simplest possible ops story and a
  legitimate outcome.

## Addendum (2026-07-08, same day)

Qwen3.6 shipped after the Qwen3.5 research above: multimodal, 256K context, but only 27b (17 GB)
and 35b (24 GB) — no small size — with an agentic-coding focus and no published OCR/document
benchmarks ([ollama.com/library/qwen3.6](https://ollama.com/library/qwen3.6)). It does not change
the recommendation: `glm-ocr` stays the OCR default; `qwen3.5:9b` remains the small general-VLM
alternative. On the 96 GB target, `qwen3.6:35b` replaces `qwen3.5:35b` as the escalation VLM.
