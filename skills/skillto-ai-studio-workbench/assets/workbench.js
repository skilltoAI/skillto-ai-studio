const $ = id => document.getElementById(id);
const labels = {queued: '等待下载', downloading: '下载与合并中', ready: '已入库', failed: '下载失败'};
let records = [], selected = new URL(location.href).searchParams.get('id'), dirty = false, current;
let timer, listSignature;
function notice(text) { $('notice').textContent = text; clearTimeout(timer); timer = setTimeout(() => $('notice').textContent = '', 6000); }
async function api(data, path = '/api/workbench/records') {
  const response = await fetch(path, data ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)} : {});
  const result = await response.json(); if (!response.ok) throw Error(result.error || '请求失败'); return result;
}
function node(tag, text, cls) { const element = document.createElement(tag); if (text) element.textContent = text; if (cls) element.className = cls; return element; }
function mediaProperties(record) {
  const size = record.bytes > 0 ? `${(record.bytes / 1024 / 1024).toFixed(2)} MB` : '大小未知';
  const resolution = record.width && record.height ? `${record.width} × ${record.height}` : '分辨率待播放';
  return `${resolution} · ${size}${record.duration > 0 ? ` · ${Math.round(record.duration)} 秒` : ''}${record.file ? ` · ${record.file.split('.').pop().toUpperCase()}` : ''}`;
}
function renderList() {
  const search = $('search').value.toLowerCase();
  const signature = JSON.stringify([selected, search, records.map(r => [r.id, r.title, r.platform, r.status])]);
  if (signature === listSignature) return;
  listSignature = signature;
  $('count').textContent = records.length; $('records').replaceChildren();
  records.filter(r => `${r.title} ${r.platform}`.toLowerCase().includes(search)).forEach(record => {
    const button = node('button', '', `record${record.id === selected ? ' selected' : ''}`);
    button.append(node('strong', record.title), node('small', `${record.platform} · ${labels[record.status] || record.status}`));
    button.onclick = () => {
      if (dirty && !confirm('笔记尚未保存，放弃修改并切换？')) return;
      dirty = false; selected = record.id; const url = new URL(location.href); url.searchParams.set('id', selected); history.pushState(null, '', url);
      renderList(); renderDetail(record);
    }; $('records').append(button);
  });
}
function renderDetail(record) {
  current = record; const main = $('detail'); main.replaceChildren();
  main.append(node('h2', record.title), node('p', `${record.platform} · ${new Date(record.createdAt).toLocaleString()} · ${labels[record.status]}`, 'meta'));
  if (record.clipStart != null && record.clipEnd != null) main.append(node('p', `来源片段：${record.clipStart.toFixed(2)} — ${record.clipEnd.toFixed(2)} 秒${record.sourceDuration ? ` · 原视频 ${record.sourceDuration.toFixed(2)} 秒` : ''}`, 'meta'));
  const player = node('div', '', 'player');
  if (record.status === 'ready') {
    const properties = node('p', mediaProperties(record), 'meta'); properties.id = 'mediaProperties'; main.append(properties);
    const video = document.createElement('video'); video.controls = true; video.preload = 'metadata'; video.src = `/api/workbench/media?id=${encodeURIComponent(record.id)}`; player.append(video);
    video.onloadedmetadata = () => {
      properties.textContent = mediaProperties({...record, width: video.videoWidth || record.width,
        height: video.videoHeight || record.height, duration: Number.isFinite(video.duration) ? video.duration : record.duration});
    };
    video.onerror = () => { properties.textContent = `${mediaProperties(record)} · 当前浏览器无法播放，可保存副本用本机播放器打开`; };
  } else player.append(node('p', record.error || '下载完成后将在这里显示视频。'));
  main.append(player);
  const actions = node('div', '', 'detail-actions');
  const source = node('a', '打开来源'); source.href = record.sourceUrl; source.target = '_blank'; source.rel = 'noopener noreferrer'; actions.append(source);
  if (record.status === 'ready') { const link = node('a', '保存视频副本'); link.href = `/api/workbench/media?id=${encodeURIComponent(record.id)}`; link.download = `${record.id}.${record.file.split('.').pop()}`; actions.append(link); }
  const exportButton = node('button', '导出拉片 JSON'); exportButton.onclick = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], {type: 'application/json'}));
    const a = node('a'); a.href = url; a.download = `breakdown-${record.id}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }; actions.append(exportButton); main.append(actions);
  const notesLabel = node('label', '拉片笔记'); notesLabel.htmlFor = 'notes';
  const notes = node('textarea'); notes.id = 'notes'; notes.value = record.notes; notes.placeholder = '记录选题、开场钩子、结构、画面、声音和可借鉴之处…';
  const shotsLabel = node('h3', '分镜时间轴');
  const shots = node('div'); shots.id = 'shots';
  function addShot(value) {
    const row = node('div', '', 'shot');
    const start = node('input'); start.type = 'number'; start.min = '0'; start.step = '0.1'; start.value = value.start; start.setAttribute('aria-label', '开始秒数');
    const end = node('input'); end.type = 'number'; end.min = '0'; end.step = '0.1'; end.value = value.end; end.setAttribute('aria-label', '结束秒数');
    const text = node('textarea'); text.value = value.text; text.placeholder = '画面、动作、镜头或声音…'; text.setAttribute('aria-label', '分镜描述');
    const seek = node('button', '▶'); seek.title = '播放此分镜'; seek.setAttribute('aria-label', '播放此分镜'); seek.onclick = () => { const video = main.querySelector('video'); if (video) { video.currentTime = Number(start.value); video.play().catch(() => notice('请点击播放器开始播放')); } };
    const remove = node('button', '移除'); remove.onclick = () => { row.remove(); dirty = true; };
    row.append(start, node('span','—'), end, text, seek, remove); shots.append(row);
  }
  record.shots.forEach(addShot);
  const add = node('button', '＋ 添加分镜'); add.onclick = () => {
    const start = Math.round((main.querySelector('video')?.currentTime || 0) * 10) / 10;
    addShot({start, end:start+3, text:''}); dirty = true;
  };
  const save = node('button', '保存笔记', 'primary'); save.onclick = async () => {
    save.disabled = true;
    try { const values = [...shots.children].map(row => { const inputs = row.querySelectorAll('input'); return {start: inputs[0].value === '' ? null : Number(inputs[0].value), end: inputs[1].value === '' ? null : Number(inputs[1].value), text:row.querySelector('textarea').value}; });
      const updated = await api({action:'update', id:record.id, revision:record.revision, notes:notes.value, shots:values});
      dirty = false; records = records.map(r => r.id === updated.id ? updated : r); renderDetail(updated); notice('已保存到本机磁盘');
    } catch (error) { notice(error.message); } finally { save.disabled = false; }
  };
  notes.oninput = shots.oninput = () => { dirty = true; };
  main.append(notesLabel, notes, shotsLabel, node('p', '开始 / 结束时间以秒为单位；添加分镜时自动取当前播放位置。', 'help'), shots, add, node('p', `修改版本 ${record.revision} · 历史保存 ${record.history.length} 次`, 'help'), save);
}
async function refresh() {
  const result = await api(); records = result.records; renderList();
  const record = records.find(r => r.id === selected);
  if (record && !dirty && (!current || current.id !== record.id || current.status !== record.status)) renderDetail(record);
}
$('search').oninput = renderList;
$('new').onclick = () => $('newDialog').showModal();
$('cancelNew').onclick = () => $('newDialog').close();
$('newForm').onsubmit = async event => {
  event.preventDefault(); const button = event.submitter; button.disabled = true;
  try { const record = await api({action:'create', url:$('url').value, authorized:$('authorized').checked}); selected = record.id; dirty = false; $('newDialog').close(); await refresh(); notice('已加入下载队列'); }
  catch(error) { notice(error.message); } finally { button.disabled = false; }
};
window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
window.addEventListener('popstate', () => { if (dirty) { notice('请先保存笔记再切换记录'); return; } selected = new URL(location.href).searchParams.get('id'); current = null; refresh().catch(error => notice(error.message)); });
refresh().catch(error => notice(error.message));
setInterval(() => { if (!document.hidden) refresh().catch(error => notice(error.message)); }, 4000);
