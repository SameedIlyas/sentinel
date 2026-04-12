"""Pydantic schemas for request/response models"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any, Dict
from datetime import datetime
from enum import Enum

# ---------------------------------------------------------------------------
# Field constraint constants — single source of truth for all input limits
# ---------------------------------------------------------------------------
FIELD_LIMITS: dict = {
    "agent_id": {"max_length": 128, "pattern": r"^[a-zA-Z0-9_\-\.]+$"},
    "tool_name": {"max_length": 256},
    "system": {"max_length": 256},
    "user_id": {"max_length": 128},
    "name": {"max_length": 255},
    "description": {"max_length": 2000},
    "batch_max_items": 100,
    "applies_to_max_items": 100,
    "rules_max_items": 50,
}


class PolicyType(str, Enum):
    """Policy type enumeration"""
    ACCESS_CONTROL = "access_control"
    FINANCIAL = "financial"
    DATA_PROTECTION = "data_protection"


class PolicyRuleCondition(BaseModel):
    """Condition expression in a policy rule"""
    field: str = Field(..., description="Field to evaluate (e.g., 'tool_name', 'amount', 'resource_type')")
    operator: str = Field(..., description="Comparison operator (eq, ne, gt, lt, gte, lte, in, not_in, contains, regex)")
    value: Any = Field(..., description="Value to compare against")
    
    @field_validator('operator')
    @classmethod
    def validate_operator(cls, v):
        """Validate operator is one of the allowed values"""
        allowed_operators = ['eq', 'ne', 'gt', 'lt', 'gte', 'lte', 'in', 'not_in', 'contains', 'regex']
        if v not in allowed_operators:
            raise ValueError(f"Operator must be one of: {', '.join(allowed_operators)}")
        return v


class PolicyRule(BaseModel):
    """Individual rule within a policy"""
    id: Optional[str] = Field(None, description="Rule identifier")
    description: Optional[str] = Field(None, description="Human-readable rule description")
    conditions: List[PolicyRuleCondition] = Field(..., description="List of conditions (AND logic)")
    action: str = Field(..., description="Action to take: 'allow', 'block', 'require_approval', 'mask'")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Additional action parameters (e.g., masking rules)")
    
    @field_validator('action')
    @classmethod
    def validate_action(cls, v):
        """Validate action is one of the allowed values"""
        allowed_actions = ['allow', 'block', 'require_approval', 'mask']
        if v not in allowed_actions:
            raise ValueError(f"Action must be one of: {', '.join(allowed_actions)}")
        return v


class PolicyCreate(BaseModel):
    """Schema for creating a new policy"""
    name: str = Field(..., min_length=1, max_length=255, description="Policy name")
    description: Optional[str] = Field(None, max_length=FIELD_LIMITS["description"]["max_length"], description="Policy description")
    policy_type: PolicyType = Field(..., description="Type of policy")
    rules: List[PolicyRule] = Field(..., min_length=1, max_length=FIELD_LIMITS["rules_max_items"], description="List of policy rules")
    applies_to: List[str] = Field(..., min_length=1, max_length=FIELD_LIMITS["applies_to_max_items"], description="List of agent IDs or ['*'] for all")
    priority: int = Field(default=0, ge=0, le=1000, description="Policy priority (0-1000)")
    enabled: bool = Field(default=True, description="Whether policy is enabled")
    
    @field_validator('applies_to')
    @classmethod
    def validate_applies_to(cls, v):
        """Validate applies_to list"""
        if not v or len(v) == 0:
            raise ValueError("applies_to must contain at least one agent ID or '*'")
        return v


class PolicyUpdate(BaseModel):
    """Schema for updating an existing policy"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Policy name")
    description: Optional[str] = Field(None, max_length=FIELD_LIMITS["description"]["max_length"], description="Policy description")
    policy_type: Optional[PolicyType] = Field(None, description="Type of policy")
    rules: Optional[List[PolicyRule]] = Field(None, min_length=1, max_length=FIELD_LIMITS["rules_max_items"], description="List of policy rules")
    applies_to: Optional[List[str]] = Field(None, min_length=1, max_length=FIELD_LIMITS["applies_to_max_items"], description="List of agent IDs or ['*'] for all")
    priority: Optional[int] = Field(None, ge=0, le=1000, description="Policy priority (0-1000)")
    enabled: Optional[bool] = Field(None, description="Whether policy is enabled")


