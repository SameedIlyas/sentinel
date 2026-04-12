"""Phase 2 — Test Coverage Retrofit: RBAC Permission Matrix.

Tests all 8 healthcare roles against the ROLE_PERMISSIONS matrix.
Covers: models/user.py (ROLE_PERMISSIONS + has_permission function)
"""
import pytest

from policy_engine.models.user import UserRole, ROLE_PERMISSIONS, has_permission


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _has(role: UserRole, resource: str, action: str) -> bool:
    return has_permission(role, resource, action)


# ---------------------------------------------------------------------------
# Task 2.3: Role permission tests
# ---------------------------------------------------------------------------

class TestSystemAdminPermissions:
    """SYSTEM_ADMIN has full access to every resource."""

    def test_system_admin_can_create_policies(self):
        assert _has(UserRole.SYSTEM_ADMIN, "policies", "create")

    def test_system_admin_can_delete_users(self):
        assert _has(UserRole.SYSTEM_ADMIN, "users", "delete")

    def test_system_admin_can_manage_organizations(self):
        assert _has(UserRole.SYSTEM_ADMIN, "organizations", "delete")

    def test_system_admin_can_access_all_healthcare_resources(self):
        healthcare_resources = [
            "model_cards", "bias_audits", "drift_detection", "hitl_reviews",
            "shadow_ai", "scribe_audits", "transparency", "prior_auth",
            "revenue_cycle", "technical_files", "post_market", "risk_scores",
        ]
        for resource in healthcare_resources:
            assert _has(UserRole.SYSTEM_ADMIN, resource, "read"), (
                f"SYSTEM_ADMIN should be able to read {resource}"
            )


class TestCMIOPermissions:
    """CMIO has full portfolio view (policies, model cards, HITL)."""

    def test_cmio_can_read_policies(self):
        assert _has(UserRole.CMIO, "policies", "read")

    def test_cmio_can_create_model_cards(self):
        assert _has(UserRole.CMIO, "model_cards", "create")

    def test_cmio_can_manage_hitl_reviews(self):
        assert _has(UserRole.CMIO, "hitl_reviews", "create")
        assert _has(UserRole.CMIO, "hitl_reviews", "update")

    def test_cmio_cannot_delete_policies(self):
        assert not _has(UserRole.CMIO, "policies", "delete")

    def test_cmio_cannot_delete_users(self):
        assert not _has(UserRole.CMIO, "users", "delete")


class TestDataScientistPermissions:
    """DATA_SCIENTIST can access model cards, bias audits, and pipeline data."""

    def test_data_scientist_can_create_model_cards(self):
        assert _has(UserRole.DATA_SCIENTIST, "model_cards", "create")

    def test_data_scientist_can_create_bias_audits(self):
        assert _has(UserRole.DATA_SCIENTIST, "bias_audits", "create")

    def test_data_scientist_can_access_drift_detection(self):
        assert _has(UserRole.DATA_SCIENTIST, "drift_detection", "read")

    def test_data_scientist_cannot_manage_users(self):
        assert not _has(UserRole.DATA_SCIENTIST, "users", "create")

    def test_data_scientist_cannot_delete_agents(self):
        assert not _has(UserRole.DATA_SCIENTIST, "agents", "delete")


class TestComplianceOfficerPermissions:
    """COMPLIANCE_OFFICER can access audit logs and read policy-related data."""

    def test_compliance_officer_can_read_audit_logs(self):
        assert _has(UserRole.COMPLIANCE_OFFICER, "audit_logs", "read")

    def test_compliance_officer_can_export_audit_logs(self):
        assert _has(UserRole.COMPLIANCE_OFFICER, "audit_logs", "export")

    def test_compliance_officer_can_update_policies(self):
        assert _has(UserRole.COMPLIANCE_OFFICER, "policies", "update")

    def test_compliance_officer_cannot_create_policies(self):
        assert not _has(UserRole.COMPLIANCE_OFFICER, "policies", "create")

    def test_compliance_officer_cannot_manage_users(self):
        assert not _has(UserRole.COMPLIANCE_OFFICER, "users", "create")


class TestClinicalUserPermissions:
    """CLINICAL_USER has transparency view only — no admin capabilities."""

    def test_clinical_user_can_read_policies(self):
        assert _has(UserRole.CLINICAL_USER, "policies", "read")

    def test_clinical_user_can_manage_hitl_reviews(self):
        assert _has(UserRole.CLINICAL_USER, "hitl_reviews", "create")

    def test_clinical_user_can_submit_prior_auth(self):
        assert _has(UserRole.CLINICAL_USER, "prior_auth", "create")

    def test_clinical_user_cannot_delete_policies(self):
        assert not _has(UserRole.CLINICAL_USER, "policies", "delete")

    def test_clinical_user_cannot_access_admin_users(self):
        assert not _has(UserRole.CLINICAL_USER, "users", "create")
        assert not _has(UserRole.CLINICAL_USER, "users", "delete")


class TestAnalystPermissions:
    """ANALYST can read policies and manage alerts/audit logs."""

    def test_analyst_can_read_policies(self):
        assert _has(UserRole.ANALYST, "policies", "read")

    def test_analyst_can_read_audit_logs(self):
        assert _has(UserRole.ANALYST, "audit_logs", "read")

    def test_analyst_can_acknowledge_alerts(self):
        assert _has(UserRole.ANALYST, "alerts", "acknowledge")

    def test_analyst_cannot_create_policies(self):
        assert not _has(UserRole.ANALYST, "policies", "create")

    def test_analyst_cannot_manage_users(self):
        # Analyst can read users but not create/delete them
        assert not _has(UserRole.ANALYST, "users", "create")


class TestViewerPermissions:
    """VIEWER has read-only access to everything except users."""

    def test_viewer_can_read_policies(self):
        assert _has(UserRole.VIEWER, "policies", "read")

    def test_viewer_can_read_agents(self):
        assert _has(UserRole.VIEWER, "agents", "read")

    def test_viewer_cannot_create_policies(self):
        assert not _has(UserRole.VIEWER, "policies", "create")

    def test_viewer_cannot_access_users(self):
        assert not _has(UserRole.VIEWER, "users", "read")


# ---------------------------------------------------------------------------
# Role escalation and edge cases
# ---------------------------------------------------------------------------

def test_permission_check_returns_false_for_unknown_permission():
    """has_permission returns False when the action doesn't exist for the role."""
    assert not _has(UserRole.VIEWER, "policies", "nonexistent_action")


def test_permission_check_returns_false_for_unknown_resource():
    """has_permission returns False for a resource not in the role's permissions."""
    assert not _has(UserRole.VIEWER, "totally_unknown_resource", "read")


def test_unauthorized_role_cannot_access_admin_users():
    """Non-admin roles cannot create or delete users."""
    non_admin_roles = [
        UserRole.DATA_SCIENTIST,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.CLINICAL_USER,
        UserRole.VIEWER,
    ]
    for role in non_admin_roles:
        assert not _has(role, "users", "delete"), (
            f"{role.value} must NOT be able to delete users"
        )


@pytest.mark.parametrize("role", [
    UserRole.SYSTEM_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CMIO,
    UserRole.DATA_SCIENTIST,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.CLINICAL_USER,
    UserRole.ANALYST,
    UserRole.VIEWER,
])
def test_all_roles_can_read_policies(role):
    """Every role must be able to read policies (minimum transparency requirement)."""
    assert _has(role, "policies", "read"), (
        f"{role.value} must have at least 'read' permission on policies"
    )
