#!/usr/bin/env python3
"""A prompt that does not fit the context window fails instead of yielding a cut extraction (#239).

Ollama trims an over-long prompt to exactly num_ctx tokens and answers anyway;
vLLM refuses with "maximum context length". Run directly or under pytest.
"""
from types import SimpleNamespace

import main
from backend import ContextOverflow, OllamaBackend, VllmBackend


class _Ollama:
    def __init__(self, used):
        self.used = used

    def chat(self, **_):
        return SimpleNamespace(prompt_eval_count=self.used, message=SimpleNamespace(content="{}"))


def _ollama(used):
    b = OllamaBackend("http://ollama:11434")
    b._clients = {"http://ollama:11434": _Ollama(used)}
    return b


def test_ollama_prompt_that_filled_the_window_fails():
    try:
        _ollama(32768).chat("m", [{"role": "user", "content": "x"}], num_ctx=32768)
    except ContextOverflow:
        return
    raise AssertionError("a cut prompt must not pass")


def test_ollama_prompt_that_fit_passes():
    assert _ollama(32767).chat("m", [{"role": "user", "content": "x"}], num_ctx=32768) == "{}"


def test_vllm_refusal_becomes_context_overflow():
    class _Refuse:
        def create(self, **_):
            raise RuntimeError("This model's maximum context length is 32768 tokens. However, you requested 40000 tokens.")

    client = SimpleNamespace(chat=SimpleNamespace(completions=_Refuse()))
    try:
        VllmBackend._create(None, client, "m", [], {})
    except ContextOverflow:
        return
    raise AssertionError("a refusal for length must surface as ContextOverflow")


def test_extraction_endpoint_names_the_cause():
    import asyncio

    saved = main.extract_entities_from_text

    def too_long(*_, **__):
        raise ContextOverflow("prompt filled the whole context window (32768 of 32768 tokens) and was truncated")

    main.extract_entities_from_text = too_long
    try:
        req = main.ExtractEntitiesRequest(text="x")
        result = asyncio.run(main.extract_entities_endpoint(req))
    finally:
        main.extract_entities_from_text = saved
    assert result.error == "document_too_long" and result.entities is None


if __name__ == "__main__":
    test_ollama_prompt_that_filled_the_window_fails()
    test_ollama_prompt_that_fit_passes()
    test_vllm_refusal_becomes_context_overflow()
    test_extraction_endpoint_names_the_cause()
    print("ok")
