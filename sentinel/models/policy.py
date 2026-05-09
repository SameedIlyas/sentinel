"""Policy check request and response models."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

try:
    from pydantic import BaseModel, Field  # noqa: F401  (re-exported for downstream models)
except ImportError:
    # Fallback for environments without pydantic
    class BaseModel:  # type: ignore
        """Minimal BaseModel fallback."""
        def __init__(self, **kwargs: Any):
            for key, value in kwargs.items():
                setattr(self, key, value)
        
        def dict(self) -> Dict[str, Any]:
            return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}


class PolicyCheckRequest(BaseModel):
    """Request model for policy check API."""
    
    agent_id: str
    user_id: Optional[str] = None
    tool_name: str
    arguments: Dict[str, Any]
    context: Dict[str, Any]
    timestamp: str
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PolicyCheckResponse(BaseModel):
    """Response model for policy check API."""
    
    decision: Literal["allow", "block", "require_approval"]
    reason: str
    masked_data: Optional[Dict[str, Any]] = None
    policy_ids: List[str] = []
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
