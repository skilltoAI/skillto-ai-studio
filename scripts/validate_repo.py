#!/usr/bin/env python3
"""Offline structural checks for the distributable repository (standard library)."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

from install import REPO_ROOT, discover_skills, excluded, package_files


def main() -> int:
    errors = []
    skills = discover_skills()
    parent = (skills['skillto-ai-studio'] / 'SKILL.md').read_text(encoding='utf-8')
    readme = (REPO_ROOT / 'README.md').read_text(encoding='utf-8')
    setup = (skills['skillto-ai-studio'] / 'references/child-setup.md').read_text(encoding='utf-8')
    compatibility = (skills['skillto-ai-studio'] / 'references/compatibility.md').read_text(encoding='utf-8')
    routes = set(re.findall(r'Use `(skillto-ai-studio-[a-z0-9-]+)`', parent))
    children = set(skills) - {'skillto-ai-studio'}
    if routes != children:
        errors.append(f'Parent routes differ from children: {sorted(routes ^ children)}')
    documented = set(re.findall(r'^## (skillto-ai-studio-[a-z0-9-]+)$', setup, re.M))
    if documented != children:
        errors.append(f'Child setup guide differs from children: {sorted(documented ^ children)}')
    for name in children:
        if f'`{name}`' not in compatibility:
            errors.append(f'Compatibility guide missing child: {name}')
    for name in skills:
        if name != 'skillto-ai-studio' and not name.startswith('skillto-ai-studio-'):
            errors.append(f'Skill outside the project namespace: {name}')
        if f'skills/{name}/SKILL.md' not in readme:
            errors.append(f'README missing skill link: {name}')
        metadata = skills[name] / 'agents/openai.yaml'
        if not metadata.is_file() or not re.search(
                r'^  display_name: "Skillto-AI-Studio(?: · [^"]+)?"$',
                metadata.read_text(encoding='utf-8') if metadata.is_file() else '', re.M):
            errors.append(f'Skill picker name missing project branding: {name}')
    manifest = json.loads((REPO_ROOT / '.claude-plugin/plugin.json').read_text(encoding='utf-8'))
    marketplace = json.loads((REPO_ROOT / '.claude-plugin/marketplace.json').read_text(encoding='utf-8'))
    if manifest.get('name') != 'skillto-ai-studio' or not re.fullmatch(r'\d+\.\d+\.\d+', manifest.get('version', '')):
        errors.append('Plugin needs the suite name and a SemVer version.')
    if marketplace.get('name') != 'skillto-ai-studio-marketplace' or not marketplace.get('owner', {}).get('name'):
        errors.append('Marketplace name or owner is missing.')
    if [(p.get('name'), p.get('source')) for p in marketplace.get('plugins', [])] != [('skillto-ai-studio', './')]:
        errors.append('Marketplace must reference the root plugin exactly once.')

    files = [REPO_ROOT / name for name in ('README.md', 'AGENTS.md', '.claude/CLAUDE.md', 'CONTRIBUTING.md')]
    files.append(REPO_ROOT / 'docs/DISTRIBUTION.md')
    for directory in skills.values():
        files.extend(directory / relative for relative in package_files(directory))
    files.extend((REPO_ROOT / 'scripts').glob('*.py'))
    files.extend((REPO_ROOT / 'tests').glob('*.py'))
    for path in files:
        if path.suffix == '.py':
            try:
                ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
            except SyntaxError as error:
                errors.append(f'Python syntax: {path.relative_to(REPO_ROOT)}:{error.lineno}')
        if path.suffix != '.md':
            continue
        for link in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)', path.read_text(encoding='utf-8')):
            link = link.strip().split(' "', 1)[0].strip('<>')
            if not link or urlsplit(link).scheme or link.startswith(('#', '/')):
                continue
            target = unquote(link.split('#', 1)[0])
            if target and not (path.parent / target).exists():
                errors.append(f'Broken local link: {path.relative_to(REPO_ROOT)} -> {target}')

    # Ignoring a file does not untrack it; check the index separately.
    tracked = subprocess.run(['git', 'ls-files', '-z'], cwd=REPO_ROOT,
                             check=True, capture_output=True).stdout.decode('utf-8').split('\0')
    for name in filter(None, tracked):
        path = Path(name)
        if any(excluded(part) for part in path.parts) or path.parts[0] in {'work', 'research', 'runtime', 'data'}:
            errors.append(f'Local state is tracked by Git: {name}')
    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1
    print(f'Validated {len(skills)} skills, parent routes, README links, plugin manifests, '
          f'Python syntax and tracked-file hygiene ({len(files)} distribution/source files).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
