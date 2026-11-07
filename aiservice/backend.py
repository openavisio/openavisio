"""
AI inference backend abstraction.
Supports Ollama (default), vLLM or any OpenAI-compatible endpoint, and Mock (dev/testing).
"""

import logging
import os
from abc import ABC, abstractmethod

import ollama

logger = logging.getLogger(__name__)

# --- Hardcoded fallback defaults (used when no env var or SystemSetting is configured) ---

_DEFAULTS: dict[str, str] = {
    "vision": "glm-ocr:Q8_0",
    "classify": "qwen3.6:27b-mtp-q4_K_M",
    "extract": "qwen3.6:27b-mtp-q4_K_M",
    "chat": "qwen3.6:27b-mtp-q4_K_M",
    "embed": "qwen3-embedding:4b",
}

# Ollama context window per stage. The aiservice owns this: Ollama's default is
# 4096, which truncates multi-page documents, and neither the operator's global
# OLLAMA_CONTEXT_LENGTH nor an OpenWebUI per-model setting reaches our API calls.
# So we set a sensible per-stage floor sized for real documents (extraction sees
# a whole document's OCR text; ~30k chars ≈ 8k tokens, 32k gives headroom). An
# operator can override up or down per stage with OLLAMA_<STAGE>_NUM_CTX. Only
# applies to the Ollama backend (vLLM sets context at server start).
_NUM_CTX_DEFAULTS: dict[str, int] = {
    "extract": 32768,
    "chat": 16384,
    "vision": 8192,
    "classify": 8192,
}

# Per-model generation quirks. GLM-OCR transcribes correctly then loops,
# repeating the text wrapped in ``` fences; stopping at the first fence yields
# the clean transcription (verified against glm-ocr:Q8_0 on a real scan, #64).
_MODEL_STOP: dict[str, list[str]] = {"glm-ocr": ["```"]}


def _stop_for_model(model: str) -> list[str] | None:
    lower = model.lower()
    for pattern, stop in _MODEL_STOP.items():
        if pattern in lower:
            return stop
    return None


def _first_url(raw: str) -> str:
    # ponytail: one host per role; a comma list from before 0.7.1 keeps its first URL
    return raw.split(",")[0].strip()


# --- Abstract backend ---

# Greedy decoding: document extraction must give the same answer for the same
# input. Not perfect determinism (GPU kernels, vLLM batching), but close.
_DETERMINISTIC = {"temperature": 0}


class ContextOverflow(RuntimeError):
    """The prompt did not fit the model's context window (#239)."""


def _is_overflow(exc: Exception) -> bool:
    # ponytail: matched on the provider's wording (vLLM, OpenAI: "maximum context length");
    # a provider that words it differently still fails, only not as ContextOverflow
    return "context length" in str(exc).lower()


def _check_fit(response, num_ctx: int | None) -> None:
    """Ollama cuts an over-long prompt to exactly num_ctx tokens and answers anyway (#239)."""
    used = getattr(response, "prompt_eval_count", None) or 0
    if num_ctx and used >= num_ctx:
        raise ContextOverflow(f"prompt filled the whole context window ({used} of {num_ctx} tokens) and was truncated")


def p_yes(top: list[tuple[str, float]]) -> float | None:
    """P(ja) from the first token's alternatives, ja against nein (ADR 059).

    Qwen emits "nein" as "ne" + "in", so any prefix of "nein" counts as no.
    """
    import math
    p = {"ja": 0.0, "nein": 0.0}
    for token, logprob in top:
        w = token.strip().lower()
        k = "ja" if w in ("ja", "j") else "nein" if w and "nein".startswith(w) else None
        if k:
            p[k] += math.exp(logprob)
    total = p["ja"] + p["nein"]
    return p["ja"] / total if total else None


