"""Policy Evaluation Service - Main orchestrator for policy evaluation"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from policy_engine.models.policy import Policy, PolicyType
from policy_engine.models.schemas import PolicyCheckRequest, PolicyCheckResponse
from policy_engine.services.access_control_evaluator import AccessControlEvaluator
from policy_engine.services.financial_evaluator import FinancialEvaluator
from policy_engine.services.data_protection_evaluator import DataProtectionEvaluator
from policy_engine.services.condition_matcher import ConditionMatcher


class PolicyEvaluationService:
    """
    Main service for evaluating policies against tool calls
    
    Orchestrates all policy evaluators and handles caching
    """
    
    def __init__(self, db: Session):
        """
        Initialize policy evaluation service
        
        Args:
            db: Database session
        """
        self.db = db
        self.access_control_evaluator = AccessControlEvaluator()
        self.financial_evaluator = FinancialEvaluator()
        self.data_protection_evaluator = DataProtectionEvaluator()
        self.matcher = ConditionMatcher()
        
        # Simple in-memory cache (in production, use Redis)
        self._cache: Dict[str, tuple] = {}
        self._cache_ttl = timedelta(minutes=5)
    
    def evaluate(self, request: PolicyCheckRequest) -> PolicyCheckResponse:
        """
        Evaluate all applicable policies for a tool call request
        
        Args:
            request: Policy check request
            
        Returns:
            Policy check response with decision
        """
        # Build evaluation context
        context = self.matcher.build_evaluation_context({
            'agent_id': request.agent_id,
            'user_id': request.user_id,
            'tool_name': request.tool_name,
            'arguments': request.arguments,
            'context': request.context,
            'timestamp': request.timestamp
        })
        
        # Check cache first
        cache_key = self._build_cache_key(request)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        
        # Get all enabled policies for this agent
        policies = self._get_applicable_policies(request.agent_id)
        
        # Separate policies by type
        access_policies = [p for p in policies if p.policy_type == PolicyType.ACCESS_CONTROL]
        financial_policies = [p for p in policies if p.policy_type == PolicyType.FINANCIAL]
        data_protection_policies = [p for p in policies if p.policy_type == PolicyType.DATA_PROTECTION]
        
        # Evaluate policies by type (in order of criticality)
        all_policy_ids = []
        masked_data = None
        final_decision = 'allow'
        final_reason = 'No policies matched this request'
        
        # 1. Data Protection (highest priority - can block or mask)
        if data_protection_policies:
            dp_decision, dp_reason, dp_policy_ids, dp_masked = self.data_protection_evaluator.evaluate(
                data_protection_policies, 
                context
            )
            all_policy_ids.extend(dp_policy_ids)
            
            if dp_decision == 'block':
                response = PolicyCheckResponse(
                    decision='block',
                    reason=dp_reason,
                    masked_data=None,
                    policy_ids=all_policy_ids,
                    metadata={'evaluator': 'data_protection'}
                )
                self._cache_result(cache_key, response)
                return response
            
            if dp_decision == 'require_approval':
                response = PolicyCheckResponse(
                    decision='require_approval',
                    reason=dp_reason,
                    masked_data=dp_masked,
                    policy_ids=all_policy_ids,
                    metadata={'evaluator': 'data_protection'}
                )
                self._cache_result(cache_key, response)
                return response
            
            if dp_masked:
                masked_data = dp_masked
                final_decision = 'allow'
                final_reason = dp_reason
        
        # 2. Access Control (can block or require approval)
        if access_policies:
            ac_decision, ac_reason, ac_policy_ids = self.access_control_evaluator.evaluate(
                access_policies, 
                context
            )
            all_policy_ids.extend(ac_policy_ids)
            
            if ac_decision == 'block':
                response = PolicyCheckResponse(
                    decision='block',
                    reason=ac_reason,
                    masked_data=None,
                    policy_ids=all_policy_ids,
                    metadata={'evaluator': 'access_control'}
                )
                self._cache_result(cache_key, response)
                return response
            
            if ac_decision == 'require_approval':
                response = PolicyCheckResponse(
                    decision='require_approval',
                    reason=ac_reason,
                    masked_data=masked_data,
                    policy_ids=all_policy_ids,
                    metadata={'evaluator': 'access_control'}
                )
                self._cache_result(cache_key, response)
                return response
            
            if ac_policy_ids:  # Policies matched
                final_decision = ac_decision
                final_reason = ac_reason
        
        # 3. Financial (can block or require approval)
        if financial_policies:
            fin_decision, fin_reason, fin_policy_ids = self.financial_evaluator.evaluate(
                financial_policies, 
                context
            )
            all_policy_ids.extend(fin_policy_ids)
            
            if fin_decision == 'block':
                response = PolicyCheckResponse(
                    decision='block',
                    reason=fin_reason,
                    masked_data=None,
                    policy_ids=all_policy_ids,
                    metadata={'evaluator': 'financial'}
                )
                self._cache_result(cache_key, response)
                return response
            
            if fin_decision == 'require_approval':
                response = PolicyCheckResponse(
                    decision='require_approval',
                    reason=fin_reason,
                    masked_data=masked_data,
                    policy_ids=all_policy_ids,
                    metadata={'evaluator': 'financial'}
                )
                self._cache_result(cache_key, response)
                return response
            
            if fin_policy_ids:  # Policies matched
                final_decision = fin_decision
                final_reason = fin_reason
        
        # Build final response
        response = PolicyCheckResponse(
            decision=final_decision,
            reason=final_reason,
            masked_data=masked_data,
            policy_ids=all_policy_ids,
            metadata={
                'evaluated_at': datetime.utcnow().isoformat(),
                'policies_evaluated': len(policies)
            }
        )
        
        # Cache the result
        self._cache_result(cache_key, response)
        
        return response
    
    def _get_applicable_policies(self, agent_id: str) -> List[Policy]:
        """
        Get all enabled policies that apply to the given agent
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of applicable policies
        """
        # Query enabled policies that apply to this agent or all agents
        policies = self.db.query(Policy).filter(
            Policy.enabled == True
        ).all()
        
        # Filter by agent applicability
        applicable_policies = []
        for policy in policies:
            if '*' in policy.applies_to or agent_id in policy.applies_to:
                applicable_policies.append(policy)
        
        return applicable_policies
    
    def _build_cache_key(self, request: PolicyCheckRequest) -> str:
        """
        Build cache key from request
        
        Args:
            request: Policy check request
            
        Returns:
            Cache key string
        """
        # Simple cache key based on agent, tool, and arguments
        # In production, use a hash of the request data
        import json
        key_data = {
            'agent_id': request.agent_id,
            'tool_name': request.tool_name,
            'arguments': request.arguments
        }
        return json.dumps(key_data, sort_keys=True)
    
    def _get_from_cache(self, cache_key: str) -> Optional[PolicyCheckResponse]:
        """
        Get result from cache if not expired
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached response or None
        """
        if cache_key in self._cache:
            cached_response, cached_time = self._cache[cache_key]
            
            # Check if cache is still valid
            if datetime.utcnow() - cached_time < self._cache_ttl:
                return cached_response
            else:
                # Remove expired cache entry
                del self._cache[cache_key]
        
        return None
    
    def _cache_result(self, cache_key: str, response: PolicyCheckResponse) -> None:
        """
        Cache evaluation result
        
        Args:
            cache_key: Cache key
            response: Policy check response
        """
        self._cache[cache_key] = (response, datetime.utcnow())
        
        # Simple cache cleanup - remove old entries if cache grows too large
        if len(self._cache) > 1000:
            self._cleanup_cache()
    
    def _cleanup_cache(self) -> None:
        """Clean up expired cache entries"""
        current_time = datetime.utcnow()
        expired_keys = [
            key for key, (_, cached_time) in self._cache.items()
            if current_time - cached_time >= self._cache_ttl
        ]
        
        for key in expired_keys:
            del self._cache[key]
    
    def clear_cache(self) -> None:
        """Clear all cached results"""
        self._cache.clear()
