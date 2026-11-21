const $ = id => document.getElementById(id);
const ticket = new URL(location.href).searchParams.get('draft');
let draft, duration = 0, job, timer, selectionPlaying = false, selectionRun = 0;
const player = $('player');
const note = (text, error = false) => { $('status').textContent = text; $('status').classList.toggle('error', error); };
function clock(seconds) { if (!Number.isFinite(seconds)) return '--:--'; const mins = Math.floor(seconds / 60); return `${String(mins).padStart(2, '0')}:${(seconds % 60).toFixed(1).padStart(4, '0')}`; }
function values() { return {start: Number($('startTime').value), end: Number($('endTime').value)}; }
function valid() { const {start, end} = values(); return duration > 0 && Number.isFinite(start) && Number.isFinite(end) && 0 <= start && start < end && end <= duration + 0.01; }
function ready() {
  const enabled = !!draft && !draft.manifest && $('authorized').checked && (!$('clipEnabled').checked || valid()) && !job;
  $('download').disabled = $('workbench').disabled = !enabled;
}
function renderRange() {
  const {start, end} = values();
  $('startHandle').value = start; $('endHandle').value = end;
  $('selectionBand').style.left = `${duration ? start / duration * 100 : 0}%`;
  $('selectionBand').style.right = `${duration ? 100 - end / duration * 100 : 0}%`;
  $('rangeLabel').textContent = $('clipEnabled').checked ? `${clock(start)} — ${clock(end)}` : '完整视频';
  $('rangeDuration').textContent = clock($('clipEnabled').checked && valid() ? end - start : duration);
  ready();
}
function previewBoundary(kind) {
  selectionRun++; selectionPlaying = false; player.pause();
  const boundary = values()[kind];
  // The end is exclusive: show the final frame inside the selected interval.
  player.currentTime = kind === 'start' ? boundary : Math.max(values().start, boundary - 0.001);
}
function rangeChanged(kind, value) {
  if (!Number.isFinite(value)) return;
  if (kind === 'start') $('startTime').value = Math.max(0, Math.min(value, Number($('endTime').value) - 0.04)).toFixed(2);
  else $('endTime').value = Math.min(duration, Math.max(value, Number($('startTime').value) + 0.04)).toFixed(2);
  $('clipEnabled').checked = true; renderRange();
  previewBoundary(kind);
}
for (const [id, kind] of [['startHandle', 'start'], ['endHandle', 'end'], ['startTime', 'start'], ['endTime', 'end']]) {
  $(id).addEventListener(id.endsWith('Handle') ? 'input' : 'change', () => rangeChanged(kind, Number($(id).value)));
  if (!id.endsWith('Handle')) $(id).oninput = () => {
    $('clipEnabled').checked = true; renderRange();
    if ($(id).value !== '' && valid()) previewBoundary(kind);
  };
}
$('markStart').onclick = () => rangeChanged('start', player.currentTime);
$('markEnd').onclick = () => rangeChanged('end', player.currentTime);
$('clipEnabled').onchange = renderRange;
$('authorized').onchange = ready;
$('playSelection').onclick = async () => {
  if (!valid()) return;
  const run = ++selectionRun;
  selectionPlaying = false; player.pause(); player.currentTime = values().start;
  try {
    await player.play();
    if (run !== selectionRun) { player.pause(); return; }
    selectionPlaying = true;
    const tick = () => {
      if (!selectionPlaying || run !== selectionRun) return;
      if (player.currentTime >= values().end) { previewBoundary('end'); return; }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  } catch { note('请点击播放器开始播放', true); }
};
player.ontimeupdate = () => {
  $('playhead').style.left = `${duration ? Math.min(100, player.currentTime / duration * 100) : 0}%`;
  if (selectionPlaying && player.currentTime >= values().end) previewBoundary('end');
};
player.onpause = () => { if (player.paused) selectionPlaying = false; };
player.onloadedmetadata = () => {
  duration = Number.isFinite(player.duration) ? player.duration : 0;
  const size = draft.size > 0 ? draft.size < 1048576 ? Math.max(1, Math.round(draft.size / 1024)) + ' KB' : (draft.size / 1048576).toFixed(1) + ' MB' : '大小待下载确认';
  $('properties').textContent = `${player.videoWidth || '—'} × ${player.videoHeight || '—'} · ${clock(duration)} · ${size}`;
  $('durationLabel').textContent = clock(duration);
  for (const id of ['clipEnabled', 'startHandle', 'endHandle', 'startTime', 'endTime', 'markStart', 'markEnd', 'playSelection']) $(id).disabled = !duration || draft.manifest;
  for (const id of ['startHandle', 'endHandle', 'startTime', 'endTime']) $(id).max = duration;
  $('endTime').value = duration.toFixed(2); renderRange();
};
player.onerror = () => {
  $('previewError').hidden = false; $('previewError').textContent = '当前资源暂不能预览。普通视频仍可完整下载；选段需要先读取视频时长。';
  ready();
};
async function poll() {
  if (!job) return;
  const response = await chrome.runtime.sendMessage({type: 'studio:status', job});
  if (!response?.ok) { note(response?.error || '读取处理状态失败', true); return; }
  const data = response.result;
  if (data.status === 'failed') { note(data.error || '视频处理失败', true); clearInterval(timer); job = null; ready(); return; }
  if (data.status === 'ready') {
    clearInterval(timer);
    if (job.destination === 'workbench') {
      note('处理完成，已同步到工作台 · 拉片'); $('openRecord').href = `${response.endpoint}/breakdowns?id=${encodeURIComponent(job.id)}`; $('openRecord').hidden = false;
    } else note(data.exportSaved ? '所选片段已交给浏览器保存' : '片段已处理，正在交给浏览器保存…');
    job = null; ready(); return;
  }
  note(data.phase === 'processing' ? '正在处理所选视频，完成后自动打开工作台…' : '正在将视频传给本机工作台…');
}
async function transferSource(config, currentJob) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 1200000);
  try {
    const source = await fetch(draft.url, {signal: controller.signal, credentials: 'include'});
    if (!source.ok || !source.body) throw Error('视频服务器未允许读取，请回到原网页播放后重新选择资源');
    const reader = source.body.getReader(); let offset = 0, buffered = 0;
    const buffer = new Uint8Array(2 * 1024**2);
    const send = async (data, final = false) => {
      const query = new URLSearchParams({id: currentJob.id, destination: currentJob.destination, offset, final: final ? '1' : '0'});
      const response = await fetch(`${config.endpoint}/api/workbench/browser-upload?${query}`, {method: 'POST',
        headers: {'Content-Type': 'application/octet-stream', Authorization: `Bearer ${config.token}`}, body: data, signal: controller.signal});
      if (!response.ok) throw Error('视频传输未完成，请检查本机工作台是否运行');
      const result = await response.json();
      if (result.status === 'failed') throw Error(result.error || '视频未通过完整性检查');
    };
    while (true) {
      const {done, value} = await reader.read(); if (done) break;
      for (let start = 0; start < value.length;) {
        const count = Math.min(buffer.length - buffered, value.length - start);
        buffer.set(value.subarray(start, start + count), buffered); buffered += count; start += count;
        if (buffered === buffer.length) {
          await send(buffer); offset += buffered; buffered = 0;
          note(`正在传给本机工作台 · ${(offset / 1048576).toFixed(1)} MB，请保留此窗口`);
        }
      }
    }
    if (buffered) { await send(buffer.subarray(0, buffered)); offset += buffered; }
    await send(new Uint8Array(), true);
    const done = await chrome.runtime.sendMessage({type: 'studio:upload-finished', id: currentJob.id});
    if (!done?.ok) throw Error(done?.error || '工作台同步未完成');
  } catch (error) {
    controller.abort();
    await chrome.runtime.sendMessage({type: 'studio:upload-finished', id: currentJob.id, failed: true}).catch(() => {});
    throw error;
  } finally { clearTimeout(timeout); }
}
async function save(destination) {
  if (!$('authorized').checked) throw Error('请先确认你有权保存此视频');
  if ($('clipEnabled').checked && !valid()) throw Error('请检查开始和结束时间');
  const {start, end} = values();
  note($('clipEnabled').checked ? '正在准备片段导出…' : '正在开始下载…');
  $('download').disabled = $('workbench').disabled = true;
  const response = await chrome.runtime.sendMessage({type: 'studio:save', draft: ticket, destination, authorized: true,
    duration, clipStart: $('clipEnabled').checked ? start : undefined, clipEnd: $('clipEnabled').checked ? end : undefined});
  if (!response?.ok) { ready(); throw Error(response?.error || '下载未能开始'); }
  if (!response.job) { note('已交给 Chrome 下载，请在浏览器下载列表查看'); ready(); return; }
  job = response.job;
  try {
    if (response.upload) await transferSource(response.upload, job);
    await poll(); if (job) timer = setInterval(() => poll().catch(() => note('工作台暂未响应，请检查本机服务', true)), 1800);
  } catch (error) { job = null; ready(); throw error; }
}
for (const [id, destination] of [['download', 'download'], ['workbench', 'workbench']]) $(id).onclick = () => save(destination).catch(error => note(error.message, true));
(async () => {
  const response = await chrome.runtime.sendMessage({type: 'studio:get-draft', draft: ticket});
  if (!response?.ok) throw Error('视频选择已失效，请从插件重新打开');
  draft = response.draft;
  $('mediaTitle').textContent = draft.title || draft.name || '视频预览';
  $('sourceHost').textContent = new URL(draft.sourceUrl).hostname;
  $('download').className = draft.destination === 'download' ? 'primary' : 'secondary';
  $('workbench').className = draft.destination === 'workbench' ? 'primary' : 'secondary';
  if (draft.manifest) {
    $('processingHint').textContent = '当前选段导出支持 MP4/WebM 等普通视频文件；HLS/DASH 清单暂不支持这两个简化导出操作。';
  }
  player.src = draft.url;
  if (/m3u8/i.test(draft.ext || '') && !player.canPlayType('application/vnd.apple.mpegurl') && window.Hls?.isSupported()) {
    const hls = new Hls({debug: false}); hls.loadSource(draft.url); hls.attachMedia(player);
  }
  ready();
})().catch(error => note(error.message, true));