class InferenceBackend(ABC):
    """Abstract base class for inference backends."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def supports_pull(self) -> bool: ...

    @abstractmethod
    def chat(self, model: str, messages: list[dict], images: list[bytes] | None = None,
             num_ctx: int | None = None, think: bool | None = None) -> str:
        """Send chat completion. Returns response text."""
        ...

    def yes_probability(self, model: str, messages: list[dict]) -> float | None:
        """P(ja) of a one-token ja/nein answer, None when the server gives no logprobs."""
        return None

    @abstractmethod
    def embed(self, model: str, texts: list[str], dimensions: int | None = None) -> list[list[float]]:
        """Generate embeddings. Returns list of vectors. `dimensions` truncates
        Matryoshka models to the schema's width (docs/research-embedding-model.md)."""
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """List available model names."""
        ...

    def list_models_detailed(self) -> list[dict]:
        """List models with metadata. Subclasses may override for richer info."""
        return [{"name": m} for m in self.list_models()]

# --- Ollama backend ---

class OllamaBackend(InferenceBackend):
    """Ollama backend via ollama Python SDK."""

    def __init__(self, url: str):
        url = _first_url(url) or "http://localhost:11434"
        # generous timeout: a ~26B model on a multi-page HTML doc can run minutes (#73)
        self._client = ollama.Client(host=url, timeout=600)
        logger.info("OllamaBackend initialized: %s", url)

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def supports_pull(self) -> bool:
        return True

    def chat(self, model: str, messages: list[dict], images: list[bytes] | None = None,
             num_ctx: int | None = None, think: bool | None = None) -> str:
        opts = {**_DETERMINISTIC, **({"num_ctx": num_ctx} if num_ctx else {})}
        stop = _stop_for_model(model)
        if stop:
            opts["stop"] = stop
        # A reasoning model spends its whole output budget thinking unless told
        # not to. Measured on qwen3.6:27b: 1175 tokens and 20.6s with thinking,
        # 34 tokens and 1.0s without, byte-identical answer. Old Ollama builds
        # reject the argument, so only send it when a caller asked.
        think_kw = {} if think is None else {"think": think}
        msgs = messages
        if images:
            msgs = [m.copy() for m in messages]
            msgs[-1]["images"] = images
        try:
            response = self._client.chat(model=model, messages=msgs, options=opts, **think_kw)
        except Exception as exc:
            if _is_overflow(exc):  # newer Ollama builds may refuse instead of cutting
                raise ContextOverflow(str(exc)) from exc
            raise
        _check_fit(response, num_ctx)
        return response.message.content

    def yes_probability(self, model: str, messages: list[dict]) -> float | None:
        r = self._client.chat(model=model, messages=messages, think=False, logprobs=True, top_logprobs=10,
                        options={**_DETERMINISTIC, "num_predict": 1})
        return p_yes([(t.token, t.logprob) for t in r.logprobs[0].top_logprobs]) if r.logprobs else None

    def embed(self, model: str, texts: list[str], dimensions: int | None = None) -> list[list[float]]:
        return self._client.embed(model=model, input=texts, dimensions=dimensions).embeddings

    def list_models(self) -> list[str]:
        return [m.model for m in self._client.list().models]

    def list_models_detailed(self) -> list[dict]:
        models = self._client.list()
        return [
            {
                "name": m.model,
                "size": m.size,
                "modified_at": str(m.modified_at) if getattr(m, "modified_at", None) else None,
            }
            for m in models.models
        ]

# --- vLLM backend ---

