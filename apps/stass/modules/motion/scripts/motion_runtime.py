"""Background downloads and a pinned, reviewed kinetic-user-core/1 adapter."""
import concurrent.futures
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
import motion_store as store
from motion_package import inspect_package, digest, KNOWN_SHA, MAX_PACKAGE
from motion_network import download

EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix='motion')
PROCESSES = {}
CANCELLED = set()
GUARD = threading.RLock()

def config():
    p = store.root() / 'runtime.local.json'
    return json.loads(p.read_text('utf-8')) if p.is_file() else {}

def environment():
    cfg = config(); env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'; env['PYTHONUTF8'] = '1'
    if cfg.get('ffmpegDirectory'): env['PATH'] = cfg['ffmpegDirectory'] + os.pathsep + env.get('PATH','')
    if cfg.get('chrome'): env['CHROME'] = cfg['chrome']
    if cfg.get('previewEncoder'): env['SKILLTO_MOTION_PREVIEW_ENCODER'] = cfg['previewEncoder']
    return cfg, env

def doctor():
    cfg, env = environment()
    py = cfg.get('python') or sys.executable
    checks = {'python': Path(py).is_file(), 'node': bool(shutil.which('node', path=env['PATH'])),
              'ffmpeg': bool(shutil.which('ffmpeg', path=env['PATH'])), 'ffprobe': bool(shutil.which('ffprobe', path=env['PATH'])),
              'chrome': bool(cfg.get('chrome') and Path(cfg['chrome']).is_file())}
    try:
        run = subprocess.run([py, '-B', '-c', 'import numpy,scipy,soundfile,pyloudnorm,jsonschema'], capture_output=True, timeout=20, env=env)
        checks['pythonPackages'] = run.returncode == 0
    except (OSError, subprocess.TimeoutExpired): checks['pythonPackages'] = False
    try:
        ffmpeg = shutil.which('ffmpeg',path=env['PATH'])
        filters = subprocess.run([ffmpeg or 'ffmpeg','-hide_banner','-filters'],capture_output=True,text=True,timeout=10,env=env)
        checks['ffmpegFilters'] = filters.returncode == 0 and all(name in filters.stdout for name in ('sidedata','amix','loudnorm'))
    except (OSError, subprocess.TimeoutExpired): checks['ffmpegFilters'] = False
    return {'checks': checks, 'ready': all(checks.values()), 'supportedProfile': 'kinetic-user-core/1', 'supportedPackageSHA256': KNOWN_SHA}

def update_job(ident, **fields):
    with store.LOCK:
        job = store.get('job', ident); job.update(fields, updatedAt=store.now()); store.write('job', job)
        return job

def cancelled(ident):
    with GUARD: return ident in CANCELLED

def kill_tree(proc):
    if proc.poll() is not None: return
    if os.name == 'nt': subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
    else:
        try: os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError: pass
    try: proc.wait(timeout=10)
    except subprocess.TimeoutExpired: proc.kill()

def cancel(ident):
    job = store.get('job', ident)
    if job['status'] not in ('queued', 'running', 'cancelling'): return job
    with GUARD:
        CANCELLED.add(ident)
        proc = PROCESSES.get(ident)
    update_job(ident, status='cancelling', stage='正在取消')
    if proc: kill_tree(proc)
    return store.get('job', ident)

def command(ident, args, cwd, log, timeout=1800):
    if cancelled(ident): raise InterruptedError('已取消')
    _, env = environment()
    with open(log, 'ab') as output:
        output.write(('\n> ' + ' '.join(map(str, args)) + '\n').encode('utf-8'))
        with GUARD:
            if cancelled(ident): raise InterruptedError('已取消')
            proc = subprocess.Popen(list(map(str, args)), cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                                    start_new_session=os.name != 'nt')
            PROCESSES[ident] = proc
        start = time.monotonic()
        try:
            while proc.poll() is None:
                if cancelled(ident): kill_tree(proc); raise InterruptedError('已取消')
                if time.monotonic() - start > timeout: kill_tree(proc); raise ValueError('执行超时；查看任务日志')
                time.sleep(.2)
            if cancelled(ident): raise InterruptedError('已取消')
            if proc.returncode:
                tail = Path(log).read_text('utf-8', errors='replace')[-2500:]
                raise ValueError('制作命令失败：' + tail)
        finally:
            with GUARD: PROCESSES.pop(ident, None)

