const KEYS = {
  TOKEN: 'sentinel_extension_token',
  ENDPOINT: 'sentinel_endpoint',
};

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
  await chrome.storage.local.set({
    [KEYS.TOKEN]: token,
    [KEYS.ENDPOINT]: endpoint,
  });
  const ok = document.getElementById('ok');
  ok.style.display = 'block';
  setTimeout(() => { ok.style.display = 'none'; }, 1500);
}

document.getElementById('save').addEventListener('click', save);
load();
