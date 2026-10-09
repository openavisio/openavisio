# The chat agent loop lives in the backend, and the aiservice stays a stateless completion API

ADR 038 hands the chat a context assembled by hand: structured records in full, documents by retrieval, lab values capped three per parameter. It named the caps as the known ceiling and tool calling as the upgrade, and deferred that upgrade because it is an architecture decision about the boundary between the two services, not something to settle while restoring a chat page. This ADR settles it.

The decision is **where the agent loop lives**, not how it is built. Implementation is blocked on latency (#215) and does not start here.

## Why now

Measured on the test server, one real Patient, 2026-07-21: 170 context lines, 14k characters, of which 143 lines are lab values after #200 capped them at three per parameter. The cap is per parameter, so the total still grows with the number of distinct parameters, and nothing bounds it. Two failure modes are already visible, and a bigger context window fixes neither:

- The model answered "the document contains no medication" while `Medikament | 2026-07-11 | Ergenyl` sat in the same context. The line was present and ignored. Recall in the middle of a long prompt is where models are weakest, so a longer context makes this more likely, not less.
- Every new field is wired into the context by hand, and every cap is a knob that will eventually sit wrong. #209 is one instance of that pattern, not the whole of it.

## The decision

The backend runs the loop. Each turn it calls the `aiservice` as a plain completion API, reads the tool calls the model emits, executes them as queries it already owns, and feeds the results back for the next turn. The `aiservice` stays stateless and model-only.

The two rejected options, and why:

- **Callback channel (loop in the `aiservice`).** The `aiservice` keeps the loop and calls back into the backend for `list_events`, `search_documents`, `get_medications`. Rejected because it inverts a trust direction that today points one way only, and the callback then needs its own authentication and access checks, duplicating what `require_patient_access` already enforces. The `aiservice` has no database access at all: no SQLAlchemy, no session, no per-Patient KEK. Giving it a privileged channel back into the data is the largest thing this decision could get wrong.
- **Status quo (keep handing everything over, keep tuning caps).** Cheapest today, and the treadmill continues: the context keeps growing with the Patient, the caps keep needing recalibration, and the recall-in-the-middle failure gets worse as the prompt gets longer.

The backend already owns everything the loop needs. Access control (ADR 003), the per-Patient KEK (ADR 031), and every query the tools would run all live there. Putting the loop there reimplements none of it. It also keeps the `aiservice` a pure model endpoint, which is the property ADR 005 depends on: it must be deployable next to whatever model an operator has pulled, with no knowledge of the schema behind it.

## What gates it

This is not shippable as decided, for two reasons that are constraints on timing, not on the choice.

- **Latency.** Each tool round trip is another model call. The deployed chat model is `qwen3.6:27b-mtp-q4_K_M`, and a single warm answer measured 19 to 32 seconds (`docs/research-extraction-model.md`, 2026-07-21), plus roughly 90 seconds cold load when the model is not resident. One call per turn means a three-turn loop is 60 to 90 seconds warm and more on a cold model, still past an interactive threshold once turns chain. Tool calling waits on the latency work in #215. A second 3090 is not the way out: the slot and the NVLink bridges do not exist on the current board (#203).
- **Model capability.** The loop depends on the operator's model emitting reliable tool calls, and ADR 005 deliberately lets them pick any model they have pulled. So this is a capability probe with a fallback to the whole-context mode of ADR 038, not a hard requirement. A model that cannot call tools gets today's behaviour, caps and all.

## Second half of the same lever: the model returns data, the client writes the text

Tool calling bounds what goes into the prompt. The same move bounds what comes out, and that is the only thing that removes the judgement problem at the source instead of filtering it after the fact (#208).

Today the model produces prose, and prose is a place where any sentence can appear, including "alle Werte liegen im Normbereich". No prompt reliably prevents that on a locally hosted model, and the phrase filter in `backend/app/routers/chat.py` is a net with holes that also catches legitimate quoted clinician recommendations.

If a factual question is answered with **record IDs instead of sentences**, the frontend renders the values with the same components the trends view already uses, and there is no step at which a verdict could be produced. The model chooses which records answer the question; it does not narrate them.

Not every question fits a schema. "Wie oft waren wir bei Dr. Meier" and "was steht im Brief von Januar" still need prose. So the realistic shape is a split: structured answers rendered by the client where the question is about records, prose where it has to be prose, and the filter kept for the prose path. This belongs to the same decision because it depends on the same thing, a model that emits reliable structured calls and a loop somewhere that can turn them into queries.

## Consequences

- **Nothing ships from this ADR yet.** It records the direction so #208 and #209 can be reasoned about against a fixed boundary. The trigger to build is #215 landing a latency budget that survives a multi-call loop.
- **When it is built, the frontend does not change for the retrieval path.** ADR 038 already promised this: a Patient outgrowing the context budget upgrades to tool calling without a client change. The structured-output path is the part that touches the client.
- **The `aiservice` contract is unchanged.** It remains a stateless completion API per ADR 005. The loop, the tool definitions, and the access checks all live in the backend next to the data.
- **This does not solve #209.** No lookup knows that Ergenyl contains valproate unless the record says so. That is a data-model gap, not a retrieval gap, and tool calling does not close it.
- **The fallback is load-bearing.** As long as ADR 005 lets operators pick any model, the whole-context mode of ADR 038 stays in the codebase as the path for models that cannot call tools. This is not a migration that deletes the old mode.

See also ADR 038 (the context this replaces), ADR 005 (AI model configuration and the any-model constraint), ADR 003 (access model), ADR 031 (per-Patient KEK), #215 (tool-loop latency), #203 (inference hosting), #208 (grading lab values), #209 (active ingredient on a medication).
