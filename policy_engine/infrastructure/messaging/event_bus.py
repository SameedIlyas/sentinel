"""In-process event bus with optional Redis pub/sub backend."""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DomainEvent:
    payload: Dict[str, Any]
    event_type: str = "domain.event"
    org_id: str = ""
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PolicyEvaluatedEvent(DomainEvent):
    event_type: str = "policy.evaluated"


@dataclass
class AlertCreatedEvent(DomainEvent):
    event_type: str = "alert.created"


@dataclass
class AuditLogCreatedEvent(DomainEvent):
    event_type: str = "audit_log.created"


@dataclass
class AgentRegisteredEvent(DomainEvent):
    event_type: str = "agent.registered"


class EventBus:
    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._handlers: Dict[str, List[Callable]] = {}
        self._fallback_queue: List[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        try:
            if self._redis:
                self._redis.publish(
                    f"sentinel:events:{event.event_type}",
                    json.dumps({
                        "event_type": event.event_type,
                        "payload": event.payload,
                        "org_id": event.org_id,
                        "timestamp": event.timestamp,
                        "correlation_id": event.correlation_id,
                    }),
                )
        except Exception as e:
            logger.warning("EventBus Redis publish failed, using in-memory: %s", e)
            self._fallback_queue.append(event)

        # Dispatch to in-process subscribers
        for handler in self._handlers.get(event.event_type, []):
            try:
                handler(event)
            except Exception as e:
                logger.warning("EventBus handler error for %s: %s", event.event_type, e)

    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._handlers.setdefault(event_type, []).append(handler)


_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
