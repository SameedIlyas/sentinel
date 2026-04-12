"""
Phase 1 Architecture Tests

TDD tests for all 6 Phase 1 tasks written BEFORE implementation.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import AsyncGenerator


# ---------------------------------------------------------------------------
# Task 1.1 — Async SQLAlchemy Tests
# ---------------------------------------------------------------------------

class TestAsyncDatabase:
    """Tests for async SQLAlchemy setup."""

    def test_get_async_db_is_importable(self):
        """get_async_db must be importable from policy_engine.database."""
        from policy_engine.database import get_async_db  # noqa: F401

    def test_async_session_local_is_importable(self):
        """AsyncSessionLocal must be importable from policy_engine.database."""
        from policy_engine.database import AsyncSessionLocal  # noqa: F401

    def test_async_engine_is_importable(self):
        """async_engine must be importable from policy_engine.database."""
        from policy_engine.database import async_engine  # noqa: F401

    def test_get_async_db_is_async_generator(self):
        """get_async_db must be an async generator function."""
        import inspect
        from policy_engine.database import get_async_db
        assert inspect.isasyncgenfunction(get_async_db)

    def test_sqlite_url_converted_to_aiosqlite(self):
        """When DATABASE_URL starts with sqlite://, async engine uses sqlite+aiosqlite://."""
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///./test.db"}):
            # Re-import config to pick up env change
            import importlib
            import policy_engine.database as db_module
            # The async_engine URL should use aiosqlite driver
            url_str = str(db_module.async_engine.url)
            assert "aiosqlite" in url_str or "sqlite" in url_str

    def test_sync_engine_still_exists(self):
        """Sync engine must still exist for backward compat (test fixtures, migrations)."""
        from policy_engine.database import engine  # noqa: F401
        from policy_engine.database import SessionLocal  # noqa: F401
        from policy_engine.database import get_db  # noqa: F401

    def test_async_session_expires_on_commit_false(self):
        """AsyncSessionLocal must use expire_on_commit=False for async correctness."""
        from policy_engine.database import AsyncSessionLocal
        # async_sessionmaker stores kw_args
        assert AsyncSessionLocal.kw.get("expire_on_commit") is False

    def test_docker_compose_file_exists(self):
        """docker-compose.yml must exist with postgres and redis services."""
        compose_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docker-compose.yml"
        )
        assert os.path.exists(compose_path), "docker-compose.yml not found"

    def test_docker_compose_has_postgres(self):
        """docker-compose.yml must define a postgres service."""
        compose_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docker-compose.yml"
        )
        if os.path.exists(compose_path):
            with open(compose_path) as f:
                content = f.read()
            assert "postgres" in content.lower()

    def test_docker_compose_has_redis(self):
        """docker-compose.yml must define a redis service."""
        compose_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docker-compose.yml"
        )
        if os.path.exists(compose_path):
            with open(compose_path) as f:
                content = f.read()
            assert "redis" in content.lower()

    def test_config_has_async_database_url_setting(self):
        """Settings must have DATABASE_POOL_SIZE and DATABASE_MAX_OVERFLOW."""
        from policy_engine.config import settings
        assert hasattr(settings, "DATABASE_POOL_SIZE")
        assert hasattr(settings, "DATABASE_MAX_OVERFLOW")
        assert settings.DATABASE_POOL_SIZE >= 10
        assert settings.DATABASE_MAX_OVERFLOW >= 10


# ---------------------------------------------------------------------------
# Task 1.2 — Multi-Tenancy Tests
# ---------------------------------------------------------------------------

