"""Local manuscript research workspace. Shares only the configured table data root."""
from __future__ import annotations

import json
import copy
import hashlib
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get('SKILLTO_TABLE_ROOT', Path.home() / 'skillto-table-data')).resolve()
FILE = ROOT / 'rewrites.json'
LOCK = threading.RLock()
SECTION_KEYS = ('claims', 'scenario', 'counterintuitive', 'value', 'similar',
                'traffic', 'audience', 'cases')
PLATFORMS = ('douyin', 'xiaohongshu', 'youtube', 'x')
ANALYSIS_KEYS = ('manuscriptAnalysis', 'keyframeAnalysis')
STORYBOARD_KEYS = ('openingStoryboard', 'fullStoryboard')
TABLE_STORE = None  # Inject the running service's authoritative table store.


class RewriteError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def uid():
    return str(uuid.uuid4())


def seed_versions(item):
    item.setdefault('motionStoryboard', {'versions': [], 'activeVersionId': '', 'revision': 0, 'updatedAt': ''})
    for key in STORYBOARD_KEYS:
        item.setdefault(key, {"rows": [], "revision": 0, "updatedAt": ""})
    for key in ANALYSIS_KEYS:
        item.setdefault(key, {'text': '', 'revision': 0, 'updatedAt': ''})
    board = item['openingStoryboard']
    if 'versions' not in board:
        board['versions'] = [{'id': 'v1', 'label': 'V1 原方案', 'rows': copy.deepcopy(board['rows']),
                              'revision': board['revision'], 'createdAt': board['updatedAt'] or now(), 'updatedAt': board['updatedAt']}]
        board['activeVersionId'] = 'v1'
    item.setdefault('videoDurationSeconds', None)
    original = item.get('transcript', '')
    timecoded_lines = [line for line in original.splitlines() if re.match(r'^\[\d{2}:\d{2}\]\s', line)]
    oral_original = '\n'.join(timecoded_lines) if timecoded_lines else original
    if 'transcriptVersions' not in item:
        item['transcriptVersions'] = [{
            'id': 'v0', 'label': 'V0 原稿', 'text': oral_original,
            'prompt': '', 'createdAt': item.get('createdAt', now()),
            'updatedAt': item.get('updatedAt', now()),
        }]
    if not item['transcriptVersions']:
        item['transcriptVersions'] = [{
            'id': 'v0', 'label': 'V0 原稿', 'text': oral_original,
            'prompt': '', 'createdAt': now(), 'updatedAt': now(),
        }]
    if item['transcriptVersions'][0]['id'] == 'v0' and item['transcriptVersions'][0]['text'] == original and timecoded_lines:
        item['transcriptVersions'][0]['text'] = oral_original
    ids = {version['id'] for version in item['transcriptVersions']}
    if item.get('activeTranscriptVersionId') not in ids:
        item['activeTranscriptVersionId'] = 'v0'


def read():
    if FILE.exists():
        data = json.loads(FILE.read_text(encoding='utf-8'))
        for item in data.get('manuscripts', []):
            item.setdefault('transcript', '')
            sections = item.setdefault('sections', {})
            for key in SECTION_KEYS:
                sections.setdefault(key, {'text': '', 'score': None, 'scoreNote': ''})
            seed_versions(item)
        return data
    return {'version': 1, 'knowledgeBases': [], 'manuscripts': []}


def write(data):
    ROOT.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.rewrites-', suffix='.json', dir=ROOT)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, FILE)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def find(items, item_id, label):
    item = next((x for x in items if x['id'] == item_id), None)
    if item is None:
        raise RewriteError(f'{label}不存在')
    return item


def project(data, kb_id, project_id):
    kb = find(data['knowledgeBases'], kb_id, '知识库')
    return kb, find(kb['projects'], project_id, '项目')


def clean_text(value, maximum=20000):
    if not isinstance(value, str) or len(value) > maximum:
        raise RewriteError('文本格式或长度无效')
    return value.strip()


LINE_TAGS = {'ip_voice', 'case', 'remotion'}


def clean_line_annotations(value, text):
    lines = text.split('\n')
    if not isinstance(value, list) or len(value) != len(lines):
        raise RewriteError('逐行类型与稿件行数不一致')
    cleaned = []
    for entry in value:
        if not isinstance(entry, dict) or not isinstance(entry.get('tags'), list):
            raise RewriteError('逐行类型格式无效')
        tags = entry['tags']
        if len(tags) != len(set(tags)) or any(tag not in LINE_TAGS for tag in tags):
            raise RewriteError('逐行类型无效')
        prompt = clean_text(entry.get('remotionPrompt', ''), 10000)
        cleaned.append({'tags': tags, 'remotionPrompt': prompt})
    return cleaned


