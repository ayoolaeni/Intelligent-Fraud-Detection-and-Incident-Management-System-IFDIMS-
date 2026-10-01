"""Simple in-memory sliding-window rate limiter (Section 13, docs/DECISIONS.md D4).

Not distributed-safe; acceptable for the single backend container this
project ships (see D4).
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from app.core.errors import ApiError


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.time()
        hits = self._hits[key]
        while hits and hits[0] <= now - self.window_seconds:
            hits.popleft()
        if len(hits) >= self.max_requests:
            raise ApiError(429, "RATE_LIMITED", "Too many requests, please slow down")
        hits.append(now)


login_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)
scoring_rate_limiter = RateLimiter(max_requests=200, window_seconds=1)
