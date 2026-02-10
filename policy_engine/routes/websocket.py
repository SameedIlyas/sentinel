"""
WebSocket support for real-time dashboard updates

Provides WebSocket endpoints for streaming dashboard metrics and events
to connected clients.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
import asyncio
import json
import logging
from datetime import datetime
from typing import List, Set

from policy_engine.database import get_db
from policy_engine.routes.dashboard import get_dashboard_metrics
from policy_engine.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

# Store active WebSocket connections
active_connections: Set[WebSocket] = set()


class ConnectionManager:
    """Manages WebSocket connections and broadcasting"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Accept and store a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
    
    async def broadcast(self, message: str):
        """Broadcast a message to all connected WebSockets"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


@router.websocket("/ws/dashboard")
async def dashboard_websocket(
    websocket: WebSocket,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time dashboard updates
    
    Sends dashboard metrics every 30 seconds to meet the 60-second
    latency requirement from Requirement 5.6
    
    Message format:
    {
        "type": "metrics_update",
        "timestamp": "2024-02-11T...",
        "data": { ...dashboard metrics... }
    }
    """
    await manager.connect(websocket)
    
    try:
        # Send initial metrics immediately upon connection
        try:
            metrics = await get_dashboard_metrics(db=db, current_user=None)
            message = {
                "type": "metrics_update",
                "timestamp": datetime.utcnow().isoformat(),
                "data": metrics.model_dump()
            }
            await manager.send_personal_message(json.dumps(message), websocket)
        except Exception as e:
            logger.error(f"Error sending initial metrics: {e}")
        
        # Start periodic updates
        while True:
            try:
                # Wait for 30 seconds before next update
                await asyncio.sleep(30)
                
                # Fetch latest metrics
                metrics = await get_dashboard_metrics(db=db, current_user=None)
                
                # Send update to this client
                message = {
                    "type": "metrics_update",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": metrics.model_dump()
                }
                await manager.send_personal_message(json.dumps(message), websocket)
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}")
                await asyncio.sleep(30)  # Continue trying
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@router.websocket("/ws/events")
async def events_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time event notifications
    
    Streams events like new alerts, blocked actions, policy violations, etc.
    
    Message format:
    {
        "type": "event",
        "event_type": "alert" | "blocked_action" | "new_agent",
        "timestamp": "2024-02-11T...",
        "data": { ...event data... }
    }
    """
    await manager.connect(websocket)
    
    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(10)
            
            # Send heartbeat
            heartbeat = {
                "type": "heartbeat",
                "timestamp": datetime.utcnow().isoformat()
            }
            await manager.send_personal_message(json.dumps(heartbeat), websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Events client disconnected")
    except Exception as e:
        logger.error(f"Events WebSocket error: {e}")
        manager.disconnect(websocket)


async def broadcast_event(event_type: str, data: dict):
    """
    Broadcast an event to all connected WebSocket clients
    
    Args:
        event_type: Type of event (alert, blocked_action, new_agent, etc.)
        data: Event data to broadcast
    """
    message = {
        "type": "event",
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data
    }
    await manager.broadcast(json.dumps(message))


# This function can be called from other parts of the application
# to push real-time updates to connected clients
async def notify_dashboard_update():
    """Notify all connected clients of a dashboard update"""
    message = {
        "type": "refresh_request",
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast(json.dumps(message))
