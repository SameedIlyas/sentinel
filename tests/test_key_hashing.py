"""Tests for Argon2 API key hashing — Task 3.1.

TDD RED phase: all tests written before implementation.
"""
import hashlib
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# key_hashing module — unit tests
# ---------------------------------------------------------------------------

class TestHashApiKey:
    def test_hash_api_key_returns_argon2id_format(self):
        """hash_api_key() must return a string starting with '$argon2id$'."""
        from policy_engine.auth.key_hashing import hash_api_key

        result = hash_api_key("my-super-secret-api-key")
        assert result.startswith("$argon2id$"), (
            f"Expected Argon2id hash prefix, got: {result[:20]}"
        )

    def test_hash_api_key_produces_unique_salts(self):
        """Two calls with the same key must produce different hashes (unique salts)."""
        from policy_engine.auth.key_hashing import hash_api_key

        h1 = hash_api_key("same-key")
        h2 = hash_api_key("same-key")
        assert h1 != h2, "Argon2id must use unique salts per hash"

    def test_hash_api_key_non_empty_result(self):
        """hash_api_key() must return a non-empty string."""
        from policy_engine.auth.key_hashing import hash_api_key

        result = hash_api_key("any-key")
        assert isinstance(result, str)
        assert len(result) > 0


class TestVerifyArgon2Hash:
    def test_verify_argon2_hash_returns_valid_no_rehash(self):
        """Verifying a valid Argon2id hash returns (True, False)."""
        from policy_engine.auth.key_hashing import hash_api_key, verify_api_key_hash

        raw_key = "correct-password"
        stored_hash = hash_api_key(raw_key)

        is_valid, needs_rehash = verify_api_key_hash(raw_key, stored_hash)
        assert is_valid is True
        assert needs_rehash is False

    def test_verify_argon2_hash_wrong_key_returns_invalid(self):
        """Wrong key against Argon2id hash returns (False, False)."""
        from policy_engine.auth.key_hashing import hash_api_key, verify_api_key_hash

        stored_hash = hash_api_key("correct-password")
        is_valid, needs_rehash = verify_api_key_hash("wrong-password", stored_hash)
        assert is_valid is False
        assert needs_rehash is False


class TestTimingSafeComparison:
    def test_sha256_comparison_uses_hmac_compare_digest(self):
        """_verify_sha256 must use hmac.compare_digest, not ==, for timing-safe comparison."""
        from unittest.mock import patch
        import hmac
        from policy_engine.auth.key_hashing import verify_api_key_hash

        sha256_hash = hashlib.sha256(b"testkey").hexdigest()
        with patch("hmac.compare_digest", wraps=hmac.compare_digest) as mock_cd:
            result, needs_rehash = verify_api_key_hash("testkey", sha256_hash)
        assert result is True
        mock_cd.assert_called_once()


class TestVerifySha256Hash:
    def test_verify_sha256_hash_returns_valid_needs_rehash(self):
        """Valid SHA-256 key returns (True, True) — needs upgrade."""
        from policy_engine.auth.key_hashing import verify_api_key_hash

        raw_key = "legacy-api-key-12345"
        sha256_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        is_valid, needs_rehash = verify_api_key_hash(raw_key, sha256_hash)
        assert is_valid is True
        assert needs_rehash is True, "SHA-256 key must signal that rehash is needed"

    def test_verify_sha256_wrong_key_returns_invalid(self):
        """Wrong key against SHA-256 hash returns (False, False)."""
        from policy_engine.auth.key_hashing import verify_api_key_hash

        sha256_hash = hashlib.sha256("correct-key".encode()).hexdigest()
        is_valid, needs_rehash = verify_api_key_hash("wrong-key", sha256_hash)
        assert is_valid is False
        assert needs_rehash is False


