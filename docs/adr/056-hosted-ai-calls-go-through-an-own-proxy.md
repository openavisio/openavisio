# Hosted AI calls go through an own proxy that stores no content

**Status:** accepted (2026-10-20)

**Depends on:** #375, #374, avisiohub ADR 0006 and 0007

Every hosted Deployment called IONOS directly with the same token, written into each `.env`. One leaked `.env` exposed the contract, a rotation meant touching every Deployment, and nobody could tell which Deployment used how much.

## The decision

**One small proxy per hosted box** (`deploy/hosted/llm-proxy/proxy.py`), next to the shared Caddy and attached to each Deployment's network the same way. It holds the IONOS token; each Deployment has its own key (`proxy-key.sh`), of which the box keeps only the SHA-256.

**It stores metadata, never content.** One row per call: Deployment, model, path, status, prompt and completion tokens, duration. The body is read for the model name and the `usage` block only; prompts and answers are health data and are neither written nor logged. The test checks the database for the prompt.

**Python standard library only**, no LiteLLM or OmniRoute: with one provider it is about 150 lines that can be read end to end, which is what makes the no-content claim checkable. Revisit when a second provider or real routing is needed.

**Not in the first version:** fair sharing of the contract's rate limit (a 429 is passed through with `Retry-After` and retried by the pipeline, #374; the proxy counts 429s per Deployment, so a real shortage shows), a web view (the report runs over SSH), and costs (per-Deployment cost is tokens times price; the contract's actual cost is in the IONOS Cost & Usage view and Billing API).

## Consequences

- If the proxy is down, no hosted Deployment has AI. It is restarted by Docker and has a healthcheck; documents wait and retry like on a 429.
- The proxy runs on the same box at the same provider, so the AVV and the record of processing gain no processor.
- `isolation-check.sh` accepts the proxy on every Deployment network, like Caddy, and fails when it is missing.
