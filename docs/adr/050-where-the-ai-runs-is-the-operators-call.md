# Where the AI runs is the operator's call, and a key says nothing about it

The aiservice refused to start a `vllm` backend that had a `VLLM_API_KEY` unless `AI_ALLOW_CLOUD_EGRESS=true` was set, and then logged "CLOUD EGRESS ENABLED" (#47). The rule inferred "hosted provider" from "has a key". That inference is wrong as often as it is right: a vLLM on the operator's own network is commonly started with `--api-key`, and the project's own homelab vLLM is. Such an operator had to set a flag named cloud egress for data that never left the house, and read a false warning on every start, which teaches everyone to ignore the warning. The same gate covered `AI_BACKEND=mistral`, a backend nothing used: Mistral was measured and rejected for inventing diagnoses (avisiohub ADR 0006).

## The decision

**Where an AI role runs is the operator's decision, and OpenAvisio does not guess it.** `vllm` is any OpenAI-compatible endpoint, with or without a key. Whether `VLLM_URL`, `VLLM_VISION_URL` and `VLLM_EMBED_URL` point at the operator's own hardware or at a provider is configuration the operator owns, as they own the choice of server host and mail provider. A hosted provider still needs a data-processing agreement; the AVV template, the RoPA and the DPIA say so, and name the provider instead of a mechanism.

**The Mistral backend is gone**, and with it `AI_ALLOW_CLOUD_EGRESS`, which guarded nothing else. Mistral's API is OpenAI-compatible, so anyone who wants it reaches it as `vllm`. An `AI_BACKEND` the aiservice does not know raises at the first AI call instead of falling back to a local Ollama.

## Rejected alternatives

- **An explicit `VLLM_ON_PREMISE=true`** to tell an own vLLM with a key from a hosted one. It keeps the gate, but every operator with a protected vLLM has to know one more variable, and the gate still only checks what the operator typed into it.
- **Deciding by address** (private IP range means on-premise). Hostnames, reverse proxies and VPNs make that a guess, and a wrong guess either blocks a legitimate setup or waves a provider through.
- **Leaving it and setting the flag on the homelab.** Fixes one installation and leaves the false alarm for every other operator with a protected vLLM.

## Consequences

- **One control fewer in the DPIA.** What stops PHI reaching a provider by accident is now the default (`AI_BACKEND=ollama`) and the operator's configuration, not a start-up refusal.
- **An installation that still says `AI_BACKEND=mistral`** fails at the first AI call with a message naming the valid backends.
- The admin UI's Mistral DPA banner, the Mistral entries in `setup.sh`, the compose file, `.env.example` and the model allowlist are removed.
