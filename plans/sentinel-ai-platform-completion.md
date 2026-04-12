# Blueprint: Sentinel AI Platform — Healthcare Governance Suite Completion

**Project:** Sentinel AI Platform  
**Root:** `C:\Users\Sameed\Documents\Devotrex\YC`  
**Stack:** Python 3.9+ / FastAPI / SQLAlchemy / Alembic / React + TypeScript / Vite  
**Created:** 2026-04-11  
**Phases:** 6 | **PRs:** 6 | **Execution Model:** Sequential (each phase gates the next)

---

## Architecture Overview

```
sentinel-ai-platform/
├── policy_engine/          # FastAPI backend (Python 3.9+)
│   ├── auth/               # JWT + API key authentication
│   ├── middleware/          # Rate limiting, logging, error handling
│   ├── models/              # SQLAlchemy ORM + Pydantic schemas
│   ├── routes/              # REST API endpoints (flat + clinical/admin/finance/regulatory)
│   └── services/            # Business logic (policy eval, alerts, audit, etc.)
├── dashboard/               # React + TypeScript + Vite frontend
│   └── src/pages/           # All UI pages (clinical, admin, finance, regulatory, risk)
├── sentinel/                # Python SDK for AI agent integration
│   └── sdk/                 # Core SDK + LLM provider adapters
└── alembic/                 # Database migrations (001–013 complete)
```

**Dependency order:** Phase 1 → 2 → 3 → 4 → 5 → 6  
Each phase ships as one PR. No phase begins until the previous phase's tests pass.

---

## Non-Negotiable Quality Standards

These apply to **every** phase. Agents must enforce without exception.

### Code Quality
- All Python functions: full type hints (mypy strict mode — `disallow_untyped_defs = true`)
- Functions < 50 lines; files < 800 lines
- No hardcoded values — constants in `config.py` or environment variables
- No `pass`-only or bare `raise NotImplementedError` outside abstract base classes
- No TODO/FIXME comments in production code paths
- `black` formatting + `isort` imports + `ruff` linting — zero warnings

### Security (Healthcare-grade, non-negotiable)
- OWASP Top 10 checked in every phase touching auth, input, or DB
- PHI/PII must never appear in logs, error messages, or responses
- All DB queries use SQLAlchemy ORM parameterization (never string interpolation)
- No secrets in source code — all from environment variables
- Rate limiting verified on every new endpoint

### Testing
- TDD: write failing test first (RED), implement (GREEN), refactor (IMPROVE)
- 80%+ coverage on all new and modified code (measured with `pytest-cov`)
- Integration tests use SQLite in-memory (`sqlite:///:memory:`) — never mocks for DB
- Each phase must pass `pytest --cov --cov-fail-under=80` before the next phase begins

---

## Phase 1 — Infrastructure Hardening

**Goal:** Fix production-blocking stubs so the platform can be safely deployed.  
**Branch:** `feat/phase-1-infra-hardening`  
**Estimated PR size:** ~250 lines changed

**Why this must come first:** The health probe is broken (always returns `ready: true`),
a core security feature (`is_new_agent` detection) is hardcoded off, and the audit archival
is a no-op stub. These must be fixed before any other work — otherwise Phase 2 tests would
cover broken production paths.

### Tasks (in order)

#### Task 1.0 — Bootstrap Minimal Test Infrastructure
**File:** `tests/conftest.py` (expand existing — file already exists with a sys.path stub)

Phase 1 writes tests that need DB and HTTP client fixtures. Phase 2 expands this further.
Create the minimal set needed for Phase 1 tests only.

```
Steps:
1. Create SQLite in-memory engine + session fixture (scope="function"):
   engine = create_engine("sqlite:///:memory:")
   Base.metadata.create_all(engine)

2. Create TestClient fixture with DB dependency override:
   app.dependency_overrides[get_db] = lambda: test_session

3. Create a conftest-level .env.test with minimum required vars so pytest
   does not fail when SECRET_KEY has no default after Task 3.3:
   - Create tests/.env.test containing:
     SECRET_KEY=test-secret-key-minimum-32-characters-here
     DATABASE_URL=sqlite:///:memory:
     REDIS_URL=redis://localhost:6379/0
   - Load it at the top of conftest.py using load_dotenv("tests/.env.test")
   NOTE: This file must be committed (no real secrets) and listed in .gitignore
   as an EXCEPTION (i.e., force-include the test env file)
```

#### Task 1.1 — Fix Health Readiness Probe
**File:** `policy_engine/routes/health.py`

The `/health/ready` endpoint has two TODO stubs (lines 40–41). Implement real connectivity checks.

```
Steps:
1. Inject database session and Redis client via FastAPI dependency injection
2. Wrap DB check in try/except: execute `SELECT 1` via SQLAlchemy text()
3. Wrap Redis check in try/except: call redis_client.ping()
4. Return HTTP 200 {"ready": true} only if both pass
5. Return HTTP 503 {"ready": false, "checks": {...}} with individual check statuses on failure
6. Add ReadinessResponse Pydantic model (never expose raw error messages — only "db: ok/fail")
```

**Security note:** Error messages must not expose connection strings, hostnames, or credentials.

#### Task 1.2 — Implement New Agent Detection
**File:** `policy_engine/routes/policy_check.py`  
**Lines:** 97, 118, 125 (three occurrences of `is_new_agent=False` inside `trigger_alert()`)

`is_new_agent` is hardcoded `False` in three places inside `trigger_alert()`. The
`AgentActivityService.register_or_update_agent()` call runs at lines 228/323 before
`trigger_alert()` is called, so it can return whether the agent is new.

**IMPORTANT:** `register_or_update_agent()` currently returns an `Agent` object (not `None`).
The fix changes the return type to `Tuple[Agent, bool]` — do NOT change it to just `bool`.

```
Steps:
1. Modify AgentActivityService.register_or_update_agent() to return Tuple[Agent, bool]
   - Return (agent, True) if the agent row was newly INSERTed
   - Return (agent, False) if it was an UPDATE on an existing row
   - New type hint: -> Tuple[Agent, bool]

2. In policy_check.py check_policy() (line 228), capture the tuple:
   agent_obj, is_new_agent = AgentActivityService.register_or_update_agent(...)

3. Pass is_new_agent into trigger_alert() as a new parameter:
   trigger_alert(db, request, response, audit_log_id, is_new_agent=is_new_agent)

4. Update trigger_alert() signature to accept is_new_agent: bool = False

5. Inside trigger_alert(), replace the three hardcoded False values at lines 97, 118, 125
   with the passed-in is_new_agent parameter

6. Repeat for check_policies_batch() at line 323

7. Verify AlertService.should_trigger_alert() already handles is_new_agent=True → CRITICAL alert
```

