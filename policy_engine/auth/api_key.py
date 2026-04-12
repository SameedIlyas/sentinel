"""API Key authentication.

Uses Argon2id for new hashes.  Legacy SHA-256 keys are transparently upgraded
to Argon2id on first successful authentication (dual-read grace period).
After DEPRECATION_DEADLINE_DAYS, SHA-256 keys are refused with an explicit
"Please re-issue your API key" error.
"""

import hashlib
import logging
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from policy_engine.database import get_db
from policy_engine.models.api_key import APIKey
from policy_engine.config import settings
from policy_engine.auth.key_hashing import (
    hash_api_key,
    verify_api_key_hash,
    DEPRECATION_DEADLINE_DAYS,
)

logger = logging.getLogger(__name__)

# Re-export hash_api_key so existing callers of this module keep working.
__all__ = ["hash_api_key", "verify_api_key", "get_current_agent", "_verify_api_key_logic"]


def _verify_api_key_logic(x_api_key: str, db: Session) -> str:
    """Core API-key verification logic (extracted for direct testability).

    Performs dual-read (Argon2id + SHA-256 fallback), transparent upgrade,
    and deadline enforcement.

    Args:
        x_api_key: Raw API key provided by the caller.
        db: Active database session.

    Returns:
        ``agent_id`` associated with the verified key.

    Raises:
        HTTPException 401: On invalid, inactive, expired, or deadline-exceeded key.
    """
    # -------------------------------------------------------------------
    # 1. Try Argon2id lookup first (fast path for already-upgraded keys).
    #    Because Argon2id hashes are salted, we cannot look up by hash —
    #    we must search by candidate keys (via agent_id or scan).
    #    Instead we retrieve all *active* records and verify each one.
    #    For performance, we first try a direct SHA-256 lookup, then fall
    #    through to an Argon2id scan.
    # -------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Path A: SHA-256 lookup (O(1) for legacy keys still in SHA-256 format)
    # ------------------------------------------------------------------
    sha256_candidate = hashlib.sha256(x_api_key.encode()).hexdigest()
    api_key_record = db.query(APIKey).filter(APIKey.key == sha256_candidate).first()

    if api_key_record:
        # Validate active / expiry before deadline check
        _assert_active_and_not_expired(api_key_record)

        # Deadline enforcement: refuse if key is too old
        _assert_sha256_within_deadline(api_key_record)

        # Transparent upgrade: rehash with Argon2id and update the DB row
        new_hash = hash_api_key(x_api_key)
        agent_id = api_key_record.agent_id
        try:
            api_key_record.key = new_hash
            api_key_record.last_used = datetime.utcnow()
            db.commit()
            logger.warning(
                "API key for agent %s was using legacy SHA-256 hash — "
                "upgraded to Argon2id transparently.",
                agent_id,
            )
        except IntegrityError:
            db.rollback()
            # Another concurrent request already upgraded this key — that's fine
            logger.debug(
                "Concurrent rehash detected for key belonging to agent %s — skipping", agent_id
            )
        return agent_id

    # ------------------------------------------------------------------
    # Path B: Argon2id lookup — scan active keys and verify each one.
    #         In practice there are few keys per agent; this is acceptable.
    # ------------------------------------------------------------------
    active_records = db.query(APIKey).filter(APIKey.is_active.is_(True)).all()
    for record in active_records:
        is_valid, needs_rehash = verify_api_key_hash(x_api_key, record.key)
        if not is_valid:
            continue

        # Found a match
        _assert_active_and_not_expired(record)

        if needs_rehash:
            # SHA-256 match found via scan (unusual path; same deadline logic)
            _assert_sha256_within_deadline(record)
            new_hash = hash_api_key(x_api_key)
            agent_id = record.agent_id
            try:
                record.key = new_hash
                record.last_used = datetime.utcnow()
                db.commit()
                logger.warning(
                    "API key for agent %s upgraded from SHA-256 to Argon2id (scan path).",
                    agent_id,
                )
            except IntegrityError:
                db.rollback()
                logger.debug(
                    "Concurrent rehash detected for key belonging to agent %s — skipping", agent_id
                )
            return agent_id

        # Valid Argon2id key
        record.last_used = datetime.utcnow()
        db.commit()
        return record.agent_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )


def _assert_active_and_not_expired(record: APIKey) -> None:
    """Raise 401 if the key record is inactive or past its expiry."""
    if not record.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is inactive",
        )
    if record.expires_at and record.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )


def _assert_sha256_within_deadline(record: APIKey) -> None:
    """Raise 401 with re-issuance message if SHA-256 key is past the deadline."""
    if record.created_at is None:
        return
    deadline = record.created_at + timedelta(days=DEPRECATION_DEADLINE_DAYS)
    if datetime.utcnow() > deadline:
        logger.error(
            "API key for agent %s is a SHA-256 key that exceeded the "
            "%d-day deprecation deadline.  Refusing authentication.",
            record.agent_id,
            DEPRECATION_DEADLINE_DAYS,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Your API key uses a deprecated hash format that has exceeded "
                "the grace period.  Please re-issue your API key."
            ),
        )


async def verify_api_key(
    x_api_key: str = Header(..., alias=settings.API_KEY_HEADER),
    db: Session = Depends(get_db),
) -> str:
    """FastAPI dependency: verify API key and return the associated agent_id.

    Args:
        x_api_key: Raw API key from the request header.
        db: Database session (injected by FastAPI).

    Returns:
        ``agent_id`` associated with the verified key.

    Raises:
        HTTPException 401: On invalid, inactive, expired, or deadline-exceeded key.
    """
    return _verify_api_key_logic(x_api_key, db)


async def get_current_agent(agent_id: str = Depends(verify_api_key)) -> str:
    """FastAPI dependency: return the authenticated agent ID."""
    return agent_id
