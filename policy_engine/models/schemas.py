"""Pydantic schemas for request/response models"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any, Dict
from datetime import datetime
from enum import Enum


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
    description: Optional[str] = Field(None, max_length=1000, description="Policy description")
    policy_type: PolicyType = Field(..., description="Type of policy")
    rules: List[PolicyRule] = Field(..., min_length=1, description="List of policy rules")
    applies_to: List[str] = Field(..., min_length=1, description="List of agent IDs or ['*'] for all")
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
    description: Optional[str] = Field(None, max_length=1000, description="Policy description")
    policy_type: Optional[PolicyType] = Field(None, description="Type of policy")
    rules: Optional[List[PolicyRule]] = Field(None, min_length=1, description="List of policy rules")
    applies_to: Optional[List[str]] = Field(None, min_length=1, description="List of agent IDs or ['*'] for all")
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
    agent_id: str = Field(..., description="Agent identifier")
    user_id: str = Field(..., description="User who triggered the agent")
    tool_name: str = Field(..., description="Name of the tool being called")
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
    metadata: Dict[str, Any]
    
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