#### Task 1.3 — Implement Audit Log Cold Storage Archival
**File:** `policy_engine/services/audit_retention.py`  
**Line:** 74 (TODO stub)

The `archive_logs()` method currently logs intent but writes nothing. Implement pluggable storage backend.

```
Steps:
1. Add config settings to policy_engine/config.py:
   - ARCHIVE_BACKEND: str = "local"  # "local" | "s3" | "gcs"
   - ARCHIVE_LOCAL_PATH: str = ""  # Required when ARCHIVE_BACKEND=local — no default (fail-fast if missing)
     NOTE: Do NOT use /var/archive/... as default — this is a Windows dev environment.
     Use: if not settings.ARCHIVE_LOCAL_PATH: raise ValueError("ARCHIVE_LOCAL_PATH must be set")
   - ARCHIVE_S3_BUCKET: str = ""
   - ARCHIVE_S3_PREFIX: str = "audit-logs/"

2. Create policy_engine/services/archive_backends.py with:
   - ArchiveBackend Protocol (abstract interface)
   - LocalArchiveBackend: writes gzip-compressed JSON to local path
   - S3ArchiveBackend: uploads to S3 using boto3 (optional dep — check import)
   - get_archive_backend(config) -> ArchiveBackend factory function

3. Update archive_logs() in audit_retention.py:
   - Call get_archive_backend(settings) to get the configured backend
   - Serialize logs to JSON (never include PHI fields — only id, agent_id, decision, timestamp)
   - Compress with gzip
   - Write via backend
   - Return actual storage location (not fabricated path)
   - Raise ArchivalError if write fails (do NOT delete logs if archival failed)

4. Update delete_archived_logs() to only delete after successful archival confirmation
```

**Security note:** Serialized archive must exclude PHI fields (arguments, data_touched).
Add an `AUDIT_LOG_PHI_FIELDS` constant listing fields to strip before archival.

#### Task 1.4 — Verify Rate Limiting Coverage on All Public Endpoints
**File:** `policy_engine/main.py`, `policy_engine/middleware/rate_limiter.py`

```
Steps:
1. Read main.py to list all registered routers and their prefixes
2. Verify middleware applies to /v1/* and /health* routes
3. Identify any routes NOT covered by rate limiting (e.g., /ws/*, /docs, /redoc)
4. Add explicit exclusion list or ensure WebSocket routes have connection-level limits
5. Update config: ensure RATE_LIMIT_PER_MINUTE is settable per-endpoint type
```

### Tests to Write (TDD order — write RED test first)

**File:** `tests/test_health.py`
```python
- test_readiness_returns_503_when_db_down
- test_readiness_returns_503_when_redis_down  
- test_readiness_returns_200_when_all_healthy
- test_liveness_always_returns_200
- test_readiness_response_never_exposes_connection_string
```

**File:** `tests/test_agent_detection.py`
```python
- test_new_agent_triggers_critical_alert
- test_known_agent_does_not_trigger_new_agent_alert
- test_register_or_update_agent_returns_true_on_first_call
- test_register_or_update_agent_returns_false_on_subsequent_calls
```

**File:** `tests/test_audit_retention.py`
```python
- test_archive_logs_writes_to_local_backend
- test_archive_logs_excludes_phi_fields
- test_delete_not_called_if_archival_fails
- test_archive_compresses_output
```

### Security Checkpoints
- [ ] Run `bandit -r policy_engine/routes/health.py policy_engine/services/audit_retention.py`
- [ ] Verify readiness response never includes connection strings (grep for `DATABASE_URL` in response)
- [ ] Verify archive serializer strips PHI fields (unit test asserts no `arguments` field in output)

### Acceptance Criteria
- [ ] `GET /health/ready` returns 503 when DB is down (tested with mock DB failure)
- [ ] `GET /health/ready` returns 503 when Redis is down (tested with mock Redis failure)
- [ ] A policy check from a brand-new `agent_id` generates a CRITICAL severity alert
- [ ] `archive_logs()` writes a real gzip file to local path (verified in test)
- [ ] `archive_logs()` omits `arguments` and `data_touched` from the archive
- [ ] `delete_archived_logs()` is NOT called when `archive_logs()` raises an exception
- [ ] `pytest --cov --cov-fail-under=80` passes on all modified files

### Agent Assignments
| Step | Agent | Role |
|------|-------|------|
| Implement tasks 1.1–1.4 | Sonnet 4.6 (main) | Implementation |
| Review after implementation | `code-reviewer` agent | Quality gate |
| Security scan | `security-reviewer` agent | OWASP + PHI check |
| Test coverage verification | `tdd-guide` agent | Enforce RED → GREEN |

---

## Phase 2 — Test Coverage Retrofit

**Goal:** Achieve ≥80% test coverage on all critical backend paths before adding new features.  
**Branch:** `feat/phase-2-test-coverage`  
**Estimated PR size:** ~1,200 lines (tests only — no production code changes)

**Why this must come before Phase 3:** Security hardening modifies auth and validation code.
Without tests, there is no way to verify that hardening changes don't break existing behavior.
Tests written here become the regression safety net for all subsequent phases.

### Tasks (in order)

#### Task 2.1 — Test Fixtures and Infrastructure
**File:** `tests/conftest.py` (create)

```
Steps:
1. Create SQLite in-memory database fixture: engine + session per test
2. Create FastAPI TestClient fixture with DB override (dependency injection)
3. Create agent_api_key fixture: creates test API key + agent_id
4. Create admin_user_jwt fixture: creates admin user + returns JWT token
5. Create role_user_jwt(role) parametrized fixture for all 8 UserRoles
6. Create mock_redis fixture using fakeredis (add fakeredis to dev deps)
7. Create mock_slack fixture to capture Slack calls without real HTTP
```

