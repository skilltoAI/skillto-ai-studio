/* Observe only tabs explicitly armed by the user; never capture cookies/headers. */
importScripts('connection.js');
importScripts('browser-download.js');
let connecting;
async function ensureWorkbench() {
  if (connecting) return connecting;
  connecting = (async () => {
    const previous = await chrome.storage.local.get(['endpoint', 'token']);
    const endpoint = await findWorkbench(previous.endpoint);
    const health = await (await fetch(`${endpoint}/api/workbench/health`)).json();
    const activeBrowserJobs = Object.keys(await chrome.storage.session.get(null)).some(key => key.startsWith('browser-download:'));
    if (!activeBrowserJobs && health.extensionVersion && health.extensionVersion !== chrome.runtime.getManifest().version) {
      chrome.runtime.reload();
      throw Error('插件正在自动更新，请再次点击图标');
    }
    if (previous.endpoint === endpoint && previous.token) {
      const check = await fetch(`${endpoint}/api/workbench/records`, {headers: {Authorization: `Bearer ${previous.token}`}, signal: AbortSignal.timeout(4000)});
      if (check.ok) return previous;
    }
    // A same-origin content script reads the existing pairing route. The server
    // continues to reject extension-origin/cross-site attempts to read its token.
    const paired = new Promise((resolve, reject) => {
      const timer = setTimeout(() => { chrome.storage.onChanged.removeListener(changed); reject(Error('自动连接未完成，请打开本地工作台后再点击插件')); }, 12000);
      function changed(changes, area) {
        if (area !== 'local' || (!changes.token && !changes.endpoint)) return;
        chrome.storage.local.get(['endpoint', 'token']).then(value => {
          if (value.endpoint === endpoint && value.token) {
            clearTimeout(timer); chrome.storage.onChanged.removeListener(changed); resolve(value);
          }
        });
      }
      chrome.storage.onChanged.addListener(changed);
    });
    const page = await chrome.tabs.create({url: `${endpoint}/breakdowns#extension-connect`, active: false});
    try { return await paired; }
    finally { await chrome.tabs.remove(page.id).catch(() => {}); }
  })();
  try { return await connecting; } finally { connecting = null; }
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (message?.type === 'workbench-connect') {
    const origin = workbenchOrigin(sender.url);
    if (sender.frameId !== 0 || !origin || message.endpoint !== origin || typeof message.token !== 'string' || !/^[A-Za-z0-9_-]{32,128}$/.test(message.token)) {
      reply({ok: false}); return;
    }
    // Only our loopback content script can originate this message.
    chrome.storage.local.set({endpoint: origin, token: message.token}).then(() => reply({ok: true}));
    return true;
  }
  if (message?.type === 'workbench-config' && sender.url?.startsWith(chrome.runtime.getURL('popup.html'))) {
    ensureWorkbench().then(config => { resumeBrowserImports().catch(() => {}); reply({ok: true, config}); }, () => reply({ok: false, error: '本地工作台未连接，请先启动 Skillto-AI-Studio，再点击重试'}));
    return true;
  }
  if (message?.type === 'browser-download' && sender.url?.startsWith(chrome.runtime.getURL('popup.html'))) {
    startBrowserDownload(message).then(record => reply({ok: true, record}), error => reply({ok: false, error: error.message}));
    return true;
  }
});
chrome.runtime.onInstalled.addListener(() => { ensureWorkbench().catch(() => {}); });
chrome.runtime.onStartup.addListener(() => { ensureWorkbench().catch(() => {}); });
const key = id => `capture:${id}`;
const serial = new Map();
function enqueue(id, task) {
  const next = (serial.get(id) || Promise.resolve()).then(task).catch(() => {});
  serial.set(id, next);
  next.finally(() => { if (serial.get(id) === next) serial.delete(id); });
}
chrome.webRequest.onHeadersReceived.addListener(details => {
  if (details.tabId < 0) return;
  const mime = (details.responseHeaders || []).find(h => h.name.toLowerCase() === 'content-type')?.value || '';
  if (!/\.(mp4|m3u8|mpd|webm)(?:[?#]|$)/i.test(details.url) && !/(video\/mp4|video\/webm|mpegurl|dash\+xml)/i.test(mime)) return;
  enqueue(details.tabId, async () => {
    const name = key(details.tabId), state = (await chrome.storage.session.get(name))[name];
    if (!state?.armed) return;
    state.resources = [...new Set([...(state.resources || []), details.url])].slice(-60);
    const header = name => (details.responseHeaders || []).find(item => item.name.toLowerCase() === name)?.value || '';
    const total = /\/(\d+)$/.exec(header('content-range'))?.[1];
    const bytes = Number(total || (details.statusCode === 200 ? header('content-length') : 0));
    state.metadata = Object.fromEntries(state.resources.map(url => [url, state.metadata?.[url] || {}]));
    state.metadata[details.url] = {mime, bytes: Number.isSafeInteger(bytes) && bytes > 0 ? bytes : null};
    await chrome.storage.session.set({[name]: state});
  });
}, {urls: ['http://*/*', 'https://*/*']}, ['responseHeaders']);
chrome.tabs.onRemoved.addListener(id => enqueue(id, () => chrome.storage.session.remove(key(id))));
chrome.tabs.onUpdated.addListener((id, change) => {
  if (change.status === 'loading') enqueue(id, async () => {
    const name = key(id), state = (await chrome.storage.session.get(name))[name];
    if (state) await chrome.storage.session.set({[name]: {...state, resources: [], metadata: {}}});
  });
});
