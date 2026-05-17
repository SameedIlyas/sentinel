# Sentinel AI v1.0 — PRD (Clinical Shield reframe)

> **Status:** v1.0 draft, generated 2026-05-17.  
> **Relation to `docs/PRD.md`:** this file **supersedes** the v1 PRD for the four sections rewritten below (§3, §4.1, §5.4, §6.1.5, §6.8.2, §10.2) and **adds** §6.8.7, §6.8.8, §6.8.9. All other sections of `docs/PRD.md` (commit `3ae3f7c` baseline) are unchanged unless the construction plan in `plans/clinical-shield-v1.md` says otherwise.  
> **Audience:** investors + engineering. Reframes the product from "enterprise AI monitoring tool" to **clinical compliance shield for small private clinics (1–50 providers).**

---

## 0. Strategic reframe

| | v1 PRD (`docs/PRD.md`) | v1.0 (this doc) |
|---|---|---|
| Buyer | Hospitals, IDNs, MedTech vendors. Clinic SKU as a SMB add-on. | **1–50 provider private clinic.** Single decision-maker (owner / practice manager). Enterprise SKU preserved as a parked path. |
| Privacy posture | **Telemetry after the fact.** Extension reports DNS hits + hashed URL → server records observations. | **Prevention before the fact.** Extension intercepts the `paste` event locally; PHI never reaches the AI tab. Server telemetry becomes a fallback. |
| HIPAA framing | "Minimum Necessary" treated as a compliance checkbox in §10.5. | **"Minimum Necessary" (45 CFR §164.502(b)) is a product feature.** Local sanitisation enforces it at the keyboard. |
| AI tools registry | Vendor + category + risk + handles-PHI flag. | **+ "Model Training Status"** field surfacing the modernised HIPAA risk view: vendor training on customer data = unauthorised disclosure = breach. |
| Roles | Eight canonical roles (`policy_engine/models/user.py:10-20`). | **Two product roles** in clinic UX (Admin / Staff). Eight-role table preserved for the enterprise tier and as a migration substrate for a future hospital persona. |

Principle override (replaces `docs/PRD.md` §4.1.6): **Fail-closed at the keyboard.** Server-side fail-closed posture stays — but the new ground truth is that the extension blocks before any byte hits a third-party AI tab.

---

## 3. Personas (rewrite)

Replaces `docs/PRD.md` §3 for the clinic tier. Enterprise persona definitions in §3 of v1 PRD are preserved unchanged.

### 3.1 Clinic personas (only two)

| Product role | Backend role(s) | Maps to | Sees |
|---|---|---|---|
| **Admin** | `admin` (ORG_ADMIN) — `policy_engine/models/user.py:13`; `system_admin` only for Sentinel staff | Practice owner, practice manager, owner-physician | Everything. AI Tools registry, Practice Rules, Reports, Plan & Billing, Shadow-AI Watcher, Compliance / BAA. |
| **Staff** | Every other backend role — `cmio`, `data_scientist`, `compliance_officer`, `clinical_user`, `analyst`, `viewer` — collapsed in the clinic UX. | Front-desk, nurse, MA, provider, clinic compliance lead | Read-only AI Tools list, Notifications, Shadow-AI Watcher. **No** Plan & Billing, **no** Practice Settings → Compliance click-through, **no** user management. |

Eight-role backend enum is **not** removed. Clinic UX renders the two-role view through an i18n / nav-config layer; enterprise tier continues to render all eight (`dashboard/src/config/navigation.ts:60` and §3 of v1 PRD). Forward migration path to a hospital persona stays open without code changes.

Section visibility is enforced server-side by `policy_engine/auth/rbac.py:19-76` and `policy_engine/models/user.py:56-163` (`ROLE_PERMISSIONS`) — both unchanged. The collapse is an **additive UX projection**, not a destructive enum change.

### 3.2 Non-personas (clinic v1.0)

