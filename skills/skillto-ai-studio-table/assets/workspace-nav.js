/* Shared top-level navigation for the local content workspace. */
(() => {
  const wikiUrl = 'https://ocnlp85xlhx0.feishu.cn/wiki/Js2MwOj6SiC9AXkRiL8cxhtQnrb';
  const documentUrl = 'https://ocnlp85xlhx0.feishu.cn/wiki/Wkv5wgrU3iDaokkuTlAcDuk7noh';
  const sections = [
    {id: 'tables', label: '表格'},
    {id: 'reports', label: '报表'},
    {id: 'rewrites', label: '洗稿'},
    {id: 'motions', label: 'Motion 模版'},
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
  const browsersLink = document.createElement('a');
  browsersLink.href = '/browser-users';
  browsersLink.textContent = '浏览器用户';
  browsersLink.className = 'workspace-link';
  links.append(browsersLink);
  const breakdownLink = document.createElement('a');
  breakdownLink.href = '/breakdowns';
  breakdownLink.textContent = '拉片';
  breakdownLink.className = 'workspace-link';
  links.insertBefore(breakdownLink, links.children[2]);

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
      link.href = button.dataset.section === 'tables' ? '/' : '/?section=' + button.dataset.section;
      link.textContent = button.textContent; button.replaceWith(link);
    }
    const activePath = location.pathname === '/breakdowns' ? '/breakdowns' : '/browser-users';
    const active = links.querySelector('a[href="' + activePath + '"]');
    if (active) { active.classList.add('active'); active.setAttribute('aria-current', 'page'); }
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

  function renderPanel(section) {
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
      title.textContent = 'Motion 模版';
      description.textContent = '加载模版中…';
    } else if (section === 'docs') {
      title.textContent = '文档';
      description.textContent = '飞书知识库中的研究文档与账号名单。';
      const card = document.createElement('div');
      card.className = 'workspace-card';
      const heading = document.createElement('h2');
      heading.textContent = 'AI教学账号名单｜自然流与付费流';
      const detail = document.createElement('p');
      detail.textContent = '2026-11-07 整理 · 自然流 64 个 · 付费流 10 个';
      const actions = document.createElement('div');
      actions.className = 'workspace-card-actions';
      actions.append(
        externalLink('打开账号名单', documentUrl, true),
        externalLink('打开飞书知识库', wikiUrl)
      );
      card.append(heading, detail, actions);
      inner.append(card);
    } else {
      title.textContent = section === 'schedule' ? '排稿' : '工具';
      description.textContent = section === 'schedule' ? '排稿功能尚未接入。' : '工具功能尚未接入。';
    }
    panel.append(inner);
  }

  function showSection(section) {
    const valid = sections.some(item => item.id === section) ? section : 'tables';
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
    if (button.dataset.section === 'tables') url.searchParams.delete('section');
    else url.searchParams.set('section', button.dataset.section);
    history.pushState(null, '', url);
    showSection(button.dataset.section);
  });
  window.addEventListener('popstate', () => showSection(sectionFromUrl()));
  showSection(sectionFromUrl());
})();
