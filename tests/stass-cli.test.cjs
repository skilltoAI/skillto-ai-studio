const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {readStatus, doctor} = require('../bin/stass.cjs');

test('status is read-only and does not create a second installation', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'STASS 中文 '));
  try {
    assert.equal(readStatus(root).installed, false);
    assert.equal((await doctor(root)).ready, false);
    assert.deepEqual(fs.readdirSync(root), []);
    fs.mkdirSync(path.join(root, 'config'));
    fs.writeFileSync(path.join(root, 'config/installation.json'), JSON.stringify({format:1, instanceId:'test', hosts:{codex:{}}, secret:'never-print'}));
    assert.equal(JSON.stringify(readStatus(root)).includes('never-print'), false);
    assert.equal((await doctor(root)).ready, false);
  } finally { fs.rmSync(root, {recursive:true}); }
});