Departments, multi-site role hierarchies, clinician-specialty routing, and per-clinic-tier RBAC sub-bands are all out of scope. Anything that needs more than Admin/Staff routes through the enterprise tier.

---

## 4.1 Product principles (revised)

Replaces `docs/PRD.md` §4.1.

1. **Structured PHI identifiers are blocked at the device.** (Was: "PHI never leaves the Policy Engine.") The extension intercepts before the paste event reaches the AI tab — `clinic-extension/background.js` gains a content-script paste hook in §6.8.7. The block covers the structured identifier set enumerated in §6.8.7.a (SSN, DOB, NPI, MRN/account, ICD-10, phone, email, ZIP, IP, insurance-ID). It **does not** automatically block free-text patient names, street addresses, biometric or photo data, or non-DOB clinical dates — those gaps are disclosed in §6.8.7.d and addressed by the Sanitize action (§6.8.9) plus the v1.1 NER roadmap. Server-side: clinic PDF reports remain anonymised rollups only (`policy_engine/services/clinic_pdf_report.py:75-158`).
2. **Minimum Necessary is a feature.** 45 CFR §164.502(b) — encoded in the AI Tools registry warning copy (§6.8.8), the paste interceptor (§6.8.7), and the sanitiser (§6.8.9).
3. **Fail-closed at the keyboard.** If the extension cannot reach the policy backend, it still blocks pastes containing local PHI regex matches; it does not fail open.
4. **Existing customers never regress.** Every clinic change is additive at the backend (`docs/PRD.md` §5.2.1 acceptance criterion preserved). An `enterprise` org sees zero behaviour change.
5. **Charge for prevention, not telemetry.** The monthly compliance PDF (`policy_engine/services/clinic_pdf_report.py`) is the visible value prop. Server telemetry from the extension is a fallback, not the product.

---

## 5.4 Clinic browser extension (rewrite)

Replaces `docs/PRD.md` §5.4 (lines 178–191) end to end. Old §5.4 described a "DNS+fingerprint reporter." New §5.4 is a **paste interceptor with telemetry as a fallback**.

### 5.4.1 Surface

- **Stack:** Manifest V3, plain JavaScript. Service worker (`clinic-extension/background.js`) + a new content script (`clinic-extension/content.js`, added in §6.8.7) injected on the hardcoded AI domain list.
- **Permissions** (delta vs. `clinic-extension/manifest.json:7-13`):
  - Kept: `storage`, `tabs`.
  - **Removed:** `webRequest` (no longer needed once DNS-hashing pipeline retires per §6.8 R1).
  - **Added:** `scripting`, `contextMenus`, `clipboardWrite`. `clipboardRead` is intentionally **not** requested — the extension reads paste payloads from the `paste` DOM event, never from a global clipboard read.
  - `host_permissions` narrows from `<all_urls>` to the **explicit AI domain allowlist** (§5.4.3). Chrome Web Store / Edge Add-ons reviewers reject `<all_urls>` content-script injection without a justification; switching to an explicit list shortens review.
- **What it transmits:** unchanged shape minus `page_url_hash` (removed per §6.8 R1). Hostname + tool fingerprint + UA + extension version only. Never PHI, never URL bodies.
- **What it does NOT transmit:** the local PHI match flag, the intercepted paste payload, the sanitised output — **none of these touch the network**. Local-only operations remain local.

### 5.4.2 New responsibilities (v1.0)

| Responsibility | Implementation surface | PRD section |
|---|---|---|
| Detect navigation to a tracked AI tab | `background.js` `chrome.tabs.onUpdated` listener | 5.4.3 |
| Inject content script on tracked tabs | `chrome.scripting.executeScript` from background | 6.8.7 |
| Intercept paste before the AI tab sees it | content-script `paste` event listener, `capture: true` | 6.8.7 |
| Local PHI regex match | shared module duplicated client-side from `policy_engine/services/phi_text_check.py:26-58` | 6.8.7 |
| "Confirm No-PHI" override modal | content-script DOM injection (Shadow DOM) | 6.8.7 |
| "Sanitize with Sentinel" right-click | `chrome.contextMenus.create` + content-script replacer | 6.8.9 |
| Telemetry fallback (server-side observation) | unchanged: `policy_engine/routes/clinic/shadow_ai.py:146-221` | 5.4.4 |

