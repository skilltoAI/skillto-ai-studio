/* Runs the real pure list selector with edge-case fixtures, without a browser. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../assets/motion-system.js'),'utf8');
const start=source.indexOf('  function rows()'),end=source.indexOf('  const itemBy',start);
assert(start>=0&&end>start,'list selector boundary changed');
const item=(id,runCount,publishedAt,rating=1,tagIds=[])=>({id,title:id,description:'',source:'MotionGit',category:'文字',aspect:'16:9',engine:'known',favorite:false,runCount,publishedAt,rating,tagIds});
const data={tags:[{id:'a',name:'字效'},{id:'b',name:'已验证'}],items:[
 item('missingold',null,'2024-01-01'),item('zero',0,'2023-01-01',5,['a']),
 item('highold',10,'2024-01-01',3,['a']),item('missingdate',null,null),
 item('highnew',10,'2025-01-01',4,['a','b']),item('missingnew',null,'2026-01-01',2,['b'])]};
const base={q:'',category:'',source:'',favorite:false,aspect:'',tags:[],tagMode:'all',untagged:false,sort:'runs',engine:''};
const select=opts=>{const ctx=vm.createContext({data,sourceFilters:{},semanticIds:null,view:{...base,...opts}});return vm.runInContext(source.slice(start,end)+';rows().map(i=>i.id).join(",")',ctx);};
assert.equal(select({}),'highnew,highold,zero,missingnew,missingold,missingdate');
assert.equal(select({sort:'rating'}),'zero,highnew,highold,missingnew,missingold,missingdate');
assert.equal(select({tags:['a','b']}),'highnew');
assert.equal(select({tags:['a','b'],tagMode:'any'}),'highnew,highold,zero,missingnew');
assert.equal(select({q:'字效',source:'MotionGit',aspect:'16:9'}),'highnew,highold,zero');
assert.equal(select({untagged:true}),'missingold,missingdate');
assert.equal(select({aspect:'9:16'}),'');
data.items.find(i=>i.id==='highnew').viewed=true;
assert.equal(select({viewed:'viewed'}),'highnew');
assert.equal(select({viewed:'unviewed'}),'highold,zero,missingnew,missingold,missingdate');
assert.equal(select({viewed:'viewed',tags:['b']}),'highnew');
data.items=[item('half',1,'2026-01-01',.5,['a']),item('manual',1,'2026-01-01',3.5,['a']),item('auto',1,'2026-01-01',1),item('unrated',1,'2026-01-01',null)];
data.items.find(i=>i.id==='auto').ratingSource='view-default';
assert.equal(select({ratingMin:'3.5',ratingMax:'3.5'}),'manual');
assert.equal(select({ratingMin:'.5',ratingMax:'1'}),'auto,half');
assert.equal(select({ratingMin:'1',ratingKind:'manual'}),'manual');
assert.equal(select({ratingKind:'default'}),'auto');
assert.equal(select({ratingKind:'unrated'}),'unrated');
assert.equal(select({ratingMax:'3.5',tags:['a']}),'half,manual');
assert.equal(select({ratingMin:'4'}),'');
console.log('17 list-selector cases passed: zero/null sorting, publication tie-break, rating, all/any tags, combined filters and empty state');
