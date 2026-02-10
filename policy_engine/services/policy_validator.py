"""Policy validation service"""

import re
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from policy_engine.models.schemas import (
    PolicyCreate,
    PolicyUpdate,
    PolicyRule,
    PolicyRuleCondition,
    ValidationError as PolicyValidationError
)
from policy_engine.models.policy import Policy, PolicyType


class PolicyValidator:
    """Validates policy rules and detects conflicts"""
    
    # Field types for different policy types
    FIELD_TYPES = {
        "access_control": {
            "tool_name": str,
            "resource_type": str,
            "database_name": str,
            "operation": str,
            "table_name": str,
        },
        "financial": {
            "tool_name": str,
            "amount": (int, float),
            "currency": str,
            "transaction_type": str,
        },
        "data_protection": {
            "tool_name": str,
            "data_classification": str,
            "contains_pii": bool,
            "export_destination": str,
        }
    }
    
    # Valid operators for different value types
    OPERATORS_BY_TYPE = {
        str: ['eq', 'ne', 'in', 'not_in', 'contains', 'regex'],
        int: ['eq', 'ne', 'gt', 'lt', 'gte', 'lte', 'in', 'not_in'],
        float: ['eq', 'ne', 'gt', 'lt', 'gte', 'lte', 'in', 'not_in'],
        bool: ['eq', 'ne'],
    }
    
    def __init__(self, db: Session):
        """Initialize validator with database session"""
        self.db = db
    
    def validate_policy(self, policy_data: PolicyCreate) -> Tuple[bool, List[PolicyValidationError]]:
        """
        Validate a policy before creation
        
        Args:
            policy_data: Policy data to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Validate rules
        for idx, rule in enumerate(policy_data.rules):
            rule_errors = self._validate_rule(rule, policy_data.policy_type, idx)
            errors.extend(rule_errors)
        
        # Validate applies_to
        if not policy_data.applies_to or len(policy_data.applies_to) == 0:
            errors.append(PolicyValidationError(
                field="applies_to",
                message="Must specify at least one agent ID or '*' for all agents"
            ))
        
        # Validate priority
        if policy_data.priority < 0 or policy_data.priority > 1000:
            errors.append(PolicyValidationError(
                field="priority",
                message="Priority must be between 0 and 1000"
            ))
        
        return len(errors) == 0, errors
    
    def _validate_rule(
        self, 
        rule: PolicyRule, 
        policy_type: PolicyType, 
        rule_index: int
    ) -> List[PolicyValidationError]:
        """
        Validate an individual policy rule
        
        Args:
            rule: Rule to validate
            policy_type: Type of policy this rule belongs to
            rule_index: Index of rule in policy (for error reporting)
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Validate conditions
        if not rule.conditions or len(rule.conditions) == 0:
            errors.append(PolicyValidationError(
                field=f"rules[{rule_index}].conditions",
                message="Rule must have at least one condition"
            ))
            return errors
        
        for cond_idx, condition in enumerate(rule.conditions):
            cond_errors = self._validate_condition(
                condition, 
                policy_type, 
                rule_index, 
                cond_idx
            )
            errors.extend(cond_errors)
        
        # Validate action-specific parameters
        if rule.action == 'mask' and not rule.parameters:
            errors.append(PolicyValidationError(
                field=f"rules[{rule_index}].parameters",
                message="Mask action requires parameters specifying what to mask"
            ))
        
        if rule.action == 'require_approval' and rule.parameters:
            if 'approver_ids' not in rule.parameters or not rule.parameters['approver_ids']:
                errors.append(PolicyValidationError(
                    field=f"rules[{rule_index}].parameters.approver_ids",
                    message="Require approval action needs approver_ids in parameters"
                ))
        
        return errors
    
    def _validate_condition(
        self,
        condition: PolicyRuleCondition,
        policy_type: PolicyType,
        rule_index: int,
        condition_index: int
    ) -> List[PolicyValidationError]:
        """
        Validate a condition expression
        
        Args:
            condition: Condition to validate
            policy_type: Type of policy
            rule_index: Index of rule
            condition_index: Index of condition
            
        Returns:
            List of validation errors
        """
        errors = []
        field_path = f"rules[{rule_index}].conditions[{condition_index}]"
        
        # Get valid fields for this policy type
        valid_fields = self.FIELD_TYPES.get(policy_type.value, {})
        
        # Validate field exists for this policy type
        if condition.field not in valid_fields:
            errors.append(PolicyValidationError(
                field=f"{field_path}.field",
                message=f"Field '{condition.field}' is not valid for {policy_type.value} policies. "
                       f"Valid fields: {', '.join(valid_fields.keys())}"
            ))
            return errors  # Can't validate further without knowing field type
        
        # Get expected type for this field
        expected_type = valid_fields[condition.field]
        if isinstance(expected_type, tuple):
            expected_types = expected_type
        else:
            expected_types = (expected_type,)
        
        # Validate operator is appropriate for field type
        valid_operators = set()
        for exp_type in expected_types:
            valid_operators.update(self.OPERATORS_BY_TYPE.get(exp_type, []))
        
        if condition.operator not in valid_operators:
            errors.append(PolicyValidationError(
                field=f"{field_path}.operator",
                message=f"Operator '{condition.operator}' is not valid for field '{condition.field}'. "
                       f"Valid operators: {', '.join(sorted(valid_operators))}"
            ))
        
        # Validate value type
        if condition.operator in ['in', 'not_in']:
            if not isinstance(condition.value, list):
                errors.append(PolicyValidationError(
                    field=f"{field_path}.value",
                    message=f"Operator '{condition.operator}' requires a list value"
                ))
        elif condition.operator == 'regex':
            if not isinstance(condition.value, str):
                errors.append(PolicyValidationError(
                    field=f"{field_path}.value",
                    message="Regex operator requires a string value"
                ))
            else:
                # Validate regex pattern
                try:
                    re.compile(condition.value)
                except re.error as e:
                    errors.append(PolicyValidationError(
                        field=f"{field_path}.value",
                        message=f"Invalid regex pattern: {str(e)}"
                    ))
        else:
            # Validate value matches expected type
            if not any(isinstance(condition.value, t) for t in expected_types):
                type_names = [t.__name__ for t in expected_types]
                errors.append(PolicyValidationError(
                    field=f"{field_path}.value",
                    message=f"Value must be of type: {' or '.join(type_names)}"
                ))
        
        return errors
    
    def detect_conflicts(
        self, 
        policy_data: PolicyCreate, 
        exclude_policy_id: Optional[str] = None
    ) -> List[str]:
        """
        Detect if the new/updated policy conflicts with existing policies
        
        A conflict occurs when two policies of the same type:
        1. Apply to the same agents (or one applies to '*')
        2. Have the same priority
        3. Have overlapping conditions that could match the same requests
        
        Args:
            policy_data: Policy to check for conflicts
            exclude_policy_id: Policy ID to exclude from conflict check (for updates)
            
        Returns:
            List of conflict messages
        """
        conflicts = []
        
        # Query existing policies of the same type
        query = self.db.query(Policy).filter(
            Policy.policy_type == policy_data.policy_type,
            Policy.enabled == True
        )
        
        if exclude_policy_id:
            query = query.filter(Policy.id != exclude_policy_id)
        
        existing_policies = query.all()
        
        for existing in existing_policies:
            # Check if policies apply to same agents
            applies_to_overlap = (
                '*' in policy_data.applies_to or
                '*' in existing.applies_to or
                bool(set(policy_data.applies_to) & set(existing.applies_to))
            )
            
            if not applies_to_overlap:
                continue
            
            # Check for priority conflicts
            if policy_data.priority == existing.priority:
                conflicts.append(
                    f"Policy '{existing.name}' (ID: {existing.id}) has the same priority ({existing.priority}) "
                    f"and applies to overlapping agents. Consider using different priorities to establish "
                    f"clear precedence."
                )
            
            # Note: Deep semantic conflict detection (overlapping conditions) is complex
            # and would require symbolic execution. We provide a basic check here.
            # For production, this could be enhanced with more sophisticated analysis.
        
        return conflicts
    
    def validate_update(
        self, 
        policy_id: str, 
        update_data: PolicyUpdate
    ) -> Tuple[bool, List[PolicyValidationError]]:
        """
        Validate a policy update
        
        Args:
            policy_id: ID of policy being updated
            update_data: Update data
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Validate rules if provided
        if update_data.rules:
            policy_type = update_data.policy_type or PolicyType.ACCESS_CONTROL  # Default, should get from DB
            for idx, rule in enumerate(update_data.rules):
                rule_errors = self._validate_rule(rule, policy_type, idx)
                errors.extend(rule_errors)
        
        # Validate applies_to if provided
        if update_data.applies_to is not None and len(update_data.applies_to) == 0:
            errors.append(PolicyValidationError(
                field="applies_to",
                message="Must specify at least one agent ID or '*' for all agents"
            ))
        
        # Validate priority if provided
        if update_data.priority is not None and (update_data.priority < 0 or update_data.priority > 1000):
            errors.append(PolicyValidationError(
                field="priority",
                message="Priority must be between 0 and 1000"
            ))
        
        return len(errors) == 0, errors
