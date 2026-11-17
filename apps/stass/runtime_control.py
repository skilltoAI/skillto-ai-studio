"""Single-user service lifecycle; never kills an unrelated process by PID."""
import ctypes
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import threading
import urllib.request

from runtime_state import RuntimeState, atomic_json, installation_lock, user_sid


def event_name(state):
    return 'Local\\STASS-stop-' + user_sid() + '-' + state['instanceId']


def event_api():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    for name in ('CreateEventW', 'OpenEventW'):
        getattr(kernel, name).restype = ctypes.c_void_p
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.OpenEventW.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.SetEvent.argtypes = [ctypes.c_void_p]
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    return kernel


def health(state, timeout=2):
    # No proxy or redirects for the local service identity check.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(state['url'] + 'health', timeout=timeout) as response:
        value = json.load(response)
    if value.get('service') != 'STASS' or value.get('instanceId') != state['instanceId']:
        raise ValueError('Port belongs to another service or STASS instance')
    return value


def port_available(port):
    with socket.socket() as sock:
        if os.name == 'nt':
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            return False
    return True


def start(root=None):
    runtime = RuntimeState(root)
    with installation_lock(runtime.root):
        state = runtime.read()
        from release_gate import verify_selected
        release = verify_selected(runtime, state)
        if not port_available(state['port']):
            identity = health(state)
            if release and (identity.get('releaseCommit') != release['commit']
                            or identity.get('dataSchema') != release['dataSchema']
                            or identity.get('protocol') != release['protocol']):
                raise ValueError('Running service does not match the selected release')
            return dict(action='reused', **identity)
        program = state.get('program')
        if not program:
            raise ValueError('No installed program; initialization alone is not installation')
        source = Path(program['directory']).resolve(strict=True)
        interpreter = Path(program['python']).resolve(strict=True)
        if not (source / 'service.py').is_file() or not (source / 'supervisor.py').is_file():
            raise ValueError('Program is incomplete')
        token = runtime.root / 'config' / 'admin.token'
        if not token.exists():
            # Exclusive creation avoids ever replacing a live service credential.
            with token.open('x', encoding='utf-8') as stream:
                stream.write(secrets.token_urlsafe(48))
        env = os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['STASS_RELEASE_COMMIT'] = release['commit'] if release else ''
        env['STASS_RELEASE_VERSION'] = release['version'] if release else 'development'
        env['STASS_DATA_SCHEMA'] = str(state.get('dataSchema', 1))
        launch_id = secrets.token_hex(24)
        env.update(STASS_CLIENT_REGISTRY=str(runtime.root / 'config' / 'clients.json'),
                   STASS_LAUNCH_ID=launch_id, STASS_DATA_ROOT=state['dataRoot'], STASS_TOKEN_FILE=str(token),
                   STASS_ALLOWED_HOSTS=f"127.0.0.1:{state['port']},localhost:{state['port']}")
        for key in ('SKILLTO_TABLE_API_URL', 'SKILLTO_TABLE_API_KEY_FILE'):
            env.pop(key, None)
        with (runtime.root / 'logs' / 'service.log').open('ab') as log:
            process = subprocess.Popen([str(interpreter), str(source / 'supervisor.py'),
                                        '--root', str(runtime.root)], cwd=source, env=env,
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       creationflags=0x08000000 | 0x00000200)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('Service exited during startup; inspect logs/service.log')
            try:
                value = health(state)
                if value.get('launchId') != launch_id:
                    raise RuntimeError('A different process acquired the selected port')
                atomic_json(runtime.root / 'config' / 'process.json', {'launcherPid':process.pid, 'launchId':launch_id})
                threading.Thread(target=process.wait, daemon=True).start()
                return dict(action='started', **value)
            except (OSError, ValueError):
                time.sleep(.1)
        raise TimeoutError('Service startup not confirmed; inspect status before retrying')


def stop(root=None):
    runtime = RuntimeState(root)
    with installation_lock(runtime.root):
        state = runtime.read()
        if port_available(state['port']):
            return {'action': 'already-stopped'}
        identity = health(state)  # Refuse to signal if a different service owns this URL.
        kernel = event_api()
        handle = kernel.OpenEventW(2, False, event_name(state))
        if not handle:
            raise RuntimeError('This instance is not managed by the shared supervisor')
        try:
            if not kernel.SetEvent(handle):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.CloseHandle(handle)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if port_available(state['port']):
                with installation_lock(runtime.root / 'config' / 'service-owner'):
                    pass
                # A Windows venv python.exe may be a launcher wrapping the actual interpreter.
                process_file = runtime.root / 'config' / 'process.json'
                if process_file.exists():
                    managed = json.loads(process_file.read_text())
                    if managed['launchId'] == identity.get('launchId'):
                        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
                        kernel.OpenProcess.restype = ctypes.c_void_p
                        process_handle = kernel.OpenProcess(0x100000, False, managed['launcherPid'])
                        if process_handle:
                            try:
                                if kernel.WaitForSingleObject(process_handle, 30000) != 0:
                                    raise TimeoutError('Service launcher is still exiting')
                            finally:
                                kernel.CloseHandle(process_handle)
                return {'action': 'stopped'}
            time.sleep(.1)
        raise TimeoutError('Graceful shutdown pending; no process was force-killed')


def register_development(root, source, interpreter, port=8080):
    """Explicit isolated development setup, never advertised as a release install."""
    runtime = RuntimeState(root)
    source = Path(source).resolve(strict=True)
    interpreter = Path(interpreter).resolve(strict=True)
    if not (source / 'service.py').is_file():
        raise ValueError('Invalid development program directory')
    runtime.initialize(port=port)
    with installation_lock(runtime.root):
        state = runtime.read()
        target = {'directory': str(source), 'python': str(interpreter), 'mode': 'development'}
        if state.get('program') and state['program'] != target:
            raise ValueError('Existing program cannot be replaced by development registration')
        state['program'] = target
        state['activeVersion'] = 'development'
        atomic_json(runtime.path, state)
    return state


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['start', 'stop'])
    parser.add_argument('--root')
    args = parser.parse_args()
    print(json.dumps(globals()[args.operation](args.root)))
