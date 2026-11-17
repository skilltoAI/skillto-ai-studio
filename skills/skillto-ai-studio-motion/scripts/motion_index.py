"""Versioned source catalog, evidence-bearing facets, FTS and optional local ONNX vectors."""
import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
from pathlib import Path
from motion_store import root, now

MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
TAXONOMY=Path(__file__).resolve().parents[1]/'assets/index-taxonomy.json'

def connect():
    c=sqlite3.connect(root()/'catalog-index.sqlite3');c.row_factory=sqlite3.Row
    c.executescript('''CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,body TEXT,text TEXT,hash TEXT);
    CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(id UNINDEXED,text,tokenize='trigram');
    CREATE TABLE IF NOT EXISTS labels(doc TEXT,facet TEXT,value TEXT,evidence TEXT,method TEXT,PRIMARY KEY(doc,facet,value));
    CREATE INDEX IF NOT EXISTS facets ON labels(facet,value,doc);
    CREATE TABLE IF NOT EXISTS overrides(doc TEXT,facet TEXT,value TEXT,evidence TEXT,PRIMARY KEY(doc,facet,value));
    CREATE TABLE IF NOT EXISTS exclusions(doc TEXT,facet TEXT,value TEXT,PRIMARY KEY(doc,facet,value));
    CREATE TABLE IF NOT EXISTS vectors(doc TEXT PRIMARY KEY,hash TEXT,model TEXT,vector BLOB);
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);''')
    return c

def language(v):return v.get('zh') or v.get('en','') if isinstance(v,dict) else v or ''

def entries(data):
    for item in data['templates']:
        yield item,False
        for child in item.get('additionalDemos',[]):yield child,False
    for item in data.get('previews',[]):yield item,True

# Only literal evidence; do not translate a presumed use case into a verified component.
RULES={
'palette':{'蓝':r'深蓝|冷蓝|蓝色|蓝白|蓝暮','青':r'青色|青绿','绿':r'荧光绿|深绿|绿色|青柠','橙':r'暖橙|橙色|橙红|橙沙','米色':'米色','黑白灰':'黑白|冷灰','金属':'金属','多彩':'彩色|多彩|鲜明配色'},
'temperature':{'冷色':'冷色|冷蓝|冷灰|冷白','暖色':'暖色|暖橙','冷暖混合':'互补配色'},
'background':{'深色底':'黑底|暗底|深色.*底|深色.*舞台|深蓝夜','浅色底':'浅色|白底|米色纸','明暗交替':'明暗.*切换'},
'style':{'科技':'科技','商务':'商务','极简':'极简','水墨':'水墨','像素':'像素','卡通':'卡通|chibi','黏土':'黏土','玻璃':'玻璃','纸感':'纸感|纸面|纸雕|宣纸','手绘':'手绘|手写','赛博朋克':'赛博朋克','瑞士网格':'瑞士','三维':'三维|3D|立体'},
'scenario':{'知识科普':'科普|知识|教学','口播解说':'口播','产品宣传':'产品宣传|产品介绍','产品教程':'产品教程|上手|操作流程','品牌叙事':'品牌故事|品牌叙事','数据汇报':'商务|数据讲解','财经解读':'财经','人物介绍':'人物|人像','活动开场':'活动开场','歌词MV':'歌词|MV'},
'grammar':{'对比':r'(?<!高)对比|比较','枚举':'枚举|清单','替换取代':'取代|代替','数字强调':'大数字|数据大字|数字.*突出','数字增长':'数字增长|计数|固定增量|指数','比例占比':'百分比|比例|占比','阶梯递进':'阶梯|递进','步骤流程':'步骤|流程','因果解释':'因果|原因|机制','时间线':'时间线','层级关系':'层级|分支','关系网络':'关系网络','关键词强调':'关键词|文字强调|重点','引用证据':'证据|引用','汇聚拆分':'汇聚|拆分','位置路径':'路径|路线','提问揭晓':'提问|揭示','结论行动':'结论|行动'},
'component':{'数字滚动':'数字滚动|翻牌数字|翻牌计数','柱状图':'柱状','折线图':'折线','饼图占比':'占比图','对比表格':'对比表格','流程图':'流程图','地图路线':'地图路线','关系网络':'关系网络','时间轴':'时间线|时间轴','打字机':'打字机','字幕':'字幕','真人口播位':'真人|讲者|人脸'},
'metric':{'粉丝数':'粉丝数|关注人数','Star数':r'\bstars?\b','人数':r'人数|(?<!真)人口','百分比':'百分比','数量':'计数|数量'},
'pace':{'快节奏':'快剪|快切|快速切换'},
'layout':{'分屏':'分屏','多屏':'多屏','网格':'网格','真人圆窗':'圆窗|圆形署名|缩圆窗'},
'input':{'字幕SRT':'SRT','配音':'自备音频|英文口播|中文口播','视频':'自备.*视频'},
'editability':{'色板可换':'配色.*替换|色板|主题层','字体可换':'字体.*替换|字体.*可换','时长可调':'时长.*调整|时长.*时间轴|时长随内容','文案可换':'替换文案|文案.*可替换','素材可换':'替换.*媒体|替换.*照片'}
}

