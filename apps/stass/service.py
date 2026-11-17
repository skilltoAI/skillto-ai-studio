"""STASS semantic service; program-owned modules, shared REST/MCP dispatch."""
import inspect
import json
import os
from pathlib import Path
import secrets
import sys
import uuid
from typing import Any

from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

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
    return JSONResponse({'service':'STASS','instanceId':INSTANCE,'version':'0.4.0-dev','capabilities':list(TOOLS),
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
inner=server.streamable_http_app(streamable_http_path='/STASS/mcp',json_response=True,stateless_http=True,
    transport_security=TransportSecuritySettings(allowed_hosts=list(ALLOWED_HOSTS),allowed_origins=['http://'+host for host in ALLOWED_HOSTS]+['https://'+host for host in ALLOWED_HOSTS]))
inner.router.routes.extend([Route('/STASS/health',health),Route('/STASS/api/v1/tools/{tool}',api,methods=['POST'])])


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
            if path!='/STASS/health' and not secrets.compare_digest(headers.get(b'authorization',b'').decode(),'Bearer '+TOKEN):
                return await JSONResponse({'error':'Authentication required'},status_code=401)(scope,receive,send)
        return await self.application(scope,receive,send)


app=Guard(inner)
