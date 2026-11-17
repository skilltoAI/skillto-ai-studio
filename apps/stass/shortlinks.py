"""Persistent short identities and immutable view snapshots, owned by STASS."""
from contextlib import closing
import json
from pathlib import Path
import secrets
import sqlite3
import string
from urllib.parse import urlsplit

ALPHABET = string.ascii_letters + string.digits


def server_root(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
            or parsed.username or parsed.password
            or not (parsed.path == '/STASS' or parsed.path.startswith('/STASS/'))):
        raise ValueError('Expected a credential-free STASS URL')
    if parsed.port is not None and not 0 < parsed.port < 65536:
        raise ValueError('Invalid port')
    return f'{parsed.scheme}://{parsed.netloc}/STASS/'


class ShortLinks:
    def __init__(self, root):
        self.path = Path(root) / 'shortlinks.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as connection, connection:
            connection.execute('CREATE TABLE IF NOT EXISTS links (short TEXT PRIMARY KEY, module TEXT NOT NULL, object_id TEXT NOT NULL, payload TEXT, deleted INTEGER NOT NULL DEFAULT 0, UNIQUE(module,object_id))')

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def create(self, module, object_id, payload=None):
        if module not in {'t', 'r', 'w', 'b', 'm', 's'} or not object_id:
            raise ValueError('Invalid object identity')
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True) if payload is not None else None
        with closing(self.connect()) as connection, connection:
            connection.execute('BEGIN IMMEDIATE')
            old = connection.execute('SELECT short,payload,deleted FROM links WHERE module=? AND object_id=?', (module, object_id)).fetchone()
            if old:
                if old[2]:
                    raise KeyError('Deleted identity cannot be reused')
                if old[1] != encoded:
                    raise ValueError('Immutable snapshot cannot be replaced')
                return old[0]
            for _ in range(100):
                code = ''.join(secrets.choice(ALPHABET) for _ in range(10))
                try:
                    connection.execute('INSERT INTO links(short,module,object_id,payload) VALUES (?,?,?,?)', (code, module, object_id, encoded))
                    return code
                except sqlite3.IntegrityError:
                    continue
            raise RuntimeError('Unable to allocate unique short identity')

    def resolve(self, module, code):
        with closing(self.connect()) as connection:
            row = connection.execute('SELECT object_id,payload,deleted FROM links WHERE short=? AND module=?', (code, module)).fetchone()
        if not row or row[2]:
            raise KeyError('Unknown or deleted short link')
        return {'id': row[0], 'view': json.loads(row[1]) if row[1] is not None else None}

    def delete(self, module, object_id):
        with closing(self.connect()) as connection, connection:
            connection.execute('UPDATE links SET deleted=1 WHERE module=? AND object_id=?', (module, object_id))
