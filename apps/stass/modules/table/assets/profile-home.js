'use strict';
(async () => {
  const area = document.getElementById('quick-actions');
  const actions = {
    assetLibrary:['打开 AI资产库','/STASS/?section=motions&assetLibrary=red-white'],
    tables:['查看素材表格','/STASS/?section=tables'],
    reports:['查看数据报表','/STASS/?section=reports'],
    rewrites:['打开讲解稿与文案版本','/STASS/?section=rewrites'],
    storyboard:['打开分镜审阅','/STASS/?section=rewrites&rewriteTab=openingStoryboard'],
    breakdowns:['打开视频拉片','/STASS/breakdowns'],
    motions:['查看 Motion 模板','/STASS/?section=motions&assetLibrary=motion'],
    characters:['整理角色与场景素材','根据我的参考素材整理角色与场景，请调用已安装的素材库或角色卡技能。'],
    creator:['编排生成工作流','使用 Creator MCP 查看我的工作流草稿，先整理所需的素材和节点。'],
    beam:['3D 录屏','请在本机启动器中打开 3D 录屏。']
  };
  async function refresh() {
    const response = await fetch('/STASS/api/v1/work-navigation');
    if (!response.ok) throw Error('无法读取工作偏好');
    const prefs = await response.json();
    if(prefs.groups === null){ location.replace('/STASS/'); return; }
    let inventory;
    try {
      const agent = localStorage.getItem('studio.featureHost') || 'codex';
      const result = await fetch('/STASS/api/v1/work-preferences', {method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'inspect',agent})});
      if(result.ok) inventory=(await result.json()).status;
    } catch {}
    const skills = {assetLibrary:'assets',tables:'table',reports:'reports',rewrites:'rewrite',
      storyboard:'rewrite',breakdowns:'workbench',motions:'motion',characters:'character-card',creator:'workflow-mcp',beam:'beam'};
    area.replaceChildren();
    for (const id of prefs.views) {
      if (!actions[id] || (id==='beam' && !prefs.beam)) continue;
      const [name, destination] = actions[id];
      const link = destination.startsWith('/STASS/') ? document.createElement('a') : document.createElement('button');
      link.textContent = name;
      if (link.tagName === 'A') link.href = destination;
      else {
        link.textContent += ' · 复制使用提示词';
        link.onclick = async () => {
          try {await navigator.clipboard.writeText(destination); document.getElementById('quick-status').textContent='使用提示词已复制';}
          catch {document.getElementById('quick-status').textContent=destination;}
        };
      }
      const card=document.createElement('div'), note=document.createElement('small');
      const status=inventory?.[skills[id]];
      note.textContent=status === '已安装' ? '技能已安装 · 外部依赖按需配置' : (status || '在本机检查配置');
      card.append(link,note); area.append(card);
    }
    if(!area.children.length) area.textContent='可以在设置中选择日常工作。';
  }
  const update = () => refresh().catch(e=>document.getElementById('quick-status').textContent=e.message);
  update(); window.addEventListener('focus',update); window.addEventListener('storage',update); window.addEventListener('work-profile-updated',update);
})();