def validate_url(value):
    value = clean_text(value, 2048)
    if value and not value.startswith(('https://', 'http://')):
        raise RewriteError('来源链接需使用 http 或 https')
    return value


def clean_storyboard(rows):
    if not isinstance(rows, list) or len(rows) > 200:
        raise RewriteError('分镜需为列表，最多200行')
    result, ids = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise RewriteError('分镜行格式无效')
        rid = clean_text(row.get('id', ''), 100)
        if not rid or rid in ids:
            raise RewriteError('分镜行ID缺失或重复')
        ids.add(rid)
        frames = row.get('frames', [])
        if not isinstance(frames, list) or len(frames) > 4:
            raise RewriteError('每个分镜最多4张关键帧')
        cleaned_frames = []
        for frame in frames:
            if not isinstance(frame, dict):
                raise RewriteError('关键帧格式无效')
            url = clean_text(frame.get('url', ''), 2048)
            if not (re.match(r'^https?://[^\s]+$', url) or re.match(r'^/assets/[^\s]+$', url)):
                raise RewriteError('关键帧需使用HTTP(S)或工作台素材地址')
            cleaned_frames.append({'url': url, 'label': clean_text(frame.get('label', ''), 100)})
        result.append({'id': rid, 'frames': cleaned_frames, **{
            key: clean_text(row.get(key, ''), 20000)
            for key in ('title', 'time', 'narration', 'description', 'animation', 'prompt', 'feedback')}})
    return result


def validate_sections(value):
    if not isinstance(value, dict) or set(value) != set(SECTION_KEYS):
        raise RewriteError('需要完整的八项分析')
    result = {}
    for key in SECTION_KEYS:
        section = value[key]
        if not isinstance(section, dict):
            raise RewriteError('分析项格式无效')
        score = section.get('score')
        if score is not None and (type(score) is not int or score < 1 or score > 5):
            raise RewriteError('人工评分必须为 1–5 颗心或未评分')
        result[key] = {'text': clean_text(section.get('text', '')),
                       'score': score, 'scoreNote': clean_text(section.get('scoreNote', ''), 2000)}
    return result


def validate_assets(value):
    if not isinstance(value, list) or len(value) > 30:
        raise RewriteError('画面列表无效')
    result = []
    for item in value:
        if not isinstance(item, dict):
            raise RewriteError('画面格式无效')
        url = clean_text(item.get('url', ''), 2048)
        if url and not (url.startswith(('https://', 'http://', '/assets/rewrite-case/'))):
            raise RewriteError('画面链接无效')
        result.append({'label': clean_text(item.get('label', ''), 200), 'url': url,
                       'note': clean_text(item.get('note', ''), 1000)})
    return result


def validate_similar(value):
    if not isinstance(value, dict) or set(value) != set(PLATFORMS):
        raise RewriteError('相似素材需要抖音、小红书、YouTube、X 四个平台')
    result = {}
    for platform in PLATFORMS:
        entries = value[platform]
        if not isinstance(entries, list) or len(entries) > 30:
            raise RewriteError('相似素材列表无效')
        result[platform] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise RewriteError('相似素材格式无效')
            result[platform].append({
                'title': clean_text(entry.get('title', ''), 300),
                'url': validate_url(entry.get('url', '')),
                'point': clean_text(entry.get('point', ''), 2000),
                'evidence': clean_text(entry.get('evidence', ''), 1000),
            })
    return result


