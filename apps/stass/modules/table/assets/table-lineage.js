/* Table-wide provenance panel for the local review page. */
(() => {
  const labels = {
    sources: '数据从哪里来',
    methods: '怎么采集或整理',
    rules: '筛选、计算与更新规则',
    destinations: '数据会去哪里'
  };
  let displayedId = null;
  const panel = document.createElement('details');
  panel.id = 'tableLineage';
  panel.className = 'table-lineage';
  panel.innerHTML = `<summary>采集与整理策略、规则 <span id="lineageCompleteness"></span></summary>
    <div class="lineage-body"><div id="lineageRead"></div>
    <form id="lineageForm" hidden>${Object.entries(labels).map(([key, label]) =>
      `<label>${label}<textarea name="${key}" rows="3" maxlength="12000"></textarea></label>`).join('')}
      <div class="lineage-actions"><button type="submit">保存说明</button><button type="button" id="lineageCancel">取消</button></div></form>
    <button type="button" id="lineageEdit">编辑说明</button><p id="lineageMessage" role="status"></p></div>`;

  function render() {
    const table = state.table;
    panel.hidden = !table;
    if (!table) return;
    if (displayedId !== table.id) {
      panel.open = false;
      panel.querySelector('#lineageForm').hidden = true;
      panel.querySelector('#lineageEdit').hidden = false;
      displayedId = table.id;
    }
    const data = table.dataLineage || {};
    const complete = Object.keys(labels).filter(key => (data[key] || '').trim()).length;
    panel.querySelector('#lineageCompleteness').textContent = complete === 4 ? '已记录' : '待补充';
    const read = panel.querySelector('#lineageRead');
    read.replaceChildren();
    for (const [key, label] of Object.entries(labels)) {
      const section = document.createElement('section');
      const title = document.createElement('strong'); title.textContent = label;
      const body = document.createElement('p'); body.textContent = data[key]?.trim() || '待补充：历史数据未记录此项';
      section.append(title, body); read.append(section);
    }
    for (const key of Object.keys(labels)) panel.querySelector(`[name="${key}"]`).value = data[key] || '';
  }

  panel.querySelector('#lineageEdit').onclick = () => {
    panel.querySelector('#lineageRead').hidden = true;
    panel.querySelector('#lineageForm').hidden = false;
    panel.querySelector('#lineageEdit').hidden = true;
  };
  panel.querySelector('#lineageCancel').onclick = () => {
    panel.querySelector('#lineageRead').hidden = false;
    panel.querySelector('#lineageForm').hidden = true;
    panel.querySelector('#lineageEdit').hidden = false;
    render();
  };
  panel.querySelector('#lineageForm').onsubmit = async event => {
    event.preventDefault();
    const tableId = state.table?.id;
    if (!tableId) return;
    const values = Object.fromEntries(Object.keys(labels).map(key => [key, panel.querySelector(`[name="${key}"]`).value]));
    const button = panel.querySelector('[type="submit"]'); button.disabled = true;
    try {
      const dataLineage = await api('/api/lineage', {tableId, dataLineage: values});
      if (state.table?.id === tableId) {
        state.table.dataLineage = dataLineage;
        cacheTable(state.table);
        panel.querySelector('#lineageRead').hidden = false;
        panel.querySelector('#lineageForm').hidden = true;
        panel.querySelector('#lineageEdit').hidden = false;
        panel.querySelector('#lineageMessage').textContent = '已保存到表格文件';
        render();
      }
    } catch (error) {
      panel.querySelector('#lineageMessage').textContent = `保存失败：${error.message}`;
    } finally { button.disabled = false; }
  };

  document.querySelector('.workspace-head').after(panel);
  new MutationObserver(render).observe(document.querySelector('#tableTitle'), {childList:true, characterData:true, subtree:true});
  render();
})();
