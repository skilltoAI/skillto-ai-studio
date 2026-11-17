(async () => {
  const response = await fetch('/api/workbench/extension-info');
  if (!response.ok) throw Error('无法读取插件安装信息');
  const info = await response.json();
  document.getElementById('installVersion').textContent = `${info.name || "SKillto.ai|工作台"} · 版本 ${info.version}`;
  document.getElementById('extensionPath').value = info.directory;
  document.getElementById('copyPath').onclick = async () => {
    try { await navigator.clipboard.writeText(info.directory); document.getElementById('installNotice').textContent = '插件目录已复制'; }
    catch { document.getElementById('extensionPath').select(); document.getElementById('installNotice').textContent = '请按 Ctrl+C 复制插件目录'; }
  };
  document.getElementById('openManager').onclick = async () => {
    const result = await fetch('/api/workbench/extension-setup', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
    document.getElementById('installNotice').textContent = result.ok ? '已打开安装入口；更新已有插件只需点击「重新加载」。' : '请手动在 Chrome 地址栏打开 chrome://extensions';
  };
})().catch(error => { document.getElementById('installNotice').textContent = error.message; });
