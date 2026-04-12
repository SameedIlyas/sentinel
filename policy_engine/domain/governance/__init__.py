"""Governance domain — pure Python entities, no framework imports."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PolicyEntity:
    """Pure domain representation of a governance policy."""
    id: str
    name: str
    policy_type: str
    rules: Dict[str, Any] = field(default_factory=dict)
    org_id: Optional[str] = None
    is_active: bool = True
    version: int = 1


@dataclass
class AgentEntity:
    """Pure domain representation of an AI agent."""
    id: str
    name: str
    agent_type: str
    org_id: Optional[str] = None
    is_active: bool = True
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


__all__ = ["PolicyEntity", "AgentEntity"]
