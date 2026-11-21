#!/usr/bin/env python3
"""Install sibling Agent Skills without copying local state or overwriting skills."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_MODULE = REPO_ROOT / 'apps' / 'stass'
if not PROFILE_MODULE.is_dir():
    PROFILE_MODULE = REPO_ROOT / 'program'
sys.path.insert(0, str(PROFILE_MODULE))
import work_profiles as profiles
from work_profiles import excluded, package_files


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


def install(destination: Path, skill: str = 'all', *, repo_root: Path = REPO_ROOT,
            dry_run: bool = False, names=None, conflicts=None) -> list[str]:
    available = discover_skills(repo_root)
    if skill != 'all' and skill not in available:
        raise ValueError(f'Unknown skill: {skill}. Available: {", ".join(available)}')
    selected = available if skill == 'all' else {skill: available[skill]}
    if names is not None:
        selected = {name: available[name] for name in names}
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
            if names is not None and profiles.same_files(source, target):
                print(f'已复用 {name}')
                continue
            if conflicts is not None:
                conflicts.append(name)
                print(f'保留已有副本，请核对 {name}')
                continue
            raise FileExistsError(f'Destination already exists: {target}. Back it up before upgrading.')
        prefix = 'skillto-ai-studio'
        if name == prefix or name.startswith(prefix + '-'):
            legacy = destination / ('skillto-int' + name[len(prefix):])
            if os.path.lexists(legacy):
                raise FileExistsError(
                    f'Legacy skill exists: {legacy}. Move it outside the skill root before installing '
                    f'{name}; see references/rename-migration.md in the parent skill.')
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


def category_install(args):
    groups = []
    aliases = {}
    for number, (key, group) in enumerate(profiles.GROUPS.items(), 1):
        aliases.update({key: key, str(number): key, group['name']: key})
    raw = args.groups
    if raw == 'ask':
        for number, group in enumerate(profiles.GROUPS.values(), 1):
            print(f"{number}. {group['name']}　{group['summary']}")
        raw = input('你日常需要处理哪些工作？（可多选） ')
    for token in re.split(r'[,，、\s]+', raw.strip()):
        if token not in aliases:
            raise ValueError(f'未知工作类别：{token}')
        if aliases[token] not in groups:
            groups.append(aliases[token])
    previous = profiles.profile()
    exact_items = None
    if args.items is not None:
        exact_items = [item.strip() for item in args.items.split(',') if item.strip()]
    items = profiles.resolve(groups, exact_items)
    if args.augment:
        groups = list(dict.fromkeys((previous['groups'] or []) + groups))
        items = profiles.resolve(groups, items + previous['items'])
    names = [profiles.PARENT] + [profiles.PARENT + '-' + key for key in items
                                 if profiles.ITEMS[key].get('kind') != 'component']
    destination = args.destination
    if destination is None:
        destination = default_destination(args.agent, codex_legacy=True) if args.codex_legacy else profiles.recorded_destination(args.agent)
    if args.agent == 'claude' and profiles.claude_plugin_present():
        raise ValueError('已登记 Studio 完整插件，请核对插件安装范围，避免重复直装。')
    conflicts = []
    install(destination, dry_run=args.dry_run, names=names, conflicts=conflicts)
    if not args.dry_run:
        profiles.remember(args.agent, destination)
        profiles.save(groups, items, previous['revision'])
        print('试试：' + profiles.GROUPS[groups[-1]]['example'])
        for key in items:
            print(profiles.ITEMS[key]['name'] + ' · ' + profiles.ITEMS[key]['needs'])
    if conflicts:
        raise ValueError('以下已有副本存在差异，其他选择已处理：' + ', '.join(conflicts))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent', choices=['codex', 'claude'], default='codex')
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument('--groups', nargs='?', const='ask', help='工作类别 ID、中文名或编号；省略值时只询问一次')
    parser.add_argument('--items', help='精确选择清单中的项目 ID，逗号分隔')
    parser.add_argument('--augment', action='store_true', help='保留已选工作并增补')
    choice.add_argument('--skill', default='all', help='all or a skills/ directory name')
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
        if (args.items or args.augment) and args.groups is None:
            parser.error('--items / --augment require --groups')
        if args.groups is not None:
            category_install(args)
            return 0
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
