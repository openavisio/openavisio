"""A rate limit at the AI provider delays work instead of failing it (#374)."""

import uuid
from types import SimpleNamespace

import httpx
import pytest
from celery.exceptions import Retry

from app.workers import pipeline
from tests.test_chat_context import _setup


def _busy_response(*a, **kw):
    return httpx.Response(429, headers={"retry-after": "2"}, request=httpx.Request("POST", "http://ai/x"))


class _Busy:
    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, *a, **kw):
        return _busy_response()


class _Task:
    def __init__(self, retries):
        self.request = SimpleNamespace(retries=retries)
        self.countdown = None

    def retry(self, countdown, max_retries):
        self.countdown = countdown
        return Retry()


def test_a_429_waits_longer_each_time():
    pauses = []
    for n in range(pipeline._BUSY_RETRIES):
        task = _Task(n)
        with pytest.raises(Retry):
            pipeline._wait_if_busy(task, _busy_response())
        pauses.append(task.countdown)
    # 15 s doubling to the 4 min cap, plus up to 10 s jitter
    assert 15 <= pauses[0] <= 25 and 240 <= pauses[-1] <= 250
    assert pauses[4] > pauses[0]


def test_retries_end_and_other_statuses_pass():
    pipeline._wait_if_busy(_Task(pipeline._BUSY_RETRIES), _busy_response())
    ok = httpx.Response(500, request=httpx.Request("POST", "http://ai/x"))
    pipeline._wait_if_busy(_Task(0), ok)


def test_a_busy_provider_does_not_fail_the_document(monkeypatch):
    updates = []

    async def get_doc(_):
        return SimpleNamespace(storage_path="x", patient_id=uuid.uuid4(), encrypted_dek=None,
                               file_name="a.pdf", content_type="application/pdf")

    async def update_doc(_, **kw):
        updates.append(kw)

    async def kek(_):
        return b"k"

    async def decrypt(*_):
        return b"%PDF"

    monkeypatch.setattr(pipeline, "_get_doc", get_doc)
    monkeypatch.setattr(pipeline, "_update_doc", update_doc)
    monkeypatch.setattr(pipeline, "_patient_kek", kek)
    monkeypatch.setattr(pipeline, "_decrypt_file", decrypt)
    monkeypatch.setattr(httpx, "AsyncClient", _Busy)

    with pytest.raises(Retry):
        pipeline.ocr_stage.run(str(uuid.uuid4()))
    assert all(u.get("processing_status") != "failed" for u in updates), updates


async def test_a_busy_provider_is_a_429_in_the_chat_and_writes_nothing(client, db, monkeypatch):
    patient, _, headers = await _setup(client, db, "busy@test.com")
    monkeypatch.setattr(httpx, "AsyncClient", _Busy)

    r = await client.post(f"/api/patients/{patient.id}/chat", json={"question": "Wann?"}, headers=headers)
    assert r.status_code == 429, r.text

    h = await client.get(f"/api/patients/{patient.id}/chat/history", headers=headers)
    assert h.json()["messages"] == []
