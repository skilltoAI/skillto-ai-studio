"""STASS semantic service; program-owned modules, shared REST/MCP dispatch."""
import inspect
import json
import os
from pathlib import Path
import secrets
import sys
import uuid
from client_auth import authenticate
from typing import Any

from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Route
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit
from web_session import WebSessions

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ['STASS_DATA_ROOT']).resolve(strict=True)
TOKEN = Path(os.environ['STASS_TOKEN_FILE']).read_text(encoding='utf-8').strip()
ALLOWED_HOSTS = set(os.environ.get('STASS_ALLOWED_HOSTS','127.0.0.1:8080,localhost:8080').split(','))
identity_file = DATA / '.stass-instance'
try:
    with identity_file.open('x', encoding='utf-8') as identity:
        identity.write(str(uuid.uuid4()))
except FileExistsError:
    pass
INSTANCE = str(uuid.UUID(identity_file.read_text(encoding='utf-8').strip()))
if len(TOKEN) < 32:
    raise ValueError('STASS token must have at least 32 characters')
os.environ['SKILLTO_TABLE_ROOT'] = str(DATA)
for name in ('table', 'motion', 'workbench'):
    sys.path.insert(0, str(HERE/'modules'/name/'scripts'))
import server as tables
import rewrite_system as rewrites
import report_system as reports
import motion_http as motions
import workbench
rewrites.TABLE_STORE = tables

server = MCPServer('STASS', version='0.4.0-dev')
TOOLS = {name: (description, callback, tables.tool_schema(name, description, hints)['inputSchema'])
         for name, (description, callback, hints) in tables.TOOLS.items() if name.startswith('table_')}


def add_dict_tool(name, description, callback):
    TOOLS[name] = (description, callback, {'type':'object', 'properties':{'arguments':{'type':'object'}}, 'required':['arguments']})


def breakdown(args):
    workspace = workbench.workspace()
    action = args.get('action', 'list')
    if action == 'list': return {'records':workspace.items()}
    if action == 'get': return workspace.get(args['id'])
    if action == 'update': return workspace.patch(args)
    if action == 'download': return workspace.submit(args)
    raise ValueError('Unsupported breakdown action')


add_dict_tool('rewrite_action', 'Read or edit manuscripts, analyses and storyboard versions.', rewrites.dispatch)
add_dict_tool('motion_action', 'Operate Motion catalog, tags, indexes and authorized production tasks.', motions.dispatch)
add_dict_tool('report_action', 'Operate report registry and Metabase content.', reports.dispatch)
add_dict_tool('breakdown_action', 'List, inspect or edit breakdowns; download requires explicit authorization.', breakdown)


def register(name, description, callback, schema):
    def invoke(**kwargs):
        if name.endswith('_action'):
            return callback(kwargs['arguments'])
        return callback({key:value for key,value in kwargs.items() if value is not None})
    required = schema.get('required', [])
    parameters=[]
    for key, definition in schema['properties'].items():
        kind=definition.get('type')
        annotation={'object':dict, 'array':list, 'boolean':bool, 'number':float, 'integer':int, 'string':str}.get(kind,Any) if isinstance(kind,str) else Any
        parameters.append(inspect.Parameter(key,inspect.Parameter.KEYWORD_ONLY,annotation=annotation,
                                           default=inspect.Parameter.empty if key in required else None))
    invoke.__signature__=inspect.Signature(parameters)
    server.tool(name=name,description=description)(invoke)


for name, (description, callback, schema) in TOOLS.items():
    register(name, description, callback, schema)


async def health(request):
    return JSONResponse({'service':'STASS','instanceId':INSTANCE,'pid':os.getpid(),'launchId':os.environ.get('STASS_LAUNCH_ID'),'releaseCommit':os.environ.get('STASS_RELEASE_COMMIT'),'version':os.environ.get('STASS_RELEASE_VERSION','0.4.0-dev'),'capabilities':list(TOOLS),
                         'protocol':1,'dataSchema':int(os.environ.get('STASS_DATA_SCHEMA','1')),
                         'status':'development; UI and cutover pending'})


async def api(request: Request):
    name=request.path_params['tool']
    if name not in TOOLS:
        return JSONResponse({'error':'Unknown operation'},status_code=404)
    try:
        args=await request.json()
        if not isinstance(args,dict): raise ValueError('Expected object')
        from starlette.concurrency import run_in_threadpool
        result=await run_in_threadpool(TOOLS[name][1], args.get('arguments',{}) if name.endswith('_action') else args)
        return JSONResponse({'result':result})
    except (ValueError,KeyError,TypeError) as exc:
        return JSONResponse({'error':str(exc)},status_code=400)


from mcp.server.transport_security import TransportSecuritySettings
web_sessions = WebSessions()

def local_web(scope, host):
    peer = scope.get('client')
    return bool(peer and peer[0] in ('127.0.0.1','::1')
                and urlsplit('http://' + host).hostname in ('127.0.0.1','localhost','::1'))

