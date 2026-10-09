# Research: embedding model for German medical retrieval (replace `nomic-embed-text`?)

*Researched 2026-07-21 against primary sources (Ollama library pages, HuggingFace model cards,
the MTEB results repository at `embeddings-benchmark/results`, Qwen/Google/Snowflake/IBM release
materials, license texts, JMIR/Europe PMC). Context: chunk and query embeddings for German
medical letters, lab reports and diary notes (`backend/app/workers/pipeline.py`,
`backend/app/workers/scheduler.py`, `backend/app/routers/chat.py`), served through
`aiservice` `POST /embed` on an Ollama host, `Vector(768)` pgvector column, RTX 3090 24 GB,
AGPL-3.0 product hosted commercially.*

## 1. The hypothesis is correct: `nomic-embed-text` is an English-only model

The [nomic-embed-text-v1.5 model card](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)
carries exactly one language tag, `en`. There is no multilingual training claim anywhere on it.
Everything else follows from that.

Per-task German numbers, pulled from the raw MTEB result files in
[`embeddings-benchmark/results`](https://github.com/embeddings-benchmark/results) (nDCG@10, higher
is better):

| Model | GermanQuAD-Retrieval | LegalQuAD | GermanSTSBenchmark |
|---|---:|---:|---:|
| [`nomic-embed-text-v1.5`](https://github.com/embeddings-benchmark/results/tree/main/results/nomic-ai__nomic-embed-text-v1.5) | **75.93** | **9.01** | **65.33** |
| [`mxbai-embed-large-v1`](https://github.com/embeddings-benchmark/results/tree/main/results/mixedbread-ai__mxbai-embed-large-v1) | n/a | 16.40 | 63.50 |
| [`granite-embedding-278m-multilingual`](https://github.com/embeddings-benchmark/results/tree/main/results/ibm-granite__granite-embedding-278m-multilingual) | 91.28 | 36.76 | 82.08 |
| [`multilingual-e5-large`](https://github.com/embeddings-benchmark/results/tree/main/results/intfloat__multilingual-e5-large) | 94.66 | 43.17 | n/a |
| [`bge-m3`](https://github.com/embeddings-benchmark/results/tree/main/results/BAAI__bge-m3) | n/a | 50.36 | 80.79 |
| [`jina-embeddings-v3`](https://github.com/embeddings-benchmark/results/tree/main/results/jinaai__jina-embeddings-v3) | 95.46 | 59.35 | 87.51 |
| [`snowflake-arctic-embed-l-v2.0`](https://github.com/embeddings-benchmark/results/tree/main/results/Snowflake__snowflake-arctic-embed-l-v2.0) | 95.55 | 65.48 | 79.41 |
| [`Qwen3-Embedding-8B`](https://github.com/embeddings-benchmark/results/tree/main/results/Qwen__Qwen3-Embedding-8B) | n/a | 66.85 | 89.57 |

LegalQuAD is the closest public analogue to our workload (long, formal, jargon-heavy German
prose, short natural-language questions). **9.01 against 50 to 67 for every multilingual model**
is not a tuning gap, it is the model not representing German. GermanQuAD-Retrieval is easier
(Wikipedia-derived, high lexical overlap between question and passage) and there `nomic` still
loses ~20 points. GermanSTSBenchmark 65.33 against 80 to 90 says the same thing about sentence
semantics rather than retrieval specifically.

Two secondary observations that are consistent with this and worth fixing regardless:

- The prefixes are **mandatory**, not optional. The card states "the text prompt _must_ include a
  _task instruction prefix_" (`search_query:` for questions, `search_document:` for corpus text).
  The current code sends neither (`pipeline.py:227`, `chat.py:112`). The measured uniform shift
  when prefixes were added is the expected outcome: a prefix selects a projection of an already
  weak German space, it does not add German to it.
- The [Ollama library page for `nomic-embed-text`](https://ollama.com/library/nomic-embed-text)
  advertises a **2K context window**, not the 8192 the HF card describes. `_chunk_text` in
  `pipeline.py:260` cuts at 500 whitespace words, which for German medical prose is roughly
  700 to 1100 tokens, so we are under the cap, but with no margin, and Ollama's `truncate`
  defaults to `true`, so oversize chunks are silently cut rather than erroring.

## 2. The threshold experiment is also partly measuring the wrong thing

Two things are true at once. The model is genuinely bad at German (section 1). But the specific
experiment (four questions against 75 chunks, look for a distance that separates on-topic from
off-topic) cannot be settled by any embedding model, and one of the four probes is not the
control it looks like.

- **"Rezept für Apfelkuchen mit Zimt" is not an off-topic question in a German medical corpus.**
  *Rezept* is the ordinary German word for a doctor's prescription. A bag-of-concepts model that
  has any German at all will match it against medication and discharge text. The control probe
  shares its head noun with the corpus domain. "WM 1998" (0.526), which shares nothing, did rank
  last, so the *ordering* was actually correct in all four cases. What failed was the absolute
  scale, not the ranking.
- **Absolute cosine distances have a floor that is a property of the model, not of relevance.**
  Learned embedding spaces degenerate into a narrow cone
  ([Gao et al., "Representation Degeneration Problem in Training Natural Language Generation
  Models", ICLR 2019](https://arxiv.org/abs/1907.12009)), so unrelated texts still sit at
  moderate cosine similarity. [Steck et al., "Is Cosine-Similarity of Embeddings Really About
  Similarity?" (WWW 2024)](https://arxiv.org/abs/2403.05440) go further and show cosine similarity
  on learned embeddings "can yield arbitrary and therefore meaningless similarities", and warn
  against "blindly using cosine-similarity". A single global constant (`CHUNK_MAX_DISTANCE = 0.8`
  in `chat.py:34`) is precisely the pattern both papers argue against.
- Mean-centering making things worse is consistent with this: centering removes the shared
  component that carries the "this is German clinical text" signal, which is real signal for a
  patient-scoped corpus.
- The corpus is small and homogeneous. 75 chunks, all from one patient, all clinical German. With
  `CHUNK_LIMIT = 5` the query always retrieves 5 of 75, so the top-5 is close to a random sample
  of one narrow topic. A distance cutoff is being asked to do the job of a relevance classifier
  on a corpus where almost everything is nearly equally (ir)relevant.

So the honest framing: **a better model raises the ceiling and widens the gap, but it will not
hand you a stable absolute threshold.** ADR 038's "nothing found" guarantee needs a relative
criterion (gap between top-1 and the rest, or a margin against a fixed random-text probe) or a
cross-encoder reranker, not a hand-tuned constant. Note that Ollama still has no native
`/api/rerank`; the [rerank support PR](https://github.com/ollama/ollama/pull/7219) is open and
unmerged, so a reranker means a second serving path.

## 3. What is actually reachable through Ollama

The [official Ollama embedding library](https://ollama.com/search?c=embedding) is the constraint
that eliminates most of the candidate list:

| Candidate | Official Ollama tag | Size | Context | Verdict |
|---|---|---|---|---|
| Qwen3-Embedding | [`qwen3-embedding:0.6b` / `:4b` / `:8b`](https://ollama.com/library/qwen3-embedding) | 639 MB / 2.5 GB / 4.7 GB | 32K / 40K / 40K | available |
| EmbeddingGemma | [`embeddinggemma:300m`](https://ollama.com/library/embeddinggemma) | 622 MB | 2K | available |
| BGE-M3 | [`bge-m3:567m`](https://ollama.com/library/bge-m3/tags) | 1.2 GB | 8K | available |
| Arctic Embed 2.0 | [`snowflake-arctic-embed2:568m`](https://ollama.com/library/snowflake-arctic-embed2) | 1.2 GB | 8K | available (this is the `-l-v2.0` model) |
| granite-embedding multilingual | [`granite-embedding:278m`](https://ollama.com/library/granite-embedding) | 563 MB | **512** | available, context too short |
| mxbai-embed-large | [`mxbai-embed-large:335m`](https://ollama.com/library/mxbai-embed-large) | 670 MB | 512 | available, English-only |
| multilingual-e5-large / -instruct | **none** | | | not in the library; only community GGUF re-uploads |
| jina-embeddings-v3 / v4 | **none** | | | not in the library, and license-disqualified (section 5) |
| KaLM-Embedding-Gemma3-12B (MMTEB #1) | community only ([`KaLM-Embedding/KaLM-Embedding-Gemma3-12B-2511`](https://ollama.com/KaLM-Embedding/KaLM-Embedding-Gemma3-12B-2511)) | ~24 GB bf16 | 32K | license-disqualified (section 5) |
| Gemini Embedding 2 | n/a | | | closed API only ([Google announcement](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-embedding-2/)), not self-hostable |

The MMTEB state of the art as of mid-2026 is
[KaLM-Embedding-Gemma3-12B-2511 at 72.32 Mean (Task)](https://huggingface.co/tencent/KaLM-Embedding-Gemma3-12B-2511),
ahead of llama-embed-nemotron-8b (69.46) and Qwen3-Embedding-8B (70.58 with a worse Borda rank).
None of the three above Qwen3 are usable here (license or no Ollama build), so **Qwen3-Embedding
is effectively the ceiling available to this project.**

## 4. German numbers, including a German medical retrieval task

MTEB carries a set of held-out German tasks under `mteb-private`, one of which is directly on
domain: [`GermanHealthcare1Retrieval`](https://huggingface.co/datasets/mteb-private/GermanHealthcare1Retrieval-sample),
described by its own dataset card as "German medical consultation retrieval", domains "Medical,
Consultation". The siblings are
[`German1Retrieval`](https://huggingface.co/datasets/mteb-private/German1Retrieval-sample)
(Business, Conversation) and
[`GermanLegal1Retrieval`](https://huggingface.co/datasets/mteb-private/GermanLegal1Retrieval-sample)
(Education, Legal). Because the corpora are private, these numbers are contamination-resistant,
which makes them the most trustworthy German figures available. nDCG@10, from the results repo:

| Model | **GermanHealthcare1** | German1 | GermanLegal1 | LegalQuAD |
|---|---:|---:|---:|---:|
| Qwen3-Embedding-8B | **87.62** | 96.97 | 69.77 | 66.85 |
| Qwen3-Embedding-4B | **84.80** | 96.52 | 70.47 | n/a |
| snowflake-arctic-embed-l-v2.0 | **77.62** | 94.09 | 69.89 | 65.48 |
| multilingual-e5-large-instruct | **74.24** | 95.77 | 64.10 | 51.25 |
| bge-m3 | **72.48** | 92.45 | 60.89 | 50.36 |
| Qwen3-Embedding-0.6B | **71.35** | 95.34 | 61.80 | n/a |
| mxbai-embed-large-v1 | **32.01** | 66.25 | 36.86 | 16.40 |
| nomic-embed-text-v1.5 | not evaluated | not evaluated | not evaluated | 9.01 |

The spread on the medical task is 71 to 88 among serious multilingual models, and mxbai (an
English model, like ours) collapses to 32. That 32 is the best available proxy for where
`nomic-embed-text` would land.

Two candidates have no German retrieval numbers in the repo and this is a genuine gap:

- **EmbeddingGemma** has only `GermanSTSBenchmark` **84.69**, which is better than bge-m3 (80.79)
  and arctic-l-v2.0 (79.41) and just under multilingual-e5-large-instruct (84.84). Its aggregate
  is [MTEB Multilingual v2 Mean (Task) 61.15](https://huggingface.co/google/embeddinggemma-300m),
  below Qwen3-Embedding-0.6B (64.34) and multilingual-e5-large-instruct (63.22), which is still
  remarkable for 300M parameters. No German medical retrieval evidence exists for it.
- **granite-embedding-278m-multilingual** publishes its own
  [MTEB German (4 tasks) average of 71.2](https://huggingface.co/ibm-granite/granite-embedding-278m-multilingual),
  but its LegalQuAD 36.76 and GermanQuAD 91.28 place it clearly below the leaders, and its 512
  token limit is disqualifying on its own (section 7).

## 5. Licenses: three of the strongest models are unusable commercially

| Model | License | Commercial hosting? |
|---|---|---|
| Qwen3-Embedding 0.6B/4B/8B | [Apache-2.0](https://huggingface.co/Qwen/Qwen3-Embedding-4B) | **Yes**, unconditionally |
| bge-m3 | [MIT](https://huggingface.co/BAAI/bge-m3) | **Yes** |
| snowflake-arctic-embed-l-v2.0 | [Apache-2.0](https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v2.0) | **Yes** |
| granite-embedding-278m-multilingual | [Apache-2.0](https://huggingface.co/ibm-granite/granite-embedding-278m-multilingual) | **Yes** |
| multilingual-e5-large(-instruct) | [MIT](https://huggingface.co/intfloat/multilingual-e5-large-instruct) | **Yes** (but no Ollama build) |
| nomic-embed-text-v1.5 / v2-moe | [Apache-2.0](https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe) | Yes |
| EmbeddingGemma | [Gemma Terms of Use](https://ai.google.dev/gemma/terms) | **Yes, with conditions.** The grant covers making Gemma "available as a hosted service via API, web access, or any other electronic or remote means"; you must pass the Gemma Prohibited Use Policy and the full Terms through to downstream recipients. Not OSI-open, but it does permit our deployment. |
| jina-embeddings-v3 | [CC-BY-NC-4.0](https://jina.ai/models/jina-embeddings-v3/) | **No.** Non-commercial; commercial use requires a separate agreement with Jina. Disqualified. |
| jina-embeddings-v4 | [Qwen Research License](https://huggingface.co/jinaai/jina-embeddings-v4) (derived from Qwen2.5-VL-3B) | **No.** Research and non-commercial only. Disqualified. |
| KaLM-Embedding-Gemma3-12B-2511 | `tencent-kalm-embedding-community`, and the model card metadata sets **`extra_gated_eu_disallowed: true`** ([card source](https://huggingface.co/tencent/KaLM-Embedding-Gemma3-12B-2511/raw/main/README.md)) | **No.** The current MMTEB leader explicitly excludes EU users. Disqualified for a German product. |

So the your-suspicion-confirmed item: **jina-embeddings-v3 is CC-BY-NC and jina-embeddings-v4 is
Qwen-Research, both disqualifying**, and the mid-2026 MMTEB leader is worse than that (EU-gated).

## 6. Dimensions: what each option costs against the `Vector(768)` column

Good news that changes the calculus: **Ollama's embed API now takes a `dimensions` parameter**,
documented as "Number of dimensions to generate embeddings for"
([docs.ollama.com/api/embed](https://docs.ollama.com/api/embed)). MRL truncation is therefore one
request field, not a client-side reimplementation. `aiservice/backend.py:239` currently calls
`client.embed(model=..., input=texts)` with no options, so this is a one-line change plus a config
knob.

| Model | Native dim | MRL support | Fits 768 without migration? |
|---|---:|---|---|
| EmbeddingGemma | **768** | 768 / 512 / 256 / 128 ([model card](https://huggingface.co/google/embeddinggemma-300m)) | **Yes, natively.** Zero risk, no `dimensions` needed. |
| Qwen3-Embedding-0.6B | 1024 | "user-defined output dimensions ranging from 32 to 1024" ([card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)) | **Yes**, 768 is inside the officially supported range |
| Qwen3-Embedding-4B | 2560 | 32 to 2560 ([card](https://huggingface.co/Qwen/Qwen3-Embedding-4B)) | **Yes** |
| Qwen3-Embedding-8B | 4096 | 32 to 4096 ([card](https://huggingface.co/Qwen/Qwen3-Embedding-8B)) | **Yes** |
| granite-embedding-278m-multilingual | **768** | none documented | Yes, natively |
| bge-m3 | 1024 | **none.** The [card](https://huggingface.co/BAAI/bge-m3) documents dense/sparse/ColBERT modes, not MRL | **No.** Requires an Alembic migration to `Vector(1024)` plus a full re-embed |
| snowflake-arctic-embed-l-v2.0 | 1024 | MRL, but the card is explicit: "**the MRL for this model is 256 dimensions**", with 1024 to 256 costing under 3 % ([card](https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v2.0)) | **No.** 768 is an untrained intermediate. You get 1024 or 256, both of which are migrations |
| nomic-embed-text-v2-moe | 768 | 768 to 256 ([card](https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe)) | Yes, but 512 token context and it is not the quality leader |

Arctic's MRL caveat is the important, easily-missed one: a model advertising "MRL" does not
imply *every* smaller dimension is trained. Snowflake trained one rung (256). Qwen and Google
document continuous / multi-rung ranges that include or land on 768.

The published MRL cost where it is measured: EmbeddingGemma loses 0.44 points going 768 to 512
and 1.47 going 768 to 256; Arctic loses 1.53 to 2.70 % relative going 1024 to 256 across
BEIR/MIRACL/CLEF. Truncating a 2560-dim Qwen3-4B vector to 768 is a bigger relative cut than any
of those and is **not separately benchmarked by Qwen**, which is the main open risk in the first
recommendation below.

## 7. Prefixes, instruction templates and context length

Exact strings, since getting these wrong silently costs 5 to 20 points:

| Model | Query side | Document side | Context |
|---|---|---|---|
| nomic-embed-text (current) | `search_query: {q}` | `search_document: {d}` | 8192 native, **2K as served by Ollama** |
| EmbeddingGemma | `task: search result \| query: {q}` | `title: none \| text: {d}` ([model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card)) | **2048** |
| Qwen3-Embedding | `Instruct: {task_description}\nQuery:{q}` | **none**, "No need to add instruction for retrieval documents" | 32K (0.6B) / 40K as served by Ollama (4B, 8B) |
| multilingual-e5-large-instruct | `Instruct: {task}\nQuery: {q}` | none | 512 |
| bge-m3 | **none**, "no longer requires adding instruction to the queries" | none | 8192 |
| snowflake-arctic-embed-l-v2.0 | `query: {q}` | none | 8192 |
| granite-embedding-278m-multilingual | none | none | **512** |

Qwen quantifies the instruction: omitting it costs "approximately 1% to 5%" of retrieval
performance, and the task description should be written in the user's language. For us that means
one German instruction string in `chat.py`, for example
`Instruct: Finde Abschnitte aus medizinischen Dokumenten, die die Frage beantworten\nQuery:`.

Context matters concretely: our chunks are 500 whitespace words. **granite (512 tokens) and
multilingual-e5 (512 tokens) would truncate roughly a third to a half of every chunk.**
EmbeddingGemma's 2048 fits, with margin. Qwen3 and bge-m3 and arctic are unconstrained at this
chunk size. There is also a latent inconsistency worth cleaning up: `backend/app/workers/pipeline.py`
chunks by whitespace words while `aiservice/chunking.py` chunks by tiktoken tokens, and only the
former is on the live path.

## 8. Medical-domain evidence

There is one directly relevant peer-reviewed study, on German hospital documents:

- **Rüther et al., "Improving Retrieval Augmented Generation for Health Care by Fine-Tuning
  Clinical Embedding Models", JMIR 2026;28:e82997**
  ([DOI 10.2196/82997](https://doi.org/10.2196/82997), open access via
  [Europe PMC PMC13016438](https://europepmc.org/articles/PMC13016438)). 400,000 clinical
  documents from a large German tertiary hospital, 163,840 patients, ~11M synthetic QA pairs.
  Information-retrieval result: the fine-tuned model reaches **mAP@100 0.27**, against
  **multilingual-e5-large 0.14** and **bge-m3 0.11**. The stated motivation is exactly our
  problem: existing models are "predominantly trained on publicly available English datasets,
  limiting their effectiveness in non-English health care settings" and "lack training on
  real-world clinical documents".

Read that carefully, because it cuts both ways. It is strong evidence that (a) German medical
retrieval is a real, distinct capability, and (b) **even the good off-the-shelf multilingual
models are weak in absolute terms on real clinical text** (mAP@100 0.11 to 0.14), and a
domain-tuned model roughly doubles them. It also happens to invert the MTEB ordering (bge-m3
below multilingual-e5-large), which is a useful reminder that leaderboard rank does not transfer
cleanly to this domain. The fine-tuned "miracle" models from that paper are not published under a
findable HuggingFace ID, so they are not a candidate today.

Beyond that: `GermanHealthcare1Retrieval` (section 4) is the only clean German medical retrieval
benchmark with per-model numbers, and none of the candidate vendors publish clinical evaluations
of their own.

## 9. Footprint on the embed host

The embed host currently holds `nomic-embed-text`, `minicpm-v` and `glm-ocr`. Embedding is
bursty (a batch per document in `embedding_stage`) plus one short query embed per chat turn, so
resident footprint matters more than throughput.

| Option | Weights | Notes |
|---|---:|---|
| `embeddinggemma:300m` | 622 MB | stays resident trivially; activations do not support fp16 (use bf16/fp32) per the model card |
| `qwen3-embedding:0.6b` | 639 MB | same class |
| `bge-m3:567m` | 1.2 GB | same class |
| `snowflake-arctic-embed2:568m` | 1.2 GB | same class |
| `qwen3-embedding:4b` | 2.5 GB | still comfortable next to `glm-ocr` (1.6 to 2.2 GB) on 24 GB, even with an 18 GB extraction model elsewhere |
| `qwen3-embedding:8b` | 4.7 GB | affordable today, but the quality delta over 4B on the German medical task is +2.8 points for +2.2 GB and roughly 2x latency |

None of these is a VRAM problem. This decision is not hardware-constrained.

## Recommendation

**Yes, change the model. `nomic-embed-text` is an English-only model doing German retrieval, and
that is a defect, not a tuning issue (LegalQuAD 9.01).** But fix the threshold separately, because
no model choice will fix it.

**First choice: `qwen3-embedding:4b` (2.5 GB), called with `dimensions: 768`.**
Best German medical retrieval number by a wide margin (GermanHealthcare1Retrieval **84.80** vs
77.62 arctic, 72.48 bge-m3, and ~32 for an English model like the one we run today), Apache-2.0
so commercial hosting is unconditional, 40K context as served by Ollama, and 768 sits inside the
officially documented MRL range (32 to 2560) so the `Vector(768)` column and its HNSW index
survive untouched. Query side needs the German instruct prefix; documents need nothing.

**Runner-up: `embeddinggemma:300m` (622 MB), native 768.**
Take this if you want the lowest-risk change: no `dimensions` parameter, no MRL truncation risk,
no migration, 300M parameters, and a German STS score (84.69) that beats bge-m3 and arctic. The
costs are real though: a 2048 token cap that leaves little headroom over our 500-word chunks, a
lower MMTEB aggregate (61.15) than even Qwen3-0.6B (64.34), **no German medical retrieval evidence
at all**, and the Gemma Terms of Use rather than a true open-source license (commercial hosting is
permitted, but you inherit pass-through obligations that Apache-2.0 does not impose).

**Rejected, and why, in one line each:** bge-m3 and snowflake-arctic-embed-l-v2.0 are both good
multilingual models but both force a `Vector(1024)` migration (bge-m3 has no MRL at all; arctic's
MRL is trained only at 256, so 768 is untrained); granite-embedding and multilingual-e5 truncate
our chunks at 512 tokens, and e5 has no official Ollama build anyway; mxbai-embed-large is English
like the incumbent; jina v3 (CC-BY-NC) and v4 (Qwen Research) are non-commercial;
KaLM-Embedding-Gemma3-12B leads MMTEB but ships with `extra_gated_eu_disallowed: true`.

**What to measure before committing, on the real 75-chunk corpus:**

1. **Re-run the same four probes** against `qwen3-embedding:4b` at `dimensions=768` and at native
   2560, with and without the German instruct prefix. The number that matters is not the absolute
   distance, it is the **gap between the genuine question and the "WM 1998" probe**, and whether
   768-truncation preserves it. Qwen does not benchmark 2560 to 768 truncation, so this is the one
   claim in the recommendation that is unverified by the sources.
2. **Replace "Rezept für Apfelkuchen mit Zimt" as the off-topic control.** *Rezept* is a German
   medical term; that probe is measuring lexical overlap, not off-topic-ness. Use something with
   no medical or German-administrative vocabulary at all, and add three or four more genuine
   questions so the on-topic side is not a sample of one.
3. **Measure recall@5, not distance.** Hand-label which of the 75 chunks actually answer each
   question and compare recall@5 between `nomic-embed-text` and the candidate. That is the number
   the JMIR study and MTEB both report, and it is the number that decides whether the chat answers
   improve.
4. **Then, separately, replace `CHUNK_MAX_DISTANCE`.** Both [Gao et al.](https://arxiv.org/abs/1907.12009)
   and [Steck et al.](https://arxiv.org/abs/2403.05440) argue a global absolute cosine cutoff is
   not a sound relevance test. Two cheap alternatives that do not need a reranker: (a) a relative
   rule, keep chunk *i* only if `distance_i <= distance_top1 * k`, so "nothing found" becomes
   "nothing stood out"; or (b) a per-request calibration probe, embed one fixed nonsense German
   sentence alongside the query and keep only chunks meaningfully closer than that floor. Both
   survive a model swap without recalibration, which the current constant does not
   (`chat.py:33` already anticipates this).
5. **If separation still is not clean after all of the above, the answer is a cross-encoder
   reranker, not another bi-encoder.** Ollama has no `/api/rerank` yet
   ([PR #7219](https://github.com/ollama/ollama/pull/7219) is open), so that is a second serving
   path and a separate decision.

**Migration cost either way:** none to the schema (both recommendations stay at 768), but every
existing chunk must be re-embedded. `embedding_scheduler` (`scheduler.py:14`) already re-enqueues
documents in batches, so clearing `document_chunks.embedding` (and the diary vectors written in
`diary_embedding_job`) is enough to trigger a full rebuild without an Alembic revision.
