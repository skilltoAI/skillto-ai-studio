"""Install a verified local program package without network access."""
import argparse
import json
from pathlib import Path

from release_gate import stage, verify_package, verify_selected, select_offline
from runtime_control import start
from runtime_state import RuntimeState, installation_lock


def install(package, digest, root=None, port=None):
    package = Path(package).resolve(strict=True)
    runtime = RuntimeState(root)
    verify_package(package, digest)
    with installation_lock(runtime.root):
        if runtime.path.exists():
            state = runtime.read()
            if port is not None and port != state['port']:
                raise ValueError('Existing workbench uses a different port')
            if state.get('program') and state.get('release', {}).get('manifestSha256') != digest:
                raise ValueError('Another program version is registered. Installation cannot replace it.')
        else:
            state = runtime.initialize(port=port or 8080)
        if not state.get('release'):
            key = stage(runtime.root, package, digest)
            state = select_offline(runtime.root, key, digest, state['generation'])
        verify_selected(runtime, state)
        result = start(runtime.root)
        return {'service':result['service'], 'action':result['action'], 'url':state['url'],
                'instanceId':state['instanceId'], 'version':state['activeVersion'],
                'launcher':str(runtime.root/'versions'/state['release']['key']/'Skillto.ai Studio.exe')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--root')
    parser.add_argument('--port', type=int)
    options = parser.parse_args()
    print(json.dumps(install(options.package, options.manifest_sha256, options.root, options.port)))