async def pair(request):
    if request.method == 'GET':
        if local_web(request.scope, request.headers['host']):
            return RedirectResponse('/STASS/',status_code=303)
        return HTMLResponse('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Skillto.ai 个人工作台配对</title><h1>连接个人工作台</h1><p>在本机程序获取一次性配对码，有效期5分钟。</p><form method="post"><label>配对码 <input name="code" autocomplete="off" required></label><button>连接</button></form></html>', headers={'Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; form-action 'self'; frame-ancestors 'none'"})
    if request.headers.get('origin') != str(request.base_url).rstrip('/'):
        return JSONResponse({'error':'Same-origin pairing required'},status_code=403)
    raw = await request.body()
    if len(raw)>1024: return JSONResponse({'error':'Pairing request too large'},status_code=413)
    try:
        token = web_sessions.exchange(parse_qs(raw.decode()).get('code',[''])[0], request.client.host if request.client else 'unknown')
    except ValueError as exc:
        return JSONResponse({'error':str(exc)},status_code=400)
    response = RedirectResponse('/STASS/',status_code=303)
    response.set_cookie('stass_session',token,httponly=True,samesite='strict',secure=request.url.scheme=='https',path='/STASS/',max_age=43200)
    return response

async def pair_code(request):
    if request.state.stass_client!='admin' or not request.client or request.client.host not in ('127.0.0.1','::1','testclient'):
        return JSONResponse({'error':'Local administrator required'},status_code=403)
    return JSONResponse({'code':web_sessions.issue(),'expiresIn':300},headers={'Cache-Control':'no-store'})

from web_ui import create_endpoint
web_endpoint=create_endpoint(tables,rewrites,reports,motions,workbench,DATA)
inner=server.streamable_http_app(streamable_http_path='/STASS/mcp',json_response=True,stateless_http=True,
    transport_security=TransportSecuritySettings(allowed_hosts=list(ALLOWED_HOSTS),allowed_origins=['http://'+host for host in ALLOWED_HOSTS]+['https://'+host for host in ALLOWED_HOSTS]))
inner.router.routes.extend([Route('/STASS/health',health),Route('/STASS/api/v1/tools/{tool}',api,methods=['POST'])])
inner.router.routes.extend([Route('/STASS/pair',pair,methods=['GET','POST']),Route('/STASS/api/v1/pair-code',pair_code),Route('/STASS/{path:path}',web_endpoint,methods=['GET','POST'])])
from contextlib import asynccontextmanager
original_lifespan=inner.router.lifespan_context
@asynccontextmanager
async def web_lifespan(application):
    async with original_lifespan(application):
        try: yield
        finally:
            from starlette.concurrency import run_in_threadpool
            await run_in_threadpool(web_endpoint.close)
inner.router.lifespan_context=web_lifespan


class Guard:
    def __init__(self, application):self.application=application
    async def __call__(self, scope, receive, send):
        if scope['type']=='http':
            headers=dict(scope['headers']);path=scope['path']
            host=headers.get(b'host',b'').decode()
            if host not in ALLOWED_HOSTS:
                return await JSONResponse({'error':'Invalid host'},status_code=403)(scope,receive,send)
            origin=headers.get(b'origin',b'').decode()
            if origin and origin != scope.get('scheme','http')+'://'+host:
                return await JSONResponse({'error':'Invalid origin'},status_code=403)(scope,receive,send)
            if path not in ('/STASS/health','/STASS/pair'):
                authorization = headers.get(b'authorization',b'').decode()
                is_admin = secrets.compare_digest(authorization,'Bearer '+TOKEN)
                client_id = 'admin' if is_admin else authenticate(os.environ.get('STASS_CLIENT_REGISTRY'), authorization[7:] if authorization.startswith('Bearer ') else '')
                cookies=SimpleCookie()
                try: cookies.load(headers.get(b'cookie',b'').decode())
                except Exception: pass
                if not client_id and 'stass_session' in cookies and web_sessions.valid(cookies['stass_session'].value): client_id='web'
                web_path = (path.startswith('/STASS/') and path != '/STASS/mcp'
                            and path != '/STASS/api/v1/pair-code' and not path.startswith('/STASS/api/v1/tools/'))
                if not client_id and web_path and local_web(scope,host):
                    client_id='web'
                if client_id=='web' and (not web_path or headers.get(b'sec-fetch-site') in (b'cross-site',b'same-site')):
                    return await JSONResponse({'error':'Browser access requires a same-origin workbench request'},status_code=403)(scope,receive,send)
                if client_id=='web' and scope['method'] not in ('GET','HEAD','OPTIONS') and origin!=scope.get('scheme','http')+'://'+host:
                    return await JSONResponse({'error':'Same-origin request required'},status_code=403)(scope,receive,send)
                if not client_id:
                    if path=='/STASS/': return await RedirectResponse('/STASS/pair')(scope,receive,send)
                    return await JSONResponse({'error':'Authentication required'},status_code=401)(scope,receive,send)
                if client_id not in ('admin','web') and path != '/STASS/mcp':
                    return await JSONResponse({'error':'Host credentials only permit MCP access'},status_code=403)(scope,receive,send)
                scope.setdefault('state', {})['stass_client'] = client_id
        return await self.application(scope,receive,send)


app=Guard(inner)
