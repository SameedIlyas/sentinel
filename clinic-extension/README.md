# Sentinel Clinic — Shadow AI Watcher (browser extension)

A lightweight Chrome / Edge extension (Manifest V3) that watches outbound
requests on clinic devices for known public-AI domains and reports
DNS-only observations to the Sentinel Policy Engine.

**No patient information ever leaves the device.** Only:
- the destination domain (e.g., `chatgpt.com`)
- the tool fingerprint label (e.g., `chatgpt`)
- a SHA-256 hash of the page URL (truncated to 32 hex chars)
- the user-agent string
- the extension version

The page URL itself, query parameters, the body of any request, the user's
input, and any response data are **never** transmitted.

## Install (developer mode)

1. In Chrome / Edge, open `chrome://extensions`.
2. Enable "Developer mode" (top right).
3. Click "Load unpacked" and select the `clinic-extension/` directory.
4. Click the extension's "Details" → "Extension options".
5. Paste the extension token from your Sentinel dashboard
   (Practice → Shadow AI watcher → Get extension token) and the Sentinel
   API endpoint (e.g., `http://localhost:8000` for dev).
6. Save.

## Distribution

For beta clinics this is shipped via an unlisted Chrome Web Store entry
or a per-clinic ZIP install. A public listing happens after the first
50 paying clinics — see `docs/CLINIC_TIER_BLUEPRINT.md` §11.

## Tracked tools

The default fingerprint set covers the most commonly-pasted-into AI tools:

| Domain | Tool | Default severity |
|---|---|---|
| chatgpt.com / chat.openai.com | chatgpt | high |
| claude.ai | claude_web | high |
| gemini.google.com / bard.google.com | gemini_web | high |
| copilot.microsoft.com | copilot_web | medium |
| perplexity.ai | perplexity | medium |
| poe.com | poe | medium |
| meta.ai | meta_ai | medium |
| character.ai | character_ai | medium |
| huggingface.co | huggingface | low |

Add more by editing the `FINGERPRINTS` object in `background.js` and
re-loading the extension.

## Privacy guarantees

- The extension reads request URLs *only* to extract the hostname.
- It never reads request bodies.
- Reporting is debounced per host (60s window) so a single ChatGPT session
  produces one observation, not hundreds.
- Network failures are silently swallowed — the extension never blocks a
  user's request.
- All settings live in `chrome.storage.sync`; nothing is sent to Google.

## Build / packaging

This is plain JavaScript — no build step. To package for the Chrome Web
Store, zip the directory:

```bash
cd clinic-extension
zip -r ../clinic-extension.zip . -x "*.md" "icons/*"
```

(Replace `icons/` with your real assets before public release.)
