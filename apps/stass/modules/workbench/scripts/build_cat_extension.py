"""Overlay the SKillto UI onto the explicitly selected Cat Catch source tree."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

BASELINE = '019c465794b5871701383e4485c0e9ee7be2f840'
BRAND = 'Skillto-AI-Studio'


def build(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Source and destination must be separate sibling trees')
    if not (source / 'manifest.json').is_file() or not (source / 'LICENSE').is_file():
        raise ValueError('Select the original Cat Catch source with manifest and GPL license')
    if (source / '.git').exists():
        revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        if revision != BASELINE: raise ValueError('Upstream revision changed; review the overlay before building')
    assets = Path(__file__).resolve().parents[1] / 'assets'
    overlay = assets / 'cat-workbench'
    if not destination.exists(): shutil.copytree(source, destination, ignore=shutil.ignore_patterns('.git'))
    for path in overlay.rglob('*'):
        if path.is_file():
            target = destination / path.relative_to(overlay)
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, target)
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    manifest.update(name=BRAND, description='发现网页视频，预览选段后下载或保存到本地拉片工作台。',
        version='2.7.4.4', version_name='2.7.4-skillto.4', minimum_chrome_version='116')
    manifest['action']['default_title'] = BRAND
    manifest['commands'] = {'_execute_action': {}}
    manifest.pop('options_ui', None)
    manifest['optional_permissions'] = []
    manifest['content_scripts'].append({'matches': ['http://127.0.0.1/*'],
        'js': ['js/studio-workspace-connect.js'], 'run_at': 'document_idle'})
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    init = (source / 'js/init.js').read_text(encoding='utf-8')
    rule = r'    /^https:\/\/.*\.douyin\.com\/.*$/i,'
    if init.count(rule) != 1: raise ValueError('Expected Douyin exclusion rule was not found exactly once')
    (destination / 'js/init.js').write_text(init.replace(rule+'\n', '', 1), encoding='utf-8', newline='\n')
    background = (source / 'js/background.js').read_text(encoding='utf-8')
    listener = 'chrome.runtime.onMessage.addListener(function (Message, sender, sendResponse) {'
    if background.count(listener) != 1: raise ValueError('Upstream message listener changed')
    background = background.replace(listener, listener+'\n    if (Message.type?.startsWith("studio:")) return;', 1)
    start = background.index('    if (details.reason == "update") {', background.index('chrome.runtime.onInstalled'))
    end = background.index('    if (details.reason == "install") {', start)
    background = background[:start] + '    if (details.reason == "update") InitOptions();\n' + background[end:]
    background += '\n// Local product integration; retain Cat Catch discovery unchanged.\nimportScripts("/js/studio-background.js");\n'
    (destination / 'js/background.js').write_text(background, encoding='utf-8', newline='\n')
    shutil.copy2(assets / 'extension/connection.js', destination / 'js/studio-connection.js')
    connector = (assets / 'extension/workspace-connect.js').read_text(encoding='utf-8').replace("type: 'workbench-connect'", "type: 'studio:pair'")
    (destination / 'js/studio-workspace-connect.js').write_text(connector, encoding='utf-8', newline='\n')
    for relative in ('img/studio-logo.png', 'img/icon.png', 'img/icon128.png'):
        shutil.copy2(assets / 'extension/icons/128.png', destination / relative)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(build(args.source, args.destination))
