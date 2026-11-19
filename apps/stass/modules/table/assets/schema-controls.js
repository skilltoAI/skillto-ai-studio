/* Shared schema-driven controls for the SkillTo review page. */
(() => {
  const views = new Map();
  const noteDrafts = new Map();
  const noteKey = (tableId, rowId, field) => JSON.stringify([tableId,rowId,field]);
  const inlineNote = field => field.type === 'text' && !field.readOnly &&
    (field.name === 'manualProcessing' || field.label === '人工处理备注');
  const mediaTypes = new Set(['image', 'video', 'short_video_info']);
  const present = value => value != null && (typeof value !== 'string' || value.trim() !== '') && (!Array.isArray(value) || value.some(item => item != null && item !== ''));
  const printable = value => Array.isArray(value) ? value.map(printable).join(' / ') : value && typeof value === 'object' ? JSON.stringify(value) : String(value ?? '');
  const fieldsFor = table => {
    const fields = [...(table.fields || [])];
    const known = new Set(fields.map(f => f.name));
    for (const row of table.rows || []) for (const [name, value] of Object.entries(row.fields || {})) {
      if (known.has(name)) continue;
      known.add(name);
      fields.push({name, label:name, type:typeof value === 'number' ? 'number' : typeof value === 'boolean' ? 'boolean' : 'text'});
    }
    return fields;
  };
  function viewFor(table) {
    if (!views.has(table.id)) {
      let saved = null;
      try { saved = JSON.parse(localStorage.getItem(`skillto-columns:${table.id}`)); } catch {}
      const fields = fieldsFor(table);
      const defaults = fields.filter(f => !/^(secUid|videoId|source.*Id|profileUrl|coverUrl)$/.test(f.name)).slice(0, 9).map(f => f.name);
      const media = fields.filter(f => f.type === 'short_video_info' || f.type === 'video').map(f => f.name);
      views.set(table.id, {filters:{}, visible:new Set(Array.isArray(saved) ? saved : [...defaults, ...media]), schema:''});
    }
    return views.get(table.id);
  }
  function matches(value, field, rule) {
    if (!rule) return true;
    if (field.type === 'number' || field.type === 'date') {
      if (!rule.min && !rule.max) return true;
      const numeric = field.type === 'number';
      const min = rule.min ? (numeric ? Number(rule.min) : rule.min) : null;
      const max = rule.max ? (numeric ? Number(rule.max) : rule.max) : null;
      if (min != null && max != null && min > max) return false;
      if (!present(value) || (numeric && (typeof value === 'boolean' || !Number.isFinite(Number(value))))) return false;
      const current = numeric ? Number(value) : String(value).slice(0,10);
      return (!numeric || Number.isFinite(current)) && (min == null || current >= min) && (max == null || current <= max);
    }
    if (mediaTypes.has(field.type)) return !rule.value || (rule.value === 'yes' ? present(value) : !present(value));
    if (field.type === 'boolean') return !rule.value || value === (rule.value === 'yes');
    if (field.type === 'single_choice' || field.type === 'multiple_choice') {
      return !rule.value || (Array.isArray(value) ? value.map(String).includes(rule.value) : String(value ?? '') === rule.value);
    }
    return !rule.value || printable(value).toLocaleLowerCase().includes(rule.value.toLocaleLowerCase());
  }
  function fieldControl(field, index, rule) {
    const label = escapeHtml(field.label || field.name), name = escapeHtml(field.name);
    const value = escapeHtml(rule?.value || '');
    let input;
    if (['number','date'].includes(field.type)) {
      const type = field.type === 'date' ? 'date' : 'number';
      input = `<div class="schema-range"><input type="${type}" ${type === 'number' ? 'step="any"' : ''} data-bound="min" value="${escapeHtml(rule?.min || '')}" aria-label="${label}最小值"><span>至</span><input type="${type}" ${type === 'number' ? 'step="any"' : ''} data-bound="max" value="${escapeHtml(rule?.max || '')}" aria-label="${label}最大值"></div>`;
    } else if (mediaTypes.has(field.type) || field.type === 'boolean') {
      const labels = field.type === 'boolean' ? ['是','否'] : ['有','无'];
      input = `<select aria-label="${label}"><option value="">不限</option><option value="yes" ${rule?.value === 'yes' ? 'selected' : ''}>${labels[0]}</option><option value="no" ${rule?.value === 'no' ? 'selected' : ''}>${labels[1]}</option></select>`;
    } else if (['single_choice','multiple_choice'].includes(field.type)) {
      const options = [...new Set([...(field.options || []).map(String), ...state.table.rows.flatMap(row => {
        const v = row.fields[field.name]; return Array.isArray(v) ? v.map(String) : present(v) ? [String(v)] : [];
      })])];
      input = `<select aria-label="${label}"><option value="">不限</option>${options.map(v => `<option value="${escapeHtml(v)}" ${rule?.value === v ? 'selected' : ''}>${escapeHtml(v)}</option>`).join('')}</select>`;
    } else input = `<input type="search" value="${value}" aria-label="${label}" placeholder="包含文字">`;
    return `<div class="schema-field" data-field="${name}"><span id="schema-label-${index}">${label}</span>${input}</div>`;
  }
  function ensureControls() {
    if (!state.table) return;
    const view = viewFor(state.table), fields = fieldsFor(state.table);
    const signature = JSON.stringify(fields);
    let host = document.getElementById('schemaControls');
    if (!host) {
      host = document.createElement('section'); host.id = 'schemaControls';
      document.querySelector('.filters').after(host);
    }
    if (host.dataset.table !== state.table.id || view.schema !== signature) {
      host.dataset.table = state.table.id; view.schema = signature;
      host.innerHTML = `<details class="schema-filter-panel"><summary>字段筛选 <span id="schemaActiveCount"></span></summary><div class="schema-fields">${fields.map((f,i) => fieldControl(f,i,view.filters[f.name])).join('')}</div><p id="schemaFilterError" role="status"></p></details><details class="schema-column-panel"><summary>显示字段</summary><div class="schema-column-actions"><button type="button" data-columns="all">全选</button><button type="button" data-columns="reset">恢复默认</button></div><div class="schema-columns">${fields.map(f=>`<label><input type="checkbox" data-column="${escapeHtml(f.name)}" ${view.visible.has(f.name)?'checked':''}>${escapeHtml(f.label||f.name)}</label>`).join('')}</div></details><button class="button schema-field-order" type="button" ${state.table.fields.length<2?'disabled':''}>字段排序</button><div class="active-filters"></div>`;
      host.oninput = event => {
        const cell = event.target.closest('[data-field]');
        if (!cell) return;
        const current = viewFor(state.table);
        const rule = current.filters[cell.dataset.field] ||= {};
        rule[event.target.dataset.bound || 'value'] = event.target.value;
        renderRows();
      };
      host.onchange = event => {
        if (event.target.dataset.column) {
          const current = viewFor(state.table), name = event.target.dataset.column;
          if (event.target.checked) current.visible.add(name); else current.visible.delete(name);
          saveColumns(current); renderRows();
        } else if (event.target.matches('select')) host.oninput(event);
      };
      host.onclick = event => {
        if (event.target.closest('.schema-field-order')) { openFieldOrder(); return; }
        const clear = event.target.closest('[data-clear-field]');
        if (clear) {
          const view = viewFor(state.table);
          delete view.filters[clear.dataset.clearField];
          view.schema = '';
          renderRows();
          host.querySelector('.schema-filter-panel summary').focus();
          return;
        }
        const mode = event.target.dataset.columns;
        if (!mode) return;
        const current = viewFor(state.table);
        current.visible = new Set(mode === 'all' ? fieldsFor(state.table).map(f=>f.name) : fieldsFor(state.table).filter(f=>! /^(secUid|videoId|source.*Id|profileUrl|coverUrl)$/.test(f.name)).slice(0,9).map(f=>f.name));
        if (mode === 'reset') fieldsFor(state.table).filter(f=>f.type==='short_video_info'||f.type==='video').forEach(f=>current.visible.add(f.name));
        saveColumns(current);
        host.querySelectorAll('[data-column]').forEach(input=>input.checked=current.visible.has(input.dataset.column));
        renderRows();
      };
    }
    for (const id of ['minVideos','dateFrom','dateTo','llmCategoryFilter']) document.getElementById(id)?.closest('label')?.setAttribute('hidden','');
    for (const id of ['ratioRange','collectRange']) document.getElementById(id)?.setAttribute('hidden','');
    const active = fields.filter(field => {
      const rule = view.filters[field.name];
      return rule && (rule.value || rule.min || rule.max);
    });
    document.getElementById('schemaActiveCount').textContent = active.length || '';
    host.querySelector('.active-filters').replaceChildren(...active.map(field => {
      const rule = view.filters[field.name];
      const control = host.querySelector(`[data-field="${CSS.escape(field.name)}"] select`);
      const value = control?.selectedOptions[0]?.textContent || rule.value ||
        [rule.min && '≥ ' + rule.min, rule.max && '≤ ' + rule.max].filter(Boolean).join('，');
      const label = (field.label || field.name) + '：' + value;
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.dataset.clearField = field.name;
      chip.textContent = label + ' ×';
      chip.setAttribute('aria-label', '清除筛选 ' + label);
      return chip;
    }));
    const inverted = fields.filter(f=>['number','date'].includes(f.type)).filter(f=>{
      const r=view.filters[f.name]; return r?.min && r?.max && (f.type==='number'?Number(r.min)>Number(r.max):r.min>r.max);
    });
    document.getElementById('schemaFilterError').textContent = inverted.length ? `${inverted.map(f=>f.label||f.name).join('、')}：最小值不能大于最大值` : '';
  }
  function openFieldOrder() {
    const tableId = state.table.id;
    const fields = new Map(state.table.fields.map(field => [field.name,field.label || field.name]));
    const original = [...fields.keys()];
    const order = [...original];
    const dialog = document.createElement('dialog');
    dialog.className = 'schema-order-dialog';
    dialog.setAttribute('aria-labelledby','schemaOrderTitle');
    dialog.innerHTML = '<h2 id="schemaOrderTitle">字段排序</h2><p>选择字段后调整位置。排序对本表生效。</p><select size="10" aria-label="字段顺序"></select><div class="schema-order-actions"><button type="button" data-move="-1">↑ 上移</button><button type="button" data-move="1">↓ 下移</button><button type="button" data-first>移到首列</button></div><p role="status" class="schema-order-status"></p><div class="schema-order-actions"><button type="button" data-cancel>取消</button><button type="button" data-save>保存顺序</button></div>';
    const list = dialog.querySelector('select');
    const status = dialog.querySelector('[role=status]');
    function draw(selected) {
      list.replaceChildren(...order.map((name,index) => new Option(`${index+1}. ${fields.get(name)}`,name)));
      list.value = selected;
    }
    function move(target) {
      const index = list.selectedIndex;
      if (index < 0 || target < 0 || target >= order.length || index === target) return;
      const [name] = order.splice(index,1);
      order.splice(target,0,name);
      draw(name);
    }
    dialog.querySelectorAll('[data-move]').forEach(button => {
      button.onclick = () => move(list.selectedIndex + Number(button.dataset.move));
    });
    dialog.querySelector('[data-first]').onclick = () => move(0);
    dialog.querySelector('[data-cancel]').onclick = () => dialog.close();
    dialog.addEventListener('close',() => dialog.remove());
    dialog.querySelector('[data-save]').onclick = async event => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        const definitions = await api('/api/define',{tableId,fieldOrder:order,expectedFieldOrder:original});
        if (state.table?.id === tableId) { state.table.fields = definitions; renderRows(); }
        dialog.close();
        notify('已保存字段顺序');
      } catch (error) {status.textContent = error.message;}
      finally {button.disabled = false;}
    };
    draw(original[0]);
    document.body.append(dialog);
    dialog.showModal();
  }
  function saveColumns(view) {
    try { localStorage.setItem(`skillto-columns:${state.table.id}`, JSON.stringify([...view.visible])); }
    catch { notify('显示字段偏好未保存，仅本次有效',true); }
  }
  filteredRows = function() {
    if (!state.table) return [];
    const fields=fieldsFor(state.table), view=viewFor(state.table);
    const query=$('#searchInput').value.trim().toLocaleLowerCase(), tag=$('#tagFilter').value;
    return state.table.rows.filter(row => (!query || fields.some(f=>printable(row.fields[f.name]).toLocaleLowerCase().includes(query)))
      && (!tag || row.tagIds?.includes(tag)) && fields.every(f=>matches(row.fields[f.name],f,view.filters[f.name])))
      .sort((a,b)=>{
        const x=a.fields[state.sort.field],y=b.fields[state.sort.field];
        if (x==null) return y==null?0:1; if(y==null) return -1;
        return state.sort.direction*(typeof x==='number'?x-y:printable(x).localeCompare(printable(y),'zh-CN'));
      });
  };
  function mediaUrl(value) {
    if (typeof value !== 'string') return '';
    if (value.startsWith('/') && !value.startsWith('//')) return value;
    return safeUrl(value);
  }
  function videoPoster(row, field) {
    const names = [field.posterField, `${field.name}Poster`, 'posterImage', 'coverImage', 'coverUrl', 'thumbnailUrl', 'thumbnail'];
    for (const name of names) {
      const src = mediaUrl(row.fields[name]);
      if (src) return src;
    }
    return mediaUrl(row.media?.find(item => item.type === 'image')?.src);
  }
  function videoCell(row, field, src) {
    const poster = videoPoster(row, field);
    const label = `${field.label || field.name}，点击全屏播放`;
    return `<button type="button" class="schema-video-trigger" data-action="schema-play-video" data-video-src="${escapeHtml(src)}" data-video-poster="${escapeHtml(poster)}" data-video-title="${escapeHtml(field.label || field.name)}" aria-label="${escapeHtml(label)}"><video muted playsinline preload="none" ${poster ? `poster="${escapeHtml(poster)}"` : ''} aria-hidden="true"></video><span class="schema-video-play" aria-hidden="true">▶</span></button>`;
  }
  let hoverPreview = null;
  function hideVideoHover() {
    if (!hoverPreview) return;
    hoverPreview.video.pause();
    hoverPreview.element.remove();
    hoverPreview = null;
  }
  function showVideoHover(trigger) {
    if (hoverPreview?.trigger === trigger) return;
    hideVideoHover();
    const src = trigger.dataset.videoSrc;
    if (!src) return;
    const element = document.createElement('div');
    element.className = 'schema-video-hover';
    element.innerHTML = '<video autoplay muted loop playsinline preload="metadata"></video><span>静音预览 · 点击全屏播放</span>';
    const video = element.querySelector('video');
    video.poster = trigger.dataset.videoPoster || '';
    video.src = src;
    document.body.append(element);
    const rect = trigger.getBoundingClientRect();
    const width = Math.min(420, window.innerWidth - 24);
    const left = Math.min(Math.max(12, rect.right + 12), window.innerWidth - width - 12);
    const height = width * 9 / 16 + 32;
    const top = Math.max(12, Math.min(rect.top, window.innerHeight - height - 12));
    element.style.left = `${left}px`;
    element.style.top = `${top}px`;
    element.style.width = `${width}px`;
    hoverPreview = {trigger, element, video};
    video.play().catch(() => {});
  }
  function videoDialog() {
    let dialog = document.getElementById('schemaVideoDialog');
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.id = 'schemaVideoDialog';
    dialog.className = 'schema-video-dialog';
    dialog.innerHTML = '<div class="schema-video-stage"><div class="schema-video-dialog-head"><strong id="schemaVideoTitle">视频播放</strong><button type="button" class="schema-video-close" aria-label="关闭视频">×</button></div><video controls playsinline preload="none"></video></div>';
    document.body.append(dialog);
    dialog.querySelector('.schema-video-close').onclick = () => dialog.close();
    dialog.addEventListener('close', () => {
      const player = dialog.querySelector('video');
      player.pause();
      player.removeAttribute('src');
      player.load();
      if (document.fullscreenElement === dialog.querySelector('.schema-video-stage')) document.exitFullscreen().catch(() => {});
    });
    document.addEventListener('fullscreenchange', () => {
      if (!document.fullscreenElement && dialog.open) dialog.close();
    });
    return dialog;
  }
  function openVideoFull(trigger) {
    const src = trigger.dataset.videoSrc;
    if (!src) return;
    hideVideoHover();
    const dialog = videoDialog();
    const player = dialog.querySelector('video');
    const stage = dialog.querySelector('.schema-video-stage');
    dialog.querySelector('#schemaVideoTitle').textContent = trigger.dataset.videoTitle || '视频播放';
    player.poster = trigger.dataset.videoPoster || '';
    player.src = src;
    dialog.showModal();
    if (stage.requestFullscreen) stage.requestFullscreen().catch(() => {});
    player.play().catch(() => {});
  }
  function cellHtml(row,field) {
    const value=row.fields[field.name];
    if (inlineNote(field)) {
      const key = noteKey(state.table.id,row.id,field.name);
      const label = escapeHtml(field.label || field.name);
      const draft = noteDrafts.get(key);
      if (draft) return `<form class="schema-inline-note" data-note-field="${escapeHtml(field.name)}"><textarea rows="3" aria-label="${label}">${escapeHtml(draft.text)}</textarea><div><button type="submit" ${draft.pending?'disabled':''}>保存备注</button><button type="button" data-note-cancel ${draft.pending?'disabled':''}>取消</button></div><small role="status">${escapeHtml(draft.error || '')}</small></form>`;
      return `<button class="schema-note-display" type="button" data-note-edit="${escapeHtml(field.name)}" aria-label="编辑${label}">${present(value)?escapeHtml(printable(value)):'＋ 填写备注'}</button>`;
    }
    if (field.candidateGroup && field.type==='image') return renderCandidateCell(row,field).replace(/^<td[^>]*>|<\/td>$/g,'');
    if (field.type==='short_video_info') return videoPreview({...row,fields:{...row.fields,recentVideos:Array.isArray(value)?value:[]}});
    if (field.type==='image') {
      const src=mediaUrl(value); return src?`<img class="video-thumb" loading="lazy" src="${escapeHtml(src)}" alt="${escapeHtml(field.label||field.name)}">`:'<span class="muted">无</span>';
    }
    if (field.type==='video') {
      const src=mediaUrl(value); return src?videoCell(row,field,src):'<span class="muted">无</span>';
    }
    if (!present(value)) return '<span class="muted">—</span>';
    if (field.type==='number') return formatNumber(value);
    if (field.type==='boolean') return `<input type="checkbox" data-schema-boolean="${escapeHtml(field.name)}" aria-label="${escapeHtml(field.label||field.name)}" ${value===true?'checked':''} ${field.readOnly?'disabled':''}>`;
    if (field.type==='date') return escapeHtml(formatDate(value));
    const text=printable(value), link=mediaUrl(value);
    if (link) return `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(text)}</a>`;
    return text.length>140?`<details class="schema-long-text"><summary>${escapeHtml(text.slice(0,100))}…</summary><p>${escapeHtml(text)}</p></details>`:escapeHtml(text);
  }
  renderRows = function() {
    if (!state.table) return;
    hideVideoHover();
    ensureControls();
    const fields=fieldsFor(state.table).filter(f=>viewFor(state.table).visible.has(f.name));
    const table=$('#dataTable');
    table.classList.remove('llm-table','benchmark-table','video-table','edit-table','fusion-table');
    table.classList.add('schema-table');
    $('#tableHead').innerHTML='<tr>'+fields.map(f=>`<th class="${f.type==='number'?'num':''}"><button data-sort="${escapeHtml(f.name)}">${escapeHtml(f.label||f.name)} ↕</button></th>`).join('')+'<th>标签</th><th>评分</th><th>编辑</th></tr>';
    const rows=filteredRows();
    $('#resultCount').textContent=`${rows.length} / ${state.table.rows.length} 条记录`;
    $('#rows').innerHTML=rows.map(row=>`<tr data-id="${escapeHtml(row.id)}">`+fields.map(f=>`<td class="${f.type==='number'?'num':''}">${cellHtml(row,f)}</td>`).join('')+`<td><div class="tag-list">${(row.tagIds||[]).map(id=>state.table.tags.find(t=>t.id===id)).filter(Boolean).map(t=>`<span class="tag" style="--tag-color:${tagColor(t.color)}">${escapeHtml(t.name)}</span>`).join('')}</div><button class="tag-edit" data-action="assign">编辑标签</button></td><td><button class="score-button" data-action="review">${ratingBlocks(row.rating?.score)}</button></td><td><button class="icon-button" data-action="edit" title="编辑记录">⋯</button></td></tr>`).join('')||`<tr><td colspan="${fields.length+3}" class="empty">没有符合条件的记录</td></tr>`;
  };
  const previousSelect=selectTable;
  selectTable=async function(entry) {
    await previousSelect(entry);
    if (!fieldsFor(state.table).some(f=>f.name===state.sort.field)) state.sort={field:fieldsFor(state.table)[0]?.name,direction:1};
    renderRows();
  };
  document.addEventListener('DOMContentLoaded',()=>{
    const rows = $('#rows');
    rows.addEventListener('click',event=>{
      const edit = event.target.closest('[data-note-edit]');
      const cancel = event.target.closest('[data-note-cancel]');
      if (!edit && !cancel) return;
      const line = event.target.closest('tr');
      const rowId = line.dataset.id;
      const field = edit ? edit.dataset.noteEdit : cancel.closest('form').dataset.noteField;
      const key = noteKey(state.table.id,rowId,field);
      if (cancel) noteDrafts.delete(key);
      else {
        const row = state.table.rows.find(item=>item.id===rowId);
        const before = row.fields[field] ?? null;
        noteDrafts.set(key,{before,text:printable(before)});
      }
      renderRows();
      [...rows.querySelectorAll('tr[data-id]')].find(item=>item.dataset.id===rowId)
        ?.querySelector(cancel ? '[data-note-edit]' : '.schema-inline-note textarea')?.focus({preventScroll:true});
    });
    rows.addEventListener('input',event=>{
      const form = event.target.closest('.schema-inline-note');
      if (!form) return;
      const draft = noteDrafts.get(noteKey(state.table.id,form.closest('tr').dataset.id,form.dataset.noteField));
      if (draft) draft.text = event.target.value;
    });
    rows.addEventListener('submit',async event=>{
      const form = event.target.closest('.schema-inline-note');
      if (!form) return;
      event.preventDefault();
      const tableId = state.table.id, rowId = form.closest('tr').dataset.id, field = form.dataset.noteField;
      const key = noteKey(tableId,rowId,field), draft = noteDrafts.get(key);
      if (!draft || draft.pending) return;
      draft.pending = true;
      form.querySelectorAll('textarea,button').forEach(control=>control.disabled = true);
      try {
        const updated = await api('/api/row',{tableId,rowId,action:'update',fields:{[field]:draft.text},expectedFields:{[field]:draft.before}});
        noteDrafts.delete(key);
        if (state.table?.id === tableId) {
          const index = state.table.rows.findIndex(row=>row.id===rowId);
          if (index >= 0) state.table.rows[index] = updated;
        }
        notify('已保存人工处理备注');
      } catch (error) { draft.error = error.message; }
      finally {draft.pending = false; if (state.table?.id === tableId) renderRows();}
    });
    rows.addEventListener('change', async event => {
      const input = event.target.closest('input[data-schema-boolean]');
      if (!input) return;
      const tableId=state.table.id, rowId=input.closest('tr').dataset.id, field=input.dataset.schemaBoolean;
      const row=state.table.rows.find(r=>r.id===rowId), before=row.fields[field];
      input.disabled=true;
      try {
        await api('/api/row',{tableId,action:'update',rowId,fields:{[field]:input.checked}});
        if(state.table?.id===tableId) await refreshTable();
        notify('已保存到磁盘');
      } catch(error) { input.checked=before===true; notify('保存失败：'+error.message,true); }
      finally { input.disabled=false; }
    });

    rows.addEventListener('pointerover', event => {
      if (event.pointerType === 'touch') return;
      const trigger = event.target.closest('.schema-video-trigger');
      if (trigger) showVideoHover(trigger);
    });
    rows.addEventListener('pointerout', event => {
      const trigger = event.target.closest('.schema-video-trigger');
      if (trigger && !trigger.contains(event.relatedTarget)) hideVideoHover();
    });
    rows.addEventListener('focusin', event => {
      const trigger = event.target.closest('.schema-video-trigger');
      if (trigger) showVideoHover(trigger);
    });
    rows.addEventListener('focusout', event => {
      if (event.target.closest('.schema-video-trigger')) hideVideoHover();
    });
    rows.addEventListener('click', event => {
      const trigger = event.target.closest('.schema-video-trigger');
      if (trigger) openVideoFull(trigger);
    });
    document.querySelector('.table-scroll').addEventListener('scroll', hideVideoHover);
    window.addEventListener('resize', hideVideoHover);
    $('#clearFilters').addEventListener('click',()=>{
      if (!state.table) return;
      const view=viewFor(state.table); view.filters={}; view.schema=''; renderRows();
    });
    // The existing media dialog reads recentVideos; resolve other schema media lists here.
    $('#rows').addEventListener('click',event=>{
      const button=event.target.closest('[data-action="videos"]');
      if (!button) return;
      const row=state.table.rows.find(r=>r.id===button.closest('tr').dataset.id);
      const fields=fieldsFor(state.table).filter(f=>f.type==='short_video_info');
      if (fields.length===1 && fields[0].name!=='recentVideos') openVideos({...row,fields:{...row.fields,recentVideos:row.fields[fields[0].name]||[]}});
    });
  });
})();