#### Task 2.2 — Policy Evaluation Pipeline Tests
**File:** `tests/test_policy_evaluation.py` (create)

Cover the full pipeline: policy_check → evaluator → alert → audit_log

```
Tests to write:
- test_allow_decision_creates_audit_log
- test_block_decision_creates_audit_log
- test_block_decision_triggers_alert
- test_allow_decision_does_not_trigger_alert
- test_policy_check_requires_valid_api_key
- test_policy_check_rejects_mismatched_agent_id
- test_access_control_evaluator_blocks_disallowed_tool
- test_access_control_evaluator_allows_permitted_tool
- test_financial_evaluator_blocks_over_limit_transaction
- test_data_protection_evaluator_blocks_pii_exposure
- test_batch_check_respects_max_batch_size
- test_fail_safe_returns_block_on_evaluation_error
- test_alert_deduplication_within_5_minute_window
- test_slack_notification_sent_when_webhook_configured
- test_slack_notification_not_sent_when_no_webhook
```

#### Task 2.3 — RBAC Permission Matrix Tests
**File:** `tests/test_rbac.py` (create)

Test all 8 healthcare roles against the ROLE_PERMISSIONS matrix.

```
Tests to write (parametrized across all 8 roles):
- test_cmio_has_full_portfolio_view
- test_data_scientist_can_access_model_and_pipeline
- test_compliance_officer_can_access_audit_logs
- test_clinical_user_has_transparency_view_only
- test_unauthorized_role_cannot_access_admin_users
- test_permission_check_returns_false_for_unknown_permission
- test_role_assignment_requires_admin
- test_user_cannot_escalate_own_role
```

#### Task 2.4 — SDK Integration Tests (Task 18.6 deferred)
**File:** `tests/sdk/test_llm_adapters.py` (create)

```
Tests to write:
- test_openai_adapter_extracts_tool_calls_from_response
- test_openai_adapter_handles_missing_tool_calls
- test_openai_adapter_detects_openai_endpoint
- test_anthropic_adapter_extracts_tool_use_blocks
- test_anthropic_adapter_handles_empty_content
- test_azure_adapter_detected_before_openai_adapter
- test_azure_adapter_extracts_deployment_from_url
- test_gemini_adapter_extracts_function_calls
- test_registry_auto_detects_provider_from_endpoint
- test_registry_returns_none_for_unknown_provider
- test_tool_call_normalization_consistent_across_providers
```

#### Task 2.5 — Alert and Slack Service Tests
**File:** `tests/test_alert_service.py` (create)

```
Tests to write:
- test_create_alert_persists_to_db
- test_deduplication_returns_none_within_window
- test_deduplication_creates_new_alert_after_window
- test_severity_classification_returns_critical_for_new_agent
- test_severity_classification_returns_high_for_block_decision
- test_determine_alert_type_returns_none_for_allow
- test_slack_message_format_includes_severity_and_agent
- test_slack_retry_on_network_failure
- test_slack_does_not_raise_on_permanent_failure
```

### Tests to Write — Coverage Targets

| Module | Target Coverage | Key Paths |
|--------|----------------|-----------|
| `routes/policy_check.py` | ≥85% | All branches of trigger_alert, create_audit_log |
| `services/policy_evaluation.py` | ≥85% | Allow/block/approve decision paths |
| `services/alert_service.py` | ≥80% | Dedup, severity, type classification |
| `services/slack_service.py` | ≥80% | Success, retry, failure paths |
| `models/user.py` (RBAC) | ≥90% | All 8 roles × all permissions |
| `sdk/adapters/*.py` | ≥80% | All 4 provider adapters |

### Security Checkpoints
- [ ] Verify test fixtures do not use real external services (all external calls mocked)
- [ ] Verify no real API keys or PHI appear in test fixtures or test data

### Acceptance Criteria
- [ ] `pytest tests/ --cov=policy_engine --cov-fail-under=80` passes
- [ ] `pytest tests/sdk/ --cov=sentinel --cov-fail-under=80` passes
- [ ] All tests run in < 30 seconds (no real I/O in unit/integration tests)
- [ ] No test writes to disk or makes real network calls

### Agent Assignments
| Step | Agent | Role |
|------|-------|------|
| Implement conftest.py + all test files | Sonnet 4.6 (main) | TDD implementation |
| Enforce write-test-first discipline | `tdd-guide` agent | RED → GREEN enforcement |
| Review test quality (no trivial assertions) | `code-reviewer` agent | Test quality gate |

---

## Phase 3 — Security Hardening

**Goal:** Achieve healthcare-grade security (HIPAA + SOC2 readiness).  
**Branch:** `feat/phase-3-security-hardening`  
**Estimated PR size:** ~400 lines changed

**Why this must come before Phase 4–6:** New features (FHIR, Model Cards) will handle real PHI.
Security hardening must be complete before any PHI-processing code is added.
Phase 2 tests provide the regression net to verify hardening doesn't break existing behavior.

### Tasks (in order)

#### Task 3.1 — Upgrade API Key Hashing to Argon2
**File:** `policy_engine/auth/api_key.py`

**Current issue (line 23):** `hashlib.sha256(api_key.encode()).hexdigest()` — SHA-256 is fast,
making brute-force attacks feasible against a leaked DB. Healthcare compliance requires
slow hashing for secrets.

**CRITICAL — read before implementing:** `rbac.py` also contains a SHA-256 hash at line 101
for API key auth. BOTH `api_key.py` AND `rbac.py` must be updated together. Updating only
one will cause auth failures. Additionally, a dual-read grace period is required — flipping
directly to Argon2-only locks out ALL existing API key users immediately because plaintext
keys are not stored and cannot be rehashed.

