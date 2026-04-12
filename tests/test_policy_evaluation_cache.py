"""Integration tests for policy evaluation with Redis cache"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from policy_engine.services.policy_evaluation import PolicyEvaluationService
from policy_engine.models.schemas import PolicyCheckRequest, PolicyCheckResponse
from policy_engine.models.policy import Policy, PolicyType


class TestPolicyEvaluationCache:
    """Test policy evaluation service with Redis cache"""
    
    @patch('policy_engine.services.policy_evaluation.RedisCacheService')
    def test_cache_hit_returns_cached_response(self, mock_redis_service):
        """Test that cache hit returns cached response without evaluation"""
        # Setup mock database
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        # Setup mock cache
        mock_cache = Mock()
        cached_response = PolicyCheckResponse(
            decision="allow",
            reason="Cached decision",
            masked_data=None,
            policy_ids=["pol_123"],
            metadata={"cached": True}
        )
        mock_cache.get_policy_decision.return_value = cached_response
        mock_cache.is_connected.return_value = True
        mock_cache.build_cache_key.return_value = "test_key"
        mock_redis_service.return_value = mock_cache
        
        # Create service and evaluate
        service = PolicyEvaluationService(mock_db)
        
        request = PolicyCheckRequest(
            agent_id="agent1",
            user_id="user1",
            tool_name="test_tool",
            arguments={"arg": "value"},
            context={},
            timestamp=datetime.utcnow()
        )
        
        result = service.evaluate(request)
        
        # Verify cached response was returned
        assert result.decision == "allow"
        assert result.reason == "Cached decision"
        assert result.metadata["cached"] is True
        
        # Verify database was not queried (cache hit)
        mock_db.query.assert_not_called()
    
    @patch('policy_engine.services.policy_evaluation.RedisCacheService')
    def test_cache_miss_evaluates_and_caches(self, mock_redis_service):
        """Test that cache miss triggers evaluation and caches result"""
        # Setup mock database with no policies
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        # Setup mock cache (miss)
        mock_cache = Mock()
        mock_cache.get_policy_decision.return_value = None  # Cache miss
        mock_cache.is_connected.return_value = True
        mock_cache.build_cache_key.return_value = "test_key"
        mock_cache.set_policy_decision.return_value = True
        mock_redis_service.return_value = mock_cache
        
        # Create service and evaluate
        service = PolicyEvaluationService(mock_db)
        
        request = PolicyCheckRequest(
            agent_id="agent1",
            user_id="user1",
            tool_name="test_tool",
            arguments={"arg": "value"},
            context={},
            timestamp=datetime.utcnow()
        )
        
        result = service.evaluate(request)
        
        # Verify evaluation occurred
        assert result.decision == "allow"
        mock_db.query.assert_called()
        
        # Verify result was cached
        mock_cache.set_policy_decision.assert_called_once()
    
    @patch('policy_engine.services.policy_evaluation.RedisCacheService')
    def test_redis_unavailable_uses_fallback_cache(self, mock_redis_service):
        """Test fallback to in-memory cache when Redis is unavailable"""
        # Setup mock database
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        # Setup mock cache (disconnected)
        mock_cache = Mock()
        mock_cache.get_policy_decision.return_value = None
        mock_cache.is_connected.return_value = False  # Redis unavailable
        mock_cache.build_cache_key.return_value = "test_key"
        mock_redis_service.return_value = mock_cache
        
        # Create service and evaluate twice
        service = PolicyEvaluationService(mock_db)
        
        request = PolicyCheckRequest(
            agent_id="agent1",
            user_id="user1",
            tool_name="test_tool",
            arguments={"arg": "value"},
            context={},
            timestamp=datetime.utcnow()
        )
        
        # First evaluation
        result1 = service.evaluate(request)
        assert result1.decision == "allow"
        
        # Second evaluation should use fallback cache
        result2 = service.evaluate(request)
        assert result2.decision == "allow"
        
        # Verify fallback cache was used (only one DB query)
        assert mock_db.query.call_count == 1
    
    @patch('policy_engine.services.policy_evaluation.RedisCacheService')
    def test_invalidate_cache_clears_entries(self, mock_redis_service):
        """Test cache invalidation"""
        mock_db = Mock()
        
        # Setup mock cache
        mock_cache = Mock()
        mock_cache.invalidate_policy_cache.return_value = 5
        mock_cache.invalidate_agent_cache.return_value = 3
        mock_redis_service.return_value = mock_cache
        
        service = PolicyEvaluationService(mock_db)
        
        # Test policy invalidation
        count = service.invalidate_cache(policy_id="pol_123")
        assert count == 5
        mock_cache.invalidate_policy_cache.assert_called_once_with("pol_123")
        
        # Test agent invalidation
        count = service.invalidate_cache(agent_id="agent1")
        assert count == 3
        mock_cache.invalidate_agent_cache.assert_called_once_with("agent1")
    
    @patch('policy_engine.services.policy_evaluation.RedisCacheService')
    def test_warm_cache_for_agent(self, mock_redis_service):
        """Test cache warming for frequently used tools"""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        # Setup mock cache
        mock_cache = Mock()
        mock_cache.warm_cache.return_value = 3
        mock_cache.is_connected.return_value = True
        mock_cache.build_cache_key.return_value = "test_key"
        mock_cache.get_policy_decision.return_value = None
        mock_cache.set_policy_decision.return_value = True
        mock_redis_service.return_value = mock_cache
        
        service = PolicyEvaluationService(mock_db)
        
        frequent_tools = [
            {"tool_name": "tool1", "arguments": {"a": 1}},
            {"tool_name": "tool2", "arguments": {"b": 2}},
            {"tool_name": "tool3", "arguments": {"c": 3}}
        ]
        
        warmed = service.warm_cache_for_agent("agent1", frequent_tools)
        
        assert warmed == 3
        mock_cache.warm_cache.assert_called_once()
    
    @patch('policy_engine.services.policy_evaluation.RedisCacheService')
    def test_get_cache_stats(self, mock_redis_service):
        """Test getting cache statistics"""
        mock_db = Mock()
        
        # Setup mock cache
        mock_cache = Mock()
        mock_cache.get_cache_stats.return_value = {
            "connected": True,
            "total_keys": 100,
            "policy_cache_keys": 50,
            "hits": 80,
            "misses": 20,
            "hit_rate": 80.0
        }
        mock_redis_service.return_value = mock_cache
        
        service = PolicyEvaluationService(mock_db)
        stats = service.get_cache_stats()
        
        assert stats["connected"] is True
        assert stats["total_keys"] == 100
        assert stats["hit_rate"] == 80.0
        assert "fallback_cache_size" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