class PolicyResponse(BaseModel):
    """Schema for policy response"""
    id: str
    name: str
    description: Optional[str]
    policy_type: PolicyType
    rules: List[Dict[str, Any]]
    applies_to: List[str]
    priority: int
    enabled: bool
    created_by: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PolicyListResponse(BaseModel):
    """Schema for paginated policy list response"""
    policies: List[PolicyResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PolicyDeleteResponse(BaseModel):
    """Schema for policy deletion response"""
    success: bool
    message: str
    policy_id: str


class ValidationError(BaseModel):
    """Schema for validation error details"""
    field: str
    message: str


class PolicyValidationResponse(BaseModel):
    """Schema for policy validation response"""
    valid: bool
    errors: Optional[List[ValidationError]] = None


# Policy Check Schemas

class PolicyCheckRequest(BaseModel):
    """Schema for policy check request"""
    agent_id: str = Field(
        ...,
        max_length=FIELD_LIMITS["agent_id"]["max_length"],
        pattern=FIELD_LIMITS["agent_id"]["pattern"],
        description="Agent identifier",
    )
    user_id: str = Field(
        ...,
        max_length=FIELD_LIMITS["user_id"]["max_length"],
        description="User who triggered the agent",
    )
    tool_name: str = Field(
        ...,
        max_length=FIELD_LIMITS["tool_name"]["max_length"],
        description="Name of the tool being called",
    )
    arguments: Dict[str, Any] = Field(..., description="Tool call arguments")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Timestamp of the request")


class PolicyCheckResponse(BaseModel):
    """Schema for policy check response"""
    decision: str = Field(..., description="Decision: 'allow', 'block', or 'require_approval'")
    reason: str = Field(..., description="Explanation for the decision")
    masked_data: Optional[Dict[str, Any]] = Field(None, description="Masked/transformed data if applicable")
    policy_ids: List[str] = Field(default_factory=list, description="IDs of policies that were evaluated")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator('decision')
    @classmethod
    def validate_decision(cls, v):
        """Validate decision is one of the allowed values"""
        allowed_decisions = ['allow', 'block', 'require_approval']
        if v not in allowed_decisions:
            raise ValueError(f"Decision must be one of: {', '.join(allowed_decisions)}")
        return v


# Audit Log Schemas

class AuditLogCreate(BaseModel):
    """Schema for creating an audit log entry"""
    agent_id: str = Field(..., description="Agent identifier")
    agent_name: str = Field(..., description="Agent name")
    user_id: str = Field(..., description="User who triggered the agent")
    tool_name: str = Field(..., description="Tool/function name called")
    arguments: Dict[str, Any] = Field(..., description="Tool call arguments (sanitized)")
    system_accessed: str = Field(..., description="System or service accessed")
    data_touched: List[str] = Field(default_factory=list, description="Resource identifiers accessed")
    decision: str = Field(..., description="Policy decision: 'allowed', 'blocked', or 'approved'")
    policy_ids: List[str] = Field(default_factory=list, description="Policy IDs evaluated")
    reason: str = Field(..., description="Explanation for the decision")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator('decision')
    @classmethod
    def validate_decision(cls, v):
        """Validate decision is one of the allowed values"""
        allowed_decisions = ['allowed', 'blocked', 'approved']
        if v not in allowed_decisions:
            raise ValueError(f"Decision must be one of: {', '.join(allowed_decisions)}")
        return v


class AuditLogResponse(BaseModel):
    """Schema for audit log response"""
    id: str
    timestamp: datetime
    agent_id: str
    agent_name: str
    user_id: str
    tool_name: str
    arguments: Dict[str, Any]
    system_accessed: str
    data_touched: List[str]
    decision: str
    policy_ids: List[str]
    reason: str
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="log_metadata")

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Schema for paginated audit log list response"""
    logs: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AuditLogSearchRequest(BaseModel):
    """Schema for audit log search request"""
    query: Optional[str] = Field(None, description="Search query across all fields")
    agent_id: Optional[str] = Field(None, description="Filter by agent ID")
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    tool_name: Optional[str] = Field(None, description="Filter by tool name")
    system_accessed: Optional[str] = Field(None, description="Filter by system accessed")
    decision: Optional[str] = Field(None, description="Filter by decision")
    start_date: Optional[datetime] = Field(None, description="Filter from this date")
    end_date: Optional[datetime] = Field(None, description="Filter until this date")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")


# ============================================================================
# Alert Schemas
# ============================================================================

class AlertSeverity(str, Enum):
    """Alert severity enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertCreate(BaseModel):
    """Schema for creating an alert"""
    severity: AlertSeverity
    alert_type: str = Field(..., description="Type of alert (blocked_access, high_transaction, new_agent, etc.)")
    agent_id: str = Field(..., description="ID of agent that triggered the alert")
    description: str = Field(..., description="Human-readable alert description")
    audit_log_id: Optional[str] = Field(None, description="Related audit log entry ID")


