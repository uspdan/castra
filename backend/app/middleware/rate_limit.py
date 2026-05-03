import time

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

from app.config import get_settings


async def _get_redis():
    settings = get_settings()
    return aioredis.from_url(settings.REDIS_URL)


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

        remaining = max(0, limit - request_count)

        if request_count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + window_seconds)),
                },
            )
    finally:
        await redis_client.close()


async def flag_rate_limit(request: Request) -> None:
    user_id = getattr(request.state, "user_id", request.client.host)
    key = f"siege:ratelimit:flag:{user_id}"
    await _check_rate_limit(key, 10, 60, request)


async def auth_rate_limit(request: Request) -> None:
    ip = request.client.host
    key = f"siege:ratelimit:auth:{ip}"
    await _check_rate_limit(key, 5, 60, request)


async def general_rate_limit(request: Request) -> None:
    user_id = getattr(request.state, "user_id", request.client.host)
    key = f"siege:ratelimit:general:{user_id}"
    await _check_rate_limit(key, 100, 60, request)
