"""Local work preferences and read-only host inventory. Standard library only."""
import fnmatch
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys

from runtime_state import atomic_json, installation_lock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if HERE.name == 'program' else HERE.parents[1]
CATALOG = json.loads((HERE / 'work_catalog.json').read_text(encoding='utf-8'))
GROUPS = {item['id']: item for item in CATALOG['groups']}
ITEMS = {item['id']: item for item in CATALOG['items']}
PARENT = 'skillto-ai-studio'


def user_config():
    if 'STASS_PREFERENCES_DIR' in os.environ:
        return Path(os.environ['STASS_PREFERENCES_DIR'])
    base = Path(os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return base / 'Skillto.ai' / 'Studio' / 'preferences'


@contextmanager
def locked():
    directory = user_config()
    directory.mkdir(parents=True, exist_ok=True)
    if os.name == 'nt':
        with installation_lock(directory):
            yield
    else:
        import fcntl
        with (directory / 'lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield


def read_json(name, default):
    try:
        return json.loads((user_config() / name).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def profile():
    return read_json('work.json', {'revision': 0, 'groups': None, 'items': []})


def checked(values, allowed):
    if not isinstance(values, list) or any(not isinstance(key, str) or key not in allowed for key in values):
        raise ValueError('选择包含未知类别或组件')
    return list(dict.fromkeys(values))


def resolve(groups, items=None):
    groups = checked(groups, GROUPS)
    if items is None:
        items = [key for key, item in ITEMS.items() if set(groups).intersection(item['defaults'])]
    wanted = set(checked(items, ITEMS))
    pending = list(wanted)
    while pending:
        for key in ITEMS[pending.pop()]['requires']:
            if key not in wanted:
                wanted.add(key)
                pending.append(key)
    return [key for key in ITEMS if key in wanted]


def save(groups, items, revision):
    groups = checked(groups, GROUPS)
    items = resolve(groups, items)
    with locked():
        previous = profile()
        if previous['groups'] == groups and previous['items'] == items:
            return previous
        if previous['revision'] != revision:
            raise ValueError('选择已在其他窗口更新，请重新检测后再保存')
        result = dict(groups=groups, items=items, revision=revision + 1)
        atomic_json(user_config() / 'work.json', result)
        return result


def remember(agent, directory):
    with locked():
        paths = read_json('hosts.json', {})
        paths[agent] = str(directory.resolve())
        atomic_json(user_config() / 'hosts.json', paths)


def recorded_destination(agent):
    return Path(read_json('hosts.json', {}).get(agent) or host_root(agent))


def host_root(agent):
    if agent == 'claude':
        return Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude') / 'skills'
    if agent == 'codex':
        return Path.home() / '.agents' / 'skills'
    raise ValueError('WorkBody 安装目录待宿主验证')


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


def same_files(source, target):
    if target.is_symlink() or getattr(target, 'is_junction', lambda: False)() or not target.is_dir():
        return False
    if not (source / 'SKILL.md').is_file() or not (target / 'SKILL.md').is_file():
        return False
    paths = set(package_files(source))
    return paths == set(package_files(target)) and all(
        (source / name).read_bytes() == (target / name).read_bytes() for name in paths)


def installed(skill, directory):
    path = directory / skill
    if not os.path.lexists(path):
        return '待安装'
    try:
        if same_files(ROOT / 'skills' / skill, path):
            return '已安装'
    except (OSError, ValueError):
        pass
    return '有差异，需核对'


def claude_plugin_present():
    config = host_root('claude').parent
    path = config / 'plugins' / 'installed_plugins.json'
    if not path.exists():
        return False
    plugins = json.loads(path.read_text(encoding='utf-8-sig')).get('plugins', {})
    return any(key.split('@')[0] == PARENT for key in plugins)


def beam_present():
    base = HERE.parent / 'beam'
    return all((base / name).is_file() for name in ('SkilltoBeam.exe', 'icudtl.dat', 'resources/app.asar'))


def snapshot(agent):
    if agent not in ('codex', 'claude', 'workbody'):
        raise ValueError('未知宿主')
    info = {'catalog': CATALOG, 'profile': profile(), 'beam': beam_present()}
    path = None
    if agent != 'workbody':
        path = recorded_destination(agent)
    plugin = agent == 'claude' and claude_plugin_present()
    def status(name):
        if path is None:
            return '宿主待验证'
        if plugin:
            return '完整插件已登记，需核对'
        return installed(name, path)
    components = {
        'cat-extension': '需在 Chrome 验证',
        'studio': '已安装' if (HERE.parent / 'release.json').is_file() else '开发环境，需核对发行包',
        'beam': '文件已就位，启动时校验' if info['beam'] else '待安装',
    }
    info['components'] = components
    info['status'] = {key: components[key] if row.get('kind') == 'component' else status(PARENT + '-' + key)
                      for key, row in ITEMS.items()}
    info['parentStatus'] = status(PARENT)
    info['source'] = CATALOG['version']
    manifest = ROOT / 'release.json'
    if manifest.is_file():
        info['source'] = json.loads(manifest.read_text(encoding='utf-8'))['commit']
    return info


def dispatch(request):
    action = request.get('action')
    if action == 'save':
        return save(request['groups'], request['items'], request['revision'])
    if action == 'inspect':
        return snapshot(request['agent'])
    if action == 'navigation':
        current = profile()
        selection = current['groups']
        return {'revision': current['revision'], 'groups': selection, 'views': sorted({view for key in selection or [] for view in GROUPS[key]['views']}),
                'beam': beam_present()}
    raise ValueError('未知操作')


if __name__ == '__main__':
    try:
        print(json.dumps(dispatch(json.load(sys.stdin)), ensure_ascii=True))
    except (OSError, KeyError, TypeError, ValueError) as error:
        sys.exit(str(error))