class AlertResponse(BaseModel):
    """Schema for alert response"""
    id: str
    timestamp: datetime
    severity: str
    alert_type: str
    agent_id: str
    description: str
    audit_log_id: Optional[str]
    acknowledged: bool
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class AlertAcknowledge(BaseModel):
    """Schema for acknowledging an alert"""
    acknowledged_by: str = Field(..., description="ID of user acknowledging the alert")


class AlertListResponse(BaseModel):
    """Schema for paginated alert list response"""
    alerts: List[AlertResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SlackConfig(BaseModel):
    """Schema for Slack webhook configuration"""
    webhook_url: str = Field(..., description="Slack webhook URL")
    channel: Optional[str] = Field(None, description="Slack channel name (optional, can be in webhook)")
    enabled: bool = Field(True, description="Whether Slack notifications are enabled")


class AlertRuleCreate(BaseModel):
    """Schema for creating an alert rule"""
    policy_type: Optional[PolicyType] = Field(None, description="Policy type to trigger alerts for")
    alert_type: str = Field(..., description="Type of alert to trigger")
    severity: AlertSeverity = Field(..., description="Severity of triggered alerts")
    conditions: Optional[Dict[str, Any]] = Field(None, description="Additional conditions for triggering")
    slack_webhook_url: Optional[str] = Field(None, description="Slack webhook URL for this alert rule")
    enabled: bool = Field(True, description="Whether this alert rule is enabled")


class AlertRuleResponse(BaseModel):
    """Schema for alert rule response"""
    id: str
    policy_type: Optional[str]
    alert_type: str
    severity: str
    conditions: Optional[Dict[str, Any]]
    slack_webhook_url: Optional[str]
    enabled: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class AlertConfigRequest(BaseModel):
    """Schema for configuring alert system"""
    global_slack_webhook: Optional[str] = Field(None, description="Global Slack webhook URL")
    alert_rules: Optional[List[AlertRuleCreate]] = Field(None, description="Alert rules configuration")
    deduplication_window_seconds: Optional[int] = Field(300, ge=0, description="Time window for alert deduplication (seconds)")


# ============================================================================
# Agent Schemas
# ============================================================================

class AgentStatus(str, Enum):
    """Agent status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class AgentCreate(BaseModel):
    """Schema for creating a new agent"""
    id: str = Field(..., min_length=1, max_length=255, description="Unique agent identifier")
    name: str = Field(..., min_length=1, max_length=255, description="Agent name")
    description: Optional[str] = Field(None, max_length=1000, description="Agent description")
    owner_user_id: str = Field(..., description="User ID who owns this agent")
    llm_provider: Optional[str] = Field(None, description="LLM provider (openai, anthropic, azure, gemini)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional agent metadata")


class AgentUpdate(BaseModel):
    """Schema for updating an agent"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Agent name")
    description: Optional[str] = Field(None, max_length=1000, description="Agent description")
    status: Optional[AgentStatus] = Field(None, description="Agent status")
    llm_provider: Optional[str] = Field(None, description="LLM provider")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional agent metadata")


class AgentResponse(BaseModel):
    """Schema for agent response"""
    id: str
    name: str
    description: Optional[str]
    owner_user_id: str
    created_at: datetime
    last_active: datetime
    status: str
    llm_provider: Optional[str]
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="agent_metadata")
    
    class Config:
        from_attributes = True


