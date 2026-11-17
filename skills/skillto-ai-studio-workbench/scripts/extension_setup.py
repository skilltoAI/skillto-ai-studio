"""Open the existing Chrome install UI; never edit browser preferences/policies."""
import os
from pathlib import Path
import shutil
import subprocess


def open_setup(directory):
    directory = Path(directory).resolve(strict=True)
    if not (directory / 'manifest.json').is_file():
        raise ValueError('插件目录不包含 manifest.json')
    candidates = [shutil.which('google-chrome'), shutil.which('chrome'), shutil.which('chromium')]
    if os.name == 'nt':
        candidates += [str(Path(os.environ.get(base, '')) / 'Google/Chrome/Application/chrome.exe')
                       for base in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA')]
    browser = next((value for value in candidates if value and Path(value).is_file()), None)
    if not browser:
        raise ValueError('未找到 Chrome，请在 Chrome 地址栏打开 chrome://extensions')
    subprocess.Popen([browser, 'chrome://extensions/'], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if os.name == 'nt':
        os.startfile(str(directory))


if __name__ == '__main__':
    open_setup(Path(__file__).resolve().parents[1] / 'assets' / 'extension')