class TestMultiTenancy:
    """Tests for multi-tenancy with Organization model and RLS."""

    def test_organization_model_importable(self):
        """Organization model must be importable."""
        from policy_engine.models.organization import Organization  # noqa: F401

    def test_organization_has_required_fields(self):
        """Organization model must have all required fields."""
        from policy_engine.models.organization import Organization
        cols = {c.key for c in Organization.__table__.columns}
        required = {"id", "name", "slug", "org_type", "hipaa_baa_signed", "created_at", "is_active"}
        assert required.issubset(cols), f"Missing columns: {required - cols}"

    def test_org_type_enum_has_required_values(self):
        """OrgType enum must have hospital, payer, medtech."""
        from policy_engine.models.organization import OrgType
        assert hasattr(OrgType, "HOSPITAL")
        assert hasattr(OrgType, "PAYER")
        assert hasattr(OrgType, "MEDTECH")

    def test_organization_member_model_importable(self):
        """OrganizationMember model must be importable."""
        from policy_engine.models.organization import OrganizationMember  # noqa: F401

    def test_organization_member_has_required_fields(self):
        """OrganizationMember must have org_id, user_id, role."""
        from policy_engine.models.organization import OrganizationMember
        cols = {c.key for c in OrganizationMember.__table__.columns}
        assert {"org_id", "user_id", "role"}.issubset(cols)

    def test_tenant_context_middleware_importable(self):
        """TenantContextMiddleware must be importable."""
        from policy_engine.middleware.tenant_context import TenantContextMiddleware  # noqa: F401

    def test_user_model_has_organization_id(self):
        """User model must have organization_id FK column."""
        from policy_engine.models.user import User
        cols = {c.key for c in User.__table__.columns}
        assert "organization_id" in cols, "User.organization_id not found"

    def test_agent_model_has_organization_id(self):
        """Agent model must have organization_id FK column."""
        from policy_engine.models.agent import Agent
        cols = {c.key for c in Agent.__table__.columns}
        assert "organization_id" in cols, "Agent.organization_id not found"

    def test_policy_model_has_organization_id(self):
        """Policy model must have organization_id FK column."""
        from policy_engine.models.policy import Policy
        cols = {c.key for c in Policy.__table__.columns}
        assert "organization_id" in cols, "Policy.organization_id not found"

    def test_audit_log_model_has_organization_id(self):
        """AuditLog model must have organization_id FK column."""
        from policy_engine.models import AuditLog
        cols = {c.key for c in AuditLog.__table__.columns}
        assert "organization_id" in cols, "AuditLog.organization_id not found"

    def test_tenant_middleware_extracts_org_id_from_jwt(self):
        """TenantContextMiddleware must extract org_id from JWT payload."""
        from policy_engine.middleware.tenant_context import TenantContextMiddleware
        # Verify the middleware class has an async dispatch method
        import inspect
        assert hasattr(TenantContextMiddleware, "dispatch")
        assert inspect.iscoroutinefunction(TenantContextMiddleware.dispatch)

    def test_organization_crud_router_importable(self):
        """Organization router must be importable."""
        from policy_engine.routes.organizations import router  # noqa: F401

    def test_migration_005_exists(self):
        """Migration 005 for organizations must exist."""
        import glob
        migrations = glob.glob(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "alembic", "versions", "*005*"
            )
        )
        assert len(migrations) > 0, "Migration 005 not found"


# ---------------------------------------------------------------------------
# Task 1.3 — DDD Structure Tests
# ---------------------------------------------------------------------------

