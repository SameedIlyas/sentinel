/* Sentinel Clinic — Shadow AI Watcher (background service worker)
 *
 * Listens for outbound requests to a curated list of public AI tool
 * domains and forwards a *minimal* observation to the Sentinel backend:
 *   { host, tool_fingerprint, severity, page_url_hash, user_agent, extension_version }
 *
 * No URL paths or query strings are transmitted.  No patient data ever
 * leaves the device.  The page URL is hashed (SHA-256, truncated) before
 * sending so support can correlate repeats without seeing the URL itself.
 */

const STORAGE_KEYS = {
  TOKEN: 'sentinel_extension_token',
  ENDPOINT: 'sentinel_endpoint',
};

// Domain → fingerprint label.  Curated list, stable across the install.
const FINGERPRINTS = {
  'chatgpt.com':       { tool: 'chatgpt',    severity: 'high'    },
  'chat.openai.com':   { tool: 'chatgpt',    severity: 'high'    },
  'claude.ai':         { tool: 'claude_web', severity: 'high'    },
  'gemini.google.com': { tool: 'gemini_web', severity: 'high'    },
  'bard.google.com':   { tool: 'gemini_web', severity: 'high'    },
  'copilot.microsoft.com': { tool: 'copilot_web', severity: 'medium' },
  'perplexity.ai':     { tool: 'perplexity', severity: 'medium'  },
  'poe.com':           { tool: 'poe',        severity: 'medium'  },
  'meta.ai':           { tool: 'meta_ai',    severity: 'medium'  },
  'character.ai':      { tool: 'character_ai', severity: 'medium' },
  'huggingface.co':    { tool: 'huggingface', severity: 'low'    },
};

const VERSION = chrome.runtime.getManifest().version;

async function sha256Hex(text) {
  const buf = new TextEncoder().encode(text);
  const hash = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
    .slice(0, 32);
}

async function getConfig() {
  // chrome.storage.local is per-installation; chrome.storage.sync replicates
  // to every Chrome profile signed into the same Google account, which
  // would put the clinic's bearer token onto staff personal devices —
  // a HIPAA breach surface.  Keep token + endpoint local-only.
  const data = await chrome.storage.local.get([STORAGE_KEYS.TOKEN, STORAGE_KEYS.ENDPOINT]);
  return {
    token: data[STORAGE_KEYS.TOKEN] || '',
    endpoint: data[STORAGE_KEYS.ENDPOINT] || 'http://localhost:8000',
  };
}

const recentlySent = new Map(); // host → ts; debounce
const DEBOUNCE_MS = 60_000;

async function reportObservation(host, fingerprint, severity, pageUrl) {
  const { token, endpoint } = await getConfig();
  if (!token) return;

  const now = Date.now();
  if ((recentlySent.get(host) ?? 0) > now - DEBOUNCE_MS) return;
  recentlySent.set(host, now);

  const pageUrlHash = pageUrl ? await sha256Hex(pageUrl) : null;

  try {
    await fetch(`${endpoint}/v1/clinic/shadow-ai/observations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Clinic-Extension-Token': token,
      },
      body: JSON.stringify({
        host,
        tool_fingerprint: fingerprint,
        page_url_hash: pageUrlHash,
        severity,
        user_agent: navigator.userAgent.slice(0, 500),
        extension_version: VERSION,
      }),
    });
  } catch (err) {
    // Network failures are non-fatal — the extension is best-effort.
    console.debug('[sentinel-clinic] report failed:', err);
  }
}

chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    try {
      const url = new URL(details.url);
      const host = url.hostname;
      const match = FINGERPRINTS[host] || FINGERPRINTS[host.split('.').slice(-2).join('.')];
      if (!match) return;
      // Only act on top-level navigations or main_frame loads to avoid noise.
      if (details.type !== 'main_frame' && details.type !== 'xmlhttprequest') return;
      reportObservation(host, match.tool, match.severity, details.url);
    } catch (_e) {
      // Swallow — never break the user's network request.
    }
  },
  { urls: ['<all_urls>'] },
  []
);

// Re-emit a heartbeat on install so the dashboard sees the device is alive.
chrome.runtime.onInstalled.addListener(async () => {
  console.log('[sentinel-clinic] installed v' + VERSION);
});
