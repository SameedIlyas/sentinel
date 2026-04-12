# Redis Caching Layer

## Overview

The Redis caching layer provides high-performance caching for policy evaluation decisions, reducing latency and database load for the Policy Engine.

## Features

### 1. Policy Decision Caching
- Caches policy evaluation results based on agent ID, tool name, and arguments
- Configurable TTL (default: 5 minutes via `CACHE_TTL` setting)
- Automatic cache key generation with MD5 hashing for long arguments

### 2. Cache Invalidation
- **Policy-level invalidation**: Invalidates all cached decisions affected by a specific policy
- **Agent-level invalidation**: Invalidates all cached decisions for a specific agent
- **Global invalidation**: Clears all cached entries (use with caution)
- Automatic invalidation on policy create/update/delete operations

### 3. Cache Warming
- Pre-populate cache with frequently used policy decisions
- Reduces cold-start latency for common operations
- Extended TTL (2x default) for warmed entries

### 4. Fallback Mechanism
- Automatic fallback to in-memory cache when Redis is unavailable
- Graceful degradation ensures service continuity
- Transparent to API consumers

## Configuration

Add to `.env` file:

```env
# Redis Cache Settings
REDIS_URL=redis://localhost:6379/0
CACHE_TTL=300  # 5 minutes in seconds
```

## API Endpoints

### Get Cache Statistics
```http
GET /v1/cache/stats
```

Returns cache performance metrics including hit rate, memory usage, and key counts.

### Invalidate Cache
```http
POST /v1/cache/invalidate
Content-Type: application/json

{
  "policy_id": "pol_123",  # Optional: invalidate specific policy
  "agent_id": "agent1"     # Optional: invalidate specific agent
}
```

### Warm Cache
```http
POST /v1/cache/warm
Content-Type: application/json

{
  "agent_id_to_warm": "agent1",
  "frequent_tools": [
    {
      "tool_name": "process_payment",
      "arguments": {"currency": "USD"},
      "user_id": "user1"
    }
  ]
}
```

### Clear All Cache
```http
DELETE /v1/cache/clear
```

**Warning**: This clears all cached entries. Use only for maintenance or debugging.

## Usage in Code

### Basic Usage

```python
from policy_engine.services.policy_evaluation import PolicyEvaluationService
from policy_engine.models.schemas import PolicyCheckRequest

# Create service (cache is initialized automatically)
service = PolicyEvaluationService(db)

# Evaluate policy (uses cache automatically)
request = PolicyCheckRequest(
    agent_id="agent1",
    user_id="user1",
    tool_name="process_payment",
    arguments={"amount": 100},
    context={},
    timestamp=datetime.utcnow()
)

response = service.evaluate(request)  # Cached after first call
```

### Manual Cache Management

```python
# Invalidate cache for a specific policy
service.invalidate_cache(policy_id="pol_123")

# Invalidate cache for a specific agent
service.invalidate_cache(agent_id="agent1")

# Warm cache for frequently used tools
frequent_tools = [
    {"tool_name": "get_customer", "arguments": {"id": "cust_123"}},
    {"tool_name": "process_payment", "arguments": {"amount": 100}}
]
service.warm_cache_for_agent("agent1", frequent_tools)

# Get cache statistics
stats = service.get_cache_stats()
print(f"Hit rate: {stats['hit_rate']}%")
```

## Cache Key Format

Cache keys follow this format:
```
policy:{agent_id}:{tool_name}:{args_hash}
```

Example:
```
policy:agent1:process_payment:a3f5e8b2c1d4f6a9
```

The `args_hash` is an MD5 hash of the sorted JSON arguments, ensuring consistent keys for identical requests.

## Performance Characteristics

- **Cache Hit Latency**: < 5ms (Redis local)
- **Cache Miss Latency**: Full policy evaluation time + cache write
- **Fallback Cache Latency**: < 1ms (in-memory)
- **Target Hit Rate**: > 80% for production workloads

## Monitoring

Monitor these metrics for optimal performance:

1. **Hit Rate**: Should be > 80% in steady state
2. **Memory Usage**: Monitor Redis memory consumption
3. **Invalidation Rate**: High rates may indicate cache thrashing
4. **Fallback Usage**: Should be minimal (indicates Redis issues)

## Troubleshooting

### Redis Connection Issues

If Redis is unavailable:
1. Service automatically falls back to in-memory cache
2. Check logs for connection errors
3. Verify `REDIS_URL` configuration
4. Ensure Redis server is running

### Low Hit Rate

If hit rate is < 50%:
1. Check if policies are frequently updated (causing invalidations)
2. Consider increasing `CACHE_TTL`
3. Implement cache warming for common operations
4. Review cache key generation for consistency

### High Memory Usage

If Redis memory is high:
1. Reduce `CACHE_TTL` to expire entries faster
2. Implement more aggressive invalidation
3. Consider Redis maxmemory policies (LRU eviction)
4. Monitor key count and average key size

## Best Practices

1. **Warm cache on startup**: Pre-populate cache with common operations
2. **Monitor hit rates**: Track cache effectiveness over time
3. **Invalidate proactively**: Clear cache when policies change
4. **Use appropriate TTL**: Balance freshness vs. performance
5. **Handle Redis failures**: Always have fallback mechanisms

## Testing

Run cache tests:
```bash
pytest tests/test_redis_cache.py -v
pytest tests/test_policy_evaluation_cache.py -v
```

## Future Enhancements

- [ ] Distributed cache invalidation (multi-instance support)
- [ ] Cache warming based on usage analytics
- [ ] Adaptive TTL based on policy update frequency
- [ ] Cache compression for large responses
- [ ] Redis Cluster support for horizontal scaling
