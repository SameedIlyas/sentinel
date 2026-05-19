"""Regression tests for CRIT-011 full close — HttpOnly cookie session.

The contract this PR establishes:

1. ``POST /v1/auth/login`` sets a ``Set-Cookie: access_token=...; HttpOnly;
   SameSite=...`` cookie carrying the JWT. The response body's
   ``access_token`` field is an empty string (browser flows use the
   cookie; SDKs may still call ``/v1/auth/login`` for the body, but the
   modern path is X-API-Key for non-browsers).
2. A second ``Set-Cookie: csrf_token=...`` cookie (NOT HttpOnly) is set
   so the SPA can echo the value into the ``X-CSRF-Token`` header.
3. Subsequent authenticated requests succeed when the browser sends the
   cookie automatically (no Authorization header).
4. ``POST /v1/auth/logout`` deletes both cookies on the response.
5. The bearer-header path still works for SDK callers.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from policy_engine.auth.jwt_utils import get_password_hash
from policy_engine.config import settings
from policy_engine.database import get_db
from policy_engine.main import app
from policy_engine.models.organization import Organization
from policy_engine.models.user import User, UserRole


def _make_org(db_session, name: str = "probe-org") -> Organization:
    org = Organization(
        id=str(uuid.uuid4()),
        name=name,
        slug=name,
        tier="enterprise",
    )
    db_session.add(org)
    db_session.commit()
    return org


def _make_user(
    db_session,
    *,
    username: str = "alice",
    password: str = "p@ssw0rd-strong",
    role: UserRole = UserRole.ORG_ADMIN,
) -> User:
    org = _make_org(db_session)
    u = User(
        id=str(uuid.uuid4()),
        username=username,
        email=f"{username}@test.local",
        password_hash=get_password_hash(password),
        role=role,
        full_name="probe",
        is_active=True,
        organization_id=org.id,
    )
    db_session.add(u)
    db_session.commit()
    return u


def _client(db_session) -> TestClient:
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# /v1/auth/login — cookie issuance
# ---------------------------------------------------------------------------

class TestLoginCookies:
    def test_login_sets_httponly_access_cookie(self, db_session):
        _make_user(db_session, username="alice", password="p@ssw0rd-strong")
        try:
            with _client(db_session) as c:
                r = c.post(
                    "/v1/auth/login",
                    json={"username": "alice", "password": "p@ssw0rd-strong"},
                )
            assert r.status_code == 200, r.text
            cookies = r.headers.get_list("set-cookie")
            access_cookie = next(
                (c for c in cookies if c.startswith(f"{settings.SESSION_COOKIE_NAME}=")),
                None,
            )
            assert access_cookie is not None, (
                f"login must Set-Cookie: {settings.SESSION_COOKIE_NAME}=...; "
                f"got: {cookies}"
            )
            assert "HttpOnly" in access_cookie, (
                "access cookie MUST be HttpOnly (CRIT-011 exfil mitigation)"
            )
            # SameSite=lax is the default; the JS cannot read the cookie
            # even on same-origin script access regardless.
            assert "SameSite=lax" in access_cookie or "samesite=lax" in access_cookie.lower()
        finally:
            app.dependency_overrides.clear()

    def test_login_sets_js_readable_csrf_cookie(self, db_session):
        _make_user(db_session, username="alice", password="p@ssw0rd-strong")
        try:
            with _client(db_session) as c:
                r = c.post(
                    "/v1/auth/login",
                    json={"username": "alice", "password": "p@ssw0rd-strong"},
                )
            cookies = r.headers.get_list("set-cookie")
            csrf_cookie = next(
                (c for c in cookies if c.startswith("csrf_token=")),
                None,
            )
            assert csrf_cookie is not None
            assert "HttpOnly" not in csrf_cookie

            body = r.json()
            assert body.get("csrf_token"), (
                "login body should also expose csrf_token for SPA bootstrap"
            )
        finally:
            app.dependency_overrides.clear()

    def test_login_body_access_token_is_empty_in_cookie_path(self, db_session):
        _make_user(db_session, username="alice", password="p@ssw0rd-strong")
        try:
            with _client(db_session) as c:
                r = c.post(
                    "/v1/auth/login",
                    json={"username": "alice", "password": "p@ssw0rd-strong"},
                )
            assert r.status_code == 200
            body = r.json()
            # CRIT-011 — the JWT does NOT travel in the response body.
            assert body["access_token"] == ""
        finally:
            app.dependency_overrides.clear()

    def test_login_bad_credentials_does_not_set_cookie(self, db_session):
        _make_user(db_session, username="alice", password="p@ssw0rd-strong")
        try:
            with _client(db_session) as c:
                r = c.post(
                    "/v1/auth/login",
                    json={"username": "alice", "password": "wrong"},
                )
            assert r.status_code == 401
            cookies = r.headers.get_list("set-cookie")
            assert not any(
                c.startswith(f"{settings.SESSION_COOKIE_NAME}=") for c in cookies
            )
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Authenticated requests via cookie
# ---------------------------------------------------------------------------

class TestCookieAuth:
    def test_validate_succeeds_with_cookie_no_authorization_header(self, db_session):
        _make_user(db_session, username="alice", password="p@ssw0rd-strong")
        try:
            with _client(db_session) as c:
                r = c.post(
                    "/v1/auth/login",
                    json={"username": "alice", "password": "p@ssw0rd-strong"},
                )
                assert r.status_code == 200
                # TestClient persists cookies — second call carries the
                # access_token cookie and NO bearer header.
                r2 = c.get("/v1/auth/validate")
            assert r2.status_code == 200, r2.text
            assert r2.json()["username"] == "alice"
        finally:
            app.dependency_overrides.clear()

    def test_validate_succeeds_with_legacy_bearer_header(self, db_session):
        """SDK path must keep working."""
        from policy_engine.auth.jwt_utils import create_access_token

        user = _make_user(db_session, username="alice", password="x")
        token = create_access_token(
            {
                "user_id": user.id,
                "username": user.username,
                "role": user.role.value,
                "org_id": user.organization_id,
            }
        )
        try:
            with _client(db_session) as c:
                r = c.get(
                    "/v1/auth/validate",
                    headers={"Authorization": f"Bearer {token}"},
                )
            assert r.status_code == 200, r.text
            assert r.json()["username"] == "alice"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# /v1/auth/logout — clears cookies
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout_clears_session_cookies(self, db_session):
        _make_user(db_session, username="alice", password="p@ssw0rd-strong")
        try:
            with _client(db_session) as c:
                c.post(
                    "/v1/auth/login",
                    json={"username": "alice", "password": "p@ssw0rd-strong"},
                )
                # The CSRF middleware enforces the double-submit on
                # mutating cookie-authed requests; honour it here.
                csrf = c.cookies.get("csrf_token") or ""
                r = c.post(
                    "/v1/auth/logout",
                    headers={"X-CSRF-Token": csrf} if csrf else {},
                )
            assert r.status_code == 200, r.text
            cookies = r.headers.get_list("set-cookie")
            # delete_cookie sets max-age=0 / expires=...; check that the
            # cookie value is empty or expiry is in the past.
            assert any(
                c.startswith(f"{settings.SESSION_COOKIE_NAME}=") and (
                    "max-age=0" in c.lower() or 'expires=' in c.lower()
                )
                for c in cookies
            ), f"logout did not clear access cookie; got: {cookies}"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# CSRF — mutating cookie-authenticated requests need the header
# ---------------------------------------------------------------------------

class TestCsrfDoubleSubmit:
    def test_mutating_cookie_request_without_csrf_header_is_403(self, db_session):
        _make_user(db_session, username="alice", password="p@ssw0rd-strong")
        try:
            with _client(db_session) as c:
                c.post(
                    "/v1/auth/login",
                    json={"username": "alice", "password": "p@ssw0rd-strong"},
                )
                # The login response sets csrf_token; we deliberately
                # omit the X-CSRF-Token header to assert the middleware
                # rejects the call.
                r = c.post("/v1/ws/ticket")
            assert r.status_code == 403, r.text
        finally:
            app.dependency_overrides.clear()

    def test_mutating_cookie_request_with_csrf_header_succeeds(self, db_session):
        _make_user(db_session, username="alice", password="p@ssw0rd-strong")
        try:
            with _client(db_session) as c:
                c.post(
                    "/v1/auth/login",
                    json={"username": "alice", "password": "p@ssw0rd-strong"},
                )
                csrf = c.cookies.get("csrf_token") or ""
                assert csrf, "csrf_token cookie missing after login"
                r = c.post(
                    "/v1/ws/ticket",
                    headers={"X-CSRF-Token": csrf},
                )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["ticket"]
            assert body["expires_in"] > 0
        finally:
            app.dependency_overrides.clear()