def build(repo):
    repo=Path(repo).resolve();raw=(repo/'catalog.json').read_bytes();data=json.loads(raw)
    if data.get('format')!='motiongit.catalog/1':raise ValueError('Unsupported catalog format')
    commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    docs=[]
    for item,preview in entries(data):
        ident=str(item.get('repositoryId') or item.get('previewId') or item.get('templateId'))+':'+str(item.get('ratio','unknown'))
        title=language(item.get('title'));summary=language(item.get('summary'));text=title+'\n'+summary
        body={k:item.get(k) for k in ['repositoryId','repository','website','version','width','height','fps','ratio','orientation','download','demo','poster','preview','sourceEdition','editionNote']}
        body.update(id=ident,title=title,summary=summary,previewOnly=preview,sourceCommit=commit,sourcePath='catalog.json',indexedAt=now())
        docs.append((ident,body,text))
    if len({d[0] for d in docs})!=len(docs):raise ValueError('Source variant IDs collide')
    c=connect()
    try:
        with c:
            c.execute('DELETE FROM documents');c.execute('DELETE FROM search');c.execute('DELETE FROM labels')
            for ident,body,text in docs:
                digest=hashlib.sha256(text.encode()).hexdigest()
                c.execute('INSERT INTO documents VALUES (?,?,?,?)',(ident,json.dumps(body,ensure_ascii=False),text,digest))
                labeltext=[]
                for facet,rules in RULES.items():
                    for value,pattern in rules.items():
                        match=re.search(pattern,text,re.I)
                        if match and not c.execute('SELECT 1 FROM exclusions WHERE doc=? AND facet=? AND value=?',(ident,facet,value)).fetchone():
                            c.execute('INSERT INTO labels VALUES (?,?,?,?,?)',(ident,facet,value,match.group(),'source-text'))
                            labeltext.append(value)
                for row in c.execute('SELECT * FROM overrides WHERE doc=?',(ident,)).fetchall():
                    c.execute('INSERT OR REPLACE INTO labels VALUES (?,?,?,?,?)',(ident,row['facet'],row['value'],row['evidence'],'human'));labeltext.append(row['value'])
                c.execute('INSERT INTO search VALUES (?,?)',(ident,text+' '+' '.join(labeltext)))
            c.execute('DELETE FROM vectors WHERE doc NOT IN (SELECT id FROM documents)')
            for k,v in {'sourceCommit':commit,'sourceCatalogSHA256':hashlib.sha256(raw).hexdigest(),'repositoryPath':str(repo),'builtAt':now(),'count':len(docs)}.items():c.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',(k,json.dumps(v)))
    finally:c.close()
    return status()

def intake_batch():
    """Normalize indexed source variants into the shared ingestion contract."""
    c=connect();items=[]
    try:
        for row in c.execute('SELECT body FROM documents ORDER BY id'):
            d=json.loads(row[0]);download=d.get('download') or {}
            d.update(source='MotionGit',sourceUrl=d.get('website') or d.get('repository') or 'https://github.com/motiontemplates/all#'+d['id'],
                     downloadUrl=(download.get('urls') or {}).get('zh') if download.get('type')=='direct-package' else None,
                     availability=download.get('availability','unknown'),
                     labels=[dict(r) for r in c.execute('SELECT facet,value,evidence,method FROM labels WHERE doc=?',(d['id'],))])
            items.append(d)
        return {'format':'skillto.motion-intake/1','items':items}
    finally:c.close()

