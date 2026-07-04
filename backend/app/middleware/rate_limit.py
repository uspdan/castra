import time

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

from app.config import get_settings


async def _get_redis():
    settings = get_settings()
    return aioredis.from_url(settings.REDIS_URL)


def client_ip(request: Request) -> str:
    """Return the trusted client IP for rate-limit keying.

    When the API sits behind Nginx (the canonical deployment),
    ``request.client.host`` is the proxy hop and every external
    caller would share one bucket — R6 in the audit register.

    Trust the right-most entry in ``X-Forwarded-For`` when the
    settings say a proxy is in front; otherwise fall back to the
    socket peer. Uvicorn should also be launched with
    ``--forwarded-allow-ips`` so ``request.client.host`` itself
    becomes the original client when the immediate hop is trusted,
    but we read XFF here defensively so the limiter is correct
    even under a misconfigured runner.

    SECURITY: nginx appends the real socket peer as the *right-most*
    ``X-Forwarded-For`` entry (``$proxy_add_x_forwarded_for``); every
    token to its left is client-supplied and therefore forgeable.
    Keying an anti-abuse limit on a spoofable value would let an
    attacker mint an unlimited number of buckets by rotating a fake
    left-most token, so we take the right-most non-empty token — the
    address our own ingress observed. With more than one trusted proxy
    this buckets per upstream edge (coarser) rather than per client,
    which fails safe; the old left-most read failed open.
    """
    settings = get_settings()
    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        xff = request.headers.get("x-forwarded-for")
        if xff:
            for token in reversed(xff.split(",")):
                t = token.strip()
                if t:
                    return t
    if request.client is not None:
        return request.client.host
    return "anonymous"


async def _check_rate_limit(key: str, limit: int, window_seconds: int, request: Request) -> None:
    redis_client = await _get_redis()
    try:
        now = time.time()
        pipeline = redis_client.pipeline()
        await pipeline.zremrangebyscore(key, 0, now - window_seconds)
        await pipeline.zadd(key, {str(now): now})
        await pipeline.zcard(key)
        await pipeline.expire(key, window_seconds)
        results = await pipeline.execute()
        request_count = results[2]

        if request_count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + window_seconds)),
                    "Retry-After": str(window_seconds),
                },
            )
    finally:
        await redis_client.close()


async def flag_rate_limit(request: Request) -> None:
    user_id = getattr(request.state, "user_id", client_ip(request))
    key = f"siege:ratelimit:flag:{user_id}"
    await _check_rate_limit(key, 10, 60, request)


async def auth_rate_limit(request: Request) -> None:
    ip = client_ip(request)
    key = f"siege:ratelimit:auth:{ip}"
    await _check_rate_limit(key, 5, 60, request)


async def auth_burst_rate_limit(request: Request) -> None:
    """Stricter limit for password-reset / MFA-verify — these are
    cheap to invoke but expensive to ignore (mail bombs, brute force).
    """
    ip = client_ip(request)
    key = f"siege:ratelimit:auth-burst:{ip}"
    await _check_rate_limit(key, 5, 300, request)


async def general_rate_limit(request: Request) -> None:
    user_id = getattr(request.state, "user_id", client_ip(request))
    key = f"siege:ratelimit:general:{user_id}"
    await _check_rate_limit(key, 100, 60, request)
