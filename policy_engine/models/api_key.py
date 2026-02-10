"""API Key database model"""

from sqlalchemy import Column, String, DateTime, Boolean
from datetime import datetime

from policy_engine.database import Base


class APIKey(Base):
    """
    API Key model for agent authentication
    
    Attributes:
        key: The API key (hashed)
        agent_id: ID of the agent this key belongs to
        name: Human-readable name for the key
        created_at: When the key was created
        last_used: When the key was last used
        expires_at: When the key expires (optional)
        is_active: Whether the key is currently active
    """
    __tablename__ = "api_keys"
    
    key = Column(String, primary_key=True, index=True)
    agent_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
