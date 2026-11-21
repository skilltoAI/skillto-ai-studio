"""User-scoped installation identity. Contains no business-storage implementation."""
import contextlib
import ctypes
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid


def default_root():
    if os.name != 'nt':
        raise RuntimeError('The shared program installer currently supports Windows only')
    return Path(os.environ['LOCALAPPDATA']) / 'Skillto.ai' / 'Studio'


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def user_sid():
    import subprocess
    # Windows emits CSV with a stable SID column, independently of display language.
    import csv
    output = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'],
                                    creationflags=0x08000000)
    row = next(csv.reader(output.decode(errors='replace').splitlines()))
    sid = row[-1]
    if not sid.startswith('S-1-'):
        raise RuntimeError('Cannot determine Windows user SID')
    return sid


@contextlib.contextmanager
def installation_lock(root, timeout_ms=30000):
    """One lock shared by every management operation, released on process death."""
    if os.name != 'nt':
        raise RuntimeError('Windows mutex required')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.ReleaseMutex.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    suffix = hashlib.sha256(str(Path(root).resolve()).casefold().encode()).hexdigest()[:24]
    handle = kernel.CreateMutexW(None, False, 'Local\\STASS-' + user_sid() + '-' + suffix)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    acquired = False
    try:
        result = kernel.WaitForSingleObject(handle, timeout_ms)
        if result not in (0, 0x80):
            raise TimeoutError('Another STASS operation is in progress')
        acquired = True
        yield
    finally:
        if acquired:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


class RuntimeState:
    def __init__(self, root=None):
        self.root = Path(root).resolve() if root else default_root()
        self.path = self.root / 'config' / 'installation.json'

    def read(self):
        value = json.loads(self.path.read_text(encoding='utf-8'))
        if value.get('format') != 1:
            raise ValueError('Unsupported installation configuration')
        uuid.UUID(value['instanceId'])
        return value

    def initialize(self, data_root=None, port=8080, *, migrated=False):
        if not 1 <= port <= 65535:
            raise ValueError('Invalid port')
        with installation_lock(self.root):
            if self.path.exists():
                state = self.read()
                if data_root and Path(data_root).resolve() != Path(state['dataRoot']):
                    raise ValueError('Changing the shared data root requires explicit migration')
                if port != state['port']:
                    raise ValueError('Existing instance uses another port; explicit reconfiguration required')
                return state
            data = Path(data_root).resolve() if data_root else self.root / 'data'
            if data.exists() and any(data.iterdir()):
                marker = data / 'migration-snapshot.json'
                if not migrated or not marker.is_file():
                    raise ValueError('Initial installation requires empty data directory; use migration for existing data')
                snapshot = json.loads(marker.read_text(encoding='utf-8'))
                origin = Path(snapshot['source']).resolve()
                if (snapshot['status'] != 'workspace-copy-verified-not-cutover' or origin == data
                        or origin in data.parents or data in origin.parents or (data/'.stass-instance').exists()):
                    raise ValueError('Expected an independent, unused migration snapshot')
            for name in ('versions', 'config', 'backups', 'logs', 'staging'):
                (self.root / name).mkdir(parents=True, exist_ok=True)
            data.mkdir(parents=True, exist_ok=True)
            instance = str(uuid.uuid4())
            state = dict(format=1, instanceId=instance, dataRoot=str(data), port=port,
                         url=f'http://127.0.0.1:{port}/STASS/', activeVersion=None, hosts={}, generation=0, dataSchema=1,
                         reportConfig=str(self.root / 'config' / 'reporting.json'))
            # Identity must exist before any service can open this data directory.
            (data / '.stass-instance').write_text(instance, encoding='utf-8')
            atomic_json(self.path, state)
            return state
