"""Single-use ticket issuance for WebSocket handshakes (CRIT-013).

The JWT bearer token must stay out of the WebSocket URL. The dashboard
posts here with its normal ``Authorization: Bearer <jwt>`` header, gets
a short-lived ticket, and opens the WebSocket with ``?ticket=<id>``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from policy_engine.auth.rbac import get_current_user
from policy_engine.models.user import User
from policy_engine.services.ws_ticket_store import (
    TICKET_TTL_SECONDS,
    get_ws_ticket_store,
)


router = APIRouter()


class WSTicketResponse(BaseModel):
    ticket: str
    expires_in: int


@router.post("/ws/ticket", response_model=WSTicketResponse)
def issue_ws_ticket(current_user: User = Depends(get_current_user)) -> WSTicketResponse:
    """Issue a fresh single-use WebSocket ticket for the caller.

    The ticket is opaque (CSPRNG-derived) and bound to the caller's
    ``user_id``. It expires after :data:`TICKET_TTL_SECONDS` and is
    invalidated on first use.
    """
    store = get_ws_ticket_store()
    ticket = store.issue(current_user.id)
    return WSTicketResponse(ticket=ticket, expires_in=TICKET_TTL_SECONDS)
