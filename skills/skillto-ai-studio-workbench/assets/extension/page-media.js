/* One user-requested, same-page detail read if passive state cannot identify
   the current Douyin item. No signatures, cookie export, retries or identity changes. */
async function resolveCurrentDouyinMedia() {
  const page = new URL(location.href);
  const id = page.searchParams.get('modal_id') || page.searchParams.get('vid') || /\/video\/(\d+)/.exec(page.pathname)?.[1];
  if (!['douyin.com', 'www.douyin.com'].includes(page.hostname) || !/^\d+$/.test(id || '')) return null;
  if ([...document.querySelectorAll('video')].some(video => video.mediaKeys)) return {error: '当前页面使用受保护的媒体，此通道不保存 DRM 视频'};
  const api = new URL('/aweme/v1/web/aweme/detail/', page.origin);
  for (const [key, value] of Object.entries({device_platform: 'webapp', aid: '6383', channel: 'channel_pc_web', aweme_id: id})) api.searchParams.set(key, value);
  try {
    const response = await fetch(api.href, {credentials: 'same-origin', signal: AbortSignal.timeout(8000)});
    if ([401, 403, 429].includes(response.status)) return {error: '当前页面的视频详情请求被平台拒绝，已停止；请检查页面是否要求人工验证'};
    if (!response.ok) return {error: '当前页面暂未提供可下载的视频详情，请播放后扫描媒体资源'};
    const text = await response.text();
    if (text.length > 4000000) return {error: '页面详情响应异常，已停止'};
    let data;
    try { data = JSON.parse(text); } catch { return {error: '页面详情未返回视频数据，请检查原页面是否需要人工验证'}; }
    const detail = data.aweme_detail;
    if (String(detail?.aweme_id || '') !== id) return {error: '未找到与当前作品对应的视频地址，请播放后扫描媒体资源'};
    const video = detail.video;
    if (!video || video.is_drm || video.drm || video.encrypted) return {error: '当前作品没有可保存的普通视频文件'};
    const urls = video.play_addr?.url_list || [];
    const url = urls.find(value => /^https?:\/\//.test(value));
    if (!url) return {error: '当前作品未提供视频文件地址，请开启网络发现后播放并扫描'};
    return {url, current: true, title: typeof detail.desc === 'string' ? detail.desc : '', provenance: 'same-page-detail', width: video.width || null,
      height: video.height || null, duration: video.duration > 0 ? video.duration / 1000 : null};
  } catch { return {error: '当前页面读取视频地址失败，请播放后扫描媒体资源；不会回退到服务器网页解析'}; }
}