```
Steps:
1. Add argon2-cffi>=23.1.0 to policy_engine/requirements.txt

2. Create policy_engine/auth/key_hashing.py (new file, single source of truth):
   - hash_api_key(api_key: str) -> str  — uses Argon2id, returns "$argon2id$..." prefixed hash
   - verify_api_key_hash(api_key: str, stored_hash: str) -> tuple[bool, bool]:
       Returns (is_valid, needs_rehash)
       - If stored_hash starts with "$argon2id$": verify with Argon2, return (result, False)
       - If stored_hash is a 64-char hex string (SHA-256 legacy): verify with SHA-256,
         if valid return (True, True) — signal that this key needs rehashing
       - Any other format: return (False, False)
   - DEPRECATION_DEADLINE_DAYS: int = 90  (configurable via config)

3. Update policy_engine/auth/api_key.py:
   - Import from key_hashing.py instead of hashlib
   - In verify_api_key(): call verify_api_key_hash()
   - If needs_rehash is True: rehash and UPDATE the stored hash in DB (transparent upgrade)
   - Log a deprecation warning: "API key {key_id} is using legacy SHA-256 hash — will expire in N days"

4. Update policy_engine/auth/rbac.py line 101:
   - Replace standalone hashlib.sha256 call with import from key_hashing.py
   - Same dual-read logic applies

5. Add HASH_VERSION prefix: stored hashes start with "$argon2id$" (Argon2) or are
   64-char hex (SHA-256 legacy) — this is the version detection mechanism

6. Add scripts/migrate_api_key_hashes.py:
   - Connects to DB, finds all SHA-256 format keys
   - Prints count and a warning that these keys will self-upgrade on next use
   - Optionally sets an expiry date on all SHA-256 keys to force re-issuance after deadline
```

**Security note:** The dual-read strategy means SHA-256 keys silently upgrade to Argon2 on
next successful auth. After DEPRECATION_DEADLINE_DAYS, refuse SHA-256 keys with a clear
"Please re-issue your API key" error. This prevents a production lockout while enforcing migration.

#### Task 3.2 — Fix JWT Audience Verification
**File:** `policy_engine/auth/jwt_utils.py`

**Current issue (line 87):** `options={"verify_aud": False}` — disables audience verification,
allowing tokens issued for other services to be accepted.

```
Steps:
1. Remove {"verify_aud": False} from jwt.decode() options
2. Add audience to token creation: already present (line 64: "aud": "sentinel-api")
3. Add ALLOWED_AUDIENCES: List[str] = ["sentinel-api"] to config.py
4. Pass audience=settings.ALLOWED_AUDIENCES to jwt.decode()
5. Verify decode_access_token() returns None on audience mismatch (tested in Phase 2)
```

#### Task 3.3 — Validate SECRET_KEY Strength at Startup (All Environments)
**File:** `policy_engine/config.py`, `policy_engine/main.py`

**Current issue:** `SECRET_KEY: str = "change-me-in-production"` is in source. The validation
in `jwt_utils.py` only runs for `APP_ENV == "production"`.

```
Steps:
1. Change config.py default: SECRET_KEY has no default (remove the fallback value)
   Use: SECRET_KEY: str = Field(..., description="JWT signing key — required")
2. Add MIN_SECRET_KEY_LENGTH: int = 32 to config.py
3. On app startup (main.py lifespan), validate:
   - SECRET_KEY is present
   - len(SECRET_KEY) >= 32
   - SECRET_KEY not in _DEFAULT_SECRETS set
   (Raise RuntimeError if any check fails — crash-early is safer than silent weak key)
4. Remove the production-only guard from jwt_utils.validate_secret_key_for_production()
   — it is replaced by the startup-time check
```

#### Task 3.4 — Audit All Pydantic Schemas for Input Validation
**File:** `policy_engine/models/schemas.py`

```
Steps:
1. Read schemas.py and list all fields typed as Any, str without constraints, or Optional[str]
2. For every string field that maps to user-controlled input, add:
   - max_length constraint (e.g., agent_id: str = Field(..., max_length=128))
   - pattern constraint where applicable (e.g., agent_id: str = Field(..., pattern=r'^[a-zA-Z0-9_-]+$'))
3. For list fields, add max_items constraint
4. For numeric fields, add ge/le constraints
5. Add a FIELD_LIMITS constants dict to document all limits in one place
```

#### Task 3.5 — Harden CORS to Environment-Aware Policy
**File:** `policy_engine/config.py`, `policy_engine/main.py`

**Current issue:** `CORS_ORIGINS` defaults to localhost in config.py. In production, this
must be set explicitly — it should not silently allow all origins on misconfiguration.

```
Steps:
1. Add CORS_ALLOW_ALL_ORIGINS: bool = False to config.py
2. In main.py: if CORS_ALLOW_ALL_ORIGINS is True AND APP_ENV == "production", raise RuntimeError
3. In main.py: log a WARNING if CORS_ORIGINS contains "*" at startup
4. Add CORS_ALLOW_CREDENTIALS: bool = True and CORS_ALLOW_METHODS, CORS_ALLOW_HEADERS to config
5. Update .env.example with CORS_ORIGINS documentation
```

#### Task 3.6 — Verify Audit Log Append-Only Enforcement
**File:** `policy_engine/routes/audit.py`

```
Steps:
1. Confirm there is no DELETE endpoint for audit logs in audit.py
2. Confirm the ROLE_PERMISSIONS matrix in models/user.py does not grant any role
   "delete_audit_logs" permission
3. Add an explicit HTTP 405 MethodNotAllowed guard: if any DELETE route is accidentally
   added in future, a startup test will catch it
4. Add test: test_no_role_can_delete_audit_logs (test all 8 roles get 403/405)
```

#### Task 3.7 — PHI Redaction Pipeline Verification
**File:** `policy_engine/routes/phi.py`, `policy_engine/services/policy_evaluation.py`

```
Steps:
1. Read PHIRedactionEngine to understand what fields it redacts
2. Trace the data flow: SDK tool call arguments → policy_check → audit_log
3. Verify arguments field in AuditLog is redacted before being written
   (if not, add PHIRedactionEngine call in create_audit_log() before db.add())
4. Verify telemetry data sent to cloud does not contain PHI
5. Add test: test_audit_log_arguments_are_redacted_for_phi_patterns
```

### Security Checkpoints
- [ ] `bandit -r policy_engine/auth/ -l` — zero HIGH severity findings
- [ ] `bandit -r policy_engine/models/schemas.py` — check for B101 (assert), B106 (hardcoded pw)
- [ ] Grep for `hashlib.sha256` in `policy_engine/auth/` only — must not appear after Task 3.1
  (SHA-256 in phi_redaction.py, routes/finance/, and domain/ is correct for non-secret hashing — do NOT change those)
- [ ] Grep for `verify_aud.*False` — must not appear after Task 3.2
- [ ] Run `safety check -r policy_engine/requirements.txt` — no known CVEs in deps