class VllmBackend(InferenceBackend):
    """vLLM backend via OpenAI-compatible API."""

    def __init__(self, url: str):
        from openai import OpenAI
        url = _first_url(url)
        if not url:
            raise RuntimeError("VLLM_URL is required for vLLM backend")
        # Whatever key the endpoint asks for; "unused" keeps a keyless vLLM working.
        key = os.environ.get("VLLM_API_KEY", "").strip() or "unused"
        self._client = OpenAI(base_url=url, api_key=key)
        logger.info("VllmBackend initialized, key %s: %s", "set" if key != "unused" else "none", url)

    @property
    def name(self) -> str:
        return "vllm"

    @property
    def supports_pull(self) -> bool:
        return False

    @staticmethod
    def _with_images(messages: list[dict], images: list[bytes]) -> list[dict]:
        """Attach images to the last user message as OpenAI content parts.

        Ollama takes raw bytes in an `images` field; the OpenAI protocol wants
        `image_url` parts carrying a data URI, which is what every hosted
        provider serving a vision model expects (ADR 0006, avisiohub).
        """
        import base64
        parts = [{"type": "image_url",
                  "image_url": {"url": "data:image/png;base64," + base64.b64encode(b).decode()}}
                 for b in images]
        out = [dict(m) for m in messages]
        for m in reversed(out):
            if m.get("role") == "user":
                m["content"] = parts + [{"type": "text", "text": m.get("content") or ""}]
                return out
        out.append({"role": "user", "content": parts})
        return out

    # Turning thinking off over an OpenAI-compatible API is not `think` — that is
    # Ollama's own field. Measured against two hosted providers on 2026-07-27:
    # chat_template_kwargs={"enable_thinking": False} changed nothing (Qwen 841 ->
    # 1042 output tokens, gpt-oss 239 -> 193), while reasoning_effort="none" cut
    # Qwen from 841 to 506 and gpt-oss from 239 to 74, with the latency to match.
    #
    # It is honoured per provider, not universally: mistral-large ignores it
    # outright — 10 runs each way on the same document produced 4401 and 4408
    # output tokens, a difference of nothing. So this reduces reasoning where a
    # provider implements it and is silently inert where one does not, unlike
    # Ollama's flag, which can be assumed.
    #
    # ponytail: one parameter and no verification that it took effect. If that
    # matters somewhere, compare completion_tokens with and without on the model
    # in question — the difference is obvious when it works.
    _NO_THINK = {"reasoning_effort": "none"}

    def _create(self, client, model: str, messages: list[dict], opts: dict, **kw):
        """Create a completion, surviving a provider that rejects `reasoning_effort="none"`.

        gpt-oss on IONOS answers 400 "Harmony does not support reasoning_effort='none'",
        so the lever meant to be silently inert kills the request instead. "low" is
        Harmony's floor and still reduces reasoning.
        """
        try:
            return client.chat.completions.create(model=model, messages=messages, temperature=0, **opts, **kw)
        except Exception as exc:
            if _is_overflow(exc):
                raise ContextOverflow(str(exc)) from exc
            if opts.get("reasoning_effort") != "none" or "reasoning_effort" not in str(exc):
                raise
            opts = {**opts, "reasoning_effort": "low"}
            return client.chat.completions.create(model=model, messages=messages, temperature=0, **opts, **kw)

    def chat(self, model: str, messages: list[dict], images: list[bytes] | None = None,
             num_ctx: int | None = None, think: bool | None = None) -> str:
        if images:
            messages = self._with_images(messages, images)
        opts = {} if think is not False else dict(self._NO_THINK)
        return self._create(self._client, model, messages, opts).choices[0].message.content

    def yes_probability(self, model: str, messages: list[dict]) -> float | None:
        r = self._create(self._client, model, messages, dict(self._NO_THINK), max_tokens=1, logprobs=True, top_logprobs=10)
        lp = r.choices[0].logprobs
        return p_yes([(t.token, t.logprob) for t in lp.content[0].top_logprobs]) if lp and lp.content else None

    @staticmethod
    def _truncate(vectors: list[list[float]], dimensions: int) -> list[list[float]]:
        """Cut Matryoshka vectors to width and renormalise.

        IONOS answers 400 to `dimensions` on Qwen3-VL-Embedding-8B and returns
        4096 instead of the 768 the schema stores. The model is Matryoshka, so
        the first 768 values carry the same retrieval quality — measured over
        731 chunks: recall@10 0.783 at both widths (avisiohub ADR 0006).
        Renormalising matters because a slice of a unit vector is not one.
        """
        out = []
        for v in vectors:
            v = v[:dimensions]
            norm = sum(x * x for x in v) ** 0.5 or 1.0
            out.append([x / norm for x in v])
        return out

    def _embed_one(self, client, model: str, texts: list[str], dimensions: int | None) -> list[list[float]]:
        try:
            response = client.embeddings.create(model=model, input=texts, dimensions=dimensions)
        except Exception as exc:
            if not dimensions or "dimensions" not in str(exc).lower():
                raise
            logger.info("%s rejects dimensions=%d, truncating client-side", model, dimensions)
            full = client.embeddings.create(model=model, input=texts)
            return self._truncate([item.embedding for item in full.data], dimensions)
        return [item.embedding for item in response.data]

    def embed(self, model: str, texts: list[str], dimensions: int | None = None) -> list[list[float]]:
        return self._embed_one(self._client, model, texts, dimensions)

    def list_models(self) -> list[str]:
        return [m.id for m in self._client.models.list().data]

