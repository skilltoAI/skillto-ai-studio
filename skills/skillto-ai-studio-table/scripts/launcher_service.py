"""HTTP entry point for the Windows launcher; preserves the configured report UI."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import runpy
import secrets
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
    endpoint = urlparse(config.get("url", "http://127.0.0.1:8880/"))
    if endpoint.scheme != "http" or endpoint.hostname != "127.0.0.1" or not endpoint.port:
        raise ValueError("Only explicit loopback HTTP ports are supported")
    data_root = Path(config["dataRoot"]).resolve(strict=True)
    if not data_root.is_dir():
        raise ValueError("dataRoot must be an existing directory")
    os.environ["SKILLTO_TABLE_ROOT"] = str(data_root)
    if config.get('catExtensionDirectory'):
        os.environ['SKILLTO_CAT_EXTENSION_DIR'] = str(Path(config['catExtensionDirectory']).resolve(strict=True))
    os.environ.pop("SKILLTO_TABLE_API_URL", None)
    os.environ.pop("SKILLTO_TABLE_API_KEY_FILE", None)
    os.chdir(config["workingDirectory"])
    application = runpy.run_path(config["serviceScript"], run_name="skillto_local_app")
    original_handler = application["Handler"]
    from browser_profiles import BrowserProfiles
    browsers = BrowserProfiles(data_root)
    browser_assets = Path(__file__).resolve().parents[1] / 'assets'

    shutdown_event = ""
    event_handle = None
    kernel = None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateEventW.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        shutdown_event = "Local\\SkillToTableShutdown-" + secrets.token_hex(16)
        event_handle = kernel.CreateEventW(None, True, False, shutdown_event)
        if not event_handle:
            raise ctypes.WinError(ctypes.get_last_error())

    class Handler(original_handler):
        def browser_request_allowed(self):
            authority = f'127.0.0.1:{endpoint.port}'
            return (self.headers.get('Host') == authority and
                    self.headers.get('Origin', 'http://' + authority) == 'http://' + authority and
                    self.headers.get('Sec-Fetch-Site', 'same-origin') in ('same-origin', 'none'))

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ('/browser-users', '/assets/browser-users.js'):
                if not self.browser_request_allowed():
                    self.respond_json({'error': 'Local requests only'}, 403)
                    return
                name = 'browser-users.html' if path == '/browser-users' else 'browser-users.js'
                self.respond((browser_assets / name).read_bytes(),
                             'text/html; charset=utf-8' if name.endswith('.html') else 'application/javascript; charset=utf-8')
            elif path == "/api/launcher-health":
                self.respond_json({"service": "skillto-ai-studio-table", "dataRoot": str(data_root),
                                   "pid": os.getpid(), "port": endpoint.port,
                                   "shutdownEvent": shutdown_event, "launcherVersion": 2})
            else:
                super().do_GET()

        def do_POST(self):
            if urlparse(self.path).path != '/api/browser':
                return super().do_POST()
            if not self.browser_request_allowed() or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                self.respond_json({'error': 'Local JSON requests only'}, 403)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 1024 * 1024:
                    raise ValueError('Invalid body size')
                args = json.loads(self.rfile.read(length))
                if args.get('expectedRoot', str(data_root)) != str(data_root):
                    raise ValueError('Browser workspace mismatch')
                self.respond_json({'result': browsers.call(args), 'dataRoot': str(data_root)})
            except Exception as exc:
                self.respond_json({'error': str(exc)}, 400)

    try:
        with ThreadingHTTPServer(("127.0.0.1", endpoint.port), Handler) as server:
            # HTTPServer defaults to daemon request threads; wait for writes on close.
            server.daemon_threads = False
            server.block_on_close = True
            if event_handle:
                def wait_for_shutdown():
                    if kernel.WaitForSingleObject(event_handle, 0xFFFFFFFF) == 0:
                        server.shutdown()
                threading.Thread(target=wait_for_shutdown, daemon=True).start()
            print(f"Skillto-AI-Studio ready: http://127.0.0.1:{endpoint.port}/ pid={os.getpid()}", flush=True)
            server.serve_forever()
        print("Skillto-AI-Studio stopped gracefully", flush=True)
    finally:
        browsers.close()
        if event_handle:
            kernel.CloseHandle(event_handle)


if __name__ == "__main__":
    main()
