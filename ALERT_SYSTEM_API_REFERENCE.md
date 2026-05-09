# Alert System API Reference

## Overview
The Alert System API provides real-time security alerting for AI agent policy violations. Alerts are automatically triggered on blocked actions, high-value transactions, and suspicious behavior, with instant Slack notifications to security teams.

**Base URL**: `http://localhost:8000/v1/alerts`

**Authentication**: All endpoints require API key authentication via `X-API-Key` header.

---

## Endpoints

### 1. Configure Alert System

Configure Slack webhooks and alert rules for different policy types.

**Endpoint**: `POST /v1/alerts/configure`

**Headers**:
```
X-API-Key: your-api-key
Content-Type: application/json
```

**Request Body**:
```json
{
  "global_slack_webhook": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
  "alert_rules": [
    {
      "policy_type": "access_control",
      "alert_type": "blocked_access",
      "severity": "high",
      "enabled": true
    },
    {
      "policy_type": "financial",
      "alert_type": "high_transaction",
      "severity": "critical",
      "slack_webhook_url": "https://hooks.slack.com/services/FINANCE/WEBHOOK",
      "enabled": true
    },
    {
      "alert_type": "new_agent",
      "severity": "critical",
      "enabled": true
    }
  ],
  "deduplication_window_seconds": 300
}
```

**Request Fields**:
- `global_slack_webhook` (string, optional): Default Slack webhook URL for all alerts
- `alert_rules` (array, optional): List of alert rule configurations
  - `policy_type` (string, optional): Policy type - "access_control", "financial", "data_protection"
  - `alert_type` (string, required): Alert type identifier
  - `severity` (string, required): "low", "medium", "high", "critical"
  - `slack_webhook_url` (string, optional): Per-rule webhook override
  - `enabled` (boolean, required): Whether this rule is active
  - `conditions` (object, optional): Additional trigger conditions (extensible)
- `deduplication_window_seconds` (integer, optional): Time window for deduplication (default: 300)

**Response**: `200 OK`
```json
{
  "message": "Alert configuration updated successfully",
  "global_webhook_configured": true,
  "rules_created": 3,
  "rules": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "policy_type": "access_control",
      "alert_type": "blocked_access",
      "severity": "high",
      "conditions": null,
      "slack_webhook_url": null,
      "enabled": true,
      "created_at": "2024-02-10T10:00:00Z"
    }
  ]
}
```

**Errors**:
- `400 Bad Request`: Invalid configuration
- `401 Unauthorized`: Missing or invalid API key
- `500 Internal Server Error`: Configuration save failed

---

### 2. Test Slack Webhook

Send a test message to verify Slack webhook configuration.

**Endpoint**: `POST /v1/alerts/test`

**Headers**:
```
X-API-Key: your-api-key
Content-Type: application/json
```

**Request Body**:
```json
{
  "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
  "enabled": true
}
```

**Response**: `200 OK`
```json
{
  "success": true,
  "message": "Test message sent successfully to Slack"
}
```

**Errors**:
- `400 Bad Request`: Slack configuration is disabled
- `401 Unauthorized`: Missing or invalid API key
- `500 Internal Server Error`: Failed to send to Slack (check webhook URL)

**Note**: Check your Slack channel for the test message!

---

### 3. Query Alerts

Query alerts with filtering and pagination.

**Endpoint**: `GET /v1/alerts`

**Headers**:
```
X-API-Key: your-api-key
```

**Query Parameters**:
- `alert_type` (string, optional): Filter by alert type
- `severity` (string, optional): Filter by severity (low/medium/high/critical)
- `acknowledged` (boolean, optional): Filter by acknowledgment status
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 50, max: 100)

**Example Request**:
```bash
GET /v1/alerts?severity=critical&acknowledged=false&page=1&page_size=20
```

