"""FastAPI application entry point for Policy Engine"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import sys
from contextlib import asynccontextmanager

from policy_engine.config import settings
from policy_engine.middleware.logging import LoggingMiddleware
from policy_engine.middleware.error_handler import ErrorHandlerMiddleware
from policy_engine.middleware.rate_limiter import RateLimitMiddleware
from policy_engine.routes import health, agents, policies, policy_check, audit, alerts, auth, users, dashboard, websocket

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(RateLimitMiddleware)

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


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Sentinel AI Policy Engine",
        "version": "0.1.0",
        "status": "running"
    }
