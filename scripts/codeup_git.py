"""Operation-scoped Codeup Git credentials. Never share FETCH/PUSH secrets."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys
from urllib.parse import urlsplit


def setting(scope: str, field: str) -> str:
    name = f'CODEUP_{scope.upper()}_{field}'
    if name in os.environ:
        return os.environ[name]
    if os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
                return str(winreg.QueryValueEx(key, name)[0])
        except FileNotFoundError:
            pass
    return ''


def config(scope: str) -> dict:
    if scope not in {'fetch', 'push'}:
        raise ValueError('Scope must be fetch or push')
    values = {key: setting(scope, key) for key in
              ('BASE_URL', 'USERNAME', 'PASSWORD', 'SSH_KEY_FILE', 'AUTH_MODE')}
    url = urlsplit(values['BASE_URL'])
    if (url.scheme != 'https' or url.hostname != 'codeup.aliyun.com'
            or url.username or url.password or url.port or url.query or url.fragment
            or not url.path.endswith('.git') or '..' in url.path.split('/')
            or any(c in values['BASE_URL'] for c in '\r\n\x00')):
        raise ValueError(f'CODEUP_{scope.upper()}_BASE_URL must be a credential-free Codeup HTTPS repository URL')
    if not values['USERNAME'] or any(c in values['USERNAME'] for c in '\r\n\x00'):
        raise ValueError(f'CODEUP_{scope.upper()}_USERNAME is missing or invalid')
    if values['AUTH_MODE'] not in {'https-password', 'ssh'}:
        raise ValueError(f'CODEUP_{scope.upper()}_AUTH_MODE must be https-password or ssh')
    if values['AUTH_MODE'] == 'https-password':
        if not values['PASSWORD'] or any(c in values['PASSWORD'] for c in '\r\n\x00'):
            raise ValueError(f'CODEUP_{scope.upper()}_PASSWORD is missing or invalid')
    else:
        if values['USERNAME'] != 'git':
            raise ValueError('Codeup SSH username must be git')
        key = Path(values['SSH_KEY_FILE']).expanduser()
        if not values['SSH_KEY_FILE'] or not key.is_absolute() or not key.is_file() or key.suffix == '.pub':
            raise ValueError(f'CODEUP_{scope.upper()}_SSH_KEY_FILE must identify an existing absolute private-key file')
        values['SSH_KEY_FILE'] = key.as_posix()
    return values


def credential(scope: str, operation: str) -> int:
    # Git captures this output over a pipe. Never invoke this mode in a terminal.
    if sys.stdin.isatty() or sys.stdout.isatty():
        return 1
    if operation != 'get':
        return 0  # No shared credential-manager writes or erasures.
    values = config(scope)
    expected = urlsplit(values['BASE_URL'])
    fields = dict(line.rstrip('\n').split('=', 1) for line in sys.stdin
                  if '=' in line)
    if (values['AUTH_MODE'] != 'https-password'
            or fields.get('protocol') != 'https'
            or fields.get('host') != expected.netloc
            or fields.get('path', '').lstrip('/') != expected.path.lstrip('/')):
        return 1
    sys.stdout.write('username=' + values['USERNAME'] + '\npassword=' + values['PASSWORD'] + '\n\n')
    return 0


def command(scope: str, operation: str, target: str | None = None):
    values = config(scope)
    env = os.environ.copy()
    other = 'PUSH' if scope == 'fetch' else 'FETCH'
    for key in list(env):
        if key.startswith('CODEUP_' + other + '_'):
            env.pop(key, None)
    # Pin this process's selected settings, including on already-running Windows hosts.
    for key, value in values.items():
        env[f'CODEUP_{scope.upper()}_{key}'] = value
    for key in list(env):
        if key.startswith(('GIT_TRACE', 'GIT_CONFIG_')) or key in {'GIT_CURL_VERBOSE', 'GIT_ASKPASS', 'SSH_ASKPASS', 'GIT_SSH', 'GIT_SSH_COMMAND'}:
            env.pop(key, None)
    env.update(GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
    args = ['git', '-c', 'credential.helper=', '-c', 'credential.useHttpPath=true',
            '-c', 'core.askPass=', '-c', 'credential.interactive=false', '-c', 'http.followRedirects=false']
    url = values['BASE_URL']
    if values['AUTH_MODE'] == 'https-password':
        helper = '!' + shlex.join([Path(sys.executable).as_posix(), Path(__file__).resolve().as_posix(), '_credential', scope])
        args += ['-c', 'credential.helper=' + helper]
    else:
        parsed = urlsplit(url)
        url = 'git@' + parsed.hostname + ':' + parsed.path.lstrip('/')
        env['GIT_SSH_COMMAND'] = shlex.join(['ssh', '-F', 'none', '-i', values['SSH_KEY_FILE'],
                                           '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none',
                                           '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes'])
    if operation == 'probe':
        args += ['ls-remote', '--symref', url, 'HEAD']
    elif operation == 'fetch' and scope == 'fetch':
        args += ['fetch', '--no-tags', url, '+refs/heads/*:refs/remotes/codeup/*']
    elif operation == 'clone' and scope == 'fetch' and target:
        args += ['clone', '--', url, str(Path(target).resolve())]
    elif operation == 'push' and scope == 'push' and target:
        checked = subprocess.run(['git', 'check-ref-format', 'refs/heads/' + target], capture_output=True)
        if checked.returncode or not target.startswith('codex/'):
            raise ValueError('Specify a valid codex/ task branch; this helper never pushes main, tags or deletes')
        args += ['push', url, f'refs/heads/{target}:refs/heads/{target}']
    else:
        raise ValueError('Operation and credential scope do not match')
    return args, env, values


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == '_credential':
        return credential(sys.argv[2], sys.argv[3])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['probe', 'fetch', 'clone', 'push'])
    parser.add_argument('--scope', choices=['fetch', 'push'])
    parser.add_argument('--destination')
    parser.add_argument('--branch')
    a = parser.parse_args()
    scope = a.scope or ('push' if a.operation == 'push' else 'fetch')
    try:
        args, env, values = command(scope, a.operation, a.destination if a.operation == 'clone' else a.branch)
        result = subprocess.run(args, env=env, capture_output=True)
        for output, stream in [(result.stdout, sys.stdout), (result.stderr, sys.stderr)]:
            message = output.decode('utf-8', errors='replace')
            for s in ('fetch', 'push'):
                secret = setting(s, 'PASSWORD')
                if secret:
                    message = message.replace(secret, '[REDACTED]')
            stream.write(message)
        return result.returncode
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        # Do not stringify subprocess exceptions that could contain child environment/output.
        print(str(error) if isinstance(error, ValueError) else 'Codeup Git process failed or timed out', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
