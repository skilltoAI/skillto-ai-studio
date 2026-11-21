/* Self-contained MAIN-world scan. Only media for the current item is returned;
   never reads cookies/headers, sends detail requests or hooks page responses. */
function collectPageMedia() {
  const metadata = {};
  const elements = [];
  function visit(root, depth = 0) {
    if (depth > 5) return;
    for (const element of root.querySelectorAll('video,video source')) elements.push(element);
    for (const element of root.querySelectorAll('*')) if (element.shadowRoot) visit(element.shadowRoot, depth + 1);
  }
  visit(document);
  const visible = elements.filter(element => element.tagName !== 'SOURCE').map(video => {
    const box = video.getBoundingClientRect?.();
    const area = box ? Math.max(0, Math.min(box.right, innerWidth) - Math.max(0, box.left))
      * Math.max(0, Math.min(box.bottom, innerHeight) - Math.max(0, box.top)) : 0;
    return {video, area};
  }).filter(item => item.area > 0 && !item.video.ended).sort((a, b) => b.area - a.area);
  const currentVideo = visible[0]?.video;
  const direct = elements.flatMap(element => {
    const video = element.tagName === 'SOURCE' ? element.closest('video') : element;
    const urls = [element.currentSrc, element.src];
    for (const url of urls.filter(value => /^https?:\/\//.test(value || ''))) {
      metadata[url] = {width: video?.videoWidth || null, height: video?.videoHeight || null,
        duration: Number.isFinite(video?.duration) && video.duration > 0 ? video.duration : null,
        current: video === currentVideo && !video.mediaKeys && url === (video.currentSrc || video.src)};
    }
    return urls;
  });
  // A blob: URL can be a MediaSource, not a downloadable file. Read existing
  // page state for this exact aweme instead of guessing among preloaded videos.
  const currentUrl = new URL(location.href);
  const itemId = currentUrl.searchParams.get('modal_id') || currentUrl.searchParams.get('vid')
    || /\/(?:video|note)\/(\d+)/.exec(currentUrl.pathname)?.[1];
  const embedded = [];
  if (/(^|\.)douyin\.com$/.test(currentUrl.hostname) && /^\d+$/.test(itemId || '') && !currentVideo?.mediaKeys) {
    const roots = [window._ROUTER_DATA, window.__INITIAL_STATE__];
    for (const script of document.querySelectorAll('script#RENDER_DATA,script[type="application/json"]')) {
      const text = (script.textContent || '').trim();
      if (text.length > 4000000) continue;
      try { roots.push(JSON.parse(text[0] === '%' ? decodeURIComponent(text) : text)); } catch {}
    }
    let parent = currentVideo;
    for (let depth = 0; parent && depth < 7; depth++, parent = parent.parentElement) {
      for (const key of Object.keys(parent)) {
        if (key.startsWith('__reactProps$')) roots.push(parent[key]);
        if (key.startsWith('__reactFiber$')) {
          let fiber = parent[key];
          for (let count = 0; fiber && count < 10; count++, fiber = fiber.return) {
            roots.push(fiber.memoizedProps, fiber.memoizedState);
          }
        }
      }
    }
    const seen = new Set(); let budget = 12000;
    function walk(value, depth = 0) {
      if (!value || typeof value !== 'object' || depth > 14 || seen.has(value) || --budget < 0 || value.nodeType) return;
      seen.add(value);
      if (String(value.aweme_id || value.awemeId || '') === itemId && value.video) {
        const video = value.video;
        if (video.is_drm || video.drm || video.encrypted) return;
        const address = video.play_addr || video.playAddr || video.bit_rate?.[0]?.play_addr;
        const urls = typeof address === 'string' ? [address] : address?.url_list || address?.urlList || [];
        const url = urls.find(value => /^https?:\/\//.test(value));
        if (url && !embedded.length) {
          embedded.push(url);
          metadata[url] = {current: true, title: typeof value.desc === 'string' ? value.desc : '', width: video.width || null, height: video.height || null,
            duration: video.duration > 0 ? video.duration / 1000 : null, provenance: 'current-page-item'};
        }
        return;
      }
      for (const key of Object.keys(value)) {
        if (['cookie', 'cookies', 'headers', 'authorization', 'token'].includes(key.toLowerCase())) continue;
        try { walk(value[key], depth + 1); } catch {}
      }
    }
    for (const root of roots) walk(root);
  }
  // blob: players can have already fetched the media before discovery was armed.
  // Only URL metadata is read; no response bodies, cookies or request headers.
  const loaded = performance.getEntriesByType('resource').map(entry => entry.name).filter(value => {
    try {
      const url = new URL(value);
      return /\.(mp4|webm|m3u8|mpd)$/i.test(url.pathname)
        || (/(^|\.)douyinvod\.com$/i.test(url.hostname) && /\/video\/tos\//.test(url.pathname));
    } catch { return false; }
  });
  return [...new Set([...direct, ...embedded, ...loaded].filter(value => /^https?:\/\//.test(value || '')))].slice(0, 60)
    .map(url => ({url, ...metadata[url]}));
}
