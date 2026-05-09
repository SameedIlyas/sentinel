"""Tests for JWT audience verification (Task 3.2)."""

import jwt as pyjwt
from datetime import datetime, timedelta

from policy_engine.config import settings
from policy_engine.auth.jwt_utils import create_access_token, decode_access_token


def _make_token_with_audience(aud) -> str:
    """Helper: build a raw JWT with a specific audience claim."""
    payload = {
        "sub": "test-user",
        "username": "tester",
        "role": "viewer",
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "iat": datetime.utcnow(),
        "iss": "sentinel",
        "aud": aud,
    }
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def test_token_with_correct_audience_is_accepted():
    """A token bearing the correct audience claim must decode successfully."""
    token = create_access_token({"sub": "u1", "username": "alice", "role": "viewer"})
    payload = decode_access_token(token)
    assert payload is not None
    assert "sub" in payload


def test_token_with_wrong_audience_is_rejected():
    """A token bearing a different audience must be rejected."""
    token = _make_token_with_audience("other-service")
    payload = decode_access_token(token)
    assert payload is None, "Token with wrong audience should be rejected"


def test_token_without_audience_is_rejected():
    """A token with no audience claim must be rejected when audience verification is on."""
    payload_data = {
        "sub": "test-user",
        "username": "tester",
        "role": "viewer",
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "iat": datetime.utcnow(),
        "iss": "sentinel",
        # no "aud" field
    }
    token = pyjwt.encode(payload_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    result = decode_access_token(token)
    assert result is None, "Token without audience should be rejected"


def test_allowed_audiences_config_contains_sentinel_api():
    """Config must have 'sentinel-api' in ALLOWED_AUDIENCES."""
    assert "sentinel-api" in settings.ALLOWED_AUDIENCES