def sync_library(dry_run=False):
    from motion_intake import ingest
    result=ingest(intake_batch(),dry_run)
    return {**result,'synced':result['received']}

def encoder():
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer
    folder=root()/'index-model';tok=Tokenizer.from_file(str(folder/'tokenizer.json'));tok.enable_truncation(max_length=128);tok.enable_padding()
    options=ort.SessionOptions();options.intra_op_num_threads=4
    session=ort.InferenceSession(str(folder/'model.onnx'),options,providers=['CPUExecutionProvider'])
    fingerprint=hashlib.sha256((folder/'model.onnx').read_bytes()).hexdigest()
    identity=MODEL+'@'+(folder/'revision.txt').read_text().strip()+':'+fingerprint+':mean128:normalized'
    def encode(texts):
        tokens=tok.encode_batch(texts);feed={'input_ids':np.array([t.ids for t in tokens],dtype=np.int64),'attention_mask':np.array([t.attention_mask for t in tokens],dtype=np.int64),'token_type_ids':np.array([t.type_ids for t in tokens],dtype=np.int64)}
        output=session.run(None,{i.name:feed[i.name] for i in session.get_inputs()})[0]
        mask=feed['attention_mask'][...,None];vec=(output*mask).sum(axis=1)/mask.sum(axis=1).clip(1)
        return (vec/np.linalg.norm(vec,axis=1,keepdims=True).clip(1e-9)).astype('float32')
    return identity,encode

def embed():
    identity,encode=encoder();c=connect()
    try:
        pending=c.execute('SELECT * FROM documents WHERE id NOT IN (SELECT doc FROM vectors WHERE hash=documents.hash AND model=?)',(identity,)).fetchall()
        for offset in range(0,len(pending),8):
            batch=pending[offset:offset+8];vectors=encode([r['text'] for r in batch])
            with c:
                for row,vec in zip(batch,vectors):c.execute('INSERT OR REPLACE INTO vectors VALUES (?,?,?,?)',(row['id'],row['hash'],identity,vec.tobytes()))
        return status()
    finally:c.close()

def status():
    c=connect()
    try:return {'documents':c.execute('SELECT count(*) FROM documents').fetchone()[0],'labels':c.execute('SELECT count(*) FROM labels').fetchone()[0],'vectorsCurrent':c.execute('SELECT count(*) FROM vectors v JOIN documents d ON d.id=v.doc AND d.hash=v.hash').fetchone()[0],'metadata':{r['key']:json.loads(r['value']) for r in c.execute('SELECT * FROM metadata')}}
    finally:c.close()