# --- Mock backend (dev/testing — no GPU needed) ---

class MockBackend(InferenceBackend):
    """Mock backend returning canned responses. Use AI_BACKEND=mock for local dev without Ollama."""

    _MOCK_OCR_TEXT = (
        "LABORATORY REPORT\n"
        "Patient: Demo Patient\n"
        "Date: 2025-01-15\n"
        "Ordering Physician: Dr. Mock\n\n"
        "Complete Blood Count (CBC)\n"
        "  WBC: 6.2 x10^3/uL (4.5-11.0)\n"
        "  RBC: 4.8 x10^6/uL (4.0-5.5)\n"
        "  Hemoglobin: 14.1 g/dL (12.0-16.0)\n"
        "  Hematocrit: 42.3% (36.0-46.0)\n"
        "  Platelets: 245 x10^3/uL (150-400)\n\n"
        "Basic Metabolic Panel\n"
        "  Glucose: 92 mg/dL (70-100)\n"
        "  Creatinine: 0.9 mg/dL (0.6-1.2)\n"
        "  Sodium: 140 mEq/L (136-145)\n"
        "  Potassium: 4.1 mEq/L (3.5-5.1)\n"
    )

    _MOCK_ENTITIES = {
        "document_type": "lab_report",
        "observations": [
            {"code": "6690-2", "display": "WBC", "value": 6.2, "unit": "x10^3/uL", "reference_range": "4.5-11.0", "status": "final"},
            {"code": "789-8", "display": "RBC", "value": 4.8, "unit": "x10^6/uL", "reference_range": "4.0-5.5", "status": "final"},
            {"code": "718-7", "display": "Hemoglobin", "value": 14.1, "unit": "g/dL", "reference_range": "12.0-16.0", "status": "final"},
            {"code": "4544-3", "display": "Hematocrit", "value": 42.3, "unit": "%", "reference_range": "36.0-46.0", "status": "final"},
            {"code": "777-3", "display": "Platelets", "value": 245, "unit": "x10^3/uL", "reference_range": "150-400", "status": "final"},
            {"code": "2345-7", "display": "Glucose", "value": 92, "unit": "mg/dL", "reference_range": "70-100", "status": "final"},
        ],
        "conditions": [],
        "diagnoses": [
            {"name": "Essential hypertension", "onset_date": "2024-06-15", "severity": "moderate", "status": "active"},
            {"name": "Type 2 diabetes mellitus", "onset_date": "2023-01-10", "severity": "mild", "status": "active"},
        ],
        "medications": [],
    }

    def __init__(self):
        logger.info("MockBackend initialized — all responses are canned data")

    @property
    def name(self) -> str:
        return "mock"

    @property
    def supports_pull(self) -> bool:
        return False

    def chat(self, model: str, messages: list[dict], images: list[bytes] | None = None,
             num_ctx: int | None = None, think: bool | None = None) -> str:
        last_msg = messages[-1]["content"] if messages else ""

        # OCR vision request — return canned lab text
        if images:
            return self._MOCK_OCR_TEXT

        # Intake Form (ADR 047): checked first, its prompts mention documents too
        if "# Intake Form questions" in last_msg:
            import json as _json
            return _json.dumps({"questions": [
                {"text": "Birth weight", "section": "Pregnancy and birth", "kind": "fact", "aging": "lasting"},
                {"text": "Which medication does your child currently take?", "section": None, "kind": "fact", "aging": "changeable"},
                {"text": "When did your child first walk on its own?", "section": None, "kind": "fact", "aging": "lasting", "ability": "Walking"},
                {"text": "Is your child's development age-appropriate?", "section": None, "kind": "judgement", "aging": "changeable"},
                {"text": "Reason for this visit", "section": None, "kind": "fact", "aging": "visit_only"},
            ]})
        if "# Intake Form answers" in last_msg:
            import json as _json
            return _json.dumps({"answers": []})

        # Classification request
        if "classify" in last_msg.lower() or "document type" in last_msg.lower():
            import json as _json
            return _json.dumps({"document_type": "lab_report", "provider": "Mock Clinic", "confidence": 0.95})

        # Extraction request
        if "extract" in last_msg.lower() or "entities" in last_msg.lower() or "observation" in last_msg.lower():
            import json as _json
            return _json.dumps(self._MOCK_ENTITIES)

        # Chat / general — context-aware mock reply
        context_summary = ""
        for msg in messages:
            if msg["role"] == "system" and "CONTEXT" in msg["content"]:
                lines = msg["content"].split("\n")
                context_lines = [ln for ln in lines if ln.strip() and "CONTEXT" not in ln and "medical assistant" not in ln.lower()]
                context_summary = " ".join(context_lines[:3])
                break
        if context_summary:
            return f"Based on the available documents: {context_summary[:200]}. This is a mock response for development — connect Ollama for real AI answers."
        return "This is a mock AI response for development. Set OLLAMA_URL and AI_BACKEND=ollama to enable real AI inference."

    def embed(self, model: str, texts: list[str], dimensions: int | None = None) -> list[list[float]]:
        import random
        random.seed(42)  # deterministic for consistency
        return [[random.gauss(0, 0.1) for _ in range(768)] for _ in texts]

    def list_models(self) -> list[str]:
        return ["mock-model"]

