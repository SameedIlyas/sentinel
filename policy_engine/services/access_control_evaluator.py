"""Access Control Policy Evaluator"""

from typing import Dict, Any, List, Tuple
from policy_engine.models.policy import Policy
from policy_engine.models.schemas import PolicyRuleCondition, PolicyRule
from policy_engine.services.condition_matcher import ConditionMatcher


class AccessControlEvaluator:
    """Evaluates access control policies for tool calls"""
    
    def __init__(self):
        self.matcher = ConditionMatcher()
    
    def evaluate(
        self, 
        policies: List[Policy], 
        context: Dict[str, Any]
    ) -> Tuple[str, str, List[str]]:
        """
        Evaluate access control policies for a tool call
        
        Args:
            policies: List of access control policies to evaluate
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
        return 'allow', 'No access control policies matched this request', []
    
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
        
        if rule.description:
            return f"Access {action} by policy '{policy.name}': {rule.description}"
        else:
            return f"Access {action} by policy '{policy.name}' for tool '{tool_name}'"
    
    def check_resource_access(
        self,
        context: Dict[str, Any],
        resource_type: str,
        operation: str
    ) -> bool:
        """
        Check if access to a specific resource type and operation is allowed
        
        Args:
            context: Evaluation context
            resource_type: Type of resource (e.g., 'database', 'file', 'api')
            operation: Operation type (e.g., 'read', 'write', 'delete')
            
        Returns:
            True if access is allowed
        """
        # resource_type and operation reserved for future fine-grained access control
        del context, resource_type, operation
        return True
