# Chrome Web Store / Edge Add-ons — Policy Pre-Submission Justification

> **Purpose:** Pre-submission discussion document for Chrome Web Store developer support and Microsoft Edge Add-ons store review. Establishes the policy basis for our paste-event interception and clipboard-write features before extension version 0.3.0 is uploaded for review.
>
> **Mitigation of risk register entry RR-15** (`plans/clinical-shield-v1.md`). Drafted 2026-05-17.
>
> **Intended workflow:** Maintainer sends this document via the Chrome Web Store developer support channel **before** the 0.3.0 submission is queued. Edge Add-ons publisher likewise; same text applies.
>
> **What this document is not:** a technical privacy policy (that lives in the extension's required Privacy practices section) or a HIPAA Business Associate Agreement (which exists between Sentinel and the clinic, not between Sentinel and Google/Microsoft).

---

## Extension at a glance

| Field | Value |
|---|---|
| Extension name (current) | Sentinel Clinic — Shadow AI Watcher |
| Extension name (proposed v0.3.0 rename) | **Sentinel Clinical Shield — HIPAA Paste Guard** |
| Current manifest version | 0.1.0 |
| Proposed | 0.3.0 (this submission rolls up R1 domain narrowing + A2 paste blocker + A3 sanitize action) |
| Maintainer | Sentinel AI (devotrex / SameedIlyas) |
| Single purpose statement | **Prevent paste of HIPAA-regulated patient identifiers from US-clinic-staff browsers into a curated allowlist of consumer LLM tools, where such pasting constitutes a HIPAA breach.** |
| Target audience | US healthcare clinics with 1–50 providers, deployed by the clinic's Practice Owner / Practice Manager (not end-user-installed). |
| Distribution | Public Chrome Web Store listing + corporate-policy enterprise install fallback if public listing is unavailable. |

## Permission delta vs. installed-base v0.1.0

| Permission | v0.1.0 | v0.3.0 | Reason |
|---|---|---|---|
| `storage` | yes | yes | Token + endpoint persistence (existing). |
| `webRequest` | yes | **removed** | DNS-only observation pipeline retired in workstream R1. The new paste-blocker is event-driven via content scripts, not request-driven. |
| `tabs` | yes | yes | Detect navigation to allowlisted AI domains. |
| `scripting` | no | **added** | Inject `content.js` paste-event interceptor on the host allowlist below. |
| `contextMenus` | no | **added** | Right-click "Sanitize with Sentinel" action on selected text (workstream A3). |
| `clipboardWrite` | no | **added** | Write sanitized text to the OS clipboard. **`clipboardRead` is deliberately not requested** — we read pasted text from the `paste` DOM event's `clipboardData`, never from a global clipboard read. |
| `host_permissions` | `<all_urls>` | **narrowed** to an explicit allowlist | See "Host allowlist" below. |

**Net effect:** removes the broadest existing permission (`<all_urls>` host access) in favour of an explicit ~50-domain allowlist; removes `webRequest`; adds three narrowly-scoped capability permissions (`scripting`, `contextMenus`, `clipboardWrite`). The total surface visible to the extension shrinks.

## Host allowlist (explicit, hardcoded in manifest)

Consumer LLM and chat-AI tools where unredacted paste of patient information constitutes a HIPAA breach. The list ships with the extension and is updated only via signed extension releases (no remote configuration of the allowlist).

```
chatgpt.com, chat.openai.com
claude.ai
gemini.google.com, bard.google.com
chat.deepseek.com
perplexity.ai, www.perplexity.ai
app.jasper.ai
copilot.microsoft.com
pi.ai, heypi.com
chat.mistral.ai
character.ai
poe.com
meta.ai
huggingface.co, hf.co
you.com
phind.com
notebooklm.google.com
chat.cohere.com
together.ai
replicate.com
```

(Final list under review by our healthcare specialist — final count ≤ 60 hosts.)

The extension has **no host permission outside this list**. It cannot read, observe, or interact with any other page.

## What the extension does on those hosts

On every tab whose host matches the allowlist, after the tab finishes loading:

1. A content script is injected (with `all_frames: true` to cover iframe-hosted input fields, e.g., ChatGPT's chat composer).
2. The content script attaches a `paste` event listener (`capture: true`).
3. When a paste occurs, the listener reads `event.clipboardData.getData('text')` (the text the user is about to paste) and runs a deterministic, **local-only** regex set against it. The regex set matches **structured HIPAA Safe Harbor identifiers**: US Social Security number, ZIP code, phone, email, US date of birth, ICD-10 short code, US National Provider Identifier (Luhn-validated per CMS 73 FR 36459), insurance-member-ID shape, IPv4/IPv6, 9+ digit MRN/account.
4. If any pattern matches, the listener calls `event.preventDefault()` + `event.stopImmediatePropagation()` to prevent the paste reaching the page input, attempts to clear the OS clipboard (via `document.execCommand('copy')` on an empty hidden textarea, then async `navigator.clipboard.writeText('')` as fallback), and displays a Shadow-DOM modal asking the user to confirm or cancel.
5. The user can choose **Cancel** (default) or **Confirm No-PHI and paste anyway**. The latter is audit-logged to the clinic's Sentinel dashboard.
6. Regardless of the user's choice, a fire-and-forget POST is sent to the clinic's Sentinel backend with the host, tool fingerprint, action (`blocked`/`allowed`/`override`), the *names* of the regex categories that matched (e.g., `['ssn', 'dob_us']` — category names only, not the matched text), the truncated user agent, and the extension version. **The paste contents never leave the user's browser.**

For the right-click "Sanitize with Sentinel" action:

1. User selects text and chooses the menu item.
2. The content script reads the selection (DOM-local), runs the same regex set, replaces matched identifiers with `[Patient_Name_N]`, `[DOB_N]`, etc., and writes the **sanitized** text to the OS clipboard via the user-gesture-triggered Clipboard API. The original DOM selection is unchanged.
3. A toast appears: *"Sanitised — but names and addresses are NOT automatically detected. Review the text before pasting."*
4. Same fire-and-forget telemetry, this time with `action: 'sanitize_used'`.

## What the extension does NOT do

- **Does not read the clipboard globally.** No `clipboardRead` permission requested. The paste blocker only sees text the user voluntarily pasted into an allowlisted AI tab; the sanitize action only sees text the user explicitly selected.
- **Does not log keystrokes.** No `keydown` / `keyup` listeners. The single DOM event we listen to is `paste`.
- **Does not transmit paste contents.** Network payloads contain category names and metadata only.
- **Does not modify the AI tab's output.** No content-script reads of the AI tool's response; no DOM manipulation outside our own Shadow-DOM modal and the context menu.
- **Does not run outside the allowlist.** Hosts not on the list see no content script and no behaviour.
- **Does not auto-update its allowlist.** New hosts require a signed extension release reviewed by the store.
- **Does not use remote-hosted code.** No `eval`, no dynamic `import()` from a non-extension URL. All code ships in the bundled extension package.

## Compliance posture

**HIPAA Privacy Rule, 45 CFR §164.502(b) — "Minimum Necessary"** requires Covered Entities (clinics) to limit PHI disclosure to the minimum necessary for the disclosure's purpose. Consumer LLM vendors that train on customer prompts cannot be brought into the "Minimum Necessary" scope by a BAA alone, because BAAs cannot lawfully authorise unbounded redistribution. This extension is a **technical safeguard** under 45 CFR §164.530(c)(1) that implements Minimum Necessary at the point of paste.

**HIPAA Security Rule, 45 CFR §164.312(b) — audit controls.** The extension's fire-and-forget telemetry (category names, not content) provides the audit trail required for a Covered Entity to demonstrate the safeguard is operational.

We are not asking Google or Microsoft to evaluate the HIPAA claim. We're providing the regulatory framing so the review team understands **why** the extension intercepts paste events at all — it is the operative technical control for the customer's compliance obligation, not a feature in search of a use.

## Single-purpose statement

The Chrome Web Store Program Policies require an extension to have a single, narrow purpose. This extension's single purpose is:

> **Detecting and blocking paste of structured HIPAA-regulated patient identifiers from a clinical staff member's browser into a curated allowlist of consumer LLM web applications.**

The right-click "Sanitize with Sentinel" action is part of this same purpose: it is the user-initiated complement to the automatic paste blocker, allowing staff to deliberately scrub structured identifiers before sharing text with a colleague or an approved AI tool.

The DNS-only observation pipeline retired in v0.3.0 (`webRequest` permission removal) was a separate purpose; the new manifest is **narrower**.

## Policy questions we'd like a yes/no on before submitting

We're submitting this document via developer support to surface the questions that we'd rather hear about now than as a rejection in two weeks. Specifically:

1. **Does intercepting `paste` events with `preventDefault()` on a third-party origin satisfy the Chrome Web Store "Limited Use" policy** when (a) the paste contents never leave the browser, (b) the host is on a hardcoded allowlist of consumer LLM tools, (c) the user can override the block, and (d) the operator (the clinic) has informed-consent documentation in place with their staff at install time? If not, what change to the design would make it satisfy?
2. **Does the `contextMenus` + `clipboardWrite` pairing for the Sanitize action raise any specific Manifest V3 concerns** beyond standard permission justification?
3. **Is "HIPAA-compliant paste prevention" sufficiently narrow as a single-purpose statement**, or does the review team prefer a more concrete phrasing (e.g., "Block paste of nine specific identifier types on twenty named hosts")?
4. **Distribution path of last resort:** if the public store cannot accept the extension under any framing, can you confirm that **enterprise-policy install** (`ExtensionInstallForcelist` / Microsoft Edge equivalent) is a supported path for an unlisted extension that meets the same technical bar but is installed by an enterprise admin rather than the end user?

A live walkthrough or a sandbox build is available on request.

## Contact

- Maintainer (developer-account holder): SameedIlyas (Sentinel AI)
- Technical contact: see the developer-account email on file
- Compliance contact: same; HIPAA / 45 CFR citations available on request

---

### Internal note (not part of the message you send)

Before sending this document, swap out any placeholder names, update the host allowlist with the final curated list (workstream R1 deliverable), and have legal review the HIPAA framing for the specific jurisdictions you intend to ship in (US v1.0; EU later — GDPR Art. 25 makes the framing easier there). The "Distribution path of last resort" question is a hedge — if Google says no, the enterprise-policy path is a supported fallback that does not require store approval at all.

Once a response is received, record the outcome as a new entry in `plans/clinical-shield-v1.md` §Plan-mutation log under workstream A2/A3, and either green-light the 0.3.0 submission or pivot to enterprise-policy distribution.
