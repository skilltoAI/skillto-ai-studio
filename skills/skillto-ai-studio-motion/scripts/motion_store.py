"""Local Motion library. SQLite is authoritative; views never edit files directly."""
import json
import math
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

LOCK = threading.RLock()
SEED = {
    'title': '酷炫科技风', 'source': 'MotionGit', 'sourceId': '385712',
    'sourceUrl': 'https://motiongit.com/@adunext/385712',
    'downloadUrl': 'https://motiontemplates.github.io/385712/downloads/kinetic-tech-0.2.7-open-beta-zh.motion',
    'previewUrl': 'https://motiontemplates.github.io/385712/assets/demo.mp4',
    'category': '文字排版', 'aspect': '16:9', 'engine': 'kinetic-user-core/1',
    'version': '0.2.7-open-beta', 'publishedAt': None, 'runCount': None,
    'runCountSource': None, 'runCountUpdatedAt': None,
    'description': '公开中文版 · 原生文字动效与动作音效。支持 B1–B4 文字场景，媒体场景通过完整参数绑定。',
}

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return uuid.uuid4().hex
def root():
    path = Path(os.environ.get('SKILLTO_TABLE_ROOT', Path.home() / 'skillto-table-data')).resolve() / 'motions'
    path.mkdir(parents=True, exist_ok=True)
    return path

@contextmanager
def db():
    con = sqlite3.connect(root() / 'library.sqlite3', timeout=30)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('CREATE TABLE IF NOT EXISTS objects (kind TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(kind,id))')
    con.execute('CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, at TEXT, kind TEXT, object_id TEXT, before_json TEXT, after_json TEXT)')
    try:
        with con:
            yield con
    finally:
        con.close()

def all_objects(kind):
    with db() as con: return [json.loads(r[0]) for r in con.execute('SELECT body FROM objects WHERE kind=?', (kind,))]

def get(kind, ident):
    with db() as con: row = con.execute('SELECT body FROM objects WHERE kind=? AND id=?', (kind, ident)).fetchone()
    if not row: raise ValueError('记录不存在')
    return json.loads(row[0])

def write(kind, value, con=None, delete=False):
    if con is None:
        with LOCK, db() as c: return write(kind, value, c, delete)
    ident = value['id']
    old = con.execute('SELECT body FROM objects WHERE kind=? AND id=?', (kind, ident)).fetchone()
    text = json.dumps(value, ensure_ascii=False)
    if delete: con.execute('DELETE FROM objects WHERE kind=? AND id=?', (kind, ident))
    else: con.execute('INSERT OR REPLACE INTO objects VALUES (?,?,?)', (kind, ident, text))
    con.execute('INSERT INTO history(at,kind,object_id,before_json,after_json) VALUES (?,?,?,?,?)',
                (now(), kind, ident, old[0] if old else None, None if delete else text))
    return value

def public(item):
    item = dict(item)
    item.setdefault('viewed', False)
    item.setdefault('viewedAt', None)
    item.setdefault('ratingSource', 'manual' if item.get('rating') is not None else None)
    local = item.get('localPath')
    item['localPath'] = local if local and Path(local).is_file() else ''
    item['renderable'] = bool(item.get('renderable') and item['localPath'])
    return item

def catalog():
    return {'items': [public(i) for i in all_objects('item')], 'tags': all_objects('tag'),
            'jobs': sorted(all_objects('job'), key=lambda j: j['createdAt'], reverse=True)[:100]}

def add(args):
    source_url = str(args.get('sourceUrl', '')).strip()
    if source_url:
        u = urlsplit(source_url)
        if u.scheme != 'https' or not u.hostname or u.username or u.password: raise ValueError('来源需要有效 HTTPS 链接')
    with LOCK:
        for item in all_objects('item'):
            if source_url and item.get('sourceUrl') == source_url and item.get('aspect') == args.get('aspect', '未知'):
                return public(item)
        title = str(args.get('title', '')).strip()
        if not title or len(title) > 200: raise ValueError('请输入 1–200 字的名称')
        item = {k: args.get(k) for k in ('sourceId','downloadUrl','previewUrl','version','publishedAt','description')}
        item.update(id=uid(), title=title, sourceUrl=source_url, source=args.get('source', 'MotionGit'),
                    category=args.get('category', '未分类'), aspect=args.get('aspect', '未知'),
                    engine=args.get('engine', '未知'), tagIds=[], rating=None, ratingSource=None,
                    viewed=False, viewedAt=None, favorite=False,
                    runCount=None, runCountSource=None, runCountUpdatedAt=None,
                    localPath='', renderable=False, status='remote', createdAt=now(), updatedAt=now())
        return write('item', item)

def seed(): return add(SEED)

def mark_viewed(ident):
    """Opening details is a view; hover, imports and source metrics are not."""
    with LOCK:
        item = get('item', ident)
        if item.get('viewed') and item.get('rating') is not None:
            return public(item)
        item['viewed'] = True
        item['viewedAt'] = item.get('viewedAt') or now()
        if item.get('rating') is None:
            item.update(rating=1, ratingSource='view-default')
        item['updatedAt'] = now()
        return public(write('item', item))

def update_item(ident, args):
    with LOCK:
        item = get('item', ident)
        for key in ('title', 'category'):
            if key in args:
                value = str(args[key]).strip()
                if not value or len(value) > 200: raise ValueError('名称不能为空或过长')
                item[key] = value
        if 'favorite' in args: item['favorite'] = bool(args['favorite'])
        if 'rating' in args:
            score = args['rating']
            if score is not None and (type(score) not in (int,float) or not math.isfinite(score) or not .5 <= score <= 5 or score*2 != int(score*2)): raise ValueError('评分应为 0.5–5（半星步进）或空')
            item['rating'] = score
            item['ratingSource'] = 'manual' if score is not None else None
            if score is None and item.get('viewed'):
                item.update(rating=1, ratingSource='view-default')
        if 'tagIds' in args:
            tags = args['tagIds']
            valid = {t['id'] for t in all_objects('tag')}
            if not isinstance(tags, list) or any(t not in valid for t in tags): raise ValueError('包含无效标签')
            item['tagIds'] = list(dict.fromkeys(tags))
        item['updatedAt'] = now()
        return public(write('item', item))

def tag_action(action, args):
    with LOCK, db() as con:
        tags = all_objects('tag')
        if action == 'delete':
            tag = get('tag', args['id'])
            for item in all_objects('item'):
                if tag['id'] in item['tagIds']:
                    item['tagIds'].remove(tag['id']); item['updatedAt'] = now(); write('item', item, con)
            write('tag', tag, con, delete=True)
            return {'deleted': tag['id']}
        name = str(args.get('name', '')).strip()
        if not name or len(name) > 40: raise ValueError('标签名称需要 1–40 字')
        if any(t['name'].casefold() == name.casefold() and t['id'] != args.get('id') for t in tags):
            raise ValueError('标签名称已存在')
        tag = get('tag', args['id']) if args.get('id') else {'id': uid()}
        tag['name'] = name
        return write('tag', tag, con)
