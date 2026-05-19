"""
Seed script to populate the Sentinel AI database with realistic demo data.

Creates: users, agents, API keys, policies, audit logs, alerts, and alert configs.
Idempotent -- checks for existing demo data before inserting.

Usage:
    python seed_demo_data.py

Run AFTER:
    alembic upgrade head
    python create_admin_user.py --default
"""

import sys
import uuid
import hashlib
import random
from datetime import datetime, timedelta

sys.path.insert(0, ".")

from policy_engine.database import SessionLocal, engine, Base
from policy_engine.models.user import User, UserRole
from policy_engine.models.agent import Agent, AgentStatus
from policy_engine.models.api_key import APIKey
from policy_engine.models.policy import Policy, PolicyType
from policy_engine.models.audit_log import AuditLog, Decision
from policy_engine.models.alert import Alert, AlertSeverity
from policy_engine.models.alert_config import AlertConfig
from policy_engine.auth.jwt_utils import get_password_hash

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
now = datetime.utcnow()

def uid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"

def rand_dt(days_back: int = 7) -> datetime:
    return now - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )

def recent_dt(hours_back: int = 4) -> datetime:
    return now - timedelta(
        hours=random.randint(0, hours_back),
        minutes=random.randint(0, 59),
    )

# ---------------------------------------------------------------------------
# Static demo data definitions
# ---------------------------------------------------------------------------

DEMO_USERS = [
    {"username": "sarah.chen", "email": "sarah.chen@sentinel.ai", "role": UserRole.ANALYST, "full_name": "Sarah Chen"},
    {"username": "marcus.johnson", "email": "marcus.johnson@sentinel.ai", "role": UserRole.ANALYST, "full_name": "Marcus Johnson"},
    {"username": "emily.rodriguez", "email": "emily.rodriguez@sentinel.ai", "role": UserRole.VIEWER, "full_name": "Emily Rodriguez"},
    {"username": "david.kim", "email": "david.kim@sentinel.ai", "role": UserRole.VIEWER, "full_name": "David Kim"},
]

DEMO_AGENTS = [
    {"id": "agent_research_assist", "name": "Research Assistant", "description": "General-purpose research agent with web and database access", "status": AgentStatus.ACTIVE, "llm_provider": "openai", "meta": {"model": "gpt-4o", "version": "2.1.0", "team": "research"}},
    {"id": "agent_code_reviewer", "name": "Code Reviewer", "description": "Automated code review agent for pull requests", "status": AgentStatus.ACTIVE, "llm_provider": "anthropic", "meta": {"model": "claude-3.5-sonnet", "version": "1.4.0", "team": "engineering"}},
    {"id": "agent_data_pipeline", "name": "Data Pipeline Bot", "description": "ETL pipeline orchestration and data transformation agent", "status": AgentStatus.ACTIVE, "llm_provider": "openai", "meta": {"model": "gpt-4o-mini", "version": "3.0.1", "team": "data-eng"}},
    {"id": "agent_customer_support", "name": "Customer Support Agent", "description": "Handles tier-1 customer inquiries and ticket routing", "status": AgentStatus.ACTIVE, "llm_provider": "anthropic", "meta": {"model": "claude-3-haiku", "version": "1.2.0", "team": "support"}},
    {"id": "agent_financial_analyst", "name": "Financial Analyst", "description": "Processes transactions, generates financial reports, manages budgets", "status": AgentStatus.ACTIVE, "llm_provider": "openai", "meta": {"model": "gpt-4o", "version": "2.0.0", "team": "finance"}},
    {"id": "agent_legacy_scraper", "name": "Legacy Scraper", "description": "Web scraping agent (deprecated, pending decommission)", "status": AgentStatus.SUSPENDED, "llm_provider": "azure_openai", "meta": {"model": "gpt-4", "version": "0.9.0", "team": "data-eng", "suspended_reason": "Excessive rate limit violations"}},
]