**Response**: `200 OK`
```json
{
  "alerts": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2024-02-10T15:30:00Z",
      "severity": "critical",
      "alert_type": "high_transaction",
      "agent_id": "agent-001",
      "description": "Agent 'agent-001' attempted action 'process_payment' which was block. Reason: Transaction exceeds threshold",
      "audit_log_id": "audit-123",
      "acknowledged": false,
      "acknowledged_by": null,
      "acknowledged_at": null
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

**Response Fields**:
- `alerts` (array): Alert entries for current page
- `total` (integer): Total alerts matching filters
- `page` (integer): Current page number
- `page_size` (integer): Items per page
- `total_pages` (integer): Total pages available

**Errors**:
- `401 Unauthorized`: Missing or invalid API key
- `422 Unprocessable Entity`: Invalid query parameters
- `500 Internal Server Error`: Database error

---

### 4. Get Specific Alert

Retrieve a specific alert by ID.

**Endpoint**: `GET /v1/alerts/{alert_id}`

**Headers**:
```
X-API-Key: your-api-key
```

**Path Parameters**:
- `alert_id` (string, required): Alert UUID

**Example Request**:
```bash
GET /v1/alerts/550e8400-e29b-41d4-a716-446655440000
```

**Response**: `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-02-10T15:30:00Z",
  "severity": "high",
  "alert_type": "blocked_access",
  "agent_id": "agent-001",
  "description": "Agent 'agent-001' attempted action 'database_query' which was block",
  "audit_log_id": "audit-456",
  "acknowledged": true,
  "acknowledged_by": "admin-001",
  "acknowledged_at": "2024-02-10T16:00:00Z"
}
```

**Errors**:
- `401 Unauthorized`: Missing or invalid API key
- `404 Not Found`: Alert not found
- `500 Internal Server Error`: Database error

---

### 5. Acknowledge Alert

Mark an alert as acknowledged by a specific user.

**Endpoint**: `POST /v1/alerts/{alert_id}/acknowledge`

**Headers**:
```
X-API-Key: your-api-key
Content-Type: application/json
```

**Path Parameters**:
- `alert_id` (string, required): Alert UUID

**Request Body**:
```json
{
  "acknowledged_by": "security-admin-001"
}
```

**Response**: `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-02-10T15:30:00Z",
  "severity": "high",
  "alert_type": "blocked_access",
  "agent_id": "agent-001",
  "description": "Agent 'agent-001' attempted...",
  "audit_log_id": "audit-456",
  "acknowledged": true,
  "acknowledged_by": "security-admin-001",
  "acknowledged_at": "2024-02-10T16:45:30Z"
}
```

**Features**:
- Records who acknowledged the alert
- Timestamps the acknowledgment
- Immutable after acknowledgment

**Errors**:
- `401 Unauthorized`: Missing or invalid API key
- `404 Not Found`: Alert not found
- `500 Internal Server Error`: Database error

---

### 6. List Alert Rules

Retrieve all configured alert rules.

**Endpoint**: `GET /v1/alerts/rules/list`

**Headers**:
```
X-API-Key: your-api-key
```

**Query Parameters**:
- `enabled_only` (boolean, optional): Show only enabled rules (default: false)

**Example Request**:
```bash
GET /v1/alerts/rules/list?enabled_only=true
```

**Response**: `200 OK`
```json
[
  {
    "id": "rule-123",
    "policy_type": "access_control",
    "alert_type": "blocked_access",
    "severity": "high",
    "conditions": null,
    "slack_webhook_url": null,
    "enabled": true,
    "created_at": "2024-02-10T10:00:00Z"
  },
  {
    "id": "rule-456",
    "policy_type": "financial",
    "alert_type": "high_transaction",
    "severity": "critical",
    "conditions": null,
    "slack_webhook_url": "https://hooks.slack.com/services/FINANCE/WEBHOOK",
    "enabled": true,
    "created_at": "2024-02-10T10:00:00Z"
  }
]
```

**Errors**:
- `401 Unauthorized`: Missing or invalid API key
- `500 Internal Server Error`: Database error

---

## Automatic Alert Triggering

Alerts are **automatically created and sent to Slack** when using the Policy Check endpoints:

### Policy Check (Automatic Alerting)
**Endpoint**: `POST /v1/policy/check`

When a policy check results in:
- `block` decision → Alert triggered
- `require_approval` decision → Alert triggered
- `allow` decision → No alert

**Alert Flow**:
1. Policy is evaluated
2. If decision is block/require_approval → Alert is created
3. Alert severity is classified based on policy type
4. Duplicate check (5-minute window by default)
5. If not duplicate → Alert saved to database
6. If Slack webhook configured → Message sent to Slack
7. Policy check response returned (non-blocking)

**Example**:
```bash
# Make policy check (alert triggered automatically if blocked)
POST /v1/policy/check
{
  "agent_id": "agent-001",
  "user_id": "user-123",
  "tool_name": "execute_code",
  "tool_args": {"code": "dangerous_command()"},
  "session_id": "session-abc"
}

