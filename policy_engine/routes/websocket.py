"""WebSocket endpoints for real-time dashboard updates.

CRIT-013 — these handshakes accept a short-lived ``?ticket=`` query
parameter, not a JWT. The JWT never reaches the URL. See
:mod:`policy_engine.services.ws_ticket_store` and
:mod:`policy_engine.routes.ws_ticket` for the ticket protocol.

The WebSocket closes with code ``4401`` on missing / expired / used
ticket, distinct from the legacy ``4001`` close code so a connecting
client can tell unsupported auth from a token problem.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
import asyncio
import json
import logging
from datetime import datetime
from typing import List, Optional, Set

from policy_engine.database import get_db
from policy_engine.routes.dashboard import get_dashboard_metrics
from policy_engine.services.ws_ticket_store import get_ws_ticket_store

logger = logging.getLogger(__name__)

router = APIRouter()

# Store active WebSocket connections
active_connections: Set[WebSocket] = set()

# Close codes documented at the WebSocket layer for the dashboard.
WS_CLOSE_BAD_TICKET = 4401


class ConnectionManager:
    """Manages WebSocket connections and broadcasting."""

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            "WebSocket connected. Total connections: %d",
            len(self.active_connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            "WebSocket disconnected. Total connections: %d",
            len(self.active_connections),
        )

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error("Error sending personal message: %s", e)

    async def broadcast(self, message: str) -> None:
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error("Error broadcasting to connection: %s", e)
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


def _authenticate_ws_ticket(ticket: Optional[str]) -> Optional[str]:
    """Atomically exchange a ticket for the bound ``user_id``.

    Returns ``None`` if the ticket is missing, expired, already
    consumed, or never existed. The ticket store deletes the entry on
    read so a replay of the same ticket fails.
    """
    if not ticket:
        return None
    return get_ws_ticket_store().consume(ticket)


@router.websocket("/ws/dashboard")
async def dashboard_websocket(
    websocket: WebSocket,
    ticket: Optional[str] = None,
    db: Session = Depends(get_db),
) -> None:
    """WebSocket endpoint for real-time dashboard updates."""
    user_id = _authenticate_ws_ticket(ticket)
    if user_id is None:
        await websocket.close(code=WS_CLOSE_BAD_TICKET)
        return

    await manager.connect(websocket)

    try:
        try:
            metrics = await get_dashboard_metrics(db=db, current_user=None)
            message = {
                "type": "metrics_update",
                "timestamp": datetime.utcnow().isoformat(),
                "data": metrics.model_dump(),
            }
            await manager.send_personal_message(json.dumps(message), websocket)
        except Exception as e:
            logger.error("Error sending initial metrics: %s", e)

        while True:
            try:
                await asyncio.sleep(30)
                metrics = await get_dashboard_metrics(db=db, current_user=None)
                message = {
                    "type": "metrics_update",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": metrics.model_dump(),
                }
                await manager.send_personal_message(json.dumps(message), websocket)
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error("Error in WebSocket loop: %s", e)
                await asyncio.sleep(30)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        manager.disconnect(websocket)


@router.websocket("/ws/events")
async def events_websocket(
    websocket: WebSocket, ticket: Optional[str] = None
) -> None:
    """WebSocket endpoint for real-time event notifications."""
    user_id = _authenticate_ws_ticket(ticket)
    if user_id is None:
        await websocket.close(code=WS_CLOSE_BAD_TICKET)
        return

    await manager.connect(websocket)

    try:
        while True:
            await asyncio.sleep(10)
            heartbeat = {
                "type": "heartbeat",
                "timestamp": datetime.utcnow().isoformat(),
            }
            await manager.send_personal_message(json.dumps(heartbeat), websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Events client disconnected")
    except Exception as e:
        logger.error("Events WebSocket error: %s", e)
        manager.disconnect(websocket)


async def broadcast_event(event_type: str, data: dict) -> None:
    """Broadcast an event to every connected WebSocket client."""
    message = {
        "type": "event",
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data,
    }
    await manager.broadcast(json.dumps(message))


async def notify_dashboard_update() -> None:
    """Notify every connected client of a dashboard refresh."""
    message = {
        "type": "refresh_request",
        "timestamp": datetime.utcnow().isoformat(),
    }
    await manager.broadcast(json.dumps(message))
