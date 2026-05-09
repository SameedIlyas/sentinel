# Tier 3 Roadmap — Pages with No Real Data Source

These two pages have working backends and CRUD endpoints, but their **data fundamentally cannot exist** without external integrations. Today they only show seed/manual data — the underlying detection or capture mechanism doesn't exist in this repo.

This document scopes how each could move from "scaffold" to "real product feature" — what to build, what to integrate, and what timeline is realistic.

---

## 1. Shadow AI Discovery (`/admin/shadow-ai`)

### Current state

- ✅ Full CRUD backend (`policy_engine/routes/admin/shadow_ai.py`, 285 lines)
- ✅ DB tables: `shadow_ai_detections`, `shadow_ai_allowlist`
- ✅ UI lists detections, severity, confidence, PHI risk, allowlist toggle
- ❌ **Nothing detects shadow AI usage** — detections only exist if a human or seed inserts them

### What "shadow AI" actually means
An employee using ChatGPT/Claude/Gemini/Cohere/Mistral *outside* the governance perimeter — e.g. pasting PHI into the public ChatGPT web app, or a developer calling `api.openai.com` from a department that hasn't been approved.

### Three viable detection paths (pick one)

#### Path A: API gateway / network egress monitoring (RECOMMENDED, ~3 sprints)
Hook into the corporate network or the SaaS API gateway and stream connection metadata to Sentinel.

**Build:**
1. Add a `POST /v1/admin/shadow-ai/ingest` endpoint that accepts batched flow records (`source_ip`, `dest_host`, `dest_port`, `bytes`, `timestamp`).
2. Build a classifier (small static map) that flags hosts in the AI provider list:
   ```
   api.openai.com, api.anthropic.com, generativelanguage.googleapis.com,
   api.cohere.ai, api.mistral.ai, character.ai, api.perplexity.ai,
   chat.deepseek.com, api.together.xyz, api.groq.com, ...
   ```
3. Write a small ingestion adapter for one source. Realistic options:
   - **Cloudflare Zero Trust / Logpush** → posts JSON to a webhook
   - **Zscaler / Netskope** → SIEM API or syslog forwarder
   - **Palo Alto NGFW** → syslog with URL filtering enabled
   - **AWS VPC Flow Logs + Lambda** → for cloud-only orgs
