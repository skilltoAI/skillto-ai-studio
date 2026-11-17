const params=new URLSearchParams(location.search);
const tableId=params.get('table');
const el=id=>document.getElementById(id);
let videos=[];
let descending=true;
const fmt=n=>Number.isFinite(Number(n))?Number(n).toLocaleString('zh-CN'):'—';
function cell(text,cls){const td=document.createElement('td');if(cls)td.className=cls;td.textContent=text??'—';return td}
function render(){
  const q=el('search').value.trim().toLowerCase(),platform=el('platform').value,from=el('from').value,to=el('to').value;
  const found=videos.filter(v=>{const f=v.fields||{};return(!q||[f.title,f.author,f.keyword].some(x=>String(x||'').toLowerCase().includes(q)))&&(!platform||f.platform===platform)&&(!from||f.publishedAt>=from)&&(!to||f.publishedAt<=to)}).sort((a,b)=>descending?(b.fields.likeCount||0)-(a.fields.likeCount||0):(a.fields.likeCount||0)-(b.fields.likeCount||0));
  el('count').textContent=`显示 ${found.length} / ${videos.length} 条短视频`;
  const body=el('rows');body.replaceChildren();
  found.forEach((v,i)=>{const f=v.fields||{},tr=document.createElement('tr');tr.append(cell(String(i+1)));
    const title=cell('');const titleText=document.createElement('div');titleText.className='video-title';titleText.textContent=f.title||'未命名视频';title.append(titleText);const kw=document.createElement('div');kw.className='keyword';kw.textContent=f.keyword||'';title.append(kw);tr.append(title);
    const author=cell(f.author||'—');const p=document.createElement('span');p.className='platform';p.textContent=f.platform||'未知平台';author.append(document.createElement('br'),p);tr.append(author);
    const date=cell(f.publishedAt||'待核验');if(f.verification==='待核验'){const mark=document.createElement('div');mark.className='date-note';mark.textContent='日期待复核';date.append(mark)}tr.append(date);tr.append(cell(fmt(f.likeCount),'likes'));
    const linkCell=cell('');const link=document.createElement('a');link.className='play';link.href=f.videoUrl||'#';link.target='_blank';link.rel='noopener noreferrer';link.textContent='▶ 看视频';linkCell.append(link);tr.append(linkCell);body.append(tr)})
}
async function load(){if(!tableId){el('summary').textContent='缺少表格 ID';return}try{const response=await fetch('/api/table?id='+encodeURIComponent(tableId));if(!response.ok)throw Error('HTTP '+response.status);const table=await response.json();videos=(table.rows||[]).filter(r=>r.fields?.videoUrl);el('title').textContent=table.title||'AI 光影短视频';el('summary').textContent='2026-08-06 至 2026-10-06 · 按点赞量浏览 · 点击“看视频”打开原作品';el('export').href='/api/export?id='+encodeURIComponent(tableId);render()}catch(e){el('summary').textContent='表格读取失败：'+e.message}}
['search','platform','from','to'].forEach(id=>el(id).addEventListener('input',render));el('reset').addEventListener('click',()=>{['search','platform','from','to'].forEach(id=>el(id).value='');render()});el('sortLikes').addEventListener('click',()=>{descending=!descending;el('sortLikes').textContent='点赞数 '+(descending?'↓':'↑');render()});load();
