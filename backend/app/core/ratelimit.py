"""Per-IP rate limiting for the auth endpoints (#109).

Account lockout alone stops guessing at *one* account; it does nothing about
spraying one common password across many accounts, and it turns into a denial-
of-service tool if an attacker can lock a known caregiver out at will.

Redis INCR with a TTL — a fixed window, not a sliding one. That is imprecise at
the window edge (an attacker can get 2x the budget by straddling it) and that
is fine: the point is to make automated guessing slow, not to be exact.

Fails OPEN: if Redis is unreachable, logins still work. A rate limiter that
locks everyone out when its own backing store hiccups is worse than the attack
it prevents.
"""

import logging

from fastapi import HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)


def client_ip(request: Request) -> str:
    """The caller's IP. Caddy sits in front and sets X-Forwarded-For."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        # left-most entry is the original client; the rest are proxies
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def enforce(key: str, limit: int, window_seconds: int) -> None:
    """Raise 429 once `key` has been seen `limit` times inside the window."""
    if not settings.rate_limit_enabled:
        return
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url)
        try:
            hits = await r.incr(key)
            if hits == 1:
                await r.expire(key, window_seconds)
            ttl = await r.ttl(key)
        finally:
            await r.aclose()
    except Exception as e:  # noqa: BLE001 — see module docstring: fail open
        logger.warning("rate limit unavailable (%s), allowing request", e)
        return

    if hits > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again later.",
            headers={"Retry-After": str(max(ttl, 1))},
        )
