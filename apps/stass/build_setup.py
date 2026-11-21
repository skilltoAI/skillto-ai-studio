"""Wrap a verified Windows payload in one executable. Sign the output after assembly."""
import argparse
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zipfile

from release_gate import sha256, verify_package


def build(package, manifest_digest, output):
    verify_package(package, manifest_digest)
    source = Path(__file__).parent / 'setup/windows/main.go'
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='stass-setup-build-') as directory:
        directory = Path(directory)
        archive = directory / 'payload.zip'
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as bundle:
            for file in sorted(package.rglob('*')):
                if file.is_file():
                    bundle.write(file, file.relative_to(package).as_posix())
        stub = directory / 'Setup.exe'
        flags = f'-H=windowsgui -s -w -X main.archiveDigest={sha256(archive)} -X main.manifestDigest={manifest_digest}'
        subprocess.run(['go', 'build', '-trimpath', '-ldflags', flags, '-o', str(stub), str(source)], check=True)
        offset = stub.stat().st_size
        with stub.open('ab') as handle, archive.open('rb') as bundle:
            shutil.copyfileobj(bundle, handle, 1024 * 1024)
            handle.write(struct.pack('<Q8s', offset, b'STASSZIP'))
        stub.rename(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', required=True, type=Path)
    options = parser.parse_args()
    if options.output.exists():
        parser.error('output already exists')
    build(options.package.resolve(), options.manifest_sha256.lower(), options.output.resolve())
