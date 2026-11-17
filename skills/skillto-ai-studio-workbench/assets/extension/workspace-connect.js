/* Runs only on loopback pages. Pair through the same-origin page, never an
   unauthenticated extension endpoint or a token in a URL/window message. */
(async () => {
  if (window.top !== window || location.hostname !== '127.0.0.1') return;
  try {
    const health = await fetch('/api/workbench/health', {signal: AbortSignal.timeout(4000)});
    if (!health.ok || !['skillto-ai-studio-workbench', 'skillto-int-workbench'].includes((await health.json()).service)) return;
    const response = await fetch('/api/workbench/pairing', {signal: AbortSignal.timeout(4000)});
    if (!response.ok) return;
    const {token} = await response.json();
    await chrome.runtime.sendMessage({type: 'workbench-connect', endpoint: location.origin, token});
  } catch { /* An unrelated loopback page is not the workspace. */ }
})();
