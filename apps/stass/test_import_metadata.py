"""Migration/import must not discard extension metadata unknown to this version."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ImportMetadataTests(unittest.TestCase):
    def test_row_extensions_history_and_ids_survive_import(self):
        source = Path(__file__).parent
        code = '''
import server
import review_web
base=server.table_workspace({'action':'create','level':'knowledge_base','name':'Base'})
project=server.table_workspace({'action':'create','level':'project','knowledgeBaseId':base['id'],'name':'Project'})
table=server.table_workspace({'action':'create','level':'table','knowledgeBaseId':base['id'],'projectId':project['id'],'name':'Table'})
payload={'rows':[{'id':'stable-row','fields':{},'futureMetadata':{'chosen':True,'revision':9},'history':[{'action':'past'}]}]}
review_web.ReviewHandler.import_table(server,{'tableId':table['id'],'data':payload})
row=server.load_table(table['id'])['rows'][0]
assert row['id']=='stable-row'
assert row['futureMetadata']=={'chosen':True,'revision':9}
assert row['history']==[{'action':'past'}]
'''
        with tempfile.TemporaryDirectory() as temporary:
            env = os.environ.copy()
            env.update(SKILLTO_TABLE_ROOT=temporary, STASS_RESOURCE_ROOT=temporary,
                       PYTHONPATH=os.pathsep.join([str(source/'modules/table/scripts'),str(source/'modules/table/base')]))
            result = subprocess.run([sys.executable,'-c',code], env=env, capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))


if __name__ == '__main__': unittest.main()