4. PHI-risk classification — heuristics on payload size and destination department (not the payload contents — we don't have those).

**Effort breakdown:**
- Ingest endpoint + classifier: 3 days
- One adapter (Cloudflare): 1 week
- Confidence-scoring logic + dedupe: 3 days
- E2E test against synthetic flow data: 2 days
- Docs for IT/sec team to enable forwarding: 2 days

**Pros:** Vendor-agnostic; covers ALL outbound AI traffic; doesn't require employee software.
**Cons:** Requires customer's IT/security team to enable forwarding (sales friction); BYOC infra.

#### Path B: Browser extension (~5 sprints, fastest "demo")
Ship a Chrome/Edge extension that detects when employees visit known AI hostnames and reports back.

**Build:**
1. `extensions/sentinel-shadow-ai/` — manifest v3 extension
2. Background service worker watches `webRequest` for AI domains
3. `POST /v1/admin/shadow-ai/ingest-browser` with hostname + employee ID (from corporate SSO)
4. Optional: detect paste-of-PHI patterns (regex for SSN, MRN format) and elevate severity

**Effort:** 4-5 weeks for production-grade extension + MDM rollout playbook.

**Pros:** Catches *user* behavior including web app usage (most shadow AI happens in the browser, not via APIs).
**Cons:** Requires corporate device install (MDM); doesn't catch backend/API usage; users can disable.

#### Path C: Self-reported via Sentinel SDK (~1 sprint, weakest)
Modify `sentinel/sdk` to detect calls to non-allowlisted LLM endpoints and log them.

**Build:** SDK already has `LLMAdapterRegistry` (Phase 4 work). Add a config `allowed_providers: List[str]`. When an interceptor sees a call to a provider not in the list, fire `POST /v1/admin/shadow-ai/ingest` with detection metadata.

**Effort:** 3 days.

**Pros:** Already 80% built; ships in next SDK release.
**Cons:** Only catches developers who already use Sentinel SDK — that's not "shadow", that's just a config check.

### Recommendation
**Path A + Path C in parallel.** Path C ships in 1 sprint as a "compliance check" feature for SDK users. Path A starts in parallel; ship Cloudflare adapter first, then add 2-3 more enterprise integrations as design partners come on.

### Success metric
A pilot customer enables Cloudflare forwarding and sees ≥10 real detections in week 1. Anything less means our classifier missed common providers — iterate the host list.

---

## 2. Scribe Audit (`/admin/scribe-audits`)

### Current state

- ✅ Full CRUD backend (`policy_engine/routes/admin/scribe_audits.py`, 271 lines)
- ✅ DB tables: `scribe_audits`, `scribe_audit_findings`
- ✅ UI shows audit_score, hallucination_detected, completeness/attribution scores, findings
- ❌ **No automatic capture** — every audit is currently manually inserted (or seeded)

### What this is
A clinical-documentation AI scribe (Nuance DAX, Abridge, Nabla, Suki, …) listens to a doctor-patient encounter and generates a SOAP/H&P note. Sentinel's job: audit that note for hallucinations, omissions, and unattributed claims **before** the doctor signs it.

### The integration problem
Scribe vendors don't expose "audit me" APIs. The audit must hook into the doctor's workflow at one of three points:

#### Point 1: EHR pre-signature webhook (RECOMMENDED, ~4-6 sprints)
EHRs (Epic, Cerner/Oracle Health, Meditech) emit FHIR `DocumentReference` resources when a clinician *previews* a note before signing.

**Build:**
1. New ingestion endpoint: `POST /v1/admin/scribe-audits/ingest` accepting `{session_id, encounter_audio_url_or_transcript, generated_note_text, ai_model_used, clinician_id}`.
2. Connector to Epic via:
   - **Epic App Orchard** — register an app, request `DocumentReference.Write` and `Encounter.Read` scopes
   - **Cerner FHIR R4 API** — similar via Cerner Code
   - Or **HL7 v2 ADT-A08 listener** for older sites
3. Audit logic (the actual work):
   - Pull encounter audio transcript (FHIR `Media` resource where `subject = Encounter`)
   - Run cross-check: every clinical claim in the note → grep transcript or flag as "unattributed"
   - Score `hallucination_detected` if any claim has zero attribution
   - Score `completeness` against a SOAP template checklist (chief complaint, HPI, ROS, exam, A/P)
   - Score `attribution` as % of claims with transcript anchor
4. Surface findings in the EHR via `Communication` resource that pops up in clinician's inbox

**Effort:**
- Ingest endpoint + score logic: 2 weeks
- Epic App Orchard registration + sandbox: 3-4 weeks (mostly waiting)
- LLM-based fact-checker (claim → transcript matcher): 2 weeks
- Pilot with 1 hospital: 2 sprints
- Total: ~6 sprints to first real audit; ~2 quarters to GA

**Pros:** Hits the workflow at exactly the right moment; clinician sees flags before signing; high clinical value.
**Cons:** EHR integration is slow (Epic app review takes 6-12 weeks); each EHR vendor is a separate effort.

#### Point 2: Scribe vendor API (FAST, but limited coverage, ~1-2 sprints per vendor)
Some scribe vendors expose webhook/audit APIs:

- **Abridge** has a partner API — sends generated note + transcript to a configured URL
- **Nabla** has webhooks for note finalization
- **Nuance DAX** — closed; no public API; requires Microsoft partnership
- **Suki / DeepScribe** — varies; some have webhooks

**Build per vendor:** webhook receiver + auth + payload parser + queue → audit pipeline.

**Effort:** 1-2 weeks per vendor.

**Pros:** No EHR integration; ships fast for design partners using one of these scribes.
**Cons:** Per-vendor work; doesn't cover sites using DAX (which is the market leader). Vendor lock-in risk.

#### Point 3: Browser-extension capture (privacy hostile, NOT RECOMMENDED)
DOM-scrape the EHR page to grab notes before signing. Don't do this — security/legal hellscape, breaks every EHR upgrade, raises BAA questions.

### Recommendation
Build **Point 1 (Epic first)** as the strategic path. Run **Point 2 (Abridge / Nabla)** in parallel for fast pilots — these become demoable in 2-3 sprints and validate the audit logic before the long Epic process completes.

### What to build first (concrete next sprint)

1. **The audit logic itself** — independent of how data arrives:
   - `policy_engine/services/scribe_auditor.py` — given (transcript, generated_note, model_name) → returns audit_score, hallucination_detected, findings list
   - LLM cost: ~$0.02 per note with Claude Haiku 4.5 used as fact-checker
   - Tests with synthetic note + transcript pairs
2. **Mock receiver for design-partner pilots:** a vendor-agnostic POST endpoint that accepts a JSON payload of `{transcript, generated_note}` so partners can hand-feed real (de-identified) examples while we wait on EHR integration

That alone makes the Scribe Audits page meaningful — the LLM judge is the moat, not the integration plumbing.

### Success metric
On a pilot of 200 real (de-identified) scribe-generated notes, our auditor catches ≥80% of hallucinations that human reviewers find, with <10% false-positive rate.

---

## Summary

| Page | Path | Effort to MVP | Effort to GA |
|---|---|---|---|
| Shadow AI Discovery | Cloudflare Zero Trust ingest + provider host list classifier | 3 sprints | 1-2 quarters (more SIEM connectors) |
| Scribe Audits | LLM-based fact-checker + Abridge/Nabla webhook adapters | 2-3 sprints | 2 quarters (Epic / Cerner integration) |

Both are **legitimate roadmap features**, not impossible ones. The fastest path to "this works for real customers" is:
1. Ship the *audit logic* / *classifier* now (the LLM brain in scribe; the host-list brain in shadow AI). Both can be tested with synthetic data.
2. Ship one fast integration each (Path C / Cloudflare) so we have a demo.
3. Ship the deep integrations (Epic, multi-SIEM) over Q3-Q4 as design partners onboard.

The platform should label both pages **"Beta — pilot integrations only"** in the UI until at least one production deployment exists. The seed data we just added makes them useful for evaluators *today* without lying about production readiness.
