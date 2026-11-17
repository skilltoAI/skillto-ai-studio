"""Explicit public-source downloads; no arbitrary proxy or credential forwarding."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

ALLOWED = {'motiontemplates.github.io', 'raw.githubusercontent.com', 'media.openaicut.com'}

def check_url(url):
    u = urlsplit(url)
    official_release = u.hostname == 'github.com' and u.path.startswith('/motiontemplates/all/releases/download/')
    if u.scheme != 'https' or (u.hostname not in ALLOWED and not official_release) or u.port not in (None, 443) or u.username or u.password:
        raise ValueError('此下载地址尚未接入；请下载后导入本机文件')
    if u.query or u.fragment: raise ValueError('不接受带凭据或查询参数的下载地址')
    return url

class Redirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        source, target = urlsplit(req.full_url), urlsplit(newurl)
        official = source.hostname == 'github.com' and source.path.startswith('/motiontemplates/all/releases/download/')
        # GitHub signs public release redirects. Accept these only in a trusted redirect
        # chain; direct signed URLs and arbitrary GitHub repositories remain rejected.
        if (official or source.hostname == 'release-assets.githubusercontent.com') and target.hostname == 'release-assets.githubusercontent.com':
            if target.scheme != 'https' or target.port not in (None,443) or target.username or target.password or target.fragment:
                raise ValueError('无效 GitHub Release 媒体重定向')
        else: check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def download(url, target, limit, cancel=lambda: False):
    check_url(url)
    target = Path(target); target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + '.part')
    try:
        with build_opener(Redirects()).open(Request(url, headers={'User-Agent': 'SkilltoStudio/1.0'}), timeout=30) as response, part.open('wb') as out:
            declared = int(response.headers.get('Content-Length', 0))
            if declared > limit: raise ValueError('文件超过下载大小限制')
            size = 0
            while True:
                if cancel(): raise InterruptedError('已取消')
                chunk = response.read(256 * 1024)
                if not chunk: break
                size += len(chunk)
                if size > limit: raise ValueError('文件超过下载大小限制')
                out.write(chunk)
        if not size: raise ValueError('下载为空')
        os.replace(part, target)
        return target
    finally:
        part.unlink(missing_ok=True)
