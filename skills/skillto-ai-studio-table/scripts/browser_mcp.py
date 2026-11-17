"""Dedicated local-only MCP entry; independent of remote table configuration."""
import os
os.environ.pop('SKILLTO_TABLE_API_URL', None)
os.environ.pop('SKILLTO_TABLE_API_KEY_FILE', None)
import server
server.TOOLS = {name: tool for name, tool in server.TOOLS.items() if name.startswith('browser_')}
if __name__ == '__main__':
    server.main()
