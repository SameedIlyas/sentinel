# Vercel Demo Deployment

This dashboard ships with a self-contained **mock API layer** so you can
host a fully functional demo on Vercel — no backend, no database, no
auth provider required. Visitors auto-login as a demo admin and every
page renders with realistic dummy data.

## How the demo build works

| Piece | Where | What it does |
|---|---|---|
| `src/api/mocks/fixtures.ts` | fixtures | All dummy data (agents, policies, audits, alerts, model cards, risk scores, etc.) |
| `src/api/mocks/router.ts` | router | URL-pattern matcher returning fixture JSON for ~50 endpoints |
| `src/api/client.ts` | interceptor | When `VITE_MOCK_API=true`, every `get/post/put/delete/patch` and every auth call short-circuits to the mock router instead of hitting the network |
| `.env.production` | env | Sets `VITE_MOCK_API=true` so Vercel builds always ship the demo |
| `vercel.json` | config | SPA rewrite (`/* → /index.html`) so React Router deep links work |

In mock mode `isAuthenticated()` always returns `true` and
`validateToken()` returns the demo admin, so the dashboard skips the
login screen on a cold load.

---

## Deploy via Vercel CLI (fastest)

```bash
# 1. Install once
npm i -g vercel

# 2. From repo root
cd dashboard

# 3. First deploy (interactive — pick scope, accept defaults)
vercel

# 4. Production deploy
vercel --prod
```

Vercel auto-detects Vite, but `vercel.json` pins everything so the build
is deterministic. No environment variables to set in the dashboard UI —
`.env.production` already enables mock mode.

## Deploy via Vercel dashboard (GUI)

1. Push this branch to GitHub.
2. Go to <https://vercel.com/new> → **Import** the repo.
3. **Root Directory:** set to `dashboard`.
4. **Framework Preset:** Vite (auto-detected).
5. **Build Command / Output Directory:** leave blank — `vercel.json`
   already specifies `npm run build` and `dist`.
6. **Environment Variables:** none required. (`VITE_MOCK_API=true` is
   already in `.env.production` and committed.)
7. Click **Deploy**.

First deploy takes ~90 seconds. Subsequent deploys are ~30 seconds.

---

## Verifying the demo locally before pushing

```bash
cd dashboard
npm install
npm run build           # produces dist/
npx vite preview        # serves dist/ on http://localhost:4173
```

Open <http://localhost:4173>. You should land directly on the dashboard
(no login screen) with populated charts, tables, and side-nav badges.

Or run the dev server in mock mode:

```bash
VITE_MOCK_API=true npm run dev
```

---

## Switching back to a real backend

In production: delete `VITE_MOCK_API` from `.env.production` (or set it
to `false`) and set `VITE_API_BASE_URL` to your backend URL. Push and
redeploy.

For local dev: the default `.env` already points at
`http://localhost:8000` with `VITE_MOCK_API=false`, so `npm run dev`
hits the real `policy_engine` backend as before.

---

## What's covered vs not

**Covered (all GET reads + most writes):**
- Dashboard metrics, all charts, all KPI cards
- Agents list / detail / activity metrics
- Policies list / create / edit / delete / toggle
- Audit logs list / detail (with filters + pagination)
- Alerts list / acknowledge / rules
- Users list / CRUD
- Clinical: model cards (list, detail, CHAI compliance, related, publish, auto-fill)
- Clinical: bias audits (list, detail, run)
- Clinical: drift (alerts + baselines)
- Clinical: HITL queue + approve/reject
- Admin: Shadow AI detections + allowlist
- Admin: Scribe audits
- Admin: Transparency portal
- Finance: Prior-auth chain + verify
- Finance: Revenue cycle audits
- Regulatory: Technical files, Adverse events, PMS reports
- Risk: Portfolio, scores, history, configuration
- Settings: Organization, Risk config, HIPAA config

**Stubbed (returns success but no real effect):**
- Audit log export (returns a JSON blob of the in-memory page)
- Slack webhook test (always says "simulated successfully")
- Password change / role assignment (returns the same user)

**Not wired (page renders, button no-ops):**
- WebSocket live-update streams — the demo is read-only snapshots.
- Clinic-tier onboarding wizard (steps render, no persistence between reloads).

If a page calls an endpoint that has no handler, the router logs a
warning to the browser console and returns an empty paginated envelope
so the page falls back to an empty state instead of crashing.

---

## Adding more demo data later

Edit `src/api/mocks/fixtures.ts` — every dataset is a plain TypeScript
array typed against `src/types/index.ts`. To handle a newly-added
endpoint, add an `add('get', '/v1/your/path', () => ...)` line to
`src/api/mocks/router.ts`.
