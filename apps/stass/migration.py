"""Non-destructive snapshot of an explicit legacy workspace for migration rehearsal.

This is not cutover: browser profiles and external referenced assets need separate
offline/reference-aware migration. The manifest explicitly records that limitation.
"""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def snapshot(source, destination):
    source = Path(source).resolve(strict=True)
    destination = Path(destination).resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Snapshot source and destination must be disjoint')
    destination.mkdir(parents=True, exist_ok=True)
    marker = destination / 'migration-snapshot.json'
    old = json.loads(marker.read_text('utf-8')) if marker.exists() else None
    if old and old['source'] != str(source):
        raise ValueError('Snapshot belongs to another source')
    if not old and any(destination.iterdir()):
        raise ValueError('New snapshot destination must be empty')
    report = {'source': str(source), 'status': 'incomplete', 'files': [],
              'pending': ['offline browser profiles', 'external referenced assets', 'PostgreSQL/Metabase', 'reference rewriting and cutover']}

    def save():
        temporary = marker.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        temporary.replace(marker)

    save()
    for folder, dirs, files in os.walk(source, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != 'browser-profiles')
        for directory in dirs:
            p = Path(folder)/directory
            if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
                raise ValueError('Linked directory requires explicit resource mapping')
        for name in sorted(files):
            p = Path(folder)/name
            if p.is_symlink():
                raise ValueError('Linked file requires explicit resource mapping')
            if name.endswith(('-wal', '-shm', '.lock')):
                continue
            relative = p.relative_to(source)
            target = destination/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with p.open('rb') as stream:
                is_db = stream.read(16) == b'SQLite format 3\x00'
            if is_db:
                handle, temporary_name = tempfile.mkstemp(dir=target.parent, suffix='.snapshot')
                os.close(handle)
                temporary = Path(temporary_name)
                try:
                    with closing(sqlite3.connect(p.as_uri()+'?mode=ro', uri=True)) as original, closing(sqlite3.connect(temporary)) as backup:
                        original.backup(backup)
                        if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                            raise ValueError('SQLite integrity check failed')
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
                method = 'sqlite-backup'
            else:
                before = p.stat()
                source_hash = digest(p)
                if not target.is_file() or digest(target) != source_hash:
                    temporary = target.with_name(target.name+'.stass-copy')
                    try:
                        shutil.copy2(p, temporary)
                        if digest(temporary) != source_hash:
                            raise ValueError('Source changed during copy')
                        temporary.replace(target)
                    finally:
                        temporary.unlink(missing_ok=True)
                after = p.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError('Source changed during snapshot; rerun after quiescing writes')
                method = 'byte-copy'
            report['files'].append({'path': relative.as_posix(), 'bytes': target.stat().st_size,
                                    'sha256': digest(target), 'method': method})
            if len(report['files']) % 100 == 0:
                save()
    report['status'] = 'workspace-copy-verified-not-cutover'
    save()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    result = snapshot(args.source, args.destination)
    print(json.dumps({'status': result['status'], 'files': len(result['files']), 'pending': result['pending']}))
