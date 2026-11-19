/* Report tree and Metabase guest dashboard in the existing local workspace. */
(() => {
  let panel, catalog, selected, timer, showArchived = false, lineageData = {};
  let scriptPromise;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const api = async (path, body) => {
    const response = await fetch(path, body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || '请求失败');
    return value;
  };
  const urlReport = () => new URL(location.href).searchParams.get('report');
  const setUrl = id => {
    const url = new URL(location.href);
    if (id) url.searchParams.set('report', id);
    else url.searchParams.delete('report');
    history.pushState(null, '', url);
  };
  function notice(message, bad = false) {
    const box = panel?.querySelector('.report-notice');
    if (box) { box.textContent = message; box.classList.toggle('error', bad); }
  }
  async function refresh() {
    [catalog, lineageData] = await Promise.all([api('/api/reports/catalog'), api('/api/reports/lineage')]);
    selected = catalog.reports.find(r => r.id === urlReport() && r.status === 'active') || null;
    render();
  }
  function projectOptions(kbId) {
    const kb = catalog.knowledgeBases.find(k => k.id === kbId);
    return (kb?.projects || []).map(p => '<option value="' + esc(p.id) + '">' + esc(p.name) + '</option>').join('');
  }
  function tree() {
    const reports = catalog.reports.filter(r => showArchived || r.status === 'active');
    return catalog.knowledgeBases.map(kb => {
      const projects = kb.projects.map(project => {
        const entries = reports.filter(r => r.knowledgeBaseId === kb.id && r.projectId === project.id);
        return '<details open><summary>' + esc(project.name) + '</summary><div class="report-tree-items">' +
          entries.map(r => '<button type="button" data-report="' + esc(r.id) + '" class="' +
            (selected?.id === r.id ? 'active' : '') + '">' + esc(r.name) +
            (r.status === 'archived' ? ' <small>已归档</small>' : '') + '</button>').join('') +
          (entries.length ? '' : '<span class="report-tree-empty">暂无报表</span>') + '</div></details>';
      }).join('');
      return '<details open><summary>' + esc(kb.name) + '</summary>' + projects + '</details>';
    }).join('');
  }
  function render() {
    if (!panel) return;
    const firstKb = catalog.knowledgeBases[0];
    panel.className = 'workspace-section report-section';
    panel.innerHTML = '<div class="report-layout"><aside class="report-sidebar">' +
      '<h1>报表</h1><button type="button" data-action="new">＋ 新建报表</button>' +
      '<button type="button" data-action="refresh">↻ 刷新报表数据</button>' +
      '<label class="report-archive-toggle"><input type="checkbox" data-action="archived" ' +
      (showArchived ? 'checked' : '') + '> 显示已归档</label>' +
      '<nav aria-label="知识库、项目和报表">' + (tree() || '<p>还没有报表。点击“新建报表”。</p>') + '</nav></aside>' +
      '<section class="report-main"><p class="report-notice" role="status"></p>' +
      (selected ? '<div class="report-heading"><div><p class="report-path">' +
        esc(catalog.knowledgeBases.find(k => k.id === selected.knowledgeBaseId)?.name) + ' / ' +
        esc(catalog.knowledgeBases.find(k => k.id === selected.knowledgeBaseId)?.projects.find(p => p.id === selected.projectId)?.name) +
        '</p><h2>' + esc(selected.name) + '</h2></div><div class="report-actions">' +
        '<button type="button" data-action="edit">重命名／移动</button>' +
        '<button type="button" data-action="archive">归档</button>' +
        '<a target="_blank" rel="noopener noreferrer" href="' + esc(catalog.metabaseUrl) +
        '/dashboard/' + encodeURIComponent(selected.metabaseDashboardId) + '">在 Metabase 编辑</a></div></div>' +
        (selected.sourceTableId === lineageData.sourceTableId ? '<details class="report-lineage"><summary>数据来源与统计口径</summary><p>' +
        esc(lineageData.sources || '待补充') + '</p><p>' + esc(lineageData.methods || '待补充') +
        '</p><p>' + esc(lineageData.rules || '待补充') + '</p><p>' +
        esc(lineageData.destinations || '待补充') + '</p></details>' : '') +
        '<div class="report-embed" id="reportEmbed">加载图表中…</div>'
        : '<div class="report-empty"><h2>选择报表</h2><p>从左侧三级菜单打开报表，或创建一个新报表。</p></div>') +
      '</section></div>' +
      '<dialog class="report-dialog" aria-labelledby="reportDialogTitle"><form method="dialog"><h2 id="reportDialogTitle">报表信息</h2>' +
      '<label>名称<input name="name" required maxlength="120"></label>' +
      '<label>知识库<select name="kb"></select></label>' +
      '<label>项目<select name="project"></select></label>' +
      '<label>说明<textarea name="description"></textarea></label>' +
      '<div class="report-dialog-buttons"><button value="cancel">取消</button><button value="save">保存</button></div>' +
      '</form></dialog>';
    panel.querySelectorAll('[data-report]').forEach(button => button.addEventListener('click', () => {
      const report = catalog.reports.find(r => r.id === button.dataset.report);
      if (report?.status === 'archived') return restore(report);
      setUrl(button.dataset.report); selected = report; render();
    }));
    panel.querySelector('[data-action="new"]').onclick = () => form(null, firstKb?.id);
    panel.querySelector('[data-action="refresh"]').onclick = async () => {
      try {
        notice('正在从已采集数据更新报表…');
        const result = await api('/api/reports/refresh', {});
        notice(result.message || '报表数据已更新。');
        if (selected) mountEmbed(selected);
      } catch (error) { notice(error.message, true); }
    };
    panel.querySelector('[data-action="archived"]').onchange = event => {
      showArchived = event.target.checked; render();
    };
    if (selected) {
      panel.querySelector('[data-action="edit"]').onclick = () => form(selected);
      panel.querySelector('[data-action="archive"]').onclick = () => archive(selected);
      mountEmbed(selected);
    }
  }
  async function ensureEmbedScript() {
    if (!scriptPromise) {
      window.metabaseConfig = {isGuest: true, instanceUrl: catalog.metabaseUrl};
      scriptPromise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = new URL('app/embed.js', catalog.metabaseUrl).href;
        script.onload = resolve; script.onerror = () => {
          scriptPromise = null;
          script.remove();
          reject(new Error('Metabase 嵌入脚本加载失败'));
        };
        document.head.append(script);
      });
    }
    return scriptPromise;
  }
  async function mountEmbed(report) {
    clearTimeout(timer);
    const target = panel.querySelector('#reportEmbed');
    try {
      const [token] = await Promise.all([api('/api/reports/embed?id=' + encodeURIComponent(report.id)), ensureEmbedScript()]);
      if (selected?.id !== report.id || !target.isConnected) return;
      const element = document.createElement('metabase-dashboard');
      element.setAttribute('token', token.token);
      element.setAttribute('with-title', 'false');
      target.replaceChildren(element);
      timer = setTimeout(() => { if (selected?.id === report.id) mountEmbed(report); }, 8 * 60 * 1000);
    } catch (error) {
      if (target.isConnected) target.textContent = error.message;
      notice(error.message, true);
    }
  }
  function form(report, kbId) {
    const dialog = panel.querySelector('.report-dialog');
    const fields = dialog.querySelector('form');
    const kb = fields.elements.kb, project = fields.elements.project;
    kb.innerHTML = catalog.knowledgeBases.map(k => '<option value="' + esc(k.id) + '">' + esc(k.name) + '</option>').join('');
    kb.value = report?.knowledgeBaseId || kbId || '';
    const updateProjects = () => { project.innerHTML = projectOptions(kb.value); };
    kb.onchange = updateProjects; updateProjects();
    project.value = report?.projectId || project.options[0]?.value || '';
    fields.elements.name.value = report?.name || '';
    fields.elements.description.value = report?.description || '';
    dialog.showModal();
    dialog.onclose = async () => {
      if (dialog.returnValue !== 'save') return;
      try {
        const result = await api('/api/reports', {action: report ? 'update' : 'create',
          reportId: report?.id, name: fields.elements.name.value,
          description: fields.elements.description.value,
          knowledgeBaseId: kb.value, projectId: project.value,
          sourceTableId: report?.sourceTableId || new URL(location.href).searchParams.get('table')});
        setUrl(result.id); await refresh(); notice('报表已保存。');
      } catch (error) { notice(error.message, true); }
    };
  }
  async function archive(report) {
    if (!confirm('归档报表“' + report.name + '”？可在“显示已归档”中恢复。')) return;
    try { await api('/api/reports', {action:'archive', reportId: report.id}); setUrl(null); await refresh(); notice('报表已归档。'); }
    catch (error) { notice(error.message, true); }
  }
  async function restore(report) {
    if (!confirm('恢复报表“' + report.name + '”？')) return;
    try { await api('/api/reports', {action:'restore', reportId: report.id}); setUrl(report.id); await refresh(); notice('报表已恢复。'); }
    catch (error) { notice(error.message, true); }
  }
  async function mount(nextPanel) {
    panel = nextPanel;
    try { await refresh(); }
    catch (error) {
      if (panel !== nextPanel) return;
      const message = document.createElement('p');
      message.className = 'report-notice error';
      message.textContent = '报表加载失败：' + error.message;
      const retry = document.createElement('button');
      retry.className = 'button';
      retry.textContent = '重试';
      retry.onclick = () => mount(nextPanel);
      panel.replaceChildren(message, retry);
    }
  }
  window.addEventListener('workspace-section-change', event => {
    if (event.detail.section === 'reports') mount(event.detail.panel);
    else { clearTimeout(timer); panel = null; }
  });
  window.addEventListener('popstate', () => {
    if (new URL(location.href).searchParams.get('section') === 'reports' && panel) refresh();
  });
  if (new URL(location.href).searchParams.get('section') === 'reports') {
    const existing = document.querySelector('.workspace-section');
    if (existing) mount(existing);
  }
})();
