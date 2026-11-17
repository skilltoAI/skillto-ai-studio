const $ = id => document.getElementById(id);
let tab, config, resources = [], metadata = {}, lastRecord, poll;
const status = message => { $('status').textContent = message; };
function endpoint() {
  const origin = workbenchOrigin(config?.endpoint);
  if (!origin) throw Error('请先启动 Skillto-AI-Studio');
  return origin;
}
async function connect() {
  const result = await chrome.runtime.sendMessage({type: 'workbench-config'});
  if (!result?.ok) throw Error(result?.error || '自动连接失败，请启动本地工作台后重试');
  config = {...config, ...result.config};
  $('serviceStatus').textContent = '已自动连接本地工作台';
  return endpoint();
}
async function api(data, origin) {
  origin ||= await connect();
  const response = await fetch(`${origin}/api/workbench/records`, {method: data ? 'POST' : 'GET',
    headers: {'Content-Type': 'application/json', Authorization: `Bearer ${config.token}`},
    body: data ? JSON.stringify(data) : undefined, signal: AbortSignal.timeout(15000)});
  if (response.status === 404) throw Error('工作台需要更新，请重新启动 Skillto-AI-Studio');
  if (response.status === 403) throw Error('工作台连接已失效，请点击“重新连接工作台”');
  let result;
  try { result = await response.json(); } catch { throw Error('本地服务返回了无效响应，请检查工作台版本'); }
  if (!response.ok) throw Error(result.error || '工作台未连接');
  return result;
}
function sizeLabel(bytes) {
  if (!(bytes > 0)) return '大小未知（下载后确认）';
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}
function describe(info = {}) {
  return `${info.width && info.height ? `${info.width} × ${info.height}` : '分辨率待预览'} · ${sizeLabel(info.bytes)}${info.duration > 0 ? ` · ${Math.round(info.duration)} 秒` : ''}`;
}
function selectResource() {
  $('previewPlayer').pause(); $('previewPlayer').removeAttribute('src'); $('previewPlayer').load();
  $('previewPlayer').hidden = true; $('previewHint').hidden = true;
  $('resourceInfo').textContent = $('resources').value ? describe(metadata[$('resources').value]) : '尚未发现资源';
  $('preview').disabled = $('downloadResource').disabled = !$('resources').value;
}
async function trackDownload() {
  if (!lastRecord) return;
  try {
    const origin = await connect(), result = await api(null, origin), record = result.records.find(row => row.id === lastRecord);
    if (!record) return;
    $('lastDownload').href = `${origin}/breakdowns?id=${encodeURIComponent(record.id)}`;
    $('lastDownload').hidden = false;
    if (record.status === 'ready') {
      status(`下载完成 · ${describe(record)}`); clearInterval(poll);
      $('lastDownload').textContent = '打开拉片并播放视频';
    } else if (record.status === 'failed') {
      status(!record.transfer && /新鲜 Cookie/.test(record.error || '') ? '上次网页解析任务失败；现在可点击“浏览器下载当前视频到拉片”' : record.error || '下载失败，请打开拉片查看'); clearInterval(poll);
    } else status(record.status === 'queued' ? '排队中，可打开拉片查看状态' : record.transfer === 'browser' ? 'Chrome 正在下载或导入视频，可打开拉片查看状态' : '正在下载与合并，可打开拉片查看状态');
  } catch (error) { clearInterval(poll); status(error.message); }
}
function action(id, callback) {
  $(id).addEventListener('click', async () => {
    $(id).disabled = true;
    status('正在处理…');
    try { await callback(); } catch (error) { status(error.message === 'Failed to fetch' ? '连接失败：请启动本地服务并检查 Chrome 的本地网络访问许可' : error.message); }
    finally { $(id).disabled = false; }
  });
}
function drawResources() {
  $('resources').replaceChildren();
  if (!resources.length) $('resources').add(new Option('未发现资源；可直接下载当前视频', ''));
  resources.forEach((url, index) => {
    const host = new URL(url).hostname;
    const type = /m3u8/i.test(url) ? 'HLS' : /\.mpd/i.test(url) ? 'DASH' : '视频';
    $('resources').add(new Option(`${index+1}. ${type} · ${host}`, url));
  });
  selectResource();
}
async function scan() {
  const found = await chrome.scripting.executeScript({target: {tabId: tab.id}, world: 'MAIN', func: collectPageMedia});
  const captured = (await chrome.storage.session.get(`capture:${tab.id}`))[`capture:${tab.id}`];
  $('capture').textContent = captured?.armed ? '◉ 停止网络发现' : '◉ 开启网络发现';
  const items = found.flatMap(r => r.result || []).map(item => typeof item === 'string' ? {url: item} : item);
  resources = [...new Set([...items.map(item => item.url), ...(captured?.resources || [])])].slice(0, 60);
  metadata = Object.fromEntries(resources.map(url => [url, {...metadata[url], ...captured?.metadata?.[url], ...items.find(item => item.url === url)}]));
  drawResources(); status(`发现 ${resources.length} 个资源；请核对所选项，列表可能包含预加载视频`);
  return items;
}
async function download(url, browser = true) {
  if (!$('authorized').checked) throw Error('请先确认下载授权');
  if (!/^https?:\/\//.test(url || '')) throw Error('请选择 HTTP/HTTPS 视频资源');
  let result;
  if (browser) {
    const response = await chrome.runtime.sendMessage({type: 'browser-download', url,
      sourceUrl: tab.url, title: metadata[url]?.title || tab.title, duration: metadata[url]?.duration, authorized: true});
    if (!response?.ok) throw Error(response?.error || '浏览器下载未能开始');
    result = response.record;
  } else result = await api({action: 'create', url, sourceUrl: tab.url, title: tab.title, authorized: true});
  lastRecord = result.id;
  status('已加入下载队列，在拉片页查看进度');
  await chrome.storage.local.set({lastRecord: result.id});
  clearInterval(poll); poll = setInterval(trackDownload, 3000); await trackDownload();
}
action('scan', scan);
action('download', async () => {
  if (!$('authorized').checked) throw Error('请先确认下载授权');
  if (!await chrome.permissions.request({permissions: ['downloads']})) throw Error('未允许浏览器下载权限');
  const items = await scan();
  let current = items.find(item => item.current);
  if (!current && ['douyin.com', 'www.douyin.com'].includes(new URL(tab.url).hostname)) {
    const result = await chrome.scripting.executeScript({target: {tabId: tab.id}, world: 'MAIN', func: resolveCurrentDouyinMedia});
    const detail = result[0]?.result;
    if (detail?.error) throw Error(detail.error);
    if (detail?.url) { current = detail; metadata[detail.url] = detail; resources = [...new Set([detail.url, ...resources])].slice(0, 60); drawResources(); }
  }
  if (!current) throw Error(resources.length ? '已找到媒体候选，请预览核对后点击“下载所选资源”；不会回退到网页解析' : '当前播放器没有暴露可保存的文件地址；请开启网络发现后播放该视频，再扫描。不会回退到网页解析');
  await download(current.url);
});
action('downloadResource', async () => {
  if (!$('authorized').checked) throw Error('请先确认下载授权');
  const url = $('resources').value;
  const manifest = /\.(m3u8|mpd)(?:[?#]|$)/i.test(url) || /mpegurl|dash\+xml/i.test(metadata[url]?.mime || '');
  if (!manifest && !await chrome.permissions.request({permissions: ['downloads']})) throw Error('未允许浏览器下载权限');
  await download(url, !manifest);
});
$('resources').onchange = selectResource;
action('preview', async () => {
  const url = $('resources').value;
  if (!url) throw Error('请先选择视频资源');
  const player = $('previewPlayer'); player.hidden = false;
  $('previewHint').hidden = false; $('previewHint').textContent = '预览所选资源；音视频分流或流媒体可能需下载合并后播放。';
  player.onloadedmetadata = () => {
    metadata[url] = {...metadata[url], width: player.videoWidth, height: player.videoHeight,
      duration: Number.isFinite(player.duration) ? player.duration : null};
    $('resourceInfo').textContent = describe(metadata[url]);
  };
  player.onerror = () => { $('previewHint').textContent = '此资源不能在弹窗直接播放，请回原页面核对，或下载合并后在拉片页播放。'; };
  player.src = url;
  await player.play().catch(() => {});
});
action('capture', async () => {
  const name = `capture:${tab.id}`;
  const previous = (await chrome.storage.session.get(name))[name];
  if (previous?.armed) {
    await chrome.storage.session.remove(name);
    $('capture').textContent = '◉ 开启网络发现';
    status('已停止当前标签的网络发现'); return;
  }
  // Must be requested directly from a user gesture; covers CDN + initiator domains.
  const granted = await chrome.permissions.request({origins: ['https://*/*', 'http://*/*']});
  if (!granted) throw Error('未授予网络发现权限，仍可扫描页面或下载当前链接');
  await chrome.storage.session.set({[`capture:${tab.id}`]: {armed: true, resources: []}});
  $('capture').textContent = '◉ 停止网络发现';
  status('已开启当前标签发现；请刷新并播放视频，再扫描');
});
action('reconnect', async () => { await chrome.storage.local.remove('token'); await connect(); status('已自动重新连接工作台'); });
action('open', async () => chrome.tabs.create({url: `${await connect()}/breakdowns`}));
(async () => {
  $('version').textContent = `视频采集 · 拉片 · ${chrome.runtime.getManifest().version}`;
  config = await chrome.storage.local.get(['endpoint', 'token', 'lastRecord']);
  [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  $('title').textContent = tab?.title || '当前页面不可访问';
  const previous = (await chrome.storage.session.get(`capture:${tab.id}`))[`capture:${tab.id}`];
  $('capture').textContent = previous?.armed ? '◉ 停止网络发现' : '◉ 开启网络发现';
  drawResources();
  await connect();
  if (/^https?:/.test(tab?.url || '') && !workbenchOrigin(tab.url)) await scan();
  if (config.token && config.lastRecord) { lastRecord = config.lastRecord; poll = setInterval(trackDownload, 3000); await trackDownload(); }
})().catch(error => status(error.message));