# If blocked, alert is created and Slack is notified automatically
# No manual alert creation needed!
```

---

## Alert Types & Severity

### Alert Types

| Alert Type | Trigger | Default Severity |
|-----------|---------|-----------------|
| `blocked_access` | Access control policy blocks action | MEDIUM |
| `high_transaction` | Financial transaction exceeds threshold | HIGH |
| `blocked_financial_action` | Other financial policy violation | HIGH |
| `data_protection_violation` | PII/credential exposure attempt | CRITICAL |
| `approval_required` | Action requires human approval | MEDIUM |
| `new_agent` | New agent detected (future feature) | CRITICAL |

### Severity Levels

| Severity | Color | Emoji | Use Case |
|---------|-------|-------|----------|
| `low` | Green | ℹ️ | Informational alerts |
| `medium` | Orange | ⚠️  | Access control violations, approval required |
| `high` | Red | 🚨 | Financial violations, multiple policy failures |
| `critical` | Dark Red | 🆘 | Data protection violations, new agents, critical threats |

---

## Slack Message Format

Alerts are sent to Slack as rich block messages:

```
🚨 High Transaction

Agent 'agent-001' attempted action 'process_payment' which was block. 
Reason: Transaction amount exceeds configured threshold

Severity: CRITICAL
Agent: agent-001
Timestamp: 2024-02-10 15:30:45 UTC
Action Attempted: process_payment
Policy Violated: Block High-Value Transactions
Audit Log ID: 550e8400-e29b-41d4-a716-446655440000

Alert ID: 7c9e6679-7425-40de-944b-e07fc1f90ae7
```

**Features**:
- Color-coded attachments (severity-based)
- Emoji indicators for quick recognition
- Structured fields for readability
- Audit log ID for traceability
- Alert ID for acknowledgment

---

## Deduplication

**Purpose**: Prevent alert fatigue from repeated violations

**How it works**:
- Time window: 5 minutes (300 seconds) default, configurable
- Deduplication key: (alert_type, agent_id)
- Within window: Only first alert is created, duplicates suppressed
- After window: New alert created normally

**Example**:
```
15:00:00 - Alert created: blocked_access for agent-001 ✓
15:01:00 - Same violation: Suppressed (duplicate) ✗
15:02:00 - Same violation: Suppressed (duplicate) ✗
15:05:01 - Same violation: New alert created ✓ (window expired)
```

**Benefits**:
- Reduces Slack notification spam
- Highlights new/different violations
- Configurable per deployment needs

---

## Configuration Examples

### Example 1: Basic Setup
```bash
curl -X POST "http://localhost:8000/v1/alerts/configure" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "global_slack_webhook": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "deduplication_window_seconds": 300
  }'
```

### Example 2: Per-Policy-Type Rules
```bash
curl -X POST "http://localhost:8000/v1/alerts/configure" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "global_slack_webhook": "https://hooks.slack.com/services/DEFAULT/WEBHOOK",
    "alert_rules": [
      {
        "policy_type": "access_control",
        "alert_type": "blocked_access",
        "severity": "high",
        "enabled": true
      },
      {
        "policy_type": "financial",
        "alert_type": "high_transaction",
        "severity": "critical",
        "enabled": true
      },
      {
        "policy_type": "data_protection",
        "alert_type": "data_protection_violation",
        "severity": "critical",
        "enabled": true
      }
    ]
  }'
```

### Example 3: Different Webhooks for Different Teams
```bash
curl -X POST "http://localhost:8000/v1/alerts/configure" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "global_slack_webhook": "https://hooks.slack.com/services/SECURITY/WEBHOOK",
    "alert_rules": [
      {
        "alert_type": "high_transaction",
        "severity": "critical",
        "slack_webhook_url": "https://hooks.slack.com/services/FINANCE/WEBHOOK",
        "enabled": true
      },
      {
        "alert_type": "data_protection_violation",
        "severity": "critical",
        "slack_webhook_url": "https://hooks.slack.com/services/COMPLIANCE/WEBHOOK",
        "enabled": true
      }
    ]
  }'
