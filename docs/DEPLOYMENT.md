# Sentinel AI — Deployment Guide (Company / Local Network)

> **Audience:** Sysadmin, platform engineer, or DevOps installing Sentinel AI on a
> company server, a single VM, or an on-prem network.
> **Scope:** local-network and single-server production-style deployment via
> Docker Compose. Kubernetes is referenced at the end (`helm/sentinel-ai/`).
> **Companion doc:** see `READINESS_ASSESSMENT.md` *before* you go live —
> the platform has open CRITICAL items that this guide does not paper over.

---

## 0. TL;DR

```bash
git clone <repo>                          # or copy the working tree
cd YC
cp .env.example .env                      # fill in REQUIRED values (§3)
docker compose up -d --build              # bring up postgres + redis + backend + frontend
docker compose exec backend alembic upgrade head
docker compose exec backend python create_admin_user.py --default
# Browser → http://<server-ip>/   (admin / admin123 — change immediately)
```

For anything beyond a single-machine evaluation, follow §4–§9 — TLS, secrets,
backups, monitoring, retention. **Do not skip §10 (security checklist) for a
production deployment.**

---

## 1. What you are deploying

The platform has four components:

| Component | What it does | Where it runs |
|---|---|---|
| **Policy Engine** (FastAPI) | REST + WebSocket API, RBAC, audit, alerts, billing, FHIR/DICOM, clinic features | `backend` container, port 8000 |
| **Dashboard** (React/Vite SPA) | Admin UI for users, policies, agents, audit, clinic | `frontend` container (nginx), port 80 |
| **PostgreSQL 16** | All persistent state | `postgres` container |
| **Redis 7** | Cache + rate limit + token blacklist | `redis` container |

Optional satellites you can integrate after the core is up:

- **Browser extension** (`clinic-extension/`) — Manifest V3, installed per workstation, posts shadow-AI observations to the Policy Engine.
- **Python SDK / `@secure_agent` decorator** (`sentinel/`) — embedded into your own AI agent code; talks to the Policy Engine over HTTPS.
- **Slack** — alert webhook (optional).
- **Stripe** — only if you are running the billing / clinic-tier flow.
- **MLflow / GitHub** — only if you use the model-card auto-fill feature.

---

## 2. Prerequisites

### 2.1 Host

| Item | Minimum | Recommended (≤25 internal users / ≤5 agents) |
|---|---|---|
| OS | Ubuntu 22.04 LTS, RHEL 9, Debian 12, or Windows Server 2022 (WSL2/Docker Desktop) | Ubuntu 22.04 LTS |
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB SSD | 100 GB SSD (audit logs + archive grow over time) |
| Network | TCP 80 (UI), 8000 (API), 443 if TLS | Reverse proxy on 443 only |
| Time | NTP-synced (audit chain integrity depends on consistent timestamps) | systemd-timesyncd or chrony |

### 2.2 Software

- **Docker Engine** ≥ 24.x and **Docker Compose plugin** ≥ 2.20 (`docker compose version`).
- **git** (to clone, or copy the tree manually).
- **openssl** (to generate secrets).
- **A modern browser** for the admin UI (Chrome 120+, Edge 120+, Firefox 121+).

### 2.3 Network topology — three deployment shapes

```
┌─────────────────────────────────────────────────────────────────────┐
│                          A — SINGLE SERVER                          │
│  staff laptops ──► http(s)://sentinel.lan ──► [docker host]         │
│                       (nginx :80/:443)            postgres, redis,  │
│                                                   backend, frontend │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                       B — REVERSE PROXY FRONT                       │
│  staff laptops ──► https://sentinel.company.com ──► [proxy host]    │
│                       (Caddy / Traefik / Nginx, TLS)                │
│                              │                                      │
│                              ▼                                      │
│                       [docker host on private subnet]               │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      C — KUBERNETES (helm chart)                    │
│  staff laptops ──► ingress ──► sentinel-ai chart (helm/)            │
│                                  ├── policy-engine deployment       │
│                                  ├── dashboard deployment           │
│                                  ├── postgres statefulset (or RDS)  │
│                                  └── redis statefulset (or Elasticache) │
└─────────────────────────────────────────────────────────────────────┘
```