class TestVerifyUnknownFormat:
    def test_verify_unknown_format_returns_invalid(self):
        """Unknown hash format returns (False, False)."""
        from policy_engine.auth.key_hashing import verify_api_key_hash

        is_valid, needs_rehash = verify_api_key_hash("any-key", "not-a-valid-hash-format")
        assert is_valid is False
        assert needs_rehash is False

    def test_verify_empty_hash_returns_invalid(self):
        """Empty stored hash returns (False, False)."""
        from policy_engine.auth.key_hashing import verify_api_key_hash

        is_valid, needs_rehash = verify_api_key_hash("any-key", "")
        assert is_valid is False
        assert needs_rehash is False

    def test_verify_bcrypt_format_returns_invalid(self):
        """A bcrypt-format hash (not Argon2) returns (False, False)."""
        from policy_engine.auth.key_hashing import verify_api_key_hash

        # Simulate a bcrypt hash format (not supported)
        is_valid, needs_rehash = verify_api_key_hash(
            "any-key",
            "$2b$12$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )
        assert is_valid is False
        assert needs_rehash is False


# ---------------------------------------------------------------------------
# Transparent upgrade in DB (via api_key.py verify_api_key)
# ---------------------------------------------------------------------------

class TestTransparentUpgrade:
    def test_sha256_key_transparently_upgrades_in_db(self, db_session):
        """A SHA-256 stored key is silently re-hashed to Argon2id on next auth."""
        from policy_engine.models.api_key import APIKey
        from policy_engine.auth.api_key import verify_api_key as _verify_api_key

        raw_key = "upgrade-me-key-abc123"
        sha256_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        record = APIKey(
            key=sha256_hash,
            agent_id="agent-upgrade-test",
            name="Legacy Key",
            is_active=True,
        )
        db_session.add(record)
        db_session.commit()

        # Simulate FastAPI dependency injection by calling the underlying logic directly
        from policy_engine.auth.api_key import _verify_api_key_logic

        agent_id = _verify_api_key_logic(raw_key, db_session)
        assert agent_id == "agent-upgrade-test"

        # The stored hash must now be Argon2id format
        db_session.expire(record)
        db_session.refresh(record)
        # The old key (SHA-256 hash) should no longer exist; new Argon2 key should
        updated = db_session.query(APIKey).filter(
            APIKey.agent_id == "agent-upgrade-test"
        ).first()
        assert updated is not None
        assert updated.key.startswith("$argon2id$"), (
            f"Key should have been upgraded to Argon2id, got: {updated.key[:30]}"
        )

    def test_argon2_key_not_rehashed_on_auth(self, db_session):
        """An already-Argon2id key does NOT trigger a rehash on auth."""
        from policy_engine.models.api_key import APIKey
        from policy_engine.auth.key_hashing import hash_api_key
        from policy_engine.auth.api_key import _verify_api_key_logic

        raw_key = "already-argon2-key-xyz"
        argon2_hash = hash_api_key(raw_key)

        record = APIKey(
            key=argon2_hash,
            agent_id="agent-argon2-test",
            name="Argon2 Key",
            is_active=True,
        )
        db_session.add(record)
        db_session.commit()

        agent_id = _verify_api_key_logic(raw_key, db_session)
        assert agent_id == "agent-argon2-test"

        db_session.expire(record)
        db_session.refresh(record)
        updated = db_session.query(APIKey).filter(
            APIKey.agent_id == "agent-argon2-test"
        ).first()
        # Still Argon2 — same hash (not rehashed because it was valid Argon2id)
        assert updated.key.startswith("$argon2id$")


# ---------------------------------------------------------------------------
# Deadline logic — SHA-256 keys rejected after DEPRECATION_DEADLINE_DAYS
# ---------------------------------------------------------------------------

class TestDeprecationDeadline:
    def test_expired_sha256_key_rejected_after_deadline(self, db_session):
        """SHA-256 key is rejected with clear error after DEPRECATION_DEADLINE_DAYS."""
        from policy_engine.models.api_key import APIKey
        from policy_engine.auth.api_key import _verify_api_key_logic
        from policy_engine.auth import key_hashing as kh
        from datetime import datetime, timedelta

        raw_key = "expired-legacy-key-abc"
        sha256_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        # Set created_at far in the past (past deadline)
        old_date = datetime.utcnow() - timedelta(days=kh.DEPRECATION_DEADLINE_DAYS + 1)

        record = APIKey(
            key=sha256_hash,
            agent_id="agent-deadline-test",
            name="Old Legacy Key",
            is_active=True,
            created_at=old_date,
        )
        db_session.add(record)
        db_session.commit()

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _verify_api_key_logic(raw_key, db_session)

        assert exc_info.value.status_code == 401
        assert "re-issue" in exc_info.value.detail.lower() or "re-issu" in exc_info.value.detail.lower() or "reissue" in exc_info.value.detail.lower() or "legacy" in exc_info.value.detail.lower()

    def test_fresh_sha256_key_still_accepted_before_deadline(self, db_session):
        """SHA-256 key created recently (before deadline) is still accepted."""
        from policy_engine.models.api_key import APIKey
        from policy_engine.auth.api_key import _verify_api_key_logic

        raw_key = "fresh-legacy-key-xyz"
        sha256_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        record = APIKey(
            key=sha256_hash,
            agent_id="agent-fresh-legacy",
            name="Fresh Legacy Key",
            is_active=True,
        )
        db_session.add(record)
        db_session.commit()

        agent_id = _verify_api_key_logic(raw_key, db_session)
        assert agent_id == "agent-fresh-legacy"


# ---------------------------------------------------------------------------
# DEPRECATION_DEADLINE_DAYS constant is accessible
# ---------------------------------------------------------------------------

class TestConstants:
    def test_deprecation_deadline_days_defined(self):
        """DEPRECATION_DEADLINE_DAYS must be accessible and positive."""
        from policy_engine.auth.key_hashing import DEPRECATION_DEADLINE_DAYS

        assert isinstance(DEPRECATION_DEADLINE_DAYS, int)
        assert DEPRECATION_DEADLINE_DAYS > 0

    def test_deprecation_deadline_days_default_is_90(self):
        """Default DEPRECATION_DEADLINE_DAYS is 90."""
        from policy_engine.auth.key_hashing import DEPRECATION_DEADLINE_DAYS

        assert DEPRECATION_DEADLINE_DAYS == 90
