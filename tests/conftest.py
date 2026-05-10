"""Pytest configuration and shared fixtures.

IMPORTANT: .env.test is loaded before any policy_engine import so that
Settings() picks up test values (e.g. SECRET_KEY, DATABASE_URL=sqlite:///:memory:).
"""
import os
import sys

# ── Step 1: project root on sys.path ────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Step 2: load test env vars BEFORE importing policy_engine ───────────────
from dotenv import load_dotenv  # noqa: E402

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), ".env.test"),
    override=True,
)

# ── Step 3: now safe to import policy_engine ────────────────────────────────
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from policy_engine.database import Base, get_db  # noqa: E402
from policy_engine.main import app  # noqa: E402

# Register all models with Base.metadata so create_all() builds every table.
from policy_engine.models import (  # noqa: F401, E402
    agent,
    audit_log,
    policy,
    user,
    organization,
    alert,
    alert_config,
    api_key,
)

# Clinical governance models
from policy_engine.models import model_card  # noqa: F401, E402
from policy_engine.models import bias_audit  # noqa: F401, E402
from policy_engine.models import drift  # noqa: F401, E402
from policy_engine.models import hitl  # noqa: F401, E402

# Admin governance models
from policy_engine.models import shadow_ai as _shadow_ai  # noqa: F401, E402
from policy_engine.models import scribe_audit as _scribe_audit  # noqa: F401, E402
from policy_engine.models import transparency as _transparency  # noqa: F401, E402

# Finance models
from policy_engine.models import prior_auth as _prior_auth  # noqa: F401, E402
from policy_engine.models import revenue_cycle as _revenue_cycle  # noqa: F401, E402

# Regulatory models
from policy_engine.models import technical_file as _technical_file  # noqa: F401, E402
from policy_engine.models import post_market as _post_market  # noqa: F401, E402
from policy_engine.models import risk_score as _risk_score  # noqa: F401, E402

# Optional models — import if present, skip gracefully if not yet created
try:
    from policy_engine.models import fhir_cache as _fhir_cache  # noqa: F401
    from policy_engine.models import dicom_metadata as _dicom_metadata  # noqa: F401
    from policy_engine.models import phi_log as _phi_log  # noqa: F401
except ImportError:
    pass

# ── Test engine (single in-memory SQLite, StaticPool = shared connection) ───
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=TEST_ENGINE,
)


def _override_get_db():
    """FastAPI dependency override: test DB session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True, scope="function")
def _db_tables():
    """Create all tables before each test; drop after.  autouse=True."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture(scope="function")
def db_session(_db_tables):
    """Sync SQLAlchemy session backed by the in-memory test engine."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client(_db_tables):
    """FastAPI TestClient with in-memory DB injected via dependency override."""
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ── Phase 2 fixtures ──────────────────────────────────────────────────────────

import hashlib  # noqa: E402
import uuid as _uuid  # noqa: E402
import fakeredis  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402

from policy_engine.models.api_key import APIKey  # noqa: E402
from policy_engine.models.user import User, UserRole  # noqa: E402
from policy_engine.auth.jwt_utils import create_access_token  # noqa: E402


@pytest.fixture(scope="function")
def agent_api_key(db_session):
    """Create a test API key + agent in the DB. Returns (raw_key, agent_id)."""
    raw_key = "test-api-key-abcdef1234567890"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    agent_id = "test-agent-001"

    record = APIKey(
        key=key_hash,
        agent_id=agent_id,
        name="Test Agent Key",
        is_active=True,
    )
    db_session.add(record)
    db_session.commit()
    return raw_key, agent_id


@pytest.fixture(scope="function")
def admin_user_jwt(db_session):
    """Create a SYSTEM_ADMIN user and return a valid JWT token."""
    from policy_engine.auth.jwt_utils import get_password_hash

    user = User(
        id=str(_uuid.uuid4()),
        username="admin_test",
        email="admin@test.local",
        password_hash=get_password_hash("testpassword"),
        role=UserRole.SYSTEM_ADMIN,
        full_name="Test Admin",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(
        data={"sub": user.id, "username": user.username, "role": user.role.value}
    )
    return token


@pytest.fixture(scope="function")
def make_user_jwt(db_session):
    """Factory fixture: call make_user_jwt(role) to get a JWT for that role."""
    from policy_engine.auth.jwt_utils import get_password_hash

    def _factory(role: UserRole) -> str:
        uid = str(_uuid.uuid4())
        user = User(
            id=uid,
            username=f"user_{role.value}_{uid[:8]}",
            email=f"{role.value}_{uid[:8]}@test.local",
            password_hash=get_password_hash("testpassword"),
            role=role,
            full_name=f"Test {role.value}",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        token = create_access_token(
            data={"sub": user.id, "username": user.username, "role": user.role.value}
        )
        return token

    return _factory


@pytest.fixture(scope="function")
def mock_redis():
    """FakeRedis instance — drop-in replacement for redis.Redis in tests."""
    return fakeredis.FakeRedis(decode_responses=False)


@pytest.fixture(scope="function")
def mock_slack():
    """Patch requests.post so Slack calls never hit the network."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "ok"

    with patch("requests.post", return_value=mock_response) as mock_post:
        yield mock_post


