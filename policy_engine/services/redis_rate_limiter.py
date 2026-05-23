"""Redis-backed sliding window rate limiter with in-memory fallback."""

import time
import logging
from collections import defaultdict
from typing import Tuple

logger = logging.getLogger(__name__)

_FALLBACK_REQUESTS: dict = defaultdict(list)


class RedisRateLimiter:
    """Distributed sliding window rate limiter using Redis atomic pipeline.

    Algorithm (check-then-add):
      1. ZREMRANGEBYSCORE  — purge entries older than 60s
      2. ZCARD             — count current requests in window
      3. If count >= limit → reject (do NOT add)
      4. ZADD              — record this request
      5. Return (True, limit - count - 1)
    """

    _CIRCUIT_COOLDOWN_SECONDS = 30

    def __init__(self, redis_client, requests_per_minute: int, fallback_enabled: bool = True):
        self._redis = redis_client
        self.requests_per_minute = requests_per_minute
        self.fallback_enabled = fallback_enabled
        self._redis_dead_until: float = 0.0

    def _build_key(self, identifier: str) -> str:
        return f"rate_limit:{identifier}"

    def is_allowed(self, identifier: str) -> Tuple[bool, int]:
        """Check if request is allowed. Returns (allowed, remaining_after_this_request)."""
        if self._redis is None or time.time() < self._redis_dead_until:
            if self.fallback_enabled:
                return self._fallback_check(identifier)
            return True, self.requests_per_minute
        try:
            return self._redis_check(identifier)
        except Exception as e:
            self._redis_dead_until = time.time() + self._CIRCUIT_COOLDOWN_SECONDS
            logger.warning(
                "Redis rate limiter unavailable, using fallback for %ss: %s",
                self._CIRCUIT_COOLDOWN_SECONDS, e,
            )
            if self.fallback_enabled:
                return self._fallback_check(identifier)
            return True, self.requests_per_minute

    def _redis_check(self, identifier: str) -> Tuple[bool, int]:
        key = self._build_key(identifier)
        now = time.time()
        window_start = now - 60

        # Step 1 & 2: purge old entries, get current count
        with self._redis.pipeline() as pipe:
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.expire(key, 60)
            results = pipe.execute()

        current_count = results[1]  # count BEFORE adding current request

        if current_count >= self.requests_per_minute:
            return False, 0

        # Step 3: record this request
        self._redis.zadd(key, {str(now): now})
        remaining = self.requests_per_minute - current_count - 1
        return True, max(0, remaining)

    def _fallback_check(self, identifier: str) -> Tuple[bool, int]:
        now = time.time()
        window_start = now - 60
        _FALLBACK_REQUESTS[identifier] = [
            t for t in _FALLBACK_REQUESTS[identifier] if t > window_start
        ]
        current_count = len(_FALLBACK_REQUESTS[identifier])
        if current_count >= self.requests_per_minute:
            return False, 0
        _FALLBACK_REQUESTS[identifier].append(now)
        remaining = self.requests_per_minute - current_count - 1
        return True, max(0, remaining)
