# The chat model decides what is an emergency question

An emergency question in the chat never reaches the answering model; it gets the fixed pointer to the Emergency Plan (ADR 048), because a misquoted dose is the one mistake the chat must not make. Which questions count was decided by keywords. Measured on 80 synthetic questions (`scripts/emergency-questions.json`), the keywords missed 24 of 40 emergencies ("Sie krampft seit fünf Minuten und reagiert nicht", "Er läuft blau an, was jetzt?") and flagged 9 of 40 history questions ("Seit wann bekommt sie Diazepam?").

## The decision

**Before each chat question the backend asks the configured chat model one ja/nein token and reads P(ja) from its logprobs.** At 0.2 or above, the question gets the pointer. The prompt is German (`aiservice/prompts/emergency.md`) because the threshold was measured with exactly that text. When the call fails, times out or the server returns no logprobs (the mock backend, an old Ollama), the keywords decide as before.

Measured with Qwen/Qwen3.8-27B: on vLLM at home, history questions scored 0.03 or less and emergencies 0.32 or more; at IONOS 0.11 or less against 0.26 or more, 388 ms per question. 0.2 separates both runs without an error. Missing an emergency costs more than a needless pointer, so the threshold sits nearer the history side. Details in `docs/research-system-one-models.md`, section 6.

## Alternatives, and why not

- **A dedicated decision model (Kev-4B).** Measured on the same set: 7 emergencies missed at its best threshold, and it needs its own server next to vLLM or Ollama; not available at IONOS.
- **Keywords OR model.** Keeps all nine false alarms of the keywords and adds nothing the model misses.
- **Reading the plain "ja"/"nein" answer.** That is a threshold of 0.5, which missed seven emergencies, most of them questions about the plan ("Was steht im Notfallplan?").

## Consequences

- Every chat question costs one more short model call (one output token), counted against the demo budget and the provider's rate limit like any other.
- A model change in the admin UI (ADR 005) can move the scores. Re-run `scripts/bench-emergency.py` against the new model before trusting the threshold.
