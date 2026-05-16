const KEYS = {
  TOKEN: 'sentinel_extension_token',
  ENDPOINT: 'sentinel_endpoint',
};

// HIGH-031 — validate the endpoint URL before persisting it to
// chrome.storage.local. background.js uses this string verbatim in fetch()
// with the X-Clinic-Extension-Token header, so an attacker who tricked a
// user into pasting javascript:/data:/file:/// or an attacker host would
// exfiltrate every observation POST (token included) on every page load.
function validateEndpoint(input) {
  if (typeof input !== 'string') {
    return { ok: false, reason: 'Endpoint must be a string' };
  }
  const trimmed = input.trim();
  if (!trimmed) {
    return { ok: false, reason: 'Endpoint is required' };
  }
  let url;
  try {
    url = new URL(trimmed);
  } catch (_e) {
    return { ok: false, reason: 'Endpoint is not a valid URL' };
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    return {
      ok: false,
      reason: 'Only http and https schemes are allowed (no javascript:, data:, file:)',
    };
  }
  if (!url.hostname) {
    return { ok: false, reason: 'Endpoint must include a hostname' };
  }
  if (url.username || url.password) {
    return {
      ok: false,
      reason: 'Endpoint must not contain embedded credentials (user:pass@host)',
    };
  }
  // Strip trailing slash so background.js can append /v1/... cleanly.
  return { ok: true, url: trimmed.replace(/\/+$/, '') };
}

async function load() {
  // storage.local — see background.js comment.  Token must not roam to
  // staff personal devices via Chrome profile sync.
  const data = await chrome.storage.local.get([KEYS.TOKEN, KEYS.ENDPOINT]);
  document.getElementById('token').value = data[KEYS.TOKEN] || '';
  document.getElementById('endpoint').value = data[KEYS.ENDPOINT] || 'http://localhost:8000';
}

async function save() {
  const token = document.getElementById('token').value.trim();
  const endpoint = document.getElementById('endpoint').value.trim();
  const ok = document.getElementById('ok');
  const err = document.getElementById('err');
  ok.style.display = 'none';
  err.style.display = 'none';

  const result = validateEndpoint(endpoint);
  if (!result.ok) {
    err.textContent = result.reason;
    err.style.display = 'block';
    return;
  }

  await chrome.storage.local.set({
    [KEYS.TOKEN]: token,
    [KEYS.ENDPOINT]: result.url,
  });
  ok.style.display = 'block';
  setTimeout(() => { ok.style.display = 'none'; }, 1500);
}

document.getElementById('save').addEventListener('click', save);
load();

if (typeof module !== 'undefined') {
  module.exports = { validateEndpoint };
}