### Acceptance Criteria
- [ ] API key hashing uses Argon2id (verified by inspecting stored hash format in DB)
- [ ] JWT tokens are rejected if audience claim is missing or wrong
- [ ] App crashes at startup with clear error if `SECRET_KEY` is absent or < 32 chars
- [ ] All Pydantic string fields that accept user input have `max_length` constraints
- [ ] `CORS_ALLOW_ALL_ORIGINS=True` + `APP_ENV=production` raises RuntimeError at startup
- [ ] No DELETE route exists for audit logs (verified by route introspection test)
- [ ] Audit log `arguments` field is PHI-redacted before DB write
- [ ] `pytest --cov --cov-fail-under=80` still passes (no regression from Phase 2)

### Agent Assignments
| Step | Agent | Role |
|------|-------|------|
| Implement tasks 3.1–3.7 | Sonnet 4.6 (main) | Security implementation |
| Security audit of auth changes | `security-reviewer` agent | OWASP A02, A03, A07 |
| Verify no regression | `code-reviewer` agent | Cross-check against Phase 2 tests |
| PHI flow review | `healthcare-reviewer` agent | HIPAA compliance |

---

## Phase 4 — Model Card Auto-Fill Engine

**Goal:** Build the core PRD differentiator — automated CHAI-format model card population from  
GitHub and MLflow, eliminating manual entry for AI developers ("Builder" user persona).  
**Branch:** `feat/phase-4-model-card-autofill`  
**Estimated PR size:** ~600 lines

**Why this must come after Phase 3:** The auto-fill engine makes external HTTP calls (GitHub API,
MLflow). Security hardening (rate limiting, input validation, secret management) must be in place
before any outbound integration is added.

### Tasks (in order)

#### Task 4.1 — GitHub Integration Service
**File:** `policy_engine/services/github_integration.py` (create)

```
Steps:
1. Add config settings to config.py:
   - GITHUB_TOKEN: Optional[str] = None  (personal access token)
   - GITHUB_API_BASE_URL: str = "https://api.github.com"
   - GITHUB_REQUEST_TIMEOUT_SECONDS: int = 10

2. Create GitHubIntegrationService class:
   - __init__(token: Optional[str], base_url: str)
   - get_repo_metadata(repo_url: str) -> RepoMetadata
     - Extract owner/repo from URL using regex (validate format before HTTP call)
     - Call GET /repos/{owner}/{repo}
     - Return: description, default_branch, language, last_push_at, topics
   - get_recent_commits(owner: str, repo: str, limit: int = 20) -> List[CommitSummary]
     - Call GET /repos/{owner}/{repo}/commits?per_page={limit}
     - Return: sha (short), message, author, date
   - get_test_metrics(owner: str, repo: str) -> Optional[TestMetrics]
     - Call GET /repos/{owner}/{repo}/actions/runs?per_page=1
     - Extract: latest run conclusion, test pass rate if available

3. PHI safety: assert no PHI patterns in repo_url before making HTTP call.
   NOTE: PHIRedactionEngine does NOT have a contains_phi() method — it only has redact().
   Instead: add a contains_phi(text: str) -> bool method to PHIRedactionEngine as a
   prerequisite sub-task (Task 4.0 below), OR use: redact(url) != url as the PHI check.
4. Use httpx>=0.27 (async) not requests — consistent with FastAPI async context
   Use connect_timeout=5.0, read_timeout=settings.GITHUB_REQUEST_TIMEOUT_SECONDS
5. Handle rate limit (429) and auth failure (401) with specific exceptions
```

#### Task 4.2 — MLflow Integration Service
**File:** `policy_engine/services/mlflow_integration.py` (create)

```
Steps:
1. Add config settings:
   - MLFLOW_TRACKING_URI: Optional[str] = None
   - MLFLOW_REQUEST_TIMEOUT_SECONDS: int = 10

2. Create MLflowIntegrationService class:
   - __init__(tracking_uri: Optional[str])
   - get_model_metrics(experiment_id: str, run_id: Optional[str] = None) -> ModelMetrics
     - Call MLflow REST API: GET /api/2.0/mlflow/runs/get or /runs/search
     - Return: accuracy, precision, recall, f1, auc, custom metrics dict
   - get_model_parameters(run_id: str) -> Dict[str, str]
     - Return: training parameters (batch_size, learning_rate, epochs, etc.)
   - get_model_artifacts(run_id: str) -> List[ArtifactSummary]
     - Return: artifact names and sizes (not contents — avoid data exfil)

3. PHI safety: MLflow artifact names may contain patient data — run through PHIRedactionEngine
4. If MLflow not configured, return None gracefully (optional integration)
```

#### Task 4.3 — CHAI Model Card Auto-Fill Service
**File:** `policy_engine/services/model_card_service.py` (create)

The CHAI (Coalition for Health AI) format has defined sections. This service maps
GitHub + MLflow data to those sections.

```
CHAI sections to auto-populate:
- intended_use: from repo description + topics
- clinical_indications: from repo topics matching clinical keywords
- contraindications: left blank (requires human input — flag as required)
- training_data_description: from MLflow parameters
- performance_metrics: from MLflow metrics (accuracy, AUC, etc.)
- subgroup_performance: from MLflow metrics with demographic tags
- known_limitations: from README sections matching "limitation" keyword
- version_history: from GitHub commits (last 10, summarized)
- last_updated: from GitHub last_push_at

Steps:
1. Create ModelCardAutoFillRequest schema (repo_url, mlflow_run_id, experiment_id)
2. Create ModelCardAutoFillResult schema (pre_filled: dict, requires_human_review: list[str])
3. Create ModelCardAutoFillService:
   - auto_fill(request: ModelCardAutoFillRequest) -> ModelCardAutoFillResult
   - Orchestrates GitHubIntegrationService + MLflowIntegrationService
   - Returns pre-filled fields + list of fields that REQUIRE human review before publishing
4. Add to routes/clinical/model_cards.py:
   - POST /v1/clinical/model-cards/{card_id}/auto-fill
```

#### Task 4.4 — Input Validation for External URLs
**File:** `policy_engine/services/github_integration.py`

Before making any external HTTP call, validate the input URL to prevent SSRF attacks.