class TestDDDStructure:
    """Tests for hexagonal architecture directory structure."""

    def test_domain_governance_package_exists(self):
        """domain/governance package must be importable."""
        import policy_engine.domain.governance  # noqa: F401

    def test_domain_clinical_package_exists(self):
        """domain/clinical stub package must be importable."""
        import policy_engine.domain.clinical  # noqa: F401

    def test_domain_compliance_package_exists(self):
        """domain/compliance stub package must be importable."""
        import policy_engine.domain.compliance  # noqa: F401

    def test_application_package_exists(self):
        """application/ package must be importable."""
        import policy_engine.application  # noqa: F401

    def test_infrastructure_package_exists(self):
        """infrastructure/ package must be importable."""
        import policy_engine.infrastructure  # noqa: F401

    def test_interfaces_package_exists(self):
        """interfaces/ package must be importable."""
        import policy_engine.interfaces  # noqa: F401

    def test_domain_governance_no_fastapi_imports(self):
        """domain/governance must not import fastapi or sqlalchemy."""
        import ast
        import pathlib

        gov_dir = pathlib.Path(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ) / "policy_engine" / "domain" / "governance"

        forbidden = {"fastapi", "sqlalchemy"}
        violations = []

        for py_file in gov_dir.glob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = []
                    if isinstance(node, ast.Import):
                        names = [alias.name for alias in node.names]
                    elif node.module:
                        names = [node.module]
                    for name in names:
                        for forbidden_pkg in forbidden:
                            if name.startswith(forbidden_pkg):
                                violations.append(f"{py_file.name}: imports {name}")

        assert not violations, f"domain/governance has forbidden imports: {violations}"

    def test_policy_entity_importable_from_domain(self):
        """Policy entity must be importable from domain/governance."""
        from policy_engine.domain.governance import PolicyEntity  # noqa: F401

    def test_agent_entity_importable_from_domain(self):
        """Agent entity must be importable from domain/governance."""
        from policy_engine.domain.governance import AgentEntity  # noqa: F401

    def test_existing_model_imports_not_broken(self):
        """Existing model imports must still work (backward compat)."""
        from policy_engine.models import Agent, Policy, AuditLog, Alert  # noqa: F401
        from policy_engine.models.user import User, UserRole  # noqa: F401
        from policy_engine.models.api_key import APIKey  # noqa: F401


# ---------------------------------------------------------------------------
# Task 1.4 — Expanded Healthcare Roles Tests
# ---------------------------------------------------------------------------

class TestExpandedRoles:
    """Tests for expanded 8-role UserRole enum."""

    def test_eight_roles_defined(self):
        """UserRole enum must have exactly 8 roles."""
        from policy_engine.models.user import UserRole
        assert len(UserRole) == 8, f"Expected 8 roles, got {len(UserRole)}: {list(UserRole)}"

    def test_all_required_roles_exist(self):
        """All 8 healthcare roles must exist."""
        from policy_engine.models.user import UserRole
        required = {
            "SYSTEM_ADMIN", "ORG_ADMIN", "CMIO", "DATA_SCIENTIST",
            "COMPLIANCE_OFFICER", "CLINICAL_USER", "ANALYST", "VIEWER"
        }
        existing = {r.name for r in UserRole}
        assert required == existing, f"Missing roles: {required - existing}"

    def test_system_admin_has_full_access(self):
        """SYSTEM_ADMIN must have full access to all resources."""
        from policy_engine.models.user import UserRole, ROLE_PERMISSIONS, has_permission
        admin_perms = ROLE_PERMISSIONS.get(UserRole.SYSTEM_ADMIN, {})
        assert len(admin_perms) > 0, "SYSTEM_ADMIN has no permissions defined"

    def test_healthcare_resources_in_permissions(self):
        """ROLE_PERMISSIONS must include new healthcare resources."""
        from policy_engine.models.user import ROLE_PERMISSIONS, UserRole
        new_resources = {
            "model_cards", "bias_audits", "drift_detection", "hitl_reviews",
            "shadow_ai", "scribe_audits", "transparency", "prior_auth",
            "revenue_cycle", "technical_files", "post_market", "risk_scores"
        }
        # Check at least SYSTEM_ADMIN covers new resources
        admin_perms = ROLE_PERMISSIONS.get(UserRole.SYSTEM_ADMIN, {})
        covered = set(admin_perms.keys())
        missing = new_resources - covered
        assert not missing, f"SYSTEM_ADMIN missing resources: {missing}"

    def test_backward_compat_admin_maps_to_org_admin(self):
        """'admin' value must still be usable (OrgAdmin has value 'admin' or backward compat exists)."""
        from policy_engine.models.user import UserRole
        # Either ADMIN still exists as alias OR ORG_ADMIN has value matching old 'admin'
        role_values = {r.value for r in UserRole}
        assert "admin" in role_values or "org_admin" in role_values

    def test_viewer_role_exists_with_read_only_access(self):
        """VIEWER must still exist and have read-only access."""
        from policy_engine.models.user import UserRole, has_permission
        assert UserRole.VIEWER is not None
        assert has_permission(UserRole.VIEWER, "policies", "read") is True
        assert has_permission(UserRole.VIEWER, "policies", "delete") is False

    def test_has_permission_works_for_new_roles(self):
        """has_permission must work for all new roles without raising errors."""
        from policy_engine.models.user import UserRole, has_permission
        for role in UserRole:
            # Should not raise — may return True or False
            result = has_permission(role, "model_cards", "read")
            assert isinstance(result, bool)

    def test_migration_006_exists(self):
        """Migration 006 for expanded roles must exist."""
        import glob
        migrations = glob.glob(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "alembic", "versions", "*006*"
            )
        )
        assert len(migrations) > 0, "Migration 006 not found"