### 5.4.3 Tracked-domain allowlist (replaces R1 hashing pipeline)

A hardcoded list shipped in `clinic-extension/manifest.json` and re-checked in `background.js`. Aims for ~50 consumer AI tools. Today's eleven (`clinic-extension/background.js:18-30`) plus targets: ChatGPT (chat.openai.com, chatgpt.com), Claude (claude.ai), Gemini (gemini.google.com, bard.google.com), DeepSeek (chat.deepseek.com), Perplexity (perplexity.ai, www.perplexity.ai), Jasper (app.jasper.ai), Copilot (copilot.microsoft.com), Pi (pi.ai, heypi.com), Mistral (chat.mistral.ai), Character.ai, Poe, Meta.ai, Hugging Face Spaces (huggingface.co, hf.co), You.com, Phind, NotebookLM, Le Chat, Inflection, Cohere coral, Replicate playground, Together.ai chat. Final list curated by the Healthcare Reviewer in the A2 phase.

Rationale for hardcoded vs. dynamic: the hashed-URL pipeline only ever proved **which top-level domains were visited**. A hardcoded list does that with zero hashing footprint and removes a tenant-scoped column from the DB (see Risk register §R-1 in `plans/clinical-shield-v1.md`).

### 5.4.4 Acceptance criteria

- No PHI leaves the device. Verified by static read of `content.js` (no `fetch` on the paste payload) plus an integration test that mocks `fetch` and asserts only `{ host, tool_fingerprint, severity, user_agent, extension_version }` payloads are sent.
- onBeforePaste blocks the paste event (`preventDefault()` + clipboard purge) when local PHI regex hits before the AI tab's input receives the event.
- Network failures are silently swallowed for telemetry; **paste blocking does NOT depend on network availability** (fail-closed at the keyboard).
- Token plaintext is shown once at issuance; only SHA-256 hash persisted (`policy_engine/models/clinic.py:161-183`, unchanged).
- Extension version on the Chrome Web Store and Edge Add-ons is the same SHA-pinned build that the dashboard's `/clinic/extension/install` page links to.

---

## 6.1.5 Alerts (revised for clinic posture)

Replaces `docs/PRD.md` §6.1.5 (line 269) for clinic tiers. Enterprise tier paragraph preserved.

For clinic tiers, the highest-value alert is no longer "the AI tool responded with X." It is **"a staff member tried to paste PHI into ChatGPT and we stopped them."**

### 6.1.5.a New alert types (clinic only)

| Alert type | Trigger | Translator copy |
|---|---|---|
| `clinic.paste.blocked` | Extension's onBeforePaste hard-intercept blocked a paste; local PHI regex hit. Posted to a new endpoint `POST /v1/clinic/shadow-ai/paste-blocked` (see plan A2). | "We blocked a paste with patient identifiers into {tool}. You don't have to do anything — this was the system protecting you." |
| `clinic.paste.override` | Staff used "Confirm No-PHI" override and pasted anyway. Audit-logged with the user, tool, and timestamp (no payload). | "Staff member {user} confirmed no-PHI and pasted into {tool} on {date}. Verify the paste contents do not contain patient identifiers." |
| `clinic.sanitize.used` | "Sanitize with Sentinel" right-click was used. Audit-logged. | "Staff member {user} sanitised text before pasting into {tool}." |
| `clinic.tool.trains_on_data` | A `ClinicAiTool` row with `model_training_status='trains_on_customer_data'` was added (or its status flipped to that value). | "Heads-up: {tool} uses entered prompts to train its public models. Move it to a Sentinel-approved tool if you handle PHI in it." |

