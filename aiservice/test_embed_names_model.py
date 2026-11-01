#!/usr/bin/env python3
"""/embed names the model behind the vectors, so the backend can record it (#238).

Run directly or under pytest.
"""
import asyncio

import main


class _Fake:
    def embed(self, model, texts, dims):
        return [[0.0] * dims for _ in texts]


def test_embed_returns_the_model():
    main.get_embed_backend, saved = (lambda: _Fake()), main.get_embed_backend
    main.get_model, saved_model = (lambda stage: "embedder-x"), main.get_model
    try:
        body = asyncio.run(main.embed_endpoint(main.EmbedRequest(texts=["a", "b"])))
    finally:
        main.get_embed_backend, main.get_model = saved, saved_model
    assert body["model"] == "embedder-x"
    assert len(body["embeddings"]) == 2


if __name__ == "__main__":
    test_embed_returns_the_model()
    print("ok")
