const $ = id => document.getElementById(id);
let sourceTab, selected, items = [], signature;
const note = text => { $('status').textContent = text; };
function size(bytes) { return bytes > 0 ? bytes < 1048576 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1048576).toFixed(1)} MB` : '大小待确认'; }
async function refresh() {
  const result = await chrome.runtime.sendMessage({Message: 'getData', tabId: sourceTab.id});
  if (result === 'error') { note('资源列表正在准备，请稍后刷新'); return; }
  items = (Array.isArray(result) ? result : []).filter(item => /^(https?):/.test(item.url || '')
    && (/video\/|mpegurl|dash\+xml/i.test(item.type || '') || /^(mp4|webm|mov|m3u8|mpd)$/i.test(item.ext || ''))).slice(-100);
  const next = JSON.stringify(items.map(item => [item.requestId, item.name, item.size]));
  if (signature === next) return;
  signature = next;
  if (!items.some(item => item.requestId === selected)) selected = items[0]?.requestId;
  $('mediaList').replaceChildren();
  for (const item of items) {
    const row = document.createElement('label'); row.className = 'media-item';
    const radio = document.createElement('input'); radio.type = 'radio'; radio.name = 'resource'; radio.value = item.requestId; radio.checked = item.requestId === selected;
    radio.onchange = () => { selected = item.requestId; };
    const content = document.createElement('div');
    const title = document.createElement('strong'); title.textContent = item.name || item.title || '页面视频';
    const detail = document.createElement('small'); detail.textContent = `${(item.ext || '视频').toUpperCase()} · ${size(item.size)} · ${new URL(item.url).hostname}`;
    const play = document.createElement('span'); play.className = 'play'; play.textContent = '▷';
    content.append(title, detail); row.append(radio, content, play); $('mediaList').append(row);
  }
  $('empty').hidden = !!items.length;
  $('download').disabled = $('workbench').disabled = !items.length;
  $('captureInfo').textContent = items.length ? `已发现 ${items.length} 个视频资源，选中后进入片段预览。` : '播放视频后，资源会显示在这里。';
}
async function edit(destination) {
  if (!selected) return;
  note('正在打开视频预览…');
  const result = await chrome.runtime.sendMessage({type: 'studio:draft', tabId: sourceTab.id, requestId: selected, destination});
  if (!result?.ok) throw Error(result?.error || '无法打开视频');
  window.close();
}
for (const [id, destination] of [['download', 'download'], ['workbench', 'workbench']]) {
  $(id).onclick = () => edit(destination).catch(error => note(error.message));
}
$('refresh').onclick = () => { signature = null; refresh().catch(() => note('读取失败，请重新打开插件')); };
(async () => {
  $('version').textContent = chrome.runtime.getManifest().version_name;
  const tabId = Number(new URL(location.href).searchParams.get('tabId'));
  sourceTab = tabId ? await chrome.tabs.get(tabId) : (await chrome.tabs.query({active: true, currentWindow: true}))[0];
  $('pageTitle').textContent = sourceTab?.title || '当前页面';
  await refresh();
  setInterval(() => { if (!document.hidden) refresh().catch(() => {}); }, 3000);
})().catch(() => note('请在视频页面点击工具栏图标'));