class AgentListResponse(BaseModel):
    """Schema for paginated agent list response"""
    agents: List[AgentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AgentActivityMetrics(BaseModel):
    """Schema for agent activity metrics"""
    agent_id: str
    total_actions: int
    blocked_actions: int
    allowed_actions: int
    systems_accessed: List[str]
    first_seen: datetime
    last_active: datetime
    status: str


class AgentMetricsResponse(BaseModel):
    """Schema for agent metrics response"""
    metrics: List[AgentActivityMetrics]
    total_agents: int
    active_agents: int
    inactive_agents: int
    suspended_agents: int


# ============================================================================
# RBAC / User Management Schemas
# ============================================================================

class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class UserCreate(BaseModel):
    """Schema for creating a new user"""
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (min 8 characters)")
    role: UserRole = Field(default=UserRole.VIEWER, description="User role")
    full_name: Optional[str] = Field(None, max_length=255, description="User's full name")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        """Validate email format"""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        """Validate username format"""
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Username must contain only letters, numbers, underscores, and hyphens")
        return v.lower()


class UserUpdate(BaseModel):
    """Schema for updating a user"""
    email: Optional[str] = Field(None, description="User email address")
    password: Optional[str] = Field(None, min_length=8, description="New password")
    role: Optional[UserRole] = Field(None, description="User role")
    full_name: Optional[str] = Field(None, max_length=255, description="User's full name")
    is_active: Optional[bool] = Field(None, description="Whether user is active")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        """Validate email format"""
        if v is None:
            return v
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()


class UserResponse(BaseModel):
    """Schema for user response (excludes password)"""
    id: str
    username: str
    email: str
    role: str
    full_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    is_active: bool
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Schema for paginated user list response"""
    users: List[UserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserLogin(BaseModel):
    """Schema for user login request"""
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """Schema for JWT token response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: UserResponse = Field(..., description="Authenticated user information")


class PasswordChange(BaseModel):
    """Schema for password change request"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")


class RoleAssignment(BaseModel):
    """Schema for role assignment"""
    user_id: str = Field(..., description="User ID to assign role to")
    role: UserRole = Field(..., description="New role to assign")


# Dashboard Metrics Schemas

class RecentAlert(BaseModel):
    """Recent alert summary"""
    id: str
    timestamp: str
    severity: str
    alert_type: str
    message: str
    agent_id: Optional[str] = None


class TopAgent(BaseModel):
    """Top agent by activity"""
    agent_id: str
    action_count: int


class PolicyViolation(BaseModel):
    """Policy violation summary"""
    policy_name: str
    count: int


class SystemAccess(BaseModel):
    """System access summary"""
    system: str
    access_count: int


class ActivityTimelineItem(BaseModel):
    """Activity timeline data point"""
    timestamp: str
    count: int


class RecentBlockedAction(BaseModel):
    """Recent blocked action"""
    id: str
    timestamp: str
    agent_id: str
    action: str
    system_accessed: str


class DashboardMetrics(BaseModel):
    """Dashboard metrics response"""
    active_agents: int = Field(..., description="Number of active agents (last 24h)")
    total_actions: int = Field(..., description="Total actions (last 30 days)")
    blocked_actions: int = Field(..., description="Blocked actions (last 30 days)")
    money_saved: float = Field(..., description="Money saved by blocking transactions")
    money_spent: float = Field(..., description="Money spent on approved transactions")
    recent_alerts: List[RecentAlert] = Field(default_factory=list, description="Recent unacknowledged alerts")
    top_agents: List[TopAgent] = Field(default_factory=list, description="Top agents by activity (last 7 days)")
    policy_violations: List[PolicyViolation] = Field(default_factory=list, description="Policy violations (last 7 days)")
    systems_accessed: List[SystemAccess] = Field(default_factory=list, description="Systems accessed (last 7 days)")
    activity_timeline: List[ActivityTimelineItem] = Field(default_factory=list, description="Hourly activity (last 24h)")
    recent_blocked_actions: List[RecentBlockedAction] = Field(default_factory=list, description="Recent blocked actions")
    alerts_by_severity: Dict[str, int] = Field(default_factory=dict, description="Alert counts by severity")
