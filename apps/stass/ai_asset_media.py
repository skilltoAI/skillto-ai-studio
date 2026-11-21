"""Forward public Feishu media using a fresh anonymous guest session, without disk caching."""
import re
import threading
import time
from urllib.parse import quote, urlsplit
import urllib.request
import urllib.error

from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
import ai_asset_library

STREAM_HOST = 'internal-api-drive-stream.feishu.cn'
CACHE = {}
LOCK = threading.RLock()
MAX_MEDIA = 512 * 1024 * 1024


def anonymous_headers(source):
    # Never attach a user's browser profile or an authenticated account.
    from playwright.sync_api import sync_playwright
    source = ai_asset_library.source_url(source).split('#')[0]
    with LOCK:
        saved = CACHE.get(source)
        if saved and saved[0] > time.monotonic():
            return dict(saved[1])
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception:
                browser = pw.chromium.launch(channel='chrome', headless=True)
            try:
                context = browser.new_context()
                # Bootstrap only page authorization; no video or image is cached by Chromium.
                context.route('**/*', lambda route: route.abort() if route.request.resource_type in ('media', 'image', 'font') or '/stream/' in route.request.url else route.continue_())
                page = context.new_page()
                page.goto(source, wait_until='domcontentloaded', timeout=30000)
                deadline = time.monotonic() + 12
                cookies = []
                while time.monotonic() < deadline:
                    cookies = context.cookies('https://' + STREAM_HOST + '/')
                    if any(c['name'] == 'is_anonymous_session' and c['value'] == '1' for c in cookies):
                        break
                    page.wait_for_timeout(200)
                if urlsplit(page.url).hostname != 'my.feishu.cn' or not any(c['name'] == 'is_anonymous_session' and c['value'] == '1' for c in cookies):
                    raise ValueError('飞书来源需要公开分享权限，无法匿名播放')
                headers = {'Cookie': '; '.join(c['name']+'='+c['value'] for c in cookies),
                           'Referer': 'https://my.feishu.cn/', 'User-Agent': page.evaluate('navigator.userAgent')}
            finally:
                browser.close()
        if len(CACHE) >= 32:
            CACHE.pop(next(iter(CACHE)))
        CACHE[source] = (time.monotonic()+240, headers)
        return dict(headers)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def open_media(item, byte_range=None):
    if byte_range and not re.fullmatch(r'bytes=(?:\d+-\d*|-\d+)', byte_range):
        raise ValueError('仅支持单段视频范围请求')
    token = item['fileToken']
    if not re.fullmatch(r'[A-Za-z0-9]+', token):
        raise ValueError('视频引用无效')
    source = item['sourceUrl'].split('#')[0]
    url = f'https://{STREAM_HOST}/space/api/box/stream/download/video/{token}/?quality=720p&mount_point=docx_file'
    for attempt in range(2):
        headers = anonymous_headers(source)
        headers['Accept-Encoding'] = 'identity'
        if byte_range:
            headers['Range'] = byte_range
        try:
            response = urllib.request.build_opener(NoRedirect()).open(urllib.request.Request(url,headers=headers),timeout=30)
        except urllib.error.HTTPError as error:
            error.close()
            if error.code in (401,403) and attempt == 0:
                with LOCK:
                    CACHE.pop(source, None)
                continue
            raise ValueError('飞书视频暂不可访问，请检查来源分享权限') from None
        if response.status not in (200,206) or not response.headers.get('Content-Type','').lower().startswith('video/'):
            response.close()
            raise ValueError('来源没有返回可播放视频')
        try:
            length = int(response.headers.get('Content-Length', MAX_MEDIA+1))
        except (ValueError, TypeError):
            response.close()
            raise ValueError('视频大小信息无效') from None
        if length < 0 or length > MAX_MEDIA:
            response.close()
            raise ValueError('视频超出在线转发大小限制，请打开来源')
        return response


def stream_chunks(response):
    try:
        total = 0
        while chunk := response.read(64*1024):
            total += len(chunk)
            if total > MAX_MEDIA:
                raise ValueError('视频超过大小限制')
            yield chunk
    finally:
        response.close()


def endpoint(store):
    async def media(request):
        try:
            item = await run_in_threadpool(ai_asset_library.get_asset, request.path_params['ident'], store)
            upstream = await run_in_threadpool(open_media, item, request.headers.get('range'))
        except Exception:
            # Never include upstream request headers or anonymous cookies in responses/logs.
            return JSONResponse({'error':'视频暂不可用，请重试或检查飞书来源分享权限。'},status_code=502)
        headers = {'Content-Type': upstream.headers['Content-Type'], 'Cache-Control':'no-store', 'Accept-Ranges':'bytes'}
        for key in ('Content-Length','Content-Range'):
            if upstream.headers.get(key):headers[key] = upstream.headers[key]
        if request.query_params.get('download') == '1':
            name = re.sub(r'[\r\n\\/]', '_', item['filename'] or item['title']+'.mp4')
            headers['Content-Disposition'] = "attachment; filename*=UTF-8''"+quote(name)
        return StreamingResponse(stream_chunks(upstream),status_code=upstream.status,headers=headers,background=BackgroundTask(upstream.close))
    return media
