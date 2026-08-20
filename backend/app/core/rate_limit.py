"""Simple in-memory rate limiter per user for AI endpoints."""

from __future__ import annotations

import time
from collections import defaultdict
from uuid import UUID

from app.core.exceptions import AppError


class RateLimitError(AppError):
    status_code = 429

    def __init__(self) -> None:
        super().__init__("Muitas requisições. Aguarde alguns segundos antes de tentar novamente.")


class _Bucket:
    __slots__ = ("tokens", "last_refill")

    def __init__(self, capacity: int) -> None:
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()


class InMemoryRateLimiter:
    def __init__(self, *, capacity: int = 5, refill_per_second: float = 0.2) -> None:
        self._capacity = capacity
        self._refill_rate = refill_per_second
        self._buckets: dict[UUID, _Bucket] = defaultdict(lambda: _Bucket(self._capacity))

    def check(self, user_id: UUID) -> None:
        bucket = self._buckets[user_id]
        now = time.monotonic()
        elapsed = now - bucket.last_refill
        bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._refill_rate)
        bucket.last_refill = now
        if bucket.tokens < 1:
            raise RateLimitError()
        bucket.tokens -= 1


ai_rate_limiter = InMemoryRateLimiter(capacity=5, refill_per_second=0.2)
