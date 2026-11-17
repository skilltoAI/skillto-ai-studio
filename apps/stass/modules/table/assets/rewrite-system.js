/* Local manuscript analysis and second-creation workspace. */
(() => {
  // Reuse the full table renderer in a manuscript, without a second app shell.
  if (new URL(location.href).searchParams.get('rewriteEmbed') === '1' && window.self !== window.top) {
    document.documentElement.classList.add('rewrite-table-embed');
    let pending=0, failed=false;
    const originalFetch=window.fetch.bind(window);
    window.fetch=async (...args)=>{
      const write=String(args[1]?.method||args[0]?.method||'GET').toUpperCase()!=='GET';
      if(write)pending++;
      try{const response=await originalFetch(...args);if(write){await response.clone().text();failed=!response.ok;}return response;}
      catch(e){if(write)failed=true;throw e;}finally{if(write)pending--;}
    };
    window.rewriteTableReadyToLeave=()=>{
      if(document.querySelector('#rowDialog[open],#tagsDialog[open],#assignDialog[open],#reviewDialog[open],#entityDialog[open]'))throw Error('请先保存或关闭表格中的编辑窗口');
      if(pending)throw Error('表格正在保存，请完成后切换');
      if(failed || /保存失败|仅浏览器/.test(document.querySelector('#saveStatus')?.textContent||''))throw Error('表格保存尚未成功，请重试后切换');
    };
    window.addEventListener('beforeunload',event=>{try{window.rewriteTableReadyToLeave();}catch(_){event.preventDefault();event.returnValue='';}});
    return;
  }
  const names = {claims:'核心观点与主张', scenario:'领域与场景', counterintuitive:'反常识／反认知', value:'观众价值与门槛', traffic:'原视频为什么有流量', audience:'目标人群／痛点／利益点／低门槛话术', cases:'案例／Scene／截图', similar:'跨平台相似素材'};
  const platforms = {douyin:'抖音', xiaohongshu:'小红书', youtube:'YouTube', x:'X'};
  const keys = Object.keys(names);
  let panel, data, selected, editing = false, versionTimer = null, versionDirty = false, versionSaving = Promise.resolve(), voicePollTimer = null, lineAnnotationsDraft = [], draftLines = [];
  const lineTags = {ip_voice:'IP口播', case:'案例', remotion:'Remotion'};
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const api = async body => {
    const response = await fetch('/api/rewrites', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || '保存失败');
    return value;
  };
  function notice(message, error = false) {
    const node = panel?.querySelector('.rewrite-notice');
    if (node) { node.textContent = message; node.classList.toggle('error', error); }
  }
  function selectedId() { return new URL(location.href).searchParams.get('manuscript'); }
  function adopt(item) {
    const index = data?.manuscripts?.findIndex(x => x.id === item.id) ?? -1;
    if (index >= 0) data.manuscripts[index] = item;
    selected = item;
  }
  function setSelected(id) {
    const url = new URL(location.href);
    url.searchParams.delete('rewriteTab');
    if (id) url.searchParams.set('manuscript', id); else url.searchParams.delete('manuscript');
    history.pushState(null, '', url);
  }
  const blank = () => ({title:'', status:'research', sourceUrl:'', transcriptUrl:'', transcript:'', videoDurationSeconds:null, sourceAuthor:'', sourcePublishedAt:'', sourceNotes:'',
    sections:Object.fromEntries(keys.map(k => [k,{text:'',score:null,scoreNote:''}])), assets:[],
    similar:Object.fromEntries(Object.keys(platforms).map(k => [k,[]])), secondCreation:''});
  async function load() {
    const response = await fetch('/api/rewrites');
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || '载入失败');
    data = value;
    selected = data.manuscripts.find(x => x.id === selectedId()) || data.manuscripts[0] || null;
    render();
  }
  function tree() {
    return data.knowledgeBases.map(kb => '<details open><summary><span>'+esc(kb.name)+'</span><button data-kind="kb" data-op="rename" data-id="'+esc(kb.id)+'" aria-label="重命名知识库">✎</button><button data-kind="kb" data-op="delete" data-id="'+esc(kb.id)+'" aria-label="删除知识库">×</button></summary>'+
      kb.projects.map(project => '<details open><summary><span>'+esc(project.name)+'</span><button data-kind="project" data-op="rename" data-kb="'+esc(kb.id)+'" data-id="'+esc(project.id)+'" aria-label="重命名项目">✎</button><button data-kind="project" data-op="delete" data-kb="'+esc(kb.id)+'" data-id="'+esc(project.id)+'" aria-label="删除项目">×</button></summary><div class="rewrite-tree-items">'+
        data.manuscripts.filter(x => x.projectId === project.id).map(x => '<button class="'+(x.id === selected?.id?'active':'')+'" data-manuscript="'+esc(x.id)+'">'+esc(x.title)+'<small>'+esc((x.createdAt || '').slice(0,10))+'</small></button>').join('')+
        '</div><button class="rewrite-tree-add" data-add="manuscript" data-kb="'+esc(kb.id)+'" data-project="'+esc(project.id)+'">＋ 新建稿件</button></details>').join('')+
      '<button class="rewrite-tree-add" data-add="project" data-kb="'+esc(kb.id)+'">＋ 新建项目</button></details>').join('');
  }
  function hearts(key, section) {
    return '<div class="rewrite-rating" role="group" aria-label="'+esc(names[key])+'人工评分">'+
      [1,2,3,4,5].map(n => '<button type="button" data-rate="'+key+'" data-score="'+n+'" class="'+(n <= (section.score || 0) ? 'filled':'')+'" title="'+n+' 颗心" aria-label="'+n+' 颗心" aria-pressed="'+(section.score === n)+'">♥</button>').join('')+
      '<button type="button" class="rewrite-clear-rate" data-rate="'+key+'" data-score="" title="清除评分">清除</button>'+
      '<span>'+(section.score ? section.score+'/5 · 人工评分':'未评分')+'</span></div>';
  }
  function lines(text) {
    return (text || '').split('\n').filter(x => x.trim()).map(x => '<li>'+esc(x.replace(/^[-•\d.、 ]+/,''))+'</li>').join('') || '<li class="rewrite-muted">待补充</li>';
  }
  function assetCards() {
    return (selected.assets || []).map(item => '<a class="rewrite-asset" href="'+esc(item.url)+'" target="_blank" rel="noopener noreferrer">'+
      (item.url.match(/\.(png|jpe?g|webp)(\?|$)/i) ? '<img src="'+esc(item.url)+'" alt="'+esc(item.label)+'" loading="lazy">' : '')+
      '<span>'+esc(item.label)+'</span><small>'+esc(item.note)+'</small></a>').join('');
  }
  function similarCards() {
    return Object.entries(platforms).map(([key,label]) => '<div class="rewrite-platform"><h4>'+label+'</h4>'+
      ((selected.similar?.[key] || []).length ? selected.similar[key].map(item => '<article><a href="'+esc(item.url)+'" target="_blank" rel="noopener noreferrer">'+esc(item.title || item.url)+'</a><p>'+esc(item.point)+'</p><small>'+esc(item.evidence)+'</small></article>').join('') : '<p class="rewrite-muted">暂无可核实的原帖；爆款数据待核实。</p>')+'</div>').join('');
  }
  function activeVersion() {
    return selected?.transcriptVersions?.find(item => item.id === selected.activeTranscriptVersionId) || selected?.transcriptVersions?.[0];
  }
  const analysisLabels = {manuscriptAnalysis:'原文亮点', keyframeAnalysis:'原视效亮点'};
  const analysisDrafts = new Map();
  let analysisSaving = Promise.resolve();
  const safeAnalysisUrl = value => /^(https?:\/\/[^\s]+|\/assets\/rewrite-case\/[^\s]+)$/.test(value) ? value : '';
  function analysisInline(value) {
    // Escape every source fragment; only explicit HTTP(S)/case-asset links survive.
    const source=String(value), pattern=/\[([^\]\n]+)\]\(([^\s)]+)\)/g;
    let html='',start=0,match;
    while((match=pattern.exec(source))) {
      html+=esc(source.slice(start,match.index));
      const url=safeAnalysisUrl(match[2]);
      html+=url?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+esc(match[1])+'</a>':esc(match[0]);
      start=pattern.lastIndex;
    }
    return (html+esc(source.slice(start))).replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
  }
  function analysisMarkdown(text) {
    const source=(text||'').split(/\r?\n/), out=[];
    const cells=line=>line.trim().replace(/^\||\|$/g,'').split('|').map(x=>x.trim());
    const separator=line=>/^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line||'');
    for(let i=0;i<source.length;i++) {
      const line=source[i].trim();if(!line)continue;
      if(line.includes('|') && separator(source[i+1])) {
        const head=cells(line);i+=2;const rows=[];
        while(i<source.length && source[i].trim().startsWith('|')){rows.push(cells(source[i]));i++;}i--;
        out.push('<div class="rewrite-analysis-table-scroll" tabindex="0" aria-label="分析表格，可横向滚动"><table><thead><tr>'+head.map(x=>'<th scope="col">'+analysisInline(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+head.map((_,j)=>'<td>'+analysisInline(row[j]||'')+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>');
      } else if(/^#{1,4}\s/.test(line)) {
        const level=Math.min(4,line.match(/^#+/)[0].length+1);
        out.push('<h'+level+'>'+analysisInline(line.replace(/^#+\s+/,''))+'</h'+level+'>');
      } else if(/^[-*]\s/.test(line)) {
        const items=[line.slice(2)];while(/^\s*[-*]\s/.test(source[i+1]||''))items.push(source[++i].trim().slice(2));
        out.push('<ul>'+items.map(x=>'<li>'+analysisInline(x)+'</li>').join('')+'</ul>');
      } else out.push('<p>'+analysisInline(line)+'</p>');
    }
    return out.join('')||'<p class="rewrite-muted">尚未填写。点击“编辑分析”补充原文证据、分析表格与结论。</p>';
  }
  function analysisDraft(key) {
    const id=selected.id+':'+key;
    const existing=analysisDrafts.get(id);
    if(!existing || (!existing.dirty && existing.revision!==(selected[key]?.revision||0))) {
      const saved=selected[key]||{};
      analysisDrafts.set(id,{manuscriptId:selected.id,key,text:saved.text||'',revision:saved.revision||0,dirty:false,editing:existing?.editing||false});
    }
    return analysisDrafts.get(id);
  }
  function analysisStatus(key,message) {
    const node=panel?.querySelector('[data-analysis-status="'+key+'"]');if(node)node.textContent=message;
  }
  async function flushAnalysis() {
    const manuscriptId=selected?.id;if(!manuscriptId)return;
    analysisSaving=analysisSaving.catch(()=>{}).then(async()=>{
      for(const key of Object.keys(analysisLabels)) {
        const draft=analysisDrafts.get(manuscriptId+':'+key);if(!draft?.dirty)continue;
        const text=draft.text;
        analysisStatus(key,'保存中…');
        try {
          const item=await api({action:'save_analysis',id:manuscriptId,analysisKey:key,text,expectedRevision:draft.revision});
          draft.revision=item[key].revision;draft.dirty=draft.text!==text;
          if(selected?.id===manuscriptId) {
            adopt(item);analysisStatus(key,draft.dirty?'有未保存修改':'已保存到磁盘');
            const body=panel.querySelector('[data-analysis-body="'+key+'"]');if(body)body.innerHTML=analysisMarkdown(item[key].text);
          }
        } catch(error) {analysisStatus(key,'保存失败，草稿已保留：'+error.message);throw error;}
      }
    });
    return analysisSaving;
  }

  const storyboardDrafts=new Map();
  function versionButtons(board,label) {
    return '<div class="rewrite-version-tabs rewrite-board-version-tabs" role="group" aria-label="'+esc(label)+'版本">'+board.versions.map(v=>'<button type="button" data-board-version="'+esc(v.id)+'" class="'+(v.id===board.activeVersionId?'active':'')+'" aria-pressed="'+(v.id===board.activeVersionId)+'" title="'+esc(v.label)+'">'+esc(v.id.toUpperCase())+'</button>').join('')+'</div>';
  }
  function bindVersionButtons(section,choose) {
    const buttons=[...section.querySelectorAll('[data-board-version]')];
    buttons.forEach((button,index)=>{
      button.onclick=()=>choose(button.dataset.boardVersion);
      button.onkeydown=event=>{
        let next;if(event.key==='ArrowRight')next=(index+1)%buttons.length;if(event.key==='ArrowLeft')next=(index+buttons.length-1)%buttons.length;if(event.key==='Home')next=0;if(event.key==='End')next=buttons.length-1;
        if(next!==undefined){event.preventDefault();buttons[next].focus();buttons[next].click();}
      };
    });
  }
  function checkMotionTable() {
    const frame=panel?.querySelector('.rewrite-motion-table');
    if(frame?.contentWindow?.rewriteTableReadyToLeave)frame.contentWindow.rewriteTableReadyToLeave();
  }
  function motionStoryboardPane() {
    const section=document.createElement('section'),board=selected.motionStoryboard||{versions:[],activeVersionId:'',revision:0};
    section.id='rewrite-pane-motionStoryboard';section.dataset.manuscriptPane='motionStoryboard';section.setAttribute('role','tabpanel');section.setAttribute('aria-labelledby','rewrite-tab-motionStoryboard');
    const active=board.versions.find(v=>v.id===board.activeVersionId);
    section.innerHTML=versionButtons(board,'motion分镜表')+'<div class="rewrite-board-versions"><span>'+esc(active?.label||'尚未关联分镜表')+'</span><button type="button" data-motion-new '+(!active?'disabled':'')+'>＋ 新增版本</button><button type="button" data-motion-link>关联已有表格</button><button type="button" data-motion-rename '+(!active?'disabled':'')+'>重命名版本</button>'+(active?'<a href="/?table='+encodeURIComponent(active.tableId)+'" target="_blank" rel="noopener">打开完整表格 ↗</a>':'')+'</div><p class="rewrite-muted">'+(active?'各版本独立保存全片分镜、媒体和人工意见。新增版本复制当前表格。':'将全片分镜表关联为首个版本；后续可复制新增版本。')+'</p><div data-motion-host></div><dialog class="rewrite-remotion-dialog" data-motion-dialog><form><h3>关联已有表格</h3><label>分镜表<select required data-motion-table></select></label><p>该表将成为一个新的分镜版本，原表内容保留。</p><div class="rewrite-remotion-actions"><button type="button" data-motion-cancel>取消</button><button type="submit">关联为新版本</button></div><p role="status" data-motion-error></p></form></dialog>';
    let busy=false;
    async function change(action,extra={}) {
      if(busy)return false;busy=true;
      section.querySelectorAll('button').forEach(b=>b.disabled=true);
      try{if(!selected.motionStoryboard)throw Error('请重启本地工作台服务后刷新，以启用motion分镜版本');await flushVersion();const item=await api({action,id:selected.id,expectedRevision:selected.motionStoryboard.revision,...extra});adopt(item);render();return true;}
      catch(e){notice(e.message,true);section.querySelector('[data-motion-error]').textContent=e.message;return false;}
      finally{busy=false;if(section.isConnected){section.querySelectorAll('button').forEach(b=>b.disabled=false);if(!active)for(const key of ['new','rename'])section.querySelector('[data-motion-'+key+']').disabled=true;}}
    }
    bindVersionButtons(section,versionId=>{if(versionId!==board.activeVersionId)change('select_motion_storyboard_version',{versionId});});
    section.querySelector('[data-motion-new]').onclick=()=>change('create_motion_storyboard_version');
    section.querySelector('[data-motion-rename]').onclick=()=>{const label=prompt('版本名称',active.label);if(label?.trim())change('rename_motion_storyboard_version',{versionId:active.id,label:label.trim()});};
    const dialog=section.querySelector('dialog');
    section.querySelector('[data-motion-link]').onclick=async()=>{
      try{await flushVersion();const response=await fetch('/api/catalog');const catalog=await response.json();if(!response.ok)throw Error(catalog.error||'表格列表载入失败');
        const options=catalog.knowledgeBases.flatMap(kb=>kb.projects.flatMap(p=>p.tables.filter(t=>!board.versions.some(v=>v.tableId===t.id)).map(t=>'<option value="'+esc(t.id)+'">'+esc(kb.name+' / '+p.name+' / '+t.name)+'</option>')));
        section.querySelector('[data-motion-table]').innerHTML='<option value="">请选择分镜表</option>'+options.join('');dialog.showModal();
      }catch(e){notice(e.message,true);}
    };
    section.querySelector('[data-motion-cancel]').onclick=()=>dialog.close();
    dialog.querySelector('form').onsubmit=async event=>{event.preventDefault();await change('link_motion_storyboard',{tableId:section.querySelector('[data-motion-table]').value});};
    section.mount=async()=>{
      const host=section.querySelector('[data-motion-host]');if(!active||host.firstChild)return;
      const loading=document.createElement('p');loading.textContent='正在载入分镜表…';loading.setAttribute('role','status');host.append(loading);
      try{
        const response=await fetch('/api/table?id='+encodeURIComponent(active.tableId));const table=await response.json();
        if(!response.ok||table.id!==active.tableId)throw Error(table.error||'分镜表不可用');
        if(!loading.isConnected)return;
        const frame=document.createElement('iframe');frame.className='rewrite-motion-table';frame.title='motion分镜表 '+active.label;frame.src='/?table='+encodeURIComponent(active.tableId)+'&rewriteEmbed=1';host.replaceChildren(frame);
      }catch(e){if(loading.isConnected){loading.textContent='载入失败：'+e.message;const retry=document.createElement('button');retry.type='button';retry.textContent='重试';retry.onclick=()=>{host.replaceChildren();section.mount();};host.append(retry);}}
    };
    section.unmount=()=>{section.querySelector('[data-motion-host]').replaceChildren();};
    return section;
  }
  function storyboardDraft(key) {
    const id=selected.id+':'+key,saved=selected[key]||{rows:[],revision:0};
    if(!storyboardDrafts.has(id)||(!storyboardDrafts.get(id).dirty&&storyboardDrafts.get(id).revision!==saved.revision))storyboardDrafts.set(id,{rows:structuredClone(saved.rows),revision:saved.revision,versionId:saved.activeVersionId,dirty:false});
    return storyboardDrafts.get(id);
  }
  let storyboardSaving=Promise.resolve();
  function flushStoryboards(){storyboardSaving=storyboardSaving.catch(()=>{}).then(saveStoryboards);return storyboardSaving;}
  async function saveStoryboards() {
    const id=selected?.id;if(!id)return;
    const invalid=panel.querySelector('[data-board-frames]:invalid');if(invalid){invalid.reportValidity();throw Error('请先修正关键帧地址');}
    for(const key of ['openingStoryboard','fullStoryboard']) {
      const d=storyboardDrafts.get(id+':'+key);if(!d?.dirty)continue;
      const rows=structuredClone(d.rows),status=panel.querySelector('[data-board-status="'+key+'"]');
      if(status)status.textContent='保存中…';
      try {
        const item=await api({action:'save_storyboard',id,storyboardKey:key,rows,versionId:d.versionId,expectedRevision:d.revision});
        d.revision=item[key].revision;d.dirty=JSON.stringify(d.rows)!==JSON.stringify(rows);
        if(selected?.id===id)adopt(item);
        if(status)status.textContent=d.dirty?'有未保存修改':'已保存到磁盘';
      } catch(e){if(status)status.textContent='保存失败，草稿已保留：'+e.message;throw e;}
    }
  }
  function storyboardPane(key,label) {
    const d=storyboardDraft(key),section=document.createElement('section');
    section.id='rewrite-pane-'+key;section.dataset.manuscriptPane=key;section.setAttribute('role','tabpanel');section.setAttribute('aria-labelledby','rewrite-tab-'+key);
    function draw() {
      const board=selected[key], versionControls=key==='openingStoryboard'?versionButtons(board,label)+'<div class="rewrite-board-versions"><span>'+esc(board.versions.find(v=>v.id===board.activeVersionId)?.label)+'</span><button type="button" data-board-new-version>＋ 新增版本</button><button type="button" data-board-rename-version>重命名版本</button></div>':'';
      section.innerHTML=versionControls+'<div class="rewrite-analysis-actions"><span role="status" data-board-status="'+key+'">'+(d.dirty?'有未保存修改':selected[key]?.updatedAt?'已保存到磁盘':'尚未填写')+'</span><button type="button" data-board-add>＋ 添加分镜</button><button type="button" data-board-save>保存分镜</button></div><p class="rewrite-muted">每镜1–4张关键帧；人工修改意见留空表示该分镜暂时不用修改。时间为设计目标，生成后按音频验收。</p><div class="rewrite-board-scroll"><table class="rewrite-board-table"><thead><tr><th>分镜／时码</th><th>口播台词</th><th>分镜图／关键帧（1–4张）</th><th>动画详细说明</th><th>人工修改意见</th></tr></thead><tbody>'+d.rows.map((r,i)=>'<tr data-board-row="'+i+'"><td><input aria-label="分镜名称" data-board-field="title" value="'+esc(r.title)+'"><input aria-label="时码" data-board-field="time" value="'+esc(r.time)+'"><textarea rows="4" aria-label="分镜画面" data-board-field="description">'+esc(r.description)+'</textarea><button type="button" data-board-remove="'+i+'">删除分镜</button></td><td><textarea rows="10" aria-label="口播台词" data-board-field="narration">'+esc(r.narration)+'</textarea></td><td><div class="rewrite-board-frames">'+r.frames.map(f=>'<a href="'+esc(f.url)+'" target="_blank" rel="noopener noreferrer"><img src="'+esc(f.url)+'" alt="'+esc(f.label)+'" loading="lazy"><span>'+esc(f.label)+'</span></a>').join('')+'</div><details><summary>编辑关键帧地址</summary><label>每行：名称 | 图片URL<textarea rows="4" aria-label="关键帧地址" data-board-frames>'+esc(r.frames.map(f=>f.label+' | '+f.url).join('\n'))+'</textarea></label></details></td><td><textarea rows="14" aria-label="动画详细说明" data-board-field="animation">'+esc(r.animation)+'</textarea><details><summary>生视频提示词</summary><textarea rows="12" aria-label="生视频提示词" data-board-field="prompt">'+esc(r.prompt)+'</textarea></details></td><td><textarea rows="10" aria-label="人工修改意见" placeholder="留空＝暂时不用修改" data-board-field="feedback">'+esc(r.feedback)+'</textarea></td></tr>').join('')+'</tbody></table></div>';
      let changing=false;
      async function versionAction(action,extra={}) {
        if(changing)return;changing=true;
        section.querySelectorAll('button,input,textarea').forEach(el=>el.disabled=true);
        try{await flushVersion();const item=await api({action,id:selected.id,expectedRevision:selected[key].revision,...extra});adopt(item);storyboardDrafts.delete(selected.id+':'+key);render();}
        catch(e){notice(e.message,true);}
        finally{changing=false;section.querySelectorAll('button,input,textarea').forEach(el=>el.disabled=false);}
      }
      if(key==='openingStoryboard') {
        bindVersionButtons(section,versionId=>{if(versionId!==board.activeVersionId)versionAction('select_storyboard_version',{versionId});});
        section.querySelector('[data-board-new-version]').onclick=()=>versionAction('create_storyboard_version');
        section.querySelector('[data-board-rename-version]').onclick=()=>{const v=board.versions.find(v=>v.id===board.activeVersionId);const name=prompt('版本名称',v.label);if(name?.trim())versionAction('rename_storyboard_version',{versionId:v.id,label:name.trim()});};
      }
      section.querySelectorAll('[data-board-field],[data-board-frames]').forEach(el=>el.oninput=()=>{
        const row=d.rows[Number(el.closest('[data-board-row]').dataset.boardRow)];
        if(el.hasAttribute('data-board-frames')) {
          const entries=el.value.split('\n').filter(x=>x.trim());
          if(entries.length>4){el.setCustomValidity('最多4张关键帧');el.reportValidity();return;}
          const frames=entries.map(line=>{const j=line.indexOf('|');return {label:j<0?'关键帧':line.slice(0,j).trim(),url:(j<0?line:line.slice(j+1)).trim()};});
          if(frames.some(f=>!(/^(https?:\/\/[^\s]+|\/assets\/[^\s]+)$/.test(f.url)))){el.setCustomValidity('请填写有效图片地址');el.reportValidity();return;}
          el.setCustomValidity('');row.frames=frames;
        } else row[el.dataset.boardField]=el.value;
        d.dirty=true;section.querySelector('[data-board-status]').textContent='有未保存修改 · 切换前会保存';
      });
      section.querySelector('[data-board-save]').onclick=async()=>{try{await flushVersion();draw();}catch(e){notice(e.message,true);}};
      section.querySelector('[data-board-add]').onclick=()=>{d.rows.push({id:crypto.randomUUID(),title:'新分镜',time:'',narration:'',description:'',animation:'',prompt:'',feedback:'',frames:[]});d.dirty=true;draw();};
      section.querySelectorAll('[data-board-remove]').forEach(b=>b.onclick=()=>{if(confirm('删除这个分镜？保存后记录历史。')){d.rows.splice(Number(b.dataset.boardRemove),1);d.dirty=true;draw();}});
    }
    draw();return section;
  }
  const stepIcon=key=>'<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'+({script:'<path d="M5 3h10l4 4v14H5zM14 3v5h5M8 12h8M8 16h6"/>',manuscriptAnalysis:'<path d="m12 3 2.5 6 6.5 3-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-3z"/>',keyframeAnalysis:'<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8" cy="10" r="1"/><path d="m4 17 5-4 3 2 4-5 4 7"/>',openingStoryboard:'<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',motionStoryboard:'<path d="m9 7 8 5-8 5z"/><rect x="2" y="3" width="20" height="18" rx="2"/>',fullStoryboard:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 9v11M3 14h18"/>'}[key])+'</svg>';
  function bindManuscriptTabs() {
    const card=panel.querySelector('.rewrite-transcript-card');if(!card)return;
    const heading=card.querySelector('.rewrite-version-heading');
    const script=document.createElement('div');script.id='rewrite-pane-script';script.dataset.manuscriptPane='script';script.setAttribute('role','tabpanel');script.setAttribute('aria-labelledby','rewrite-tab-script');
    for(const child of [...card.children])if(child!==heading)script.append(child);
    card.append(script);
    const labels={script:'文案版本',...analysisLabels,openingStoryboard:'前12秒分镜',motionStoryboard:'motion分镜表'};
    const nav=document.createElement('div');nav.className='rewrite-manuscript-tabs';nav.setAttribute('role','tablist');nav.setAttribute('aria-label','稿件内容与分析');
    nav.innerHTML=Object.entries(labels).map(([key,label])=>'<button type="button" id="rewrite-tab-'+key+'" role="tab" data-manuscript-tab="'+key+'" aria-controls="rewrite-pane-'+key+'">'+stepIcon(key)+'<span>'+label+'</span></button>').join('');
    panel.querySelector(".rewrite-main").prepend(nav);
    card.append(storyboardPane("openingStoryboard","前12秒分镜"),motionStoryboardPane());
    for(const [key,label] of Object.entries(analysisLabels)) {
      const draft=analysisDraft(key), section=document.createElement('section');
      section.id='rewrite-pane-'+key;section.dataset.manuscriptPane=key;section.setAttribute('role','tabpanel');section.setAttribute('aria-labelledby','rewrite-tab-'+key);
      section.innerHTML='<div class="rewrite-analysis-actions"><span data-analysis-status="'+key+'" role="status">'+(draft.dirty?'有未保存修改':selected[key]?.updatedAt?'已保存到磁盘':'尚未填写')+'</span><button type="button" data-edit-analysis="'+key+'" aria-expanded="'+draft.editing+'">'+(draft.editing?'阅读分析':'编辑分析')+'</button><button type="button" data-save-analysis="'+key+'">保存分析</button></div><div class="rewrite-analysis-body" data-analysis-body="'+key+'">'+analysisMarkdown(draft.text)+'</div><label class="rewrite-analysis-editor" '+(draft.editing?'':'hidden')+'>'+label+'（支持标题、列表和 Markdown 表格）<textarea rows="24" aria-label="'+label+'正文"></textarea></label>'+(key==='keyframeAnalysis' && selected.assets?.length?'<details class="rewrite-analysis-evidence"><summary>查看原始关键帧拼图</summary><div class="rewrite-assets">'+assetCards()+'</div></details>':'');
      card.append(section);
      const editor=section.querySelector('textarea'),body=section.querySelector('.rewrite-analysis-body');editor.value=draft.text;body.hidden=draft.editing;
      editor.oninput=()=>{draft.text=editor.value;draft.dirty=true;analysisStatus(key,'有未保存修改 · 切换前会保存');};
      section.querySelector('[data-save-analysis]').onclick=async()=>{try{await flushAnalysis(); await flushStoryboards();}catch(error){notice(error.message,true);}};
      section.querySelector('[data-edit-analysis]').onclick=async()=>{
        try{await flushAnalysis();draft.editing=!draft.editing;body.hidden=draft.editing;section.querySelector('label').hidden=!draft.editing;const button=section.querySelector('[data-edit-analysis]');button.textContent=draft.editing?'阅读分析':'编辑分析';button.setAttribute('aria-expanded',String(draft.editing));if(draft.editing)editor.focus();}catch(error){notice(error.message,true);}
      };
    }
    let current='script';
    try{current=new URL(location.href).searchParams.get('rewriteTab')||localStorage.getItem('skillto.rewrite.tab.'+selected.id)||'script';}catch(_error){}
    function show(key) {
      if(key==='fullStoryboard')key='motionStoryboard';
      if(!labels[key])key='script';current=key;
      for(const button of nav.children){const active=button.dataset.manuscriptTab===key;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;}
      card.querySelectorAll('[data-manuscript-pane]').forEach(node=>node.hidden=node.dataset.manuscriptPane!==key);
      heading.querySelector('.rewrite-version-heading-actions').hidden=key!=='script';
      heading.querySelector('h3').textContent=key==='script'?(selected.sourceUrl?.includes('/note/')?'原图文页面 OCR／文案版本':'原视频口播逐字稿／文案版本'):labels[key];
      const motion=card.querySelector('#rewrite-pane-motionStoryboard');if(key==='motionStoryboard')motion.mount();else motion.unmount();
      if(key==='script')refreshLineStats();
    }
    nav.onclick=async event=>{const button=event.target.closest('[data-manuscript-tab]');if(!button)return;
      try{await flushVersion();show(button.dataset.manuscriptTab);try{localStorage.setItem('skillto.rewrite.tab.'+selected.id,current);}catch(_error){}const url=new URL(location.href);url.searchParams.set('rewriteTab',current);history.replaceState(null,'',url);}catch(error){notice(error.message,true);}
    };
    nav.onkeydown=event=>{const keys=Object.keys(labels),index=keys.indexOf(current);let next;
      if(event.key==='ArrowRight')next=keys[(index+1)%keys.length];if(event.key==='ArrowLeft')next=keys[(index+keys.length-1)%keys.length];if(event.key==='Home')next=keys[0];if(event.key==='End')next=keys.at(-1);
      if(next){event.preventDefault();const button=nav.querySelector('[data-manuscript-tab="'+next+'"]');button.focus();button.click();}
    };
    show(current);
  }
  const comparisonViews=new Map();
  let leftSaveTimer=null, leftDirty=false, leftSaving=Promise.resolve(), leftDraft=null;
  function comparisonView() {
    if(!comparisonViews.has(selected.id)) {
      let saved={};try{saved=JSON.parse(localStorage.getItem('skillto.rewrite.compare.'+selected.id)||'{}')||{};}catch(_error){}
      const requestedLeft=new URL(location.href).searchParams.get('compareLeft');
      comparisonViews.set(selected.id,{enabled:requestedLeft?true:saved.enabled!==false,leftId:requestedLeft||saved.leftId});
    }
    const view=comparisonViews.get(selected.id), versions=selected.transcriptVersions;
    if(!versions.some(v=>v.id===view.leftId))view.leftId=versions[Math.max(0,versions.findIndex(v=>v.id===activeVersion().id)-1)].id;
    return view;
  }
  function rememberComparison(){try{localStorage.setItem('skillto.rewrite.compare.'+selected.id,JSON.stringify(comparisonView()));}catch(_error){}}
  function comparisonHtml() {
    const view=comparisonView(), reference=selected.transcriptVersions.find(v=>v.id===view.leftId), version=activeVersion();
    const options=id=>selected.transcriptVersions.map(v=>'<option value="'+esc(v.id)+'" '+(v.id===id?'selected':'')+'>'+esc(v.label)+'</option>').join('');
    return '<div class="rewrite-compare-controls"><button type="button" data-compare-toggle>'+ (view.enabled?'单版本编辑':'双版本编辑')+'</button></div>'+
      '<section class="rewrite-compare" '+(view.enabled?'':'hidden')+' aria-label="双版本多行编辑"><div class="rewrite-dual-editors">'+
      '<label class="rewrite-dual-pane">左侧版本<select data-compare-left aria-label="左侧版本">'+options(reference.id)+'</select><textarea class="rewrite-compare-left-text" aria-label="左侧版本正文" wrap="off" spellcheck="false" '+(reference.id==='v0'?'readonly':'')+'></textarea><span class="rewrite-left-save-status" role="status">'+(reference.id==='v0'?'V0 原稿只读':'已自动保存')+'</span></label>'+
      '<label class="rewrite-dual-pane">右侧版本<select data-compare-right aria-label="右侧版本">'+options(version.id)+'</select><textarea class="rewrite-compare-right-text" aria-label="右侧版本正文" wrap="off" spellcheck="false" '+(version.id==='v0'?'readonly':'')+'></textarea><span class="rewrite-compare-summary" role="status">'+(version.id==='v0'?'V0 原稿只读':'已自动保存')+'</span></label></div></section>';
  }
  function remapComparisonAnnotations(before,after,annotations) {
    const old=before.split('\n'), next=after.split('\n');
    let prefix=0,suffix=0;
    while(prefix<old.length && prefix<next.length && old[prefix]===next[prefix])prefix++;
    while(suffix<old.length-prefix && suffix<next.length-prefix && old[old.length-1-suffix]===next[next.length-1-suffix])suffix++;
    return next.map((_,i)=>structuredClone(i<prefix?annotations[i]:i>=next.length-suffix?annotations[old.length-(next.length-i)]:i-prefix<old.length-prefix-suffix?annotations[i]:null)||{tags:[],remotionPrompt:''});
  }
  async function saveComparisonLeft() {
    clearTimeout(leftSaveTimer);
    if(!leftDirty || !leftDraft)return leftSaving;
    const draft={...leftDraft};leftDirty=false;
    const status=panel.querySelector('.rewrite-left-save-status');if(status)status.textContent='保存中…';
    leftSaving=leftSaving.then(async()=>{
      const version=selected.transcriptVersions.find(v=>v.id===draft.versionId);
      const item=await api({action:'save_version',id:draft.manuscriptId,versionId:draft.versionId,text:draft.text,prompt:version.prompt||'',lineAnnotations:remapComparisonAnnotations(version.text,draft.text,version.lineAnnotations||[])});
      if(selected?.id===draft.manuscriptId) {
        adopt(item);
        if(status && !leftDirty)status.textContent='已自动保存到磁盘';
      }
    });
    try{await leftSaving;}catch(error){leftSaving=Promise.resolve();leftDirty=true;if(status)status.textContent='保存失败，请重试';throw error;}
  }
  async function flushComparisonLeft(){clearTimeout(leftSaveTimer);await leftSaving;if(leftDirty)await saveComparisonLeft();}
  function bindComparison() {
    const view=comparisonView(), reference=selected.transcriptVersions.find(v=>v.id===view.leftId);
    const leftSelect=panel.querySelector('[data-compare-left]'),rightSelect=panel.querySelector('[data-compare-right]');
    const left=panel.querySelector('.rewrite-compare-left-text'),right=panel.querySelector('.rewrite-compare-right-text'),editor=panel.querySelector('.rewrite-version-text');
    panel.querySelector('.rewrite-transcript-card').classList.toggle('rewrite-comparing',view.enabled);
    left.value=reference.text;right.value=editor.value;
    leftDraft={manuscriptId:selected.id,versionId:reference.id,text:reference.text};leftDirty=false;
    panel.querySelector('[data-compare-toggle]').onclick=async()=>{try{await flushVersion();view.enabled=!view.enabled;rememberComparison();render();}catch(error){notice(error.message,true);}};
    let changing=false;
    async function choose(leftId,rightId) {
      if(changing)return;changing=true;leftSelect.disabled=rightSelect.disabled=true;
      try{await flushVersion();if(rightId!==activeVersion().id)adopt(await api({action:'select_version',id:selected.id,versionId:rightId}));view.leftId=leftId;rememberComparison();render();}
      catch(error){leftSelect.value=view.leftId;rightSelect.value=activeVersion().id;notice(error.message,true);}
      finally{changing=false;leftSelect.disabled=rightSelect.disabled=false;}
    }
    leftSelect.onchange=()=>choose(leftSelect.value,rightSelect.value);
    rightSelect.onchange=()=>choose(leftSelect.value,rightSelect.value);
    let syncing=false;
    function syncScroll(from,to){if(syncing)return;syncing=true;to.scrollTop=from.scrollTop;requestAnimationFrame(()=>{syncing=false;});}
    left.addEventListener('scroll',()=>syncScroll(left,right));right.addEventListener('scroll',()=>syncScroll(right,left));
    right.addEventListener('input',()=>{
      if(right.readOnly)return;
      editor.value=right.value;editor.dispatchEvent(new Event('input',{bubbles:true}));
      panel.querySelector('.rewrite-compare-summary').textContent='待保存';
      if(view.leftId===activeVersion().id){left.value=right.value;leftDraft.text=right.value;}
    });
    left.addEventListener('input',()=>{
      if(left.readOnly)return;
      if(view.leftId===activeVersion().id){right.value=left.value;right.dispatchEvent(new Event('input',{bubbles:true}));return;}
      leftDraft.text=left.value;leftDirty=true;
      panel.querySelector('.rewrite-left-save-status').textContent='待保存';
      clearTimeout(leftSaveTimer);leftSaveTimer=setTimeout(()=>saveComparisonLeft().catch(error=>notice(error.message,true)),600);
    });
    for(const input of [left,right])input.addEventListener('blur',()=>flushVersion().catch(error=>notice(error.message,true)));
  }

  function versionEditorHtml() {
    const version = activeVersion();
    if (!version) return '';
    const original = version.id === 'v0';
    return '<section class="rewrite-card rewrite-transcript-card"><div class="rewrite-version-heading"><h3>'+(selected.sourceUrl?.includes('/note/') ? '原图文页面 OCR／文案版本' : '原视频口播逐字稿／文案版本')+'</h3><div class="rewrite-version-heading-actions"><button type="button" data-generate-voice>小与AI语音</button><button type="button" data-new-version>＋ 新增版本</button></div></div>'+
      '<div class="rewrite-version-tabs" role="group" aria-label="稿件版本">'+selected.transcriptVersions.map(item => '<button type="button" data-version="'+esc(item.id)+'" class="'+(item.id === version.id?'active':'')+'" aria-pressed="'+(item.id === version.id)+'">'+esc(item.label)+'</button>').join('')+'</div>'+
      '<p class="rewrite-transcript-note">'+(original?'V0 是 ASR／OCR 原稿，正文只读；可标注逐行类型。':'新版本从上一版复制；稿件、Prompt 和逐行类型修改后自动保存。')+' 视频总时长：'+(selected.videoDurationSeconds ? esc(selected.videoDurationSeconds)+' 秒' : '未设置，编辑稿件后填写秒数')+'。逐行字数不计空格、标点和时间戳；时间仅供估算。全选复制稿件文本框不会带上两侧辅助栏。</p>'+
      '<div class="rewrite-voice-panel"><span class="rewrite-voice-status" role="status">'+(version.voiceAudio ? '当前版本的小与语音已生成' : '当前版本尚未生成语音')+'</span>'+(version.voiceAudio ? (version.voiceAudio.segments?.length ? version.voiceAudio.segments : [{url:version.voiceAudio.url,label:'完整音频'}]).map(segment=>'<div class="rewrite-voice-segment"><span>'+esc(segment.label)+(segment.characters?' · '+segment.characters+'字':'')+'</span><audio controls preload="none" src="'+esc(segment.url)+'"></audio><a href="'+esc(segment.url)+'" download>下载 WAV</a></div>').join('') : '')+'</div>'+
      comparisonHtml()+
      '<div class="rewrite-version-grid"><div class="rewrite-line-panel"><p class="rewrite-line-caption">行 · 字 · 预计起止</p><div class="rewrite-line-table" role="table" aria-label="所有行的字数与估算时间"></div></div><div class="rewrite-version-inputs"><label class="rewrite-script-label">稿件内容<textarea class="rewrite-version-text" rows="20" wrap="off" spellcheck="false" '+(original?'readonly':'')+'>'+esc(version.text)+'</textarea></label><label>此版本的 Prompt<textarea class="rewrite-version-prompt" rows="6" placeholder="记录生成或修改此版本使用的 Prompt" '+(original?'readonly':'')+'>'+esc(version.prompt || '')+'</textarea></label>'+
      '<div class="rewrite-version-actions"><span class="rewrite-version-status" role="status">已自动保存</span></div></div><div class="rewrite-line-type-panel"><p class="rewrite-line-caption">逐行类型 · 可多选</p><div class="rewrite-line-types" aria-label="稿件逐行类型"></div></div></div>'+
      '<dialog class="rewrite-remotion-dialog"><form method="dialog"><h3>Remotion Prompt</h3><p class="rewrite-remotion-line"></p><label>该行的 Remotion Prompt<textarea class="rewrite-remotion-prompt" rows="8" placeholder="描述这一行对应的 Remotion 画面、动画或镜头"></textarea></label><div class="rewrite-remotion-actions"><button type="button" data-remotion-cancel>取消</button><button type="button" data-remotion-save>保存 Prompt</button></div></form></dialog></section>';
  }
  function timeLabel(seconds) {
    if (!Number.isFinite(seconds)) return '—';
    const minutes = Math.floor(seconds / 60);
    return String(minutes).padStart(2,'0')+':'+(seconds % 60).toFixed(1).padStart(4,'0');
  }
  function lineStats(text, original) {
    const lines = text.split(/\r?\n/);
    const hasStamps = original && lines.some(line => /^\[\d{2}:\d{2}\]/.test(line));
    const rows = lines.map((line,index) => {
      const match = line.match(/^\[(\d{2}):(\d{2})\]\s*/);
      const body = match ? line.slice(match[0].length) : line;
      return {lineNo:index+1, chars:Array.from(body.replace(/[\s\p{P}\p{S}]/gu,'')).length,
        stamp:match ? Number(match[1])*60+Number(match[2]) : null, isMetadata:hasStamps && !match};
    });
    const duration = Number(selected.videoDurationSeconds);
    const total = rows.reduce((sum,row)=>sum+row.chars,0);
    let elapsed = 0;
    rows.forEach((row,index) => {
      if (hasStamps && row.stamp !== null) {
        row.start = row.stamp;
        row.end = rows.slice(index+1).find(next => next.stamp !== null)?.stamp ?? (duration > 0 ? duration : NaN);
      } else if (row.isMetadata) {
        row.start = row.end = NaN;
      } else {
        row.start = duration > 0 && total ? elapsed/total*duration : NaN;
        elapsed += row.chars;
        row.end = duration > 0 && total ? elapsed/total*duration : NaN;
      }
    });
    return rows;
  }
  function refreshLineStats() {
    const editor = panel.querySelector('.rewrite-version-text');
    const table = panel.querySelector('.rewrite-line-table');
    const types = panel.querySelector('.rewrite-line-types');
    if (!editor || !table || !types) return;
    const rows = lineStats(editor.value,activeVersion()?.id === 'v0');
    table.innerHTML = rows.map(row => '<div class="rewrite-line-row" role="row" data-line="'+row.lineNo+'"><span>'+row.lineNo+'</span><span>'+row.chars+'</span><span>'+timeLabel(row.start)+'–'+timeLabel(row.end)+'</span></div>').join('');
    types.innerHTML = rows.map(row => {
      const annotation = lineAnnotationsDraft[row.lineNo-1] || {tags:[],remotionPrompt:''};
      return '<div class="rewrite-line-type-row" data-line="'+row.lineNo+'">'+Object.entries(lineTags).map(([key,label]) => '<button type="button" class="rewrite-line-tag '+(annotation.tags.includes(key)?'active':'')+'" data-tag="'+key+'" aria-pressed="'+annotation.tags.includes(key)+'" aria-label="第 '+row.lineNo+' 行 '+label+'">'+label+'</button>').join('')+
        (annotation.tags.includes('remotion')?'<button type="button" class="rewrite-remotion-edit" data-remotion-edit aria-label="编辑第 '+row.lineNo+' 行 Remotion Prompt">编辑</button>':'')+'</div>';
    }).join('');
    table.scrollTop = editor.scrollTop;
    types.scrollTop = editor.scrollTop;
  }
  function reconcileAnnotations(nextLines) {
    const old = draftLines, annotations = lineAnnotationsDraft;
    if (old.length === nextLines.length) {draftLines = nextLines; return;}
    let prefix = 0, suffix = 0;
    while (prefix < old.length && prefix < nextLines.length && old[prefix] === nextLines[prefix]) prefix++;
    while (suffix < old.length-prefix && suffix < nextLines.length-prefix && old[old.length-1-suffix] === nextLines[nextLines.length-1-suffix]) suffix++;
    const middle = nextLines.length-prefix-suffix, oldMiddle = old.length-prefix-suffix;
    lineAnnotationsDraft = [...annotations.slice(0,prefix), ...Array.from({length:middle},(_,i) => i < oldMiddle ? annotations[prefix+i] : {tags:[],remotionPrompt:''}), ...annotations.slice(old.length-suffix)];
    draftLines = nextLines;
  }
  function queueVersionSave() {
    versionDirty = true;
    const status = panel.querySelector('.rewrite-version-status');
    if (status) status.textContent = '待保存';
    clearTimeout(versionTimer);
    versionTimer = setTimeout(() => {saveVersion().catch(error => notice(error.message,true));},600);
  }
  async function saveVersion() {
    clearTimeout(versionTimer);
    if (!versionDirty || !selected) return versionSaving;
    const manuscriptId = selected.id, versionId = activeVersion().id;
    const editor = panel.querySelector('.rewrite-version-text'), promptEditor = panel.querySelector('.rewrite-version-prompt');
    if (!editor || !promptEditor) return versionSaving;
    const text = editor.value, prompt = promptEditor.value, lineAnnotations = structuredClone(lineAnnotationsDraft);
    versionDirty = false;
    const status = panel.querySelector('.rewrite-version-status');
    if (status) status.textContent = '保存中…';
    versionSaving = versionSaving.then(async () => {
      const item = await api(versionId === 'v0' ? {action:'save_line_annotations',id:manuscriptId,versionId,lineAnnotations} : {action:'save_version',id:manuscriptId,versionId,text,prompt,lineAnnotations});
      if (selected?.id === manuscriptId) {
        const hadVoice = Boolean(activeVersion()?.voiceAudio);
        adopt(item);
        if (hadVoice && !activeVersion()?.voiceAudio && editor.isConnected) {
          const voicePanel = panel.querySelector('.rewrite-voice-panel');
          if (voicePanel) voicePanel.innerHTML = '<span class="rewrite-voice-status" role="status">稿件已修改，请重新生成语音</span>';
        }
        if (editor.isConnected && activeVersion()?.id === versionId) {
          if (editor.value !== text || promptEditor.value !== prompt || JSON.stringify(lineAnnotationsDraft) !== JSON.stringify(lineAnnotations)) {versionDirty = true; queueVersionSave();}
          else {
            if (status) status.textContent = '已自动保存';
            const comparisonStatus=panel.querySelector('.rewrite-compare-summary');
            if(comparisonStatus && comparisonView().enabled) comparisonStatus.textContent='已自动保存到磁盘';
          }
        }
      }
      return item;
    });
    try {return await versionSaving;} catch(error) {versionSaving = Promise.resolve(); versionDirty = true; if(status) status.textContent = '保存失败'; const comparisonStatus=panel.querySelector('.rewrite-compare-summary'); if(comparisonStatus)comparisonStatus.textContent='保存失败，修改仍在编辑区；请重试后再切换版本。'; throw error;}
  }
  async function flushVersion() {checkMotionTable();clearTimeout(versionTimer); await flushComparisonLeft(); await versionSaving; if(versionDirty) await saveVersion(); await flushAnalysis(); await flushStoryboards();}
  async function requestVoice(body) {
    const response = await fetch('/api/rewrites/voice', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '小与语音生成失败');
    return result;
  }
  async function watchVoiceJob(manuscriptId,versionId,jobId='') {
    if (selected?.id !== manuscriptId || activeVersion()?.id !== versionId) return;
    const query = new URLSearchParams({id:manuscriptId,versionId});
    if (jobId) query.set('job',jobId);
    try {
      const response = await fetch('/api/rewrites/voice-status?'+query);
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || '语音状态读取失败');
      showVoiceState(result,manuscriptId,versionId);
    } catch(error) {
      const status = panel.querySelector('.rewrite-voice-status');
      if (status) status.textContent = error.message;
    }
  }
  function showVoiceState(result,manuscriptId,versionId) {
    if (selected?.id !== manuscriptId || activeVersion()?.id !== versionId) return;
    const status = panel.querySelector('.rewrite-voice-status');
    const button = panel.querySelector('[data-generate-voice]');
    if (!status || !button) return;
    if (result.state === 'done' && result.audio) {
      button.disabled = false;
      if (activeVersion().voiceAudio?.url !== result.audio.url) {
        activeVersion().voiceAudio = result.audio;
        render();
      } else status.textContent = '当前版本的小与语音已生成';
    } else if (result.state === 'error') {
      button.disabled = false;
      status.textContent = '生成失败：'+(result.error || '未知错误');
    } else if (result.state === 'stale') {
      button.disabled = false;
      status.textContent = result.error || '稿件已修改，请重新生成语音';
    } else if (result.state === 'queued' || result.state === 'running') {
      button.disabled = true;
      status.textContent = result.state === 'queued' ? '小与语音排队中…' : '小与语音生成中，较长稿件可能需要几分钟…';
      clearTimeout(voicePollTimer);
      voicePollTimer = setTimeout(() => watchVoiceJob(manuscriptId,versionId,result.jobId),2000);
    }
  }
  function bindVersionEditor() {
    const editor = panel.querySelector('.rewrite-version-text');
    if (!editor) return;
    const promptEditor = panel.querySelector('.rewrite-version-prompt');
    const lineTable = panel.querySelector('.rewrite-line-table');
    const lineTypes = panel.querySelector('.rewrite-line-types');
    draftLines = editor.value.split(/\r?\n/);
    lineAnnotationsDraft = draftLines.map((_,i) => ({tags:[...(activeVersion().lineAnnotations?.[i]?.tags || [])],remotionPrompt:activeVersion().lineAnnotations?.[i]?.remotionPrompt || ''}));
    editor.addEventListener('input', () => {reconcileAnnotations(editor.value.split(/\r?\n/)); refreshLineStats(); queueVersionSave();});
    editor.addEventListener('blur', () => flushVersion().catch(error => notice(error.message,true)));
    editor.addEventListener('scroll', () => {lineTable.scrollTop = editor.scrollTop; lineTypes.scrollTop = editor.scrollTop;});
    lineTable.addEventListener('scroll', () => {editor.scrollTop = lineTable.scrollTop; lineTypes.scrollTop = lineTable.scrollTop;});
    lineTypes.addEventListener('scroll', () => {editor.scrollTop = lineTypes.scrollTop; lineTable.scrollTop = lineTypes.scrollTop;});
    lineTypes.addEventListener('click', event => {
      const button = event.target.closest('button'), row = button?.closest('[data-line]');
      if (!row) return;
      const index = Number(row.dataset.line)-1, annotation = lineAnnotationsDraft[index];
      if (button.dataset.tag) {
        const tag = button.dataset.tag;
        annotation.tags = annotation.tags.includes(tag) ? annotation.tags.filter(item => item !== tag) : [...annotation.tags,tag];
        refreshLineStats(); queueVersionSave();
      } else if (button.hasAttribute('data-remotion-edit')) {
        const dialog = panel.querySelector('.rewrite-remotion-dialog');
        dialog.dataset.line = String(index);
        dialog.querySelector('.rewrite-remotion-line').textContent = '第 '+(index+1)+' 行：'+draftLines[index].slice(0,100);
        dialog.querySelector('.rewrite-remotion-prompt').value = annotation.remotionPrompt;
        dialog.showModal();
      }
    });
    const dialog = panel.querySelector('.rewrite-remotion-dialog');
    dialog.querySelector('[data-remotion-cancel]').onclick = () => dialog.close();
    dialog.querySelector('[data-remotion-save]').onclick = () => {
      lineAnnotationsDraft[Number(dialog.dataset.line)].remotionPrompt = dialog.querySelector('.rewrite-remotion-prompt').value;
      queueVersionSave(); dialog.close();
    };
    promptEditor.addEventListener('input', queueVersionSave);
    promptEditor.addEventListener('blur', () => flushVersion().catch(error => notice(error.message,true)));
    panel.querySelector('[data-generate-voice]').onclick = async () => {
      try {
        await flushVersion();
        const manuscriptId = selected.id, versionId = activeVersion().id;
        panel.querySelector('.rewrite-voice-status').textContent = '正在提交小与语音任务…';
        showVoiceState(await requestVoice({id:manuscriptId,versionId}),manuscriptId,versionId);
      } catch(error) {const status=panel.querySelector('.rewrite-voice-status');if(status) status.textContent='生成失败：'+error.message;}
    };
    panel.querySelector('[data-new-version]').onclick = async () => {
      try {await flushVersion(); const baseId=activeVersion().id; adopt(await api({action:'create_version',id:selected.id,baseVersionId:baseId})); comparisonView().leftId=baseId; render(); notice('已新增 '+activeVersion().label);}
      catch(error) {notice(error.message,true);}
    };
    panel.querySelectorAll('[data-version]').forEach(button => button.onclick = async () => {
      if (button.dataset.version === activeVersion().id) return;
      try {await flushVersion(); adopt(await api({action:'select_version',id:selected.id,versionId:button.dataset.version})); render();}
      catch(error) {notice(error.message,true);}
    });
    refreshLineStats();
    bindComparison();
    watchVoiceJob(selected.id,activeVersion().id);
  }
  function detail() {
    if (!selected) return '<div class="rewrite-empty"><h2>选择稿件</h2><p>从左侧三级菜单打开稿件，或创建知识库、项目和稿件。</p></div>';
    const statusLabel = {research:'研究中',draft:'二创草稿',reviewed:'已复核'}[selected.status] || selected.status;
    return '<div class="rewrite-heading"><div><p class="rewrite-path">'+esc(data.knowledgeBases.find(k => k.id === selected.knowledgeBaseId)?.name)+' / '+esc(data.knowledgeBases.find(k => k.id === selected.knowledgeBaseId)?.projects.find(p => p.id === selected.projectId)?.name)+'</p><h2>'+esc(selected.title)+' <details class="rewrite-source-info"><summary aria-label="原稿基础信息" title="悬浮查看原稿信息">ⓘ</summary><div><p>'+esc(selected.sourceAuthor)+' · '+esc(selected.sourcePublishedAt)+' · '+esc(statusLabel)+'</p><a href="'+esc(selected.sourceUrl)+'" target="_blank" rel="noopener noreferrer">打开原素材 ↗</a>'+(selected.transcriptUrl?' · <a href="'+esc(selected.transcriptUrl)+'" target="_blank" rel="noopener noreferrer">逐字稿文件 ↗</a>':'')+'<p>'+esc(selected.sourceNotes)+'</p></div></details></h2></div><div class="rewrite-actions"><button data-action="edit">编辑稿件</button><button data-action="delete">删除稿件</button></div></div>'+
      versionEditorHtml()+
      keys.map(key => '<section class="rewrite-card"><div class="rewrite-card-head"><h3>'+names[key]+'</h3>'+hearts(key,selected.sections[key])+'</div><ul>'+lines(selected.sections[key].text)+'</ul>'+
        (key === 'cases' && selected.assets.length ? '<div class="rewrite-assets">'+assetCards()+'</div>' : '')+
        (key === 'similar' ? '<div class="rewrite-platforms">'+similarCards()+'</div>' : '')+
        (selected.sections[key].scoreNote ? '<p class="rewrite-score-note">评分说明：'+esc(selected.sections[key].scoreNote)+'</p>' : '')+'</section>').join('')+
      '<section class="rewrite-card"><h3>二创稿</h3><div class="rewrite-copy">'+esc(selected.secondCreation || '待撰写')+'</div></section>';
  }
  function render() {
    if (!panel || !data) return;
    clearTimeout(voicePollTimer);
    panel.className = 'workspace-section rewrite-section';
    panel.innerHTML = '<div class="rewrite-layout"><aside class="rewrite-sidebar"><h1>洗稿</h1><p>原稿拆解 · 相似素材 · 二创</p><button data-add="kb">＋ 新建知识库</button><nav aria-label="知识库、项目和稿件">'+tree()+'</nav></aside><main class="rewrite-main"><p class="rewrite-notice" role="status"></p>'+detail()+'</main></div>';
    panel.querySelectorAll('[data-manuscript]').forEach(node => node.onclick = async () => {try {await flushVersion(); selected = data.manuscripts.find(x => x.id === node.dataset.manuscript); editing=false; setSelected(selected.id); render();} catch(error) {notice(error.message,true);}});
    panel.querySelectorAll('summary button').forEach(node => node.onclick = event => { event.preventDefault(); event.stopPropagation(); hierarchy(node.dataset); });
    panel.querySelectorAll('[data-add]').forEach(node => node.onclick = () => add(node.dataset));
    panel.querySelectorAll('[data-rate]').forEach(node => node.onclick = async () => {try {await flushVersion(); await rate(node.dataset);} catch(error) {notice(error.message,true);}});
    if (selected) {
      bindVersionEditor();
      bindManuscriptTabs();
      const info=panel.querySelector('.rewrite-source-info');
      if(info){info.onmouseenter=()=>info.open=true;info.onmouseleave=()=>{if(!info.contains(document.activeElement))info.open=false;};info.addEventListener('keydown',e=>{if(e.key==='Escape'){info.open=false;info.querySelector('summary').focus();}});}

      panel.querySelector('[data-action="edit"]').onclick = async () => {try {await flushVersion(); edit();} catch(error) {notice(error.message,true);}};
      panel.querySelector('[data-action="delete"]').onclick = () => remove();
    }
  }
  function formField(name,label,value,rows=0) {
    return '<label>'+label+(rows ? '<textarea name="'+name+'" rows="'+rows+'">'+esc(value)+'</textarea>' : '<input name="'+name+'" '+(name==='videoDurationSeconds'?'type="number" min="0.001" max="86400" step="0.001" ':'')+'value="'+esc(value)+'">')+'</label>';
  }
  function formHtml(record) {
    const options = data.knowledgeBases.flatMap(kb => kb.projects.map(p => '<option value="'+esc(kb.id)+'|'+esc(p.id)+'" '+(kb.id === record.knowledgeBaseId && p.id === record.projectId ? 'selected':'')+'>'+esc(kb.name)+' / '+esc(p.name)+'</option>')).join('');
    return '<form class="rewrite-form"><h2>'+(record.id?'编辑稿件':'新建稿件')+'</h2><label>所属项目<select name="location">'+options+'</select></label>'+formField('title','稿件标题',record.title)+formField('sourceUrl','原素材链接',record.sourceUrl)+formField('transcriptUrl','逐字稿文件链接',record.transcriptUrl)+formField('sourceAuthor','原作者',record.sourceAuthor)+formField('sourcePublishedAt','原发布时间',record.sourcePublishedAt)+
      '<label>状态<select name="status"><option value="research" '+(record.status==='research'?'selected':'')+'>研究中</option><option value="draft" '+(record.status==='draft'?'selected':'')+'>二创草稿</option><option value="reviewed" '+(record.status==='reviewed'?'selected':'')+'>已复核</option></select></label>'+formField('videoDurationSeconds','原视频时长（秒，用于逐行时间估算）',record.videoDurationSeconds ?? '')+formField('sourceNotes','来源与核实说明',record.sourceNotes,3)+(record.id?'':formField('transcript','V0 原稿（ASR／字幕 OCR；图文稿填页面 OCR）',record.transcript,16))+
      keys.map(key => '<fieldset><legend>'+names[key]+'</legend>'+formField('section_'+key,'逐条写，每行一点',record.sections[key].text,5)+formField('note_'+key,'评分说明',record.sections[key].scoreNote,2)+'</fieldset>').join('')+
      '<fieldset><legend>场景／截图</legend>'+formField('assets','每行：名称 | 图片链接 | 说明',record.assets.map(x => [x.label,x.url,x.note].join(' | ')).join('\n'),4)+'</fieldset>'+
      Object.entries(platforms).map(([key,label]) => '<fieldset><legend>'+label+'相似素材</legend>'+formField('similar_'+key,'每行：标题 | 原帖链接 | 相似观点 | 数据／核实状态',(record.similar[key]||[]).map(x => [x.title,x.url,x.point,x.evidence].join(' | ')).join('\n'),4)+'</fieldset>').join('')+
      formField('secondCreation','二创稿／改写角度',record.secondCreation,10)+
      '<div class="rewrite-form-actions"><button type="button" data-cancel>取消</button><button type="submit">保存到本地</button></div></form>';
  }
  function parseRows(text, count) {
    return text.split('\n').filter(x => x.trim()).map(line => {
      const values = line.split('|').map(x => x.trim());
      if (values.length < 2) throw new Error('列表行至少需要名称和链接，用 | 分隔');
      while (values.length < count) values.push('');
      return values;
    });
  }
  function edit(record = selected) {
    editing = true;
    panel.querySelector('.rewrite-main').innerHTML = '<p class="rewrite-notice" role="status"></p>'+formHtml(record);
    const form = panel.querySelector('.rewrite-form');
    form.querySelector('[data-cancel]').onclick = () => {editing=false; render();};
    form.onsubmit = async event => {
      event.preventDefault();
      try {
        const values = new FormData(form);
        const [knowledgeBaseId,projectId] = values.get('location').split('|');
        const duration = values.get('videoDurationSeconds').trim();
        const manuscript = {title:values.get('title'),status:values.get('status'),sourceUrl:values.get('sourceUrl'),transcriptUrl:values.get('transcriptUrl'),transcript:record.id?record.transcript:values.get('transcript'),videoDurationSeconds:duration?Number(duration):null,sourceAuthor:values.get('sourceAuthor'),sourcePublishedAt:values.get('sourcePublishedAt'),sourceNotes:values.get('sourceNotes'),
          sections:Object.fromEntries(keys.map(key => [key,{text:values.get('section_'+key),score:record.sections[key].score,scoreNote:values.get('note_'+key)}])),
          assets:parseRows(values.get('assets'),3).map(([label,url,note]) => ({label,url,note})),
          similar:Object.fromEntries(Object.keys(platforms).map(key => [key,parseRows(values.get('similar_'+key),4).map(([title,url,point,evidence]) => ({title,url,point,evidence}))])),
          secondCreation:values.get('secondCreation')};
        const item = await api({action:record.id?'update':'create',id:record.id,knowledgeBaseId,projectId,manuscript});
        setSelected(item.id); editing=false; await load(); notice('已保存到本地文件');
      } catch (error) { notice(error.message,true); }
    };
  }
  async function rate({rate,score}) {
    if (!selected) return;
    const manuscript = JSON.parse(JSON.stringify(selected));
    manuscript.sections[rate].score = score ? Number(score) : null;
    try { await api({action:'update',id:selected.id,manuscript}); await load(); notice('人工评分已保存'); }
    catch (error) { notice(error.message,true); }
  }
  async function add(info) {
    try {
      if (info.add === 'manuscript') {const record=blank(); record.knowledgeBaseId=info.kb;record.projectId=info.project;edit(record);return;}
      const name = prompt(info.add === 'kb' ? '知识库名称' : '项目名称');
      if (!name) return;
      await api({action:info.add === 'kb'?'create_kb':'create_project',name,knowledgeBaseId:info.kb});
      await load(); notice('已创建');
    } catch(error) {notice(error.message,true);}
  }
  async function hierarchy(info) {
    const kind=info.kind, op=info.op, id=info.id;
    try {
      if (op === 'rename') {
        const name=prompt(kind==='kb'?'知识库名称':'项目名称');
        if (!name) return;
        await api({action:kind==='kb'?'rename_kb':'rename_project',id,projectId:id,knowledgeBaseId:info.kb,name});
      } else {
        const label=kind==='kb'?'知识库':'项目';
        if (!confirm('删除'+label+'？请先删除其下的稿件和子项目。')) return;
        await api({action:kind==='kb'?'delete_kb':'delete_project',id,projectId:id,knowledgeBaseId:info.kb});
      }
      await load(); notice('已保存');
    } catch(error) {notice(error.message,true);}
  }
  async function remove() {
    if (!confirm('确定删除稿件“'+selected.title+'”？此操作不可撤销。')) return;
    try {await api({action:'delete',id:selected.id}); setSelected(null); await load(); notice('稿件已删除');}
    catch(error) {notice(error.message,true);}
  }
  window.addEventListener('workspace-section-change', event => {
    if (event.detail.section !== 'rewrites') return;
    panel=event.detail.panel; load().catch(error => {panel.textContent=error.message;});
  });
  window.addEventListener('popstate', () => {if (panel && !panel.hidden && !editing) load().catch(()=>{});});
  window.addEventListener('beforeunload', event => {
    try{checkMotionTable();}catch(_){event.preventDefault();event.returnValue='';}
    if([...analysisDrafts.values(),...storyboardDrafts.values()].some(draft=>draft.dirty)){event.preventDefault();event.returnValue='';}
  });
  if (new URL(location.href).searchParams.get('section') === 'rewrites') {
    panel = document.querySelector('.workspace-section');
    if (panel) load().catch(error => {panel.textContent=error.message;});
  }
})();
