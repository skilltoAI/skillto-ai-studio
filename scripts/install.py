#!/usr/bin/env python3
"""Install sibling Agent Skills without copying local state or overwriting skills."""
from __future__ import annotations

import argparse
import fnmatch
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = (
    '__pycache__', '*.pyc', '*.pyo', '.DS_Store', '.git', '.venv', 'venv',
    '.env', '.env.*', '*.key', '*.pem', '*cookie*.txt', '*cookie*.json',
    '*.sqlite', '*.sqlite3', '*.db', '*.log', '*.exe', '*.syso',
    'launcher.local.json', 'node_modules', '.pytest_cache', '.ruff_cache',
    'runtime', 'data', '.test-tmp', '.install-test', '.cache', '.playwright-cli',
    '.remotion', '*.bak', '*.tmp', '*.local.json', '*.env',
)


def excluded(name: str) -> bool:
    return any(fnmatch.fnmatchcase(name.lower(), pattern.lower()) for pattern in EXCLUDED)


def discover_skills(repo_root: Path = REPO_ROOT) -> dict[str, Path]:
    skills = {}
    for path in sorted((repo_root / 'skills').iterdir()):
        if not path.is_dir() or not (path / 'SKILL.md').is_file():
            continue
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError(f'Skill source must be a real directory: {path}')
        text = (path / 'SKILL.md').read_text(encoding='utf-8')
        header = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', text, re.S)
        name = re.search(r'^name:\s*([a-z0-9]+(?:-[a-z0-9]+)*)\s*$', header[1], re.M) if header else None
        if not name or name[1] != path.name or len(path.name) > 64:
            raise ValueError(f'Skill name/frontmatter does not match directory: {path}')
        if not re.search(r'^description:\s*\S', header[1], re.M):
            raise ValueError(f'Skill description missing: {path}')
        skills[path.name] = path
    if not skills:
        raise ValueError('No skills found under skills/.')
    return skills


def default_destination(agent: str, *, codex_legacy: bool = False) -> Path:
    if agent == 'claude':
        return (Path(os.environ['CLAUDE_CONFIG_DIR']).expanduser() if os.environ.get('CLAUDE_CONFIG_DIR')
                else Path.home() / '.claude') / 'skills'
    if codex_legacy:
        return (Path(os.environ['CODEX_HOME']).expanduser() if os.environ.get('CODEX_HOME')
                else Path.home() / '.codex') / 'skills'
    return Path.home() / '.agents' / 'skills'


def package_files(source: Path):
    """Yield portable files; do not follow links into other local directories."""
    for root, directories, files in os.walk(source, followlinks=False):
        root = Path(root)
        directories[:] = sorted(name for name in directories if not excluded(name))
        for name in directories + sorted(files):
            path = root / name
            if excluded(name):
                continue
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                raise ValueError(f'Symlinks/junctions are not distributable: {path}')
            if path.is_file():
                yield path.relative_to(source)


def install(destination: Path, skill: str = 'all', *, repo_root: Path = REPO_ROOT,
            dry_run: bool = False) -> list[str]:
    available = discover_skills(repo_root)
    if skill != 'all' and skill not in available:
        raise ValueError(f'Unknown skill: {skill}. Available: {", ".join(available)}')
    selected = available if skill == 'all' else {skill: available[skill]}
    destination = destination.expanduser().resolve()
    # Preflight the complete selection before creating or copying anything.
    for source in available.values():
        if destination == source.resolve() or source.resolve() in destination.parents:
            raise ValueError('Destination must be outside source skill directories.')
    if destination.exists() and not destination.is_dir():
        raise ValueError(f'Destination is not a directory: {destination}')
    plans = []
    for name, source in selected.items():
        target = destination / name
        if os.path.lexists(target):
            raise FileExistsError(f'Destination already exists: {target}. Back it up before upgrading.')
        plans.append((name, source, list(package_files(source))))
    if dry_run:
        for name, _, files in plans:
            print(f'Would install {name} ({len(files)} files) -> {destination / name}')
        return list(selected)
    destination.mkdir(parents=True, exist_ok=True)
    # Stage first so a read/copy failure cannot leave a discoverable partial skill.
    with tempfile.TemporaryDirectory(prefix='.skillto-install-', dir=destination) as temporary:
        staging = Path(temporary)
        for name, source, files in plans:
            for relative in files:
                target = staging / name / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / relative, target)
        for name, _, _ in plans:
            target = destination / name
            if os.path.lexists(target):
                raise FileExistsError(f'Destination appeared during installation: {target}')
            (staging / name).rename(target)
            print(f'Installed {name} -> {target}')
    return list(selected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent', choices=['codex', 'claude'], default='codex')
    parser.add_argument('--skill', default='all', help='all or a skills/ directory name')
    parser.add_argument('--destination', type=Path, help='Explicit skill root; overrides --agent default')
    parser.add_argument('--dry-run', action='store_true', help='Check and print plan without writing')
    parser.add_argument('--list', action='store_true', help='List bundled skills without installing')
    parser.add_argument('--codex-legacy', action='store_true',
                        help='Use $CODEX_HOME/skills or ~/.codex/skills for older Codex installations')
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error('Python 3.10+ is required.')
    if args.codex_legacy and args.agent != 'codex':
        parser.error('--codex-legacy is only valid with --agent codex.')
    try:
        if args.list:
            print('\n'.join(discover_skills()))
            return 0
        install(args.destination if args.destination is not None else
                default_destination(args.agent, codex_legacy=args.codex_legacy),
                args.skill, dry_run=args.dry_run)
    except (OSError, ValueError) as error:
        print(f'Installation failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
