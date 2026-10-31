import extraction

# other tests here assign extraction.call_ollama_text for good; keep the real one
_REAL = extraction.call_ollama_text


def test_the_language_is_repeated_after_the_document(monkeypatch):
    """Kassen letters came back in English with the language line only at the top."""
    seen = {}

    class _Backend:
        def chat(self, model, messages, **kw):
            seen["prompt"] = messages[0]["content"]
            return '{"summary": "x"}'

    monkeypatch.setattr(extraction, "get_backend", lambda: _Backend())
    _REAL("Brief der Kasse", "m", "de")
    assert seen["prompt"].index("--- END ---") < seen["prompt"].rindex("in German.")
