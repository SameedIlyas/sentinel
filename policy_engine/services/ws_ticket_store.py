"""Single-use, short-lived ticket store for WebSocket handshakes.

CRIT-013 — historically the dashboard passed a long-lived JWT in the
``?token=`` query parameter of the WebSocket URL. URLs are written to
proxy access logs, the browser History API, OS process listings, and
sometimes to APM trace headers, so a JWT in the URL is a JWT in many
places that should never see one.

The fix is a server-issued ticket:

1. The dashboard POSTs to ``/v1/ws/ticket`` with its Authorization
   header (JWT in a header, not the URL) and receives an opaque
   ticket string.
2. The dashboard opens the WebSocket with ``?ticket=<ticket>``.
3. The server atomically exchanges ticket -> user_id, deleting the
   ticket on read (single-use).
4. Tickets expire after 30 seconds — long enough for the round-trip,
   too short to be useful to anyone who scrapes a log.

Tickets are stored in Redis when available so the design supports
multi-replica deployments. In tests and dev we fall back to a process-
local dict; a startup-guard refuses to start in production with the
fallback active so we never ship the wrong store to prod.
"""
from __future__ import annotations

import logging
import secrets
import threading
import time
from typing import Optional

try:
    import redis  # type: ignore
    from redis.exceptions import RedisError, ConnectionError as RedisConnError
except ImportError:  # pragma: no cover — Redis is a runtime dep
    redis = None  # type: ignore
    RedisError = Exception  # type: ignore
    RedisConnError = Exception  # type: ignore

from policy_engine.config import settings


logger = logging.getLogger(__name__)

# Tickets live for at most this many seconds. Long enough for a normal
# fetch-then-connect round-trip; short enough that a leaked ticket is
# useless within seconds.
TICKET_TTL_SECONDS = 30

# 32 bytes of CSPRNG output, base64-url encoded -> ~43 char opaque token.
_TICKET_BYTES = 32

# Redis key prefix so the ticket store can share a Redis db with caches
# without colliding.
_REDIS_KEY_PREFIX = "ws_ticket:"


class _InMemoryStore:
    """Thread-safe fallback store. Only acceptable in dev / tests."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def setex(self, ticket: str, user_id: str, ttl_seconds: int) -> None:
        expiry = time.time() + ttl_seconds
        with self._lock:
            self._data[ticket] = (user_id, expiry)

    def getdel(self, ticket: str) -> Optional[str]:
        with self._lock:
            entry = self._data.pop(ticket, None)
        if entry is None:
            return None
        user_id, expiry = entry
        if expiry < time.time():
            return None
        return user_id


class WSTicketStore:
    """Issue and atomically consume single-use WebSocket tickets."""

    def __init__(self, *, redis_client: Optional["redis.Redis"] = None) -> None:
        self._redis = redis_client
        self._fallback = _InMemoryStore()
        # Detect once at construction whether Redis is reachable; we
        # re-detect on each call to handle restart-after-redis-bounce.

    @property
    def using_in_memory_fallback(self) -> bool:
        """True if the store is using the in-memory dict.

        Production deployments MUST surface this as a hard error at
        startup — see :func:`_ensure_production_safe`.
        """
        return self._redis is None

    def issue(self, user_id: str) -> str:
        """Mint a fresh single-use ticket bound to ``user_id``."""
        if not user_id:
            raise ValueError("user_id required to issue a WS ticket")

        ticket = secrets.token_urlsafe(_TICKET_BYTES)

        if self._redis is not None:
            try:
                self._redis.setex(
                    _REDIS_KEY_PREFIX + ticket,
                    TICKET_TTL_SECONDS,
                    user_id,
                )
                return ticket
            except (RedisError, RedisConnError) as e:
                # Fall through to the in-memory store but log loudly.
                logger.warning(
                    "WSTicketStore: Redis SETEX failed (%s); using in-memory "
                    "fallback for this ticket. This is unsafe in multi-replica "
                    "deployments.",
                    e,
                )

        self._fallback.setex(ticket, user_id, TICKET_TTL_SECONDS)
        return ticket

    def consume(self, ticket: str) -> Optional[str]:
        """Atomically exchange a ticket for the bound ``user_id``.

        Returns ``None`` if the ticket is unknown, expired, or already
        consumed. The single-use contract is enforced via Redis
        ``GETDEL`` (one round-trip, atomic) or the in-memory store's
        ``pop`` under a lock.
        """
        if not ticket:
            return None

        if self._redis is not None:
            try:
                # GETDEL was added in Redis 6.2 — most managed Redis
                # services support it. Fall back to GET+DEL in a pipeline
                # if not (still atomic on a single connection).
                val = self._redis.getdel(_REDIS_KEY_PREFIX + ticket)
                if val is None:
                    return None
                # decode_responses=True is on for our Redis client, so
                # this is already a str — but be defensive.
                if isinstance(val, bytes):
                    val = val.decode("utf-8")
                return val
            except AttributeError:
                # Redis < 6.2 or fakeredis without GETDEL
                try:
                    with self._redis.pipeline() as pipe:
                        pipe.get(_REDIS_KEY_PREFIX + ticket)
                        pipe.delete(_REDIS_KEY_PREFIX + ticket)
                        got, _ = pipe.execute()
                    if got is None:
                        return None
                    return got.decode("utf-8") if isinstance(got, bytes) else got
                except (RedisError, RedisConnError) as e:
                    logger.warning(
                        "WSTicketStore: Redis fallback consume failed: %s", e
                    )
            except (RedisError, RedisConnError) as e:
                logger.warning(
                    "WSTicketStore: Redis GETDEL failed: %s. The in-memory "
                    "fallback is consulted next.",
                    e,
                )

        return self._fallback.getdel(ticket)


_INSTANCE: Optional[WSTicketStore] = None
_INSTANCE_LOCK = threading.Lock()


def _build_redis_client() -> Optional["redis.Redis"]:
    if redis is None:
        return None
    try:
        client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        return client
    except (RedisError, RedisConnError, Exception) as e:
        logger.warning(
            "WSTicketStore: cannot reach Redis at %s (%s). The in-memory "
            "fallback is in use — production deployments must fail startup.",
            settings.REDIS_URL,
            e,
        )
        return None


def get_ws_ticket_store() -> WSTicketStore:
    """Return the process-wide ticket store, building it on first use."""
    global _INSTANCE
    if _INSTANCE is not None:
        return _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = WSTicketStore(redis_client=_build_redis_client())
    return _INSTANCE


def reset_ws_ticket_store_for_tests() -> None:
    """Reset the singleton so tests can swap Redis backends cleanly."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = None


def ensure_production_safe() -> None:
    """Fail loudly if production is running on the in-memory fallback.

    Called from :mod:`policy_engine.main` startup so a misconfigured
    prod env can't silently degrade to a non-shared ticket store.
    """
    if settings.APP_ENV != "production":
        return
    store = get_ws_ticket_store()
    if store.using_in_memory_fallback:
        raise RuntimeError(
            "WSTicketStore is using the in-memory fallback in production. "
            "Multi-replica deployments require a shared Redis store — "
            "configure REDIS_URL and verify connectivity before starting."
        )