All four route through `policy_engine/services/clinic_alert_translator.py` (unchanged surface).

### 6.1.5.b Acceptance criteria

- New alert types acknowledge through the existing `Alert.acknowledged` field; no schema change to `Alert`.
- WebSocket push within 2 s of the event (`docs/PRD.md` §11 NFR preserved).
- Alert payloads contain **only**: tool name, host, severity, user ID, timestamp. **No** paste content, **no** PHI regex match string.

---

## 6.8.2 AI Tools — Model Training Status (rewrite)

Replaces `docs/PRD.md` §6.8.2 (line 551). Adds one field, two i18n strings, one alert type.

### 6.8.2.a Field additions

To `ClinicAiTool` (`policy_engine/models/clinic.py:52-98`):

| Field | Type | Default | Surfaces in |
|---|---|---|---|
| `model_training_status` | `Enum('unknown', 'no_training', 'trains_on_customer_data', 'opt_out_available')` | `'unknown'` | Tool list, Tool detail, Monthly PDF compliance report. **Records the vendor's capability only.** |
| `practice_opt_out_state` | `Enum('not_applicable', 'required_not_set', 'required_and_set', 'verified')` | `'not_applicable'` | Tool detail + Compliance report. **Records the practice's actual configuration**, separately from vendor capability — audit-relevant. |
| `opt_out_verified_at` | `DateTime` nullable | `NULL` | Tool detail. Set when `practice_opt_out_state` flips to `'verified'`. |
| `opt_out_verified_by_user_id` | FK `users.id` nullable | `NULL` | Tool detail. Provenance of the verification. Only `Admin` (product role, §3.1) can set; Staff cannot. |
| `model_training_status_evidence` | `String(2000)` nullable | `NULL` | Tool detail only (notes-equivalent field for "where did we confirm this") |

Rationale for the split (per adversarial review — see §Review log finding HEALTH-5): `opt_out_available` describes what the vendor offers; it does not prove the practice has set it. A compliance officer asked "is opt-out actually toggled in our ChatGPT Team account today?" must be able to answer from the database, not from memory. The two-field split makes that auditable.

Alembic migration applied on top of the current head. Backfill: all existing rows set to `'unknown'` / `'not_applicable'` (forces clinic admins to triage during the v1.0 rollout — turning the v1.0 release into a UX-driven re-audit of the AI Tools registry, which is itself a sales moment).

### 6.8.2.b UI copy (BAA-aware, bilingual)

Banner copy is a function of `(model_training_status, practice_opt_out_state, organization.hipaa_baa_signed_with_vendor)`. The original "permanently leaked to the public domain" string from the gap analysis was rewritten on adversarial-review grounds (see §Review log finding HEALTH-2): it conflates training-set inclusion with publication, is BAA-unaware, and is legally exposed. Replacement copy below.

**Bilingual requirement.** All four keys must ship in English **and** Spanish at v1.0 launch (US small clinics are frequently Spanish-primary at the front desk). i18n dictionary files: `dashboard/src/i18n/dict/clinic_basic.ts`, `clinic_standard.ts`, `clinic_multi_site.ts`, and the Spanish overlay layer in `clinic_basic.es.ts` (new) etc. Translation reviewed by `healthcare-reviewer`.

| Condition | Banner copy |
|---|---|
| `model_training_status == 'trains_on_customer_data'` AND `practice_opt_out_state in (not_applicable, required_not_set)` AND no signed BAA covering training | **"This tool may train its models on what you type here. Treat anything entered as disclosed outside your practice. Do not enter patient information unless your written BAA with the vendor explicitly permits training use — most BAAs do not."** |
| `model_training_status == 'trains_on_customer_data'` AND practice has signed-BAA-covering-training | "This tool's vendor trains on prompts, but your BAA permits this use. Patient information is still handled under the BAA's terms — confirm with your compliance lead before entering new categories of PHI." |
| `model_training_status == 'opt_out_available'` AND `practice_opt_out_state == 'required_not_set'` | "This tool trains on prompts unless you turn it off in the vendor's settings. Confirm the opt-out is set, then mark this tool as Verified in Sentinel." |
| `model_training_status == 'opt_out_available'` AND `practice_opt_out_state == 'verified'` | "Opt-out verified on {date} by {user}." (informational; no warning style) |
| `model_training_status == 'no_training'` | No banner. |
| `model_training_status == 'unknown'` | Muted "Status not yet confirmed — assign to a practice admin to investigate." Link to the vendor-discovery checklist in `docs/USER_MANUAL.md`. |

