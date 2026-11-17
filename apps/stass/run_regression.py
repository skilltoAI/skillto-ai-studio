"""Run migrated module baselines in separate processes and isolated data roots."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
SUITES = {
    'tables': ('table/scripts', 'test_server.py'),
    'rewrites_browser': ('table/scripts/tests', 'test_*.py'),
    'reports': ('table/reporting', 'test_*.py'),
    'motions': ('motion/scripts', 'test_*.py'),
    'breakdowns_extension': ('workbench/scripts', 'test_*.py'),
}


def run(item):
    name, (folder, pattern) = item
    with tempfile.TemporaryDirectory(prefix='stass-regression-') as data:
        env = os.environ.copy()
        env['SKILLTO_TABLE_ROOT'] = data
        env['SKILLTO_REPORT_CONFIG'] = str(Path(data) / 'report-config.json')
        for key in ('SKILLTO_TABLE_API_URL', 'SKILLTO_TABLE_API_KEY', 'SKILLTO_TABLE_API_KEY_FILE'):
            env.pop(key, None)
        directory = ROOT / 'modules' / folder
        env['PYTHONPATH'] = os.pathsep.join([str(ROOT/'modules/table/scripts'), str(directory)])
        result = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', str(directory), '-p', pattern, '-v'],
                                env=env, cwd=ROOT, capture_output=True, timeout=600)
        output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
        return name, {'exitCode': result.returncode, 'output': output}


if __name__ == '__main__':
    destination = Path(sys.argv[1]).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = dict(pool.map(run, SUITES.items()))
    for name, result in results.items():
        (destination/(name+'.log')).write_text(result['output'], encoding='utf-8')
        print(name, result['exitCode'], result['output'][-500:])
    (destination/'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    raise SystemExit(any(result['exitCode'] for result in results.values()))