```
Steps:
1. Create validate_github_url(url: str) -> tuple[str, str]:
   - Assert URL matches r'^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$'
   - Raise ValueError with safe message on mismatch
   - Return (owner, repo) tuple
2. Create validate_mlflow_uri(uri: str) -> str:
   - Assert URI scheme is http or https only (reject file://, ftp://, etc.)
   - Parse hostname with urllib.parse.urlparse()
   - Resolve hostname to IP FIRST using socket.getaddrinfo() — do this BEFORE any regex/range check
     to prevent DNS rebinding bypass (attacker's domain resolves to 127.0.0.1)
   - Check ALL resolved IPs against private ranges using ipaddress module:
     private = [IPv4Network("127.0.0.0/8"), IPv4Network("10.0.0.0/8"),
                IPv4Network("172.16.0.0/12"), IPv4Network("192.168.0.0/16"),
                IPv4Network("169.254.0.0/16"), IPv4Network("::1/128")]
   - Pin the resolved IP for the actual httpx request (pass explicit IP, override Host header)
     to prevent TOCTOU/DNS rebinding after validation passes
   - Reject non-standard ports (only 80 and 443 allowed unless MLFLOW_ALLOW_CUSTOM_PORT=True)
   - Raise SSRFBlockedError (custom exception) on any violation
3. Apply validation at the top of every method that makes outbound calls
   NOTE: validate_mlflow_uri must be called in MLflowIntegrationService.__init__(), not just
   at the call sites, so the tracking URI is validated once at construction time
```

### Tests to Write

**File:** `tests/test_model_card_autofill.py`
```python
- test_github_service_extracts_owner_repo_from_url
- test_github_service_rejects_non_github_urls (SSRF prevention)
- test_github_service_rejects_private_ip_mlflow_uri
- test_github_service_returns_none_on_rate_limit
- test_model_card_auto_fill_populates_intended_use
- test_model_card_auto_fill_flags_contraindications_as_required
- test_model_card_auto_fill_works_without_mlflow_configured
- test_phi_check_rejects_repo_url_with_patient_id
```

### Security Checkpoints
- [ ] SSRF prevention: private IP ranges blocked for all outbound URLs
- [ ] GitHub token stored in env var, never logged
- [ ] PHI check on all external URLs before HTTP call
- [ ] `bandit -r policy_engine/services/github_integration.py` — check B310 (URL open)

### Acceptance Criteria
- [ ] `POST /v1/clinical/model-cards/{id}/auto-fill` with a real public GitHub URL returns pre-filled data
- [ ] SSRF attack (using `http://127.0.0.1:8000` as MLflow URI) returns 400, not a server-side request
- [ ] Auto-fill marks `contraindications` as requiring human review
- [ ] `pytest --cov=policy_engine/services/github_integration.py --cov-fail-under=80` passes

### Agent Assignments
| Step | Agent | Role |
|------|-------|------|
| Implement 4.1–4.4 | Sonnet 4.6 (main) | Feature implementation |
| SSRF + injection review | `security-reviewer` agent | OWASP A10 (SSRF) |
| API design review | `code-reviewer` agent | Interface quality |

---

## Phase 5 — FHIR/DICOM Integration

**Goal:** Implement real HL7 FHIR R4 parsing and DICOM de-identification,  
wiring to existing `fhir_cache.py` and `dicom_metadata.py` models.  
**Branch:** `feat/phase-5-fhir-dicom`  
**Estimated PR size:** ~700 lines

**Why this must come after Phase 4:** PHI redaction pipeline (Phase 3) and security hardening
are prerequisites for any code that processes real patient data. FHIR/DICOM resources may
contain PHI that must be de-identified before storage.

### Tasks (in order)

#### Task 5.1 — Make pydicom a Hard Dependency
**File:** `policy_engine/requirements.txt`

**Current issue:** `infrastructure/external/dicom_client.py` raises `NotImplementedError`
if `pydicom` is not installed. This silently breaks DICOM functionality.

```
Steps:
1. Add pydicom>=2.4.0 to policy_engine/requirements.txt (hard dep, not optional)
2. Add fhir.resources>=7.0.0 to requirements.txt for FHIR R4 resource models
3. Remove the NotImplementedError guard from dicom_client.py
4. Update pyproject.toml dependencies section to match
```

#### Task 5.2 — FHIR R4 Parser Service
**File:** `policy_engine/services/fhir_service.py` (create)

```
Steps:
1. Create FHIRParserService class:
   - parse_patient(resource: dict) -> PatientRecord
     - Extract: id, birth_date (year only for de-id), gender, race, ethnicity
     - Strip: name, address, phone, SSN, MRN (PHI fields)
   - parse_observation(resource: dict) -> ObservationRecord
     - Extract: code (LOINC), value, unit, effective_date, status
     - Link to patient_id (de-identified)
   - parse_diagnostic_report(resource: dict) -> DiagnosticReportRecord
     - Extract: code, conclusion, issued_date, performer (role only, not name)
   - store_to_cache(records: list, db: Session) -> int
     - Write to fhir_cache.py model (existing)
     - Return count of records stored

2. De-identification rules (Safe Harbor method per HIPAA 45 CFR 164.514(b)):
   - Remove: names, geographic data smaller than state, all dates except year,
     phone, fax, email, SSN, MRN, health plan numbers, account numbers,
     certificate numbers, VINs, device identifiers, URLs, IP addresses,
     biometric identifiers, full-face photos, any other unique identifier
   - Create PHI_FHIR_FIELDS_TO_STRIP: List[str] constant for the stripping list

3. Create /v1/fhir route file: policy_engine/routes/fhir.py
   - POST /v1/fhir/ingest (accepts FHIR Bundle or individual resources)
   - GET /v1/fhir/cache (paginated list of cached de-identified records)
   - Auth: requires compliance_officer or data_scientist role
```

#### Task 5.3 — DICOM De-Identification Pipeline
**File:** `policy_engine/services/dicom_service.py` (create)

