"""Clinic billing — Stripe Payment Links, Customer Portal, and webhook.

Endpoints
---------
``GET  /v1/billing/clinic/plans``         — list of clinic SKUs + their
  Stripe Payment Link URLs (pulled from env vars).
``GET  /v1/billing/clinic/payment-link``  — single-plan link lookup.
``POST /v1/billing/clinic/portal``        — issue a Stripe Customer
  Portal session for the current org.
``POST /v1/billing/clinic/webhook``       — Stripe webhook receiver.
  Handles checkout, subscription, and invoice events.  Idempotent via
  ``billing_events.stripe_event_id``.

The webhook signature is verified end-to-end when
``STRIPE_WEBHOOK_SECRET`` is set; in dev / test it is skipped so the
``stripe trigger`` CLI works without round-tripping every event.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from policy_engine.auth.rbac import get_current_user
from policy_engine.billing.plans import (
    PLANS,
    is_clinic_plan,
    stripe_payment_link,
)
from policy_engine.billing.stripe_client import (
    StripeUnavailable,
    billing_portal_return_url,
    get_stripe,
    webhook_secret,
)
from policy_engine.database import get_db
from policy_engine.models.clinic import BillingEvent
from policy_engine.models.organization import (
    Organization,
    TIER_CLINIC_BASIC,
    TIER_CLINIC_MULTI_SITE,
    TIER_CLINIC_STANDARD,
)
from policy_engine.models.user import User
from policy_engine.services.tier_filter import require_clinic_tier

logger = logging.getLogger(__name__)
router = APIRouter()


# ── List + lookup ───────────────────────────────────────────────────────


class PlanSummary(BaseModel):
    tier: str
    display_name: str
    monthly_price_usd: int
    description: str
    payment_link_url: Optional[str]


@router.get("/clinic/plans", response_model=list[PlanSummary])
def list_clinic_plans():
    out = []
    for plan in PLANS.values():
        if not is_clinic_plan(plan.name):
            continue
        out.append(
            PlanSummary(
                tier=plan.name,
                display_name=plan.display_name,
                monthly_price_usd=plan.monthly_price_usd,
                description=plan.description,
                payment_link_url=stripe_payment_link(plan.name),
            )
        )
    return out


@router.get("/clinic/payment-link")
def payment_link(plan: str):
    if not is_clinic_plan(plan):
        raise HTTPException(status_code=400, detail="Unknown clinic plan")
    url = stripe_payment_link(plan)
    if not url:
        raise HTTPException(
            status_code=503,
            detail=(
                "Payment link not configured for this plan. "
                "Set the corresponding STRIPE_PAYMENT_LINK_* env var."
            ),
        )
    return {"plan": plan, "url": url}


# ── Customer Portal ─────────────────────────────────────────────────────


class PortalResponse(BaseModel):
    url: str


@router.post("/clinic/portal", response_model=PortalResponse)
def create_portal_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_clinic_tier),
):
    """Issue a Stripe Customer Portal URL for the current org.

    The portal lets customers update their card, view invoices, and
    cancel at period end.  Plan switching is disabled in the portal
    config (per BILLING_IMPLEMENTATION.md §7.4) so upgrades flow through
    our own checkout link and we capture the conversion event.
    """
    billing = (org.settings or {}).get("billing") or {}
    customer_id = billing.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(
            status_code=409,
            detail=(
                "No Stripe customer is associated with this practice yet. "
                "Complete a checkout first or contact support."
            ),
        )
    try:
        stripe = get_stripe()
    except StripeUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=billing_portal_return_url(),
        )
    except Exception as exc:  # pragma: no cover — Stripe-side failures
        logger.exception("Stripe portal session creation failed: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"Stripe portal error: {exc}"
        )
    return PortalResponse(url=session.url)


# ── Webhook ─────────────────────────────────────────────────────────────


def _is_production_env() -> bool:
    """Detect production from common signals so we can fail-closed there."""
    env = (os.environ.get("APP_ENV") or os.environ.get("ENVIRONMENT") or "").lower()
    return env in {"production", "prod", "live"}


def _verify_stripe_signature(payload: bytes, signature_header: Optional[str]) -> bool:
    secret = webhook_secret()
    if not secret:
        # Production fail-closed: refuse unsigned webhooks so a forgotten
        # env var cannot turn into a tier-flip attack vector.
        if _is_production_env():
            logger.error(
                "STRIPE_WEBHOOK_SECRET is not set in production — "
                "rejecting webhook to prevent unsigned tier flips."
            )
            return False
        # Non-prod — accept anything to keep the Stripe CLI replay path
        # frictionless during development and tests.
        return True
    if not signature_header:
        return False
    try:
        stripe = get_stripe()
        stripe.Webhook.construct_event(payload, signature_header, secret)
        return True
    except StripeUnavailable as exc:
        # SDK not installed — fail closed.
        logger.warning("Webhook signature requested but %s", exc)
        return False
    except Exception as exc:  # pragma: no cover — bad signature
        logger.warning("Stripe signature verification failed: %s", exc)
        return False


# ── PII redaction for the audit trail ───────────────────────────────────

_REDACT_DETAIL_KEYS = ("address", "phone", "tax_ids", "tax_exempt", "tax_id_data")


def _redact_event_for_audit(event: dict) -> dict:
    """Strip avoidable PII from the Stripe payload before we persist it.

    GDPR Art. 5(c) data minimisation — we keep enough to replay the
    event semantically (customer id, subscription id, status, plan) but
    drop billing addresses, phone numbers, and tax id details that we
    don't use for audit.
    """
    try:
        data_obj = ((event.get("data") or {}).get("object") or {})
        details = data_obj.get("customer_details")
        if isinstance(details, dict):
            for key in _REDACT_DETAIL_KEYS:
                details.pop(key, None)
        # Top-level customer billing fields some events expose.
        for key in _REDACT_DETAIL_KEYS:
            data_obj.pop(key, None)
        # Card fingerprint / last4 are not needed for our audit trail.
        if isinstance(data_obj.get("payment_method_details"), dict):
            data_obj["payment_method_details"] = {
                "type": data_obj["payment_method_details"].get("type"),
            }
    except Exception:  # pragma: no cover — defensive
        pass
    return event


_PLAN_LINK_ENV_TO_TIER = {
    "STRIPE_PAYMENT_LINK_CLINIC_BASIC": TIER_CLINIC_BASIC,
    "STRIPE_PAYMENT_LINK_CLINIC_STANDARD": TIER_CLINIC_STANDARD,
    "STRIPE_PAYMENT_LINK_CLINIC_MULTI_SITE": TIER_CLINIC_MULTI_SITE,
}


def _tier_from_session(session_obj: dict) -> Optional[str]:
    """Resolve which clinic tier a checkout session corresponds to."""
    client_ref = session_obj.get("client_reference_id")
    if client_ref in PLANS and is_clinic_plan(client_ref):
        return client_ref
    metadata = session_obj.get("metadata") or {}
    md_plan = metadata.get("plan") or metadata.get("tier")
    if md_plan in PLANS and is_clinic_plan(md_plan):
        return md_plan
    payment_link_id = session_obj.get("payment_link")
    if payment_link_id:
        for env_key, tier in _PLAN_LINK_ENV_TO_TIER.items():
            url = os.environ.get(env_key, "")
            if url and payment_link_id in url:
                return tier
    return None


def _resolve_org_for_session(db: Session, session_obj: dict) -> Optional[Organization]:
    org_slug = (session_obj.get("metadata") or {}).get("org_slug")
    if org_slug:
        org = db.query(Organization).filter(Organization.slug == org_slug).first()
        if org:
            return org
    customer_id = session_obj.get("customer")
    if customer_id:
        for org in db.query(Organization).all():
            billing = (org.settings or {}).get("billing") or {}
            if billing.get("stripe_customer_id") == customer_id:
                return org
    customer_email = (
        (session_obj.get("customer_details") or {}).get("email")
        or session_obj.get("customer_email")
    )
    if customer_email:
        # Best-effort domain match on stored billing_email.
        for org in db.query(Organization).all():
            billing = (org.settings or {}).get("billing") or {}
            if billing.get("billing_email") == customer_email:
                return org
    return None


def _resolve_org_by_customer(db: Session, customer_id: Optional[str]) -> Optional[Organization]:
    if not customer_id:
        return None
    for org in db.query(Organization).all():
        billing = (org.settings or {}).get("billing") or {}
        if billing.get("stripe_customer_id") == customer_id:
            return org
    return None


def _set_billing(org: Organization, **updates: Any) -> None:
    settings = dict(org.settings or {})
    billing = dict(settings.get("billing") or {})
    billing.update({k: v for k, v in updates.items() if v is not None})
    settings["billing"] = billing
    org.settings = settings
    flag_modified(org, "settings")
    org.updated_at = datetime.utcnow()


# ── Per-event handlers ──────────────────────────────────────────────────

HandlerResult = tuple[str, Optional[str], Optional[str]]
# (record_status, org_id_for_audit, error_message)


def _handle_checkout_completed(db: Session, event: dict, event_id: str) -> HandlerResult:
    session_obj = (event.get("data") or {}).get("object") or {}
    tier = _tier_from_session(session_obj)
    org = _resolve_org_for_session(db, session_obj)
    if not org or not tier:
        return ("skipped", None, "Could not resolve org or tier from session")
    org.tier = tier
    _set_billing(
        org,
        stripe_customer_id=session_obj.get("customer"),
        stripe_subscription_id=session_obj.get("subscription"),
        subscription_status="active",
        plan=tier,
        last_event_id=event_id,
        billing_email=(
            (session_obj.get("customer_details") or {}).get("email")
            or session_obj.get("customer_email")
        ),
    )
    return ("processed", org.id, None)


def _handle_subscription_updated(db: Session, event: dict, event_id: str) -> HandlerResult:
    sub = (event.get("data") or {}).get("object") or {}
    org = _resolve_org_by_customer(db, sub.get("customer"))
    if not org:
        return ("skipped", None, "No org matched stripe customer")
    status = sub.get("status")  # active | trialing | past_due | unpaid | canceled
    cancel_at_period_end = bool(sub.get("cancel_at_period_end"))
    period_end = sub.get("current_period_end")  # epoch seconds
    cancel_at = sub.get("cancel_at")
    _set_billing(
        org,
        stripe_subscription_id=sub.get("id"),
        subscription_status=("canceled" if status == "canceled" else status),
        cancel_at_period_end=cancel_at_period_end,
        current_period_end=period_end,
        cancel_at=cancel_at,
        last_event_id=event_id,
    )
    return ("processed", org.id, None)


def _handle_subscription_deleted(db: Session, event: dict, event_id: str) -> HandlerResult:
    """Customer canceled.  Keep tier (read access) until current_period_end;
    the ``subscription_lifecycle`` job reverts to enterprise after that."""
    sub = (event.get("data") or {}).get("object") or {}
    org = _resolve_org_by_customer(db, sub.get("customer"))
    if not org:
        return ("skipped", None, "No org matched stripe customer")
    period_end = sub.get("current_period_end")
    _set_billing(
        org,
        subscription_status="canceled",
        current_period_end=period_end,
        cancel_at=sub.get("cancel_at") or period_end,
        canceled_at=sub.get("canceled_at"),
        last_event_id=event_id,
    )
    return ("processed", org.id, None)


def _handle_invoice_payment_failed(db: Session, event: dict, event_id: str) -> HandlerResult:
    invoice = (event.get("data") or {}).get("object") or {}
    org = _resolve_org_by_customer(db, invoice.get("customer"))
    if not org:
        return ("skipped", None, "No org matched stripe customer")
    _set_billing(
        org,
        subscription_status="past_due",
        last_payment_failed_at=datetime.now(timezone.utc).isoformat(),
        last_failed_invoice_id=invoice.get("id"),
        last_event_id=event_id,
    )
    return ("processed", org.id, None)


def _handle_invoice_payment_succeeded(db: Session, event: dict, event_id: str) -> HandlerResult:
    invoice = (event.get("data") or {}).get("object") or {}
    org = _resolve_org_by_customer(db, invoice.get("customer"))
    if not org:
        return ("skipped", None, "No org matched stripe customer")
    # Recovery: if we marked past_due, this restores to active.  Otherwise no-op.
    billing = (org.settings or {}).get("billing") or {}
    updates: dict[str, Any] = {
        "last_payment_succeeded_at": datetime.now(timezone.utc).isoformat(),
        "last_invoice_id": invoice.get("id"),
        "last_event_id": event_id,
    }
    if billing.get("subscription_status") == "past_due":
        updates["subscription_status"] = "active"
        updates["last_payment_failed_at"] = None
        updates["last_failed_invoice_id"] = None
    _set_billing(org, **updates)
    return ("processed", org.id, None)


_HANDLERS: dict[str, Callable[[Session, dict, str], HandlerResult]] = {
    "checkout.session.completed": _handle_checkout_completed,
    "customer.subscription.created": _handle_subscription_updated,
    "customer.subscription.updated": _handle_subscription_updated,
    "customer.subscription.deleted": _handle_subscription_deleted,
    "invoice.payment_failed": _handle_invoice_payment_failed,
    "invoice.payment_succeeded": _handle_invoice_payment_succeeded,
}


@router.post("/clinic/webhook")
async def clinic_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
):
    payload = await request.body()
    if not _verify_stripe_signature(payload, stripe_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        event = json.loads(payload.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Malformed JSON")

    event_id = event.get("id") or f"evt_local_{uuid.uuid4().hex[:16]}"
    event_type = event.get("type") or "unknown"

    # Idempotency — same Stripe event arriving twice is a no-op.
    existing = (
        db.query(BillingEvent)
        .filter(BillingEvent.stripe_event_id == event_id)
        .first()
    )
    if existing is not None:
        return {"status": "skipped", "reason": "duplicate"}

    handler = _HANDLERS.get(event_type)
    record_status: str
    org_id_for_audit: Optional[str]
    error_message: Optional[str]

    try:
        if handler is None:
            record_status, org_id_for_audit, error_message = (
                "skipped",
                None,
                f"unhandled event type: {event_type}",
            )
        else:
            record_status, org_id_for_audit, error_message = handler(db, event, event_id)

        redacted_payload = _redact_event_for_audit(event)
        db.add(
            BillingEvent(
                id=str(uuid.uuid4()),
                org_id=org_id_for_audit,
                stripe_event_id=event_id,
                event_type=event_type,
                payload=redacted_payload,
                processed_at=datetime.utcnow(),
                status=record_status,
                error_message=error_message,
            )
        )
        db.commit()
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception("Webhook handler failed: %s", exc)
        db.rollback()
        db.add(
            BillingEvent(
                id=str(uuid.uuid4()),
                org_id=None,
                stripe_event_id=event_id,
                event_type=event_type,
                payload=_redact_event_for_audit(event),
                processed_at=datetime.utcnow(),
                status="failed",
                error_message=str(exc)[:500],
            )
        )
        db.commit()
        raise HTTPException(status_code=500, detail="Webhook processing failed")

    return {"status": record_status, "event_type": event_type}