```

---

## Query Examples

### Example 1: Critical Unacknowledged Alerts
```bash
curl -X GET "http://localhost:8000/v1/alerts?severity=critical&acknowledged=false" \
  -H "X-API-Key: your-api-key"
```

### Example 2: All Financial Alerts
```bash
curl -X GET "http://localhost:8000/v1/alerts?alert_type=high_transaction&page=1&page_size=20" \
  -H "X-API-Key: your-api-key"
```

### Example 3: Acknowledged Alerts
```bash
curl -X GET "http://localhost:8000/v1/alerts?acknowledged=true&page=1&page_size=50" \
  -H "X-API-Key: your-api-key"
```

---

## Error Handling

All endpoints return standard HTTP status codes:

- `200 OK`: Successful request
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Missing or invalid API key
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Invalid query parameters
- `500 Internal Server Error`: Server error

Error responses include a detail message:
```json
{
  "detail": "Alert with ID '...' not found"
}
```

---

## Rate Limiting

All alert endpoints are subject to rate limiting:
- Default: 1000 requests per minute per API key
- Retry on `429 Too Many Requests` with exponential backoff

---

## Best Practices

1. **Configure Webhooks**: Set up separate Slack channels for different alert types
2. **Test First**: Use `/v1/alerts/test` before going live
3. **Acknowledge Alerts**: Keep track of investigated incidents
4. **Filter Wisely**: Use severity filters to focus on critical issues
5. **Monitor Deduplication**: Adjust window if alerts are too noisy or too sparse
6. **Per-Team Routing**: Use per-rule webhooks to route alerts to appropriate teams
7. **Regular Reviews**: Check unacknowledged alerts regularly

---

## Troubleshooting

### Slack Messages Not Arriving

1. **Check webhook URL**: Test with `/v1/alerts/test`
2. **Verify Slack app**: Ensure webhook is active in Slack
3. **Check logs**: Look for Slack send failures in policy engine logs
4. **Network issues**: Ensure policy engine can reach hooks.slack.com

### Too Many Alerts

1. **Increase deduplication window**: Change `deduplication_window_seconds`
2. **Adjust severity**: Use higher severity thresholds
3. **Disable noisy rules**: Set `enabled: false` for specific alert types

### Alerts Not Triggering

1. **Check configuration**: Verify alert rules are enabled
2. **Verify policies**: Ensure policies are creating block/require_approval decisions
3. **Check logs**: Look for alert creation in policy engine logs
4. **Test manually**: Trigger a known policy violation

---

## Integration Example (Python)

```python
import requests

BASE_URL = "http://localhost:8000/v1"
API_KEY = "your-api-key"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Configure alerts
config = {
    "global_slack_webhook": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "alert_rules": [
        {
            "policy_type": "access_control",
            "alert_type": "blocked_access",
            "severity": "high",
            "enabled": True
        }
    ],
    "deduplication_window_seconds": 300
}

response = requests.post(
    f"{BASE_URL}/alerts/configure",
    headers=headers,
    json=config
)
print(f"Configuration: {response.json()}")

# Test Slack webhook
test_config = {
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "enabled": True
}

response = requests.post(
    f"{BASE_URL}/alerts/test",
    headers=headers,
    json=test_config
)
print(f"Test result: {response.json()}")

# Query critical alerts
response = requests.get(
    f"{BASE_URL}/alerts",
    headers=headers,
    params={
        "severity": "critical",
        "acknowledged": False,
        "page": 1,
        "page_size": 10
    }
)
alerts = response.json()
print(f"Critical alerts: {alerts['total']}")

# Acknowledge an alert
if alerts['alerts']:
    alert_id = alerts['alerts'][0]['id']
    response = requests.post(
        f"{BASE_URL}/alerts/{alert_id}/acknowledge",
        headers=headers,
        json={"acknowledged_by": "security-admin"}
    )
    print(f"Acknowledged: {response.json()['acknowledged']}")
```

---

## Support

For issues or questions about the Alert System:
1. Check the test script: `test_task_9.py`
2. Review the implementation summary: `TASK_9_SUMMARY.md`
3. Examine the source code:
   - `policy_engine/routes/alerts.py`
   - `policy_engine/services/alert_service.py`
   - `policy_engine/services/slack_service.py`
