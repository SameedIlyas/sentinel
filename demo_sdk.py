"""
Live SDK demo script for Sentinel AI.

Sends real policy check requests against the running policy engine and displays
the decisions with colored output. Run with the backend server running.

Usage:
    # Terminal 1 - start the backend
    python run_policy_engine.py

    # Terminal 2 - run this demo
    python demo_sdk.py

Requires: requests (pip install requests)
"""

import sys
import time
import json
import textwrap

sys.path.insert(0, ".")

try:
    import requests
except ImportError:
    print("ERROR: 'requests' is required. Install with: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE = "http://localhost:8000"
POLICY_CHECK_URL = f"{API_BASE}/v1/policy/check"
HEALTH_URL = f"{API_BASE}/health"

# ANSI color codes
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"

DECISION_STYLE = {
    "allow": (C.GREEN, C.BG_GREEN, "ALLOWED"),
    "block": (C.RED, C.BG_RED, "BLOCKED"),
    "require_approval": (C.YELLOW, C.BG_YELLOW, "NEEDS APPROVAL"),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_api_keys():
    """Look up raw API keys from the database so the user doesn't have to copy-paste."""
    try:
        import hashlib
        from policy_engine.database import SessionLocal
        from policy_engine.models.api_key import APIKey

        db = SessionLocal()
        records = db.query(APIKey).filter(APIKey.is_active == True).all()
        db.close()

        if not records:
            return {}

        # We can't reverse the hash, so we need to brute-force match with
        # the keys that the seed script could have generated. Instead, we
        # return a mapping of agent_id -> key_hash, and we'll send the raw
        # key via X-API-Key. Since we can't reverse SHA-256, we'll generate
        # a fresh key, store it, and use it.
        #
        # Better approach: generate temporary keys for the demo.
        import uuid
        keys = {}
        for record in records:
            agent_id = record.agent_id
            raw_key = f"sentinel_demo_{uuid.uuid4().hex[:24]}"
            new_hash = hashlib.sha256(raw_key.encode()).hexdigest()

            # Create a temporary demo key
            demo_key = APIKey(
                key=new_hash,
                agent_id=agent_id,
                name=f"Demo Session Key ({agent_id})",
                is_active=True,
            )
            db2 = SessionLocal()
            try:
                db2.add(demo_key)
                db2.commit()
                keys[agent_id] = raw_key
            except Exception:
                db2.rollback()
            finally:
                db2.close()

        return keys

    except Exception as e:
        print(f"{C.YELLOW}  Warning: Could not auto-resolve API keys: {e}{C.RESET}")
        return {}


def check_health():
    try:
        r = requests.get(HEALTH_URL, timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def policy_check(api_key: str, payload: dict) -> dict:
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
    }
    r = requests.post(POLICY_CHECK_URL, json=payload, headers=headers, timeout=10)
    return {"status_code": r.status_code, "body": r.json()}


def print_header():
    print()
    print(f"{C.BOLD}{C.MAGENTA}" + "=" * 70 + C.RESET)
    print(f"{C.BOLD}{C.MAGENTA}  Sentinel AI -- Live SDK Demo{C.RESET}")
    print(f"{C.BOLD}{C.MAGENTA}" + "=" * 70 + C.RESET)
    print()
    print(f"  {C.DIM}This demo sends real policy check requests to the Sentinel")
    print(f"  policy engine and shows how policies enforce governance rules.{C.RESET}")
    print()


def print_scenario(num: int, title: str, description: str):
    print(f"\n{C.BOLD}{C.CYAN}  [{num}] {title}{C.RESET}")
    print(f"  {C.DIM}{description}{C.RESET}")
    print(f"  {C.DIM}{'-' * 60}{C.RESET}")


def print_request(agent_id: str, tool: str, args: dict):
    print(f"  {C.DIM}Agent:{C.RESET}  {C.WHITE}{agent_id}{C.RESET}")
    print(f"  {C.DIM}Tool:{C.RESET}   {C.WHITE}{tool}{C.RESET}")
    compact_args = json.dumps(args, separators=(",", ":"))
    if len(compact_args) > 70:
        compact_args = compact_args[:67] + "..."
    print(f"  {C.DIM}Args:{C.RESET}   {C.DIM}{compact_args}{C.RESET}")


def print_response(result: dict):
    status = result["status_code"]
    body = result["body"]

    if status != 200:
        print(f"\n  {C.RED}{C.BOLD}  HTTP {status}{C.RESET}")
        detail = body.get("detail", json.dumps(body))
        print(f"  {C.RED}  {detail}{C.RESET}")
        return

    decision = body.get("decision", "unknown")
    reason = body.get("reason", "")
    policy_ids = body.get("policy_ids", [])

    fg, bg, label = DECISION_STYLE.get(decision, (C.WHITE, "", decision.upper()))

    print(f"\n  {C.BOLD}  Decision: {bg}{C.WHITE} {label} {C.RESET}")
    print(f"  {C.DIM}  Reason:   {C.RESET}{fg}{reason}{C.RESET}")
    if policy_ids:
        print(f"  {C.DIM}  Policies: {C.RESET}{C.DIM}{', '.join(policy_ids)}{C.RESET}")


def pause(seconds: float = 1.5):
    time.sleep(seconds)


# ---------------------------------------------------------------------------
# Demo scenarios
# ---------------------------------------------------------------------------

SCENARIOS = [
    {
        "title": "Research Agent queries analytics database",
        "description": "A routine read operation -- should be ALLOWED by all policies.",
        "agent_id": "agent_research_assist",
        "payload": {
            "agent_id": "agent_research_assist",
            "user_id": "user_sarah_chen",
            "tool_name": "query_database",
            "arguments": {
                "query": "SELECT COUNT(*) FROM orders WHERE status = 'completed'",
                "database": "analytics_db",
            },
            "context": {"agent_name": "Research Assistant", "llm_provider": "openai"},
        },
    },
    {
        "title": "Research Agent tries to DELETE production records",
        "description": "Destructive operation -- should be BLOCKED by Production Database Protection policy.",
        "agent_id": "agent_research_assist",
        "payload": {
            "agent_id": "agent_research_assist",
            "user_id": "user_sarah_chen",
            "tool_name": "delete_record",
            "arguments": {
                "table": "customers",
                "record_id": "rec_a1b2c3d4",
                "reason": "Duplicate record cleanup",
            },
            "context": {"agent_name": "Research Assistant", "llm_provider": "openai"},
        },
    },
    {
        "title": "Financial Agent processes a small $150 refund",
        "description": "Under the $1,000 threshold -- should be ALLOWED.",
        "agent_id": "agent_financial_analyst",
        "payload": {
            "agent_id": "agent_financial_analyst",
            "user_id": "user_marcus_johnson",
            "tool_name": "transfer_funds",
            "arguments": {
                "amount": 150,
                "currency": "USD",
                "from_account": "acct_7890",
                "to_account": "acct_1234",
                "memo": "Customer refund #4521",
            },
            "context": {"agent_name": "Financial Analyst", "llm_provider": "openai"},
        },
    },
    {
        "title": "Financial Agent attempts a $50,000 wire transfer",
        "description": "High-value transaction -- demonstrates financial governance.",
        "agent_id": "agent_financial_analyst",
        "payload": {
            "agent_id": "agent_financial_analyst",
            "user_id": "user_marcus_johnson",
            "tool_name": "transfer_funds",
            "arguments": {
                "amount": 50000,
                "currency": "USD",
                "from_account": "acct_7890",
                "to_account": "acct_ext_9999",
                "memo": "Vendor payment - Q4 invoice",
            },
            "context": {"agent_name": "Financial Analyst", "llm_provider": "openai"},
        },
    },
    {
        "title": "Data Pipeline Bot attempts to DROP a table",
        "description": "Schema destruction -- should be BLOCKED by Production Database Protection.",
        "agent_id": "agent_data_pipeline",
        "payload": {
            "agent_id": "agent_data_pipeline",
            "user_id": "user_david_kim",
            "tool_name": "drop_table",
            "arguments": {
                "table": "customers",
                "database": "postgres-prod",
                "reason": "Cleanup unused table",
            },
            "context": {"agent_name": "Data Pipeline Bot", "llm_provider": "openai"},
        },
    },
    {
        "title": "Code Reviewer reads a config file from S3",
        "description": "Normal file read from internal storage -- should be ALLOWED.",
        "agent_id": "agent_code_reviewer",
        "payload": {
            "agent_id": "agent_code_reviewer",
            "user_id": "user_emily_rodriguez",
            "tool_name": "read_file",
            "arguments": {
                "path": "configs/deployment.yaml",
                "bucket": "sentinel-configs",
            },
            "context": {"agent_name": "Code Reviewer", "llm_provider": "anthropic"},
        },
    },
    {
        "title": "Customer Support Agent requests schema migration",
        "description": "Schema change -- should REQUIRE APPROVAL per Production Database Protection.",
        "agent_id": "agent_customer_support",
        "payload": {
            "agent_id": "agent_customer_support",
            "user_id": "user_sarah_chen",
            "tool_name": "alter_table",
            "arguments": {
                "table": "customers",
                "action": "add_column",
                "column_name": "loyalty_tier",
                "column_type": "varchar(50)",
            },
            "context": {"agent_name": "Customer Support Agent", "llm_provider": "anthropic"},
        },
    },
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print_header()

    # Health check
    print(f"  {C.DIM}Checking server health...{C.RESET}", end="", flush=True)
    if not check_health():
        print(f" {C.RED}FAILED{C.RESET}")
        print(f"\n  {C.RED}Server is not reachable at {API_BASE}")
        print(f"  Make sure the backend is running: python run_policy_engine.py{C.RESET}\n")
        sys.exit(1)
    print(f" {C.GREEN}OK{C.RESET}")

    # Resolve API keys from database
    print(f"  {C.DIM}Resolving API keys...{C.RESET}", end="", flush=True)
    keys = resolve_api_keys()
    if not keys:
        print(f" {C.RED}FAILED{C.RESET}")
        print(f"\n  {C.RED}No API keys found. Run seed_demo_data.py first.{C.RESET}\n")
        sys.exit(1)
    print(f" {C.GREEN}{len(keys)} agents ready{C.RESET}")

    pause(1)

    print(f"\n{C.BOLD}  Running {len(SCENARIOS)} demo scenarios...{C.RESET}")
    print(f"  {C.DIM}{'=' * 60}{C.RESET}")

    allowed_count = 0
    blocked_count = 0
    approval_count = 0

    for i, scenario in enumerate(SCENARIOS, 1):
        print_scenario(i, scenario["title"], scenario["description"])
        pause(0.8)

        agent_id = scenario["agent_id"]
        api_key = keys.get(agent_id)
        if not api_key:
            print(f"  {C.RED}  No API key for {agent_id} -- skipping{C.RESET}")
            continue

        print_request(agent_id, scenario["payload"]["tool_name"], scenario["payload"]["arguments"])
        pause(0.5)

        try:
            result = policy_check(api_key, scenario["payload"])
            print_response(result)

            decision = result["body"].get("decision", "")
            if decision == "allow":
                allowed_count += 1
            elif decision == "block":
                blocked_count += 1
            elif decision == "require_approval":
                approval_count += 1

        except requests.exceptions.ConnectionError:
            print(f"\n  {C.RED}  Connection error -- is the server running?{C.RESET}")
        except Exception as e:
            print(f"\n  {C.RED}  Error: {e}{C.RESET}")

        pause(1.2)

    # Summary
    print(f"\n\n{C.BOLD}{C.MAGENTA}" + "=" * 70 + C.RESET)
    print(f"{C.BOLD}{C.MAGENTA}  Demo Complete -- Summary{C.RESET}")
    print(f"{C.BOLD}{C.MAGENTA}" + "=" * 70 + C.RESET)
    print()
    print(f"  {C.GREEN}{C.BOLD}{allowed_count}{C.RESET} {C.GREEN}allowed{C.RESET}  |  "
          f"{C.RED}{C.BOLD}{blocked_count}{C.RESET} {C.RED}blocked{C.RESET}  |  "
          f"{C.YELLOW}{C.BOLD}{approval_count}{C.RESET} {C.YELLOW}needs approval{C.RESET}")
    print()
    print(f"  {C.DIM}All decisions were logged as audit entries and can be viewed")
    print(f"  in the Sentinel dashboard at http://localhost:5173{C.RESET}")
    print()
    print(f"  {C.CYAN}Key takeaways:{C.RESET}")
    print(f"    {C.DIM}-{C.RESET} Policies enforce governance rules in real-time (<100ms)")
    print(f"    {C.DIM}-{C.RESET} Every agent action is audited with full context")
    print(f"    {C.DIM}-{C.RESET} Blocked actions trigger alerts visible in the dashboard")
    print(f"    {C.DIM}-{C.RESET} Policies are configurable per-agent and per-tool")
    print()


if __name__ == "__main__":
    main()
