"""Local Chrome profiles. All Playwright objects belong to one worker thread."""
import base64
import json
import os
import queue
import threading
import uuid
from concurrent.futures import Future
from pathlib import Path
from urllib.parse import urlparse


class BrowserProfiles:
    def __init__(self, root):
        self.root = Path(root) / 'browser-profiles'
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry = self.root / 'users.json'
        self.jobs = queue.Queue()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def call(self, args):
        future = Future()
        self.jobs.put((dict(args), future))
        return future.result(timeout=120)

    def close(self):
        self.call({'action': '_shutdown'})
        self.thread.join(timeout=20)

    def _worker(self):
        self.contexts = {}
        self.pages = {}
        self.pw = None
        while True:
            try:
                args, future = self.jobs.get(timeout=0.05)
            except queue.Empty:
                # Chrome is also used by humans. New targets are paused by CDP
                # until Playwright dispatches their attach/resume events.
                # Blocking indefinitely on Queue.get strands manual popups.
                self._pump_events()
                continue
            try:
                if args.get('action') == '_shutdown':
                    for context in list(self.contexts.values()):
                        context.close()
                    if self.pw:
                        self.pw.stop()
                    future.set_result({'closed': True})
                    return
                future.set_result(self._dispatch(args))
            except Exception as exc:
                future.set_exception(exc)

    def _pump_events(self):
        if not self.pw:
            return
        # One Playwright wait services the shared connection for all profiles.
        for profile_id, context in list(self.contexts.items()):
            try:
                if context.pages:
                    context.pages[0].wait_for_timeout(20)
                    return
                context.close()
                self.contexts.pop(profile_id, None)
            except Exception:
                # User may close a page/window while the event loop is pumping.
                continue

    def _read(self):
        return json.loads(self.registry.read_text(encoding='utf-8')) if self.registry.exists() else []

    def _save(self, users):
        temp = self.registry.with_suffix('.tmp')
        with temp.open('w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, self.registry)

    def _view(self, user):
        return {**user, 'running': user['id'] in self.contexts}

    def _register_page(self, page):
        page_id = next((key for key, value in self.pages.items() if value is page), None)
        if page_id is None:
            page_id = str(uuid.uuid4())
            self.pages[page_id] = page
            page.on('close', lambda *_: self.pages.pop(page_id, None))
        return page_id

    def _page_list(self, context):
        result = []
        for page in context.pages:
            if page.is_closed():
                continue
            page_id = self._register_page(page)
            result.append({'pageId': page_id, 'url': page.url})
        return result

    def _dispatch(self, args):
        action = args.get('action', 'list')
        users = self._read()
        self._pump_events()
        if action == 'list':
            return {'users': [self._view(u) for u in users]}
        if action in ('create', 'rename'):
            name = str(args.get('name', '')).strip()
            if not name or len(name) > 100:
                raise ValueError('用户名不能为空，且最多 100 字')
            current_id = args.get('userId') or next((u['id'] for u in users if u['name'] == args.get('username')), None)
            if any(u['name'].casefold() == name.casefold() and (action == 'create' or u['id'] != current_id) for u in users):
                raise ValueError('用户名已存在')
            if action == 'create':
                user = {'id': str(uuid.uuid4()), 'name': name}
                users.append(user)
                self._save(users)
                return self._view(user)
        user = next((u for u in users if u['id'] == args.get('userId') or
                     ('userId' not in args and u['name'] == args.get('username'))), None)
        if user is None:
            raise ValueError('浏览器用户不存在，请先 list')
        uid = user['id']
        if action == 'rename':
            user['name'] = name
            self._save(users)
            return self._view(user)
        if action == 'delete':
            if args.get('confirmName') != user['name']:
                raise ValueError('删除需要 confirmName 与当前用户名完全一致')
            if uid in self.contexts:
                raise ValueError('请先关闭该用户的浏览器再删除')
            # Retain on-disk profile in trash; never recursively delete login data.
            profile = self.root / uid
            if profile.exists():
                trash = self.root / 'trash'
                trash.mkdir(exist_ok=True)
                profile.rename(trash / (uid + '-' + uuid.uuid4().hex))
            users.remove(user)
            self._save(users)
            return {'deleted': uid, 'recoverable': True}
        if action == 'close':
            context = self.contexts.get(uid)
            if context:
                context.close()
            return self._view(user)
        if action == 'launch':
            if uid not in self.contexts:
                if not self.pw:
                    from playwright.sync_api import sync_playwright
                    self.pw = sync_playwright().start()
                context = self.pw.chromium.launch_persistent_context(
                    str(self.root / uid), channel='chrome', headless=False, chromium_sandbox=True,
                    no_viewport=True, timeout=45000)
                context.set_default_timeout(15000)
                context.set_default_navigation_timeout(30000)
                self.contexts[uid] = context
                context.on('page', self._register_page)
                def closed(*_):
                    self.contexts.pop(uid, None)
                    self.pages = {k: p for k, p in self.pages.items() if not p.is_closed()}
                context.on('close', closed)
            if self.contexts[uid].pages:
                self.contexts[uid].pages[0].bring_to_front()
            return {**self._view(user), 'pages': self._page_list(self.contexts[uid])}
        context = self.contexts.get(uid)
        if not context:
            raise ValueError('请先 launch 启动该用户浏览器')
        pages = self._page_list(context)
        if action == 'pages':
            return {'pages': pages}
        if action == 'new_page':
            page = context.new_page()
        else:
            page_id = args.get('pageId')
            page = self.pages.get(page_id) if page_id else (context.pages[0] if context.pages else None)
            if page is None or page.is_closed() or page.context is not context:
                raise ValueError('页面不存在或不属于该用户')
        if action in ('navigate', 'new_page'):
            url = args.get('url', 'about:blank')
            if url != 'about:blank' and urlparse(url).scheme not in ('http', 'https'):
                raise ValueError('仅支持 http/https 或 about:blank')
            page.goto(url, wait_until='domcontentloaded')
        elif action in ('click', 'fill', 'press'):
            locator = page.locator(args['selector'])
            if action == 'click':
                locator.click()
            elif action == 'fill':
                locator.fill(args['text'])
            else:
                locator.press(args['key'])
        elif action == 'evaluate':
            return {'value': page.evaluate(args['expression'])}
        elif action == 'screenshot':
            return {'mimeType': 'image/png', 'base64': base64.b64encode(page.screenshot()).decode()}
        elif action == 'close_page':
            page.close()
            return {'pages': self._page_list(context)}
        elif action != 'snapshot':
            raise ValueError('未知浏览器操作')
        return {'pages': self._page_list(context), 'url': page.url, 'title': page.title(),
                'snapshot': page.locator('body').aria_snapshot()[:60000]}


def browser_call(args):
    """MCP shares the launcher service's worker; never opens a second writer."""
    from urllib.request import Request, urlopen, ProxyHandler, build_opener
    from urllib.error import HTTPError
    endpoint = os.environ.get('SKILLTO_BROWSER_URL', 'http://127.0.0.1:8880')
    parsed = urlparse(endpoint)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.path not in ('', '/'):
        raise ValueError('Browser service must be local loopback')
    args = {**args, 'expectedRoot': str(Path(os.environ.get('SKILLTO_TABLE_ROOT', Path.home() / 'skillto-table-data')).resolve())}
    req = Request(endpoint.rstrip('/') + '/api/browser', data=json.dumps(args).encode(),
                  headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with build_opener(ProxyHandler({})).open(req, timeout=125) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise ValueError(json.load(exc).get('error', str(exc))) from exc
    if result.get('dataRoot') != str(Path(os.environ.get('SKILLTO_TABLE_ROOT', Path.home() / 'skillto-table-data')).resolve()):
        raise ValueError('Browser service dataRoot differs from MCP workspace')
    return result['result']