DEMO_POLICIES = [
    {
        "id": "pol_prod_db_protect",
        "name": "Production Database Protection",
        "description": "Prevents destructive operations on production databases",
        "policy_type": PolicyType.ACCESS_CONTROL,
        "priority": 100,
        "applies_to": ["*"],
        "rules": [
            {"name": "block_delete_operations", "conditions": [{"field": "tool_name", "operator": "in", "value": ["delete_record", "drop_table", "truncate_table"]}], "action": "block", "reason": "Destructive database operations are not permitted via AI agents"},
            {"name": "block_schema_changes", "conditions": [{"field": "tool_name", "operator": "in", "value": ["alter_table", "create_index", "drop_index"]}], "action": "require_approval", "reason": "Schema changes require human approval"},
        ],
    },
    {
        "id": "pol_pii_access",
        "name": "PII Access Control",
        "description": "Controls access to personally identifiable information",
        "policy_type": PolicyType.ACCESS_CONTROL,
        "priority": 90,
        "applies_to": ["*"],
        "rules": [
            {"name": "restrict_pii_queries", "conditions": [{"field": "arguments.query", "operator": "contains", "value": "ssn"}, {"field": "arguments.query", "operator": "contains", "value": "social_security"}], "action": "block", "reason": "Direct SSN access is prohibited"},
            {"name": "mask_email_in_bulk", "conditions": [{"field": "tool_name", "operator": "eq", "value": "export_data"}, {"field": "arguments.include_email", "operator": "eq", "value": True}], "action": "mask", "reason": "Email addresses must be masked in bulk exports"},
        ],
    },
    {
        "id": "pol_transaction_limit",
        "name": "Transaction Limit Policy",
        "description": "Enforces transaction amount limits for AI-initiated payments",
        "policy_type": PolicyType.FINANCIAL,
        "priority": 95,
        "applies_to": ["agent_financial_analyst", "agent_customer_support"],
        "rules": [
            {"name": "block_high_transactions", "conditions": [{"field": "tool_name", "operator": "eq", "value": "transfer_funds"}, {"field": "arguments.amount", "operator": "gt", "value": 10000}], "action": "block", "reason": "Transactions over $10,000 must be processed manually"},
            {"name": "approval_medium_transactions", "conditions": [{"field": "tool_name", "operator": "eq", "value": "transfer_funds"}, {"field": "arguments.amount", "operator": "gt", "value": 1000}], "action": "require_approval", "reason": "Transactions over $1,000 require manager approval"},
        ],
    },
    {
        "id": "pol_budget_approval",
        "name": "Budget Approval Workflow",
        "description": "Requires approval for budget modifications and allocations",
        "policy_type": PolicyType.FINANCIAL,
        "priority": 80,
        "applies_to": ["agent_financial_analyst"],
        "rules": [
            {"name": "approve_budget_changes", "conditions": [{"field": "tool_name", "operator": "in", "value": ["modify_budget", "allocate_funds", "create_purchase_order"]}], "action": "require_approval", "reason": "Budget modifications require CFO approval"},
        ],
    },
    {
        "id": "pol_data_export",
        "name": "Data Export Restrictions",
        "description": "Restricts bulk data exports to prevent data exfiltration",
        "policy_type": PolicyType.DATA_PROTECTION,
        "priority": 85,
        "applies_to": ["*"],
        "rules": [
            {"name": "block_large_exports", "conditions": [{"field": "tool_name", "operator": "eq", "value": "export_data"}, {"field": "arguments.row_count", "operator": "gt", "value": 5000}], "action": "block", "reason": "Bulk exports exceeding 5,000 rows are blocked"},
            {"name": "block_external_exports", "conditions": [{"field": "tool_name", "operator": "eq", "value": "export_data"}, {"field": "arguments.destination", "operator": "contains", "value": "external"}], "action": "block", "reason": "Exports to external destinations are not permitted"},
        ],
    },
    {
        "id": "pol_sensitive_masking",
        "name": "Sensitive Data Masking",
        "description": "Automatically masks sensitive fields in API responses",
        "policy_type": PolicyType.DATA_PROTECTION,
        "priority": 70,
        "applies_to": ["agent_customer_support", "agent_research_assist"],
        "rules": [
            {"name": "mask_credit_cards", "conditions": [{"field": "arguments.fields", "operator": "contains", "value": "credit_card"}], "action": "mask", "reason": "Credit card numbers must be masked"},
            {"name": "mask_passwords", "conditions": [{"field": "arguments.fields", "operator": "contains", "value": "password"}], "action": "mask", "reason": "Password fields must be masked"},
        ],
    },
]

