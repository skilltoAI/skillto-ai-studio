"""Install a verified local program package without network access."""
import argparse
import json
from pathlib import Path

from release_gate import stage, verify_package, select_offline
from runtime_control import start
from runtime_state import RuntimeState, installation_lock


def install(package, digest, root=None, port=None, migrated_data=None):
    package = Path(package).resolve(strict=True)
    runtime = RuntimeState(root)
    verify_package(package, digest)
    with installation_lock(runtime.root):
        if runtime.path.exists():
            state = runtime.read()
            if migrated_data and Path(migrated_data).resolve() != Path(state['dataRoot']):
                raise ValueError('Existing instance is registered with another data root')
            if port is not None and port != state['port']:
                raise ValueError('Existing workbench uses a different port')
            if state.get('program') and state.get('release', {}).get('manifestSha256') != digest:
                raise ValueError('Another program version is registered. Installation cannot replace it.')
        else:
            state = runtime.initialize(data_root=migrated_data, port=port or 8080, migrated=bool(migrated_data))
        if not state.get('release'):
            key = stage(runtime.root, package, digest)
            state = select_offline(runtime.root, key, digest, state['generation'])
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
    parser.add_argument('--migrated-data')
    options = parser.parse_args()
    print(json.dumps(install(options.package, options.manifest_sha256, options.root, options.port, options.migrated_data)))
