const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = vm.createContext({AbortSignal, URL});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../assets/extension/connection.js'), 'utf8'), context);
(async () => {
  const calls = [];
  const request = async url => {
    calls.push(url);
    return {ok: url.includes(':8880/'), json: async () => ({service: 'skillto-ai-studio-workbench'})};
  };
  assert.equal(await context.findWorkbench('http://127.0.0.1:8891', request), 'http://127.0.0.1:8880');
  assert.equal(calls.length, 2);
  assert.equal(await context.findWorkbench(null, async () => ({ok: true,
    json: async () => ({service: 'skillto-int-workbench'})})), 'http://127.0.0.1:8880');
  assert.equal(await context.findWorkbench('http://127.0.0.1:8880', request), 'http://127.0.0.1:8880');
  assert.equal(context.workbenchOrigin('http://127.0.0.1:9234/breakdowns'), 'http://127.0.0.1:9234');
  assert.equal(context.workbenchOrigin('http://127.0.0.1.evil.example'), null);
  assert.equal(context.workbenchOrigin('http://user:pass@127.0.0.1'), null);
  await assert.rejects(context.findWorkbench('http://evil.example', async url => {
    assert.ok(url.startsWith('http://127.0.0.1:'));
    return {ok: true, json: async () => ({service: 'unrelated-service'})};
  }), /未找到/);
  await assert.rejects(context.findWorkbench(null, async () => {throw Error('network error');}), /未找到/);
  console.log('Workbench discovery: stale port fallback, service identity and loopback boundaries passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