TOOL_SYSTEM_MAP = {
    "query_database": ["postgres-prod", "postgres-analytics", "mysql-legacy"],
    "send_email": ["sendgrid-api", "slack-api"],
    "transfer_funds": ["stripe-api", "plaid-api"],
    "read_file": ["s3-storage", "gcs-storage"],
    "write_file": ["s3-storage", "gcs-storage"],
    "api_call": ["github-api", "jira-api", "salesforce-api", "slack-api"],
    "delete_record": ["postgres-prod", "mysql-legacy"],
    "export_data": ["s3-storage", "postgres-analytics"],
    "search_index": ["elasticsearch", "algolia"],
    "create_ticket": ["jira-api", "zendesk-api"],
    "run_query": ["postgres-analytics", "bigquery"],
    "modify_budget": ["netsuite-api", "stripe-api"],
}

TOOL_ARGS_TEMPLATES = {
    "query_database": lambda: {"query": random.choice(["SELECT * FROM users WHERE active = true", "SELECT COUNT(*) FROM orders WHERE date > '2024-01-01'", "SELECT name, email FROM customers LIMIT 100", "SELECT SUM(amount) FROM transactions GROUP BY month"]), "database": random.choice(["users_db", "orders_db", "analytics_db"])},
    "send_email": lambda: {"to": f"user{random.randint(1, 500)}@example.com", "subject": random.choice(["Monthly Report", "Account Update", "Password Reset", "Welcome Email"]), "template": random.choice(["report_v2", "notification", "transactional"])},
    "transfer_funds": lambda: {"amount": random.choice([50, 150, 500, 750, 1200, 2500, 5000, 15000, 50000]), "currency": "USD", "from_account": f"acct_{random.randint(1000, 9999)}", "to_account": f"acct_{random.randint(1000, 9999)}", "memo": random.choice(["Invoice payment", "Refund", "Subscription", "Vendor payment"])},
    "read_file": lambda: {"path": random.choice(["reports/q4_summary.pdf", "data/export_2024.csv", "configs/pipeline.yaml", "logs/agent_audit.json"]), "bucket": random.choice(["sentinel-data", "sentinel-reports"])},
    "write_file": lambda: {"path": f"outputs/{random.choice(['report', 'analysis', 'summary'])}_{random.randint(100, 999)}.json", "bucket": "sentinel-outputs", "size_bytes": random.randint(1024, 1048576)},
    "api_call": lambda: {"method": random.choice(["GET", "POST", "PUT"]), "endpoint": random.choice(["/api/v1/users", "/api/v1/repos", "/api/v2/issues", "/api/v1/contacts"]), "params": {"page": 1, "limit": random.choice([25, 50, 100])}},
    "delete_record": lambda: {"table": random.choice(["temp_reports", "staging_data", "old_sessions"]), "record_id": f"rec_{uuid.uuid4().hex[:8]}", "reason": "Cleanup expired records"},
    "export_data": lambda: {"format": random.choice(["csv", "json", "parquet"]), "row_count": random.choice([100, 500, 1000, 3000, 8000, 15000]), "destination": random.choice(["s3://sentinel-exports/", "external://partner-sftp/"])},
    "search_index": lambda: {"query": random.choice(["customer churn prediction", "security incident Q4", "revenue forecast", "agent performance"]), "index": random.choice(["documents", "tickets", "knowledge_base"])},
    "create_ticket": lambda: {"title": random.choice(["Bug: Login timeout", "Feature: Dark mode", "Incident: API latency spike", "Task: Update dependencies"]), "priority": random.choice(["low", "medium", "high"]), "assignee": random.choice(["sarah.chen", "marcus.johnson", "unassigned"])},
    "run_query": lambda: {"sql": random.choice(["SELECT * FROM daily_metrics ORDER BY date DESC LIMIT 30", "SELECT agent_id, COUNT(*) FROM audit_logs GROUP BY agent_id", "SELECT AVG(response_time) FROM api_requests WHERE date = CURRENT_DATE"]), "timeout_seconds": 30},
    "modify_budget": lambda: {"department": random.choice(["engineering", "marketing", "sales", "operations"]), "amount": random.choice([5000, 10000, 25000, 50000]), "action": random.choice(["increase", "decrease", "reallocate"])},
}

