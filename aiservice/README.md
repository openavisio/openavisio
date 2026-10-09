# OpenAvisio AI Service

Python FastAPI microservice for medical document extraction. Supports Ollama (local), vLLM (high-throughput, and any OpenAI-compatible endpoint including hosted providers) backends.

> **Model and GPU sizing:** See [`docs/models.md`](../docs/models.md) for what each GPU size costs in extraction quality, measured on real German documents.

## How It Works

1. Receives uploaded document (PDF or image) via `/extract`
2. PDFs: extracts text with pypdfium2. If text is substantial → text model. If scanned → vision model on page images.
3. Images: sends directly to vision model.
4. Returns structured JSON summary (diagnoses, medications, observations, etc.)

## Determinism

All chat/inference calls run with **`temperature=0`** (greedy decoding), set centrally in `backend.py` for every backend. Without it, Ollama samples at its 0.8 default and vLLM at 1.0 — uploading the same document then yields different extraction results on every run, which makes the pipeline untrustworthy and undebuggable. Do not add sampling parameters per call site; if a use case ever genuinely needs creative sampling, make it an explicit, documented exception. Note: `temperature=0` is not bit-perfect determinism (GPU kernels, vLLM batching), but same-input runs are practically stable.

## Hardware Requirements

- **Recommended:** 24 GB (RTX 3090 / 4090) for the text model, plus a smaller second
  card for vision and embeddings — or a single 32 GB card for all three
- **Workable:** 16 GB, with a smaller text model and measurably worse appointment
  extraction ([`docs/models.md`](../docs/models.md))
- **Not recommended:** 8 GB. A model that small keeps working and files worse clinical
  data, with no error anywhere — see the measurements before choosing it
- CPU-only works for testing but is very slow

## Model Options

| Model | VRAM | Type | Use Case |
|-------|------|------|----------|
| `qwen3.6:27b-mtp-q4_K_M` | ~18 GB | Text | **Default** — extraction, classification *and* chat, all three roles on this one model |
| `glm-ocr:Q8_0` | ~1.6 GB | Vision | **Default** — #1 OmniDocBench OCR, German + handwriting |
| `qwen3-embedding:4b` | ~2.5 GB | Embedding | **Required** for RAG chat pipeline (German, see [`docs/research-embedding-model.md`](../docs/research-embedding-model.md)) |

Total working set is ~22 GB, which leaves no room for context on a 24 GB card. The
reference deployment therefore splits the roles across two Ollama hosts — the text model
alone on the 24 GB card (`OLLAMA_URL`), vision and embeddings together on a smaller one
(`OLLAMA_VISION_URL` / `OLLAMA_EMBED_URL`). A single 32 GB card holds all three at once.

On a smaller GPU, swap the text model for a smaller qwen3 — see
[`docs/models.md`](../docs/models.md) for what each size costs, measured on real German
documents. The vision and embedding models are already small and should stay as they are.

## Setup

### 1. Install Ollama

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Or via Docker (handled by Aspire AppHost)
docker run -d --gpus all -v ollama:/root/.ollama -p 11434:11434 ollama/ollama
```

### 2. Pull models

```bash
ollama pull qwen3.6:27b-mtp-q4_K_M
ollama pull glm-ocr:Q8_0
ollama pull qwen3-embedding:4b
```

### 3. Run locally (without Aspire)

```bash
uv sync
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SERVICES__OLLAMA__HTTP__0` | Ollama URL (Aspire convention) | — |
| `OLLAMA_URL` | Ollama URL(s), comma-separated for round-robin | `http://localhost:11434` |
| `OLLAMA_MODEL` | Default model for extraction | `qwen3.6:27b-mtp-q4_K_M` |
| `OLLAMA_<STAGE>_MODEL` | Per-stage model (`EXTRACT`/`CLASSIFY`/`CHAT`/`VISION`) | — |
| `OLLAMA_<STAGE>_NUM_CTX` | Per-stage Ollama context window (tokens). The aiservice sets a per-stage default (extract 32768, chat 16384, vision/classify 8192) because Ollama's own default is 4096 and truncates multi-page documents — and neither a server-wide `OLLAMA_CONTEXT_LENGTH` nor an OpenWebUI per-model setting reaches these API calls. Override up (longer docs) or down (save VRAM) per stage. Bigger = more KV-cache VRAM | *(stage default above)* |
| `AI_BACKEND` | Backend: `ollama` or `vllm` (any OpenAI-compatible endpoint, your own or a hosted provider's) | `ollama` |
| `AI_PROFILE` | Profile for model defaults: `homelab`, `team`, `org`, `cloud` | *(none)* |
| `VLLM_URL` | vLLM or any OpenAI-compatible endpoint(s), comma-separated for round-robin | — |
| `VLLM_MODEL` / `VLLM_<STAGE>_MODEL` | Model name at that endpoint, overall and per stage | — |
| `VLLM_API_KEY` | Bearer token for `VLLM_URL`, if the endpoint asks for one (a hosted provider, or your own vLLM started with `--api-key`) | — |
| `VLLM_VISION_URL` / `VLLM_VISION_MODEL` | Serve vision OCR from an OpenAI-compatible endpoint instead of an Ollama. Defaults to `VLLM_URL` when `AI_BACKEND=vllm`; `OLLAMA_VISION_URL` takes precedence if set | — |
| `VLLM_EMBED_URL` / `VLLM_EMBED_MODEL` | Serve embeddings from an OpenAI-compatible endpoint. Vectors are truncated to 768d client-side if the provider rejects `dimensions` | — |

## API Endpoints

- `GET /health` — health check
- `POST /extract` — upload file, get structured extraction
- `POST /ocr` — Tesseract/OCRmyPDF text extraction
- `POST /ocr/vision` — vision model OCR fallback
- `POST /classify` — document classification
- `POST /extract-entities` — entity extraction from text
- `POST /embed` — generate embeddings
- `POST /chat` — RAG chat
- `POST /chat/stream` — RAG chat with SSE streaming
- `GET /models` — list available models
- `GET /backend` — backend info
- `GET /connection/test` — test connectivity