i18n keys (English file shown; mirror in `*.es.ts`):

- `clinic.tools.training_status.warning_no_baa`
- `clinic.tools.training_status.warning_baa_present`
- `clinic.tools.training_status.opt_out_required`
- `clinic.tools.training_status.opt_out_verified`
- `clinic.tools.training_status.unknown`

### 6.8.2.c Acceptance criteria

- Field surfaces in `ToolCreate`, `ToolUpdate`, `ToolResponse` schemas (`policy_engine/routes/clinic/tools.py:39-77`).
- `model_training_status='trains_on_customer_data'` triggers a `clinic.tool.trains_on_data` alert exactly once per tool per 30-day window (idempotent — flipping back and forth does not flood the queue).
- Monthly compliance PDF (`policy_engine/services/clinic_pdf_report.py:183-237`) gains a "Tools that train on your data" row in the "Tools registry" section.

---

## 6.8.7 Paste interceptor — `onBeforePaste` hard intercept (NEW)

New v1.0 feature. Implementation is split across the extension and a new server endpoint; the plan in `plans/clinical-shield-v1.md` calls this workstream **A2**.

### 6.8.7.a Behaviour

When the active tab's hostname matches the §5.4.3 allowlist:

1. Content script injected with **`all_frames: true`** (per adversarial review SEC-2 — ChatGPT and Gemini render their inputs inside iframes; a top-frame-only listener is bypassed). Attaches a `paste` event listener with `capture: true, passive: false` on `document` of every same-origin frame on the allowlist.
2. On paste, the listener reads `event.clipboardData.getData('text')` (no global clipboard read, no other MIME types in v1.0).
3. Run the local PHI regex from `clinic-extension/phi_patterns.js`, which is **generated at build time from `policy_engine/services/phi_patterns.json` so client and server can never drift** (per adversarial review ARCH-5). Patterns:
   - From `phi_text_check.py:26-58`: SSN, phone, email, DOB-ISO, DOB-US, 9+ digit MRN/account.
   - **Added in v1.0** (also added to the server side in the same PR): NPI with the CMS `80840` Luhn-prefix algorithm (CMS 73 FR 36459 — quoted verbatim in the implementation file), ICD-10 short-code (`/\b[A-TV-Z][0-9][0-9AB](\.[0-9A-TV-Z]{1,4})?\b/`), US ZIP (5-digit and ZIP+4), IPv4, IPv6, generic insurance-member-ID (alphanumeric 8–16 chars with mixed letters and digits), 2-digit-year DOB gated on a `DOB|dob|born|d\.o\.b` left-context anchor.
   - **Not in v1.0 — explicit gap, disclosed in §6.8.7.d**: free-text patient names, street addresses, non-DOB clinical dates (admission / discharge / death), biometric IDs, fax numbers, vehicle / device serials, photo / image content. The Sanitize action (§6.8.9) covers name redaction with a soft heuristic and explicit user-review prompt; the v1.1 roadmap (`docs/PRD.v2.md` §0 → Tier-1.5) adds local NER.
