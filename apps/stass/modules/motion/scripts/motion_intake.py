"""Validated, atomic ingestion into the visible Studio Motion library."""
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit
import motion_store as store

FORMAT='skillto.motion-intake/1'

def validate(batch):
    if not isinstance(batch,dict) or batch.get('format')!=FORMAT:raise ValueError('需要 skillto.motion-intake/1 录入清单')
    items=batch.get('items')
    if not isinstance(items,list) or not 1<=len(items)<=1000:raise ValueError('每批需要 1–1000 条记录')
    taxonomy=json.loads((Path(__file__).resolve().parents[1]/'assets/index-taxonomy.json').read_text('utf-8'))['facets']
    seen=set()
    for i in items:
        if not isinstance(i,dict):raise ValueError('录入项应为对象')
        for key in ('id','title','source','sourceUrl','ratio'):
            if not isinstance(i.get(key),str) or not i[key].strip():raise ValueError('缺少录入字段：'+key)
        if len(i['title'])>200 or len(i['id'])>200:raise ValueError('名称或身份字段过长')
        if not re.fullmatch(r'[1-9][0-9]*:[1-9][0-9]*|未知',i['ratio']):raise ValueError('画幅应为正整数比例或未知')
        if not isinstance(i.get('labels',[]),list):raise ValueError('labels 应为列表')
        if 'previewOnly' in i and not isinstance(i['previewOnly'],bool):raise ValueError('previewOnly 应为布尔值')
        identity=(i['source'],i['id'])
        if identity in seen:raise ValueError('同批重复来源画幅 ID')
        seen.add(identity)
        for key in ('sourceUrl','poster','demo','downloadUrl'):
            value=i.get(key)
            if value:
                u=urlsplit(value)
                if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('需要不含凭据的 HTTPS 链接：'+key)
                if u.query:raise ValueError('录入链接不得携带查询凭据：'+key)
        for key in ('width','height','fps'):
            value=i.get(key)
            if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0):raise ValueError('无效规格：'+key)
        for tag in i.get('labels',[]):
            if not isinstance(tag,dict):raise ValueError('标签应为对象')
            f,v=tag.get('facet'),tag.get('value')
            if f not in taxonomy or v not in taxonomy[f]['values'] or not tag.get('evidence') or tag.get('method') not in ('source-text','human','visual-reviewed','package-verified'):raise ValueError('无效维度标签或缺少证据')
        if i.get('previewOnly') and i.get('downloadUrl'):raise ValueError('预览条目不能声称已有直接下载包')
    return items

def ingest(batch,dry_run=False):
    items=validate(batch);created=updated=0;mapping=[]
    # Validate the entire batch first, then commit records + history together.
    with store.LOCK,store.db() as con:
        existing=[json.loads(r[0]) for r in con.execute("SELECT body FROM objects WHERE kind='item'")]
        for d in items:
            matches=[x for x in existing if (x.get('source')==d['source'] and x.get('indexId')==d['id'])]
            if not matches:matches=[x for x in existing if x.get('sourceUrl')==d['sourceUrl'] and x.get('aspect')==d['ratio']]
            if len(matches)>1:raise ValueError('已有重复来源身份，需人工合并：'+d['id'])
            fresh=not matches
            item=dict(matches[0]) if matches else dict(id=store.uid(),title=d['title'],source=d['source'],sourceUrl=d['sourceUrl'],aspect=d['ratio'],tagIds=[],rating=None,favorite=False,runCount=None,runCountSource=None,runCountUpdatedAt=None,localPath='',renderable=False,status='remote',createdAt=store.now(),category='模版合集',engine='未知')
            labels=d.get('labels',[])
            item.update(intakeFormat=FORMAT,indexId=d['id'],sourceId=d.get('repositoryId'),sourceFacets=labels,sourceDescription=d.get('summary',''),sourceCommit=d.get('sourceCommit'),availability=d.get('availability','unknown'),previewOnly=bool(d.get('previewOnly')),sourceMetadata={k:d.get(k) for k in ('version','width','height','fps','ratio','sourceEdition','editionNote')},updatedAt=store.now())
            if item.get('category')=='模版合集':item['category']=next((t['value'] for t in labels if t['facet']=='scenario'),'其他模版')
            if not item.get('localPath'):
                item.update(version=d.get('version'),previewUrl=d.get('demo'),posterUrl=d.get('poster'),downloadUrl=d.get('downloadUrl'),statusMessage='预览/预上线 · 下载状态以来源为准' if d.get('previewOnly') else '已录入 · 下载或导入后检查制作支持')
            if not item.get('description'):item['description']=d.get('summary','')
            if not dry_run:store.write('item',item,con)
            if fresh:existing.append(item);created+=1
            else:updated+=1
            mapping.append({'indexId':d['id'],'itemId':item['id']})
    return {'format':FORMAT,'dryRun':dry_run,'received':len(items),'created':created,'updated':updated,'mapping':mapping}
