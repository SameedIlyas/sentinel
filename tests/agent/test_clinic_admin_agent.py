"""Synthetic clinic-admin agent — deterministic state machine driving the API.

Per v2 plan (review C2): NO ``claude-agent-sdk`` dependency. A hand-rolled
agent that calls the FastAPI ``client`` through scripted scenarios. Goals:

* Behavioral E2E coverage of the full clinic flow (onboard → BAA → tools
  → observation → report → billing) without UI / Playwright.
* PHI guard on every captured response — agent transcripts must never
  contain PHI patterns.
* Deterministic — runs in every CI invocation, no skipif.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient

from policy_engine.database import get_db
from policy_engine.main import app
from policy_engine.services.phi_text_check import scan_for_phi
from tests.factories.billing import (
    checkout_session_completed,
    serialize_and_sign,
)
from tests.factories.clinic import make_clinic_admin, make_clinic_org


pytestmark = pytest.mark.agent


@dataclass
class AgentTranscript:
    steps: list[tuple[str, int, str]] = field(default_factory=list)

    def record(self, intent: str, status: int, body_summary: str) -> None:
        self.steps.append((intent, status, body_summary))


class ClinicAdminAgent:
    """Deterministic state machine that simulates a clinic admin using the API.

    Each ``run_*`` method represents an intent; the agent records the
    outcome to the transcript so tests can assert end-state plus PHI
    discipline.
    """

    def __init__(self, client: TestClient, transcript: AgentTranscript) -> None:
        self.client = client
        self.transcript = transcript

    def _record(self, intent: str, resp: Any) -> Any:
        body_text = ""
        try:
            body_text = resp.text[:500]
        except Exception:  # pragma: no cover
            pass
        self.transcript.record(intent, resp.status_code, body_text)
        return resp

    def get_baa_status(self) -> Any:
        return self._record("get_baa_status", self.client.get("/v1/clinic/baa/status"))

    def accept_baa(self, *, legal_name: str, accepter: str, title: str) -> Any:
        return self._record(
            "accept_baa",
            self.client.post(
                "/v1/clinic/baa/accept",
                json={
                    "organization_legal_name": legal_name,
                    "accepter_full_name": accepter,
                    "accepter_title": title,
                },
            ),
        )

    def register_tool(self, **payload: Any) -> Any:
        return self._record("register_tool", self.client.post("/v1/clinic/tools", json=payload))

    def list_tools(self) -> Any:
        return self._record("list_tools", self.client.get("/v1/clinic/tools"))

    def view_dashboard(self) -> Any:
        return self._record(
            "view_dashboard", self.client.get("/v1/clinic/dashboard/summary")
        )

    def view_billing_plans(self) -> Any:
        return self._record(
            "view_billing_plans", self.client.get("/v1/billing/clinic/plans")
        )


@dataclass(frozen=True)
class Scenario:
    name: str
    run: Callable[[ClinicAdminAgent], None]
    assert_outcome: Callable[[AgentTranscript], None]


def _scan_transcript_for_phi(transcript: AgentTranscript) -> list[tuple[str, Any]]:
    findings = []
    for intent, _status, body in transcript.steps:
        f = scan_for_phi(intent, body)
        if f is not None:
            findings.append((intent, f))
    return findings


# ── Helpers ─────────────────────────────────────────────────────────────


def _make_authed_client(db_session, *, tier: str = "clinic_basic", baa_signed: bool = False):
    org = make_clinic_org(db_session, tier=tier, baa_signed=baa_signed, slug=f"agent-{tier}")
    user, jwt = make_clinic_admin(db_session, org)
    app.dependency_overrides[get_db] = lambda: db_session
    c = TestClient(app, raise_server_exceptions=True)
    c.headers.update({"Authorization": f"Bearer {jwt}"})
    return c, org, user


# ── Scenarios ───────────────────────────────────────────────────────────


def test_happy_path_full_clinic_flow(db_session) -> None:
    """Onboard → sign BAA → register 3 tools → list → dashboard → billing.

    The agent simulates a clinic-basic admin completing the full workflow.
    """
    c, _org, _user = _make_authed_client(db_session, tier="clinic_basic", baa_signed=False)
    transcript = AgentTranscript()
    agent = ClinicAdminAgent(c, transcript)

    try:
        # Step 1: BAA status — basic tier offers click-through.
        status_resp = agent.get_baa_status()
        assert status_resp.status_code == 200
        assert status_resp.json()["mode"] == "click_through"

        # Step 2: Accept BAA.
        accept_resp = agent.accept_baa(
            legal_name="Acme Health LLC",
            accepter="Test Manager",
            title="Practice Manager",
        )
        assert accept_resp.status_code == 200
        assert accept_resp.json()["signed"] is True

        # Step 3-5: Register three tools (within clinic_basic 10-tool cap).
        for i, name in enumerate(["Acme Scribe", "Foo Helper", "QA Decision Tool"]):
            r = agent.register_tool(
                name=name,
                vendor="Acme AI",
                category="ambient_scribe",
                purpose="General assistance.",
                handles_phi=False,
                risk_level="low",
                notes="Reviewed by practice manager monthly.",
            )
            assert r.status_code == 201, f"step {i} failed: {r.text}"

        # Step 6: List — three tools present.
        tools_resp = agent.list_tools()
        assert tools_resp.status_code == 200
        assert len(tools_resp.json()) == 3

        # Step 7: Dashboard summary.
        dash = agent.view_dashboard()
        assert dash.status_code == 200

        # Step 8: Billing plans visible.
        plans = agent.view_billing_plans()
        assert plans.status_code == 200
    finally:
        app.dependency_overrides.clear()

    # Transcript invariant: NO PHI in any captured response body.
    leaks = _scan_transcript_for_phi(transcript)
    assert leaks == [], f"PHI leaked into agent transcript: {leaks}"
    # And we recorded every expected step.
    intents = {step[0] for step in transcript.steps}
    assert {
        "get_baa_status",
        "accept_baa",
        "register_tool",
        "list_tools",
        "view_dashboard",
        "view_billing_plans",
    } <= intents


def test_phi_blocked_scenario(db_session) -> None:
    """Tool registration with PHI in notes → 422; transcript must NOT echo SSN."""
    c, _org, _user = _make_authed_client(db_session, tier="clinic_basic", baa_signed=True)
    transcript = AgentTranscript()
    agent = ClinicAdminAgent(c, transcript)
    try:
        r = agent.register_tool(
            name="Sneaky Tool",
            vendor="Acme",
            notes="Patient SSN: 123-45-6789 was leaked here",
        )
        assert r.status_code == 422
        body = r.json()
        # The agent's response detail must NOT echo the SSN string.
        assert "123-45-6789" not in r.text
        assert body["detail"]["error"] == "phi_in_freetext"
    finally:
        app.dependency_overrides.clear()
    # Transcript scan: the agent's recorded body MUST not contain the SSN
    # because the API stripped it from the error message.
    for intent, _status, body in transcript.steps:
        assert "123-45-6789" not in body, (
            f"SSN leaked into agent transcript on intent {intent!r}: {body!r}"
        )


def test_tier_block_scenario(db_session) -> None:
    """Enterprise-tier user attempts clinic onboarding → 403."""
    c, _org, _user = _make_authed_client(db_session, tier="enterprise", baa_signed=False)
    transcript = AgentTranscript()
    agent = ClinicAdminAgent(c, transcript)
    try:
        r = agent.get_baa_status()
        assert r.status_code == 403
        assert r.json()["detail"]["error"] == "tier_required"
    finally:
        app.dependency_overrides.clear()


def test_baa_required_scenario(db_session) -> None:
    """clinic-with-no-BAA tries to register a tool → 403 with error=baa_required."""
    c, _org, _user = _make_authed_client(db_session, tier="clinic_basic", baa_signed=False)
    transcript = AgentTranscript()
    agent = ClinicAdminAgent(c, transcript)
    try:
        r = agent.register_tool(name="Premature Tool", vendor="Foo")
        assert r.status_code == 403
        assert r.json()["detail"]["error"] == "baa_required"
    finally:
        app.dependency_overrides.clear()


def test_e2e_billing_to_clinic_flow(db_session, client) -> None:
    """End-to-end via Stripe webhook → clinic agent operates on the upgraded org.

    A new enterprise org receives a Stripe checkout webhook → tier flips
    to clinic_standard → agent (re-authenticated with that org's admin)
    can now access clinic routes.
    """
    org = make_clinic_org(
        db_session, tier="enterprise", baa_signed=False, slug="upgraded-clinic"
    )
    secret = os.environ["STRIPE_WEBHOOK_SECRET"]
    evt = checkout_session_completed(
        customer="cus_agent_e2e",
        subscription="sub_agent_e2e",
        client_reference_id="clinic_standard",
        org_slug="upgraded-clinic",
    )
    body, sig = serialize_and_sign(evt, secret=secret)
    resp = client.post(
        "/v1/billing/clinic/webhook",
        content=body,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig},
    )
    assert resp.status_code == 200
    db_session.refresh(org)
    assert org.tier == "clinic_standard"

    # Now spin up an admin for the upgraded org and verify clinic access.
    user, jwt = make_clinic_admin(db_session, org)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        c = TestClient(app, raise_server_exceptions=True)
        c.headers.update({"Authorization": f"Bearer {jwt}"})
        transcript = AgentTranscript()
        agent = ClinicAdminAgent(c, transcript)
        # Standard tier uses bundled BAA; cannot click-through accept.
        baa = agent.get_baa_status()
        assert baa.status_code == 200
        assert baa.json()["mode"] == "executed_bundled"
        # Tools list is empty but accessible.
        tools = agent.list_tools()
        assert tools.status_code == 200
    finally:
        app.dependency_overrides.clear()