ALERT_TYPES = ["blocked_access", "high_transaction", "data_export_attempt", "rate_limit_exceeded", "suspicious_pattern", "unauthorized_access", "policy_violation"]

ALERT_DESCRIPTIONS = {
    "blocked_access": "Agent '{agent}' attempted to access '{system}' which was blocked by policy '{policy}'",
    "high_transaction": "Agent '{agent}' attempted a ${amount} transaction exceeding the ${limit} limit",
    "data_export_attempt": "Agent '{agent}' attempted to export {rows} rows from {system}",
    "rate_limit_exceeded": "Agent '{agent}' exceeded the rate limit of {limit} requests/minute on {system}",
    "suspicious_pattern": "Unusual activity pattern detected for agent '{agent}': {detail}",
    "unauthorized_access": "Agent '{agent}' attempted to access restricted resource on {system}",
    "policy_violation": "Agent '{agent}' violated policy '{policy}' while using tool '{tool}'",
}


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def seed_users(db):
    print("\n  Users...")
    created = 0
    for u in DEMO_USERS:
        if db.query(User).filter(User.username == u["username"]).first():
            continue
        user = User(
            id=uid("user_"),
            username=u["username"],
            email=u["email"],
            password_hash=get_password_hash("demo1234"),
            role=u["role"],
            full_name=u["full_name"],
            created_at=now - timedelta(days=random.randint(30, 120)),
            updated_at=now - timedelta(days=random.randint(0, 5)),
            last_login=recent_dt(48) if random.random() > 0.2 else None,
            is_active=True,
        )
        db.add(user)
        created += 1
    db.commit()
    print(f"    {created} users created ({len(DEMO_USERS) - created} already existed)")
    return created


def seed_agents(db):
    print("\n  Agents...")
    admin = db.query(User).filter(User.role == UserRole.ORG_ADMIN).first()
    owner_id = admin.id if admin else "user_system"
    created = 0
    for a in DEMO_AGENTS:
        if db.query(Agent).filter(Agent.id == a["id"]).first():
            continue
        agent = Agent(
            id=a["id"],
            name=a["name"],
            description=a["description"],
            owner_user_id=owner_id,
            created_at=now - timedelta(days=random.randint(14, 90)),
            last_active=recent_dt(12) if a["status"] == AgentStatus.ACTIVE else now - timedelta(days=14),
            status=a["status"],
            llm_provider=a["llm_provider"],
            agent_metadata=a["meta"],
        )
        db.add(agent)
        created += 1
    db.commit()
    print(f"    {created} agents created ({len(DEMO_AGENTS) - created} already existed)")
    return created


def seed_api_keys(db):
    print("\n  API Keys...")
    raw_keys = {}
    created = 0
    for a in DEMO_AGENTS:
        existing = db.query(APIKey).filter(APIKey.agent_id == a["id"]).first()
        if existing:
            continue
        raw_key = f"sentinel_{uuid.uuid4().hex}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key = APIKey(
            key=key_hash,
            agent_id=a["id"],
            name=f"{a['name']} Production Key",
            created_at=now - timedelta(days=random.randint(14, 60)),
            last_used=recent_dt(6) if a["status"] == AgentStatus.ACTIVE else None,
            expires_at=now + timedelta(days=365),
            is_active=a["status"] != AgentStatus.SUSPENDED,
        )
        db.add(api_key)
        raw_keys[a["id"]] = raw_key
        created += 1
    db.commit()

    if raw_keys:
        print(f"    {created} API keys created. Raw keys (save these!):")
        for agent_id, key in raw_keys.items():
            print(f"      {agent_id}: {key}")
    else:
        print(f"    {created} API keys created ({len(DEMO_AGENTS)} already existed)")

    return raw_keys


