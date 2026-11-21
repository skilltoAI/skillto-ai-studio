const $ = id => document.getElementById(id);
let busy = false, editing;
async function call(args) {
  const response = await fetch('/api/browser', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(args)});
  const data = await response.json();
  if (!response.ok) throw Error(data.error || '操作失败');
  return data.result;
}
async function refresh() {
  const {users} = await call({action:'list'});
  $('users').replaceChildren();
  if (!users.length) $('users').textContent = '暂无浏览器用户，请先创建。';
  for (const user of users) {
    const row = document.createElement('article');
    const name = document.createElement('span'); name.className='name'; name.textContent=user.name;
    const status = document.createElement('span'); status.className='status'; status.textContent=user.running?'运行中':'已关闭';
    row.append(name,status);
    for (const [label,action] of [[user.running?'查看浏览器':'打开浏览器','launch'],['关闭浏览器','close'],['改名','rename'],['删除','delete']]) {
      const button=document.createElement('button'); button.textContent=label;
      button.disabled=busy || (action==='close'&&!user.running) || (action==='delete'&&user.running);
      if(action==='delete') button.className='danger';
      button.onclick=()=>{
        if(action==='rename'||action==='delete') {
          editing={user,action}; $('edit-title').textContent=action==='rename'?'修改用户名':'删除浏览器用户';
          $('edit-help').textContent=action==='rename'?'改名保留所有 Cookie 和用户环境。':`输入“${user.name}”确认删除。环境将移入本地回收目录。`;
          $('edit-name').value=action==='rename'?user.name:''; $('editor').showModal(); $('edit-name').focus();
        } else run(async()=>{
          await call({action,userId:user.id});
        });
      };
      row.append(button);
    }
    $('users').append(row);
  }
}
async function run(job) {
  if(busy)return; busy=true; $('message').textContent='正在处理…';
  document.querySelectorAll('button').forEach(b=>b.disabled=true);
  try { await job(); $('message').textContent='已保存到本机。'; }
  catch(e){$('message').textContent=e.message;}
  finally {busy=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);await refresh().catch(e=>$('message').textContent=e.message);}
}
$('create').onsubmit=e=>{e.preventDefault();run(async()=>{await call({action:'create',name:$('name').value});$('name').value='';});};
$('edit').onsubmit=e=>{e.preventDefault();const {user,action}=editing;const value=$('edit-name').value;$('editor').close();run(()=>call({action,userId:user.id,...(action==='rename'?{name:value}:{confirmName:value})}));};
$('cancel').onclick=()=>$('editor').close();
$('refresh').onclick=()=>run(async()=>{});
refresh().catch(e=>$('message').textContent=e.message);
