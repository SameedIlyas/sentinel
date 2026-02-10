"""Condition matching engine for policy evaluation"""

import re
from typing import Any, Dict, List
from policy_engine.models.schemas import PolicyRuleCondition


class ConditionMatcher:
    """Evaluates policy rule conditions against tool call data"""
    
    @staticmethod
    def get_field_value(data: Dict[str, Any], field: str) -> Any:
        """
        Get field value from nested data structure using dot notation
        
        Args:
            data: Data dictionary to extract from
            field: Field path (e.g., 'arguments.amount' or 'tool_name')
            
        Returns:
            Field value or None if not found
        """
        parts = field.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return None
            else:
                return None
        
        return current
    
    @staticmethod
    def evaluate_operator(operator: str, actual_value: Any, expected_value: Any) -> bool:
        """
        Evaluate a comparison operator
        
        Args:
            operator: Comparison operator
            actual_value: Actual value from tool call
            expected_value: Expected value from policy rule
            
        Returns:
            True if condition matches, False otherwise
        """
        # Handle None values
        if actual_value is None:
            return operator == 'ne' and expected_value is not None
        
        # Equality operators
        if operator == 'eq':
            return actual_value == expected_value
        
        if operator == 'ne':
            return actual_value != expected_value
        
        # Numeric comparison operators
        if operator in ['gt', 'lt', 'gte', 'lte']:
            try:
                actual_num = float(actual_value)
                expected_num = float(expected_value)
                
                if operator == 'gt':
                    return actual_num > expected_num
                elif operator == 'lt':
                    return actual_num < expected_num
                elif operator == 'gte':
                    return actual_num >= expected_num
                elif operator == 'lte':
                    return actual_num <= expected_num
            except (ValueError, TypeError):
                return False
        
        # List membership operators
        if operator == 'in':
            if not isinstance(expected_value, list):
                return False
            return actual_value in expected_value
        
        if operator == 'not_in':
            if not isinstance(expected_value, list):
                return False
            return actual_value not in expected_value
        
        # String operators
        if operator == 'contains':
            if not isinstance(actual_value, str) or not isinstance(expected_value, str):
                return False
            return expected_value in actual_value
        
        if operator == 'regex':
            if not isinstance(actual_value, str) or not isinstance(expected_value, str):
                return False
            try:
                pattern = re.compile(expected_value)
                return bool(pattern.search(actual_value))
            except re.error:
                return False
        
        return False
    
    @classmethod
    def evaluate_condition(cls, condition: PolicyRuleCondition, data: Dict[str, Any]) -> bool:
        """
        Evaluate a single condition against tool call data
        
        Args:
            condition: Policy rule condition
            data: Tool call data
            
        Returns:
            True if condition matches, False otherwise
        """
        # Get the actual value from data
        actual_value = cls.get_field_value(data, condition.field)
        
        # Evaluate the operator
        return cls.evaluate_operator(condition.operator, actual_value, condition.value)
    
    @classmethod
    def evaluate_conditions(cls, conditions: List[PolicyRuleCondition], data: Dict[str, Any]) -> bool:
        """
        Evaluate multiple conditions with AND logic
        
        Args:
            conditions: List of policy rule conditions
            data: Tool call data
            
        Returns:
            True if ALL conditions match, False otherwise
        """
        if not conditions:
            return False
        
        # All conditions must match (AND logic)
        return all(cls.evaluate_condition(condition, data) for condition in conditions)
    
    @classmethod
    def build_evaluation_context(cls, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build evaluation context from policy check request
        
        This flattens the request structure to make it easier to evaluate conditions
        
        Args:
            request_data: Policy check request data
            
        Returns:
            Flattened context dictionary
        """
        context = {
            'agent_id': request_data.get('agent_id'),
            'user_id': request_data.get('user_id'),
            'tool_name': request_data.get('tool_name'),
            'timestamp': request_data.get('timestamp'),
        }
        
        # Add arguments with 'arguments.' prefix
        arguments = request_data.get('arguments', {})
        for key, value in arguments.items():
            context[f'arguments.{key}'] = value
            # Also add without prefix for convenience
            context[key] = value
        
        # Add context fields with 'context.' prefix
        ctx = request_data.get('context', {})
        for key, value in ctx.items():
            context[f'context.{key}'] = value
        
        return context
