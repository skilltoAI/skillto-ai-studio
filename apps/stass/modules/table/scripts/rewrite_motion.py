"""Version references to full, schema-driven tables; never flatten media/ratings."""
import copy
import uuid


def change_version(data, args, store, save, now):
    if store is None:
        raise ValueError('表格服务未连接')
    item = next((m for m in data['manuscripts'] if m['id'] == args.get('id')), None)
    if item is None:
        raise ValueError('稿件不存在')
    board = item['motionStoryboard']
    if type(args.get('expectedRevision')) is not int or args['expectedRevision'] != board['revision']:
        raise ValueError('motion分镜版本已改变，请保留草稿并刷新后合并')
    action = args['action']
    at, before = now(), copy.deepcopy(board)
    versions = board['versions']

    def find(vid):
        version = next((v for v in versions if v['id'] == vid), None)
        if version is None:
            raise ValueError('motion分镜版本不存在')
        return version

    number = max((int(v['id'][1:]) for v in versions), default=0) + 1
    label = args.get('label', 'V' + str(number))
    if not isinstance(label, str) or not label.strip() or len(label) > 120:
        raise ValueError('版本名称需为1–120个字符')
    source_version = args.get('sourceTranscriptVersionId', item['activeTranscriptVersionId'])
    if source_version not in {v['id'] for v in item['transcriptVersions']}:
        raise ValueError('来源文案版本不存在')
    new_path = None
    catalog_before = None
    # Table edits and cloning share the same cross-process lock as table CRUD.
    with store.locked():
        try:
            if action in ('link_motion_storyboard', 'create_motion_storyboard_version'):
                if len(versions) >= 30:
                    raise ValueError('最多30个motion分镜版本')
                if action == 'link_motion_storyboard':
                    table_id = args.get('tableId')
                    table = store.load_table(table_id)
                    if not any(t['id'] == table_id for kb in store.catalog()['knowledgeBases']
                               for p in kb['projects'] for t in p['tables']):
                        raise ValueError('表格不在工作区中')
                    if any(v['tableId'] == table_id for v in versions):
                        raise ValueError('此表已关联，请切换到已有版本')
                else:
                    base = find(args.get('baseVersionId', board['activeVersionId']))
                    table = copy.deepcopy(store.load_table(base['tableId']))
                    catalog = store.catalog()
                    parent = next((p for kb in catalog['knowledgeBases'] for p in kb['projects']
                                   if any(t['id'] == base['tableId'] for t in p['tables'])), None)
                    if parent is None:
                        raise ValueError('来源表格不在工作区中')
                    catalog_before = copy.deepcopy(catalog)
                    table_id = str(uuid.uuid4())
                    table.update(id=table_id, title=item['title'] + '｜motion分镜 ' + label.strip())
                    table.setdefault('history', []).append(store.event('clone_storyboard_table',
                        sourceTableId=base['tableId'], manuscriptId=item['id']))
                    new_path = store.table_path(table_id)
                    store.write_json(new_path, table)
                    parent['tables'].append({'id': table_id, 'name': table['title'], 'description': ''})
                    store.write_json(store.CATALOG, catalog)
                    source_version = base.get('sourceTranscriptVersionId', source_version)
                versions.append({'id': 'v' + str(number), 'label': label.strip(), 'tableId': table_id,
                    'tableTitle': table['title'], 'sourceTranscriptVersionId': source_version,
                    'createdAt': at, 'updatedAt': at})
                board['activeVersionId'] = versions[-1]['id']
            elif action == 'select_motion_storyboard_version':
                version = find(args.get('versionId'))
                store.load_table(version['tableId'])  # Do not select a deleted/broken table.
                if version['id'] == board['activeVersionId']:
                    return item
                board['activeVersionId'] = version['id']
            else:
                version = find(args.get('versionId'))
                version.update(label=label.strip(), updatedAt=at)
            board.update(revision=board['revision'] + 1, updatedAt=at)
            item['updatedAt'] = at
            item['history'].append({'at': at, 'action': action, 'storyboardKey': 'motionStoryboard', 'before': before})
            save(data)
        except Exception:
            # If publishing the reference fails, remove only this operation's new table.
            if new_path is not None:
                if catalog_before is not None:
                    store.write_json(store.CATALOG, catalog_before)
                new_path.unlink(missing_ok=True)
            raise
    return item