def import_package(ident, source):
    source = Path(source).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() != '.motion': raise ValueError('请选择 .motion 文件')
    info = inspect_package(source)
    target = store.root() / 'packages' / (info['sha256'] + '.motion')
    target.parent.mkdir(parents=True, exist_ok=True)
    if source != target and not target.exists(): shutil.copyfile(source, target)
    runner = store.root() / 'runners' / info['sha256']
    if info['status'] == 'verified' and not runner.exists(): inspect_package(target, runner)
    with store.LOCK:
        item = store.get('item', ident); manifest = info['manifest']; output = manifest.get('output', {})
        item.update(localPath=str(target), packageSHA256=info['sha256'], packageInfo=info,
                    runnerPath=str(runner) if runner.is_dir() else '', renderable=info['renderable'],
                    status=info['status'], statusMessage=info.get('reason',''), updatedAt=store.now())
        if manifest.get('template'): item['version'] = manifest['template'].get('version')
        if manifest.get('runtime'): item['engine'] = manifest['runtime'].get('profile', '未知')
        if output.get('width') and output.get('height'):
            from math import gcd
            w,h = int(output['width']),int(output['height']); g=gcd(w,h)
            item['aspect'] = f'{w//g}:{h//g}'
        store.write('item', item)
    return store.public(item)

def basic_params(args):
    if isinstance(args.get('parameters'), dict): return args['parameters']
    return {'mode':'user-media', 'language':'zh', 'layout':'landscape', 'duration':8,
            'title': args.get('title','文字动效'), 'presenterLabel':'', 'scenes':[{'id':'B1','title':args.get('keyword','主题')}],
            'content':{}, 'basic':{'keyword':args.get('keyword',''), 'explanation':args.get('text','')},
            'media':{'presenter':{'mode':'none'}, 'voice':{'mode':'none'}, 'music':{'mode':'none'}},
            'soundEffects':'native', 'captions':[]}

