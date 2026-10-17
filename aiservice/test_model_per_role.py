#!/usr/bin/env python3
"""VLLM_MODEL names the model of the vLLM endpoint, not of every stage (#312).

Text at a hosted vLLM with vision and embeddings on a local Ollama sent the text
model's name to the Ollama, which answered 404. Run directly or under pytest.
"""
import os

from backend import get_model

_DEMO = {
    "AI_BACKEND": "vllm",
    "VLLM_URL": "https://provider.example/v1",
    "VLLM_MODEL": "Qwen/Qwen3.8-27B",
    "OLLAMA_VISION_URL": "http://ollama:11434",
    "OLLAMA_EMBED_URL": "http://ollama:11434",
}


def _with(env: dict, stage: str) -> str:
    saved = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)
    try:
        return get_model(stage)
    finally:
        os.environ.clear()
        os.environ.update(saved)


def test_ollama_roles_ignore_vllm_model():
    assert _with(_DEMO, "chat") == "Qwen/Qwen3.8-27B"
    assert _with(_DEMO, "extract") == "Qwen/Qwen3.8-27B"
    assert _with(_DEMO, "embed") == "qwen3-embedding:4b"
    assert _with(_DEMO, "vision") == "glm-ocr:Q8_0"


def test_roles_at_the_provider_use_vllm_models():
    env = {k: v for k, v in _DEMO.items() if not k.startswith("OLLAMA_")}
    env |= {"VLLM_EMBED_URL": "https://provider.example/v1", "VLLM_EMBED_MODEL": "Qwen/Qwen3-VL-Embedding-8B"}
    assert _with(env, "vision") == "Qwen/Qwen3.8-27B"     # the chat endpoint serves vision
    assert _with(env, "embed") == "Qwen/Qwen3-VL-Embedding-8B"


if __name__ == "__main__":
    test_ollama_roles_ignore_vllm_model()
    test_roles_at_the_provider_use_vllm_models()
    print("ok")
