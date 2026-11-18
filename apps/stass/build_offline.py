"""Build an offline Windows candidate from committed sources and local wheels."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from release_gate import sha256, verify_package


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ZIP_HASH = '9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38'


def build(output, version, python_zip, wheels, launcher):
    if sha256(python_zip) != PYTHON_ZIP_HASH:
        raise ValueError('Expected the official Python 3.13.17 amd64 embeddable archive')
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='offline-build-') as temp:
        temp = Path(temp)
        payload = temp/'payload'
        payload.mkdir()
        runtime = payload/'runtime'
        source_zip = temp/'source.zip'
        commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        subprocess.run(['git','archive','--format=zip','-o',str(source_zip),commit,
                        'apps/stass','skills','scripts/install.py','README.md','docs/规范','技术规范.md'],cwd=ROOT,check=True)
        with zipfile.ZipFile(source_zip) as source:
            source.extractall(temp/'source')
        source = temp/'source'
        (source/'apps/stass').rename(payload/'program')
        for name in ('skills','scripts','README.md','docs','技术规范.md'):
            (source/name).rename(payload/name)
        shutil.copyfile(payload/'program/Install.ps1',payload/'Install.ps1')
        shutil.copyfile(launcher,payload/'Skillto.ai Studio.exe')
        with zipfile.ZipFile(python_zip) as archive:
            archive.extractall(runtime)
        (runtime/'python313._pth').write_text('python313.zip\n.\npackages\n../program\n',encoding='ascii')
        subprocess.run([sys.executable,'-m','pip','install','--no-index','--find-links',str(wheels),
                        '--only-binary=:all:','--no-compile','--target',str(runtime/'packages'),
                        '-r',str(payload/'program/requirements-windows.lock.txt')],check=True)
        subprocess.run([str(runtime/'python.exe'),'-B','-c','import uvicorn, mcp, playwright, psycopg'],check=True)
        files={path.relative_to(payload).as_posix():sha256(path) for path in sorted(payload.rglob('*')) if path.is_file()}
        manifest=payload/'release.json'
        manifest.write_text(json.dumps(dict(format=1,version=version,commit=commit,protocol=1,dataSchema=1,files=files),
                                       ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        digest=sha256(manifest)
        verify_package(payload,digest)
        payload.rename(output)
        return digest


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--version',required=True)
    parser.add_argument('--python-zip',required=True,type=Path)
    parser.add_argument('--wheels',required=True,type=Path)
    parser.add_argument('--launcher',required=True,type=Path)
    args=parser.parse_args()
    print('Manifest SHA-256:',build(args.output.resolve(),args.version,args.python_zip.resolve(),args.wheels.resolve(),args.launcher.resolve()))
