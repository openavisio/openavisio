#!/usr/bin/env python3
"""A rate limit at the provider reaches the caller as 429 with Retry-After (#374).

Before, the broad handlers turned it into a 500, a 200 with an error, or a silent
Tesseract fallback, and the pipeline marked the document failed. Run directly or
under pytest.
"""
import asyncio

import httpx
from openai import RateLimitError

import main


def _busy(*_, **__):
    request = httpx.Request("POST", "https://provider/v1/chat/completions")
    response = httpx.Response(429, headers={"retry-after": "2"}, request=request)
    raise RateLimitError("Error code: 429", response=response, body=None)


def _raises_rate_limit(call) -> bool:
    try:
        asyncio.run(call())
    except RateLimitError:
        return True
    return False


def test_extraction_passes_the_rate_limit_on():
    saved = main.extract_entities_from_text
    main.extract_entities_from_text = _busy
    try:
        assert _raises_rate_limit(lambda: main.extract_entities_endpoint(main.ExtractEntitiesRequest(text="x")))
    finally:
        main.extract_entities_from_text = saved


def test_ocr_does_not_fall_back_to_tesseract_on_a_rate_limit():
    from starlette.datastructures import UploadFile
    import io

    saved = main.vision_ocr
    main.vision_ocr = _busy
    try:
        upload = UploadFile(io.BytesIO(b"%PDF-1.4"), filename="a.pdf", headers={"content-type": "application/pdf"})
        assert _raises_rate_limit(lambda: main.ocr_endpoint(upload))
    finally:
        main.vision_ocr = saved


def test_handler_answers_429_with_retry_after():
    try:
        _busy()
    except RateLimitError as exc:
        resp = asyncio.run(main.provider_busy(None, exc))
    assert resp.status_code == 429 and resp.headers["retry-after"] == "2"


if __name__ == "__main__":
    test_extraction_passes_the_rate_limit_on()
    test_ocr_does_not_fall_back_to_tesseract_on_a_rate_limit()
    test_handler_answers_429_with_retry_after()
    print("ok")
