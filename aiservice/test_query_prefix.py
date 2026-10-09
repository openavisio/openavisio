#!/usr/bin/env python3
"""Query-instruction prefixes per embedding model (#237).

Getting this wrong is invisible: retrieval keeps working and quietly returns
worse chunks. Run directly (`python3 aiservice/test_query_prefix.py`) or under
pytest — no fixtures, no framework needed.
"""
import main

Q = ["Welche Diagnosen sind dokumentiert?"]


def test_qwen_instruction_is_language_specific():
    assert main._as_query(Q, "qwen3-embedding:4b", "de")[0].startswith("Instruct: Finde Abschnitte")
    assert main._as_query(Q, "qwen3-embedding:4b", "en")[0].startswith("Instruct: Find passages")


def test_vendor_named_qwen_embedding_still_matches():
    """Hosted providers serve it as Qwen3-VL-Embedding-8B, which does not
    contain 'qwen3-embedding'. Losing the prefix here would be silent."""
    main._warned_unprefixed.clear()
    assert main._as_query(Q, "Qwen3-VL-Embedding-8B", "de")[0].startswith("Instruct: Finde")
    assert not main._warned_unprefixed


def test_nomic_prefix_is_a_token_not_a_sentence():
    for lang in ("de", "en"):
        assert main._as_query(Q, "nomic-embed-text:latest", lang) == ["search_query: " + Q[0]]


def test_bge_m3_gets_no_prefix_and_no_warning():
    """Empty means 'this model wants none', which is a decision and must not
    look like a missing entry."""
    main._warned_unprefixed.clear()
    assert main._as_query(Q, "bge-m3", "de") == Q
    assert not main._warned_unprefixed


def test_unknown_model_passes_through_and_warns_once():
    main._warned_unprefixed.clear()
    assert main._as_query(Q, "some-new-embedder", "de") == Q
    main._as_query(Q, "some-new-embedder", "en")
    assert main._warned_unprefixed == {"some-new-embedder"}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
