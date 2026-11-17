/* Browser-native progressive downloads. No cookies are extracted or exported. */
const browserImports = new Map();
async function browserApi(config, body) {
  const response = await fetch(`${config.endpoint}/api/workbench/records`, {method: 'POST',
    headers: {'Content-Type': 'application/json', Authorization: `Bearer ${config.token}`},
    body: JSON.stringify(body), signal: AbortSignal.timeout(120000)});
  if (!response.ok) throw Error('工作台未能接收浏览器下载，请检查工作台服务');
  return response.json();
}
async function finishBrowserDownload(id) {
  if (browserImports.has(id)) return browserImports.get(id);
  const task = (async () => {
    const key = `browser-download:${id}`, saved = (await chrome.storage.session.get(key))[key];
    if (!saved) return;
    const [item] = await chrome.downloads.search({id});
    if (!item || item.byExtensionId !== chrome.runtime.id) return;
    if (!['complete', 'interrupted'].includes(item.state)) return;
    const config = await chrome.storage.local.get(['endpoint', 'token']);
    if (config.endpoint !== saved.endpoint || !config.token) return;
    await browserApi(config, {action: 'browser-finish', id: saved.recordId,
      filename: item.state === 'complete' ? item.filename : undefined, failed: item.state === 'interrupted'});
    await chrome.storage.session.remove(key);
  })();
  browserImports.set(id, task);
  try { await task; } finally { browserImports.delete(id); }
}
async function startBrowserDownload(message) {
  if (message.authorized !== true) throw Error('请先确认下载授权');
  if (!await chrome.permissions.contains({permissions: ['downloads']})) throw Error('请允许 Chrome 下载权限');
  listenBrowserDownloads();
  const url = new URL(message.url);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw Error('请选择有效媒体资源');
  if (/\.(m3u8|mpd)$/i.test(url.pathname)) throw Error('此资源是流媒体清单，请使用流媒体合并下载');
  const config = await ensureWorkbench();
  const record = await browserApi(config, {action: 'browser-start', url: message.url,
    sourceUrl: message.sourceUrl, title: message.title, duration: message.duration, authorized: true});
  try {
    const id = await chrome.downloads.download({url: message.url,
      filename: `SkilltoWorkbench/${record.browserFilename}`, saveAs: false, conflictAction: 'uniquify'});
    await chrome.storage.session.set({[`browser-download:${id}`]: {recordId: record.id, endpoint: config.endpoint}});
    await chrome.storage.local.set({lastRecord: record.id});
    finishBrowserDownload(id).catch(() => {});
    return record;
  } catch {
    await browserApi(config, {action: 'browser-finish', id: record.id, failed: true});
    throw Error('Chrome 未能开始下载，请检查浏览器下载提示');
  }
}
let downloadsListening = false;
function listenBrowserDownloads() {
  if (downloadsListening || !chrome.downloads?.onChanged) return;
  chrome.downloads.onChanged.addListener(change => { finishBrowserDownload(change.id).catch(() => {}); });
  downloadsListening = true;
}
listenBrowserDownloads();
chrome.permissions.onAdded.addListener(permissions => { if (permissions.permissions?.includes('downloads')) listenBrowserDownloads(); });
async function resumeBrowserImports() {
  if (!await chrome.permissions.contains({permissions: ['downloads']})) return;
  listenBrowserDownloads();
  const keys = Object.keys(await chrome.storage.session.get(null)).filter(key => key.startsWith('browser-download:'));
  for (const key of keys) finishBrowserDownload(Number(key.split(':')[1])).catch(() => {});
}