def _vllm_url(stage: str) -> str:
    """The OpenAI-compatible endpoint serving this stage, or "" when Ollama or mock does (#312)."""
    backend_type = os.environ.get("AI_BACKEND", "ollama").lower().strip()
    if backend_type == "mock":
        return ""
    main = os.environ.get("VLLM_URL", "").strip() if backend_type == "vllm" else ""
    if stage == "vision":
        # OLLAMA_VISION_URL always wins; otherwise a hosted vision endpoint or the chat one
        if os.environ.get("OLLAMA_VISION_URL", "").strip():
            return ""
        return os.environ.get("VLLM_VISION_URL", "").strip() or main
    if stage == "embed":
        return os.environ.get("VLLM_EMBED_URL", "").strip() if backend_type == "vllm" else ""
    return main


# --- Singletons ---

_backend: InferenceBackend | None = None
_vision_backend: OllamaBackend | None = None
_embed_backend: InferenceBackend | None = None


def get_backend() -> InferenceBackend:
    """Get the configured inference backend (singleton)."""
    global _backend
    if _backend is not None:
        return _backend

    backend_type = os.environ.get("AI_BACKEND", "ollama").lower().strip()

    if backend_type == "mock":
        _backend = MockBackend()
        logger.info("Using Mock backend (canned responses, no GPU needed)")
    elif backend_type == "vllm":
        url = os.environ.get("VLLM_URL", "").strip()
        if not url:
            raise RuntimeError("AI_BACKEND=vllm but VLLM_URL is not set")
        # where it runs is the operator's call, a key says nothing about it (ADR 050)
        _backend = VllmBackend(url)
    elif backend_type in ("ollama", ""):
        url = os.environ.get("OLLAMA_URL") or "http://localhost:11434"
        _backend = OllamaBackend(url)
    else:
        # mistral was removed (ADR 050); its API is OpenAI-compatible, reach it as vllm
        raise RuntimeError(f"Unknown AI_BACKEND={backend_type!r}: use ollama, vllm or mock")

    return _backend


