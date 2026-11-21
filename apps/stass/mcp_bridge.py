"""Stdio transport adapter. No business storage imports, local fallback or server startup."""
import sys

# Some hosts invoke the interpreter without -B. Apply the policy before imports.
if __name__ == '__main__':
    sys.dont_write_bytecode = True

import argparse
import asyncio
import json
from pathlib import Path

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from client import execute


async def serve(profile_path):
    def profile():
        return json.loads(Path(profile_path).read_text(encoding='utf-8'))

    async def list_tools(ctx, params):
        _, result = await execute(profile(), 'list')
        return types.ListToolsResult.model_validate(result)

    async def call_tool(ctx, params):
        _, result = await execute(profile(), 'call', params.name, params.arguments)
        return types.CallToolResult.model_validate(result)

    server = Server('STASS client bridge', version='0.4.6',
                    on_list_tools=list_tools, on_call_tool=call_tool)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', required=True)
    args = parser.parse_args()
    asyncio.run(serve(args.profile))
