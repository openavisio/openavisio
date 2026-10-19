# A document that does not fit the context window fails instead of being cut

**Status:** accepted (2026-10-19)

**Depends on:** #239, ADR 009 (admin log viewer)

Ollama cuts a prompt longer than `num_ctx` to exactly `num_ctx` tokens and answers anyway. The extraction then runs on part of the document, and the diagnoses or dates of the missing pages never reach the record, while the record looks complete. vLLM and OpenAI-compatible providers such as IONOS refuse such a request instead.

## The decision

**A cut prompt is an error.** The aiservice compares Ollama's `prompt_eval_count` with `num_ctx` after every non-streaming call and raises `ContextOverflow` when the prompt filled the window. A provider's refusal for length becomes the same exception. The extraction answers `document_too_long`, and the pipeline marks the Document failed with it. Nothing partial goes into the record.

**The family reads why.** The document page shows "Das Dokument ist zu lang, um es auf einmal auszuwerten" instead of the code. The admin log names the Document.

**The chat only warns.** A chat answer writes nothing into the record, so a cut chat prompt is logged and answered.

On a hosted Deployment neither the family nor the operator can widen a provider's window, so a document this long stays unanalysed until extraction works in parts (#369).

## Consequences

- Ollama builds that report `prompt_eval_count` without the cached part can miss a cut prompt after a cache hit. They never report one that fit.
- An extraction that fails for any other reason no longer passes as a result: the pipeline now reads the aiservice's `error` field instead of storing it as entities.
