"""Semantic CLI for the running Studio service; JSON in/out, same operations as UI."""
import argparse
import json
from urllib.request import Request,urlopen
from urllib.error import HTTPError

def call(base, args):
    with urlopen(base+'/api/motions/session',timeout=10) as r:token=json.load(r)['token']
    req=Request(base+'/api/motions/action',data=json.dumps(args,ensure_ascii=False).encode(),
                headers={'Content-Type':'application/json','X-Motion-Token':token})
    with urlopen(req,timeout=60) as r:return json.load(r)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['catalog','prepare_previews','seed','add','update','view','tag','download','import','render','cancel','retry','remove','doctor','sync_index','search_index','ingest'])
    p.add_argument('--json',default='{}',help='JSON arguments; use --file for long parameters')
    p.add_argument('--file');p.add_argument('--url',default='http://127.0.0.1:8880')
    a=p.parse_args()
    try:
        from pathlib import Path
        args=json.loads(Path(a.file).read_text('utf-8') if a.file else a.json);args['action']=a.action
        print(json.dumps(call(a.url,args),ensure_ascii=False,indent=2))
    except HTTPError as e:
        print(e.read().decode('utf-8'));raise SystemExit(1)
