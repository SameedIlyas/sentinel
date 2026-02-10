"""
Dashboard metrics endpoints

Provides aggregated metrics and statistics for the dashboard overview.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc

from policy_engine.database import get_db
from policy_engine.models.agent import Agent
from policy_engine.models.audit_log import AuditLog
from policy_engine.models.alert import Alert
from policy_engine.models.policy import Policy
from policy_engine.models.schemas import DashboardMetrics
from policy_engine.auth.rbac import get_current_user
from policy_engine.models.user import User

router = APIRouter()


@router.get("/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get dashboard metrics including:
    - Active agent count
    - Total actions
    - Blocked actions
    - Money saved/spent
    - Recent alerts
    - Top agents by activity
    - Policy violation statistics
    """
    
    # Calculate time windows
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)
    
    # 1. Active agents (active in last 24 hours)
    active_agents_count = db.query(Agent).filter(
        Agent.last_active >= last_24h
    ).count()
    
    # 2. Total actions (audit logs in last 30 days)
    total_actions = db.query(AuditLog).filter(
        AuditLog.timestamp >= last_30d
    ).count()
    
    # 3. Blocked actions (policy_decision = 'block' in last 30 days)
    blocked_actions = db.query(AuditLog).filter(
        and_(
            AuditLog.timestamp >= last_30d,
            AuditLog.policy_decision == 'block'
        )
    ).count()
    
    # 4. Financial metrics (from audit log metadata)
    # Look for financial actions in audit logs
    money_saved = 0
    money_spent = 0
    
    financial_logs = db.query(AuditLog).filter(
        and_(
            AuditLog.timestamp >= last_30d,
            AuditLog.action.like('%payment%') | AuditLog.action.like('%transaction%')
        )
    ).all()
    
    for log in financial_logs:
        if log.details:
            amount = log.details.get('amount', 0)
            if log.policy_decision == 'block':
                money_saved += amount
            elif log.policy_decision == 'allow':
                money_spent += amount
    
    # 5. Recent alerts (last 10 unacknowledged alerts)
    recent_alerts_query = db.query(Alert).filter(
        Alert.acknowledged == False
    ).order_by(desc(Alert.timestamp)).limit(10).all()
    
    recent_alerts = [
        {
            "id": alert.id,
            "timestamp": alert.timestamp.isoformat(),
            "severity": alert.severity,
            "alert_type": alert.alert_type,
            "message": alert.message,
            "agent_id": alert.agent_id,
            "policy_id": alert.policy_id,
        }
        for alert in recent_alerts_query
    ]
    
    # 6. Top agents by action count (last 7 days)
    top_agents_query = db.query(
        AuditLog.agent_id,
        func.count(AuditLog.id).label('action_count')
    ).filter(
        AuditLog.timestamp >= last_7d
    ).group_by(
        AuditLog.agent_id
    ).order_by(
        desc('action_count')
    ).limit(10).all()
    
    top_agents = [
        {
            "agent_id": agent_id,
            "action_count": action_count
        }
        for agent_id, action_count in top_agents_query
    ]
    
    # 7. Policy violations by policy (last 7 days)
    violations_query = db.query(
        Policy.name,
        func.count(AuditLog.id).label('count')
    ).join(
        AuditLog, AuditLog.policy_id == Policy.id
    ).filter(
        and_(
            AuditLog.timestamp >= last_7d,
            AuditLog.policy_decision == 'block'
        )
    ).group_by(
        Policy.name
    ).order_by(
        desc('count')
    ).limit(10).all()
    
    policy_violations = [
        {
            "policy_name": policy_name,
            "count": count
        }
        for policy_name, count in violations_query
    ]
    
    # 8. Systems accessed (unique systems from last 7 days)
    systems_accessed_query = db.query(
        AuditLog.system_accessed,
        func.count(AuditLog.id).label('access_count')
    ).filter(
        AuditLog.timestamp >= last_7d
    ).group_by(
        AuditLog.system_accessed
    ).order_by(
        desc('access_count')
    ).limit(10).all()
    
    systems_accessed = [
        {
            "system": system,
            "access_count": count
        }
        for system, count in systems_accessed_query
    ]
    
    # 9. Activity timeline (hourly breakdown for last 24 hours)
    activity_timeline = []
    for hour in range(24):
        hour_start = now - timedelta(hours=24-hour)
        hour_end = hour_start + timedelta(hours=1)
        
        hour_count = db.query(AuditLog).filter(
            and_(
                AuditLog.timestamp >= hour_start,
                AuditLog.timestamp < hour_end
            )
        ).count()
        
        activity_timeline.append({
            "timestamp": hour_start.isoformat(),
            "count": hour_count
        })
    
    # 10. Recent blocked actions (last 20)
    recent_blocked_query = db.query(AuditLog).filter(
        and_(
            AuditLog.timestamp >= last_7d,
            AuditLog.policy_decision == 'block'
        )
    ).order_by(desc(AuditLog.timestamp)).limit(20).all()
    
    recent_blocked_actions = [
        {
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "agent_id": log.agent_id,
            "action": log.action,
            "system_accessed": log.system_accessed,
            "policy_id": log.policy_id,
        }
        for log in recent_blocked_query
    ]
    
    # 11. Alert counts by severity
    alert_counts = db.query(
        Alert.severity,
        func.count(Alert.id).label('count')
    ).filter(
        Alert.timestamp >= last_7d
    ).group_by(
        Alert.severity
    ).all()
    
    alerts_by_severity = {
        severity: count
        for severity, count in alert_counts
    }
    
    return DashboardMetrics(
        active_agents=active_agents_count,
        total_actions=total_actions,
        blocked_actions=blocked_actions,
        money_saved=money_saved,
        money_spent=money_spent,
        recent_alerts=recent_alerts,
        top_agents=top_agents,
        policy_violations=policy_violations,
        systems_accessed=systems_accessed,
        activity_timeline=activity_timeline,
        recent_blocked_actions=recent_blocked_actions,
        alerts_by_severity=alerts_by_severity,
    )
