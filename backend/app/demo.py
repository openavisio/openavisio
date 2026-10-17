"""The public demo is read-only: every visitor shares one login, so anything
one of them writes, every other one reads until the nightly reset. Writes are refused but for
signing in, the bundled sample and the chat, whose history is not kept; every IP has a budget.
"""
import re

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.ratelimit import client_ip, enforce

ALLOWED = [
    ("POST", re.compile(r"/api/auth/(login|refresh)")),
    ("POST", re.compile(r"/api/patients/[^/]+/documents/upload")),
    ("DELETE", re.compile(r"/api/documents/[^/]+")),  # the sample only, documents.py checks
    ("POST", re.compile(r"/api/patients/[^/]+/chat")),
]


async def read_only(request: Request, call_next):
    if not settings.demo_locked_upload_sha256:
        return await call_next(request)
    if request.url.path.startswith("/api/"):
        try:
            # ponytail: a flood budget per IP, not DDoS protection; that belongs in front of the host
            await enforce(f"rl:demo:ip:{client_ip(request)}", limit=600, window_seconds=300)
        except HTTPException as e:  # raised inside a middleware it would be a 500
            return JSONResponse({"detail": e.detail}, status_code=e.status_code, headers=e.headers)
    if request.method in ("GET", "HEAD", "OPTIONS") or any(
        request.method == m and p.fullmatch(request.url.path) for m, p in ALLOWED
    ):
        return await call_next(request)
    return JSONResponse({"detail": "This is a public demo, it is read-only."}, status_code=403)
