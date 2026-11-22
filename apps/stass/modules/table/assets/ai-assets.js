/* AI asset navigation. Motion keeps its existing store, controls and production boundaries. */
(() => {
  const libraries = [['motion','Motion 模版'],['red-white','AI红白模库'],['jianying','剪映AI模版库']];
  const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const topicParam = 'assetTopic';
  const localTopicPrefix = 'local:';
  const embedOrigin = 'https://www.skillto.ai';
  const allowedParentOrigin = 'http://127.0.0.1:8080';
  const challengeIdPattern = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
  let panel, catalog, dialog, mediaObserver, epoch=0;
  const mediaUrl = (item,download=false) => '/api/ai-assets/media/'+item.id+(download?'?download=1':'');
  function videoCard(item) {
    if (!playable(item)) return '<p>视频访问待验证</p>';
    const src = esc(mediaUrl(item));
    const poster = item.hasCover ? ' poster="' + src + '?cover=1"' : '';
    return '<video class="asset-video" src="' + src + '"' + poster
      + ' controls playsinline preload="none" aria-label="' + esc(item.title) + '视频"></video>';
  }
  const playable = item => ['local-file', 'source-page'].includes(item.playback);
  const accessLabel = item => ({'local-file':'本机视频', 'source-page':'飞书视频 · 免登录播放'})[item.playback] || '访问待验证';
  const copyIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V4a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h4"/></svg>';
  const downloadIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4"/></svg>';
  function releaseMedia(root) {root?.querySelectorAll('video').forEach(video=>{video.pause();video.removeAttribute('src');video.load();});}
  const library = () => {
    const id = new URL(location.href).searchParams.get('assetLibrary');
    return libraries.some(([key])=>key===id) ? id : 'motion';
  };
  let cloudMount;
  function unmount() {
    cloudMount?.abort();
    epoch++;
    mediaObserver?.disconnect();
    releaseMedia(panel);
    window.StudioMotion?.unmount();
    if (dialog) {const previous=dialog;dialog=null;previous.close();previous.remove();}
  }
  function details(item, opener) {
    dialog=document.createElement('dialog');
    dialog.className='asset-details';
    dialog.setAttribute('aria-labelledby','assetDetailTitle');
    dialog.innerHTML=`<header><h2 id="assetDetailTitle">${esc(item.title)}</h2><button type="button" data-close aria-label="关闭资产详情">×</button></header><p>${esc(item.description)}</p><div class="asset-detail-actions">${item.references.map(ref=>`<a href="${esc(ref.url)}" target="_blank" rel="noopener noreferrer">${esc(ref.title)} ↗</a>`).join('')}<button type="button" data-copy aria-label="复制提示词" title="复制提示词">${copyIcon}</button></div><p class="asset-access">${accessLabel(item)}</p><h3>提示词</h3><pre>${esc(item.prompt||'来源尚未提供提示词')}</pre><p role="status"></p>`;
    dialog.querySelector('[data-close]').onclick=()=>dialog.close();
    dialog.querySelector('[data-copy]').onclick=async()=>{
      try {await navigator.clipboard.writeText(item.prompt);dialog.querySelector('[role=status]').textContent='提示词已复制';}
      catch {dialog.querySelector('[role=status]').textContent='复制失败，请选择正文手动复制';}
    };
    const opened=dialog;
    dialog.addEventListener('close',()=>{opened.remove();if(dialog===opened)dialog=null;if(opener.isConnected)opener.focus();},{once:true});
    document.body.append(dialog);dialog.showModal();
  }
  function renderLibrary(content, id) {
    const entries=catalog.items.filter(item=>item.library===id);
    const groupBySource = id === 'red-white';
    const sourceUrls = new Map(catalog.sources.map(source => [source.url, source.id]));
    const memberships = new Map();
    const counts = new Map();
    if (groupBySource) {
      for (const item of entries) {
        const ids = new Set(item.references.map(ref => sourceUrls.get(ref.url.split('#')[0])));
        ids.add(item.topicId || item.sourceId);
        ids.delete(undefined);
        memberships.set(item.id, ids);
        for (const sourceId of ids) counts.set(sourceId, (counts.get(sourceId) || 0) + 1);
      }
    }
    const sources = catalog.sources.filter(source => counts.has(source.id));
    const topics = [...(catalog.topics || []).filter(topic => topic.library === id), ...sources];
    const requestedTopic = new URL(location.href).searchParams.get(topicParam);
    const sourceId = requestedTopic?.startsWith(localTopicPrefix) ? requestedTopic.slice(localTopicPrefix.length) : requestedTopic;
    let topic = topics.some(entry => entry.id === sourceId) ? sourceId : '';
    content.innerHTML=`<section class="asset-library"><header class="asset-heading"><div><h1>${esc(libraries.find(([key])=>key===id)[1])}</h1><p>${id==='red-white'?'本机视频、公开动作参考与提示词':'剪映AI模版收藏'}</p></div><input type="search" aria-label="搜索AI资产" placeholder="搜索名称、动作或提示词"></header><div class="asset-count" role="status"></div><div class="asset-grid"></div>${id==='red-white'&&sources.length?`<details class="asset-sources"><summary>资料来源与访问状态</summary>${sources.map(source=>`<div><a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${esc(source.title)}</a><span>${source.access==='anonymous'?'免登录可读':source.access==='login-required'?'需要公开分享权限':'尚未验证'}</span><p>${esc(source.note)}</p></div>`).join('')}</details>`:''}</section>`;
    if (groupBySource) {
      const main = content.firstElementChild;
      const layout = document.createElement('div');
      layout.className = 'asset-topic-layout';
      layout.innerHTML = `<nav class="asset-topic-nav" aria-label="红白模 Topic"><h2>Topic</h2>${[{id:"", title:"全部本机红白模"}, ...topics].map(source => `<button type="button" data-topic="${esc(source.id)}"${source.id === topic ? ' aria-current="true"' : ''}><span>${esc(source.title)}</span><span class="asset-topic-count">${source.id ? (counts.get(source.id) || 0) : entries.length}</span></button>`).join("")}</nav>`;
      const nav = layout.firstElementChild;
      content.replaceChildren(layout);
      layout.append(main);
      nav.addEventListener('click', event => {
        const button = event.target.closest('[data-topic]');
        if (!button || (button.dataset.topic === topic && button.hasAttribute('aria-current'))) return;
        topic = button.dataset.topic;
        const url = new URL(location.href);
        url.searchParams.set(topicParam, localTopicPrefix + topic);
        history.pushState(null, '', url);
        for (const choice of nav.querySelectorAll('[data-topic]')) {
          if (choice === button) choice.setAttribute('aria-current', 'true');
          else choice.removeAttribute('aria-current');
        }
        draw();
      });
    }
    const search=content.querySelector('input');
    const grid=content.querySelector('.asset-grid');
    function draw() {
      const q=search.value.trim().toLocaleLowerCase();
      const list = entries.filter(item =>
        (!topic || memberships.get(item.id).has(topic)) &&
        [item.title, item.description, item.prompt].join(' ').toLocaleLowerCase().includes(q)
      );
      content.querySelector('.asset-count').textContent=`${list.length} 组资产`;
      mediaObserver?.disconnect();
      releaseMedia(grid);
      grid.innerHTML=list.length?list.map(item=>`<article class="asset-card" data-asset="${esc(item.id)}"><div class="asset-card-title"><h2>${esc(item.title)}</h2><div class="asset-card-icons"><button type="button" data-copy="${esc(item.id)}" aria-label="复制${esc(item.title)}提示词" title="复制提示词">${copyIcon}</button>${playable(item)?`<a class="asset-download" href="${mediaUrl(item,true)}" download="${esc(item.filename)}" aria-label="下载${esc(item.title)}视频" title="下载视频">${downloadIcon}</a>`:''}</div></div>${videoCard(item)}<p class="asset-media-error" hidden>视频暂不可用，请检查文件或打开来源。</p><p class="asset-description">${esc(item.description)}</p><div class="asset-prompt-label">提示词<button type="button" data-detail="${esc(item.id)}">展开</button></div><pre class="asset-prompt" tabindex="0" aria-label="${esc(item.title)}提示词">${esc(item.prompt||'来源尚未提供提示词')}</pre><footer><span class="asset-access">${accessLabel(item)}</span>${item.sourceUrl ? `<a href="${esc(item.sourceUrl)}" target="_blank" rel="noopener noreferrer">来源 ↗</a>` : ''}</footer><span class="asset-card-status" role="status"></span></article>`).join(''):`<div class="asset-empty"><h2>${q?'没有匹配的资产':'暂时为空'}</h2><p>${q?'试试其他名称或动作关键词。':id==='jianying'?'这里将收纳剪映AI模版。':'本机上传或公开来源导入完成后，资产会显示在这里。'}</p></div>`;
      grid.querySelectorAll('video').forEach(video=>{
        video.onerror=()=>{video.closest('article').querySelector('.asset-media-error').hidden=false;};
        video.onplay=()=>grid.querySelectorAll('video').forEach(other=>{if(other!==video)other.pause();});
      });
      mediaObserver=new IntersectionObserver(entries=>entries.forEach(entry=>{
        if(entry.isIntersecting){entry.target.preload='metadata';entry.target.load();mediaObserver.unobserve(entry.target);}
      }),{rootMargin:'100px'});
      grid.querySelectorAll('video:not([poster])').forEach(video=>mediaObserver.observe(video));
    }
    search.oninput=draw;
    grid.onclick=async event=>{
      const detail=event.target.closest('[data-detail]');if(detail)details(entries.find(item=>item.id===detail.dataset.detail),detail);
      const copy=event.target.closest('[data-copy]');if(!copy)return;
      const item=entries.find(item=>item.id===copy.dataset.copy);
      const status=copy.closest('article').querySelector('[role=status]');
      try {await navigator.clipboard.writeText(item.prompt);status.textContent='提示词已复制';}
      catch {status.textContent='复制失败，请选择正文手动复制';}
    };
    draw();
  }
  async function mountOfficial(content, current) {
    const nav = content.querySelector('.asset-topic-nav');
    if (!nav) return;
    const local = content.querySelector('.asset-library');
    const group = document.createElement('section');
    const heading = document.createElement('h2');
    heading.textContent = '官方专题';
    group.className = 'asset-official-topics';
    nav.prepend(group);
    group.append(heading);
    const localTitle = nav.querySelector(':scope > h2');
    if (localTitle) localTitle.textContent = '本机';
    const online = document.createElement('section');
    online.className = 'asset-official-page';
    online.hidden = true;
    local.after(online);
    let mounted;
    const clear = () => {
      mounted?.abort();
      online.replaceChildren();
      online.hidden = true;
      local.hidden = false;
    };
    const lifecycle = new AbortController();
    cloudMount = lifecycle;
    lifecycle.signal.addEventListener('abort',clear,{once:true});
    nav.addEventListener('click',e => {
      if (e.target.closest('[data-topic]')) {
        clear();
        group.querySelector('[aria-current]')?.removeAttribute('aria-current');
      }
    },{signal:lifecycle.signal});
    const retry = () => {
      const button = document.createElement('button');
      button.textContent = '重试官方专题';
      button.onclick = () => mount(panel);
      group.append(button);
    };
    try {
      const res = await fetch('/api/ai-assets/official',{signal:lifecycle.signal});
      if (!res.ok) throw Error();
      const catalog = await res.json();
      if (current !== epoch) return;
      if (!catalog.topics.length) {
        const empty = document.createElement('p');
        empty.textContent = '暂无官方专题';
        group.append(empty);
        return;
      }
      const aliases = {'415e11d55370f0178b7577ff':'sto_4ba1c5e9-116d-5f0e-9098-4fd38d4e7c81',
                       '749a6a5b32fb5db8e00c3c23':'sto_bbb5b7e0-777b-5f62-ac4d-5e9070fe0c49'};
      const select = async (entry,button,push) => {
        clear();
        mediaObserver?.disconnect();
        releaseMedia(local);
        local.hidden = true;
        online.hidden = false;
        delete online.dataset.ready;
        mounted = new AbortController();
        const signal = mounted.signal;
        const url = new URL(location.href);
        url.searchParams.set(topicParam,entry.id);
        if (push) history.pushState(null,'',url);
        else history.replaceState(null,'',url);
        nav.querySelectorAll('[aria-current]').forEach(node=>node.removeAttribute('aria-current'));
        button.setAttribute('aria-current','true');
        const link=document.createElement('a');
        const dest='https://www.skillto.ai/red-white/topics/'+entry.id;
        link.href=dest;link.target='_blank';link.rel='noopener noreferrer';link.textContent='在浏览器打开';
        const status=document.createElement('p');status.setAttribute('role','status');status.textContent='正在打开官方专题…';
        online.append(link,status);
        try {
          const res=await fetch('/api/ai-assets/official?topic='+encodeURIComponent(entry.id),{signal});
          if (!res.ok) throw Error();
          const descriptor=await res.json();
          if (descriptor.protocolVersion!==1 || descriptor.externalUrl!==dest || descriptor.url!==`https://www.skillto.ai/red-white/embed/topics/${entry.id}`) throw Error();
          if (location.origin!==allowedParentOrigin) {
            status.textContent='此工作台地址可通过浏览器打开官方专题。';
            return;
          }
          const frame=document.createElement('iframe');
          frame.title='红白模专题 · '+entry.title;frame.referrerPolicy='no-referrer';
          frame.setAttribute('sandbox','allow-scripts allow-same-origin allow-downloads allow-popups allow-popups-to-escape-sandbox');frame.allow='fullscreen; clipboard-write';
          frame.src=descriptor.url;
          const mountId=crypto.randomUUID();
          const init=()=>frame.contentWindow?.postMessage({type:'skillto.redWhite.init',version:1,topicId:entry.id,mountId},embedOrigin);
          frame.addEventListener('load',init,{signal});
          const timer=setInterval(init,500);
          const timeout=setTimeout(()=>{clearInterval(timer);status.textContent='嵌入超时，可在浏览器打开或重新选择专题。';},12000);
          const stop=()=>{clearInterval(timer);clearTimeout(timeout);};
          signal.addEventListener('abort',stop,{once:true});
          window.addEventListener('message',e=>{
            const m=e.data;
            if(e.source!==frame.contentWindow || e.origin!==embedOrigin || m?.version!==1 || m.topicId!==entry.id || m.mountId!==mountId)return;
            if(m.type==='skillto.redWhite.ready'){
              stop();
              status.textContent='';
              online.dataset.ready='true';
            }
            if(m.type==='skillto.redWhite.resize' && Number.isSafeInteger(m.height) && m.height>0 && m.height<=250000){
              frame.style.height=m.height+'px';
            }
            if(m.type==='skillto.redWhite.openOnline' && m.intent==='purchase'){
              link.dataset.purchase='true';
              link.href=dest+'?buy=1';link.textContent='在 Skillto.ai 购买专题';
            }
            if(m.type==='skillto.redWhite.openOnline' && typeof m.challengeId==='string' && challengeIdPattern.test(m.challengeId)){
              link.dataset.purchase='true';
              link.href=dest+'?challenge='+encodeURIComponent(m.challengeId);link.textContent='在浏览器购买或关联已购专题';
            }
          },{signal});
          online.append(frame);
        } catch(error){if(!signal.aborted)status.textContent='嵌入失败，可在浏览器打开。';}
      };
      const requested=new URL(location.href).searchParams.get(topicParam);
      const candidate=aliases[requested] || requested;
      const localSelected = requested?.startsWith(localTopicPrefix) ||
        (requested && Array.from(nav.querySelectorAll('[data-topic]')).some(b=>b.dataset.topic===requested));
      const active=catalog.topics.some(r=>r.id===candidate) ? candidate : localSelected ? null : catalog.defaultTopicId;
      for (const entry of catalog.topics) {
        const button=document.createElement('button');
        button.textContent=entry.title+(entry.access==='paid'?' · 付费':' · 免费');
        button.onclick=()=>select(entry,button,true);
        group.append(button);
        if (entry.id===active) select(entry,button,false);
      }
    } catch(error){if(!lifecycle.signal.aborted)retry();}
  }
  async function mount(target) {
    unmount();panel=target;
    const current=epoch,id=library();
    panel.className='workspace-section ai-assets-shell';
    panel.innerHTML=`<div class="asset-tabs" role="tablist" aria-label="AI资产分类">${libraries.map(([key,label])=>`<button role="tab" type="button" data-library="${key}" aria-selected="${key===id}" tabindex="${key===id?'0':'-1'}" aria-controls="assetContent">${label}</button>`).join('')}</div><div id="assetContent" role="tabpanel"></div>`;
    const content=panel.querySelector('#assetContent');
    const tabs=panel.querySelector('.asset-tabs');
    const switchTo=key=>{
      const url=new URL(location.href);url.searchParams.set('section','motions');url.searchParams.set('assetLibrary',key);
      history.pushState(null,'',url);mount(panel);panel.querySelector(`[data-library="${key}"]`).focus();
    };
    tabs.onclick=event=>{const button=event.target.closest('[data-library]');if(button&&button.dataset.library!==id)switchTo(button.dataset.library);};
    tabs.onkeydown=event=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      event.preventDefault();const index=libraries.findIndex(([key])=>key===id);
      const next=event.key==='Home'?0:event.key==='End'?2:(index+(event.key==='ArrowRight'?1:2))%3;
      switchTo(libraries[next][0]);
    };
    if(id==='motion'){await window.StudioMotion.mount(content);return;}
    content.innerHTML='<p class="asset-empty" role="status">正在读取资产库…</p>';
    try {
      const response=await fetch('/api/ai-assets/catalog');
      if(!response.ok)throw Error('资产库读取失败');
      const result=await response.json();if(current!==epoch)return;
      catalog=result;renderLibrary(content,id);if (id==='red-white') mountOfficial(content,current);
    } catch(error) {if(current===epoch)content.innerHTML=`<div class="asset-empty" role="alert">${esc(error.message)}<p>请刷新重试。</p></div>`;}
  }
  window.addEventListener('workspace-section-change',event=>{if(event.detail.section==='motions')mount(event.detail.panel);else unmount();});
  if(new URL(location.href).searchParams.get('section')==='motions')mount(document.querySelector('.workspace-section'));
})();
