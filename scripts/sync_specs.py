"""Build/check the portable standards bundled with the parent skill."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'skills/skillto-ai-studio/references/standards'


def expected():
    source = ROOT / '技术规范.md'
    files = {'技术规范.md': source.read_bytes()}
    for path in sorted((ROOT / 'docs/规范').glob('*.md')):
        files['docs/规范/' + path.name] = path.read_bytes()
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    version = json.loads((ROOT / '.claude-plugin/plugin.json').read_text(encoding='utf-8'))['version']
    files['manifest.json'] = (json.dumps({'format': 1, 'packageVersion': version, 'sha256': hashes}, ensure_ascii=False, indent=2) + '\n').encode()
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    files = expected()
    if args.check:
        stale = [name for name, data in files.items() if not (DEST/name).is_file() or (DEST/name).read_bytes() != data]
        extras = [str(p.relative_to(DEST)) for p in DEST.rglob('*') if p.is_file() and p.relative_to(DEST).as_posix() not in files]
        if stale or extras:
            print('Standards mismatch:', stale, extras)
            return 1
    else:
        for name, data in files.items():
            path = DEST / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print('Portable standards verified' if args.check else 'Portable standards generated')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
