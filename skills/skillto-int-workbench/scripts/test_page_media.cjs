const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../assets/extension/page-media.js'), 'utf8');
async function resolve(status, body, href = 'https://www.douyin.com/user/test?modal_id=123') {
  let calls = 0;
  const context = vm.createContext({URL, AbortSignal, location: {href}, document: {querySelectorAll: () => []}, fetch: async url => {
    calls++; assert.equal(new URL(url).searchParams.get('aweme_id'), '123');
    return {status, ok: status === 200, text: async () => JSON.stringify(body)};
  }});
  vm.runInContext(script, context);
  const result = await context.resolveCurrentDouyinMedia();
  return {result, calls};
}
(async () => {
  const body = {aweme_detail: {aweme_id: '123', video: {play_addr: {url_list: ['https://cdn.example/video?signature=keep']}, width: 1920, height: 1080, duration: 12000}}};
  const good = await resolve(200, body);
  assert.equal(good.result.url, 'https://cdn.example/video?signature=keep');
  assert.equal(good.result.duration, 12);
  assert.equal(good.calls, 1);
  for (const status of [401, 403, 429]) {
    const blocked = await resolve(status, body);
    assert.ok(blocked.result.error);
    assert.equal(blocked.calls, 1);
  }
  assert.ok((await resolve(200, {aweme_detail: {...body.aweme_detail, aweme_id: '999'}})).result.error);
  assert.equal((await resolve(200, body, 'https://evil.example/video/123')).calls, 0);
  console.log('Current-page media: exact item, one same-page request, denied-access stop and origin boundaries passed');
})().catch(error => {console.error(error);process.exitCode = 1;});
