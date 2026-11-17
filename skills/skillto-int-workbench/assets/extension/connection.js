/* The workspace page supplies its live origin; 8880 is the launcher default. */
function workbenchOrigin(value) {
  try {
    const url = new URL(value);
    if (url.protocol === 'http:' && url.hostname === '127.0.0.1' && !url.username && !url.password) return url.origin;
  } catch {}
  return null;
}
async function findWorkbench(preferred, request = fetch) {
  const candidates = [...new Set([workbenchOrigin(preferred), 'http://127.0.0.1:8880'].filter(Boolean))];
  for (const origin of candidates) {
    try {
      const response = await request(`${origin}/api/workbench/health`, {signal: AbortSignal.timeout(3000)});
      if (response.ok && (await response.json()).service === 'skillto-int-workbench') return origin;
    } catch { /* Try the other supported service, without replaying any mutation. */ }
  }
  throw Error('未找到可用的拉片服务，请启动本地工作台后重试');
}