Most internal company deployments use **Shape B**. Single-machine evaluations
use **Shape A**. Helm is included but not the primary path of this guide.

---

## 3. Configure `.env`

```bash
cp .env.example .env
```

Then edit `.env` and supply the **REQUIRED** values. The rest have sensible
defaults in `policy_engine/config.py`.

### 3.1 Required values

| Variable | How to generate / pick | Notes |
|---|---|---|
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` | ≥ 32 chars. App refuses to start otherwise. Never reuse across environments. |
| `POSTGRES_PASSWORD` | `openssl rand -base64 32` | Used by both the `postgres` container and the backend's `DATABASE_URL`. |
| `REDIS_PASSWORD` | `openssl rand -base64 32` | Used by both the `redis` container and the backend's `REDIS_URL`. |
| `APP_ENV` | `production` | Triggers CORS wildcard guard and other prod-only checks. |
| `CORS_ORIGINS` | `["https://sentinel.company.com"]` | JSON array. Exact origins only — no `*` in production. |

### 3.2 Strongly recommended

| Variable | Why |
|---|---|
| `LOG_LEVEL=INFO` | DEBUG leaks SQL + request bodies. |
| `RATE_LIMIT_PER_MINUTE=120` | Default 1000 is for stress-testing; tighten for prod. |
| `ARCHIVE_BACKEND=local` and `ARCHIVE_LOCAL_PATH=/var/sentinel/archives` | Audit logs older than retention are written here before delete. The path must be a mounted volume (see §6). |
| `ACCESS_TOKEN_EXPIRE_MINUTES=480` | 24 h is the default; shorter is safer. |

### 3.3 Optional integrations — leave unset to disable

| Variable | Used by |
|---|---|
| `GITHUB_TOKEN`, `GITHUB_API_BASE_URL` | Model-card auto-fill from GitHub repos. |
| `MLFLOW_TRACKING_URI`, `MLFLOW_ALLOW_CUSTOM_PORT` | Model-card auto-fill from MLflow registry. |
| `DICOM_MAX_FILE_SIZE_MB` | Upper bound for the `/v1/dicom/extract` endpoint. |
| Stripe keys (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, etc.) | Only if you run the clinic-tier billing flow. Leave unset for internal-only deployments. |
| `SLACK_WEBHOOK_URL` | Outbound alert delivery. |

### 3.4 Dashboard `.env`

```bash
cp dashboard/.env.example dashboard/.env
```

Set:

```env
VITE_API_BASE_URL=https://sentinel.company.com/api
```

For Shape A (single server, no reverse proxy) you can use
`http://<server-ip>:8000` — but **only** for evaluation. Production must be HTTPS.

---

## 4. Bring up the stack

```bash
docker compose up -d --build
docker compose ps                         # all four services should show "healthy"
docker compose logs -f backend | head -100
```

You should see:

```
Starting Policy Engine service...
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

If the backend exits immediately, the most common causes are:

| Log fragment | Cause | Fix |
|---|---|---|
| `SECRET_KEY must be at least 32 characters` | Weak / missing secret | Regenerate per §3.1. |
| `SECRET_KEY is a known weak default` | Left `change-me-in-production` | Regenerate. |
| `CORS_ALLOW_ALL_ORIGINS=True is not allowed in production` | Wildcard CORS + `APP_ENV=production` | Set explicit origins. |
| `psycopg2 ... could not connect` | Postgres not ready / wrong password | `docker compose logs postgres`; check `POSTGRES_PASSWORD` matches both sides. |

---

## 5. Initialize the database and first admin

```bash
# Apply all alembic migrations (idempotent)
docker compose exec backend alembic upgrade head

# Confirm head revision
docker compose exec backend alembic current

# Create the default admin (admin / admin123) — CHANGE THE PASSWORD AT FIRST LOGIN
docker compose exec backend python create_admin_user.py --default

# OR interactively
docker compose exec backend python create_admin_user.py
```

Then in a browser visit `http://<server-ip>/` (Shape A) or
`https://sentinel.company.com/` (Shape B). Log in with the admin you just
created. Change the password under **Profile → Change Password** *before* you
provision any other user.

### 5.1 Optional — seed demo data

