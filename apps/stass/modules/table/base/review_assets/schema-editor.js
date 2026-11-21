(() => {
  let definitions = [];
  let initialValues = [];
  let deleteButton;
  const previousPreview = videoPreview;
  videoPreview = row => previousPreview(row).replaceAll('title="在抖音播放"', 'title="打开原视频"');
  const previousVideos = openVideos;
  openVideos = row => {
    previousVideos(row);
    document.querySelectorAll('#videosList .play-link').forEach(link => link.title = '打开原视频');
  };
  openRow = function(row = null) {
    state.row = row;
    definitions = [...(state.table.fields || [])];
    for (const [name, value] of Object.entries(row?.fields || {})) {
      if (!definitions.some(field => field.name === name)) definitions.push({name, label: name, type: typeof value === 'number' ? 'number' : typeof value === 'boolean' ? 'boolean' : 'text'});
    }
    $('#rowDialogTitle').textContent = row ? '编辑记录' : '添加记录';
    deleteButton ??= $('#deleteRow');
    const form = $('#rowForm');
    form.innerHTML = definitions.map((field, index) => {
      const value = row?.fields[field.name];
      const name = `field${index}`;
      let control;
      if (field.type === 'boolean') control = `<select name="${name}"><option value="">未设置</option><option value="true" ${value === true ? 'selected' : ''}>是</option><option value="false" ${value === false ? 'selected' : ''}>否</option></select>`;
      else if (field.type === 'single_choice') control = `<select name="${name}"><option value="">未设置</option>${[...new Set([...(field.options || []), ...(value == null ? [] : [value])])].map(option => `<option ${option === value ? 'selected' : ''}>${escapeHtml(option)}</option>`).join('')}</select>`;
      else if (field.type === 'number') control = `<input name="${name}" type="number" step="any" value="${escapeHtml(value ?? '')}">`;
      else control = `<textarea name="${name}" rows="${['short_video_info','multiple_choice'].includes(field.type) ? 4 : 2}">${escapeHtml(value == null ? '' : typeof value === 'object' ? JSON.stringify(value, null, 2) : value)}</textarea>`;
      return `<label class="field-label">${escapeHtml(field.label || field.name)}${control}</label>`;
    }).join('') + '<div class="modal-actions"><button class="button primary" type="submit">保存</button></div>';
    if (row && deleteButton) form.querySelector('.modal-actions').prepend(deleteButton);
    initialValues = definitions.map((_, index) => form.elements[`field${index}`].value);
    $('#rowDialog').showModal();
  };
  const previousSelect = selectTable;
  selectTable = async function(entry) {
    await previousSelect(entry);
    document.title = state.table.title || entry.table.name;
    $('#addRowButton').hidden = false;
    $('#addRowButton').textContent = '+ 添加记录';
    $('#searchInput').placeholder = '搜索记录';
    document.querySelector('.sidebar-head small').textContent = '本地资料';
    document.querySelector('.metrics').style.display = 'none';
  };
  document.addEventListener('DOMContentLoaded', () => {
    $('#rowForm').onsubmit = async event => {
      event.preventDefault();
      try {
        const fields = {};
        definitions.forEach((field, index) => {
          const value = event.target.elements[`field${index}`].value;
          if (state.row && value === initialValues[index]) return;
          fields[field.name] = value === '' ? null : field.type === 'number' ? Number(value) : field.type === 'boolean' ? value === 'true' : ['short_video_info','multiple_choice'].includes(field.type) ? JSON.parse(value) : value;
        });
        if (!state.row || Object.keys(fields).length) await api('/api/row', {tableId: state.table.id, action: state.row ? 'update' : 'create', rowId: state.row?.id, fields});
        $('#rowDialog').close();
        await refreshTable();
        notify('已保存到本地文件');
      } catch (error) { notify(error.message, true); }
    };
  });
})();
