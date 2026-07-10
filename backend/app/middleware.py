"""Rate limiting & security middleware."""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter — per-IP sliding window.

    Production: use Redis-based rate limiter (e.g., slowapi + redis).
    """

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self._max = max_requests
        self._window = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Skip health check
        if request.url.path == "/health":
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        # Clean old entries
        bucket = self._buckets[ip]
        cutoff = now - self._window
        bucket[:] = [t for t in bucket if t > cutoff]

        if len(bucket) >= self._max:
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后重试")

        bucket.append(now)
        return await call_next(request)
