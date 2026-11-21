const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../assets/extension/discovery.js'), 'utf8');
function scan(direct, loaded, pageData = null, href = "https://example.com/video") {
  const context = vm.createContext({URL, innerWidth: 1280, innerHeight: 720,
    location: {href}, window: {},
    document: {querySelectorAll: selector => selector.startsWith('script') ? (pageData ? [{textContent: JSON.stringify(pageData)}] : []) : direct},
    performance: {getEntriesByType: () => loaded.map(name => ({name}))}});
  vm.runInContext(source, context);
  return JSON.parse(JSON.stringify(vm.runInContext('collectPageMedia()', context)));
}
const signed = 'https://v.example.douyinvod.com/a/video/tos/item?sign=keep-this';
assert.deepEqual(scan([{currentSrc: 'blob:local', src: ''}], [signed,
  'https://example.com/tracking.js', 'https://evil.douyinvod.com.evil/video/tos/a',
  'https://example.com/playlist.m3u8?sign=keep', 'file:///secret.mp4']),
  [{url: signed}, {url: 'https://example.com/playlist.m3u8?sign=keep'}]);
assert.deepEqual(scan([{currentSrc: signed, src: signed, videoWidth: 1920, videoHeight: 1080, duration: 12}], [signed]),
  [{url: signed, width: 1920, height: 1080, duration: 12, current: false}]);
assert.equal(scan([], Array.from({length: 80}, (_, i) => `https://example.com/${i}.mp4`)).length, 60);
const main = {currentSrc: signed, src: signed, videoWidth: 1920, videoHeight: 1080, duration: 12,
  getBoundingClientRect: () => ({left: 0, top: 0, right: 900, bottom: 600})};
const preloaded = {currentSrc: 'https://example.com/preloaded.mp4', src: '',
  getBoundingClientRect: () => ({left: 0, top: 900, right: 100, bottom: 1000})};
assert.deepEqual(scan([main, preloaded], ['https://example.com/another.mp4']).filter(item => item.current).map(item => item.url), [signed]);
console.log('Page media discovery: blob fallback, signed URLs, host boundaries, deduplication and cap passed');

const pageData = {aweme_id: '123', video: {play_addr: {url_list: [signed]}, width: 1920, height: 1080, duration: 12000}};
assert.equal(scan([], [], pageData, 'https://www.douyin.com/user/person?modal_id=123')[0].current, true);
assert.equal(scan([], [], pageData, 'https://www.douyin.com/user/person?modal_id=999').length, 0);
assert.equal(scan([], [], {...pageData, video: {...pageData.video, is_drm: true}}, 'https://www.douyin.com/video/123').length, 0);
console.log('Current-item page data: blob source mapping, unrelated-item exclusion and DRM exclusion passed');