4. If any pattern matches → `event.preventDefault()` + `event.stopImmediatePropagation()` + clipboard clear. **Clipboard clear uses a two-step path** (per adversarial review SEC-3 — `navigator.clipboard.writeText('')` silently fails under several common Permissions-Policy configurations): primary path is a synchronous `document.execCommand('copy')` against a hidden empty textarea attached to the Shadow DOM; the async `writeText('')` runs as a fallback with a `.catch()` that surfaces a modal line `"Note: your clipboard may still hold the original text — copy something else now before pasting anywhere."` Tested per §6.8.7.e.  
   Inject a Shadow-DOM modal: **"This paste appears to contain patient information. Sentinel stopped it."**  
   Modal offers two options: **Cancel** (default) or **Confirm No-PHI and paste anyway** (logs `clinic.paste.override`).
5. If no pattern match → paste proceeds unmodified.
6. Either way → fire-and-forget POST to `/v1/clinic/shadow-ai/paste-blocked` (new endpoint, see below) with `{ host, tool_fingerprint, action: 'blocked'|'allowed'|'override', regex_categories_matched: ['ssn','dob_us'], user_agent }`. **No paste content, no match snippet, no character offsets** — just the *names* of the regex categories that fired (already known locally, themselves non-PHI). `regex_categories_matched` per adversarial review HEALTH-3, addresses 45 CFR §164.312(b) audit-reconstruction need without making the platform a PHI archive. If the request fails, the local block decision is unchanged.

### 6.8.7.b Server endpoint

New route on `policy_engine/routes/clinic/shadow_ai.py`:

```
POST /v1/clinic/shadow-ai/paste-blocked
  Headers: X-Clinic-Extension-Token: <token>
  Body:    { host: str <=255,
             tool_fingerprint: str | None <=120,
             action: 'blocked' | 'allowed' | 'override' | 'sanitize_used',
             regex_categories_matched: list[str] <=10 items,
                                              each <=30 chars,
                                              matching ^[a-z_]+$,
             user_agent: str | None <=120 }
  Returns: 202 Accepted
  429: rate-limit exceeded
  409: BAA not signed
```

Persistence: a new `ClinicPasteEvent` row keyed on `org_id`, `observed_at`, `action`, `host`, `regex_categories_matched`. Schema mirrors `ClinicAiObservation` (`policy_engine/models/clinic.py:101-126`) minus `page_url_hash`. Cascade delete on org removal.

**Rate-limit + idempotency** (per adversarial review SEC-4): 60 events per token per minute. Deduplicate at insert time on `(org_id, host, action, regex_categories_matched, observed_at` rounded to 1 s`)` — prevents replay-poisoning the audit log.

Authorization via the same hashed-token table (`ClinicExtensionToken`).

### 6.8.7.c Acceptance criteria

- Block fires **before** the AI tab's input receives the keystroke (verified by an integration test that uses Playwright to paste into a mock AI tab and asserts the textarea is still empty post-event). **Includes iframe target** — Playwright spec covers a paste into an `<iframe>` whose `src` matches the allowlist.
- Local block is independent of network. Disconnect the policy backend, paste — still blocked.
- False-positive rate < 5% on a synthetic non-PHI corpus.
- False-negative rate < 1% on the **structured-PHI** sub-corpus (SSN, DOB, NPI, MRN, ICD-10, ZIP, IP, insurance ID) — eval gate is **HARD**.
- **Free-text narrative sub-corpus** (name + address + clinical narrative, no structured identifiers) — reported separately; v1.0 acceptable FN is **< 50%** with the regex-only detector, and the result is gated behind the Sanitize action (§6.8.9) plus explicit disclaimers in the modal and the §10.2.d sales claim. Per adversarial review HEALTH-1, averaging this corpus into the headline 1% FN is forbidden.
- Audit log (server-side) records every override with `user_id`, `tool`, `host`, `regex_categories_matched`, `timestamp` — never the paste content. Decision trade-off documented in §10.2.c.

### 6.8.7.d Disclosed coverage gaps (v1.0)

The paste blocker is intentionally **not** a complete HIPAA Safe Harbor (45 CFR §164.514(b)(2)) detector. Identifiers **not** automatically caught by v1.0:

