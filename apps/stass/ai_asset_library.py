"""AI asset libraries with remote imports and instance-owned local videos."""
import hashlib
import re
from urllib.parse import urlsplit
import ai_asset_local

LIBRARIES = [
    {'id': 'motion', 'name': 'Motion 模版'},
    {'id': 'red-white', 'name': 'AI红白模库'},
    {'id': 'jianying', 'name': '剪映AI模版库'},
]


def source_url(value):
    if not isinstance(value, str):
        raise ValueError('来源链接必须为飞书公开文档')
    url = urlsplit(value)
    if (url.scheme != 'https' or url.hostname != 'my.feishu.cn' or url.username
            or url.password or url.port or url.query
            or not re.fullmatch(r'/(wiki|docx)/[A-Za-z0-9]+', url.path)):
        raise ValueError('来源链接必须为飞书公开文档')
    return value


def text(value, limit, name):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(name + '格式或长度不正确')
    return value.strip()


def dispatch(args, store):
    if args.get('action') == 'set_cover':
        return ai_asset_local.set_cover(args, store)
    path = store.ROOT / 'ai-assets.json'
    with store.locked():
        data = store.read_json(path) if path.exists() else {'sources': [], 'items': [], 'history': []}
        if args.get('action', 'catalog') == 'catalog':
            sources = {source['id']: source for source in data['sources']}
            # Identical source assets share a card, while retaining every attribution link.
            grouped = {}
            for original in data['items']:
                item = dict(original)
                if sources[item['sourceId']]['access'] != 'anonymous':
                    item['playback'] = 'unverified'
                key = (item['library'], item['title'], item['prompt'], item['filename'], item.get('mediaDigest') or item.get('fileToken'))
                reference = {'title': sources[item['sourceId']]['title'], 'url': item['sourceUrl'],
                             'playback': item['playback'], 'checkedAt': item['checkedAt']}
                if key in grouped:
                    grouped[key]['references'].append(reference)
                    if grouped[key]['playback'] != 'source-page' and item['playback'] == 'source-page':
                        item['references'] = grouped[key]['references']
                        grouped[key] = item
                else:
                    item['references'] = [reference]
                    grouped[key] = item
            local_items = [dict(item, hasCover=ai_asset_local.cover_path(store, item['id']).is_file())
                           for item in data.get('localItems', [])]
            return {'libraries': LIBRARIES, 'sources': data['sources'],
                    'topics': data.get('localTopics', []), 'items': list(grouped.values()) + local_items}
        if args.get('action') in ai_asset_local.OPERATIONS:
            return ai_asset_local.dispatch(args, store, path, data)
        if args.get('action') != 'ingest':
            raise ValueError('未知AI资产操作')
        source = args.get('source')
        items = args.get('items', [])
        if not isinstance(source, dict) or not isinstance(items, list) or len(items) > 500:
            raise ValueError('需要来源信息和不超过500项的资产列表')
        url = source_url(source.get('url'))
        if urlsplit(url).fragment:
            raise ValueError('资料来源使用完整文档地址，条目使用定位链接')
        status = source.get('access')
        if status not in ('anonymous', 'login-required', 'unverified'):
            raise ValueError('请记录来源的匿名访问验证状态')
        source_id = hashlib.sha256(url.encode()).hexdigest()[:24]
        prepared_source = {'id': source_id, 'url': url,
                           'title': text(source.get('title', ''), 200, '来源标题'),
                           'access': status, 'checkedAt': text(source.get('checkedAt', ''), 80, '检查时间'),
                           'note': text(source.get('note', ''), 1000, '来源说明')}
        prepared = []
        seen = set()
        for item in items:
            if not isinstance(item, dict) or item.get('library') not in ('red-white', 'jianying'):
                raise ValueError('资产库必须为AI红白模库或剪映AI模版库')
            anchor = text(item.get('sourceBlockId', ''), 100, '来源定位')
            if not re.fullmatch(r'[A-Za-z0-9]+', anchor) or anchor in seen:
                raise ValueError('来源定位不可为空或重复')
            seen.add(anchor)
            title = text(item.get('title', ''), 200, '资产名称')
            if not title:
                raise ValueError('资产名称不能为空')
            playback = item.get('playback', 'unverified')
            if playback not in ('source-page', 'unverified') or (playback == 'source-page' and status != 'anonymous'):
                raise ValueError('免登录原页播放必须先验证公开来源')
            file_token = text(item.get('fileToken', ''), 100, '视频引用')
            if not re.fullmatch(r'[A-Za-z0-9]+', file_token):
                raise ValueError('需要飞书原始视频引用')
            digest = text(item.get('mediaDigest', ''), 64, '视频摘要')
            if digest and not re.fullmatch(r'[a-f0-9]{64}', digest):
                raise ValueError('视频摘要格式不正确')
            prepared.append({'id': hashlib.sha256((url+'#'+anchor).encode()).hexdigest()[:24],
                'sourceId': source_id, 'sourceBlockId': anchor, 'sourceUrl': url+'#'+anchor,
                'library': item['library'], 'title': title,
                'description': text(item.get('description', ''), 1000, '摘要'),
                'prompt': text(item.get('prompt', ''), 40000, '提示词'),
                'filename': text(item.get('filename', ''), 300, '视频名称'),
                'fileToken': file_token, 'mediaDigest': digest,
                'playback': playback, 'checkedAt': prepared_source['checkedAt']})
        sources = {item['id']: item for item in data['sources']}
        saved = {item['id']: item for item in data['items']}
        changed = sources.get(source_id) != prepared_source or any(saved.get(item['id']) != item for item in prepared)
        sources[source_id] = prepared_source
        for item in prepared:
            saved[item['id']] = item
        result = {'sourceId': source_id, 'count': len(prepared), 'dryRun': bool(args.get('dryRun')), 'changed': changed}
        if changed and not args.get('dryRun'):
            data['sources'], data['items'] = list(sources.values()), list(saved.values())
            data['history'].append(store.event('ingest_ai_assets', None, {'source': prepared_source, 'items': prepared}))
            store.write_json(path, data)
        return result


def get_asset(ident, store):
    if not re.fullmatch(r'[a-f0-9]{24}', ident):
        raise ValueError('资产不存在')
    data = dispatch({'action': 'catalog'}, store)
    item = next((item for item in data['items'] if item['id'] == ident), None)
    if not item or item['playback'] != 'source-page':
        raise ValueError('视频尚未通过匿名访问验证，请打开来源查看')
    return item


def get_local_asset(ident, store):
    path = store.ROOT / 'ai-assets.json'
    if not path.exists():
        return None
    return next((item for item in store.read_json(path).get('localItems', []) if item['id'] == ident), None)
