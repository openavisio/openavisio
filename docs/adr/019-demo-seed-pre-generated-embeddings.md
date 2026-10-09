# ADR 019: Pre-generated embeddings for the demo seed

**Status:** Accepted

The demo seed script (`scripts/seed_demo.py`) populates `DocumentChunk` rows with embedding
vectors generated in advance by `scripts/generate_demo_embeddings.py`, rather than invoking
the Processing Pipeline's embedding stage at seed time.

Embedding requires a running AI service (Ollama, vLLM, or Mistral). At demo-instance deploy
time no AI service is guaranteed to be available, and requiring one would couple the seed to a
live model. Running `generate_demo_embeddings.py` once — against any configured AI service —
and committing `scripts/demo_data/embeddings.json` makes the seed entirely self-contained.

## Considered options

- **Run the embedding stage at seed time.** Requires an AI service at deploy; seed output
  differs across model versions; breaks if the service is unavailable.
- **Skip embeddings.** The AI Health Assistant's semantic search over Lena's documents returns
  no results — the primary demo feature does not work.
- **Pre-generate and commit.** Chosen. One-time cost, deterministic, no AI service dependency
  at deploy time.

## Consequences

Regenerate `scripts/demo_data/embeddings.json` whenever:

- the embedding model changes (different model or dimension — current dimension: 768)
- the text content of any demo document changes (chunk texts in `seed_demo.py`)

`scripts/demo_data/embeddings.json` ships with `"placeholder": true` and empty arrays. The
seed script prints a warning when it detects this and seeds without embeddings — the AI Health
Assistant will not function semantically until real vectors are committed.

Schema changes to `DocumentChunk` (column renames, added non-nullable fields) require updating
`seed_demo.py`. Changes to the pipeline extraction format or `DocumentReference` fields also
require updating `seed_demo.py` and possibly the demo PDFs in `docs/demo/`.
