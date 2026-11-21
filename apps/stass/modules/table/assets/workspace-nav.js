/* Shared top-level navigation for the local content workspace. */
(() => {
  const sections = [
    {id: 'tables', label: '表格'},
    {id: 'reports', label: '报表'},
    {id: 'rewrites', label: '洗稿'},
    {id: 'motions', label: 'AI资产'},
    {id: 'docs', label: '文档'},
    {id: 'schedule', label: '排稿'},
    {id: 'tools', label: '工具'}
  ];
  const shell = document.querySelector('.app-shell');


  document.title = 'Skillto-AI-Studio';
  const nav = document.createElement('nav');
  nav.className = 'workspace-nav';
  nav.setAttribute('aria-label', '工作区导航');
  const brand = document.createElement('span');
  brand.className = 'workspace-nav-brand';
  const logo = document.createElement('img');
  logo.src = '/studio-wordmark.png';
  logo.alt = 'Skillto.ai · 个人工作台';
  brand.append(logo);
  const links = document.createElement('div');
  links.className = 'workspace-nav-links';
  for (const section of sections) {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.section = section.id;
    button.textContent = section.label;
    links.append(button);
  }
  nav.append(brand, links);
  const publicLink = (label, href) => {
    const link = document.createElement('a');
    link.className = 'workspace-link'; link.textContent = label; link.href = href;
    return link;
  };
  links.append(publicLink('设置 · 组件与技能','/STASS/features.html'),
               publicLink('关于','/STASS/about'));
  const browsersLink = document.createElement('a');
  browsersLink.href = '/browser-users';
  browsersLink.textContent = '浏览器用户';
  browsersLink.className = 'workspace-link';
  links.append(browsersLink);
  const breakdownLink = document.createElement('a');
  breakdownLink.href = '/breakdowns';
  breakdownLink.textContent = '拉片';
  breakdownLink.className = 'workspace-link';
  browsersLink.dataset.workView = 'browser';
  breakdownLink.dataset.workView = 'breakdowns';
  links.insertBefore(breakdownLink, links.querySelector('[data-section="reports"]'));

  let lastRevision;
  async function applyWorkFilters() {
    const response = await fetch('/STASS/api/v1/work-navigation');
    if (!response.ok) return;
    const prefs = await response.json();
    if (lastRevision === prefs.revision) return;
    const changed = lastRevision !== undefined;
    lastRevision = prefs.revision;
    if (prefs.groups !== null) document.querySelector('.profile-welcome')?.remove();
    if (changed) window.dispatchEvent(new Event('work-profile-updated'));
    for (const link of links.querySelectorAll('[data-work-view], [data-section]')) {
      const view = link.dataset.workView || link.dataset.section;
      const visible = prefs.groups === null || prefs.views.includes(view) || (view === 'motions' && prefs.views.includes('assetLibrary')) ||
        (view === 'browser' && prefs.groups.includes('social'));
      link.hidden = !visible;
    }
    if (prefs.groups === null && shell && location.search === '' &&
        !localStorage.getItem('studio.profileWelcome.dismissed') && !document.querySelector('.profile-welcome')) {
      const banner=document.createElement('aside'), close=document.createElement('button');
      banner.className='profile-welcome'; close.textContent='关闭';
      close.onclick=()=>{localStorage.setItem('studio.profileWelcome.dismissed','1');banner.remove();};
      banner.append(publicLink('按我的工作整理界面','/STASS/features.html'),close);nav.after(banner);
    }
  }
  const refreshWork = () => applyWorkFilters().catch(console.warn);
  refreshWork();
  window.addEventListener('focus',refreshWork);
  window.addEventListener('storage',refreshWork);
  setInterval(() => { if (!document.hidden) refreshWork(); }, 5000);

  // Reports and breakdowns share a mobile directory. Their lists can be
  // replaced by module renderers, so resolve the current list when opening.
  const directory = document.createElement('button');
  directory.className = 'directory-toggle';
  directory.type = 'button';
  directory.textContent = '☰';
  directory.setAttribute('aria-label', '打开目录');
  directory.setAttribute('aria-expanded', 'false');
  nav.prepend(directory);
  const shade = document.createElement('button');
  shade.className = 'directory-shade';
  shade.type = 'button';
  shade.setAttribute('aria-label', '关闭目录');
  document.body.append(shade);
  function closeDirectory() {
    if (!document.body.classList.contains('directory-open')) return;
    document.body.classList.remove('directory-open');
    directory.setAttribute('aria-expanded', 'false');
    directory.focus();
  }
  directory.onclick = () => {
    const side = document.querySelector('.report-sidebar, .workspace > aside');
    if (!side) return;
    side.id ||= 'workspace-directory';
    directory.setAttribute('aria-controls', side.id);
    directory.setAttribute('aria-expanded', 'true');
    document.body.classList.add('directory-open');
    (side.querySelector('button, input, summary') || shade).focus();
  };
  shade.onclick = closeDirectory;
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape' || document.querySelector('dialog[open]')) return;
    closeDirectory();
    const rewriteShade = document.querySelector('.rewrite-directory-shade');
    if (rewriteShade?.getClientRects().length) rewriteShade.click();
    if (document.querySelector('#sidebar.open')) {
      document.querySelector('#closeSidebar').click();
      document.querySelector('#openSidebar').focus();
    }
  });
  document.addEventListener('click', event => {
    if (event.target.closest('.report-tree-items button, #records .record')) closeDirectory();
  }, true);
  matchMedia('(max-width: 760px)').addEventListener('change', closeDirectory);

  const panel = document.createElement('main');
  panel.className = 'workspace-section';
  panel.hidden = true;
  panel.setAttribute('aria-live', 'polite');
  if (shell) { document.body.insertBefore(nav, shell); shell.after(panel); }
  else {
    const oldHeader = document.querySelector('body > header');
    if (oldHeader && location.pathname === '/breakdowns') oldHeader.hidden = true;
    document.body.prepend(nav);
    for (const button of links.querySelectorAll('button[data-section]')) {
      const link = document.createElement('a');
      link.className = 'workspace-link';
      link.href = button.dataset.section === 'tables' ? '/?section=tables' : '/?section=' + button.dataset.section;
      link.dataset.workView = button.dataset.section; link.textContent = button.textContent; button.replaceWith(link);
    }
    const activePath = location.pathname === '/breakdowns' ? '/breakdowns' : '/browser-users';
    const active = links.querySelector('a[href="' + activePath + '"]');
    if (active) { active.classList.add('active'); active.setAttribute('aria-current', 'page'); }
    if (document.getElementById('quick-actions')) {document.title = '我的工作台'; return;}
    document.title = (location.pathname === '/breakdowns' ? '拉片' : '浏览器用户') + ' · Skillto-AI-Studio';
    return;
  }

  function externalLink(label, href, primary = false) {
    const link = document.createElement('a');
    link.href = href;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.className = primary ? 'workspace-link primary' : 'workspace-link';
    link.textContent = label;
    return link;
  }

  async function renderDocuments(inner, status) {
    const endpoint = '/STASS/api/v1/document-links';
    const list = document.createElement('div');
    list.className = 'document-list';
    const form = document.createElement('form');
    form.hidden = true;
    const fields = [
      ['文档名称', 'text', 120],
      ['HTTPS 文档链接', 'url', 2048]
    ].map(([labelText, type, maxLength]) => {
      const label = document.createElement('label');
      label.textContent = labelText + ' ';
      const input = document.createElement('input');
      Object.assign(input, {type, required: true, maxLength});
      label.append(input);
      form.append(label);
      return input;
    });
    const add = document.createElement('button');
    add.textContent = '添加文档';
    form.append(add);
    inner.append(list, form);

    async function request(change) {
      const response = await fetch(endpoint, change ? {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(change)
      } : undefined);
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || '文档链接暂不可用。');
      return result;
    }

    function show(items) {
      list.replaceChildren();
      status.textContent = items.length ? '' : '暂无文档。可以添加自己的飞书或其他 HTTPS 文档链接。';
      for (const item of items) {
        const row = document.createElement('article');
        const remove = document.createElement('button');
        remove.textContent = '移除';
        remove.onclick = async () => {
          remove.disabled = true;
          try {
            show(await request({action: 'remove', id: item.id}));
          } catch (error) {
            status.textContent = error.message;
            remove.disabled = false;
          }
        };
        row.append(externalLink(item.title, item.url), remove);
        list.append(row);
      }
    }

    form.onsubmit = async event => {
      event.preventDefault();
      add.disabled = true;
      try {
        show(await request({action: 'add', title: fields[0].value, url: fields[1].value}));
        form.reset();
      } catch (error) {
        status.textContent = error.message;
      } finally {
        add.disabled = false;
      }
    };

    status.textContent = '正在读取文档链接…';
    try {
      show(await request());
      form.hidden = false;
    } catch (error) {
      status.textContent = error.message;
    }
  }

  function renderPanel(section) {
    panel.className = 'workspace-section';
    panel.replaceChildren();
    const inner = document.createElement('div');
    inner.className = 'workspace-section-inner';
    const eyebrow = document.createElement('p');
    eyebrow.className = 'workspace-eyebrow';
    eyebrow.textContent = 'Skillto-AI-Studio';
    const title = document.createElement('h1');
    const description = document.createElement('p');
    description.className = 'workspace-section-description';
    inner.append(eyebrow, title, description);
    if (section === 'reports') {
      title.textContent = '报表';
      description.textContent = '加载报表中…';
    } else if (section === 'rewrites') {
      title.textContent = '洗稿';
      description.textContent = '加载稿件中…';
    } else if (section === 'motions') {
      title.textContent = 'AI资产';
      description.textContent = '加载资产库中…';
    } else if (section === 'docs') {
      title.textContent = '文档';
      renderDocuments(inner, description);
    } else {
      title.textContent = section === 'schedule' ? '排稿' : '工具';
      description.textContent = section === 'schedule' ? '排稿功能尚未接入。' : '工具功能尚未接入。';
    }
    panel.append(inner);
  }

  function showSection(section) {
    const valid = sections.some(item => item.id === section) ? section : 'tables';
    closeDirectory();
    panel.dataset.view = valid;
    shell.hidden = valid !== 'tables';
    panel.hidden = valid === 'tables';
    for (const button of links.children) {
      const active = button.dataset.section === valid;
      button.classList.toggle('active', active);
      if (active) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    }
    if (valid !== 'tables') renderPanel(valid);
    window.dispatchEvent(new CustomEvent('workspace-section-change', {detail: {section: valid, panel}}));
  }

  function sectionFromUrl() {
    return new URL(window.location.href).searchParams.get('section') || 'tables';
  }
  links.addEventListener('click', event => {
    const button = event.target.closest('button[data-section]');
    if (!button) return;
    const url = new URL(window.location.href);
    url.searchParams.set('section', button.dataset.section);
    history.pushState(null, '', url);
    showSection(button.dataset.section);
  });
  window.addEventListener('popstate', () => showSection(sectionFromUrl()));
  showSection(sectionFromUrl());
})();