| Safe Harbor # | Identifier | Why not in v1.0 | Mitigation |
|---|---|---|---|
| 1 | Patient names | Capitalisation heuristic only (in Sanitize, §6.8.9). Free-text NER deferred to v1.1. | User-review modal in Sanitize; staff training in onboarding. |
| 2 | Street address / geo finer than state | Heuristic out of scope | ZIP only is caught. Sanitize action attempts no replacement. |
| 3 | Non-DOB dates (admission, discharge, death) | Indistinguishable from non-clinical dates without context | Disclosed in modal. |
| 5 | Fax numbers | Indistinguishable from phone — phone regex covers most cases | Accepted overlap. |
| 11–13 | Vehicle, device, biometric IDs | Out of scope for clinic LLM paste | n/a |
| 17 | Photos | Paste-text only; image MIME types not handled | v1.1 + binary detection |

These gaps are surfaced in the §10.2.d sales-claim language and in the Sanitize toast (§6.8.9.a).

### 6.8.7.e Verified-claim test list (sales-truth)

Each claim has a named test that must pass before §10.2.d copy goes live:

| Claim | Test |
|---|---|
| "Sentinel cleared your clipboard" | `tests/e2e/test_clipboard_actually_clears.spec.ts` — paste a known string, trigger block, run a second paste, assert empty. |
| "Block works without an internet connection" | `tests/e2e/test_block_offline.spec.ts` — disconnect network, paste with PHI, assert blocked. |
| "Block works on iframe-embedded inputs" | `tests/e2e/test_block_iframe.spec.ts` — paste into an iframe input on a mock ChatGPT-shaped page. |
| "Audit captures categories, not content" | `tests/clinic/test_paste_blocked_audit_redaction.py` — assert no row contains anything resembling SSN/DOB/email in any column. |

---

## 6.8.8 AI Tools — Model Training Status (NEW)

Cross-references §6.8.2. The new field, copy, alert, and PDF row are specified there end to end. This section exists as an anchor for the construction plan (A1).

---

## 6.8.9 Sanitize with Sentinel — right-click action (NEW)

New v1.0 feature. Plan workstream **A3**.

### 6.8.9.a Behaviour

1. Extension registers a context menu item via `chrome.contextMenus.create({ id: 'sentinel-sanitize', title: 'Sanitize with Sentinel', contexts: ['selection'] })`.
2. When a user right-clicks selected text and chooses the menu item:
   - Selected text is **read in the content script**, never sent to the background or to the server.
   - Local transformations are applied:
     - Names (heuristic: 2+ capitalised tokens not in a stop-list) → `[Patient_Name_N]` where `N` increments per unique surface form within the selection.
     - DOBs (ISO + US patterns from `phi_text_check.py`) → `[DOB_N]`.
     - SSN → `[SSN_N]`.
     - Account/MRN (9+ digit runs, NPI, ICD-10) → `[ID_N]`.
     - Phone, email → `[CONTACT_N]`.
   - Transformed text is written to the OS clipboard (`navigator.clipboard.writeText(...)`). Original selection is **never** placed back on the clipboard. Original DOM is unchanged.
   - A toast: "Sanitised version copied. Paste as usual."
3. Fire-and-forget telemetry: `POST /v1/clinic/shadow-ai/paste-blocked` with `action: 'sanitize_used'` (no content, no match details).

### 6.8.9.b Out of scope (v1.0)

- ML-based named-entity recognition. Regex + capitalisation heuristic only.
- Image / PDF sanitisation.
- Backend audit of the sanitised payload — by design, the payload never leaves the device.

**In scope** (added per adversarial review HEALTH-2): Spanish translation of the toast string at v1.0 launch.

### 6.8.9.c Acceptance criteria