For evaluation only. **Never run on a production DB.**

```bash
docker compose exec backend python seed_demo_data.py
docker compose exec backend python seed_demo_extended.py
docker compose exec backend python seed_demo_healthcare.py
```

---

## 6. Persistence and backup

### 6.1 Docker-managed volumes

`docker-compose.yml` declares two volumes:

| Volume | Mount | Contains |
|---|---|---|
| `postgres_data` | `/var/lib/postgresql/data` (inside postgres container) | All application state |
| `redis_data` | `/data` (inside redis container) | Cache, rate-limit, token blacklist (lossy is fine — rebuild on restart) |

Audit-log archives (`ARCHIVE_LOCAL_PATH`) are *not* mounted by default in the
shipped compose file — add a bind mount before you go live:

```yaml
# docker-compose.yml — backend service
volumes:
  - /var/sentinel/archives:/var/sentinel/archives
```

and ensure `ARCHIVE_LOCAL_PATH=/var/sentinel/archives` in `.env`.

### 6.2 Backup strategy

Minimum acceptable for an internal deployment:

```bash
# 1. Postgres logical backup (daily, retain 30 days)
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  | gzip > /var/backups/sentinel/db-$(date +%F).sql.gz

# 2. Audit archive directory rsync (daily)
rsync -a --delete /var/sentinel/archives/ /backup/sentinel/archives/

# 3. Off-host copy (weekly) — required for any deployment touching real users
```

For HIPAA-touching deployments, audit logs are subject to a 6-year retention
floor (HIPAA §164.530(j)). The default retention worker deletes after 365 days
— **this is currently insufficient for covered entities** (see
`READINESS_ASSESSMENT.md` → CRIT-008). Until that is remediated, you must
archive **before** the retention sweep runs and ensure archive durability.

### 6.3 Restore drill

You have not done a backup until you have done a restore. Schedule a quarterly
drill:

```bash
docker compose down
docker volume rm yc_postgres_data
docker compose up -d postgres
gunzip < /var/backups/sentinel/db-YYYY-MM-DD.sql.gz \
  | docker compose exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB"
docker compose up -d
```

---

## 7. TLS, reverse proxy, and exposure

The shipped `nginx.conf` (inside the `frontend` container) serves the SPA on
port 80 and proxies `/api/` to the backend over the docker network. It does
**not** terminate TLS. For anything beyond a single-machine evaluation you must
front the stack with a TLS-terminating reverse proxy on the host.

### 7.1 Caddy (simplest — automatic Let's Encrypt)

`/etc/caddy/Caddyfile`:

```
sentinel.company.com {
    encode gzip
    reverse_proxy 127.0.0.1:80   # the frontend nginx container

    # WebSocket pass-through is automatic in Caddy.
    @api path /api/* /v1/* /ws/*
    reverse_proxy @api 127.0.0.1:8000
}
```

Then publish only port 80 of the frontend and port 8000 of the backend to
`127.0.0.1` in `docker-compose.yml`:

```yaml
backend:
  ports:
    - "127.0.0.1:8000:8000"
frontend:
  ports:
    - "127.0.0.1:80:80"
```

### 7.2 Nginx on the host

If you already run nginx, add a server block:

```nginx
server {
    listen 443 ssl http2;
    server_name sentinel.company.com;
    ssl_certificate     /etc/ssl/certs/sentinel.crt;
    ssl_certificate_key /etc/ssl/private/sentinel.key;

    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location ~ ^/(api|v1|ws)/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
    }
}
```

### 7.3 Firewall rules

| Port | Direction | Open to |
|---|---|---|
| 80 (HTTP) | inbound | redirect to 443 only |
| 443 (HTTPS) | inbound | LAN CIDR (company network) — or VPN range |
| 22 (SSH) | inbound | admin jump host |
| 5432, 6379, 8000 | inbound | **closed** (bound to `127.0.0.1` only) |

For a true intranet deployment, restrict 443 ingress to the company CIDR or
require VPN.

---

## 8. Provisioning users, organizations, agents

After first login the admin should:

1. **Create an Organization** (the tenant boundary): `/organizations` page.
   *Currently* the backend stores `organization_id` on most rows but does not
   enforce it on every read path — see CRIT-001 / CRIT-004 / CRIT-010 in the
   readiness assessment. For a single-tenant internal deployment this is
   manageable; multi-tenant deployments are not yet safe.