```
Steps:
1. Create DICOMDeidentificationService class:
   - deidentify_metadata(dicom_file_bytes: bytes) -> DICOMMetadataRecord
     - Use pydicom to parse DICOM file
     - Apply DICOM PS 3.15 Annex E de-identification profile (Basic Application Level)
     - Strip: PatientName, PatientID, PatientBirthDate (keep AgeAtExam if available)
       NOTE: Do NOT strip PatientSex — it is NOT one of the 18 HIPAA Safe Harbor identifiers
       (45 CFR 164.514(b)(2)), and it is required for CHAI subgroup performance analysis by sex
     - Preserve: StudyDescription, Modality, Manufacturer, SOPClassUID, StudyDate (year only)
     - Return de-identified metadata dict (never return pixel data)
   - extract_ai_relevant_metadata(record: DICOMMetadataRecord) -> AIMetadata
     - Return: modality, body_part, study_description, manufacturer, model_name

2. Create /v1/dicom route file: policy_engine/routes/dicom.py
   - POST /v1/dicom/extract (accepts multipart/form-data with DICOM file)
   - GET /v1/dicom/metadata (paginated de-identified metadata)
   - File size limit: 50MB (config: DICOM_MAX_FILE_SIZE_MB: int = 50)
   - Content-Type validation: only application/dicom accepted
   - Auth: requires data_scientist or cmio role
```

#### Task 5.4 — Domain Events Route
**File:** `policy_engine/routes/domain_events.py` (create)

**Gap identified in audit:** Migration 007 created `domain_events` table but no route exists.

```
Steps:
1. Create GET /v1/domain-events route with:
   - Pagination (offset/limit)
   - Filter by event_type, agent_id, timestamp range
   - Auth: requires compliance_officer role
2. Maintain append-only: no POST/PUT/DELETE endpoints
```

### Tests to Write

**File:** `tests/test_fhir_service.py`
```python
- test_patient_resource_strips_phi_fields
- test_patient_resource_preserves_birth_year_only
- test_observation_resource_preserves_loinc_code
- test_fhir_bundle_ingestion_returns_count
- test_fhir_ingest_requires_auth
```

**File:** `tests/test_dicom_service.py`
```python
- test_dicom_deidentification_removes_patient_name
- test_dicom_deidentification_preserves_modality
- test_dicom_file_size_limit_enforced
- test_dicom_rejects_non_dicom_content_type
- test_dicom_pixel_data_never_returned
```

### Security Checkpoints
- [ ] Verify FHIR endpoint never returns raw PHI (test with patient name in fixture, assert not in response)
- [ ] Verify DICOM pixel data is never returned by any endpoint
- [ ] File upload endpoint validates Content-Type and enforces size limit
- [ ] `bandit -r policy_engine/routes/fhir.py policy_engine/routes/dicom.py`

### Acceptance Criteria
- [ ] FHIR Patient resource ingest strips all 18 HIPAA Safe Harbor identifiers
- [ ] DICOM upload returns de-identified metadata only (no pixel data, no patient name)
- [ ] `GET /v1/domain-events` returns paginated results (no 404)
- [ ] pydicom import works without NotImplementedError
- [ ] `pytest --cov --cov-fail-under=80` passes

### Agent Assignments
| Step | Agent | Role |
|------|-------|------|
| Implement 5.1–5.4 | Sonnet 4.6 (main) | Feature implementation |
| PHI de-identification review | `healthcare-reviewer` agent | HIPAA Safe Harbor validation |
| Security review of file uploads | `security-reviewer` agent | File upload security |

---

## Phase 6 — Deployment Packaging

**Goal:** Package the platform for production deployment (Docker, Helm, on-prem installer).  
**Branch:** `feat/phase-6-deployment`  
**Estimated PR size:** ~400 lines (config/infra files)

**Why this must come last:** Deployment packaging depends on the final shape of all
configuration values (added in Phases 1–5). Running this phase first would produce
stale config documentation.

### Tasks (in order)

#### Task 6.1 — Policy Engine Dockerfile
**File:** `Dockerfile.backend` (create at root)

```
Requirements:
- Multi-stage build: builder stage + runtime stage
- Runtime stage: python:3.11-slim (not full image)
- Non-root user: create sentinel user (UID 1000), run as that user
- No secrets in any layer: all config via ENV vars at runtime
- COPY only policy_engine/, sentinel/, alembic/, requirements files
- Expose port 8000
- HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
  NOTE: Do NOT use curl — python:3.11-slim does not include curl. Use the Python stdlib instead.
- Use .dockerignore to exclude .env, .venv, __pycache__, *.pyc, tests/, plans/
```

#### Task 6.2 — Dashboard Dockerfile
**File:** `Dockerfile.frontend` (create at root)

```
Requirements:
- Stage 1: node:18-alpine — install deps + build (npm run build)
- Stage 2: nginx:alpine — copy dist/ to /usr/share/nginx/html
- Custom nginx.conf: 
  - gzip compression enabled
  - Security headers: X-Frame-Options SAMEORIGIN, X-Content-Type-Options nosniff,
    Content-Security-Policy (script-src 'self')
  - Try_files for SPA routing (all paths → index.html)
  - API proxy: /api/* → http://backend:8000/
- EXPOSE 80
- Non-root: run nginx as non-root user (nginx user already exists in nginx:alpine)
```

#### Task 6.3 — Docker Compose for Local Dev
**File:** `docker-compose.yml` (create at root)

```
Services:
- postgres:
    image: postgres:16-alpine
    environment: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD (from .env)
    volumes: postgres_data:/var/lib/postgresql/data
    healthcheck: pg_isready
- redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    healthcheck: redis-cli ping
- backend:
    build: Dockerfile.backend
    depends_on: [postgres, redis] (with condition: service_healthy)
    environment: all required ENV vars (from .env)
    ports: "8000:8000"
    volumes: ./alembic:/app/alembic (for running migrations)
- frontend:
    build: Dockerfile.frontend
    depends_on: [backend]
    ports: "3000:80"

Networks: single bridge network (sentinel-network)
Volumes: postgres_data, redis_data
```

#### Task 6.4 — Environment Variable Documentation
**File:** `.env.example` (create/update at root)

Document every required and optional environment variable with:
- Variable name
- Required/Optional
- Default value (if optional)
- Description
- Example value (never real values)

