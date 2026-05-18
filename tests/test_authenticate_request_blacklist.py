"""Regression test for CRIT-007 — authenticate_request must honour token blacklist.

Before the fix, `authenticate_request` (the dependency used by audit, agents,
policies, alerts routes) only verified JWT signature/expiry and skipped the
blacklist check that `get_current_user` performs. A logged-out user's token
remained valid against those routes for the full TTL.

This test exercises the dependency directly because the production routes
that wire it also impose tenancy + role gates that are out of scope here.
"""
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from policy_engine.auth.jwt_utils import create_access_token
from policy_engine.auth.rbac import authenticate_request
from policy_engine.database import get_db
from policy_engine.models.user import User, UserRole
from policy_engine.services.token_blacklist import get_token_blacklist


def _build_test_app(db_session):
    """Tiny FastAPI app whose only route depends on authenticate_request."""
    app = FastAPI()

    @app.get("/_probe")
    def probe(identity: str = Depends(authenticate_request)):
        return {"identity": identity}

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    return app


def _make_user(db_session, role: UserRole = UserRole.ADMIN) -> User:
    from policy_engine.auth.jwt_utils import get_password_hash
    import uuid

    user = User(
        id=str(uuid.uuid4()),
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"u_{uuid.uuid4().hex[:8]}@test.local",
        password_hash=get_password_hash("x"),
        role=role,
        full_name="probe",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_authenticate_request_rejects_blacklisted_token(db_session, mock_redis, monkeypatch):
    """A token whose jti is in the blacklist must produce 401, even via authenticate_request."""
    # Wire the blacklist to a fakeredis instance for deterministic state.
    from policy_engine.services import token_blacklist as tb_mod

    bl = tb_mod.TokenBlacklist(redis_client=mock_redis)
    monkeypatch.setattr(tb_mod, "_blacklist_instance", bl, raising=False)

    user = _make_user(db_session)
    token = create_access_token({"user_id": user.id, "username": user.username, "role": user.role.value})

    # Decode to extract jti, blacklist it.
    from policy_engine.auth.jwt_utils import decode_access_token

    payload = decode_access_token(token)
    assert payload is not None
    jti = payload["jti"]
    get_token_blacklist().add(jti, expires_in_seconds=3600)

    app = _build_test_app(db_session)
    with TestClient(app, raise_server_exceptions=True) as c:
        r = c.get("/_probe", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 401, r.text
    assert r.json()["detail"] == "Token has been revoked"


def test_authenticate_request_accepts_valid_token(db_session, mock_redis, monkeypatch):
    """Sanity: a non-blacklisted token still authenticates."""
    from policy_engine.services import token_blacklist as tb_mod

    bl = tb_mod.TokenBlacklist(redis_client=mock_redis)
    monkeypatch.setattr(tb_mod, "_blacklist_instance", bl, raising=False)

    user = _make_user(db_session)
    token = create_access_token({"user_id": user.id, "username": user.username, "role": user.role.value})

    app = _build_test_app(db_session)
    with TestClient(app, raise_server_exceptions=True) as c:
        r = c.get("/_probe", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 200, r.text
    assert r.json()["identity"] == user.id