def seed_policies(db):
    print("\n  Policies...")
    admin = db.query(User).filter(User.role == UserRole.ORG_ADMIN).first()
    created_by = admin.id if admin else "user_system"
    created = 0
    for p in DEMO_POLICIES:
        if db.query(Policy).filter(Policy.id == p["id"]).first():
            continue
        policy = Policy(
            id=p["id"],
            name=p["name"],
            description=p["description"],
            policy_type=p["policy_type"],
            rules=p["rules"],
            applies_to=p["applies_to"],
            priority=p["priority"],
            enabled=True,
            created_by=created_by,
            created_at=now - timedelta(days=random.randint(7, 60)),
            updated_at=now - timedelta(days=random.randint(0, 7)),
        )
        db.add(policy)
        created += 1
    db.commit()
    print(f"    {created} policies created ({len(DEMO_POLICIES) - created} already existed)")
    return created


def seed_audit_logs(db, count: int = 220):
    print("\n  Audit Logs...")
    existing = db.query(AuditLog).count()
    if existing >= 100:
        print(f"    Skipped -- {existing} audit logs already exist")
        return 0

    active_agents = [a for a in DEMO_AGENTS if a["status"] == AgentStatus.ACTIVE]
    all_tools = list(TOOL_SYSTEM_MAP.keys())
    policy_ids = [p["id"] for p in DEMO_POLICIES]

    users = db.query(User).all()
    user_ids = [u.id for u in users] if users else ["user_system"]

    logs = []
    for i in range(count):
        agent = random.choice(active_agents)
        tool = random.choice(all_tools)
        system = random.choice(TOOL_SYSTEM_MAP[tool])
        args = TOOL_ARGS_TEMPLATES[tool]()

        roll = random.random()
        if roll < 0.70:
            decision = Decision.ALLOWED
            reason = "Action permitted by policy evaluation"
            matched_policies = random.sample(policy_ids, k=random.randint(1, 2))
        elif roll < 0.90:
            decision = Decision.BLOCKED
            reason = random.choice([
                "Action blocked: destructive database operation not permitted",
                "Action blocked: transaction exceeds agent limit",
                "Action blocked: bulk export exceeds row limit",
                "Action blocked: access to restricted resource denied",
                "Action blocked: PII access requires additional authorization",
            ])
            matched_policies = random.sample(policy_ids, k=random.randint(1, 3))
        else:
            decision = Decision.APPROVED
            reason = "Action requires human approval - escalated to manager"
            matched_policies = random.sample(policy_ids, k=1)

        ts = rand_dt(7)
        log = AuditLog(
            id=uid("audit_"),
            timestamp=ts,
            agent_id=agent["id"],
            agent_name=agent["name"],
            user_id=random.choice(user_ids),
            tool_name=tool,
            arguments=args,
            system_accessed=system,
            data_touched=[f"resource_{uuid.uuid4().hex[:8]}" for _ in range(random.randint(0, 3))],
            decision=decision,
            policy_ids=matched_policies,
            reason=reason,
            log_metadata={"latency_ms": random.randint(5, 120), "sdk_version": "0.1.0"},
        )
        logs.append(log)

    db.add_all(logs)
    db.commit()
    print(f"    {len(logs)} audit logs created")
    return len(logs)


