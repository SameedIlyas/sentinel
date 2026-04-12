"""Redis caching service for policy decisions"""

import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import redis
from redis.exceptions import RedisError, ConnectionError

from policy_engine.config import settings
from policy_engine.models.schemas import PolicyCheckResponse

logger = logging.getLogger(__name__)


class RedisCacheService:
    """
    Redis-based caching service for policy evaluation results
    
    Provides caching, invalidation, and warming capabilities
    """
    
    def __init__(self):
        """Initialize Redis connection"""
        self._client: Optional[redis.Redis] = None
        self._connected = False
        self._connect()
    
    def _connect(self) -> None:
        """Establish Redis connection"""
        try:
            self._client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
                health_check_interval=30
            )
            # Test connection
            self._client.ping()
            self._connected = True
            logger.info(f"Connected to Redis at {settings.REDIS_URL}")
        except (RedisError, ConnectionError) as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            self._client = None
    
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        if not self._client:
            return False
        
        try:
            self._client.ping()
            return True
        except (RedisError, ConnectionError):
            self._connected = False
            return False
    
    def get_policy_decision(self, cache_key: str) -> Optional[PolicyCheckResponse]:
        """
        Get cached policy decision
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached policy response or None
        """
        if not self._connected or not self._client:
            return None
        
        try:
            cached_data = self._client.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                # Reconstruct PolicyCheckResponse
                return PolicyCheckResponse(**data)
            
            return None
        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to get from cache: {e}")
            return None
    
    def set_policy_decision(
        self, 
        cache_key: str, 
        response: PolicyCheckResponse,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache policy decision
        
        Args:
            cache_key: Cache key
            response: Policy check response
            ttl: Time to live in seconds (defaults to settings.CACHE_TTL)
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not self._connected or not self._client:
            return False
        
        try:
            # Serialize response
            data = response.model_dump()
            serialized = json.dumps(data)
            
            # Set with TTL
            ttl = ttl or settings.CACHE_TTL
            self._client.setex(cache_key, ttl, serialized)
            
            # Track this key for the agent (for invalidation)
            agent_key = self._extract_agent_from_key(cache_key)
            if agent_key:
                self._add_to_agent_keys(agent_key, cache_key)
            
            return True
        except RedisError as e:
            logger.warning(f"Failed to set cache: {e}")
            return False
    
    def invalidate_policy_cache(self, policy_id: Optional[str] = None) -> int:
        """
        Invalidate cached policy decisions
        
        Args:
            policy_id: Optional specific policy ID to invalidate.
                      If None, invalidates all policy caches.
            
        Returns:
            Number of keys invalidated
        """
        if not self._connected or not self._client:
            return 0
        
        try:
            if policy_id:
                # Invalidate caches that used this specific policy
                pattern = f"policy:*:policies:*{policy_id}*"
            else:
                # Invalidate all policy decision caches
                pattern = "policy:*"
            
            keys = self._client.keys(pattern)
            
            if keys:
                deleted = self._client.delete(*keys)
                logger.info(f"Invalidated {deleted} cache entries for pattern: {pattern}")
                return deleted
            
            return 0
        except RedisError as e:
            logger.error(f"Failed to invalidate cache: {e}")
            return 0
    
    def invalidate_agent_cache(self, agent_id: str) -> int:
        """
        Invalidate all cached decisions for a specific agent
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Number of keys invalidated
        """
        if not self._connected or not self._client:
            return 0
        
        try:
            # Get all keys for this agent
            agent_keys_key = f"agent_keys:{agent_id}"
            keys = self._client.smembers(agent_keys_key)
            
            if keys:
                # Delete all cached decisions
                deleted = self._client.delete(*keys)
                # Delete the tracking set
                self._client.delete(agent_keys_key)
                logger.info(f"Invalidated {deleted} cache entries for agent: {agent_id}")
                return deleted
            
            return 0
        except RedisError as e:
            logger.error(f"Failed to invalidate agent cache: {e}")
            return 0
    
    def warm_cache(
        self, 
        agent_id: str, 
        frequent_tools: List[Dict[str, Any]],
        response_generator
    ) -> int:
        """
        Pre-populate cache with frequently used policy decisions
        
        Args:
            agent_id: Agent ID
            frequent_tools: List of frequently used tool calls
            response_generator: Function to generate PolicyCheckResponse for a tool call
            
        Returns:
            Number of entries warmed
        """
        if not self._connected or not self._client:
            return 0
        
        warmed = 0
        
        for tool_call in frequent_tools:
            try:
                # Generate cache key
                cache_key = self.build_cache_key(
                    agent_id=agent_id,
                    tool_name=tool_call.get('tool_name'),
                    arguments=tool_call.get('arguments', {})
                )
                
                # Check if already cached
                if self._client.exists(cache_key):
                    continue
                
                # Generate response
                response = response_generator(tool_call)
                
                # Cache with extended TTL for frequently used items
                if self.set_policy_decision(cache_key, response, ttl=settings.CACHE_TTL * 2):
                    warmed += 1
                    
            except Exception as e:
                logger.warning(f"Failed to warm cache for tool {tool_call.get('tool_name')}: {e}")
                continue
        
        logger.info(f"Warmed {warmed} cache entries for agent: {agent_id}")
        return warmed
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache stats
        """
        if not self._connected or not self._client:
            return {
                "connected": False,
                "total_keys": 0,
                "memory_used": "0B"
            }
        
        try:
            info = self._client.info('stats')
            memory_info = self._client.info('memory')
            
            # Count policy cache keys
            policy_keys = len(self._client.keys("policy:*"))
            
            return {
                "connected": True,
                "total_keys": self._client.dbsize(),
                "policy_cache_keys": policy_keys,
                "memory_used": memory_info.get('used_memory_human', 'N/A'),
                "hits": info.get('keyspace_hits', 0),
                "misses": info.get('keyspace_misses', 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get('keyspace_hits', 0),
                    info.get('keyspace_misses', 0)
                )
            }
        except RedisError as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                "connected": False,
                "error": str(e)
            }
    
    @staticmethod
    def build_cache_key(agent_id: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Build cache key from request parameters
        
        Args:
            agent_id: Agent ID
            tool_name: Tool name
            arguments: Tool arguments
            
        Returns:
            Cache key string
        """
        # Sort arguments for consistent key generation
        args_str = json.dumps(arguments, sort_keys=True)
        # Create a hash for long argument strings
        import hashlib
        args_hash = hashlib.md5(args_str.encode(), usedforsecurity=False).hexdigest()  # nosec B324
        
        return f"policy:{agent_id}:{tool_name}:{args_hash}"
    
    def _extract_agent_from_key(self, cache_key: str) -> Optional[str]:
        """Extract agent ID from cache key"""
        parts = cache_key.split(':')
        if len(parts) >= 2 and parts[0] == 'policy':
            return parts[1]
        return None
    
    def _add_to_agent_keys(self, agent_id: str, cache_key: str) -> None:
        """Add cache key to agent's key tracking set"""
        try:
            agent_keys_key = f"agent_keys:{agent_id}"
            self._client.sadd(agent_keys_key, cache_key)
            # Set expiry on the tracking set
            self._client.expire(agent_keys_key, settings.CACHE_TTL * 2)
        except RedisError as e:
            logger.warning(f"Failed to track agent key: {e}")
    
    @staticmethod
    def _calculate_hit_rate(hits: int, misses: int) -> float:
        """Calculate cache hit rate"""
        total = hits + misses
        if total == 0:
            return 0.0
        return round((hits / total) * 100, 2)
    
    def clear_all(self) -> bool:
        """
        Clear all cache entries (use with caution)
        
        Returns:
            True if successful
        """
        if not self._connected or not self._client:
            return False
        
        try:
            self._client.flushdb()
            logger.warning("Cleared all cache entries")
            return True
        except RedisError as e:
            logger.error(f"Failed to clear cache: {e}")
            return False
