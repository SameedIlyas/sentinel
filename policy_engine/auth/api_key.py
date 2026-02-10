"""API Key authentication"""

from fastapi import Header, HTTPException, Depends, status
from sqlalchemy.orm import Session
from datetime import datetime
import hashlib

from policy_engine.database import get_db
from policy_engine.models.api_key import APIKey
from policy_engine.config import settings


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for storage
    
    Args:
        api_key: The raw API key
        
    Returns:
        Hashed API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


async def verify_api_key(
    x_api_key: str = Header(..., alias=settings.API_KEY_HEADER),
    db: Session = Depends(get_db)
) -> str:
    """
    Verify API key and return agent_id
    
    Args:
        x_api_key: API key from header
        db: Database session
        
    Returns:
        Agent ID associated with the API key
        
    Raises:
        HTTPException: If API key is invalid or expired
    """
    # Hash the provided key
    key_hash = hash_api_key(x_api_key)
    
    # Look up the key in database
    api_key_record = db.query(APIKey).filter(APIKey.key == key_hash).first()
    
    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    if not api_key_record.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is inactive"
        )
    
    if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired"
        )
    
    # Update last_used timestamp
    api_key_record.last_used = datetime.utcnow()
    db.commit()
    
    return api_key_record.agent_id


async def get_current_agent(agent_id: str = Depends(verify_api_key)) -> str:
    """
    Get current authenticated agent ID
    
    Args:
        agent_id: Agent ID from API key verification
        
    Returns:
        Agent ID
    """
    return agent_id