def search(query,filters=None,mode='hybrid',limit=10):
    filters=filters or {};c=connect()
    if not query.strip():c.close();raise ValueError('Search query must not be empty')
    try:
        eligible={r['id'] for r in c.execute('SELECT id FROM documents')}
        for facet,values in filters.items():
            if not isinstance(values,list) or any(not isinstance(v,str) for v in values):raise ValueError('Filter values must be string lists')
            if facet in ('ratio','orientation','availability'):
                eligible &= {r['id'] for r in c.execute('SELECT id,body FROM documents') if str((json.loads(r['body']).get('download') or {}).get('availability') if facet=='availability' else json.loads(r['body']).get(facet)) in values}
                continue
            if facet not in json.loads(TAXONOMY.read_text('utf-8'))['facets']:raise ValueError('Unknown filter dimension')
            # AND between dimensions, OR within a dimension.
            selected={r['doc'] for r in c.execute('SELECT doc,value FROM labels WHERE facet=?',(facet,)) if r['value'] in values};eligible&=selected
        ranks=[]
        if mode in ('keyword','hybrid'):
            terms=[t for t in re.findall(r'[\w]+',query) if len(t)>=3]
            hits=[]
            if terms:
                expression=' OR '.join('"'+t.replace('"','""')+'"' for t in terms)
                hits=[r['id'] for r in c.execute('SELECT id FROM search WHERE search MATCH ? ORDER BY rank',(expression,)) if r['id'] in eligible]
            # Chinese queries shorter than the trigram tokenizer supports.
            if not hits and query:hits=[r['id'] for r in c.execute('SELECT id,text FROM documents') if query.casefold() in r['text'].casefold() and r['id'] in eligible]
            ranks.append(hits)
        if mode in ('vector','hybrid'):
            import numpy as np
            identity,encode=encoder();q=encode([query])[0];scored=[]
            for r in c.execute('SELECT v.* FROM vectors v JOIN documents d ON d.id=v.doc AND d.hash=v.hash WHERE v.model=?',(identity,)):
                if r['doc'] in eligible:scored.append((float(np.frombuffer(r['vector'],dtype='float32')@q),r['doc']))
            if not scored:raise ValueError('No matching current vectors; run embed using this exact model first')
            ranks.append([ident for score,ident in sorted(scored,reverse=True)])
        scores={}
        for ranking in ranks:
            for n,ident in enumerate(ranking):scores[ident]=scores.get(ident,0)+1/(60+n+1)
        output=[]
        for ident in sorted(scores,key=lambda x:(-scores[x],x))[:limit]:
            body=json.loads(c.execute('SELECT body FROM documents WHERE id=?',(ident,)).fetchone()[0]);body['score']=scores[ident];body['labels']=[dict(r) for r in c.execute('SELECT facet,value,evidence,method FROM labels WHERE doc=?',(ident,))];output.append(body)
        return output
    finally:c.close()

def label(ident,facet,value,evidence,delete=False):
    taxonomy=json.loads(TAXONOMY.read_text('utf-8'))['facets']
    if facet not in taxonomy or value not in taxonomy[facet]['values']:raise ValueError('Unknown controlled facet/value')
    if not evidence.strip():raise ValueError('Record review evidence or reason')
    c=connect()
    try:
        if not c.execute('SELECT 1 FROM documents WHERE id=?',(ident,)).fetchone():raise ValueError('Unknown document')
        with c:
            if delete:
                c.execute('INSERT OR IGNORE INTO exclusions VALUES (?,?,?)',(ident,facet,value))
                c.execute('DELETE FROM overrides WHERE doc=? AND facet=? AND value=?',(ident,facet,value));c.execute('DELETE FROM labels WHERE doc=? AND facet=? AND value=?',(ident,facet,value))
            else:
                c.execute('DELETE FROM exclusions WHERE doc=? AND facet=? AND value=?',(ident,facet,value))
                c.execute('INSERT OR REPLACE INTO overrides VALUES (?,?,?,?)',(ident,facet,value,evidence));c.execute('INSERT OR REPLACE INTO labels VALUES (?,?,?,?,?)',(ident,facet,value,evidence,'human'))
        # FTS is rebuilt from current evidence labels; vectors depend only on source descriptions.
        repo=json.loads(c.execute("SELECT value FROM metadata WHERE key='repositoryPath'").fetchone()[0])
    finally:c.close()
    return build(repo)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['build','embed','search','status','taxonomy','label','sync']);p.add_argument('--repo',default=str(root()/'sources/motiontemplates-all'));p.add_argument('--query',default='');p.add_argument('--filters',default='{}');p.add_argument('--mode',choices=['keyword','vector','hybrid'],default='hybrid');p.add_argument('--limit',type=int,default=10);p.add_argument('--id');p.add_argument('--facet');p.add_argument('--value');p.add_argument('--evidence',default='');p.add_argument('--delete',action='store_true');a=p.parse_args()
    if a.action=='build':out=build(a.repo)
    elif a.action=='embed':out=embed()
    elif a.action=='sync':out=sync_library()
    elif a.action=='search':out=search(a.query,json.loads(a.filters),a.mode,max(1,min(a.limit,100)))
    elif a.action=='taxonomy':out=json.loads(TAXONOMY.read_text('utf-8'))
    elif a.action=='label':out=label(a.id,a.facet,a.value,a.evidence,a.delete)
    else:out=status()
    print(json.dumps(out,ensure_ascii=False,indent=2))