2. **Invite users** — assign roles from: `SYSTEM_ADMIN`, `ADMIN`, `ANALYST`,
   `VIEWER`, plus healthcare roles (`CMIO`, `COMPLIANCE_OFFICER`,
   `DATA_SCIENTIST`, `CLINICAL_USER`). **On PostgreSQL the healthcare role
   enum is currently incomplete** (CRIT-009) — only `ADMIN`, `ANALYST`,
   `VIEWER` will work until that migration is fixed.
3. **Define policies** — `/policies` page. Start with a deny-list against
   PHI patterns if you are running healthcare workloads.
4. **Register agents** — `/agents` page. Each agent gets an API key for
   `X-API-Key` auth from the SDK.
5. **Configure alerts** — `/alerts` page. Pick severity thresholds and
   (optionally) the Slack webhook.

---

## 9. Operations runbook

### 9.1 Health checks

| Endpoint | What it tells you |
|---|---|
| `GET /health` | Backend liveness (returns 200 once startup guards pass) |
| `GET /` | API banner |
| `GET /nginx-health` (frontend) | nginx liveness |
| `docker compose ps` | Container status + healthcheck state |

Wire `/health` into your uptime monitor (Uptime Kuma, Pingdom, Datadog, etc.).

### 9.2 Logs

```bash
docker compose logs -f backend          # follow API logs
docker compose logs -f frontend         # follow nginx logs
docker compose logs --since=1h backend  # last hour
```

Production: pipe to a central log store (Loki, ELK, CloudWatch). Backend logs
in JSON-adjacent format; nginx logs in the default `combined` format. The
backend already redacts known PHI patterns from audit-log arguments
(`policy_engine/services/phi_text_check.py`) before write — but **not from
its own application logs**. Treat the backend log stream as PHI-adjacent and
protect accordingly.

### 9.3 Common operational tasks

```bash
# Upgrade after a code pull
git pull
docker compose build backend frontend
docker compose up -d backend frontend
docker compose exec backend alembic upgrade head

# Reset a forgotten password
docker compose exec backend python create_admin_user.py
# (Re-creates with same username — choose a new password.)

# Inspect the audit chain (read-only)
docker compose exec backend python -c \
  "from policy_engine.routes.finance.prior_auth import verify_chain; print(verify_chain())"

# Rotate the JWT secret (forces all sessions to re-login)
#  1. Update SECRET_KEY in .env
#  2. docker compose up -d backend
```

### 9.4 Scheduled jobs

The backend runs an in-process asyncio scheduler (see
`policy_engine/services/scheduler.py`). Active jobs:

| Job | Default interval | Purpose |
|---|---|---|
| `mlflow_auto_sync` | hourly | Drafts model cards from MLflow runs |
| `risk_recompute` | 6 h | Daily risk-portfolio recompute |
| `pms_auto_generate` | daily | Post-market surveillance reports |
| `drift_auto_recompute` | 6 h | Drift detection refresh |
| `clinic_monthly_report` | monthly | Generates the compliance PDF |
| `clinic_subscription_lifecycle` | hourly | Reverts canceled subscriptions after grace |
| `clinic_retention_sweep` | daily | GDPR storage-limitation sweep |

Disable individual jobs by clearing the corresponding env var or feature flag
in `policy_engine/services/*.py`. The scheduler is **single-process** —
running multiple backend replicas will duplicate every job. For multi-replica
deployments, run jobs in a dedicated single-replica `worker` deployment (a
Helm-chart story, not the compose default).

### 9.5 Browser extension rollout (optional)

The clinic shadow-AI extension lives in `clinic-extension/`. To install on a
workstation in unpacked / developer mode:

1. Open `chrome://extensions`, enable Developer Mode.
2. *Load unpacked* → select the `clinic-extension/` directory.
3. Right-click the extension icon → *Options* → set:
   - Endpoint: `https://sentinel.company.com/v1/clinic/shadow-ai/observations`
   - Token: the per-extension token issued from the dashboard (clinic onboarding flow)

