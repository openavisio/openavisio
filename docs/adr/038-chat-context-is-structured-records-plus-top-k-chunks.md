# The chat sees structured records whole and documents by retrieval, and it lists rather than counts

The AI chat answers questions about one Patient's own data: "wie oft waren wir bei Dr. Meier", "seit wann geben wir Levetiracetam", "wann konnte er frei laufen". It is a **read-only** assistant over material the Organization already holds. It does not judge, advise, or write.

Two things make it work, and both are decisions rather than obvious defaults: **structured records are handed over in full, documents only by vector retrieval**, and **the answer lists what was found instead of stating how much exists**.

## Why the structured records go in whole

The chat was built as classic RAG: embed the question, take the five nearest `document_chunks`, answer from those. That is the right shape for "what stands in the letter from January" and the wrong shape for almost every question a family caregiver actually asks, because those questions are about the *set*: how often, since when, which ones. Five nearest chunks cannot answer a question about a set, and worse, they cannot reveal that they failed to, because a top-K query always returns K rows.

So the context is assembled from two sources with different rules:

- **Structured records, complete and compact.** All Milestones plus the 150 most recent appointments from `calendar_events`, all `medication_statements`, all `conditions` that are not merged away, the 100 most recent `incidents`. One line per record, newest first so truncation drops the oldest.
- **Documents, by retrieval.** The existing top-5 `document_chunks` lookup. Diary entries need no special handling: they are already chunked into the same index.
- **Laboratory `observations`, the three most recent results per parameter.** A Patient with years of blood counts has thousands of rows, which no context window survives, so this is the one source capped *per parameter* rather than overall (#200). A yearly-checked thyroid value must not be pushed out by a weekly-checked drug level, which is exactly what a global "newest 100" would do. Three results, not one, because the question is usually "wie hat sich der Valproat-Spiegel entwickelt" and one value cannot be read against anything. The chat still may not interpret the movement it can now see: that rule lives in the prompt and did not change, and trends have their own view under `/calendar/trends`.

The budget works out: the chat stage runs at `num_ctx = 16384` (`aiservice/backend.py`), 150 calendar lines are roughly 3k tokens, medications and conditions together stay under 1k, five chunks land around 2 to 3k, lab values a few hundred lines at most. Roughly 8k used, with headroom.

### The two alternatives, and why not

- **Tool calling.** The model would call `list_events(provider=...)`, `search_documents(q)` itself. It is more precise, it scales past any context window, and it is where this goes if a real Patient outgrows the budget. It was rejected *now* because the `aiservice` has no database access at all: no SQLAlchemy, no session, no per-Patient KEK. Tools mean either a callback channel from `aiservice` into the backend, inverting a trust direction that today points one way only, or moving the agent loop into the backend and reducing `aiservice` to a tool-call relay. That is an architecture decision about the boundary between the two services, and it should not be made as a side effect of restoring a chat page. It also makes the feature depend on the operator picking a model that emits tool calls reliably, where ADR-005 deliberately lets them pick any model they have pulled.
- **A question router** classifying "appointment question" versus "medication question" before fetching. Rejected on failure mode, not on cost: a misrouted question puts the right source outside the context, and the chat then answers "das steht nicht in Ihren Unterlagen" about something that plainly does. A confident false negative is the worst thing this feature can produce, because it looks exactly like a fact. It also breaks on questions spanning two sources, and it spends a second model round trip to save context we are not short of.

## Why it lists and does not count

"Vier Termine bei Dr. Meier" is not a statement about the retrieved rows, it is a statement about **completeness**. The model cannot verify completeness, and when the context was capped it will still produce a number, in the same confident tone. A wrong count is worse than no count, especially since these answers are copied into research questionnaires.

So the contract is: name the entries with their dates and where they come from, and let the reader count four lines. The same rule governs "seit wann": the honest form is "der früheste Eintrag, den ich sehe, ist vom 03.02.2024", not "seit dem 03.02.2024", which asserts that nothing came before. Where the record set was capped, the answer says so.

This is the same line `prompts/chat_system.md` already draws for clinical judgement (ADR-005, #117): describing is allowed, asserting beyond the evidence is not. Counting is simply that rule applied to quantity instead of significance.

## Provenance

- **Documents are cited deterministically.** The backend knows exactly which chunks it retrieved, so the answer carries a source list of those documents, deduplicated by document rather than by chunk, linked to the viewer. It is worded as what it is: documents searched, not documents proven relevant.
- **A distance threshold is required, not optional.** `ORDER BY embedding <-> :emb LIMIT 5` has no cutoff, so an unrelated question still returns five documents. Without a threshold, a source list is a false positive dressed as evidence, and "nothing found" can never happen. The value is empirical and depends on the embedding model the operator chose, so it is calibrated against real documents and held as one named constant.

  The calibration turned out to be a decision about the embedding model rather than about a number. Against 75 real German chunks, `nomic-embed-text` put five genuine questions at 0.334 to 0.424 and five unrelated ones at 0.413 to 0.453: overlapping, so **no threshold existed at all** and the cutoff was decorative. That model carries a single language tag, `en`. With `qwen3-embedding:4b` truncated to the schema's 768 dimensions and the query instruction prefix, the same probes land at 0.237 to 0.519 and 0.663 to 0.735, and the constant is the midpoint of that gap (`docs/research-embedding-model.md`).

  Two consequences worth naming. The constant is only valid for one model, so a model change is a recalibration, not a config edit. And the literature is against absolute cosine cutoffs in general ([Steck et al., WWW'24](https://arxiv.org/abs/2403.05440)); if recalibration becomes a habit, the upgrade is a relative rule (keep a chunk only while it stays close to the best hit), which survives a model swap.
- **Calendar entries are not cited, they are linked by month.** Because those records are handed over whole rather than retrieved, the backend cannot know which lines the answer used. Dates in the answer text link to the calendar month instead, and only for months that actually contain entries, a set the backend already has in hand. A citation link that opens an empty month teaches the reader to stop clicking links.

Marker citations (`[K3]`, `[D1]` resolved back to entity IDs) would give real per-record provenance for both sources. They are deferred because they depend on a locally hosted model citing disciplined markers, and the failure mode is either no evidence or evidence pointing at the wrong record.

## Conversation memory

The last six messages are passed to the `aiservice`, whose `history` field with its role allowlist was built for this and never used. Retrieval embeds the previous user question together with the current one, because "und wann war der letzte?" embeds to nothing useful on its own and the history in the prompt arrives after retrieval has already happened. Query rewriting by the model would be more accurate and costs a second round trip on local hardware.

Beyond that window the chat says it cannot see further and asks for a fully worded question, rather than guessing. A standing "my memory is limited" notice under every answer was rejected for the reason `AiNotice` documents: a warning shown always is read never.

## Consequences

- **The context grows with the Patient.** The caps are the known ceiling. A Patient with more than 150 appointments or 100 incidents silently loses the oldest ones, which is why the answer must disclose the cap. When a real Patient reaches it, tool calling is the upgrade, and the frontend does not change.
- **Every chat answer now reads five tables.** One query per source per question, all indexed on `patient_id`.
- **Access and erasure are unchanged.** The endpoint keeps `require_patient_access`, messages stay encrypted under the per-Patient KEK (ADR-031), and `services/erasure.py` already covers `chat_messages`.
- **The prompt is now load-bearing for three separate rules**: no clinical judgement, no completeness claims, no guessing past the history window. It is one file, `aiservice/prompts/chat_system.md`, and it is the thing to read before changing chat behaviour.
- Deferred: marker citations, streaming responses, tool calling.

See also ADR-005 (AI model configuration), ADR-031 (per-Patient KEK), ADR-003 (access model), `docs/regulatory-positioning.md` (why the chat may not judge).
