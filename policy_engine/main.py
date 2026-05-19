"""FastAPI application entry point for Policy Engine"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys
from contextlib import asynccontextmanager

from policy_engine.config import settings
from policy_engine.middleware.logging import LoggingMiddleware
from policy_engine.middleware.error_handler import ErrorHandlerMiddleware
from policy_engine.middleware.rate_limiter import RateLimitMiddleware
from policy_engine.middleware.csrf import CSRFMiddleware
from policy_engine.middleware.tenant_context import TenantContextMiddleware
from policy_engine.routes import health, agents, policies, policy_check, audit, alerts, auth, users, dashboard, websocket, cache, organizations
from policy_engine.routes import ws_ticket
from policy_engine.routes import phi
from policy_engine.routes.clinical import model_cards as clinical_model_cards
from policy_engine.routes.clinical import bias_audits as clinical_bias_audits
from policy_engine.routes.clinical import drift as clinical_drift
from policy_engine.routes.clinical import hitl as clinical_hitl
from policy_engine.routes.admin import shadow_ai as admin_shadow_ai
from policy_engine.routes.admin import scribe_audits as admin_scribe_audits
from policy_engine.routes.admin import transparency as admin_transparency
from policy_engine.routes.finance import prior_auth as finance_prior_auth
from policy_engine.routes.finance import revenue_cycle as finance_revenue_cycle
from policy_engine.routes.regulatory import technical_files as regulatory_technical_files
from policy_engine.routes.regulatory import adverse_events as regulatory_adverse_events
from policy_engine.routes.regulatory import pms_reports as regulatory_pms_reports
from policy_engine.routes.regulatory import risk_scores as regulatory_risk_scores
from policy_engine.routes import fhir as fhir_routes
from policy_engine.routes import dicom as dicom_routes
from policy_engine.routes import domain_events as domain_events_routes
# Clinic-tier routes
from policy_engine.routes.clinic import tools as clinic_tools
from policy_engine.routes.clinic import onboarding as clinic_onboarding
from policy_engine.routes.clinic import reports as clinic_reports
from policy_engine.routes.clinic import policy_templates as clinic_policy_templates
from policy_engine.routes.clinic import alerts as clinic_alerts
from policy_engine.routes.clinic import baa as clinic_baa
from policy_engine.routes.clinic import settings as clinic_settings
from policy_engine.routes.clinic import shadow_ai as clinic_shadow_ai
from policy_engine.routes.clinic import dashboard as clinic_dashboard
from policy_engine.routes.billing import clinic as billing_clinic

# Import clinical models so they are registered with Base
from policy_engine.models import model_card, bias_audit, drift, hitl  # noqa: F401
# Import admin governance models so they are registered with Base
from policy_engine.models import shadow_ai as shadow_ai_models  # noqa: F401
from policy_engine.models import scribe_audit as scribe_audit_models  # noqa: F401
from policy_engine.models import transparency as transparency_models  # noqa: F401
# Import finance models so they are registered with Base
from policy_engine.models import prior_auth as prior_auth_models  # noqa: F401
from policy_engine.models import revenue_cycle as revenue_cycle_models  # noqa: F401
# Import regulatory models so they are registered with Base
from policy_engine.models import technical_file as technical_file_models  # noqa: F401
from policy_engine.models import post_market as post_market_models  # noqa: F401
from policy_engine.models import risk_score as risk_score_models  # noqa: F401
# Import Phase 5 models so they are registered with Base
from policy_engine.models import fhir_cache as fhir_cache_models  # noqa: F401
from policy_engine.models import dicom_metadata as dicom_metadata_models  # noqa: F401
# Clinic-tier models so they are registered with Base
from policy_engine.models import clinic as clinic_models  # noqa: F401
from policy_engine.routes.domain_events import DomainEvent  # noqa: F401  — registers table

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


_WEAK_KEYS = {"change-me-in-production", "your-secret-key-change-this-in-production"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # SECRET_KEY strength checks — enforced in ALL environments
    if not settings.SECRET_KEY:
        raise RuntimeError("SECRET_KEY must be set")
    if len(settings.SECRET_KEY) < settings.MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY must be at least {settings.MIN_SECRET_KEY_LENGTH} characters"
        )
    if settings.SECRET_KEY in _WEAK_KEYS:
        raise RuntimeError(
            "SECRET_KEY is a known weak default — please generate a strong key"
        )
    # CORS production guard
    if settings.CORS_ALLOW_ALL_ORIGINS and settings.APP_ENV == "production":
        raise RuntimeError("CORS_ALLOW_ALL_ORIGINS=True is not allowed in production")
    if "*" in settings.CORS_ORIGINS:
        logger.warning("CORS_ORIGINS contains wildcard '*' — this allows all origins")

    # CRIT-013 — production must not boot on the in-memory WS ticket
    # fallback (it doesn't span replicas, so tickets minted on one pod
    # cannot be consumed on another).
    from policy_engine.services.ws_ticket_store import ensure_production_safe
    ensure_production_safe()

    logger.info("Starting Policy Engine service...")

    # ── Tier 2 Sprint 2-5: register periodic background jobs ────────────────
    from policy_engine.services.scheduler import get_scheduler
    from policy_engine.services import (
        drift_ingestion,
        mlflow_auto_sync,
        pms_auto_service,
        risk_recompute,
    )

    scheduler = get_scheduler()
    # Idempotency guard — the scheduler is a module-level singleton, so
    # any process that re-enters the lifespan (graceful redeploy, hot
    # reload, pytest TestClient re-entered per test) would otherwise hit
    # ``scheduler.register()``'s "Job already registered" guard and crash.
    # Skip the entire registration block when jobs are already present.
    _already_registered = bool(scheduler.list_jobs())
    if _already_registered:
        logger.info("Scheduler already has jobs registered; skipping re-register")
    if not _already_registered and mlflow_auto_sync.is_enabled():
        scheduler.register(
            name="mlflow_auto_sync",
            interval_seconds=mlflow_auto_sync.sync_interval_seconds(),
            initial_delay_seconds=30.0,
            func=mlflow_auto_sync.make_sync_job(
                tracking_uri=settings.MLFLOW_TRACKING_URI,
            ),
        )
    if not _already_registered and risk_recompute.is_enabled():
        scheduler.register(
            name="risk_recompute",
            interval_seconds=risk_recompute.recompute_interval_seconds(),
            initial_delay_seconds=120.0,
            func=risk_recompute.make_recompute_job(),
        )
    if not _already_registered and pms_auto_service.is_enabled():
        scheduler.register(
            name="pms_auto_generate",
            interval_seconds=pms_auto_service.auto_interval_seconds(),
            initial_delay_seconds=180.0,
            func=pms_auto_service.make_auto_generate_job(),
        )
    if not _already_registered and drift_ingestion.is_recompute_enabled():
        scheduler.register(
            name="drift_auto_recompute",
            interval_seconds=drift_ingestion.recompute_interval_seconds(),
            initial_delay_seconds=240.0,
            func=drift_ingestion.make_recompute_job(),
        )

    # Clinic-tier monthly compliance PDF generator
    from policy_engine.services import clinic_pdf_report
    if not _already_registered and clinic_pdf_report.is_enabled():
        scheduler.register(
            name="clinic_monthly_report",
            interval_seconds=clinic_pdf_report.interval_seconds(),
            initial_delay_seconds=300.0,
            func=clinic_pdf_report.make_monthly_report_job(),
        )

    # Clinic-tier subscription lifecycle (revert canceled subs after grace)
    from policy_engine.services import subscription_lifecycle
    if not _already_registered and subscription_lifecycle.is_enabled():
        scheduler.register(
            name="clinic_subscription_lifecycle",
            interval_seconds=subscription_lifecycle.interval_seconds(),
            initial_delay_seconds=600.0,
            func=subscription_lifecycle.make_lifecycle_job(),
        )

    # Clinic-tier retention sweep (GDPR Art. 5(e) storage limitation)
    from policy_engine.services import clinic_retention
    if not _already_registered and clinic_retention.is_enabled():
        scheduler.register(
            name="clinic_retention_sweep",
            interval_seconds=clinic_retention.interval_seconds(),
            initial_delay_seconds=900.0,
            func=clinic_retention.make_retention_job(),
        )

    scheduler.start()

    try:
        yield
    finally:
        logger.info("Shutting down Policy Engine service...")
        await scheduler.stop()


# Create FastAPI application
app = FastAPI(
    title="Sentinel AI Policy Engine",
    description="Real-time security and policy enforcement for AI agents",
    version="0.1.0",
    lifespan=lifespan
)

# Add custom middleware (added first = runs innermost)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(LoggingMiddleware)

# CORS must be added LAST so it runs as the outermost middleware,
# ensuring CORS headers are present on ALL responses including errors.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/v1/auth", tags=["authentication"])
app.include_router(users.router, prefix="/v1/users", tags=["users"])
app.include_router(dashboard.router, prefix="/v1/dashboard", tags=["dashboard"])
app.include_router(websocket.router, tags=["websocket"])  # WebSocket doesn't use prefix
app.include_router(ws_ticket.router, prefix="/v1", tags=["websocket"])  # CRIT-013
app.include_router(agents.router, prefix="/v1/agents", tags=["agents"])
app.include_router(policies.router, prefix="/v1/policies", tags=["policies"])
app.include_router(policy_check.router, prefix="/v1/policy", tags=["policy-evaluation"])
app.include_router(audit.router, prefix="/v1/audit", tags=["audit"])
app.include_router(alerts.router, prefix="/v1/alerts", tags=["alerts"])
app.include_router(cache.router, prefix="/v1/cache", tags=["cache"])
app.include_router(organizations.router, prefix="/v1/organizations", tags=["organizations"])
app.include_router(phi.router, prefix="/v1/phi", tags=["phi"])
app.include_router(clinical_model_cards.router, prefix="/v1/clinical", tags=["clinical-model-cards"])
app.include_router(clinical_bias_audits.router, prefix="/v1/clinical", tags=["clinical-bias-audits"])
app.include_router(clinical_drift.router, prefix="/v1/clinical", tags=["clinical-drift"])
app.include_router(clinical_hitl.router, prefix="/v1/clinical", tags=["clinical-hitl"])
app.include_router(admin_shadow_ai.router, prefix="/v1/admin", tags=["admin-shadow-ai"])
app.include_router(admin_scribe_audits.router, prefix="/v1/admin", tags=["admin-scribe-audits"])
app.include_router(admin_transparency.router, prefix="/v1", tags=["transparency"])
app.include_router(finance_prior_auth.router, prefix="/v1/finance", tags=["finance-prior-auth"])
app.include_router(finance_revenue_cycle.router, prefix="/v1/finance", tags=["finance-revenue-cycle"])
app.include_router(regulatory_technical_files.router, prefix="/v1/regulatory", tags=["regulatory-technical-files"])
app.include_router(regulatory_adverse_events.router, prefix="/v1/regulatory", tags=["regulatory-adverse-events"])
app.include_router(regulatory_pms_reports.router, prefix="/v1/regulatory", tags=["regulatory-pms-reports"])
app.include_router(regulatory_risk_scores.router, prefix="/v1", tags=["risk-scoring"])
app.include_router(fhir_routes.router, prefix="/v1", tags=["fhir"])
app.include_router(dicom_routes.router, prefix="/v1", tags=["dicom"])
app.include_router(domain_events_routes.router, prefix="/v1", tags=["domain-events"])

# ── Clinic-tier routers ────────────────────────────────────────────────
app.include_router(clinic_dashboard.router, prefix="/v1/clinic", tags=["clinic-dashboard"])
app.include_router(clinic_tools.router, prefix="/v1/clinic", tags=["clinic-tools"])
app.include_router(clinic_onboarding.router, prefix="/v1/clinic", tags=["clinic-onboarding"])
app.include_router(clinic_reports.router, prefix="/v1/clinic", tags=["clinic-reports"])
app.include_router(clinic_policy_templates.router, prefix="/v1/clinic", tags=["clinic-policies"])
app.include_router(clinic_alerts.router, prefix="/v1/clinic", tags=["clinic-alerts"])
app.include_router(clinic_baa.router, prefix="/v1/clinic", tags=["clinic-baa"])
app.include_router(clinic_settings.router, prefix="/v1/clinic", tags=["clinic-settings"])
app.include_router(clinic_shadow_ai.router, prefix="/v1/clinic", tags=["clinic-shadow-ai"])
app.include_router(billing_clinic.router, prefix="/v1/billing", tags=["billing-clinic"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Sentinel AI Policy Engine",
        "version": "0.1.0",
        "status": "running"
    }
