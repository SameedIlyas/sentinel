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
    logger.info("Starting Policy Engine service...")
    yield
    logger.info("Shutting down Policy Engine service...")


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


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Sentinel AI Policy Engine",
        "version": "0.1.0",
        "status": "running"
    }
