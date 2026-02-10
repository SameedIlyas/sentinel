"""Local policy cache with TTL for Sentinel SDK."""

import hashlib
import json
import logging
import time
from threading import Lock
from typing import Any, Dict, Optional

from sentinel.models.policy import PolicyCheckResponse


logger = logging.getLogger(__name__)


class PolicyCache:
    """In-memory cache for policy decisions with TTL support."""
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize the policy cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries in seconds (default: 300 = 5 minutes)
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        logger.info(f"Initialized policy cache with TTL={ttl_seconds}s")
    
    def _generate_cache_key(
        self,
        agent_id: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> str:
        """
        Generate a cache key based on tool call signature.
        
        Args:
            agent_id: Agent identifier
            tool_name: Name of the tool being called
            arguments: Tool call arguments
            
        Returns:
            Cache key as hex string
        """
        # Create a deterministic representation of the call
        key_data = {
            "agent_id": agent_id,
            "tool_name": tool_name,
            "arguments": arguments
        }
        
        # Serialize to JSON with sorted keys for consistency
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        
        # Generate hash
        cache_key = hashlib.sha256(key_string.encode()).hexdigest()
        
        return cache_key
    
    def get(
        self,
        agent_id: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Optional[PolicyCheckResponse]:
        """
        Get a cached policy decision if available and not expired.
        
        Args:
            agent_id: Agent identifier
            tool_name: Name of the tool being called
            arguments: Tool call arguments
            
        Returns:
            Cached PolicyCheckResponse if available and valid, None otherwise
        """
        cache_key = self._generate_cache_key(agent_id, tool_name, arguments)
        
        with self._lock:
            if cache_key not in self._cache:
                logger.debug(f"Cache miss for key: {cache_key[:16]}...")
                return None
            
            entry = self._cache[cache_key]
            current_time = time.time()
            
            # Check if entry has expired
            if current_time > entry["expires_at"]:
                logger.debug(f"Cache entry expired for key: {cache_key[:16]}...")
                del self._cache[cache_key]
                return None
            
            logger.debug(f"Cache hit for key: {cache_key[:16]}...")
            return entry["response"]
    
    def set(
        self,
        agent_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        response: PolicyCheckResponse
    ) -> None:
        """
        Store a policy decision in the cache.
        
        Args:
            agent_id: Agent identifier
            tool_name: Name of the tool being called
            arguments: Tool call arguments
            response: Policy check response to cache
        """
        cache_key = self._generate_cache_key(agent_id, tool_name, arguments)
        current_time = time.time()
        
        with self._lock:
            self._cache[cache_key] = {
                "response": response,
                "cached_at": current_time,
                "expires_at": current_time + self.ttl_seconds
            }
            logger.debug(f"Cached policy decision for key: {cache_key[:16]}...")
    
    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {count} cache entries")
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries from the cache.
        
        Returns:
            Number of entries removed
        """
        current_time = time.time()
        removed_count = 0
        
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if current_time > entry["expires_at"]
            ]
            
            for key in expired_keys:
                del self._cache[key]
                removed_count += 1
            
            if removed_count > 0:
                logger.debug(f"Cleaned up {removed_count} expired cache entries")
        
        return removed_count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            current_time = time.time()
            active_entries = sum(
                1 for entry in self._cache.values()
                if current_time <= entry["expires_at"]
            )
            expired_entries = len(self._cache) - active_entries
            
            return {
                "total_entries": len(self._cache),
                "active_entries": active_entries,
                "expired_entries": expired_entries,
                "ttl_seconds": self.ttl_seconds
            }
