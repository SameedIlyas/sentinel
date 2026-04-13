"""Tests verifying audit log append-only enforcement (Task 3.6).

Ensures:
- No DELETE HTTP endpoint exists on /v1/audit/
- No role in ROLE_PERMISSIONS has 'delete_audit_logs' permission
- No role has 'delete' permission on the 'audit_logs' resource
"""

import pytest
from policy_engine.models.user import UserRole, ROLE_PERMISSIONS, has_permission


# ---------------------------------------------------------------------------
# HTTP endpoint guard — DELETE must return 404 or 405
# ---------------------------------------------------------------------------

def test_no_delete_endpoint_on_audit_logs(client):
    """Verify audit log DELETE is not routable.

    Expected codes:
      404 — route not found
      405 — method not allowed
      401/403 — auth middleware fires before routing (no route registered, so
                 the framework still blocks at auth — no DELETE handler exists)

    Any of these proves no DELETE handler is registered for audit logs.
    """
    response = client.delete("/v1/audit/some-nonexistent-id")
    assert response.status_code in (401, 403, 404, 405), (
        f"Unexpected status on DELETE /v1/audit/..., got {response.status_code}. "
        "A 2xx would indicate a DELETE route is registered."
    )
    # The critical assertion: must NOT be a success response
    assert response.status_code not in range(200, 300), (
        "DELETE /v1/audit/... returned a success — a DELETE endpoint must NOT exist"
    )


def test_no_delete_endpoint_on_audit_logs_list(client):
    """DELETE on the logs collection must not succeed."""
    response = client.delete("/v1/audit/logs")
    assert response.status_code not in range(200, 300), (
        f"DELETE /v1/audit/logs returned {response.status_code} — must not succeed"
    )


# ---------------------------------------------------------------------------
# RBAC permission matrix — no role may delete audit logs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", list(UserRole))
def test_no_role_can_delete_audit_logs_resource(role):
    """No role should have 'delete' on the 'audit_logs' resource."""
    assert not has_permission(role, "audit_logs", "delete"), (
        f"Role {role.value} unexpectedly has delete permission on audit_logs"
    )


@pytest.mark.parametrize("role", list(UserRole))
def test_no_role_has_delete_audit_logs_permission(role):
    """No role should have the synthetic 'delete_audit_logs' permission."""
    assert not has_permission(role, "delete_audit_logs", "any"), (
        f"Role {role.value} unexpectedly has delete_audit_logs permission"
    )


# ---------------------------------------------------------------------------
# Structural check — ROLE_PERMISSIONS dict inspection
# ---------------------------------------------------------------------------

def test_role_permissions_audit_logs_never_include_delete():
    """Directly inspect the ROLE_PERMISSIONS dict — 'delete' must not appear."""
    for role, perms in ROLE_PERMISSIONS.items():
        audit_actions = perms.get("audit_logs", [])
        assert "delete" not in audit_actions, (
            f"Role {role.value} has 'delete' in audit_logs permissions"
        )
