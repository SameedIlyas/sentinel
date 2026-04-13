"""API key hashing utilities — single source of truth for key hash operations.

Supports Argon2id (current) and SHA-256 (legacy, deprecated).
SHA-256 keys are transparently upgraded to Argon2id on first successful use.
After DEPRECATION_DEADLINE_DAYS, SHA-256 keys are refused.
"""

import hashlib
import hmac
import logging
from typing import Tuple

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Number of days before SHA-256 legacy keys are refused entirely.
#: Override via config if needed; defaults to 90.
DEPRECATION_DEADLINE_DAYS: int = 90

#: Length (hex chars) of a raw SHA-256 digest — 256 bits = 32 bytes = 64 hex chars.
_SHA256_HEX_LENGTH: int = 64

#: Prefix that identifies an Argon2id hash.
_ARGON2ID_PREFIX: str = "$argon2id$"

# Argon2id hasher with OWASP-recommended parameters (time=2, mem=64MiB, par=1).
_hasher: PasswordHasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MiB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def hash_api_key(api_key: str) -> str:
    """Hash an API key using Argon2id.

    Args:
        api_key: Raw plaintext API key.

    Returns:
        Argon2id hash string (starts with ``$argon2id$``).
    """
    return _hasher.hash(api_key)


def verify_api_key_hash(
    api_key: str,
    stored_hash: str,
) -> Tuple[bool, bool]:
    """Verify an API key against a stored hash.

    Supports both Argon2id (current) and SHA-256 (legacy) formats.

    Args:
        api_key: Raw plaintext API key provided by the caller.
        stored_hash: Hash value retrieved from the database.

    Returns:
        ``(is_valid, needs_rehash)`` where:

        - ``is_valid`` — ``True`` if the key matches the stored hash.
        - ``needs_rehash`` — ``True`` if the stored hash is in legacy SHA-256
          format and must be upgraded to Argon2id.

    Hash format detection:
        - ``$argon2id$…`` → Argon2id verification.
        - 64-char lowercase hex string → SHA-256 legacy verification.
        - Anything else → treated as unknown/invalid; returns ``(False, False)``.
    """
    if not stored_hash:
        return False, False

    if stored_hash.startswith(_ARGON2ID_PREFIX):
        return _verify_argon2(api_key, stored_hash)

    if _is_sha256_hex(stored_hash):
        return _verify_sha256(api_key, stored_hash)

    logger.warning("Unknown hash format encountered (len=%d)", len(stored_hash))
    return False, False


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _verify_argon2(api_key: str, stored_hash: str) -> Tuple[bool, bool]:
    """Verify key against an Argon2id hash.  Never signals rehash."""
    try:
        _hasher.verify(stored_hash, api_key)
        return True, False
    except VerifyMismatchError:
        return False, False
    except (VerificationError, InvalidHashError) as exc:
        logger.error("Argon2 verification error: %s", exc)
        return False, False


def _verify_sha256(api_key: str, stored_hash: str) -> Tuple[bool, bool]:
    """Verify key against a legacy SHA-256 hex digest.

    Returns (True, True) on match — signalling that the caller must rehash.
    """
    expected = hashlib.sha256(api_key.encode()).hexdigest()
    if hmac.compare_digest(expected, stored_hash):
        return True, True
    return False, False


def _is_sha256_hex(value: str) -> bool:
    """Return True if *value* looks like a raw SHA-256 hex digest."""
    if len(value) != _SHA256_HEX_LENGTH:
        return False
    try:
        int(value, 16)
        return True
    except ValueError:
        return False
