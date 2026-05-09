"""Agent activity tracking service"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import List, Dict, Any, Tuple

from policy_engine.models.agent import Agent, AgentStatus
from policy_engine.models.audit_log import AuditLog


class AgentActivityService:
    """Service for tracking agent activity and metrics"""
    
    @staticmethod
    def update_last_active(db: Session, agent_id: str) -> None:
        """
        Update the last_active timestamp for an agent
        
        Args:
            db: Database session
            agent_id: Agent identifier
        """
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if agent:
            agent.last_active = datetime.utcnow()
            db.commit()
    
    @staticmethod
    def register_or_update_agent(
        db: Session,
        agent_id: str,
        agent_name: str = None,
        owner_user_id: str = None,
        llm_provider: str = None,
        metadata: Dict[str, Any] = None
    ) -> Tuple[Agent, bool]:
        """
        Register a new agent or update existing agent's last_active timestamp.
        Called automatically on every policy check.

        Args:
            db: Database session
            agent_id: Agent identifier
            agent_name: Agent name (optional, defaults to agent_id)
            owner_user_id: Owner user ID (optional, defaults to 'system')
            llm_provider: LLM provider (optional)
            metadata: Additional metadata (optional)

        Returns:
            (agent, is_new) — is_new is True when the agent was just created,
            False when an existing record was updated.
        """
        agent = db.query(Agent).filter(Agent.id == agent_id).first()

        if agent:
            # Update existing agent's last_active
            agent.last_active = datetime.utcnow()
            db.commit()
            db.refresh(agent)
            return agent, False
        else:
            # Create new agent (auto-registration)
            new_agent = Agent(
                id=agent_id,
                name=agent_name or agent_id,
                description=f"Auto-registered agent: {agent_id}",
                owner_user_id=owner_user_id or "system",
                created_at=datetime.utcnow(),
                last_active=datetime.utcnow(),
                status=AgentStatus.ACTIVE,
                llm_provider=llm_provider,
                metadata=metadata or {}
            )
            db.add(new_agent)
            db.commit()
            db.refresh(new_agent)
            return new_agent, True
    
    @staticmethod
    def get_agent_metrics(db: Session, agent_id: str) -> Dict[str, Any]:
        """
        Get activity metrics for a specific agent
        
        Args:
            db: Database session
            agent_id: Agent identifier
            
        Returns:
            Dictionary with agent metrics
        """
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            return None
        
        # Get audit log statistics
        total_actions = db.query(func.count(AuditLog.id)).filter(
            AuditLog.agent_id == agent_id
        ).scalar() or 0
        
        blocked_actions = db.query(func.count(AuditLog.id)).filter(
            AuditLog.agent_id == agent_id,
            AuditLog.decision == "BLOCKED"
        ).scalar() or 0
        
        allowed_actions = db.query(func.count(AuditLog.id)).filter(
            AuditLog.agent_id == agent_id,
            AuditLog.decision == "ALLOWED"
        ).scalar() or 0
        
        # Get unique systems accessed
        systems_accessed_result = db.query(
            func.distinct(AuditLog.system_accessed)
        ).filter(
            AuditLog.agent_id == agent_id
        ).all()
        
        systems_accessed = [row[0] for row in systems_accessed_result if row[0]]
        
        # Get first seen timestamp (earliest audit log)
        first_log = db.query(AuditLog).filter(
            AuditLog.agent_id == agent_id
        ).order_by(AuditLog.timestamp.asc()).first()
        
        first_seen = first_log.timestamp if first_log else agent.created_at
        
        return {
            "agent_id": agent.id,
            "total_actions": total_actions,
            "blocked_actions": blocked_actions,
            "allowed_actions": allowed_actions,
            "systems_accessed": systems_accessed,
            "first_seen": first_seen,
            "last_active": agent.last_active,
            "status": agent.status.value
        }
    
    @staticmethod
    def get_all_agent_metrics(db: Session) -> Dict[str, Any]:
        """
        Get aggregated metrics for all agents
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with aggregated metrics
        """
        # Get all agents
        agents = db.query(Agent).all()
        
        # Count by status
        active_agents = db.query(func.count(Agent.id)).filter(
            Agent.status == AgentStatus.ACTIVE
        ).scalar() or 0
        
        inactive_agents = db.query(func.count(Agent.id)).filter(
            Agent.status == AgentStatus.INACTIVE
        ).scalar() or 0
        
        suspended_agents = db.query(func.count(Agent.id)).filter(
            Agent.status == AgentStatus.SUSPENDED
        ).scalar() or 0
        
        # Get metrics for each agent
        metrics = []
        for agent in agents:
            agent_metrics = AgentActivityService.get_agent_metrics(db, agent.id)
            if agent_metrics:
                metrics.append(agent_metrics)
        
        return {
            "metrics": metrics,
            "total_agents": len(agents),
            "active_agents": active_agents,
            "inactive_agents": inactive_agents,
            "suspended_agents": suspended_agents
        }
    
    @staticmethod
    def get_systems_accessed_by_agent(db: Session, agent_id: str) -> List[str]:
        """
        Get list of systems accessed by an agent
        
        Args:
            db: Database session
            agent_id: Agent identifier
            
        Returns:
            List of system names
        """
        systems = db.query(
            func.distinct(AuditLog.system_accessed)
        ).filter(
            AuditLog.agent_id == agent_id
        ).all()
        
        return [row[0] for row in systems if row[0]]
