"""Cache management endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import logging

from policy_engine.database import get_db
from policy_engine.auth.api_key import get_current_agent
from policy_engine.services.policy_evaluation import PolicyEvaluationService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/stats")
async def get_cache_stats(
    agent_id: str = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    Get cache statistics
    
    Args:
        agent_id: Authenticated agent ID
        db: Database session
        
    Returns:
        Cache statistics
    """
    eval_service = PolicyEvaluationService(db)
    stats = eval_service.get_cache_stats()
    
    return {
        "success": True,
        "stats": stats
    }


@router.post("/invalidate")
async def invalidate_cache(
    policy_id: str = None,
    agent_id_to_invalidate: str = None,
    authenticated_agent_id: str = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    Invalidate cache entries
    
    Args:
        policy_id: Optional policy ID to invalidate
        agent_id_to_invalidate: Optional agent ID to invalidate
        authenticated_agent_id: Authenticated agent ID
        db: Database session
        
    Returns:
        Invalidation result
    """
    eval_service = PolicyEvaluationService(db)
    
    try:
        invalidated = eval_service.invalidate_cache(
            policy_id=policy_id,
            agent_id=agent_id_to_invalidate
        )
        
        return {
            "success": True,
            "message": f"Invalidated {invalidated} cache entries",
            "invalidated_count": invalidated
        }
    except Exception as e:
        logger.error(f"Failed to invalidate cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to invalidate cache: {str(e)}"
        )


@router.post("/warm")
async def warm_cache(
    agent_id_to_warm: str,
    frequent_tools: List[Dict[str, Any]],
    authenticated_agent_id: str = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    Warm cache with frequently used policy decisions
    
    Args:
        agent_id_to_warm: Agent ID to warm cache for
        frequent_tools: List of frequently used tool calls
        authenticated_agent_id: Authenticated agent ID
        db: Database session
        
    Returns:
        Cache warming result
    """
    eval_service = PolicyEvaluationService(db)
    
    try:
        warmed = eval_service.warm_cache_for_agent(agent_id_to_warm, frequent_tools)
        
        return {
            "success": True,
            "message": f"Warmed {warmed} cache entries for agent {agent_id_to_warm}",
            "warmed_count": warmed
        }
    except Exception as e:
        logger.error(f"Failed to warm cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to warm cache: {str(e)}"
        )


@router.delete("/clear")
async def clear_cache(
    agent_id: str = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    Clear all cache entries (use with caution)
    
    Args:
        agent_id: Authenticated agent ID
        db: Database session
        
    Returns:
        Clear result
    """
    eval_service = PolicyEvaluationService(db)
    
    try:
        eval_service.clear_cache()
        
        return {
            "success": True,
            "message": "All cache entries cleared"
        }
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}"
        )