def validate_manuscript(payload, current=None):
    if not isinstance(payload, dict):
        raise RewriteError('稿件格式无效')
    title = clean_text(payload.get('title', ''), 200)
    if not title:
        raise RewriteError('稿件标题不能为空')
    status = payload.get('status', 'research')
    if status not in ('research', 'draft', 'reviewed'):
        raise RewriteError('状态无效')
    duration = payload.get('videoDurationSeconds', current.get('videoDurationSeconds') if current else None)
    if duration in ('', None):
        duration = None
    elif type(duration) not in (int, float) or not 0 < duration <= 86400:
        raise RewriteError('原视频时长需为 0–86400 秒')
    data = {
        'title': title, 'status': status,
        'sourceUrl': validate_url(payload.get('sourceUrl', '')),
        'transcriptUrl': clean_text(payload.get('transcriptUrl', ''), 2048),
        'transcript': clean_text(payload.get('transcript', current.get('transcript', '') if current else ''), 100000),
        'videoDurationSeconds': duration,
        'sourceAuthor': clean_text(payload.get('sourceAuthor', ''), 200),
        'sourcePublishedAt': clean_text(payload.get('sourcePublishedAt', ''), 80),
        'sourceNotes': clean_text(payload.get('sourceNotes', ''), 5000),
        'sections': validate_sections(payload.get('sections')),
        'assets': validate_assets(payload.get('assets', [])),
        'similar': validate_similar(payload.get('similar')),
        'secondCreation': clean_text(payload.get('secondCreation', '')),
    }
    # Analysis has its own revision-checked write action. General forms and
    # older clients cannot erase a newer analysis with a stale manuscript.
    for key in ANALYSIS_KEYS:
        data[key] = (current or {}).get(key, {'text': '', 'revision': 0, 'updatedAt': ''})
    if data['transcriptUrl'] and not data['transcriptUrl'].startswith(('https://', 'http://', '/assets/rewrite-case/')):
        raise RewriteError('转写链接无效')
    return data


def attach_voice_audio(manuscript_id, version_id, audio):
    """Store metadata for an audio file produced by the fixed local Xiaoyu worker."""
    with LOCK:
        data = read()
        item = find(data['manuscripts'], manuscript_id, '稿件')
        version = find(item['transcriptVersions'], version_id, '逐字稿版本')
        text = '\n'.join(re.sub(r'^\[\d{2}:\d{2}\]\s*', '', line).strip()
                         for line in version['text'].splitlines() if line.strip()).strip()
        if hashlib.sha256(text.encode('utf-8')).hexdigest()[:12] != audio.get('sourceTextHash'):
            raise RewriteError('生成期间稿件已修改，请重新生成语音')
        version['voiceAudio'] = audio
        version['updatedAt'] = now()
        item['updatedAt'] = now()
        write(data)
        return item


