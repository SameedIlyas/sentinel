"""Data Protection Policy Evaluator"""

import re
from typing import Dict, Any, List, Optional, Tuple, Set
from policy_engine.models.policy import Policy
from policy_engine.models.schemas import PolicyRuleCondition, PolicyRule
from policy_engine.services.condition_matcher import ConditionMatcher


class DataProtectionEvaluator:
    """Evaluates data protection policies for tool calls"""
    
    # PII detection patterns
    PII_PATTERNS = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'phone': r'\b(\+\d{1,2}\s?)?(\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}\b',
        'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
        'ip_address': r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
    }
    
    # Credential patterns
    CREDENTIAL_PATTERNS = {
        'api_key': r'(api[_-]?key|apikey)[\s:=]+["\']?([a-zA-Z0-9_-]{32,})["\']?',
        'password': r'(password|passwd|pwd)[\s:=]+["\']?([^\s"\']+)["\']?',
        'token': r'(token|auth)[\s:=]+["\']?([a-zA-Z0-9_-]{32,})["\']?',
        'secret': r'(secret|private[_-]?key)[\s:=]+["\']?([a-zA-Z0-9_-]{32,})["\']?',
    }
    
    def __init__(self):
        self.matcher = ConditionMatcher()
    
    def evaluate(
        self, 
        policies: List[Policy], 
        context: Dict[str, Any]
    ) -> Tuple[str, str, List[str], Optional[Dict[str, Any]]]:
        """
        Evaluate data protection policies for a tool call
        
        Args:
            policies: List of data protection policies to evaluate
            context: Evaluation context with tool call data
            
        Returns:
            Tuple of (decision, reason, policy_ids, masked_data)
            - decision: 'allow', 'block', or 'require_approval'
            - reason: Explanation for the decision
            - policy_ids: List of policy IDs that matched
            - masked_data: Masked/transformed data if masking was applied
        """
        matched_policies = []
        masked_data = None
        
        # Detect PII in the data
        pii_detected = self._detect_pii(context)
        credentials_detected = self._detect_credentials(context)
        
        # Add PII/credential detection to context for policy evaluation
        enhanced_context = {
            **context,
            'contains_pii': len(pii_detected) > 0,
            'pii_types': list(pii_detected),
            'contains_credentials': len(credentials_detected) > 0,
            'credential_types': list(credentials_detected),
        }
        
        # Sort policies by priority (highest first)
        sorted_policies = sorted(policies, key=lambda p: p.priority, reverse=True)
        
        for policy in sorted_policies:
            # Check if policy applies to this agent
            if not self._applies_to_agent(policy, context.get('agent_id')):
                continue
            
            # Evaluate each rule in the policy
            for rule_data in policy.rules:
                rule = self._parse_rule(rule_data)
                
                if self._evaluate_rule(rule, enhanced_context):
                    matched_policies.append(policy.id)
                    
                    # Handle different actions
                    if rule.action == 'block':
                        reason = self._build_reason(policy, rule, enhanced_context, pii_detected, credentials_detected)
                        return 'block', reason, matched_policies, None
                    
                    elif rule.action == 'require_approval':
                        reason = self._build_reason(policy, rule, enhanced_context, pii_detected, credentials_detected)
                        return 'require_approval', reason, matched_policies, None
                    
                    elif rule.action == 'mask':
                        # Apply masking
                        masked_data = self._apply_masking(context, rule, pii_detected, credentials_detected)
                        reason = self._build_reason(policy, rule, enhanced_context, pii_detected, credentials_detected)
                        return 'allow', reason, matched_policies, masked_data
                    
                    elif rule.action == 'allow':
                        reason = self._build_reason(policy, rule, enhanced_context, pii_detected, credentials_detected)
                        return 'allow', reason, matched_policies, None
        
        # No policies matched - default allow
        return 'allow', 'No data protection policies matched this request', [], None
    
    def _applies_to_agent(self, policy: Policy, agent_id: str) -> bool:
        """Check if policy applies to the given agent"""
        if '*' in policy.applies_to:
            return True
        return agent_id in policy.applies_to
    
    def _parse_rule(self, rule_data: Dict[str, Any]) -> PolicyRule:
        """Parse rule data into PolicyRule object"""
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
        """Evaluate a single rule against context"""
        return self.matcher.evaluate_conditions(rule.conditions, context)
    
    def _detect_pii(self, context: Dict[str, Any]) -> Set[str]:
        """
        Detect PII in the tool call data
        
        Args:
            context: Evaluation context
            
        Returns:
            Set of detected PII types
        """
        detected = set()
        
        # Convert context to string for pattern matching
        context_str = str(context)
        
        for pii_type, pattern in self.PII_PATTERNS.items():
            if re.search(pattern, context_str, re.IGNORECASE):
                detected.add(pii_type)
        
        return detected
    
    def _detect_credentials(self, context: Dict[str, Any]) -> Set[str]:
        """
        Detect credentials in the tool call data
        
        Args:
            context: Evaluation context
            
        Returns:
            Set of detected credential types
        """
        detected = set()
        
        # Convert context to string for pattern matching
        context_str = str(context)
        
        for cred_type, pattern in self.CREDENTIAL_PATTERNS.items():
            if re.search(pattern, context_str, re.IGNORECASE):
                detected.add(cred_type)
        
        return detected
    
    def _apply_masking(
        self,
        context: Dict[str, Any],
        rule: PolicyRule,
        pii_detected: Set[str],
        credentials_detected: Set[str]
    ) -> Dict[str, Any]:
        """
        Apply data masking based on rule parameters
        
        Args:
            context: Evaluation context
            rule: Masking rule
            pii_detected: Set of detected PII types
            credentials_detected: Set of detected credential types
            
        Returns:
            Masked data dictionary
        """
        masked_data = {}
        parameters = rule.parameters or {}
        
        # Get fields to mask from rule parameters
        fields_to_mask = parameters.get('fields_to_mask', [])
        mask_pattern = parameters.get('mask_pattern', '***')
        
        # Get arguments from context
        arguments = context.get('arguments', {})
        
        # Apply field-based masking
        for field in fields_to_mask:
            if field in arguments:
                masked_data[field] = mask_pattern
            elif field in context:
                masked_data[field] = mask_pattern
        
        # Apply pattern-based masking for detected PII
        if pii_detected:
            masked_data['pii_masked'] = list(pii_detected)
        
        if credentials_detected:
            masked_data['credentials_masked'] = list(credentials_detected)
        
        # If no specific fields, mask all detected sensitive data
        if not fields_to_mask and (pii_detected or credentials_detected):
            masked_data['arguments'] = self._mask_sensitive_values(arguments)
        
        return masked_data
    
    def _mask_sensitive_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively mask sensitive values in a dictionary
        
        Args:
            data: Data dictionary to mask
            
        Returns:
            Masked data dictionary
        """
        masked = {}
        
        for key, value in data.items():
            if isinstance(value, dict):
                masked[key] = self._mask_sensitive_values(value)
            elif isinstance(value, str):
                # Check if value contains PII or credentials
                has_pii = any(
                    re.search(pattern, value, re.IGNORECASE) 
                    for pattern in self.PII_PATTERNS.values()
                )
                has_cred = any(
                    re.search(pattern, value, re.IGNORECASE) 
                    for pattern in self.CREDENTIAL_PATTERNS.values()
                )
                
                if has_pii or has_cred:
                    masked[key] = '***MASKED***'
                else:
                    masked[key] = value
            else:
                masked[key] = value
        
        return masked
    
    def _build_reason(
        self, 
        policy: Policy, 
        rule: PolicyRule, 
        context: Dict[str, Any],
        pii_detected: Set[str],
        credentials_detected: Set[str]
    ) -> str:
        """Build explanation for the decision"""
        action_text = {
            'allow': 'allowed',
            'block': 'blocked',
            'require_approval': 'requires approval',
            'mask': 'allowed with data masking'
        }
        
        tool_name = context.get('tool_name', 'unknown tool')
        action = action_text.get(rule.action, rule.action)
        
        base_reason = f"Data access {action} by policy '{policy.name}'"
        
        if rule.description:
            base_reason += f": {rule.description}"
        
        # Add PII/credential info
        if pii_detected:
            base_reason += f". PII detected: {', '.join(pii_detected)}"
        
        if credentials_detected:
            base_reason += f". Credentials detected: {', '.join(credentials_detected)}"
        
        return base_reason
    
    def check_data_export(
        self,
        context: Dict[str, Any],
        blocked_destinations: List[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if data export is allowed to destination
        
        Args:
            context: Evaluation context
            blocked_destinations: List of blocked export destinations
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        export_destination = context.get('export_destination') or context.get('arguments.export_destination')
        
        if not export_destination:
            return True, None
        
        for blocked in blocked_destinations:
            if blocked.lower() in str(export_destination).lower():
                return False, f"Export to '{export_destination}' is blocked by policy"
        
        return True, None
