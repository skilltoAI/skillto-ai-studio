"""Build the Windows x64 Beam companion from a pinned upstream source archive."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile


COMMIT = '808c3b2c091a3270f1417974ea16b5f16ad00159'
VERSION = '0.6.2'
BUILD_URL = f'https://codeload.github.com/BeamRecorder/Beam/zip/{COMMIT}'
APP_ID = 'ai.skillto.studio.beam'
HERE = Path(__file__).resolve().parent


def replace(source, relative, old, new):
    path = source / relative
    text = path.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise ValueError(f'Expected exactly one branding patch anchor in {relative}')
    path.write_text(text.replace(old, new), encoding='utf-8')


def integrate(source):
    metadata = source / 'package.json'
    package = json.loads(metadata.read_text(encoding='utf-8'))
    if package['version'] != VERSION or package['build']['appId'] != 'com.beam.app':
        raise ValueError('Unexpected Beam package metadata')
    package['desktopName'] = APP_ID
    package['build'].update(appId=APP_ID, productName='SkilltoBeam', executableName='SkilltoBeam')
    package['build'].pop('publish')
    metadata.write_text(json.dumps(package, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    replace(source, 'apps/desktop/cli/beam.cmd',
            r'%~dp0..\..\Beam.exe', r'%~dp0..\..\SkilltoBeam.exe')
    replace(source, 'apps/desktop/electron/main.cjs', 'initializeSingleInstance({\n  app,',
            # Electron uses the application name in media request headers.
            # Keep it ASCII and apply the localized brand to visible titles.
            "app.setName('SkilltoBeam');\n"
            "app.setAppUserModelId('" + APP_ID + "');\n"
            "app.setPath('userData', path.join(app.getPath('appData'), 'Skillto.ai', 'Studio', 'Beam'));\n"
            "app.on('browser-window-created', (_event, window) => {\n"
            "  const prefix = 'Skillto.ai | 个人工作台 · ';\n"
            "  const title = (value) => prefix + (value && value !== 'SkilltoBeam' ? value : 'Beam');\n"
            "  window.setTitle(title(window.getTitle()));\n"
            "  window.on('page-title-updated', (event, value) => {\n"
            "    event.preventDefault();\n"
            "    window.setTitle(title(value));\n"
            "  });\n"
            "});\n"
            "initializeSingleInstance({\n  app,")
    replace(source, 'apps/desktop/electron/lifecycle/application-updater.cjs',
            "resolveUpdatePreview({ app, autoUpdater, enabled: process.env.BEAM_UPDATE_PREVIEW === '1' })",
            'resolveUpdatePreview({ app, autoUpdater, enabled: false })')
    replace(source, 'apps/desktop/electron/lifecycle/application-updater.cjs',
            'const updateCache = app.isPackaged', 'const updateCache = false')
    replace(source, 'apps/desktop/electron/lifecycle/application-updater.cjs',
            'isPackaged: app.isPackaged || resolved.preview,', 'isPackaged: false,')
    replace(source, 'apps/desktop/electron/storage/user-paths.cjs',
            "path.join(app.getPath('videos'), 'Beam', 'user')",
            "path.join(app.getPath('videos'), 'Skillto.ai Studio Beam', 'user')")
    replace(source, 'apps/desktop/src/components/brand/BrandLogo.vue',
            '    <BrandSymbol :symbol=',
            '''    <img v-if="symbol === 'beam'" src="/brand/studio-wordmark.png"
         alt="Skillto.ai | 个人工作台" style="max-width: 132px; height: 20px; object-fit: contain" />
    <BrandSymbol :symbol=''')
    shutil.copyfile(HERE / 'modules/table/scripts/windows/ui/assets/studio-wordmark.png',
                    source / 'public/brand/studio-wordmark.png')
    # These upstream decorative packs have no confirmed commercial redistribution grant.
    decorative_cursors = source / 'public/cursorPacks/assets'
    if decorative_cursors.exists():
        shutil.rmtree(decorative_cursors)
    packs = source / 'apps/desktop/src/components/editor/properties/cursor/builtin-cursor-packs.json'
    packs.write_text('[]\n', encoding='utf-8')


def build(output, archive=None, *, checkout=None, validate_only=False):
    output.mkdir(parents=True, exist_ok=False)
    if not archive and not checkout:
        archive = output / f'beam-{COMMIT}.zip'
        with urllib.request.urlopen(BUILD_URL, timeout=60) as response, archive.open('wb') as file:
            shutil.copyfileobj(response, file)
    with tempfile.TemporaryDirectory(prefix='stass-beam-', dir=output.parent) as folder:
        if checkout:
            head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip()
            if head != COMMIT or subprocess.check_output(
                    ['git', 'status', '--porcelain', '--untracked-files=no'], cwd=checkout):
                raise ValueError('Expected a clean checkout of the pinned Beam commit')
            source = Path(folder) / 'Beam'
            files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=checkout).decode('utf-8')
            for relative in filter(None, files.split('\0')):
                src = checkout / relative
                if src.is_file():
                    target = source / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, target)
        elif zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as bundle:
                roots = {name.split('/', 1)[0] for name in bundle.namelist()}
                if roots != {f'Beam-{COMMIT}'} and not (
                    roots == {'Beam-master'} and bundle.comment == COMMIT.encode('ascii')
                ):
                    raise ValueError('Expected the pinned Beam source ZIP')
                bundle.extractall(folder)
            source = Path(folder) / roots.pop()
        else:
            with tarfile.open(archive, 'r:gz') as bundle:
                roots = {member.name.split('/', 1)[0] for member in bundle.getmembers()}
                if roots not in ({f'Beam-{COMMIT}'}, {f'BeamRecorder-Beam-{COMMIT[:7]}'}):
                    raise ValueError('Expected the pinned Beam source tarball')
                bundle.extractall(folder, filter='data')
            source = Path(folder) / roots.pop()
        integrate(source)
        with zipfile.ZipFile(output / 'beam-corresponding-source.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(source.rglob('*')):
                relative = path.relative_to(source)
                # These gallery assets are not inputs to the Windows application build.
                # Keep their redistribution restrictions outside the program source bundle.
                if (relative.parts[0] in {'examples', 'experiments'}
                        or relative.parts[:2] == ('website', 'public')
                        or relative.parts[:3] == ('website', 'docs', 'public')):
                    continue
                if path.is_file():
                    bundle.write(path, Path('Beam') / relative)
        if validate_only:
            return
        bun = shutil.which('bun.exe') or shutil.which('bun')
        if not bun:
            raise RuntimeError('Install Bun 1.4.2 and make bun available on PATH')
        if subprocess.check_output([bun, '--version'], text=True).strip() != '1.4.2':
            raise RuntimeError('The pinned Beam build requires Bun 1.4.2')
        env = {**os.environ, 'CSC_IDENTITY_AUTO_DISCOVERY': 'false'}
        cargo_bin = Path.home() / '.cargo/bin'
        if cargo_bin.is_dir():
            env['PATH'] = str(cargo_bin) + os.pathsep + env['PATH']
        for args in (['install', '--frozen-lockfile'], ['run', 'build'],
                     ['x', 'electron-builder', '--win', '--x64', '--dir', '--publish', 'never']):
            subprocess.run([bun, *args], cwd=source, env=env, check=True)
        runtime = source / 'dist_electron/win-unpacked'
        for relative in ('SkilltoBeam.exe', 'icudtl.dat', 'resources/app.asar',
                         f'resources/capture-engine/capture-engine-{VERSION}.exe'):
            if not (runtime / relative).is_file():
                raise ValueError(f'Incomplete Windows x64 Beam build: {relative}')
        shutil.copytree(runtime, output / 'beam')
        licenses = output / 'beam-notices'
        licenses.mkdir()
        for relative, name in (
            ('LICENSE', 'MPL-2.0.txt'),
            ('LICENSING.md', 'LICENSING.md'),
            ('THIRD_PARTY_NOTICES.md', 'THIRD_PARTY_NOTICES.md'),
            ('public/THIRD_PARTY_NOTICES.md', 'RESOURCE-NOTICES.md'),
            ('packages/engine/src/zoom/recordly/LICENSE.md', 'Recordly-AGPL-3.0.txt'),
            ('docs/third-party/ffmpeg.md', 'FFmpeg.md'),
        ):
            shutil.copyfile(source / relative, licenses / name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument('--archive', type=Path, help='Local ZIP or tarball of the pinned official source')
    inputs.add_argument('--checkout', type=Path, help='Clean Git checkout at the pinned commit')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--validate-only', action='store_true', help='Apply the source changes without building Electron')
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('Use a Windows x64 build host')
    build(args.output.resolve(), args.archive, checkout=args.checkout, validate_only=args.validate_only)
