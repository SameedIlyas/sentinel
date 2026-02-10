"""Agent database model"""

from sqlalchemy import Column, String, DateTime, JSON, Enum
from datetime import datetime
import enum

from policy_engine.database import Base


class AgentStatus(str, enum.Enum):
    """Agent status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class Agent(Base):
    """
    Agent model representing an AI agent in the system
    
    Attributes:
        id: Unique agent identifier
        name: Human-readable agent name
        description: Agent description
        owner_user_id: ID of the user who owns this agent
        created_at: Timestamp when agent was created
        last_active: Timestamp of last agent activity
        status: Current agent status (active/inactive/suspended)
        llm_provider: LLM provider used by agent (openai, anthropic, etc.)
        metadata: Additional agent metadata as JSON
    """
    __tablename__ = "agents"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    owner_user_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_active = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(Enum(AgentStatus), default=AgentStatus.ACTIVE, nullable=False)
    llm_provider = Column(String, nullable=True)
    metadata = Column(JSON, default=dict, nullable=False)