For a fleet, use Group Policy / Workspace policy `ExtensionInstallForcelist`
with a packaged `.crx` URL. The repo does not ship a signed build; sign with
your own keypair via `chrome.runtime.id` whitelisting in the manifest.

---

## 10. Pre-go-live security checklist

Walk this list before exposing the platform to any real user. Anything left
unchecked is a known risk you are accepting.

- [ ] `SECRET_KEY` ≥ 32 chars, generated by `secrets.token_hex(32)`, unique per environment
- [ ] `APP_ENV=production`
- [ ] `CORS_ORIGINS` is an explicit allow-list, no `*`
- [ ] TLS terminator in front of the stack; backend + DB ports bound to `127.0.0.1` only
- [ ] Default admin password changed at first login
- [ ] PostgreSQL password unique, ≥ 24 chars
- [ ] Redis password set; Redis not reachable from outside the docker network
- [ ] Daily DB backup + audit archive backup, weekly off-host copy
- [ ] Restore drill scheduled (quarterly)
- [ ] NTP / time sync verified (audit-chain hashes depend on it)
- [ ] Rate limit set conservatively (`RATE_LIMIT_PER_MINUTE`)
- [ ] Token lifetime reduced from default 24 h (`ACCESS_TOKEN_EXPIRE_MINUTES`)
- [ ] Outbound egress restricted: backend only needs to reach Postgres, Redis,
      and any opt-in integrations (Stripe, MLflow, GitHub, Slack)
- [ ] Log shipping to a tamper-resistant store
- [ ] Read `READINESS_ASSESSMENT.md` and consciously accept (or remediate)
      every CRITICAL listed there
- [ ] If healthcare data: do **NOT** deploy until the CRIT cluster on
      tenancy, audit-chain integrity, and PHI handling is closed (see
      `READINESS_ASSESSMENT.md`)

---

## 11. Uninstall / teardown

```bash
docker compose down                   # stop containers, keep volumes
docker compose down -v                # stop and delete volumes (DATA LOSS)
docker image prune -f
```

For a clean re-install, also delete `/var/sentinel/archives` if the data is
no longer needed (and verify nothing under legal hold).

---

## 12. Kubernetes deployment (advanced)

A starter Helm chart lives at `helm/sentinel-ai/`. It is provided as-is and
has not been the focus of the v1.0 work — review `values.yaml` carefully
before use. Notable differences from docker-compose:

- The scheduler must run in **exactly one** replica (set
  `policyEngine.replicaCount: 1` or split a `worker` deployment).
- Postgres and Redis are not packaged in the chart — point at managed services
  (RDS, ElastiCache, Cloud SQL, Memorystore).
- `Ingress` resource needs the same TLS rules and CORS origin as §7.
- Run migrations via a one-shot `Job` (`alembic upgrade head`) before the
  Deployment starts taking traffic.

---

## 13. Where to look when something breaks

| Symptom | First file to read |
|---|---|
| Backend won't start | `docker compose logs backend` → match against §4 table |
| Login fails | `docker compose logs backend` → search for `auth`; verify admin exists |
| Dashboard blank / sidebar empty | Browser dev-tools console; check `VITE_API_BASE_URL` and CORS |
| WebSocket disconnects | `dashboard/src/hooks/useWebSocket.ts`; check reverse-proxy upgrade headers |
| Migration fails | `alembic/versions/` head; check Postgres logs |
| Slow audit page | `policy_engine/routes/audit.py` + Postgres indices (see DB review) |
| Alert never fires | `policy_engine/services/alert_service.py`; check scheduler logs |

---

## 14. Support and references

- **Backend README:** `policy_engine/README.md`
- **Quickstart (developer):** `QUICKSTART.md`
- **Platform overview / pricing:** `docs/PLATFORM_OVERVIEW.md`, `docs/PRICING.md`
- **Clinic-tier blueprint:** `docs/CLINIC_TIER_BLUEPRINT.md`
- **User manual:** `docs/USER_MANUAL.md`
- **OpenAPI docs (live):** `https://<your-host>/api/docs` (only in non-prod) — or run the backend with `DEBUG=true` locally
- **Readiness gates / known issues:** `READINESS_ASSESSMENT.md` (next to this file)

*End of deployment guide.*
