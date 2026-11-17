"""Per-host credentials; only hashes are persisted in the service registry."""
import hashlib
import json
from pathlib import Path
import secrets

from runtime_state import RuntimeState, atomic_json, installation_lock

HOSTS = ('codex', 'claude', 'openclaw')


def digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def issue(root, host):
    if host not in HOSTS:
        raise ValueError('Unknown host')
    runtime = RuntimeState(root)
    with installation_lock(runtime.root):
        state = runtime.read()
        registry_file = runtime.root / 'config' / 'clients.json'
        registry = json.loads(registry_file.read_text()) if registry_file.exists() else {}
        token_file = runtime.root / 'config' / ('client-' + host + '.token')
        if host in registry and token_file.exists():
            token = token_file.read_text().strip()
            if secrets.compare_digest(registry[host]['sha256'], digest(token)):
                return {'url':state['url'], 'instanceId':state['instanceId'], 'tokenFile':str(token_file)}
            raise ValueError('Host credential differs from registry; explicit revoke required')
        if token_file.exists():
            raise ValueError('Unregistered credential exists; explicit revoke required')
        token = secrets.token_urlsafe(48)
        token_file.write_text(token, encoding='utf-8')
        registry[host] = {'sha256':digest(token)}
        atomic_json(registry_file, registry)
        profile = {'url':state['url'], 'instanceId':state['instanceId'], 'tokenFile':str(token_file)}
        atomic_json(runtime.root / 'config' / ('client-' + host + '.json'), profile)
        return profile


def revoke(root, host):
    if host not in HOSTS:
        raise ValueError('Unknown host')
    runtime = RuntimeState(root)
    with installation_lock(runtime.root):
        registry_file = runtime.root / 'config' / 'clients.json'
        registry = json.loads(registry_file.read_text()) if registry_file.exists() else {}
        registry.pop(host, None)
        atomic_json(registry_file, registry)
        (runtime.root / 'config' / ('client-' + host + '.token')).unlink(missing_ok=True)
        (runtime.root / 'config' / ('client-' + host + '.json')).unlink(missing_ok=True)


def authenticate(registry_file, token):
    if not registry_file or not token:
        return None
    try:
        registry = json.loads(Path(registry_file).read_text())
        value = digest(token)
        for host, record in registry.items():
            if host in HOSTS and secrets.compare_digest(record['sha256'], value):
                return host
    except (OSError, ValueError, KeyError, TypeError):
        pass  # Fail closed on invalid or unavailable registry.
    return None
