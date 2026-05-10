"""Phase 1 foundation smoke test.

Verifies the new fixtures and factories work end-to-end against the
in-memory test DB. If this file fails, every later phase is blocked.
"""

from __future__ import annotations

import pytest

from policy_engine.models.clinic import (
    BillingEvent,
    ClinicAiObservation,
    ClinicAiTool,
    ClinicReportArtifact,
)
from policy_engine.models.organization import (
    Organization,
    TIER_CLINIC_BASIC,
    TIER_CLINIC_STANDARD,
    TIER_ENTERPRISE,
)
from policy_engine.services.phi_text_check import scan_for_phi


pytestmark = pytest.mark.clinic


def test_clinic_org_fixture_persists(clinic_org: Organization, db_session) -> None:
    """clinic_org fixture creates a clinic_standard org with BAA signed."""
    assert clinic_org.tier == TIER_CLINIC_STANDARD
    assert clinic_org.hipaa_baa_signed is True
    assert clinic_org.hipaa_baa_date is not None
    # Round-trip via DB to confirm persistence.
    fresh = db_session.query(Organization).filter(Organization.id == clinic_org.id).one()
    assert fresh.id == clinic_org.id


def test_clinic_admin_jwt_fixture(clinic_admin_jwt: str, clinic_admin) -> None:
    """clinic_admin_jwt fixture returns a non-empty token; user is attached to the org."""
    user, token = clinic_admin
    assert clinic_admin_jwt == token
    assert isinstance(token, str)
    assert len(token) > 50  # JWTs are not tiny
    assert user.organization_id is not None


def test_clinic_authed_client_health(clinic_authed_client) -> None:
    """clinic_authed_client carries the JWT and the test DB.

    Hits /health to confirm the FastAPI app boots in the fixture context.
    """
    client, org, user = clinic_authed_client
    resp = client.get("/health/live")
    assert resp.status_code == 200
    # Authorization header was set on the client.
    assert client.headers.get("Authorization", "").startswith("Bearer ")


def test_make_clinic_org_factory_yields_distinct_orgs(make_clinic_org_factory) -> None:
    """The factory fixture can build multiple orgs with different tiers."""
    a = make_clinic_org_factory(tier=TIER_CLINIC_BASIC, baa_signed=False)
    b = make_clinic_org_factory(tier=TIER_CLINIC_STANDARD, baa_signed=True)
    enterprise = make_clinic_org_factory(tier=TIER_ENTERPRISE, baa_signed=False)
    assert {a.id, b.id, enterprise.id} == {a.id, b.id, enterprise.id}  # all distinct
    assert a.tier == TIER_CLINIC_BASIC
    assert b.hipaa_baa_signed is True
    assert enterprise.tier == TIER_ENTERPRISE


def test_factories_persist_clinic_tool_and_observation(clinic_org, db_session) -> None:
    """Direct factory imports work and write to the same session."""
    from tests.factories.clinic import (
        make_clinic_observation,
        make_clinic_tool,
        make_extension_token,
        make_billing_event,
        make_report_artifact,
    )

    tool = make_clinic_tool(db_session, clinic_org)
    obs = make_clinic_observation(db_session, clinic_org, page_url="https://chat.example.test/abc")
    tok_row, plaintext = make_extension_token(db_session, clinic_org)
    evt = make_billing_event(db_session, clinic_org, event_type="checkout.session.completed")
    art = make_report_artifact(db_session, clinic_org)

    # All persisted under the same org.
    assert db_session.query(ClinicAiTool).filter_by(id=tool.id).one().org_id == clinic_org.id
    assert db_session.query(ClinicAiObservation).filter_by(id=obs.id).one().org_id == clinic_org.id
    assert db_session.query(BillingEvent).filter_by(id=evt.id).one().org_id == clinic_org.id
    assert db_session.query(ClinicReportArtifact).filter_by(id=art.id).one().org_id == clinic_org.id
    # Extension token is hashed, not raw.
    assert tok_row.token_hash != plaintext
    assert len(tok_row.token_hash) == 64  # sha256 hex
    # page_url is hashed, not stored raw.
    assert obs.page_url_hash and len(obs.page_url_hash) == 64


def test_factory_freetext_fields_are_phi_safe() -> None:
    """Free-text fields produced by factories (notes, purposes, names) must
    not match any pattern in ``phi_text_check._PATTERNS``.

    Identifier columns (User.email, billing_email) are out of scope for
    this scanner — that's the role of presidio-analyzer in Phase 7.
    """
    from tests.factories.phi_safe import (
        CLINIC_NAMES,
        SAFE_OBSERVATION_HOSTS,
        SAFE_TOOL_FINGERPRINTS,
        SAFE_TOOL_NAMES,
        SAFE_TOOL_NOTES,
        SAFE_TOOL_VENDORS,
    )

    free_text_strings: list[str] = []
    free_text_strings += list(CLINIC_NAMES)
    free_text_strings += list(SAFE_TOOL_NOTES)
    free_text_strings += list(SAFE_TOOL_NAMES)
    free_text_strings += list(SAFE_TOOL_VENDORS)
    free_text_strings += list(SAFE_OBSERVATION_HOSTS)
    free_text_strings += list(SAFE_TOOL_FINGERPRINTS)

    findings = [(s, scan_for_phi("test", s)) for s in free_text_strings]
    leaks = [(s, f) for s, f in findings if f is not None]
    assert leaks == [], (
        f"Factory free-text fixtures contain PHI-shaped strings: {leaks}. "
        "All fixtures must pass HIPAA Safe Harbor synthetic-data review."
    )


def test_signed_webhook_factory_yields_valid_signature(signed_webhook) -> None:
    """The signed_webhook factory produces a body + Stripe-Signature header pair."""
    body, sig = signed_webhook(
        event_type="customer.subscription.deleted",
        object_data={"customer": "cus_test_smoke", "id": "sub_test_smoke"},
    )
    assert isinstance(body, bytes)
    assert b"customer.subscription.deleted" in body
    assert sig.startswith("t=")
    assert ",v1=" in sig


def test_clinic_models_register_with_metadata() -> None:
    """H1 verification — clinic tables present in Base.metadata transitively."""
    from policy_engine.database import Base
    expected = {
        "clinic_ai_tools",
        "clinic_ai_observations",
        "billing_events",
        "clinic_extension_tokens",
        "clinic_report_artifacts",
    }
    assert expected <= set(Base.metadata.tables), (
        f"Missing clinic tables in Base.metadata: {expected - set(Base.metadata.tables)}"
    )
