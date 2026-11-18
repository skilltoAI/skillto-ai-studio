"""Verified immutable release staging and offline compare-and-swap selection.

This is a consistency gate, not a downloader, migration runner or release publisher.
The expected manifest digest must come from the explicitly selected release record.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile

from runtime_state import RuntimeState, atomic_json, installation_lock


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def relative_file(root, name):
    if not isinstance(name, str) or '\\' in name or ':' in name:
        raise ValueError('Invalid release file path')
    parts = PurePosixPath(name)
    if parts.is_absolute() or '..' in parts.parts or not parts.parts or str(parts) != name:
        raise ValueError('Invalid release file path')
    target = root.joinpath(*parts.parts)
    for path in [target, *target.parents]:
        if path == root.parent:
            break
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError('Release links and junctions are forbidden')
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Release path escapes package')
    return target


def verify_package(root, expected_digest):
    root = Path(root).resolve(strict=True)
    manifest_path = relative_file(root, 'release.json')
    if not re.fullmatch('[a-f0-9]{64}', expected_digest) or sha256(manifest_path) != expected_digest:
        raise ValueError('Release manifest digest mismatch')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('format') != 1 or not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', manifest.get('version', '')):
        raise ValueError('Expected a numbered release manifest')
    if not re.fullmatch('[a-f0-9]{40}', manifest.get('commit', '')):
        raise ValueError('Release must pin a full Git commit')
    if type(manifest.get('dataSchema')) is not int or manifest['dataSchema'] < 1:
        raise ValueError('Invalid data schema version')
    if manifest.get('protocol') != 1:
        raise ValueError('Unsupported client protocol')
    files = manifest.get('files', {})
    if not files or len({name.casefold() for name in files}) != len(files):
        raise ValueError('Empty or case-colliding release file list')
    if 'release.json' in files:
        raise ValueError('Manifest cannot list itself')
    actual = set()
    for directory, directories, filenames in os.walk(root, followlinks=False):
        for name in directories + filenames:
            path = Path(directory) / name
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                raise ValueError('Release links and junctions are forbidden')
        for name in filenames:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if relative == 'release.json':
                continue
            if relative not in files:
                raise ValueError('Unlisted files in release package: ' + relative)
            if sha256(path) != files[relative]:
                raise ValueError('Release file digest mismatch: ' + relative)
            actual.add(relative)
    if actual != set(files):
        raise ValueError('Missing files in release package')
    for required in ('program/service.py', 'program/supervisor.py', 'runtime/python.exe', 'Skillto.ai Studio.exe'):
        if required not in files:
            raise ValueError('Required program component missing: ' + required)
    return manifest


def stage(root, package, manifest_digest):
    runtime = RuntimeState(root)
    package = Path(package).resolve(strict=True)
    with installation_lock(runtime.root):
        runtime.read()  # Staging must not initialize another data directory.
        manifest = verify_package(package, manifest_digest)
        key = manifest['version'] + '-' + manifest_digest[:16]
        destination = runtime.root / 'versions' / key
        if destination.exists():
            verify_package(destination, manifest_digest)
            return key
        with tempfile.TemporaryDirectory(dir=runtime.root / 'staging', prefix='release-') as temp:
            tree = Path(temp) / 'payload'
            shutil.copytree(package, tree)
            verify_package(tree, manifest_digest)  # Detect mutation during copying.
            tree.rename(destination)
        return key


def verify_selected(runtime, state):
    release = state.get('release')
    if not release:
        return None
    root = relative_file(runtime.root, 'versions/' + release['key'])
    manifest = verify_package(root, release['manifestSha256'])
    expected_program = {'directory':str(root / 'program'), 'python':str(root / 'runtime/python.exe'), 'mode':'release'}
    if (state.get('program') != expected_program or state.get('dataSchema') != manifest['dataSchema']
            or state.get('activeVersion') != manifest['version'] or release.get('commit') != manifest['commit']):
        raise ValueError('Active configuration differs from verified release')
    return manifest


def select_offline(root, key, manifest_digest, expected_generation):
    """Select only an equal-schema release while stopped; stale callers must retry."""
    from runtime_control import port_available
    runtime = RuntimeState(root)
    with installation_lock(runtime.root):
        state = runtime.read()
        if state.get('generation', 0) != expected_generation:
            raise ValueError('Stale update request: reread shared installation state')
        if not port_available(state['port']):
            raise ValueError('Service must be stopped before selecting another version')
        with installation_lock(runtime.root / 'config' / 'service-owner', 0):
            location = relative_file(runtime.root, 'versions/' + key)
            manifest = verify_package(location, manifest_digest)
            if manifest['dataSchema'] != state.get('dataSchema', 1):
                raise ValueError('Schema migration required; offline selection cannot modify data')
            old = state.get('release')
            if old:
                verify_selected(runtime, state)
                previous_version = tuple(map(int, state['activeVersion'].split('.')))
                if tuple(map(int, manifest['version'].split('.'))) < previous_version:
                    raise ValueError('Implicit downgrade forbidden; use validated rollback workflow')
                if state['activeVersion'] == manifest['version'] and old['manifestSha256'] != manifest_digest:
                    raise ValueError('A published version cannot be replaced with different content')
                if old['manifestSha256'] == manifest_digest:
                    return state
            state['previousRelease'] = old
            state['release'] = {'key':key, 'manifestSha256':manifest_digest, 'commit':manifest['commit']}
            state['program'] = {'directory':str(location/'program'), 'python':str(location/'runtime/python.exe'), 'mode':'release'}
            state['activeVersion'] = manifest['version']
            state['dataSchema'] = manifest['dataSchema']
            state['generation'] = expected_generation + 1
            atomic_json(runtime.path, state)
            return state
