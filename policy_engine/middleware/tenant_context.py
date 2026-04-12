"""Tenant context middleware — injects org_id from JWT into DB session."""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from policy_engine.auth.jwt_utils import decode_access_token

logger = logging.getLogger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Extracts org_id from the JWT bearer token and stores it in request.state.

    For PostgreSQL, you would also execute:
        SET LOCAL app.current_org_id = '<org_id>'
    before each query to activate Row-Level Security.  The async route layer
    is responsible for calling that statement via the AsyncSession.

    For SQLite (tests), no SET LOCAL is issued — application-level filtering
    is used instead.
    """

    async def dispatch(self, request: Request, call_next):
        org_id = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):]
            payload = decode_access_token(token)
            if payload:
                org_id = payload.get("org_id")

        request.state.org_id = org_id
        response = await call_next(request)
        return response
