#!/usr/bin/env python3
"""`reasoning_effort="none"` must never kill a request (IONOS gpt-oss, 2026-07-28).

Harmony answers 400 instead of ignoring the field, so a lever meant to be
silently inert took the whole extraction with it. Run directly or under pytest.
"""
from backend import VllmBackend


class _Client:
    """Rejects reasoning_effort="none" the way Harmony does, records what it got."""

    def __init__(self):
        self.seen = []
        self.chat = type("_", (), {"completions": self})()

    def create(self, **kw):
        self.seen.append(kw.get("reasoning_effort"))
        if kw.get("reasoning_effort") == "none":
            raise RuntimeError("Error code: 400 - Harmony does not support reasoning_effort='none'")
        return "ok"


def test_none_falls_back_to_low():
    client = _Client()
    backend = VllmBackend.__new__(VllmBackend)          # no network, no pool
    assert backend._create(client, "gpt-oss", [], {"reasoning_effort": "none"}) == "ok"
    assert client.seen == ["none", "low"]


def test_other_errors_are_not_swallowed():
    class _Broken(_Client):
        def create(self, **kw):
            raise RuntimeError("Error code: 429 - rate limited")

    try:
        VllmBackend.__new__(VllmBackend)._create(_Broken(), "m", [], {"reasoning_effort": "none"})
    except RuntimeError as exc:
        assert "429" in str(exc)
    else:
        raise AssertionError("a 429 must propagate, not become a retry")



# --- images over the OpenAI protocol (#246) ---

def test_images_become_content_parts_on_the_last_user_message():
    msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "Text Recognition:"}]
    out = VllmBackend._with_images(msgs, [b"\x89PNG-a", b"\x89PNG-b"])
    assert out[0] == {"role": "system", "content": "sys"}          # untouched
    parts = out[1]["content"]
    assert [p["type"] for p in parts] == ["image_url", "image_url", "text"]
    assert parts[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert parts[-1]["text"] == "Text Recognition:"
    assert msgs[1]["content"] == "Text Recognition:"                # caller's list not mutated


# --- Matryoshka truncation when a provider rejects `dimensions` (#238) ---

def test_truncate_cuts_and_renormalises():
    out = VllmBackend._truncate([[3.0, 4.0, 99.0, 99.0]], 2)
    assert out == [[0.6, 0.8]]


def test_embed_falls_back_to_truncation_on_a_dimensions_error():
    class _C:
        def __init__(self):
            self.calls = []
            self.embeddings = self

        def create(self, **kw):
            self.calls.append(kw.get("dimensions"))
            if kw.get("dimensions"):
                raise RuntimeError("Received an unhandled error: dimensions is not supported")
            return type("_", (), {"data": [type("_", (), {"embedding": [3.0, 4.0, 9.0]})()]})()

    b = VllmBackend.__new__(VllmBackend)
    c = _C()
    assert b._embed_one(c, "qwen", ["text"], 2) == [[0.6, 0.8]]
    assert c.calls == [2, None]


if __name__ == "__main__":
    test_none_falls_back_to_low()
    test_other_errors_are_not_swallowed()
    test_images_become_content_parts_on_the_last_user_message()
    test_truncate_cuts_and_renormalises()
    test_embed_falls_back_to_truncation_on_a_dimensions_error()
    print("ok")