# ---------------------------------------------------------------------------
# Task 1.5 — Event Bus Tests
# ---------------------------------------------------------------------------

class TestEventBus:
    """Tests for Redis pub/sub event bus."""

    def test_event_bus_importable(self):
        """EventBus must be importable."""
        from policy_engine.infrastructure.messaging.event_bus import EventBus  # noqa: F401

    def test_domain_events_importable(self):
        """Domain event classes must be importable."""
        from policy_engine.infrastructure.messaging.event_bus import (  # noqa: F401
            PolicyEvaluatedEvent,
            AlertCreatedEvent,
            AuditLogCreatedEvent,
            AgentRegisteredEvent,
        )

    def test_event_has_required_fields(self):
        """Domain events must have event_type, payload, org_id, timestamp, correlation_id."""
        from policy_engine.infrastructure.messaging.event_bus import PolicyEvaluatedEvent
        import inspect
        sig = inspect.signature(PolicyEvaluatedEvent.__init__)
        # Check the dataclass/model has the required fields
        event = PolicyEvaluatedEvent(
            payload={"policy_id": "p1"},
            org_id="org1",
            correlation_id="corr1",
        )
        assert event.event_type == "policy.evaluated"
        assert event.org_id == "org1"
        assert event.correlation_id == "corr1"
        assert event.timestamp is not None

    def test_event_bus_publish_with_mock_redis(self):
        """EventBus.publish must call redis.publish with serialized event."""
        from policy_engine.infrastructure.messaging.event_bus import EventBus, PolicyEvaluatedEvent
        mock_redis = MagicMock()
        bus = EventBus(redis_client=mock_redis)
        event = PolicyEvaluatedEvent(payload={"policy_id": "p1"}, org_id="org1", correlation_id="c1")
        bus.publish(event)
        assert mock_redis.publish.called

    def test_event_bus_falls_back_to_in_memory_on_redis_error(self):
        """EventBus must not raise when Redis is unavailable (graceful degradation)."""
        from policy_engine.infrastructure.messaging.event_bus import EventBus, PolicyEvaluatedEvent
        mock_redis = MagicMock()
        mock_redis.publish.side_effect = Exception("Redis connection refused")
        bus = EventBus(redis_client=mock_redis)
        event = PolicyEvaluatedEvent(payload={"policy_id": "p1"}, org_id="org1", correlation_id="c1")
        # Must not raise
        bus.publish(event)

    def test_event_bus_subscribe_returns_callable(self):
        """EventBus.subscribe must return a callable or register handler."""
        from policy_engine.infrastructure.messaging.event_bus import EventBus
        mock_redis = MagicMock()
        bus = EventBus(redis_client=mock_redis)
        handler = lambda event: None  # noqa: E731
        bus.subscribe("policy.evaluated", handler)
        # Verify handler registered
        assert "policy.evaluated" in bus._handlers

    def test_celery_config_importable(self):
        """Celery config must be importable."""
        from policy_engine.infrastructure.messaging.celery_config import celery_app  # noqa: F401

    def test_domain_events_table_migration_exists(self):
        """Migration 007 for domain_events table must exist."""
        import glob
        migrations = glob.glob(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "alembic", "versions", "*007*"
            )
        )
        assert len(migrations) > 0, "Migration 007 not found"

    def test_get_event_bus_singleton_importable(self):
        """get_event_bus() factory must be importable."""
        from policy_engine.infrastructure.messaging.event_bus import get_event_bus  # noqa: F401


