# AI model configuration — dynamic selection, no profiles

Model selection for the Processing Pipeline (extract, classify, chat, vision) is configured via the admin UI and stored in `SystemSetting`. The Ollama model list drives the dropdowns — only models the admin has already pulled appear as options. A `models.json` file shipped with the aiservice annotates known model names with task suitability hints displayed in the UI. Resolution order at runtime: env var (`OLLAMA_EXTRACT_MODEL` etc.) → `SystemSetting` → hardcoded fallback.

## Considered options

**AI_PROFILE presets (homelab/team/org/cloud).** Removed. Presets encoded opinionated model bundles that silently overrode UI choices and required a new release to update model recommendations. Dynamic selection gives each deployment the right model for their hardware without shipping profile knowledge into code.

**Model pulling in OpenAvisio UI.** Rejected. Ollama is the model manager; OpenAvisio lists what is already available. Adding a pull UI duplicates Ollama's own tooling and blurs the boundary between the two services.

**Editable extraction/classification prompts.** Deferred. The extraction prompt defines the JSON schema that the verify endpoint depends on — exposing it to Coordinators risks silently breaking document processing. Only the chat system prompt (AI Health Assistant persona and instructions) is Coordinator-editable; it is stored as a `SystemSetting` row. Extraction and classification prompts are locked and live in `aiservice/prompts/` as `.md` files.

**Silent extraction failure.** One silent retry on JSON parse failure before surfacing an error on the Document. A model that fails twice is a configuration problem, not a transient one.

## Extraction language

The pipeline prepends a language instruction to the extraction and classification prompts at runtime, derived from `Organization.default_language` (see ADR 013). The `.md` prompt files define the JSON schema only; language is injected dynamically so the schema stays stable across locales. JSON keys are always English; free-text values (summary, recommendations) are produced in the org's language. Named entities (drug names, doctor names) are extracted as-is from the source document.