def get_vision_backend() -> InferenceBackend:
    """Get backend for vision tasks (Ollama, vLLM or Mock, singleton)."""
    global _vision_backend
    if _vision_backend is not None:
        return _vision_backend

    backend_type = os.environ.get("AI_BACKEND", "ollama").lower().strip()
    if backend_type == "mock":
        _vision_backend = MockBackend()
        return _vision_backend

    # A hosted vision model (VLLM_VISION_URL, or the chat endpoint itself) keeps
    # OCR at the provider instead of requiring an Ollama next to it.
    vllm_url = _vllm_url("vision")
    if vllm_url:
        _vision_backend = VllmBackend(vllm_url)
        logger.info("Vision backend using %s (vLLM)", vllm_url)
        return _vision_backend

    # Role-specific URL so the vision model can live on its own Ollama/GPU. The
    # URL pool is round-robin, so mixing roles into one OLLAMA_URL mis-routes.
    url = os.environ.get("OLLAMA_VISION_URL", "").strip() or os.environ.get("OLLAMA_URL", "").strip()
    if not url:
        raise RuntimeError(
            "OLLAMA_VISION_URL, VLLM_VISION_URL (or OLLAMA_URL) is required for vision OCR."
        )
    _vision_backend = OllamaBackend(url)
    logger.info("Vision backend using %s", url)
    return _vision_backend


def get_embed_backend() -> InferenceBackend:
    """Get backend for embeddings: VLLM_EMBED_URL, OLLAMA_EMBED_URL, or the main backend."""
    global _embed_backend
    if _embed_backend is not None:
        return _embed_backend

    backend_type = os.environ.get("AI_BACKEND", "ollama").lower().strip()
    if backend_type == "mock":
        _embed_backend = get_backend()  # MockBackend handles embed
    elif backend_type == "vllm":
        # A hosted embedding endpoint keeps this role at the provider too. Measured
        # over 731 chunks: Qwen3-VL-Embedding-8B truncated to 768d matches the local
        # qwen3-embedding:4b (avisiohub ADR 0006).
        vllm_embed = _vllm_url("embed")
        if vllm_embed:
            _embed_backend = VllmBackend(vllm_embed)
            logger.info("Embed backend using %s (vLLM)", vllm_embed)
            return _embed_backend
        url = os.environ.get("OLLAMA_EMBED_URL", "").strip() or os.environ.get("OLLAMA_URL", "").strip()
        if not url:
            raise RuntimeError(
                "Embeddings require Ollama (qwen3-embedding:4b, truncated to 768d). "
                "Set OLLAMA_EMBED_URL or OLLAMA_URL, or disable embeddings."
            )
        _embed_backend = OllamaBackend(url)
        logger.info("Using Ollama for embeddings (%s backend cannot serve them)", backend_type)
    else:
        # Role-specific URL so embeddings can share the vision GPU instead of
        # competing for the LLM's VRAM. Falls back to the main backend.
        embed_url = os.environ.get("OLLAMA_EMBED_URL", "").strip()
        if embed_url:
            _embed_backend = OllamaBackend(embed_url)
            logger.info("Embed backend using %s", embed_url)
        else:
            _embed_backend = get_backend()

    return _embed_backend


def get_ollama_url() -> str:
    """Legacy helper — returns first OLLAMA_URL for backwards compat."""
    return _first_url(os.environ.get("OLLAMA_URL", "")) or "http://localhost:11434"


def get_model(stage: str) -> str:
    """Resolve model name for a pipeline stage.

    Resolution order: env var → hardcoded default.
    The backend pipeline may override by passing the model name directly
    when it has read a selection from SystemSetting.
    """
    stage_upper = stage.upper()

    if _vllm_url(stage):
        val = os.environ.get(f"VLLM_{stage_upper}_MODEL", "").strip()
        if val:
            return val
        val = os.environ.get("VLLM_MODEL", "").strip()
        if val:
            return val

    val = os.environ.get(f"OLLAMA_{stage_upper}_MODEL", "").strip()
    if val:
        return val
    val = os.environ.get("OLLAMA_MODEL", "").strip()
    if val:
        return val

    return _DEFAULTS.get(stage, _DEFAULTS["chat"])


def get_num_ctx(stage: str) -> int | None:
    """Ollama context window for a stage: OLLAMA_<STAGE>_NUM_CTX env → default → None."""
    val = os.environ.get(f"OLLAMA_{stage.upper()}_NUM_CTX", "").strip()
    if val:
        try:
            return int(val)
        except ValueError:
            logger.warning("Invalid OLLAMA_%s_NUM_CTX=%r, ignoring", stage.upper(), val)
    return _NUM_CTX_DEFAULTS.get(stage)