def run_job(ident):
    job = store.get('job', ident)
    try:
        if cancelled(ident): raise InterruptedError('已取消')
        update_job(ident, status='running', stage='准备中')
        item = store.get('item', job['itemId']); args = job['args']
        work = store.root() / 'instances' / ident; work.mkdir(parents=True, exist_ok=True)
        (work/'task.log').write_text(f"{store.now()} {job['kind']} {ident}\n",'utf-8')
        if job['kind'] == 'prepare_previews':
            from motion_media import ensure_preview
            _,env=environment();results=[]
            for item_id in args.get('ids',[item['id']]):
                if cancelled(ident): raise InterruptedError('已取消')
                try:
                    current=store.get('item',item_id)
                    url=current.get('previewUrl')
                    if not url: continue
                    update_job(ident,stage=f"检查/压缩示例 {len(results)+1}：{current['title']}")
                    result=ensure_preview(url,env,execute=lambda cmd:command(ident,cmd,work,work/'task.log',3600),cancel=lambda:cancelled(ident),inspect_only=True)
                    if cancelled(ident): raise InterruptedError('已取消')
                    results.append({'itemId':item_id,'path':str(result) if result else None,'status':'ready' if result else 'source-small'})
                except InterruptedError: raise
                except Exception as exc: results.append({'itemId':item_id,'status':'failed','error':str(exc)[-1000:]})
                update_job(ident,mediaResults=results)
            failures=sum(r['status']=='failed' for r in results)
            update_job(ident,status='failed' if failures else 'succeeded',stage=f'示例视频检查完成 · {len(results)} 项 / {failures} 失败',error=f'{failures} 项失败，见 mediaResults，可重试' if failures else None)
            return
        if job['kind'] in ('download', 'import'):
            source = args.get('path')
            if job['kind'] == 'download':
                update_job(ident, stage='下载 .motion')
                source = download(item.get('downloadUrl') or args.get('url',''), work/'download.motion', MAX_PACKAGE, lambda:cancelled(ident))
            update_job(ident, stage='检查文件与完整性')
            result = import_package(item['id'], source)
            with (work/'task.log').open('a',encoding='utf-8') as log:
                log.write(json.dumps({'status':result['status'],'path':result['localPath']},ensure_ascii=False)+'\n')
            if cancelled(ident): raise InterruptedError('已取消')
            update_job(ident, status='succeeded', stage='检查完成', localPath=result['localPath'])
            return
        if not store.public(item)['renderable']: raise ValueError('此模板尚未保存到本机或运行适配未验证')
        if not doctor()['ready']: raise ValueError('运行依赖缺失，请运行 motion_cli.py doctor 检查')
        if digest(item['localPath']) != KNOWN_SHA: raise ValueError('原包已变化，请重新导入')
        runner = Path(item['runnerPath'])
        integrity = json.loads((runner/'integrity.json').read_text('utf-8'))
        # Compare extracted files against the trusted original, not a mutable local checksum list.
        import zipfile
        with zipfile.ZipFile(item['localPath']) as z:
            trusted = json.loads(z.read('integrity.json'))
            if integrity != trusted: raise ValueError('解包清单已变化')
            for name, checksum in trusted['files'].items():
                if digest(runner/name) != checksum: raise ValueError('工程文件已变化：'+name)
        if not (runner/'node_modules/playwright-core/package.json').is_file():
            update_job(ident, stage='安装模板锁定依赖')
            npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
            if not npm: raise ValueError('缺少 npm')
            command(ident, [npm,'ci','--ignore-scripts','--no-audit','--no-fund'], runner, work/'task.log', 300)
        params = basic_params(args)
        (work/'input.json').write_text(json.dumps(params, ensure_ascii=False, indent=2), 'utf-8')
        cfg,_ = environment(); py = cfg.get('python',sys.executable)
        adapter = [py, '-B', str(runner/'adapter.py')]
        for stage, cmd in [('校验内容与编排', ['plan','--input',work/'input.json','--out',work/'plan.json']),
                           ('绑定素材', ['prepare','--input',work/'input.json','--out',work/'scene']),
                           ('生成实际预览', ['preview','--instance',work/'scene','--out',work/'preview.png','--time','3'])]:
            update_job(ident, stage=stage); command(ident, adapter+cmd, runner, work/'task.log')
        update_job(ident, previewUrl=f'/api/motions/file/{ident}/preview.png')
        update_job(ident, stage='渲染视频与混音')
        command(ident, adapter+['render','--instance',work/'scene','--out',work/'video.mp4'], runner, work/'task.log', 3600)
        final = work/'video-with-audio.mp4'
        if not final.is_file() or not final.stat().st_size: raise ValueError('未生成完整成片')
        update_job(ident, status='succeeded', stage='制作完成', outputPath=str(final),
                   outputUrl=f'/api/motions/file/{ident}/video-with-audio.mp4')
        with store.LOCK:
            item = store.get('item', item['id'])
            item['posterUrl'] = f'/api/motions/file/{ident}/preview.png'
            item['localPreviewUrl'] = f'/api/motions/file/{ident}/video-with-audio.mp4'
            store.write('item', item)
    except InterruptedError:
        update_job(ident, status='cancelled', stage='已取消')
    except Exception as exc:
        update_job(ident, status='cancelled' if cancelled(ident) else 'failed', stage='已取消' if cancelled(ident) else '失败', error=str(exc)[-3000:])

def submit(kind, ident, args):
    if kind not in ('download','import','render','prepare_previews'): raise ValueError('无效任务类型')
    store.get('item', ident)
    with GUARD:
        active = [j for j in store.all_objects('job') if j['status'] in ('queued','running','cancelling')]
        if len(active) >= 10: raise ValueError('队列已满，请等待当前任务')
        if kind != 'render' and any(j['itemId']==ident and j['kind'] in ('download','import') for j in active):
            raise ValueError('此模板已有下载或导入任务')
        job = {'id':store.uid(),'itemId':ident,'kind':kind,'args':args,'status':'queued','stage':'排队中', 'createdAt':store.now()}
        store.write('job', job); EXECUTOR.submit(run_job, job['id'])
    return job

def recover():
    for job in store.all_objects('job'):
        if job['status'] in ('queued','running','cancelling'):
            update_job(job['id'], status='failed', stage='服务重启中断，可重试', error='服务重启；历史输入与输出已保留')
