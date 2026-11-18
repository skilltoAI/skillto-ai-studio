"""Serve and import explicitly referenced legacy media under authenticated STASS routes."""
import json
import mimetypes
from pathlib import Path, PurePosixPath
import re
import shutil
from urllib.parse import unquote

from migration import digest

FAMILIES = ('assets/research/', 'assets/rewrite-case/', 'assets/rewrite-audio/',
            'generated/', 'media/', 'artifacts/omni_depth/')
EXTENSIONS = {'.png','.jpg','.jpeg','.webp','.gif','.mp4','.webm','.wav','.mp3','.txt','.md','.vtt','.srt'}
PREFIX = '(?:' + '|'.join(map(re.escape,FAMILIES)) + ')'
REFERENCE = re.compile(r'(?<![\w/:.])(?:https?://(?:127\.0\.0\.1|localhost):8880)?/(' + PREFIX + r'[^\s<>"\'`\])?#]+)')


def relative(value):
    value = unquote(value)
    path = PurePosixPath(value)
    if (not value.startswith(FAMILIES) or path.is_absolute() or '..' in path.parts
            or '\\' in value or ':' in value or '\x00' in value or path.suffix.lower() not in EXTENSIONS):
        raise ValueError('Unsupported legacy asset path')
    return path


def safe_file(root, path):
    root = Path(root).resolve()
    result = (root / path).resolve()
    if not result.is_relative_to(root):
        raise ValueError('Asset outside mapped source')
    return result


def rewrite_urls(value):
    if isinstance(value,str):
        return REFERENCE.sub(lambda match: '/STASS/'+match[1], value)
    if isinstance(value,list):
        return [rewrite_urls(item) for item in value]
    if isinstance(value,dict):
        return {key:rewrite_urls(item) for key,item in value.items()}
    return value


def source_path(name, project, scrapling, voice):
    head, tail = next((part,name[len(part):]) for part in FAMILIES if name.startswith(part))
    path = relative(name)
    tail = PurePosixPath(*path.parts[len(PurePosixPath(head).parts):])
    if head == 'assets/rewrite-case/':
        if re.fullmatch(r'slide-[1-4]\.png',str(tail)):
            return safe_file(project/'work', 'note_7694608697625416674_slide_'+tail.name[6:])
        if tail.parts[0] in ('7700790158655753507','7705653137557818639') and len(tail.parts)==2:
            filename = tail.name.replace('contact-', 'contact_', 1)
            return safe_file(project/'work', 'video_'+tail.parts[0]+'/'+filename)
        raise ValueError('Unknown rewrite case mapping')
    roots={'assets/research/':project/'research','assets/rewrite-audio/':voice,
           'generated/':scrapling/'downloads/generated_table_images',
           'media/':scrapling/'downloads/douyin_originals',
           'artifacts/omni_depth/':scrapling/'outputs/omni_depth'}
    return safe_file(roots[head],tail)


def import_references(data, project, scrapling, voice):
    data,project,scrapling,voice=map(Path,(data,project,scrapling,voice))
    names=set()
    for path in [data/'catalog.json',data/'rewrites.json',*sorted((data/'tables').glob('*.json'))]:
        if path.is_file() and not path.name.startswith('.'):
            names.update(match[1] for match in REFERENCE.finditer(path.read_text(encoding='utf-8-sig')))
    report={'copied':[],'missing':[]}
    for name in sorted(names):
        try:
            path=relative(name)
            source=source_path(name,project,scrapling,voice)
        except ValueError:
            report['missing'].append(name)
            continue
        if not source.is_file():
            report['missing'].append(name)
            continue
        destination=safe_file(data/'legacy-assets',path)
        destination.parent.mkdir(parents=True,exist_ok=True)
        original=digest(source)
        if not destination.is_file() or digest(destination)!=original:
            temporary=destination.with_suffix(destination.suffix+'.copying')
            shutil.copy2(source,temporary)
            if digest(temporary)!=original:
                raise ValueError('Source changed while copying '+name)
            temporary.replace(destination)
        report['copied'].append({'path':path.as_posix(),'sha256':original,'size':destination.stat().st_size})
    (data/'legacy-assets-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def response(data, name):
    from starlette.responses import FileResponse, JSONResponse
    try:
        target=safe_file(data/'legacy-assets',relative(name))
    except ValueError:
        return JSONResponse({'error':'Invalid asset path'},status_code=404)
    if not target.is_file():
        return JSONResponse({'error':'Asset unavailable'},status_code=404)
    content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
    return FileResponse(target,media_type=content_type,headers={'X-Content-Type-Options':'nosniff','Cache-Control':'private, no-store'})
