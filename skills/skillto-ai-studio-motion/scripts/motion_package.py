"""Bounded, non-executing reader for public MotionGit content archives."""
import hashlib
import json
import re
import stat
import shutil
import tempfile
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath

KNOWN_SHA = '472a95af35f8e0c09c0f7dc2ca0992b7c9a3405c5aa8063730c347fc4e015c21'
MAX_PACKAGE = 384 * 1024 * 1024

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def safe_name(name):
    if not isinstance(name, str): raise ValueError('Package reference must be a string')
    parts = PurePosixPath(name).parts
    if not name or '\\' in name or ':' in name or name.startswith('/') or any(p in ('','.','..') for p in name.rstrip('/').split('/')) or any(
        p in ('.', '..') or p.endswith((' ', '.')) or
        re.match(r'^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', p, re.I)
        for p in parts
    ) or any(ord(c) < 32 for c in name):
        raise ValueError('Invalid package path: ' + name)
    return name.rstrip('/')

def inspect_package(path, destination=None):
    path = Path(path)
    if path.stat().st_size > MAX_PACKAGE:
        raise ValueError('Package exceeds 384 MiB')
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 5000 or sum(i.file_size for i in entries) > 600 * 1024 * 1024:
            raise ValueError('Expanded package limit exceeded')
        names, files = {}, {}
        for item in entries:
            name = safe_name(item.filename)
            canonical = unicodedata.normalize('NFC', name).casefold()
            mode = item.external_attr >> 16
            if canonical in names or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise ValueError('Duplicate, alias or special entry: ' + name)
            names[canonical] = item.is_dir()
            if item.flag_bits & 1 or item.file_size > 150 * 1024 * 1024:
                raise ValueError('Encrypted or oversized archive entry')
            if item.file_size > 10 * 1024 * 1024 and item.file_size / max(1, item.compress_size) > 200:
                raise ValueError('Unsafe compression ratio')
            if not item.is_dir(): files[name] = item
        for name in names:
            for parent in PurePosixPath(name).parents:
                if str(parent) != '.' and names.get(str(parent)) is False:
                    raise ValueError('File/directory collision')
        def read_json(name):
            safe_name(name)
            if name not in files: raise ValueError('Missing reference: ' + name)
            if files[name].file_size > 8 * 1024 * 1024: raise ValueError('Metadata too large')
            return json.loads(archive.read(name))
        manifest = read_json('motion.json')
        if not isinstance(manifest, dict): raise ValueError('motion.json must be an object')
        profile = manifest.get('packageProfile')
        if profile or manifest.get('specVersion') == '1.0.0-rc.1':
            return {'manifest': {'packageProfile': profile, 'specVersion': manifest.get('specVersion')},
                    'status': 'unsupported', 'reason': '个人包/保护封装暂不执行', 'renderable': False,
                    'sha256': digest(path)}
        if manifest.get('format') != 'motiongit-template': raise ValueError('Not a MotionGit content manifest')
        for key in ('template', 'runtime', 'output'):
            if not isinstance(manifest.get(key), dict): raise ValueError('Missing manifest object: ' + key)
        refs = [manifest['runtime'].get('entry'), manifest['runtime'].get('dependencyLock')]
        for obj, key in [('parameters','schema'),('parameters','defaultPreset'),('assets','manifest'),('ai','entry'),('ai','guide'),('license','file')]:
            if not isinstance(manifest.get(obj, {}), dict): raise ValueError('Invalid manifest object: '+obj)
            refs.append(manifest.get(obj, {}).get(key))
        for ref in filter(None, refs):
            if safe_name(ref) not in files: raise ValueError('Missing reference: ' + ref)
        integrity = manifest.get('integrity')
        if integrity:
            checks = read_json(integrity)
            if not isinstance(checks, dict): raise ValueError('Integrity must be an object')
            if checks.get('algorithm') != 'sha256' or not isinstance(checks.get('files'), dict):
                raise ValueError('Unsupported integrity declaration')
            if set(checks['files']) != set(files) - {integrity}:
                raise ValueError('Integrity membership mismatch')
            for name, expected in checks['files'].items():
                if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                    raise ValueError('Integrity mismatch: ' + name)
        sha = digest(path)
        supported = manifest.get('specVersion') == '0.1.0-draft.1'
        renderable = supported and sha == KNOWN_SHA and manifest['runtime'].get('profile') == 'kinetic-user-core/1'
        result = {'manifest': manifest, 'sha256': sha, 'status': 'verified' if supported else 'unsupported',
                  'renderable': renderable, 'reason': '' if renderable else '已检查；此版本或运行适配尚未验证',
                  'integrityVerified': bool(integrity), 'entries': len(entries)}
        if destination and supported:
            target = Path(destination)
            if target.exists(): raise ValueError('Extraction target already exists')
            target.parent.mkdir(parents=True, exist_ok=True)
            # Failed CRC / disk writes must never leave a seemingly reusable runner.
            with tempfile.TemporaryDirectory(prefix='.motion-',dir=target.parent) as temp:
                stage = Path(temp)/'content'; stage.mkdir()
                for name, item in files.items():
                    output = stage.joinpath(*PurePosixPath(name).parts)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as src, output.open('xb') as dst:
                        shutil.copyfileobj(src, dst)
                stage.rename(target)
        return result
