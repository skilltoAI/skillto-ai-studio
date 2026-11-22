"""Explicitly paired STASS MCP client. No workspace-file access or fallback."""
import sys

# An installed program must remain byte-for-byte identical to its release.
if __name__ == '__main__':
    sys.dont_write_bytecode = True

import argparse
import asyncio
import base64
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from shortlinks import server_root


@asynccontextmanager
async def connection(profile, *, transport=None):
    base=server_root(profile['url'])
    async with httpx2.AsyncClient(transport=transport, follow_redirects=False, timeout=30) as http:
        response=await http.get(base+'health');response.raise_for_status();identity=response.json()
        if identity.get('service')!='STASS' or not identity.get('instanceId'):
            raise ValueError('Endpoint is not an identified STASS service')
        if identity.get('protocol') != 1:
            raise ValueError('Incompatible STASS client protocol; refusing to send credentials')
        if profile.get('instanceId') and profile['instanceId']!=identity['instanceId']:
            raise ValueError('Workspace identity changed; refusing to send credentials')
        secret=Path(profile['tokenFile']).read_text(encoding='utf-8').strip()
        if not secret:raise ValueError('Missing pairing credential')
        http.headers['Authorization']='Bearer '+secret
        async with Client(streamable_http_client(base+'mcp',http_client=http)) as client:
            yield identity, client


async def execute(profile, operation, name=None, arguments=None, *, transport=None):
    async with connection(profile, transport=transport) as (identity, client):
        if operation in ('pair','list'):
            result=await client.list_tools()
        else:
            result=await client.call_tool(name,arguments or {})
        return identity,result.model_dump(mode='json')


async def upload_asset(profile, video, arguments):
    async with connection(profile) as (_, client):
        async def action(name, **payload):
            response = await client.call_tool('ai_assets_action', {'arguments': {'action': name, **payload}})
            if response.is_error:
                raise ValueError(response.content[0].text)
            return json.loads(response.content[0].text)

        with video.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            ticket = await action('begin_upload', **{
                **arguments, 'filename': video.name, 'size': os.fstat(stream.fileno()).st_size, 'sha256': digest})
            if ticket['complete']:
                return ticket
            offset = ticket['offset']
            stream.seek(offset)
            while chunk := stream.read(ticket['chunkBytes']):
                result = await action('upload_chunk', uploadId=ticket['uploadId'], offset=offset,
                                      base64=base64.b64encode(chunk).decode('ascii'))
                offset = result['offset']
            return await action('finish_upload', uploadId=ticket['uploadId'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['pair','list','call','upload-asset'])
    parser.add_argument('--profile',default=str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'STASS/client.json'))
    parser.add_argument('--url');parser.add_argument('--token-file');parser.add_argument('--tool');parser.add_argument('--arguments',help='UTF-8 JSON argument file')
    parser.add_argument('--video', type=Path, help='Explicitly selected local MP4 for upload-asset')
    args=parser.parse_args();path=Path(args.profile).expanduser().resolve()
    if args.operation=='pair':
        if not args.url or not args.token_file:parser.error('pair requires --url and --token-file')
        profile={'url':server_root(args.url),'tokenFile':str(Path(args.token_file).expanduser().resolve(strict=True))}
    else:
        profile=json.loads(path.read_text(encoding='utf-8'))
        if args.url and server_root(args.url)!=profile['url']:raise ValueError('Explicit URL differs from paired target; pair it in a separate profile')
        if args.operation=='call' and not args.tool:parser.error('call requires --tool')
    arguments=json.loads(Path(args.arguments).read_text('utf-8')) if args.arguments else {}
    if args.operation == 'upload-asset':
        if not args.video or not args.arguments or 'topicId' not in arguments or 'itemKey' not in arguments:
            parser.error('upload-asset requires --video and --arguments with topicId, itemKey and title')
        print(json.dumps(asyncio.run(upload_asset(profile, args.video, arguments)), ensure_ascii=False))
        return
    identity,result=asyncio.run(execute(profile,args.operation,args.tool,arguments))
    if args.operation=='pair':
        profile['instanceId']=identity['instanceId'];path.parent.mkdir(parents=True,exist_ok=True)
        fd,temp=tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as out:json.dump(profile,out,ensure_ascii=False)
            os.replace(temp,path)
        finally:
            Path(temp).unlink(missing_ok=True)
        print(json.dumps({'paired':True,'url':profile['url'],'instanceId':identity['instanceId']}))
    else:print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