def dispatch(args):
    if not isinstance(args, dict):
        raise RewriteError('请求格式无效')
    action = args.get('action', 'list')
    if action == 'attach_voice_audio':
        import rewrite_voice
        audio = args.get('audio')
        if not isinstance(audio, dict) or audio.get('profile') != '小与':
            raise RewriteError('仅接受固定小与音频')
        entries = audio.get('segments') or [audio]
        if not isinstance(entries, list) or not 1 <= len(entries) <= 200:
            raise RewriteError('音频列表无效')
        for entry in entries:
            url = entry.get('url', '')
            if not url.startswith('/assets/rewrite-audio/'):
                raise RewriteError('仅接受本地稿件音频')
            path = rewrite_voice.audio_path(url.removeprefix('/assets/rewrite-audio/'))
            if not path.is_file() or path.stat().st_size <= 44:
                raise RewriteError('音频文件不存在或为空')
        return attach_voice_audio(args['id'], args['versionId'], audio)
    with LOCK:
        data = read()
        if action == 'list':
            data['manuscripts'].sort(key=lambda item: item.get('createdAt', ''), reverse=True)
            return data
        if action == 'create_kb':
            name = clean_text(args.get('name', ''), 120)
            if not name:
                raise RewriteError('知识库名称不能为空')
            item = {'id': uid(), 'name': name, 'projects': []}
            data['knowledgeBases'].append(item)
        elif action == 'rename_kb':
            item = find(data['knowledgeBases'], args.get('id'), '知识库')
            item['name'] = clean_text(args.get('name', ''), 120)
            if not item['name']:
                raise RewriteError('知识库名称不能为空')
        elif action == 'delete_kb':
            item = find(data['knowledgeBases'], args.get('id'), '知识库')
            if item['projects'] or any(x['knowledgeBaseId'] == item['id'] for x in data['manuscripts']):
                raise RewriteError('请先删除该知识库下的项目和稿件')
            data['knowledgeBases'].remove(item)
        elif action == 'create_project':
            kb = find(data['knowledgeBases'], args.get('knowledgeBaseId'), '知识库')
            name = clean_text(args.get('name', ''), 120)
            if not name:
                raise RewriteError('项目名称不能为空')
            item = {'id': uid(), 'name': name}
            kb['projects'].append(item)
        elif action == 'rename_project':
            _, item = project(data, args.get('knowledgeBaseId'), args.get('projectId'))
            item['name'] = clean_text(args.get('name', ''), 120)
            if not item['name']:
                raise RewriteError('项目名称不能为空')
        elif action == 'delete_project':
            kb, item = project(data, args.get('knowledgeBaseId'), args.get('projectId'))
            if any(x['projectId'] == item['id'] for x in data['manuscripts']):
                raise RewriteError('请先删除该项目下的稿件')
            kb['projects'].remove(item)
        elif action == 'create':
            project(data, args.get('knowledgeBaseId'), args.get('projectId'))
            record = validate_manuscript(args.get('manuscript'))
            item = {'id': uid(), 'knowledgeBaseId': args['knowledgeBaseId'],
                    'projectId': args['projectId'], 'createdAt': now(), 'updatedAt': now(),
                    **record, 'history': []}
            seed_versions(item)
            data['manuscripts'].append(item)
        elif action == 'update':
            item = find(data['manuscripts'], args.get('id'), '稿件')
            project(data, args.get('knowledgeBaseId', item['knowledgeBaseId']),
                    args.get('projectId', item['projectId']))
            record = validate_manuscript(args.get('manuscript'), item)
            before = {key: item[key] for key in record}
            if record != before or args.get('projectId', item['projectId']) != item['projectId']:
                item['history'].append({'at': now(), 'action': 'update', 'before': before})
                item.update(record)
                item['knowledgeBaseId'] = args.get('knowledgeBaseId', item['knowledgeBaseId'])
                item['projectId'] = args.get('projectId', item['projectId'])
                item['updatedAt'] = now()
        elif action in ('link_motion_storyboard', 'create_motion_storyboard_version',
                        'select_motion_storyboard_version', 'rename_motion_storyboard_version'):
            from rewrite_motion import change_version
            return change_version(data, args, TABLE_STORE, write, now)
        elif action in ('create_storyboard_version', 'select_storyboard_version', 'rename_storyboard_version'):
            item = find(data['manuscripts'], args.get('id'), '稿件')
            board = item['openingStoryboard']
            if type(args.get('expectedRevision')) is not int or args['expectedRevision'] != board['revision']:
                raise RewriteError('分镜版本已改变，请保留草稿并刷新')
            before = copy.deepcopy(board)
            at = now()
            if action == 'create_storyboard_version':
                if len(board['versions']) >= 30:
                    raise RewriteError('最多30个分镜版本')
                base = find(board['versions'], args.get('baseVersionId', board['activeVersionId']), '分镜版本')
                vid = 'v' + str(max(int(v['id'][1:]) for v in board['versions']) + 1)
                label = clean_text(args.get('label', vid.upper()), 120)
                if not label: raise RewriteError('版本名称不能为空')
                version = {'id': vid, 'label': label, 'rows': copy.deepcopy(base['rows']), 'revision': 0, 'createdAt': at, 'updatedAt': at}
                board['versions'].append(version)
                board['activeVersionId'] = vid
                board['rows'] = copy.deepcopy(version['rows'])
            elif action == 'select_storyboard_version':
                version = find(board['versions'], args.get('versionId'), '分镜版本')
                board['activeVersionId'] = version['id']
                board['rows'] = copy.deepcopy(version['rows'])
            else:
                version = find(board['versions'], args.get('versionId'), '分镜版本')
                label = clean_text(args.get('label', ''), 120)
                if not label: raise RewriteError('版本名称不能为空')
                version.update(label=label, updatedAt=at)
            board.update(revision=board['revision'] + 1, updatedAt=at)
            item['updatedAt'] = at
            item['history'].append({'at': at, 'action': action, 'before': before})
        elif action == 'save_storyboard':
            item = find(data['manuscripts'], args.get('id'), '稿件')
            key = args.get('storyboardKey')
            if key not in STORYBOARD_KEYS:
                raise RewriteError('分镜模块无效')
            previous = item[key]
            revision = args.get('expectedRevision')
            if type(revision) is not int or revision != previous['revision']:
                raise RewriteError('分镜已被其他页面修改，草稿已保留，请刷新后合并')
            if key == 'openingStoryboard' and args.get('versionId', previous['activeVersionId']) != previous['activeVersionId']:
                raise RewriteError('分镜版本已切换，请刷新后重试')
            rows = clean_storyboard(args.get('rows'))
            if rows != previous['rows']:
                at = now()
                item['history'].append({'at': at, 'action': 'save_storyboard',
                                        'storyboardKey': key, 'before': copy.deepcopy(previous)})
                item[key] = {**previous, 'rows': rows, 'revision': revision + 1, 'updatedAt': at}
                if key == 'openingStoryboard':
                    version = find(item[key]['versions'], previous['activeVersionId'], '分镜版本')
                    version.update(rows=copy.deepcopy(rows), revision=version['revision'] + 1, updatedAt=at)
                item['updatedAt'] = at
        elif action == 'save_analysis':
            item = find(data['manuscripts'], args.get('id'), '稿件')
            key = args.get('analysisKey')
            if key not in ANALYSIS_KEYS:
                raise RewriteError('分析模块无效')
            previous = item[key]
            revision = args.get('expectedRevision')
            if type(revision) is not int or revision != previous['revision']:
                raise RewriteError('分析已被其他页面修改，请复制当前草稿后刷新重试')
            text = clean_text(args.get('text', ''), 100000)
            if text != previous['text']:
                at = now()
                item['history'].append({'at': at, 'action': 'save_analysis',
                                        'analysisKey': key, 'before': dict(previous)})
                item[key] = {'text': text, 'revision': revision + 1, 'updatedAt': at}
                item['updatedAt'] = at
        elif action == 'create_version':
            item = find(data['manuscripts'], args.get('id'), '稿件')
            versions = item['transcriptVersions']
            if len(versions) >= 30:
                raise RewriteError('最多保存 30 个逐字稿版本')
            base = find(versions, args.get('baseVersionId', item['activeTranscriptVersionId']), '原版本')
            number = max((int(version['id'][1:]) for version in versions if version['id'].startswith('v') and version['id'][1:].isdigit()), default=0) + 1
            text = base['text']
            if base['id'] == 'v0':
                oral_lines = [line.split('] ', 1)[1] for line in text.splitlines() if line.startswith('[') and '] ' in line]
                if oral_lines:
                    text = '\n'.join(oral_lines)
            version = {'id': f'v{number}', 'label': f'V{number}', 'text': text,
                       'prompt': base.get('prompt', ''), 'createdAt': now(), 'updatedAt': now()}
            if len(text.split('\n')) == len(base['text'].split('\n')):
                version['lineAnnotations'] = base.get('lineAnnotations', [])
            versions.append(version)
            item['activeTranscriptVersionId'] = version['id']
            item['updatedAt'] = now()
        elif action == 'save_version':
            item = find(data['manuscripts'], args.get('id'), '稿件')
            version = find(item['transcriptVersions'], args.get('versionId'), '逐字稿版本')
            if version['id'] == 'v0':
                raise RewriteError('V0 原稿不可编辑；请新增版本')
            new_text = args.get('text', '')
            if not isinstance(new_text, str) or len(new_text) > 100000:
                raise RewriteError('稿件文本格式或长度无效')
            new_prompt = clean_text(args.get('prompt', ''), 20000)
            new_annotations = clean_line_annotations(args.get('lineAnnotations',
                version.get('lineAnnotations') or [{'tags': [], 'remotionPrompt': ''} for _ in new_text.split('\n')]), new_text)
            if new_text != version['text'] or new_prompt != version.get('prompt', '') or new_annotations != version.get('lineAnnotations', []):
                item['history'].append({'at': now(), 'action': 'save_version', 'versionId': version['id'],
                                        'before': {'text': version['text'], 'prompt': version.get('prompt', ''),
                                                   'lineAnnotations': version.get('lineAnnotations', [])}})
                if new_text != version['text']:
                    version.pop('voiceAudio', None)
                version['text'], version['prompt'], version['lineAnnotations'], version['updatedAt'] = new_text, new_prompt, new_annotations, now()
                item['updatedAt'] = now()
        elif action == 'save_line_annotations':
            item = find(data['manuscripts'], args.get('id'), '稿件')
            version = find(item['transcriptVersions'], args.get('versionId'), '逐字稿版本')
            new_annotations = clean_line_annotations(args.get('lineAnnotations'), version['text'])
            if new_annotations != version.get('lineAnnotations', []):
                version['lineAnnotations'] = new_annotations
                version['updatedAt'] = item['updatedAt'] = now()
        elif action == 'select_version':
            item = find(data['manuscripts'], args.get('id'), '稿件')
            version = find(item['transcriptVersions'], args.get('versionId'), '逐字稿版本')
            item['activeTranscriptVersionId'] = version['id']
        elif action == 'delete':
            item = find(data['manuscripts'], args.get('id'), '稿件')
            data['manuscripts'].remove(item)
        else:
            raise RewriteError('未知操作')
        write(data)
        return item
