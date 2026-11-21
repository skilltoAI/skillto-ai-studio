"""Install a verified local program package without network access."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from release_gate import stage, verify_package, select_offline, verify_selected
from runtime_control import port_available, start, stop
from runtime_state import RuntimeState, atomic_json, installation_lock


def ensure_webview2(package):
    """Check both per-user and machine-wide Evergreen registrations."""
    if os.name != 'nt':
        return
    import winreg
    client = r'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'

    def installed():
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
                try:
                    with winreg.OpenKey(hive, client, 0, winreg.KEY_READ | view) as key:
                        version, _ = winreg.QueryValueEx(key, 'pv')
                        if tuple(map(int, version.split('.'))) > (0, 0, 0, 0):
                            return True
                except (OSError, ValueError, AttributeError):
                    continue
        return False

    if installed():
        return
    installer = package/'prerequisites/MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
    if not installer.is_file():
        raise RuntimeError('WebView2 Runtime is required. Install Microsoft WebView2 Evergreen x64 and retry.')
    subprocess.run([str(installer), '/silent', '/install'], check=True, timeout=300,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    if not installed():
        raise RuntimeError('Microsoft WebView2 Runtime setup completed without a valid registration')


def install(package, digest, root=None, port=None, migrated_data=None):
    package = Path(package).resolve(strict=True)
    runtime = RuntimeState(root)
    verify_package(package, digest)
    if (package/'prerequisites').is_dir():
        ensure_webview2(package)
    with installation_lock(runtime.root):
        if runtime.path.exists():
            state = runtime.read()
            if migrated_data and Path(migrated_data).resolve() != Path(state['dataRoot']):
                raise ValueError('Existing instance is registered with another data root')
            if port is not None and port != state['port']:
                raise ValueError('Existing workbench uses a different port')
        else:
            state = runtime.initialize(data_root=migrated_data, port=port or 8080, migrated=bool(migrated_data))
        old = state.get('release')
        upgrading = old is not None and old['manifestSha256'] != digest
        if state.get('program') and not old:
            raise ValueError('An explicit migration is required for this development instance.')
        if upgrading and not port_available(state['port']):
            raise ValueError('请等待正在执行的任务完成，在旧工作台中停止服务后重试安装。')
        if not old or upgrading:
            key = stage(runtime.root, package, digest)
            previous = state
            state = select_offline(runtime.root, key, digest, state['generation'])
            try:
                result = start(runtime.root)
            except (OSError, ValueError, RuntimeError) as exc:
                if upgrading:
                    if not port_available(state['port']):
                        stop(runtime.root)
                    verify_selected(runtime, previous)
                    atomic_json(runtime.path, {**previous, 'generation': state['generation'] + 1})
                    raise RuntimeError('新版本启动失败，已恢复旧版本配置。请使用原启动入口。') from exc
                raise
        else:
            result = start(runtime.root)
        return {'service':result['service'], 'action':result['action'], 'url':state['url'],
                'instanceId':state['instanceId'], 'version':state['activeVersion'],
                'commit':state['release']['commit'], 'manifestSha256':state['release']['manifestSha256'],
                'launcher':str(runtime.root/'versions'/state['release']['key']/'Skillto.ai Studio.exe')}


def install_skills(package, host, destination, previous_package):
    spec = importlib.util.spec_from_file_location('stass_skill_installer', package / 'scripts/install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = Path(destination).resolve() if destination else module.default_destination(host)
    if host == 'claude' and not destination and module.profiles.claude_plugin_present():
        raise ValueError('已安装 Studio Claude 插件，请通过同一插件来源更新 Skills。')
    names = list(module.discover_skills(package))
    with contextlib.redirect_stdout(io.StringIO()):
        for name in names:
            source = package / 'skills' / name
            current = target / name
            if not os.path.lexists(current) or module.profiles.same_files(source, current):
                continue
            previous = previous_package / 'skills' / name if previous_package else None
            if previous is None or not previous.exists() or not module.profiles.same_files(previous, current):
                continue  # The shared installer reports a conflict and preserves local edits.
            with tempfile.TemporaryDirectory(dir=target, prefix='.skillto-update-') as staging:
                backup = Path(staging) / name
                current.rename(backup)
                try:
                    module.install(target, name, repo_root=package)
                except Exception:
                    backup.rename(current)
                    raise
        conflicts = []
        module.install(target, repo_root=package, names=names, conflicts=conflicts)
    return {'status': 'needs-attention' if conflicts else 'ready', 'directory': str(target),
            'conflicts': conflicts, 'count': len(names) - len(conflicts)}


def register_codex(runtime, release_directory):
    codex = shutil.which('codex.exe')
    if not codex:
        raise RuntimeError('找不到 codex.exe；使用 Codex CLI 注册本地 MCP。')
    config = subprocess.run([codex, 'mcp', 'list', '--json'], capture_output=True, check=True, timeout=20)
    saved = next((entry for entry in json.loads(config.stdout) if entry['name'] == 'skillto-stass'), None)
    profile = runtime.root / 'config/client-codex.json'
    if saved:
        transport = saved.get('transport', {})
        args = transport.get('args', [])
        if saved.get('enabled') and len(args) >= 2 and args[-2:] == ['--profile', str(profile)] and profile.is_file():
            return 'registered'
        raise RuntimeError('已有同名 MCP 配置；请先核对现有设置。')
    from client_auth import issue
    issue(runtime.root, 'codex')
    subprocess.run([codex, 'mcp', 'add', 'skillto-stass', '--',
                    str(release_directory / 'runtime/python.exe'), '-B',
                    str(release_directory / 'program/mcp_bridge.py'), '--profile', str(profile)],
                   capture_output=True, check=True, timeout=20)
    return 'registered'


def create_shortcut(runtime, launcher):
    from win32com.client import Dispatch
    shell = Dispatch('WScript.Shell')
    menu = Path(shell.SpecialFolders('Programs'))
    menu.mkdir(parents=True, exist_ok=True)
    identity = hashlib.sha256(str(runtime.root).casefold().encode()).hexdigest()[:8]
    name = 'Skillto.ai Studio' if runtime.root == RuntimeState().root else f'Skillto.ai Studio ({identity})'
    path = menu / f'{name}.lnk'
    shortcut = shell.CreateShortcut(str(path))
    if path.exists() and shortcut.Arguments != subprocess.list2cmdline(['--config', str(runtime.path)]):
        raise ValueError('同名开始菜单入口属于其他实例。')
    shortcut.TargetPath = launcher
    shortcut.Arguments = subprocess.list2cmdline(['--config', str(runtime.path)])
    shortcut.WorkingDirectory = str(Path(launcher).parent)
    shortcut.Save()
    return str(path)


def setup(options):
    runtime = RuntimeState(options.root)
    with installation_lock(runtime.root):
        state = runtime.read() if runtime.path.exists() else {}
        previous = state.get('previousRelease') if state.get('release', {}).get('manifestSha256') == options.manifest_sha256 else state.get('release')
        result = install(options.package, options.manifest_sha256, runtime.root, options.port)
        directory = Path(result['launcher']).parent
        result['program'] = {'status': 'ready'}
        result['launchCommand'] = subprocess.list2cmdline([result['launcher'], '--config', str(runtime.path)])
        result['skills'] = {'status': 'skipped'}
        result['mcp'] = {'status': 'skipped'}
        result['window'] = {'status': 'skipped'}
        try:
            result['launchEntry'] = create_shortcut(runtime, result['launcher'])
        except Exception as exc:
            result['launchEntry'] = result['launcher']
            result['shortcutError'] = str(exc)
        if options.host:
            try:
                previous_directory = runtime.root / 'versions' / previous['key'] if previous else None
                result['skills'] = install_skills(directory, options.host, options.skills_root, previous_directory)
            except (OSError, ValueError, RuntimeError) as exc:
                result['skills'] = {'status': 'needs-attention', 'message': str(exc)}
        if options.register_mcp and options.host == 'codex':
            try:
                result['mcp'] = {'status': register_codex(runtime, directory)}
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                result['mcp'] = {'status': 'needs-attention', 'message': str(exc)}
    if not options.no_open:
        try:
            with tempfile.TemporaryDirectory(prefix='stass-window-') as temporary:
                receipt = Path(temporary) / 'window.json'
                process = subprocess.Popen([result['launcher'], '--config', str(runtime.path),
                                            '--result-file', str(receipt), '--quiet-errors'],
                                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL)
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if receipt.is_file():
                        try:
                            window = json.loads(receipt.read_text(encoding='utf-8'))
                        except (OSError, ValueError):
                            window = {}
                        if window.get('error'):
                            raise RuntimeError(window['error'])
                        if window.get('serverPid'):
                            result['window'] = {'status': 'opened', 'pid': process.pid}
                            break
                    if process.poll() is not None:
                        raise RuntimeError('启动器提前退出。')
                    time.sleep(.2)
                else:
                    raise RuntimeError('未收到窗口启动回执，可手动打开启动入口。')
        except (OSError, RuntimeError) as exc:
            result['window'] = {'status': 'open-manually', 'message': str(exc)}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--root')
    parser.add_argument('--port', type=int)
    parser.add_argument('--migrated-data')
    parser.add_argument('--setup', action='store_true')
    parser.add_argument('--host', choices=['codex', 'claude'])
    parser.add_argument('--skills-root')
    parser.add_argument('--register-mcp', action='store_true')
    parser.add_argument('--no-open', action='store_true')
    parser.add_argument('--result-file', type=Path)
    options = parser.parse_args()
    try:
        result = setup(options) if options.setup else install(
            options.package, options.manifest_sha256, options.root, options.port, options.migrated_data)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        if options.result_file:
            atomic_json(options.result_file, {'program': {'status': 'failed', 'message': str(exc)}})
        sys.exit(str(exc))
    if options.result_file:
        atomic_json(options.result_file, result)
    print(json.dumps(result))