def seed_alerts(db, count: int = 35):
    print("\n  Alerts...")
    existing = db.query(Alert).count()
    if existing >= 15:
        print(f"    Skipped -- {existing} alerts already exist")
        return 0

    active_agents = [a for a in DEMO_AGENTS if a["status"] == AgentStatus.ACTIVE]
    severities = list(AlertSeverity)
    severity_weights = [0.30, 0.30, 0.25, 0.15]  # low, medium, high, critical

    users = db.query(User).filter(User.role.in_([UserRole.ORG_ADMIN, UserRole.ANALYST])).all()
    ack_users = [u.id for u in users] if users else ["user_system"]

    audit_logs = db.query(AuditLog).filter(AuditLog.decision == Decision.BLOCKED).limit(count).all()
    audit_log_ids = [log.id for log in audit_logs]

    alerts = []
    for i in range(count):
        agent = random.choice(active_agents)
        severity = random.choices(severities, weights=severity_weights, k=1)[0]
        alert_type = random.choice(ALERT_TYPES)
        ts = rand_dt(7)

        template = ALERT_DESCRIPTIONS.get(alert_type, "Policy violation by agent '{agent}'")
        description = template.format(
            agent=agent["name"],
            system=random.choice(["postgres-prod", "stripe-api", "s3-storage"]),
            policy=random.choice([p["name"] for p in DEMO_POLICIES]),
            amount=random.choice([5000, 15000, 50000]),
            limit=10000,
            rows=random.choice([8000, 15000, 25000]),
            detail=random.choice(["5 blocked actions in 2 minutes", "Access attempt outside business hours", "Repeated access to restricted table"]),
            tool=random.choice(list(TOOL_SYSTEM_MAP.keys())),
        )

        is_acked = random.random() < 0.4
        alert = Alert(
            id=uid("alert_"),
            timestamp=ts,
            severity=severity,
            alert_type=alert_type,
            agent_id=agent["id"],
            description=description,
            audit_log_id=audit_log_ids[i] if i < len(audit_log_ids) else None,
            acknowledged=is_acked,
            acknowledged_by=random.choice(ack_users) if is_acked else None,
            acknowledged_at=ts + timedelta(minutes=random.randint(5, 120)) if is_acked else None,
        )
        alerts.append(alert)

    db.add_all(alerts)
    db.commit()
    print(f"    {len(alerts)} alerts created")
    return len(alerts)


def seed_alert_configs(db):
    print("\n  Alert Configs...")
    existing = db.query(AlertConfig).count()
    if existing >= 2:
        print(f"    Skipped -- {existing} alert configs already exist")
        return 0

    configs = [
        AlertConfig(id=uid("acfg_"), policy_type="access_control", alert_type="blocked_access", severity="high", conditions={"min_severity": "high"}, enabled=True, created_at=now - timedelta(days=30), updated_at=now - timedelta(days=2)),
        AlertConfig(id=uid("acfg_"), policy_type="financial", alert_type="high_transaction", severity="critical", conditions={"threshold_amount": 10000}, enabled=True, created_at=now - timedelta(days=30), updated_at=now - timedelta(days=5)),
        AlertConfig(id=uid("acfg_"), policy_type="data_protection", alert_type="data_export_attempt", severity="high", conditions={"max_rows": 5000}, enabled=True, created_at=now - timedelta(days=30), updated_at=now - timedelta(days=1)),
        AlertConfig(id=uid("acfg_"), policy_type=None, alert_type="suspicious_pattern", severity="medium", conditions={"window_minutes": 5, "threshold_count": 5}, enabled=True, created_at=now - timedelta(days=30), updated_at=now - timedelta(days=10)),
    ]
    db.add_all(configs)
    db.commit()
    print(f"    {len(configs)} alert configs created")
    return len(configs)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("  Sentinel AI -- Demo Data Seeder")
    print("=" * 70)

    # Ensure all tables exist (covers alert_configs which has no migration)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_users(db)
        seed_agents(db)
        raw_keys = seed_api_keys(db)
        seed_policies(db)
        seed_audit_logs(db)
        seed_alerts(db)
        seed_alert_configs(db)

        print("\n" + "=" * 70)
        print("  [OK] Demo data seeded successfully!")
        print("=" * 70)

        if raw_keys:
            print("\n  Save these API keys for the SDK demo (demo_sdk.py):\n")
            for agent_id, key in raw_keys.items():
                print(f"    {agent_id}:")
                print(f"      {key}\n")

        print("  Dashboard credentials:")
        print("    admin / admin123")
        print("    sarah.chen / demo1234")
        print("    marcus.johnson / demo1234")
        print()

    except Exception as e:
        print(f"\n  ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