@pytest.fixture(scope="function")
def authed_client(_db_tables, agent_api_key):
    """TestClient with API key pre-injected into request headers."""
    raw_key, agent_id = agent_api_key
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        c.headers.update({"X-API-Key": raw_key})
        yield c, agent_id
    app.dependency_overrides.clear()


# ── Clinic-tier fixtures (Phase 1) ──────────────────────────────────────
# These build on the factories in tests/factories/clinic.py so every
# fixture writes only PHI-safe synthetic data.

from policy_engine.models.organization import (  # noqa: E402
    TIER_CLINIC_BASIC,
    TIER_CLINIC_STANDARD,
    TIER_CLINIC_MULTI_SITE,
    TIER_ENTERPRISE,
)


@pytest.fixture(scope="function")
def clinic_org(db_session):
    """A clinic_standard Organization with BAA signed.

    Most clinic-route happy-path tests want this. Negative tests requiring
    enterprise tier or unsigned BAA should call ``make_clinic_org`` from
    ``tests.factories.clinic`` directly with overrides.
    """
    from tests.factories.clinic import make_clinic_org
    return make_clinic_org(db_session, tier=TIER_CLINIC_STANDARD, baa_signed=True)


@pytest.fixture(scope="function")
def clinic_admin(db_session, clinic_org):
    """A clinic admin user attached to ``clinic_org``. Returns (user, jwt)."""
    from tests.factories.clinic import make_clinic_admin
    return make_clinic_admin(db_session, clinic_org)


@pytest.fixture(scope="function")
def clinic_admin_jwt(clinic_admin):
    """Just the JWT string for the clinic admin (most tests only want the token)."""
    _user, token = clinic_admin
    return token


@pytest.fixture(scope="function")
def clinic_authed_client(_db_tables, db_session, clinic_org, clinic_admin):
    """TestClient with a clinic-admin JWT pre-injected.

    Yields ``(client, org, user)`` so tests can assert against the
    underlying records without re-querying.
    """
    user, token = clinic_admin
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c, clinic_org, user
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def signed_webhook():
    """Factory fixture — returns ``(body_bytes, signature_header)`` for a Stripe event.

    Usage::

        body, sig = signed_webhook(event_type="customer.subscription.deleted",
                                   object_data={"customer": "cus_123", ...})
        client.post("/v1/billing/clinic/webhook", content=body,
                    headers={"Stripe-Signature": sig})
    """
    import os
    from tests.factories.billing import make_stripe_event, serialize_and_sign

    def _build(
        event_type: str,
        *,
        object_data: dict | None = None,
        event_id: str | None = None,
        secret: str | None = None,
        timestamp: int | None = None,
    ):
        evt = make_stripe_event(event_type, object_data=object_data, event_id=event_id)
        s = secret if secret is not None else os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        return serialize_and_sign(evt, secret=s, timestamp=timestamp)

    return _build


@pytest.fixture(scope="function")
def make_clinic_org_factory(db_session):
    """Curried factory for tests that need multiple orgs (cap-breach, multi-tenant)."""
    from tests.factories.clinic import make_clinic_org

    def _factory(**kwargs):
        return make_clinic_org(db_session, **kwargs)

    return _factory


# Re-export tier constants for convenience in test files.
__all_tiers__ = (
    TIER_ENTERPRISE,
    TIER_CLINIC_BASIC,
    TIER_CLINIC_STANDARD,
    TIER_CLINIC_MULTI_SITE,
)


# ── Phase 6: auto-mark legacy phase tests as `regression` ──────────────
# Saves us from editing 30+ existing test files just to add a module-level
# pytestmark. Anything in tests/test_phase*.py becomes a regression test.

import re as _re  # noqa: E402

_PHASE_TEST_PATTERN = _re.compile(r"[/\\]tests[/\\]test_phase\d+_")


def pytest_collection_modifyitems(config, items):
    regression = pytest.mark.regression
    for item in items:
        if _PHASE_TEST_PATTERN.search(str(item.fspath)):
            item.add_marker(regression)
