# Probe documents

Synthetic documents that reproduce a specific extraction failure. **They contain
no patient data**, so they can be sent to any provider, anywhere, as often as
needed — which is the point: a model can be judged before an account exists,
before an AVV is signed, and without a single real document leaving the box.

Each file carries its pass/fail criteria in an HTML comment at the top.

## Why these exist

Comparing models on real documents needs a provider you already trust, and
trusting a provider needs the comparison. A probe breaks that circle for the one
question that disqualifies a model outright.

## Running one

```bash
# against a local Ollama through the aiservice
python3 scripts/ab-extract.py --url http://localhost:8000 \
    --models qwen3.6:27b-mtp-q4_K_M --language de \
    scripts/probe_docs/lab-fabrication.md

# against any hosted provider: point a throwaway aiservice at it
# (AI_BACKEND=vllm, VLLM_URL, VLLM_API_KEY, AI_ALLOW_CLOUD_EGRESS=true)
# and pass its --url
```

Then read the `diagnoses` array against the criteria in the file's header
comment. Counting entities is not enough — the question is *which* ones.

## The files

| File | What it probes |
|---|---|
| `lab-fabrication.md` | Does the model invent diagnoses from out-of-range lab values? Found on 2026-07-27: `mistral-large` wrote Hyperkaliämie, Folsäuremangel and Zinküberladung from table rows, on a report where the laboratory itself warned the potassium may be artefactual. Both Qwen models returned nothing. |

## Adding one

Reproduce a failure that was seen on a real document, then strip it down to what
triggers it and add controls — something the model **must** find, so a model that
passes by extracting nothing at all still fails.