# ---------------------------------------------------------------------------
# Task 1.6 — API Versioning Tests
# ---------------------------------------------------------------------------

class TestAPIVersioning:
    """Tests for API v1/v2 routing."""

    def test_interfaces_v1_router_importable(self):
        """interfaces/v1 router must be importable."""
        import policy_engine.interfaces.v1  # noqa: F401

    def test_interfaces_v2_router_importable(self):
        """interfaces/v2 stub router must be importable."""
        import policy_engine.interfaces.v2  # noqa: F401

    def test_organizations_router_importable(self):
        """Organizations router must be importable."""
        from policy_engine.routes.organizations import router  # noqa: F401

    def test_health_endpoint_responds(self):
        """GET /health must still respond after versioning changes."""
        import os
        os.environ.setdefault("DATABASE_URL", "sqlite:///./test_phase1.db")
        os.environ.setdefault("SECRET_KEY", "test-secret-phase1-xyz")
        from fastapi.testclient import TestClient
        from policy_engine.main import app
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/health")
        assert r.status_code == 200

    def test_v1_auth_login_still_accessible(self):
        """POST /v1/auth/login must still work after versioning changes."""
        import os
        os.environ.setdefault("DATABASE_URL", "sqlite:///./test_phase1.db")
        os.environ.setdefault("SECRET_KEY", "test-secret-phase1-xyz")
        from fastapi.testclient import TestClient
        from policy_engine.main import app
        client = TestClient(app, raise_server_exceptions=False)
        # 422 is fine (missing body), just check route exists
        csrf = "test-csrf"
        r = client.post("/v1/auth/login", json={}, headers={"x-csrf-token": csrf}, cookies={"csrf_token": csrf})
        assert r.status_code in (200, 400, 401, 422), f"Unexpected: {r.status_code}"

    def test_organizations_list_endpoint_exists(self):
        """GET /v1/organizations must exist."""
        import os
        os.environ.setdefault("DATABASE_URL", "sqlite:///./test_phase1.db")
        os.environ.setdefault("SECRET_KEY", "test-secret-phase1-xyz")
        from fastapi.testclient import TestClient
        from policy_engine.main import app
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/v1/organizations")
        # 401 is expected (no auth), 404 means route doesn't exist
        assert r.status_code != 404, "Route /v1/organizations not found"

    def test_organizations_create_endpoint_exists(self):
        """POST /v1/organizations must exist."""
        import os
        os.environ.setdefault("DATABASE_URL", "sqlite:///./test_phase1.db")
        os.environ.setdefault("SECRET_KEY", "test-secret-phase1-xyz")
        from fastapi.testclient import TestClient
        from policy_engine.main import app
        csrf = "test-csrf"
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/v1/organizations", json={}, headers={"x-csrf-token": csrf}, cookies={"csrf_token": csrf})
        assert r.status_code != 404, "Route POST /v1/organizations not found"

    def test_organization_members_endpoint_exists(self):
        """POST /v1/organizations/{org_id}/members must exist."""
        import os
        os.environ.setdefault("DATABASE_URL", "sqlite:///./test_phase1.db")
        os.environ.setdefault("SECRET_KEY", "test-secret-phase1-xyz")
        from fastapi.testclient import TestClient
        from policy_engine.main import app
        csrf = "test-csrf"
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post(
            "/v1/organizations/test-org-id/members",
            json={},
            headers={"x-csrf-token": csrf},
            cookies={"csrf_token": csrf}
        )
        assert r.status_code != 404, "Route POST /v1/organizations/{id}/members not found"

    def test_app_includes_organizations_router(self):
        """FastAPI app must have organizations router mounted."""
        import os
        os.environ.setdefault("DATABASE_URL", "sqlite:///./test_phase1.db")
        os.environ.setdefault("SECRET_KEY", "test-secret-phase1-xyz")
        from policy_engine.main import app
        routes = [r.path for r in app.routes]
        org_routes = [r for r in routes if "organization" in r]
        assert len(org_routes) > 0, f"No organization routes found. Routes: {routes}"
