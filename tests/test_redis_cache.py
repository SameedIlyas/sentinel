"""Tests for Redis cache service"""

import pytest
from unittest.mock import Mock, patch
import json

from policy_engine.services.redis_cache import RedisCacheService
from policy_engine.models.schemas import PolicyCheckResponse


class TestRedisCacheService:
    """Test Redis cache service"""
    
    @patch('policy_engine.services.redis_cache.redis.from_url')
    def test_connection_success(self, mock_redis):
        """Test successful Redis connection"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        cache = RedisCacheService()
        
        assert cache.is_connected() is True
        mock_redis.assert_called_once()
        mock_client.ping.assert_called()
    
    @patch('policy_engine.services.redis_cache.redis.from_url')
    def test_connection_failure(self, mock_redis):
        """Test Redis connection failure"""
        from redis.exceptions import ConnectionError as RedisConnectionError
        mock_redis.side_effect = RedisConnectionError("Connection failed")
        
        cache = RedisCacheService()
        
        assert cache.is_connected() is False
    
    @patch('policy_engine.services.redis_cache.redis.from_url')
    def test_get_policy_decision_hit(self, mock_redis):
        """Test cache hit for policy decision"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        
        # Mock cached response
        cached_data = {
            "decision": "allow",
            "reason": "Test reason",
            "masked_data": None,
            "policy_ids": ["pol_123"],
            "metadata": {}
        }
        mock_client.get.return_value = json.dumps(cached_data)
        mock_redis.return_value = mock_client
        
        cache = RedisCacheService()
        result = cache.get_policy_decision("test_key")
        
        assert result is not None
        assert result.decision == "allow"
        assert result.reason == "Test reason"
        mock_client.get.assert_called_once_with("test_key")
    
    @patch('policy_engine.services.redis_cache.redis.from_url')
    def test_get_policy_decision_miss(self, mock_redis):
        """Test cache miss for policy decision"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.get.return_value = None
        mock_redis.return_value = mock_client
        
        cache = RedisCacheService()
        result = cache.get_policy_decision("test_key")
        
        assert result is None
    
    @patch('policy_engine.services.redis_cache.redis.from_url')
    def test_set_policy_decision(self, mock_redis):
        """Test setting policy decision in cache"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.setex.return_value = True
        mock_client.sadd.return_value = 1
        mock_client.expire.return_value = True
        mock_redis.return_value = mock_client
        
        cache = RedisCacheService()
        
        response = PolicyCheckResponse(
            decision="block",
            reason="Test block",
            masked_data=None,
            policy_ids=["pol_456"],
            metadata={}
        )
        
        result = cache.set_policy_decision("policy:agent1:tool:hash", response, ttl=300)
        
        assert result is True
        mock_client.setex.assert_called_once()
        # Verify TTL was set
        args = mock_client.setex.call_args[0]
        assert args[0] == "policy:agent1:tool:hash"
        assert args[1] == 300
    
    @patch('policy_engine.services.redis_cache.redis.from_url')
    def test_invalidate_policy_cache(self, mock_redis):
        """Test invalidating policy cache"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.keys.return_value = ["key1", "key2", "key3"]
        mock_client.delete.return_value = 3
        mock_redis.return_value = mock_client
        
        cache = RedisCacheService()
        invalidated = cache.invalidate_policy_cache("pol_123")
        
        assert invalidated == 3
        mock_client.keys.assert_called_once()
        mock_client.delete.assert_called_once_with("key1", "key2", "key3")
    
    @patch('policy_engine.services.redis_cache.redis.from_url')
    def test_invalidate_agent_cache(self, mock_redis):
        """Test invalidating agent cache"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.smembers.return_value = {"key1", "key2"}
        mock_client.delete.return_value = 2
        mock_redis.return_value = mock_client
        
        cache = RedisCacheService()
        invalidated = cache.invalidate_agent_cache("agent1")
        
        assert invalidated == 2
        mock_client.smembers.assert_called_once_with("agent_keys:agent1")
    
    @patch('policy_engine.services.redis_cache.redis.from_url')
    def test_build_cache_key(self, mock_redis):
        """Test cache key building"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        cache = RedisCacheService()
        
        key = cache.build_cache_key(
            agent_id="agent1",
            tool_name="process_payment",
            arguments={"amount": 100, "currency": "USD"}
        )
        
        assert key.startswith("policy:agent1:process_payment:")
        assert len(key.split(':')) == 4
    
    @patch('policy_engine.services.redis_cache.redis.from_url')
    def test_cache_key_consistency(self, mock_redis):
        """Test that cache keys are consistent for same inputs"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        cache = RedisCacheService()
        
        # Same arguments in different order should produce same key
        key1 = cache.build_cache_key(
            agent_id="agent1",
            tool_name="tool1",
            arguments={"a": 1, "b": 2}
        )
        
        key2 = cache.build_cache_key(
            agent_id="agent1",
            tool_name="tool1",
            arguments={"b": 2, "a": 1}
        )
        
        assert key1 == key2
    
    @patch('policy_engine.services.redis_cache.redis.from_url')
    def test_get_cache_stats(self, mock_redis):
        """Test getting cache statistics"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.info.side_effect = [
            {"keyspace_hits": 100, "keyspace_misses": 20},
            {"used_memory_human": "1.5M"}
        ]
        mock_client.dbsize.return_value = 150
        mock_client.keys.return_value = ["key1", "key2"]
        mock_redis.return_value = mock_client
        
        cache = RedisCacheService()
        stats = cache.get_cache_stats()
        
        assert stats["connected"] is True
        assert stats["total_keys"] == 150
        assert stats["policy_cache_keys"] == 2
        assert stats["memory_used"] == "1.5M"
        assert stats["hits"] == 100
        assert stats["misses"] == 20
        assert stats["hit_rate"] == 83.33
    
    @patch('policy_engine.services.redis_cache.redis.from_url')
    def test_warm_cache(self, mock_redis):
        """Test cache warming"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.exists.return_value = False
        mock_client.setex.return_value = True
        mock_client.sadd.return_value = 1
        mock_client.expire.return_value = True
        mock_redis.return_value = mock_client
        
        cache = RedisCacheService()
        
        frequent_tools = [
            {"tool_name": "tool1", "arguments": {"a": 1}},
            {"tool_name": "tool2", "arguments": {"b": 2}}
        ]
        
        def mock_generator(tool_call):
            return PolicyCheckResponse(
                decision="allow",
                reason="Test",
                masked_data=None,
                policy_ids=[],
                metadata={}
            )
        
        warmed = cache.warm_cache("agent1", frequent_tools, mock_generator)
        
        assert warmed == 2
        assert mock_client.setex.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
