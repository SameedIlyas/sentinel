# Agent Management API Reference

## Overview
The Agent Management API provides comprehensive visibility and control over AI agents in the Sentinel platform. It includes automatic agent registration, activity tracking, metrics aggregation, and administrative controls.

**Base URL**: `http://localhost:8000/v1/agents`

**Authentication**: All endpoints require API key authentication via `X-API-Key` header.

---

## Key Features

- **Automatic Registration**: Agents self-register on first SDK call
- **Activity Tracking**: Last active timestamp updated on every action
- **Metrics Aggregation**: Total actions, blocked/allowed counts, systems accessed
- **Status Management**: Active, inactive, suspended states
- **Search & Filter**: Find agents by status, owner, name, or ID
- **System Visibility**: See which systems each agent has accessed

---

## Endpoints

### 1. List All Agents

Retrieve all agents with filtering, search, and pagination.

**Endpoint**: `GET /v1/agents`

**Headers**:
```
X-API-Key: your-api-key
```

**Query Parameters**:
- `status_filter` (string, optional): Filter by status ("active", "inactive", "suspended")
- `owner_user_id` (string, optional): Filter by owner user ID
- `search` (string, optional): Search by agent name or ID (case-insensitive)
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 50, max: 100)

**Example Request**:
```bash
GET /v1/agents?status_filter=active&page=1&page_size=20
```

**Response**: `200 OK`
```json
{
  "agents": [
    {
      "id": "test_agent_001",
      "name": "Test Agent 001",
      "description": "Auto-registered agent: test_agent_001",
      "owner_user_id": "user_123",
      "created_at": "2024-02-10T10:00:00Z",
      "last_active": "2024-02-10T15:30:00Z",
      "status": "active",
      "llm_provider": "openai",
      "metadata": {
        "agent_name": "Test Agent 001",
        "llm_provider": "openai",
        "session_id": "test_session_001"
      }
    }
  ],
  "total": 25,
  "page": 1,
  "page_size": 20,
  "total_pages": 2
}
```

**Response Fields**:
- `agents` (array): Agent entries for current page
- `total` (integer): Total agents matching filters
- `page` (integer): Current page number
- `page_size` (integer): Items per page
- `total_pages` (integer): Total pages available

**Errors**:
- `400 Bad Request`: Invalid status filter
- `401 Unauthorized`: Missing or invalid API key
- `500 Internal Server Error`: Database error

---

### 2. Get Specific Agent

Retrieve detailed information about a specific agent.

**Endpoint**: `GET /v1/agents/{agent_id}`

**Headers**:
```
X-API-Key: your-api-key
```

**Path Parameters**:
- `agent_id` (string, required): Agent identifier

**Example Request**:
```bash
GET /v1/agents/test_agent_001
```

**Response**: `200 OK`
```json
{
  "id": "test_agent_001",
  "name": "Test Agent 001",
  "description": "Auto-registered agent: test_agent_001",
  "owner_user_id": "user_123",
  "created_at": "2024-02-10T10:00:00Z",
  "last_active": "2024-02-10T15:30:00Z",
  "status": "active",
  "llm_provider": "openai",
  "metadata": {
    "agent_name": "Test Agent 001",
    "llm_provider": "openai",
    "department": "finance",
    "version": "1.0"
  }
}
```

**Errors**:
- `401 Unauthorized`: Missing or invalid API key
- `404 Not Found`: Agent not found
- `500 Internal Server Error`: Database error

---

### 3. Update Agent

Update an agent's configuration, status, or metadata.

**Endpoint**: `PUT /v1/agents/{agent_id}`

**Headers**:
```
X-API-Key: your-api-key
Content-Type: application/json
```

**Path Parameters**:
- `agent_id` (string, required): Agent identifier

**Request Body**:
```json
{
  "name": "Updated Agent Name",
  "description": "New description",
  "status": "suspended",
  "llm_provider": "anthropic",
  "metadata": {
    "version": "2.0",
    "suspension_reason": "Security review"
  }
}
```

**Request Fields** (all optional):
- `name` (string): Agent name
- `description` (string): Agent description
- `status` (string): Agent status ("active", "inactive", "suspended")
- `llm_provider` (string): LLM provider
- `metadata` (object): Custom metadata