- Selected text never touches `chrome.runtime.sendMessage`, `fetch`, or any non-clipboard `navigator.*` API. Verified by static read of `content.js` and a CI lint.
- Sanitised clipboard write happens; original DOM selection unchanged.
- **Eval gate (rewritten per adversarial review HEALTH-7):** zero leakage of *structured* identifier categories (SSN, DOB, NPI, MRN, ICD-10, ZIP, IP, insurance ID, email, phone) in sanitised output. Name / address coverage is **not** gated — the toast disclaims it.
- Idempotency: pressing the context menu twice on the same selection produces identical output.
- Toast copy (English + Spanish, locked): **"Sanitised — but names and addresses are NOT automatically detected. Review the text before pasting."** (Not the softer "We replaced N identifiers" copy from the original draft.)

---

## 10.2 PHI handling (rewrite)

Replaces `docs/PRD.md` §10.2 (line 919). New posture is **prevention at the keyboard**, with the prior server-side guarantees preserved as a second layer.

### 10.2.a Defence layers (in execution order — innermost first)

1. **Keyboard layer (NEW).** Extension content script intercepts the paste event before any AI tab DOM receives it (§6.8.7). The Sanitize action (§6.8.9) is the user-initiated complement.
2. **Server-side PHI scrub.** `policy_engine/services/phi_text_check.py:26-58` continues to run on `ClinicAiTool.notes` and other free-text fields. **Unchanged.**
3. **Anonymised PDF rollups.** `policy_engine/services/clinic_pdf_report.py:75-158` — aggregated counts only, no patient rows. **Unchanged.**
4. **Tenant isolation.** `TenantContextMiddleware` (`docs/PRD.md` §10.2 bullet 4). **Unchanged.**
5. **At-rest encryption.** `services/encryption.py`. **Unchanged.**

### 10.2.b What gets transmitted from the extension

Whitelist (the **only** fields ever sent to the server):

| Field | Where | Why |
|---|---|---|
| `host` | `POST /v1/clinic/shadow-ai/observations` and `POST /v1/clinic/shadow-ai/paste-blocked` | Tool identification |
| `tool_fingerprint` | both | Tool classification for the alert translator |
| `action` | `/paste-blocked` only | `blocked` / `allowed` / `override` / `sanitize_used` |
| `severity` | `/observations` only | Existing alert ranking |
| `user_agent` (≤ 120 chars, trimmed per GDPR Art. 5(c)) | both | Support diagnostics |
| `extension_version` | both | Compatibility |

Removed from the payload (vs. `docs/PRD.md` §5.4):

- `page_url_hash` — see Plan workstream R1. The field provides no value the hardcoded domain list does not provide and adds a tenant-scoped column with a SHA-256 footprint.

### 10.2.c HIPAA "Minimum Necessary" (45 CFR §164.502(b))

The keyboard layer **is** the Minimum Necessary control for clinic tiers: it prevents data going to a third-party processor that has no business need for it (and, for vendors with `model_training_status='trains_on_customer_data'`, no Business Associate posture even if a BAA exists, because the BAA cannot lawfully permit unbounded redistribution).

### 10.2.d Acceptance criteria

- All five layers above are independently verified (test per layer).
- Layer 1 (keyboard) fails closed — block is locally evaluated.
- Layer 3 (PDF) static-read test asserts no patient identifiers in rendered HTML.
- Sales-facing claim "PHI never leaves the device on supported AI tools" is mechanically true for the §5.4.3 allowlist; explicitly **not** claimed for tools outside the allowlist (this gap is the v1.1 telemetry-fallback story).

---

## Cross-references

- v1 PRD baseline: `docs/PRD.md` @ working draft (untracked) on `fix/security-and-logic-pass-1`.
- Construction plan: `plans/clinical-shield-v1.md` — phase-by-phase execution of A1, R1, R2, A2, A3, and the K1 re-affirmation.
- HIPAA Minimum Necessary: 45 CFR §164.502(b).
- HIPAA BAA: 45 CFR §164.504(e). Vendors who train on customer data cannot be brought into compliance via BAA wording alone — the **technical** prevention in §6.8.7 is the actual control.

---

*End of PRD v1.0 reframe.*
