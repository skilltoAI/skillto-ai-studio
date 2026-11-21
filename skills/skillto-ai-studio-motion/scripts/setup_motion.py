"""Configure an isolated local renderer environment; no host credentials."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from motion_store import root

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ffmpeg-directory',required=True);p.add_argument('--chrome',required=True)
    a=p.parse_args()
    if sys.version_info < (3,11):raise SystemExit('Python 3.11+ required')
    ff=Path(a.ffmpeg_directory).resolve(strict=True);chrome=Path(a.chrome).resolve(strict=True)
    if not chrome.is_file() or not shutil.which('ffmpeg',path=str(ff)) or not shutil.which('ffprobe',path=str(ff)):
        raise SystemExit('Need real Chrome, FFmpeg and ffprobe executables')
    if not shutil.which('node'):raise SystemExit('Install Node.js 22+ before setup')
    env=root()/'environment'; py=env/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    if not py.is_file():subprocess.run([sys.executable,'-m','venv',str(env)],check=True)
    if subprocess.run([str(py),'-m','pip','--version'],capture_output=True).returncode:
        subprocess.run([str(py),'-m','ensurepip','--upgrade'],check=True)
    subprocess.run([str(py),'-m','pip','install','numpy','scipy','soundfile','pyloudnorm','jsonschema'],check=True)
    lock=subprocess.check_output([str(py),'-m','pip','freeze'],text=True)
    (root()/'environment.lock.txt').write_text(lock,'utf-8')
    (root()/'runtime.local.json').write_text(json.dumps({'python':str(py),'ffmpegDirectory':str(ff),'chrome':str(chrome)},indent=2),'utf-8')
    from motion_runtime import doctor
    print(json.dumps(doctor(),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