**Response**: `200 OK`
```json
{
  "id": "test_agent_001",
  "name": "Updated Agent Name",
  "description": "New description",
  "owner_user_id": "user_123",
  "created_at": "2024-02-10T10:00:00Z",
  "last_active": "2024-02-10T15:30:00Z",
  "status": "suspended",
  "llm_provider": "anthropic",
  "metadata": {
    "version": "2.0",
    "suspension_reason": "Security review"
  }
}
```

**Features**:
- Partial updates (only specified fields updated)
- Status changes for lifecycle management
- Metadata updates for custom tracking

**Errors**:
- `401 Unauthorized`: Missing or invalid API key
- `404 Not Found`: Agent not found
- `422 Unprocessable Entity`: Invalid request data
- `500 Internal Server Error`: Database error

---

### 4. Get Agent Activity Metrics

Retrieve detailed activity metrics for a specific agent.

**Endpoint**: `GET /v1/agents/{agent_id}/metrics`

**Headers**:
```
X-API-Key: your-api-key
```

**Path Parameters**:
- `agent_id` (string, required): Agent identifier

**Example Request**:
```bash
GET /v1/agents/test_agent_001/metrics
```

**Response**: `200 OK`
```json
{
  "agent_id": "test_agent_001",
  "total_actions": 150,
  "blocked_actions": 12,
  "allowed_actions": 138,
  "systems_accessed": [
    "database",
    "api_gateway",
    "file_system"
  ],
  "first_seen": "2024-02-01T08:00:00Z",
  "last_active": "2024-02-10T15:30:00Z",
  "status": "active"
}
```

**Metrics Provided**:
- `agent_id`: Agent identifier
- `total_actions`: Total policy checks performed
- `blocked_actions`: Number of actions blocked by policies
- `allowed_actions`: Number of actions allowed by policies
- `systems_accessed`: Unique list of systems accessed (from audit logs)
- `first_seen`: Timestamp of first activity (earliest audit log)
- `last_active`: Timestamp of most recent activity
- `status`: Current agent status

**Errors**:
- `401 Unauthorized`: Missing or invalid API key
- `404 Not Found`: Agent not found
- `500 Internal Server Error`: Database error

---

### 5. Get All Agent Metrics

Retrieve aggregated metrics for all agents in the system.

**Endpoint**: `GET /v1/agents/metrics/all`

**Headers**:
```
X-API-Key: your-api-key
```

**Example Request**:
```bash
GET /v1/agents/metrics/all
```

**Response**: `200 OK`
```json
{
  "metrics": [
    {
      "agent_id": "agent_001",
      "total_actions": 150,
      "blocked_actions": 12,
      "allowed_actions": 138,
      "systems_accessed": ["database", "api"],
      "first_seen": "2024-02-01T08:00:00Z",
      "last_active": "2024-02-10T15:30:00Z",
      "status": "active"
    },
    {
      "agent_id": "agent_002",
      "total_actions": 75,
      "blocked_actions": 5,
      "allowed_actions": 70,
      "systems_accessed": ["file_system"],
      "first_seen": "2024-02-05T10:00:00Z",
      "last_active": "2024-02-10T14:00:00Z",
      "status": "active"
    }
  ],
  "total_agents": 25,
  "active_agents": 20,
  "inactive_agents": 3,
  "suspended_agents": 2
}
```

**Response Fields**:
- `metrics` (array): Per-agent metrics for all agents
- `total_agents` (integer): Total number of agents
- `active_agents` (integer): Number of active agents
- `inactive_agents` (integer): Number of inactive agents
- `suspended_agents` (integer): Number of suspended agents

**Errors**:
- `401 Unauthorized`: Missing or invalid API key
- `500 Internal Server Error`: Database error

---

## Automatic Agent Registration

Agents are **automatically registered** on their first policy check. No manual registration required!

### How It Works

1. Agent makes first policy check via SDK
2. `AgentActivityService.register_or_update_agent()` is called
3. If agent doesn't exist → Create new agent record
4. If agent exists → Update `last_active` timestamp
5. Policy evaluation proceeds normally

### Registration Flow

```python
# SDK code
from sentinel import secure_agent

@secure_agent(
    agent_id="my_agent_001",
    api_key="your-api-key",
    context={
        "agent_name": "My Finance Agent",
        "llm_provider": "openai",
        "department": "finance"
    }
)
def my_agent():
    # First call automatically creates agent with:
    # - id: "my_agent_001"
    # - name: "My Finance Agent"
    # - owner_user_id: from policy check request
    # - llm_provider: "openai"
    # - metadata: {"department": "finance", ...}
    pass
```

### What Gets Captured

