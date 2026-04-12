"""Redis-backed token blacklist for JWT invalidation on logout."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory fallback set (process-local, not distributed)
_fallback_blacklist: set = set()


class TokenBlacklist:
    """Stores invalidated JWT JTIs in Redis with TTL-based expiry."""

    KEY_PREFIX = "blacklist:"

    def __init__(self, redis_client=None):
        self._redis = redis_client

    def add(self, jti: str, expires_in_seconds: int) -> None:
        """Add a JTI to the blacklist."""
        key = f"{self.KEY_PREFIX}{jti}"
        try:
            self._redis.setex(key, expires_in_seconds, "1")
        except Exception as e:
            logger.warning("Redis blacklist unavailable, using in-memory fallback: %s", e)
            _fallback_blacklist.add(jti)

    def is_blacklisted(self, jti: str) -> bool:
        """Return True if the JTI is blacklisted."""
        try:
            return bool(self._redis.exists(f"{self.KEY_PREFIX}{jti}"))
        except Exception as e:
            logger.warning("Redis blacklist unavailable, checking in-memory: %s", e)
            return jti in _fallback_blacklist


# Module-level singleton — initialised lazily
_blacklist_instance: Optional[TokenBlacklist] = None


def get_token_blacklist() -> TokenBlacklist:
    """Return the global TokenBlacklist instance."""
    global _blacklist_instance
    if _blacklist_instance is None:
        try:
            import redis as redis_lib
            from policy_engine.config import settings
            r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=1)
            _blacklist_instance = TokenBlacklist(redis_client=r)
        except Exception as e:
            logger.warning("Could not connect to Redis for blacklist: %s", e)
            _blacklist_instance = TokenBlacklist(redis_client=None)
    return _blacklist_instance