```
Required (platform will not start without these):
SECRET_KEY=                    # min 32 chars, generate: python -c "import secrets; print(secrets.token_hex(32))"
DATABASE_URL=                  # postgresql://user:pass@host:5432/dbname
REDIS_URL=                     # redis://:password@host:6379/0

Optional with safe defaults:
APP_ENV=development            # "development" | "production"
CORS_ORIGINS=                  # comma-separated list of allowed origins
RATE_LIMIT_PER_MINUTE=1000
ARCHIVE_BACKEND=local          # "local" | "s3" | "gcs"
GITHUB_TOKEN=                  # for Model Card auto-fill (Phase 4)
MLFLOW_TRACKING_URI=           # for Model Card auto-fill (Phase 4)
DICOM_MAX_FILE_SIZE_MB=50
```

#### Task 6.5 — Helm Chart Skeleton
**Directory:** `helm/sentinel-ai/` (create)

```
Structure:
helm/sentinel-ai/
├── Chart.yaml          (name, version, appVersion)
├── values.yaml         (all configurable values with defaults)
├── templates/
│   ├── backend-deployment.yaml
│   ├── backend-service.yaml
│   ├── frontend-deployment.yaml
│   ├── frontend-service.yaml
│   ├── ingress.yaml (with TLS section)
│   ├── secret.yaml (for SECRET_KEY, DB creds — references existing K8s Secret)
│   └── configmap.yaml (for non-sensitive config)

Security requirements for Helm templates:
- securityContext: runAsNonRoot: true, readOnlyRootFilesystem: true
- resources.limits defined (no unbounded containers)
- No secrets in values.yaml — only secret name references
- networkPolicy template (allow only backend→postgres, backend→redis, frontend→backend)
```

### Tests to Write

**File:** `tests/test_docker_build.sh` (shell script, not pytest)
```bash
- Build both images without error
- Run backend container, verify /health returns 200
- Run frontend container, verify nginx serves index.html
- Verify no secrets leaked in docker inspect output
```

**File:** `tests/test_env_validation.py`
```python
- test_app_crashes_if_secret_key_missing
- test_app_crashes_if_database_url_missing
- test_app_starts_with_all_required_vars_set
```

### Security Checkpoints
- [ ] `docker scout cves Dockerfile.backend` — no CRITICAL CVEs in base image
- [ ] Verify non-root user in both containers: `docker run --rm sentinel-backend whoami` → not root
- [ ] Verify no .env file is copied into any image layer
- [ ] Helm templates: all secrets reference K8s Secret objects (no plaintext in values.yaml)

### Acceptance Criteria
- [ ] `docker build -f Dockerfile.backend .` succeeds
- [ ] `docker build -f Dockerfile.frontend .` succeeds
- [ ] `docker-compose up` starts all 4 services and passes health checks
- [ ] `helm lint helm/sentinel-ai/` passes with zero warnings
- [ ] `.env.example` documents every variable used in config.py
- [ ] Backend container runs as non-root user

### Agent Assignments
| Step | Agent | Role |
|------|-------|------|
| Implement 6.1–6.5 | Sonnet 4.6 (main) | Infrastructure implementation |
| Container security review | `security-reviewer` agent | Image hardening, secret leakage |
| Review nginx config | `code-reviewer` agent | Security headers, CSP |

---

## Dependency Graph

```
Phase 1 (Infra Hardening)
    │
    ▼
Phase 2 (Test Coverage) ──── requires Phase 1 stubs fixed
    │
    ▼
Phase 3 (Security Hardening) ─── requires Phase 2 tests as regression net
    │
    ▼
Phase 4 (Model Card Auto-Fill) ── requires Phase 3 PHI + SSRF hardening
    │
Phase 5 (FHIR/DICOM) ─────────── requires Phase 3 PHI redaction pipeline
    │
    ├── Phase 4 and 5 CAN run in parallel if two engineers are available
    │
    ▼
Phase 6 (Deployment Packaging) ── requires all config vars finalized (Phases 1–5)
```

**Parallelism opportunity:** Phase 4 and Phase 5 are independent of each other.
They share only the Phase 3 security foundation. If capacity allows, they can be
developed in parallel branches and merged in any order before Phase 6.

---

## Phase Completion Gates

Before marking any phase complete:

1. `pytest --cov --cov-fail-under=80` passes on all files modified in this phase
2. `bandit -r <changed-files> -l` — zero HIGH severity findings
3. `mypy policy_engine/ --strict` — zero type errors on changed files
4. `ruff check policy_engine/` — zero linting errors
5. `black --check policy_engine/` — zero formatting violations
6. PR description includes security checklist (checked off)
7. `code-reviewer` agent has reviewed and approved
8. `security-reviewer` agent has reviewed changes touching auth, input, or external calls

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Argon2 migration breaks existing API keys | High | Medium | Add migration script; document re-issuance in Phase 3 |
| pydicom not available in CI | Low | Low | Hard dep added in Phase 5 requirements |
| GitHub API rate limiting in tests | Medium | Low | Mock all external HTTP in tests (Phase 2 conftest) |
| FHIR de-identification misses PHI field | Medium | High | Use established HIPAA Safe Harbor field list; add PHI-check test |
| Docker non-root breaks file permissions | Low | Low | Test container startup in Phase 6 acceptance criteria |
| Phase 4 SSRF via MLflow URI | Medium | Critical | Validate URI against private IP ranges before any HTTP call |

---

## Rollback Strategy

Each phase ships as one PR on a feature branch.

- **Phase 1–3:** If a phase introduces a regression, revert the PR (git revert merge commit).
  Tests from Phase 2 will catch regressions before merge.
- **Phase 4–5:** These add new routes only — no existing routes are modified.
  Rollback = delete new route files and remove router registration from main.py.
- **Phase 6:** Infrastructure-only. No application code changed.
  Rollback = delete Docker/Helm files. No impact on running application.

**Database:** Alembic migrations are in-flight through Phase 5. Each phase that adds
a migration must include a corresponding `downgrade()` function. Test the downgrade
path before merging any migration.

---

## Execution Instructions for Fresh Agent

When starting any phase in a new session:

1. Read this file: `plans/sentinel-ai-platform-completion.md`
2. Check current branch: `git branch --show-current`
3. Run: `pytest --cov 2>/dev/null | tail -5` — confirm current baseline
4. Read the specific phase section in this document
5. Use `tdd-guide` agent for TDD enforcement
6. After implementation: run `code-reviewer` agent, then `security-reviewer` agent
7. Only mark phase complete after all Acceptance Criteria are checked off