From SDK context:
- `agent_name`: Human-readable agent name
- `llm_provider`: LLM provider (openai, anthropic, etc.)
- Custom metadata: Any additional fields in context

Default values:
- `id`: From agent_id in policy check
- `owner_user_id`: From user_id in policy check
- `description`: "Auto-registered agent: {agent_id}"
- `status`: "active"
- `created_at`: Current timestamp
- `last_active`: Current timestamp

---

## Activity Tracking

### Automatic Tracking

Every policy check updates the agent's `last_active` timestamp. No manual tracking required!

**What's Tracked**:
- Last active timestamp (updated on every policy check)
- Systems accessed (from audit log `system_accessed` field)
- Total actions (count of audit log entries)
- Blocked vs allowed actions (from audit log `decision` field)

**Example**:
```bash
# Make a policy check
POST /v1/policy/check
{
  "agent_id": "agent_001",
  "user_id": "user_123",
  "tool_name": "database_query",
  "arguments": {...},
  "context": {"system": "production_db"}
}

# Agent's last_active is automatically updated
# System "production_db" is added to systems_accessed list
```

---

## Agent Status Management

### Status States

| Status | Description | Use Case |
|--------|-------------|----------|
| `active` | Agent is operational | Normal operation |
| `inactive` | Agent is not in use | Deactivated agents |
| `suspended` | Agent is temporarily blocked | Security incidents, reviews |

### Changing Agent Status

**Suspend an agent**:
```bash
curl -X PUT "http://localhost:8000/v1/agents/agent_001" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "suspended",
    "metadata": {
      "suspension_reason": "Security review required",
      "suspended_by": "admin_001",
      "suspended_at": "2024-02-10T16:00:00Z"
    }
  }'
```

**Reactivate an agent**:
```bash
curl -X PUT "http://localhost:8000/v1/agents/agent_001" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "active"
  }'
```

**Note**: Changing status to `suspended` does NOT revoke the agent's API key. The agent can still make policy checks. To fully block an agent, revoke its API key separately.

---

## Filter & Search Examples

### Example 1: Active Agents Only
```bash
curl -X GET "http://localhost:8000/v1/agents?status_filter=active&page=1&page_size=50" \
  -H "X-API-Key: your-api-key"
```

### Example 2: Agents by Owner
```bash
curl -X GET "http://localhost:8000/v1/agents?owner_user_id=user_123&page=1" \
  -H "X-API-Key: your-api-key"
```

### Example 3: Search by Name or ID
```bash
curl -X GET "http://localhost:8000/v1/agents?search=finance&page=1" \
  -H "X-API-Key: your-api-key"
```

### Example 4: Combined Filters
```bash
curl -X GET "http://localhost:8000/v1/agents?status_filter=active&search=test&page=1&page_size=10" \
  -H "X-API-Key: your-api-key"
```

---

## Metrics Use Cases

### Dashboard Overview
```bash
# Get high-level metrics for dashboard
curl -X GET "http://localhost:8000/v1/agents/metrics/all" \
  -H "X-API-Key: your-api-key"

# Returns:
# - Total agents: 25
# - Active: 20
# - Inactive: 3
# - Suspended: 2
# - Per-agent details
```

### Agent Health Check
```bash
# Check specific agent's activity
curl -X GET "http://localhost:8000/v1/agents/agent_001/metrics" \
  -H "X-API-Key: your-api-key"

# Returns:
# - Total actions: 150
# - Blocked: 12 (8% block rate - might need review)
# - Allowed: 138
# - Systems: ["database", "api"]
# - Last active: 2 hours ago
```

### Identify Risky Agents
```python
# Get all agent metrics
response = requests.get(
    "http://localhost:8000/v1/agents/metrics/all",
    headers={"X-API-Key": "your-api-key"}
)

metrics = response.json()

# Find agents with high block rates
risky_agents = [
    m for m in metrics['metrics']
    if m['total_actions'] > 0 and
       (m['blocked_actions'] / m['total_actions']) > 0.2  # >20% blocked
]

print(f"Agents with >20% block rate: {len(risky_agents)}")
for agent in risky_agents:
    block_rate = agent['blocked_actions'] / agent['total_actions']
    print(f"  - {agent['agent_id']}: {block_rate:.1%} blocked")
```

