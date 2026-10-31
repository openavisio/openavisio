# System One models for OpenAvisio

Research note, 31 Oct 2026. Question: would fast "System One" models (models that return a typed decision, a choice from fixed options, a score, or yes/no with a probability, instead of generated text) make sense for some of OpenAvisio's AI tasks, and for which ones.

Constraints taken as given: hosted instances run all AI at the IONOS AI Model Hub (Germany, AVV in place), no US processor sees patient data, self-hosters run Ollama or vLLM, the operator decides where AI runs (ADR 050) and picks models in the admin UI (ADR 005). Jev is the reference point only.

## Short answer

- **No System One product fits today.** Jev is US and API-only. The open-weight decision models that appeared after it (Kev-4B, GLiNER2.5-Decide, Perplexity's pplx-decider) are served by custom code that neither Ollama nor vLLM runs, and none is in the IONOS catalog. English-only training is not the obstacle: measured on German questions, Kev-4B ranked them mostly right, but the configured 27B separated them cleanly where Kev did not (section 6).
- **The idea is still usable without a new model.** A typed decision can be read off the model already deployed: constrain the answer to one token per option and read the probability from logprobs. Ollama, vLLM and (per its docs) IONOS all expose logprobs. That works under ADR 005 and ADR 050 with no new dependency, and gives a real probability instead of the verbalized `confidence` the classification prompt asks for today.
- **Two decision points would gain:** the two keyword filters in the chat, `_is_emergency` and `_strip_judgement` (`backend/app/routers/chat.py`). Both are regexes that, as probed below, miss paraphrases and also hit sentences they should let through. A third, the chat's source list, could gain from a reranker, which is a System One model in all but name and is in the IONOS catalog.
- **The pipeline stages would not gain much.** Classification runs once per Document in a background job whose cost and time are dominated by OCR and extraction. Swapping its model saves seconds nobody waits for. The worthwhile change there is smaller: stop asking the model for a confidence number and either read a real one or drop it.
- **First experiment, done:** emergency-question detection by a one-token yes/no call on the configured chat model, on a synthetic German question set (no patient data). It caught all 40 emergencies with no false alarm, where the regex missed 24 (section 6).

## 1. What a System One model is

TypeSafe AI launched Jev on 15 Sep 2026 as "the first of what it calls System One Models". Callers send a state plus typed questions; Jev answers all of them in one parallel pass with three types, Choice, Score and Noul (yes/no), each with a probability distribution and a confidence ([InfoQ](https://infoq.com/news/2026/10/typesafe-ai-jev-released)).

Vendor-claimed, not independently verified: 70 to 500 ms end to end, $0.042 per million input tokens, output free, 32k context, training by "Reinforcement Learning for Calibrated Decisions", calibrated probabilities. TypeSafe's own "jaggedness" page lists counting, arithmetic and date comparison as weak spots and advises keeping math in code. Critics note that "cannot emit an invalid type" is a claim about format, not correctness: a well-formed answer can still be wrong (InfoQ, quoting Hacker News and Armin Ronacher).

The first independent benchmark, TypedBench ([arXiv 2610.11392](https://arxiv.org/abs/2610.11392)), evaluates a hosted typed decision model, an open encoder and open decoders from 0.8B to 9B on identical items. Its findings: the hosted model "follows the stated policy but is wording-sensitive and systematically underconfident", and under asymmetric costs using its probabilities "can be worse than taking its top answer"; decoders route exactly but get slower and less accurate as options grow. Its conclusion is that such models must be judged on policy adherence, wording robustness, probability quality and the decisions they cause, not on accuracy alone. That is the bar any experiment here should use.

## 2. Who does what today

| Stage | Self-hosted default (`aiservice/backend.py:19-25`) | Hosted (`deploy/hosted/provision.sh:89-91`) |
|---|---|---|
| OCR (vision) | `glm-ocr:Q8_0`, Tesseract fallback | `lightonai/LightOnOCR-2-1B` |
| Classify | `qwen3.6:27b-mtp-q4_K_M` | `Qwen/Qwen3.8-27B` |
| Extract | same 27B | same 27B |
| Chat | same 27B | same 27B |
| Embed | `qwen3-embedding:4b` | `Qwen/Qwen3-VL-Embedding-8B` |

Every text decision in the pipeline and the chat is made by one 27B generative model with thinking switched off, or by a regex. Model choice per stage is the admin's (ADR 005); the URL is the operator's (ADR 050).

## 3. Decision points

"Typed" means the answer is a closed set. "Per" is how often it runs. Line numbers are as of commit 523aee8.

| # | Decision | Where | Today | Per | Cost of a wrong answer |
|---|---|---|---|---|---|
| D1 | Document type (12 labels) | `aiservice/classification.py:30-56`, `prompts/classification.md`, stored in `backend/app/workers/pipeline.py:150-158` | 27B LLM, free JSON, verbalized `confidence` | Document | Steers extraction. `lab_report` drops all diagnoses and medications, `questionnaire` drops all clinical data (`aiservice/extraction.py:159-164, 222-234`). A doctor's letter typed as a lab report silently loses its diagnoses before verification; a lab report typed as a letter reopens the fabricated-diagnosis path the drop was built to close. |
| D2 | Is this a Bescheid with a Rechtsbehelfsbelehrung (yes/no) | Inside the extraction prompt (`prompts/extraction.md`, "decision" null or object), used at `pipeline.py:205-216` and `backend/app/routers/documents.py:471` | 27B LLM, part of the big JSON | Document | False negative: no Widerspruch deadline, the harm ADR 041 exists to prevent. Also decided a second time, independently, by D1's `insurance_decision` label; the two can disagree. |
| D3 | Diagnosis assertion (present, suspected, family, absent) | `prompts/extraction.md`, filtered at `extraction.py:169, 249-259` | 27B LLM, field in the JSON | Diagnosis | A relative's or ruled-out condition enters the Patient's record (after verification). |
| D4 | Expense category (6 labels), is-invoice | `prompts/extraction.md` | 27B LLM, field in the JSON | Expense | Wrong bucket in the expense overview; low. |
| D5 | Appointment past or future | `prompts/extraction.md` (`is_future`), shown at `frontend/.../verify/VerifyForm.tsx:448` | 27B LLM | Appointment | Wrong badge on the verification screen. This is a date comparison, which code does exactly and models do worst (Jev's own jaggedness list, Kev-4B's 0.65 on date arithmetic below). Not a model task at all. |
| D6 | Intake question kind (fact, judgement) and aging (3 labels) | `aiservice/intake.py:38-54`, `prompts/intake_questions.md`, defaults at `backend/app/services/intake.py:90-93` | 27B LLM, per item in one JSON | Form question | A judgement taken as a fact gets answered from the record (still only with a real source, `intake.py:76-82`). The default "in doubt, judgement" makes the other error the safe one. |
| D7 | Is the chat question an emergency question | `backend/app/routers/chat.py:139-154`, called at 422 | Regex | Chat question | False negative: the 27B model answers it (the prompt tells it not to, a second layer). False positive: a history question gets the fixed pointer instead of an answer. |
| D8 | Does an answer line grade a value or advise | `chat.py:113-137, 164-184` | Regex, line-wise | Chat answer line | False negative: a clinical judgement reaches a lay caregiver, which is the MDR line (`docs/regulatory-positioning.md`). False positive: a correct line is cut. The code's own comment names the upgrade, "a second model call, which costs another 40s per answer on this hardware". |
| D9 | Is the question about the Patient at all | `prompts/chat_system.md` | The chat model declines itself | Chat question | ADR 038 rejected a router on failure mode (a false negative looks like a fact); ADR 057 measured that the model declines correctly. |
| D10 | Is a retrieved chunk relevant (source list) | `chat.py:53, 365-390`, `CHUNK_MAX_DISTANCE = 0.59` | Cosine distance cutoff | Chat question x 5 chunks | ADR 057: filters nothing with `Qwen3-VL-Embedding-8B`; "Durchsuchte Dokumente" lists unrelated letters. |
| D11 | OCR route: table page or prose page | `aiservice/vision_ocr.py:48`, `aiservice/page_analysis.py:83-94` | Pixel heuristic | Page | A table read as prose loses column alignment (ADR 028). Cheap and model-free; not a candidate. |
| D12 | Vision OCR empty, fall back to Tesseract | `aiservice/main.py:177-202` | Empty-string check | Document | Not a judgement call. |

Two probes of the chat regexes, run locally against the compiled patterns (no server, no data):

- D7 flags "Seit wann bekommt sie Diazepam?" and "Wann wurde Midazolam zuletzt verschrieben?" as emergencies (the rescue-medication names match unconditionally), and misses "Sie krampft seit fünf Minuten und reagiert nicht", "Er läuft blau an, was jetzt?" and "Muss ich den Rettungswagen holen?".
- D8 strips "Im Arztbrief vom 03.02.2026 steht als Empfehlung: Kontrolle in sechs Wochen (Dr. Meier)." and "Der Befund vom 14.01. lautet laut Radiologie: unauffällig.", both attributed quotes that `chat_system.md` explicitly allows, and lets through "Die Werte sind alle prima.", "Das sieht gut aus, kein Grund zur Sorge." and "Der Kaliumwert ist höher als beim letzten Mal.".

Both are the failure the `ponytail:` comments predicted. They are exactly the shape a typed decision model is for: short input, one yes/no, a threshold, an asymmetric cost.

## 4. Options that satisfy the constraints

### 4.1 Open-weight "System One" models

| Model | What it is | Fit |
|---|---|---|
| **Kev-4B** ([card](https://huggingface.co/jaredpalmer/kev-4b)) | LoRA plus pointer head on frozen Qwen3.5-4B-Base, prefill-only, one forward pass, returns a probability per option; temperature-calibrated (T = 2.41). Apache 2.0. Implements TypeSafe's `/v1/systemone` API. | Trained on English only, yet usable on German questions (section 6). bf16 on CUDA (about 14.3 GB) or MLX; not an Ollama or vLLM model, custom server. Self-reported: ECE 0.029 on its own test set but 0.084 to 0.101 on trained document families; date arithmetic 0.65 (Jev 0.95); trails Jev on held-out sets. |
| **GLiNER2.5-multi-Decide** ([card](https://huggingface.co/fastino/GLiNER2.5-multi-Decide)) | 287M encoder (mDeBERTa-v3-base), labels given at call time, runs on CPU via the `gliner2` library. Apache 2.0. | "Multilingual" but German not named, benchmark suite English only, 56.7% on the vendor's own suite. The card does not describe per-label probabilities or calibration. Runs beside Ollama, not inside it, so a self-hoster gets one more service. In Parallel's test the English sibling scored 23.5 AUPRC where Jev scored 87.9 on one task ([Parallel](https://parallel.ai/blog/are-all-system-one-models-created-equal)). |
| **pplx-decider v1.2** ([card](https://huggingface.co/perplexity-ai/pplx-decider-v1.2)) | Qwen3.8-27B fine-tune with noncausal attention and per-marker readout; choice, score and yes/no with probabilities. Apache 2.0. | **Private repository** (token access), custom `pplx_decider` package, "a serving system needs both the noncausal attention and the per-marker readout", so no vLLM, no Ollama, no IONOS. About 52 GiB BF16. Self-reported dev ECE 0.014, held-out about 0.05, "somewhat over-confident". |

Others named in blogs (JevK5, Rune 26B, Bespoke Nimble 9B, NeoHorse) have no primary source beyond their own pages and were not assessed. Parallel's own conclusion was that closed and larger models did better and that "self-hosting open models can erase their cost and latency advantages".

**Verdict:** none of these is deployable here without a custom inference server next to vLLM or Ollama. Kev-4B was measured on German and works, but less sharply than the model already configured (section 6). Revisit when one ships as a standard Ollama or vLLM model, or appears at IONOS.

### 4.2 Logprob choice scoring on the model already configured

The mechanism behind every decision model above can be approximated with the generative model OpenAvisio already runs: ask for exactly one token out of a fixed set ("ja"/"nein", or "A".."L" for twelve document types), request logprobs, and normalize the probabilities of the allowed tokens. Qwen3-Reranker computes its score exactly this way, as the softmax of the "yes" and "no" logits at the last position ([card](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)).

Availability on the three paths:

- **Ollama:** `/api/chat` takes `logprobs` (boolean) and `top_logprobs` (integer) ([docs](https://docs.ollama.com/api/chat)). The installed Ollama version and the `ollama` Python client version must be checked; older ones lacked it.
- **vLLM:** OpenAI-compatible `logprobs`/`top_logprobs`, and the choice can be enforced with `extra_body={"structured_outputs": {"choice": [...]}}` (`guided_choice` was removed in v0.12.0) ([docs](https://docs.vllm.ai/en/latest/features/structured_outputs.html)).
- **IONOS:** the text generation how-to documents `top_logprobs` with a range of 0 to 20 ([docs](https://docs.ionos.com/cloud/ai/ai-model-hub/how-tos/text-generation.md)). It does not document `response_format`, `json_schema` or a choice constraint, so the one-token answer must come from the prompt, and whether logprobs actually come back through the own proxy (ADR 056) is untested.

What it buys: a probability you can threshold, from the model the admin picked, with no new service. What it does not buy: speed comparable to Jev. A one-token answer on a 27B model still pays the full prefill and the queue; it removes the decode time (most of the 20 s chat answer), not the model load. The probabilities are raw, not calibrated; a threshold has to be set per model on a labeled set, the same "model change is a recalibration" rule ADR 038 states for the distance cutoff. Thinking must stay off, which the backends already do (`think=False`, `reasoning_effort: "none"`).

A smaller model at IONOS makes this cheaper: **Qwen3.5-9B** is in the catalog (Apache 2.0, 262k context, reasoning switchable with `reasoning_effort: "none"`, [model page](https://docs.ionos.com/cloud/ai/ai-model-hub/models/llms/qwen3-5-9b.md)) at 0.10 EUR input and 0.15 EUR output per million tokens ([price list](https://docs.ionos.com/support/general-information/price-list/ionos-cloud-eur-en)), and the same open weights run in Ollama for self-hosters. The Qwen3.8-27B price was not found in the list.

### 4.3 Constrained decoding (schema, not probability)

Not System One, but the cheap reliability half of it: Ollama's `format` accepts a JSON schema ([docs](https://docs.ollama.com/api/chat)) and vLLM accepts `response_format` with `json_schema` ([docs](https://docs.vllm.ai/en/latest/features/structured_outputs.html)). An enum on `document_type` would make D1 return only valid labels and would remove the "retry once on bad JSON" path in classification, extraction and intake. IONOS does not document it, so the hosted path would keep the retry. This improves format, not correctness, and gives no probability.

### 4.4 Rerankers as yes/no scorers

A cross-encoder reranker answers "is this passage relevant to this question" with a score, which is a typed decision. **IONOS hosts `Qwen/Qwen3-VL-Reranker-8B`** at `POST /v1/rerank`, returning a `relevance_score` between 0 and 1 per document, 32k context, Apache 2.0 ([model page](https://docs.ionos.com/cloud/ai/ai-model-hub/models/reranking-models/qwen3-vl-reranker-8b.md), [how-to](https://docs.ionos.com/cloud/ai/ai-model-hub/how-tos/reranking.md)). Self-hosters can run the open `Qwen3-Reranker` 0.6B, 4B or 8B (100+ languages, Apache 2.0); Ollama has no rerank endpoint, so either vLLM or the logprob trick from 4.2 on the reranker prompt.

This is the one place where a typed model directly attacks a measured problem: ADR 057 showed that cosine distance cannot separate relevant from irrelevant chunks for either embedding model. A cross-encoder sees question and chunk together, which is why it can separate what a distance cannot. Whether it does on this corpus is unmeasured. ADR 038's warning stands: use it only for the source list, never to drop chunks from the context, or it produces the confident false negative ADR 038 calls the worst outcome.

### 4.5 Small encoder classifiers

- **Embedding plus logistic regression** on the existing `/embed` call: milliseconds, calibratable with standard methods, no new model. But it must be retrained whenever the operator changes the embedding model (hosted and self-hosted already differ), and it needs labeled examples. Labeling real chat answers or documents means reading health data, so the training set would have to be synthetic.
- **SetFit** (contrastive fine-tune of a sentence transformer plus a head, few labeled pairs, multilingual by swapping the body, [arXiv 2209.11055](https://arxiv.org/abs/2209.11055)) and multilingual encoders such as **mmBERT** (1800+ languages, [arXiv 2509.06888](https://arxiv.org/abs/2509.06888)) are the standard route to a fast fine-tuned classifier. Both mean shipping a model OpenAvisio owns, outside the admin's model list, which ADR 005 deliberately avoids, and an artifact that a self-hoster cannot pick or audit like the others.

These are the fastest options and the worst fit for the configuration model. Worth it only if a decision point turns out to need millisecond latency at volume, which none does today.

### 4.6 The IONOS catalog in short (checked 31 Oct 2026)

LLMs: Qwen3.5 9B, Mistral Small 24B, Qwen3.8 27B, Llama 3.3 70B, GPT-OSS 120B, Qwen3.5 397B A17B ([LLMs](https://docs.ionos.com/cloud/ai/ai-model-hub/models/llms.md)). Embeddings: BGE M3 (1024 dims), Paraphrase Multilingual MPNet v2 (768 dims, retiring 30 Nov 2026), Qwen3-VL-Embedding-8B (4096 dims) ([embeddings](https://docs.ionos.com/cloud/ai/ai-model-hub/models/embedding-models.md)). Reranker: Qwen3-VL-Reranker-8B. No classifier or decision model, and no documented structured-output parameter ([models](https://docs.ionos.com/cloud/ai/ai-model-hub/models.md)).

### 4.7 About the "confidence" OpenAvisio asks for today

`classification.md` asks the model for `"confidence": 0.0 to 1.0`. A number a model writes is not a probability; verbalized confidence is systematically overconfident ([Xiong et al., arXiv 2306.13063](https://arxiv.org/abs/2306.13063)). The pipeline already discards it (`pipeline.py:150-158`), in line with #111's rule that a fake number is worse than none. A logprob-derived probability is the honest replacement if a "please check the type" hint is ever wanted on the verification screen.

## 5. Recommendation

| Decision | Gain from a typed model | Why |
|---|---|---|
| D7 emergency question | **Yes, first** | Regex misses paraphrases and hits history questions about rescue drugs. One short input, yes/no, asymmetric cost. OR-ing a model's "yes" with the regex can only add recall, so the safety floor does not drop. |
| D8 judgement lines | **Yes, second** | Same shape, larger effect: both false negatives (MDR exposure) and false positives (allowed quotes cut). A one-token call per line, batched, costs far less than the 40 s second answer the comment rejected. Harder than D7: an OR would cut more lines, so it needs a real threshold and a set that includes attributed quotes. |
| D10 source relevance | **Maybe**, as an experiment | Reranker at IONOS and as open weights. Directly addresses the ADR 057 measurement. Source list only. |
| D1 document type | **Small** | Background job, extraction dominates the time. Enum-constrained output (4.3) and a logprob probability (4.7) are the useful parts; a dedicated model is not. |
| D2 Rechtsbehelfsbelehrung | **Not as a model swap** | High stakes, but the evidence sits in one paragraph the 27B model already reads. The cheaper fix is to stop deciding it twice (D1 label vs D2 object). A logprob yes/no would let a low-probability "no" ask the User to confirm. |
| D3, D4, D6 | **No** | Fields inside one extraction or intake call; splitting them into separate calls multiplies calls for little gain. D6 already defaults to the safe side. |
| D5 past/future | **No model at all** | It is a date comparison; do it in code against the document date or today. |
| D9 off-topic | **No** | ADR 038 rejected a router on failure mode, ADR 057 measured that the model declines correctly. Do not re-add it as a gate. |
| D11, D12 | **No** | Model-free and adequate. |

Is it worth it now? For the pipeline, no. For the two chat filters, yes, but as "a one-token typed call on the configured model", not as a System One product. No candidate product satisfies the constraints, and the measured independent evidence (TypedBench, Parallel) says the probabilities need per-model checking anyway.

### Cheapest first experiment

1. Build a labeled German question set for D7, synthetic, no patient data: the 13 cases in `backend/tests/test_chat_fhir_emergency_plan.py:103-116`, the five probes above, and 50 to 100 more written by hand (action questions with and without keywords, history questions mentioning Anfall, Notfall, Buccolam, Diazepam).
2. Score each with one call: a short German system prompt ("Fragt diese Frage, was jetzt im Notfall zu tun ist? Antworte nur mit ja oder nein."), `think=False`, `max_tokens=1`, `logprobs` on, P(ja) = softmax over the "ja" and "nein" logprobs. Run it on the homelab Ollama with the default 27B and with Qwen3.5-9B.
3. Report per model: recall and false positives of regex alone, model alone, regex OR model at a few thresholds; median latency of the call.
4. Ship only if regex OR model at one threshold catches the paraphrases without flagging the history questions, and the call adds well under a second. If Ollama's logprobs do not come back, the same experiment with a plain one-word answer still measures accuracy; the probability is then the missing part.

No IONOS call is needed for the first run. Whether `top_logprobs` survive the own proxy (ADR 056) is the one hosted check before shipping.

## 6. Measured: emergency detection (31 Oct 2026)

The experiment above, run on homeai: 80 synthetic German and English questions, 40 asking what to do in an acute emergency, for the Emergency Plan or a rescue dose, and 40 history and record questions, many with the same keywords ("Seit wann bekommt sie Diazepam?"). Set in `scripts/emergency-questions.json`, harness `scripts/bench-emergency.py`. No patient data.

| Method | Missed emergencies | False alarms | Per question |
|---|---|---|---|
| `_is_emergency` regex today | 24 / 40 | 9 / 40 | 0 ms |
| Kev-4B, P(yes) >= 0.3 | 7 / 40 | 0 / 40 | 58 ms |
| regex OR Kev-4B at 0.3 | 2 / 40 | 9 / 40 | 58 ms |
| **Qwen3.8-27B one-token ja/nein, P(ja) >= 0.3** | **0 / 40** | **0 / 40** | 104 ms |

- **Qwen3.8-27B** (vLLM, fp8, TP=2, thinking off, `max_tokens: 1`, `top_logprobs: 10`, German system prompt in the harness): every history question scored 0.03 or less, every emergency question 0.32 or more. The lowest emergencies are questions about the plan ("Was steht im Notfallplan?" 0.32, "Ab wann muss ich das Nasenspray geben?" 0.32), so 0.5 would miss seven; the threshold is 0.3.
- **Kev-4B** (`kev.serve` on one 3090, without the fused kernels, English instruction, German question as state): no false alarm, but the two classes touch ("Was mache ich im Notfall?" 0.29, "Wann wurde das Notfallmedikament zuletzt nachbestellt?" 0.28), and it missed plan questions ("Was steht im Notfallplan?" 0.19). A German-tuned instruction might move this; not tried.
- **Tokenisation trap:** Qwen emits "nein" as "ne" + "in". Matching whole words only counts every answer as yes; the harness counts any prefix of "nein".
- **Limits:** 80 hand-written questions, not real chats; one run each; measured on the homelab vLLM, not at IONOS or through the own proxy.

**At IONOS** (same model, same prompt, through the aiservice on the calibration box): logprobs came back for all 80 questions, 388 ms per question. The spread is narrower: history questions up to 0.11, emergencies from 0.26, so 0.3 misses two ("Was steht im Notfallplan?", "Wie lege ich sie in die stabile Seitenlage?") and 0.2 separates both runs without error. The own proxy (ADR 056) forwards request and response bytes unchanged.

Conclusion: the configured chat model, asked one ja/nein token with its probability, replaces the regex for D7 without a second service. Kev-4B is not worth running beside it. Before shipping: check that `top_logprobs` come back through IONOS and the proxy, and keep the regex as the fallback when the call fails.

## Side findings (not fixed, for decision)

- **D7 regex false positives on history questions about rescue medication.** "Seit wann bekommt sie Diazepam?" returns the emergency pointer instead of an answer. Possible fixes: require an action word for the drug names too (as already done for seizures), or the experiment above.
- **D8 strips attributed clinician quotes the prompt allows** ("Empfehlung", "unauffällig" inside a quote). Possible fixes: skip lines that carry an attribution pattern ("laut", "steht", a date plus a name), or the typed call in D8.
- **The Rechtsbehelfsbelehrung is judged twice** (classification label `insurance_decision`, extraction `decision` object), independently. Possible fix: derive the label from the extraction result, or pass the classification to the extraction prompt as a hint only.
- **`is_future` is asked of the model** although it is a date comparison. Possible fix: compute it in the backend from the appointment date and the document date.
- **The extraction prompt sets `document_type: "invoice"`**, a label the classification prompt does not offer and the pipeline never stores. Possible fix: add `invoice` to the classification labels, or drop it from the extraction prompt.

## Sources

- InfoQ, Jev release: https://infoq.com/news/2026/10/typesafe-ai-jev-released
- TypedBench, arXiv 2610.11392: https://arxiv.org/abs/2610.11392
- Parallel, "Are all System One models created equal": https://parallel.ai/blog/are-all-system-one-models-created-equal
- Kev-4B model card: https://huggingface.co/jaredpalmer/kev-4b
- GLiNER2.5-multi-Decide model card: https://huggingface.co/fastino/GLiNER2.5-multi-Decide
- pplx-decider v1.2 model card: https://huggingface.co/perplexity-ai/pplx-decider-v1.2
- Qwen3-Reranker-0.6B model card: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
- Ollama chat API: https://docs.ollama.com/api/chat
- vLLM structured outputs: https://docs.vllm.ai/en/latest/features/structured_outputs.html
- IONOS models overview: https://docs.ionos.com/cloud/ai/ai-model-hub/models.md
- IONOS LLMs: https://docs.ionos.com/cloud/ai/ai-model-hub/models/llms.md
- IONOS Qwen3.5 9B: https://docs.ionos.com/cloud/ai/ai-model-hub/models/llms/qwen3-5-9b.md
- IONOS embedding models: https://docs.ionos.com/cloud/ai/ai-model-hub/models/embedding-models.md
- IONOS Qwen3-VL-Reranker-8B: https://docs.ionos.com/cloud/ai/ai-model-hub/models/reranking-models/qwen3-vl-reranker-8b.md
- IONOS reranking how-to: https://docs.ionos.com/cloud/ai/ai-model-hub/how-tos/reranking.md
- IONOS text generation how-to: https://docs.ionos.com/cloud/ai/ai-model-hub/how-tos/text-generation.md
- IONOS price list (EUR): https://docs.ionos.com/support/general-information/price-list/ionos-cloud-eur-en
- Xiong et al., verbalized confidence, arXiv 2306.13063: https://arxiv.org/abs/2306.13063
- SetFit, arXiv 2209.11055: https://arxiv.org/abs/2209.11055
- mmBERT, arXiv 2509.06888: https://arxiv.org/abs/2509.06888
