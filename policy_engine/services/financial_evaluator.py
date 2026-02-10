"""Financial Policy Evaluator"""

from typing import Dict, Any, List, Optional, Tuple
from policy_engine.models.policy import Policy
from policy_engine.models.schemas import PolicyRuleCondition, PolicyRule
from policy_engine.services.condition_matcher import ConditionMatcher


class FinancialEvaluator:
    """Evaluates financial guardrail policies for tool calls"""
    
    def __init__(self):
        self.matcher = ConditionMatcher()
    
    def evaluate(
        self, 
        policies: List[Policy], 
        context: Dict[str, Any]
    ) -> Tuple[str, str, List[str]]:
        """
        Evaluate financial policies for a tool call
        
        Args:
            policies: List of financial policies to evaluate
            context: Evaluation context with tool call data
            
        Returns:
            Tuple of (decision, reason, policy_ids)
            - decision: 'allow', 'block', or 'require_approval'
            - reason: Explanation for the decision
            - policy_ids: List of policy IDs that matched
        """
        matched_policies = []
        
        # Sort policies by priority (highest first)
        sorted_policies = sorted(policies, key=lambda p: p.priority, reverse=True)
        
        for policy in sorted_policies:
            # Check if policy applies to this agent
            if not self._applies_to_agent(policy, context.get('agent_id')):
                continue
            
            # Evaluate each rule in the policy
            for rule_data in policy.rules:
                rule = self._parse_rule(rule_data)
                
                if self._evaluate_rule(rule, context):
                    matched_policies.append(policy.id)
                    
                    # First matching rule determines the decision (due to priority sorting)
                    decision = rule.action
                    reason = self._build_reason(policy, rule, context)
                    
                    # Map action to decision
                    if decision == 'block':
                        return 'block', reason, matched_policies
                    elif decision == 'require_approval':
                        return 'require_approval', reason, matched_policies
                    elif decision == 'allow':
                        return 'allow', reason, matched_policies
        
        # No policies matched - default allow
        return 'allow', 'No financial policies matched this request', []
    
    def _applies_to_agent(self, policy: Policy, agent_id: str) -> bool:
        """
        Check if policy applies to the given agent
        
        Args:
            policy: Policy to check
            agent_id: Agent ID
            
        Returns:
            True if policy applies to this agent
        """
        if '*' in policy.applies_to:
            return True
        return agent_id in policy.applies_to
    
    def _parse_rule(self, rule_data: Dict[str, Any]) -> PolicyRule:
        """
        Parse rule data into PolicyRule object
        
        Args:
            rule_data: Rule data from database
            
        Returns:
            PolicyRule object
        """
        conditions = [
            PolicyRuleCondition(**cond) 
            for cond in rule_data.get('conditions', [])
        ]
        
        return PolicyRule(
            id=rule_data.get('id'),
            description=rule_data.get('description'),
            conditions=conditions,
            action=rule_data.get('action'),
            parameters=rule_data.get('parameters')
        )
    
    def _evaluate_rule(self, rule: PolicyRule, context: Dict[str, Any]) -> bool:
        """
        Evaluate a single rule against context
        
        Args:
            rule: Policy rule to evaluate
            context: Evaluation context
            
        Returns:
            True if rule matches
        """
        return self.matcher.evaluate_conditions(rule.conditions, context)
    
    def _build_reason(
        self, 
        policy: Policy, 
        rule: PolicyRule, 
        context: Dict[str, Any]
    ) -> str:
        """
        Build explanation for the decision
        
        Args:
            policy: Matched policy
            rule: Matched rule
            context: Evaluation context
            
        Returns:
            Human-readable reason
        """
        action_text = {
            'allow': 'allowed',
            'block': 'blocked',
            'require_approval': 'requires approval'
        }
        
        tool_name = context.get('tool_name', 'unknown tool')
        action = action_text.get(rule.action, rule.action)
        
        # Try to extract transaction amount for better messaging
        amount = context.get('amount') or context.get('arguments.amount')
        currency = context.get('currency') or context.get('arguments.currency', 'USD')
        
        if rule.description:
            base_reason = f"Transaction {action} by policy '{policy.name}': {rule.description}"
        else:
            base_reason = f"Transaction {action} by policy '{policy.name}' for tool '{tool_name}'"
        
        # Add amount info if available
        if amount is not None:
            base_reason += f" (Amount: {currency} {amount})"
        
        # Add approval info if required
        if rule.action == 'require_approval' and rule.parameters:
            approvers = rule.parameters.get('approver_ids', [])
            if approvers:
                base_reason += f". Approval required from: {', '.join(approvers)}"
        
        return base_reason
    
    def check_transaction_limits(
        self,
        context: Dict[str, Any],
        max_amount: float,
        currency: str = 'USD'
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if transaction amount exceeds limits
        
        Args:
            context: Evaluation context
            max_amount: Maximum allowed amount
            currency: Currency code
            
        Returns:
            Tuple of (is_within_limit, reason)
        """
        # Extract amount from context
        amount = context.get('amount') or context.get('arguments.amount')
        
        if amount is None:
            return True, None  # No amount specified, allow
        
        try:
            amount_value = float(amount)
            if amount_value > max_amount:
                return False, f"Transaction amount {currency} {amount_value} exceeds limit of {currency} {max_amount}"
            return True, None
        except (ValueError, TypeError):
            return False, "Invalid transaction amount"
    
    def requires_approval(
        self,
        context: Dict[str, Any],
        threshold: float
    ) -> bool:
        """
        Check if transaction requires approval based on threshold
        
        Args:
            context: Evaluation context
            threshold: Approval threshold amount
            
        Returns:
            True if approval is required
        """
        amount = context.get('amount') or context.get('arguments.amount')
        
        if amount is None:
            return False
        
        try:
            amount_value = float(amount)
            return amount_value >= threshold
        except (ValueError, TypeError):
            return False