### Find Inactive Agents
```python
from datetime import datetime, timedelta

# Get all agents
response = requests.get(
    "http://localhost:8000/v1/agents",
    headers={"X-API-Key": "your-api-key"},
    params={"page": 1, "page_size": 100}
)

agents = response.json()['agents']

# Find agents inactive for >7 days
inactive_threshold = datetime.utcnow() - timedelta(days=7)

inactive_agents = [
    a for a in agents
    if datetime.fromisoformat(a['last_active'].replace('Z', '+00:00')) < inactive_threshold
]

print(f"Agents inactive for >7 days: {len(inactive_agents)}")
```

---

## Integration Example (Python)

```python
import requests
from datetime import datetime

BASE_URL = "http://localhost:8000/v1"
API_KEY = "your-api-key"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# List all active agents
response = requests.get(
    f"{BASE_URL}/agents",
    headers=headers,
    params={"status_filter": "active", "page": 1, "page_size": 10}
)
agents = response.json()
print(f"Total active agents: {agents['total']}")

# Get specific agent details
agent_id = "agent_001"
response = requests.get(
    f"{BASE_URL}/agents/{agent_id}",
    headers=headers
)
agent = response.json()
print(f"Agent: {agent['name']}, Status: {agent['status']}")

# Update agent metadata
response = requests.put(
    f"{BASE_URL}/agents/{agent_id}",
    headers=headers,
    json={
        "metadata": {
            "last_reviewed": datetime.utcnow().isoformat(),
            "review_status": "approved"
        }
    }
)
updated_agent = response.json()
print(f"Updated metadata: {updated_agent['metadata']}")

# Get agent metrics
response = requests.get(
    f"{BASE_URL}/agents/{agent_id}/metrics",
    headers=headers
)
metrics = response.json()
print(f"Total actions: {metrics['total_actions']}")
print(f"Blocked: {metrics['blocked_actions']}")
print(f"Systems: {', '.join(metrics['systems_accessed'])}")

# Get all agent metrics
response = requests.get(
    f"{BASE_URL}/agents/metrics/all",
    headers=headers
)
all_metrics = response.json()
print(f"Total agents: {all_metrics['total_agents']}")
print(f"Active: {all_metrics['active_agents']}")
print(f"Suspended: {all_metrics['suspended_agents']}")

# Find agents with high block rates
for m in all_metrics['metrics']:
    if m['total_actions'] > 10:
        block_rate = m['blocked_actions'] / m['total_actions']
        if block_rate > 0.1:  # >10% blocked
            print(f"⚠️  {m['agent_id']}: {block_rate:.1%} block rate")
```

---

## Error Handling

### Common Errors

**404 Not Found**:
```json
{
  "detail": "Agent with ID 'unknown_agent' not found"
}
```

**400 Bad Request** (invalid status):
```json
{
  "detail": "Invalid status: unknown. Must be one of: active, inactive, suspended"
}
```

**401 Unauthorized**:
```json
{
  "detail": "Invalid API key"
}
```

**422 Unprocessable Entity** (invalid data):
```json
{
  "detail": [
    {
      "loc": ["body", "status"],
      "msg": "value is not a valid enumeration member",
      "type": "type_error.enum"
    }
  ]
}
```

---

## Best Practices

1. **Monitor Inactive Agents**: Regularly check for agents with old `last_active` timestamps
2. **Review High Block Rates**: Agents with >20% block rate may need policy adjustments
3. **Suspend Suspicious Agents**: Use `suspended` status for security reviews
4. **Track System Access**: Monitor which systems agents are accessing
5. **Use Metadata**: Store custom tracking info in agent metadata
6. **Pagination**: Use reasonable page sizes (50-100) for performance
7. **Filter First**: Use filters before fetching full agent list

---

## Performance Considerations

### Metrics Calculation
- Metrics calculated on-demand from audit logs
- Uses indexed database queries (agent_id, decision, system_accessed)
- Efficient for 100s of agents
- For 1000s+ agents, consider adding caching

### Activity Tracking
- Minimal overhead: single UPDATE query per policy check
- Database indexed on agent.id for fast lookups
- Non-blocking: doesn't delay policy evaluation

### Recommendations
- Use pagination for large agent lists
- Cache metrics if queried frequently
- Consider pre-computing metrics for dashboard
- Index audit_logs table on agent_id and timestamp

---

## Support

For issues or questions:
1. Check test script: `test_task_10.py`
2. Review implementation summary: `TASK_10_SUMMARY.md`
3. Examine source code:
   - `policy_engine/routes/agents.py`
   - `policy_engine/services/agent_activity_service.py`
   - `policy_engine/models/schemas.py`
