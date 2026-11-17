/* SKillto.ai local UI integration. Cat Catch remains the discovery engine.
   Only selected media URLs and Referer/Origin are used; credentials stay in Chrome. */
importScripts('studio-connection.js');
let studioConnecting;
const studioReconciling = new Map();
function studioUI(sender) {
  return sender.id === chrome.runtime.id && ['popup.html', 'studio-editor.html'].some(path => sender.url?.startsWith(chrome.runtime.getURL(path)));
}
async function studioConfig() {
  if (studioConnecting) return studioConnecting;
  studioConnecting = (async () => {
    const previous = await chrome.storage.local.get(['studioEndpoint', 'studioToken']);
    const endpoint = await findWorkbench(previous.studioEndpoint);
    if (previous.studioEndpoint === endpoint && previous.studioToken) {
      const check = await fetch(`${endpoint}/api/workbench/records`, {headers: {Authorization: `Bearer ${previous.studioToken}`}, signal: AbortSignal.timeout(4000)});
      if (check.ok) return {endpoint, token: previous.studioToken};
    }
    let listener, timeout;
    const paired = new Promise((resolve, reject) => {
      listener = async (changes, area) => {
        if (area !== 'local' || (!changes.studioToken && !changes.studioEndpoint)) return;
        const value = await chrome.storage.local.get(['studioEndpoint', 'studioToken']);
        if (value.studioEndpoint === endpoint && value.studioToken) resolve({endpoint, token: value.studioToken});
      };
      chrome.storage.onChanged.addListener(listener);
      timeout = setTimeout(() => reject(Error('请先启动 SKillto.ai 工作台，再重新点击下载')), 12000);
    });
    let temporary;
    try {
      const existing = (await chrome.tabs.query({})).find(tab => workbenchOrigin(tab.url) === endpoint && ['/', '/breakdowns'].includes(new URL(tab.url).pathname));
      if (existing) await chrome.scripting.executeScript({target: {tabId: existing.id}, files: ['js/studio-workspace-connect.js']});
      else temporary = await chrome.tabs.create({url: `${endpoint}/breakdowns#extension-connect`, active: false});
      return await paired;
    } finally { clearTimeout(timeout); chrome.storage.onChanged.removeListener(listener); if (temporary) await chrome.tabs.remove(temporary.id).catch(() => {}); }
  })();
  try { return await studioConnecting; } finally { studioConnecting = null; }
}
async function studioApi(config, body, query) {
  const response = await fetch(`${config.endpoint}${query || '/api/workbench/records'}`, {
    method: body ? 'POST' : 'GET', headers: {'Content-Type': 'application/json', Authorization: `Bearer ${config.token}`},
    body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(120000)});
  if (!response.ok) throw Error(response.status === 404 ? '请更新并重启本机工作台，再导出片段' : '本机工作台暂未能处理此任务');
  return response.json();
}
async function studioOpenWorkspace(config, id) {
  const key = `studio:opened:${id}`;
  if ((await chrome.storage.session.get(key))[key]) return;
  const tabs = (await chrome.tabs.query({})).filter(tab => workbenchOrigin(tab.url) === config.endpoint);
  const existing = tabs.find(tab => new URL(tab.url).pathname === '/breakdowns') || tabs.find(tab => new URL(tab.url).pathname === '/');
  const url = `${config.endpoint}/breakdowns?id=${encodeURIComponent(id)}`;
  const tab = existing ? await chrome.tabs.update(existing.id, {url, active: true}) : await chrome.tabs.create({url, active: true});
  await chrome.storage.session.set({[key]: tab.id});
  await chrome.windows.update(tab.windowId, {focused: true}).catch(() => {});
}
async function studioComplete(config, job) {
  const key = `complete:${job.id}`;
  if (studioReconciling.has(key)) return studioReconciling.get(key);
  const complete = studioCompleteOnce(config, job);
  studioReconciling.set(key, complete);
  try { return await complete; } finally { studioReconciling.delete(key); }
}
async function studioCompleteOnce(config, job) {
  if (job.destination === 'workbench') return studioOpenWorkspace(config, job.id);
  const key = `studio:exported:${job.id}`;
  if (!(await chrome.storage.session.get(key))[key]) {
    const id = await chrome.downloads.download({url: `${config.endpoint}/api/workbench/export-media?id=${encodeURIComponent(job.id)}`,
      headers: [{name: 'Authorization', value: `Bearer ${config.token}`}], filename: job.outputName, saveAs: false});
    await chrome.storage.session.set({[key]: id});
  }
}
async function studioReconcileUpload(key) {
  const job = (await chrome.storage.session.get(key))[key];
  if (!job || job.phase !== 'processing') return;
  const config = await studioConfig();
  const result = await studioApi(config, null, `/api/workbench/transfers?id=${encodeURIComponent(job.id)}&destination=${job.destination}`);
  if (result.status === 'ready') await studioComplete(config, job);
  if (['ready', 'failed'].includes(result.status)) { await chrome.storage.session.remove(key); await studioCleanupDraft(job.draftId); }
}
async function studioDraft(id) {
  if (typeof id !== 'string' || !/^[a-f0-9-]{36}$/.test(id)) throw Error('视频选择无效');
  const value = (await chrome.storage.session.get(`studio:draft:${id}`))[`studio:draft:${id}`];
  if (!value) throw Error('视频选择已失效，请重新选择');
  return value;
}
async function studioCreateDraft(message) {
  const item = cacheData[message.tabId]?.find(value => value.requestId === message.requestId);
  if (!item || !/^https?:/.test(item.url || '')) throw Error('资源已失效，请刷新列表后重试');
  const source = await chrome.tabs.get(message.tabId);
  const id = crypto.randomUUID();
  const ruleId = 1900000000 + crypto.getRandomValues(new Uint32Array(1))[0] % 1000000;
  const headers = [];
  const referer = item.requestHeaders?.referer || source.url;
  if (/^https?:/.test(referer || '')) headers.push({header: 'referer', operation: 'set', value: referer});
  if (/^https?:/.test(item.requestHeaders?.origin || '')) headers.push({header: 'origin', operation: 'set', value: item.requestHeaders.origin});
  if (headers.length) await chrome.declarativeNetRequest.updateSessionRules({removeRuleIds: [ruleId], addRules: [{id: ruleId, priority: 1,
    action: {type: 'modifyHeaders', requestHeaders: headers},
    condition: {urlFilter: `|${item.url}|`, initiatorDomains: [chrome.runtime.id], resourceTypes: ['media', 'xmlhttprequest', 'other']}}]});
  const draft = {id, ruleId, url: item.url, title: item.title || source.title || '网页视频', name: item.name || '网页视频',
    size: item.size || null, type: item.type || '', ext: item.ext || '', sourceUrl: source.url,
    destination: message.destination === 'download' ? 'download' : 'workbench', createdAt: Date.now(),
    manifest: /mpegurl|dash\+xml/i.test(item.type || '') || /^(m3u8|mpd)$/i.test(item.ext || '')};
  await chrome.storage.session.set({[`studio:draft:${id}`]: draft});
  const tab = await chrome.tabs.create({url: chrome.runtime.getURL(`studio-editor.html?draft=${id}`)});
  await chrome.storage.session.set({[`studio:editor:${tab.id}`]: id});
  return {ok: true, draft: id};
}
function studioFilename(draft, clipped = false) {
  let name = String(draft.name || draft.title || 'video').replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_').slice(0, 150);
  name = name.replace(/\.(mp4|webm|mov|m4v)$/i, '');
  return `${name}${clipped ? '_片段' : ''}.${clipped ? 'mp4' : draft.ext?.toLowerCase() === 'webm' ? 'webm' : 'mp4'}`;
}
async function studioSave(message, editorTab) {
  if (message.authorized !== true) throw Error('请先确认你有权保存此视频');
  if (!['download', 'workbench'].includes(message.destination)) throw Error('下载目标无效');
  const draft = await studioDraft(message.draft);
  if (draft.manifest) throw Error('当前片段导出暂不支持流媒体清单，请选择普通视频文件');
  const clipped = message.clipStart !== undefined || message.clipEnd !== undefined;
  if (clipped && (!Number.isFinite(message.clipStart) || !Number.isFinite(message.clipEnd)
      || !(0 <= message.clipStart && message.clipStart < message.clipEnd) || message.clipEnd > message.duration + 0.01)) throw Error('请检查片段开始和结束时间');
  if (!clipped && message.destination === 'download') {
    await chrome.downloads.download({url: draft.url, filename: studioFilename(draft), saveAs: false});
    return {ok: true};
  }
  const config = await studioConfig();
  const health = await (await fetch(`${config.endpoint}/api/workbench/health`, {signal: AbortSignal.timeout(4000)})).json();
  if (!health.features?.browserUpload) throw Error('请更新并重启本机工作台后同步视频；尚未提交任何任务');
  if (clipped) {
    if (!health.features?.clipExports || !health.features?.independentExports) throw Error('请更新并重启本机工作台后使用片段导出；尚未提交任何下载任务');
  }
  const item = await studioApi(config, {action: 'browser-start', url: draft.url, sourceUrl: draft.sourceUrl, title: draft.title,
    authorized: true, destination: message.destination, duration: message.duration, clipStart: message.clipStart, clipEnd: message.clipEnd});
  const job = {id: item.id, destination: message.destination, endpoint: config.endpoint, draftId: draft.id, editorTab,
    outputName: studioFilename(draft, clipped), phase: 'receiving'};
  await chrome.storage.session.set({[`studio:upload:${job.id}`]: job});
  await chrome.alarms.create('studio:transfers', {periodInMinutes: 1});
  return {ok: true, job: {id: job.id, destination: job.destination}, upload: config};
}
async function studioReconcile(downloadId) {
  if (studioReconciling.has(downloadId)) return studioReconciling.get(downloadId);
  const task = (async () => {
    const key = `studio:download:${downloadId}`, job = (await chrome.storage.session.get(key))[key];
    if (!job) return;
    const config = await studioConfig();
    if (config.endpoint !== job.endpoint) return;
    if (job.phase === 'receiving') {
      const [download] = await chrome.downloads.search({id: downloadId});
      if (!download || download.byExtensionId !== chrome.runtime.id || !['complete', 'interrupted'].includes(download.state)) return;
      const result = await studioApi(config, {action: 'browser-finish', id: job.id, destination: job.destination,
        filename: download.state === 'complete' ? download.filename : undefined, failed: download.state === 'interrupted'});
      if (result.status === 'failed') { await chrome.storage.session.remove(key); return; }
      job.phase = 'processing'; await chrome.storage.session.set({[key]: job});
    }
    const result = await studioApi(config, null, `/api/workbench/transfers?id=${encodeURIComponent(job.id)}&destination=${job.destination}`);
    if (result.status === 'failed') { await chrome.storage.session.remove(key); return; }
    if (result.status !== 'ready') return;
    await studioComplete(config, job);
    await chrome.storage.session.remove(key);
    await studioCleanupDraft(job.draftId);
  })();
  studioReconciling.set(downloadId, task);
  try { return await task; } finally { studioReconciling.delete(downloadId); }
}
async function studioReconcileAll() {
  const values = await chrome.storage.session.get(null);
  await Promise.allSettled(Object.keys(values).filter(key => key.startsWith('studio:download:')).map(key => studioReconcile(Number(key.split(':')[2]))));
  await Promise.allSettled(Object.keys(values).filter(key => key.startsWith('studio:upload:')).map(studioReconcileUpload));
}
chrome.downloads.onChanged.addListener(change => { studioReconcile(change.id).catch(() => {}); });
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === 'studio:transfers') studioReconcileAll().catch(() => {}); });
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (!message.type?.startsWith('studio:')) return;
  (async () => {
    if (message.type === 'studio:pair') {
      const origin = workbenchOrigin(sender.url);
      if (sender.frameId !== 0 || !origin || origin !== message.endpoint || !/^[A-Za-z0-9_-]{32,128}$/.test(message.token || '')) throw Error('连接来源无效');
      await chrome.storage.local.set({studioEndpoint: origin, studioToken: message.token}); return {ok: true};
    }
    if (!studioUI(sender)) throw Error('操作来源无效');
    if (message.type === 'studio:draft') return studioCreateDraft(message);
    if (message.type === 'studio:get-draft') return {ok: true, draft: await studioDraft(message.draft)};
    if (message.type === 'studio:save') return studioSave(message, sender.tab?.id);
    if (message.type === 'studio:upload-finished') {
      const key = `studio:upload:${message.id}`, job = (await chrome.storage.session.get(key))[key];
      if (!job || job.editorTab !== sender.tab?.id) throw Error('视频传输任务无效');
      if (message.failed) {
        await studioApi(await studioConfig(), {action: 'browser-finish', id: job.id, destination: job.destination, failed: true});
        await chrome.storage.session.remove(key);
      } else { job.phase = 'processing'; await chrome.storage.session.set({[key]: job}); await studioReconcileUpload(key); }
      return {ok: true};
    }
    if (message.type === 'studio:status') {
      await studioReconcileAll();
      const config = await studioConfig();
      const result = await studioApi(config, null, `/api/workbench/transfers?id=${encodeURIComponent(message.job.id)}&destination=${message.job.destination}`);
      result.exportSaved = !!(await chrome.storage.session.get(`studio:exported:${message.job.id}`))[`studio:exported:${message.job.id}`];
      return {ok: true, result, endpoint: config.endpoint};
    }
    throw Error('操作无效');
  })().then(reply, error => reply({ok: false, error: ['Failed to fetch', 'fetch failed'].includes(error.message) ? '请先启动本机工作台，片段导出需要本机处理' : error.message}));
  return true;
});
chrome.runtime.onInstalled.addListener(async details => {
  if (details.reason === 'update') {
    const previous = await chrome.storage.local.get('studioUiVersion');
    if (previous.studioUiVersion !== '1') await chrome.tabs.create({url: chrome.runtime.getURL('install.html')});
  }
  await chrome.storage.local.set({studioUiVersion: '1', featAutoDownTabId: []});
  await chrome.storage.sync.set({contextMenus: false});
  await chrome.contextMenus.removeAll();
});
async function studioCleanupDraft(id) {
  const values = await chrome.storage.session.get(null);
  if (Object.entries(values).some(([key, value]) => key.startsWith('studio:editor:') && value === id
    || (key.startsWith('studio:download:') || key.startsWith('studio:upload:')) && value.draftId === id)) return;
  const draft = values[`studio:draft:${id}`];
  if (draft?.ruleId) await chrome.declarativeNetRequest.updateSessionRules({removeRuleIds: [draft.ruleId]});
  await chrome.storage.session.remove(`studio:draft:${id}`);
}
chrome.tabs.onRemoved.addListener(async tabId => {
  const uploads = await chrome.storage.session.get(null);
  for (const [key, job] of Object.entries(uploads)) {
    if (!key.startsWith('studio:upload:') || job.editorTab !== tabId || job.phase !== 'receiving') continue;
    try { await studioApi(await studioConfig(), {action: 'browser-finish', id: job.id, destination: job.destination, failed: true}); } catch {}
    await chrome.storage.session.remove(key);
  }
  const key = `studio:editor:${tabId}`, id = (await chrome.storage.session.get(key))[key];
  if (!id) return;
  await chrome.storage.session.remove(key);
  await studioCleanupDraft(id);
});
