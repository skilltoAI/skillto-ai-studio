'use strict';
const el = id => document.getElementById(id);
const launcher = window.parent !== window && window.parent.go?.main?.Launcher;
const host = el('host');
try { host.value = localStorage.getItem('studio.featureHost') || 'codex'; } catch {}
let info, groups, wanted, pending = false, generation = 0;
const area = document.querySelector('textarea');
const handoff = '安装提示词已复制。请在你使用的 Codex、Claude Code 或 WorkBody 中粘贴并运行。';
function message(value) {
  el('result').hidden = false;
  el('message').textContent = value;
}
async function request(args) {
  if (launcher) return JSON.parse(await launcher.WorkPreferences(JSON.stringify(args)));
  const response = await fetch('/STASS/api/v1/work-preferences', {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(args)
  });
  const body = await response.json();
  if (!response.ok) throw Error(body.error || '无法读取配置');
  return body;
}
function resolved() {
  const result = new Set(wanted);
  for (const id of result) {
    for (const dep of info.catalog.items.find(row => row.id === id).requires) result.add(dep);
  }
  return result;
}
function card(row, selected, toggle, status='', required=false) {
  const box = document.createElement('article');
  const label = document.createElement('label'), check = document.createElement('input');
  check.type = 'checkbox'; check.checked = selected; check.disabled = required;
  check.onchange = () => toggle(check.checked);
  label.append(check, ' ' + row.name);
  const summary = document.createElement('p');
  summary.textContent = row.summary;
  const detail = document.createElement('details'), title = document.createElement('summary');
  title.textContent = '了解功能';
  detail.append(title, document.createTextNode(row.description));
  box.append(label, summary);
  if (status) {
    const note = document.createElement('small');
    note.textContent = status + (required ? ' · 所选功能需要' : '');
    box.append(note);
  }
  if (row.requires) {
    const meta = document.createElement('p');
    const belongs = info.catalog.groups.filter(g => [...row.defaults,...row.optional].includes(g.id)).map(g=>g.name);
    const deps = row.requires.map(key=>info.catalog.items.find(r=>r.id===key).name);
    meta.textContent = '适用工作：' + belongs.join('、') + '。' + (deps.length ? '配套项目：' + deps.join('、') + '。' : '') + row.needs;
    detail.append(meta);
  }
  box.append(detail);
  return box;
}
function changeGroup(id, on) {
  const oldGroups = new Set(groups);
  if (on) groups.add(id); else groups.delete(id);
  for (const item of info.catalog.items) {
    const wasDefault = item.defaults.some(key => oldGroups.has(key));
    const isDefault = item.defaults.some(key => groups.has(key));
    const isRelevant = [...item.defaults, ...item.optional].some(key => groups.has(key));
    if (isDefault && !wasDefault) wanted.add(item.id);
    if (!isRelevant || (wasDefault && !isDefault)) wanted.delete(item.id);
  }
  render();
}
function differences() {
  const selected = [...resolved()];
  const old = info.profile;
  const hiding = old.groups !== null && [...groups].every(id => old.groups.includes(id)) &&
    selected.every(id => old.items.includes(id)) &&
    (groups.size < old.groups.length || selected.length < old.items.length);
  if (hiding || !groups.size && !selected.length) return [];
  const missing = selected.filter(id => info.status[id] !== '已安装');
  return info.parentStatus === '已安装' ? missing : ['skillto-ai-studio', ...missing];
}
function render() {
  const selected = resolved();
  el('groups').replaceChildren(...info.catalog.groups.map(row =>
    card(row, groups.has(row.id), on => changeGroup(row.id,on))));
  el('items').replaceChildren(...info.catalog.items.filter(row =>
    selected.has(row.id) || [...row.defaults,...row.optional].some(id=>groups.has(id))).map(row =>
    card(row, selected.has(row.id), on => { if(on) wanted.add(row.id); else wanted.delete(row.id); render(); },
      info.status[row.id], selected.has(row.id) && !wanted.has(row.id))));
  const diff = differences();
  const reused = selected.size - [...selected].filter(key=>info.status[key] !== '已安装').length;
  const missing = diff.filter(id => (info.status[id] || info.parentStatus) === '待安装').length;
  el('count').textContent = '已选 ' + groups.size + ' 类 · 可复用 ' + reused + ' 项 · 将新增 ' + missing + ' 项' +
    (diff.length > missing ? ' · 需核对 ' + (diff.length-missing) + ' 项' : '');
  el('save').textContent = diff.length ? '保存选择并复制安装提示词' : '保存界面设置';
  el('save').disabled = pending;
}
async function load(keep = false) {
  const token = ++generation;
  el('save').disabled = true;
  try {
    const next = await request({action:'inspect',agent:host.value});
    if(token !== generation) return;
    if (!keep || !info || next.profile.revision !== info.profile.revision) {
      groups = new Set(next.profile.groups || []);
      wanted = new Set(next.profile.items);
    }
    info = next; render();
  } catch (error) { if(token === generation) {info = null; message(String(error));} }
}
function promptText(diff) {
  const catalog = info.catalog;
  return [
    '从 https://github.com/skilltoAI/skillto-ai-studio 按当前客户端增补组件和技能。',
    '仓库提交或清单版本：' + info.source,
    '本次新增类别：' + catalog.groups.filter(g=>groups.has(g.id) && !(info.profile.groups || []).includes(g.id)).map(g=>g.name).join('、'),
    '工作类别：' + catalog.groups.filter(g=>groups.has(g.id)).map(g=>g.name).join('、'),
    '已选项目：' + [...resolved()].join(', '), '待安装或需核对：' + diff.join(', '),
    '直接使用清单，不再询问类别。先核对宿主、版本、安装范围和已有文件，保留本机修改。按组件指引单独配置外部程序。',
    'Codex / Claude Code 可在对应版本运行 python scripts/install.py --agent <codex或claude> --groups ' +
      [...groups].join(',') + ' --items "' + [...resolved()].join(',') + '"。',
    'WorkBody 请先验证自身技能接口，无法识别时报告缺项。最后分别报告新增、复用、待配置和第一条示例任务。'
  ].join('\n');
}
async function copy() {
  try {
    if (launcher) {
      if (!await window.parent.runtime.ClipboardSetText(area.value)) throw Error();
    } else await navigator.clipboard.writeText(area.value);
    message(handoff);
  } catch {
    el('preview').open = true; area.focus(); area.select(); message('请复制已选中的提示词，在客户端中运行。');
  }
}
el('copy').onclick = copy;
el('save').onclick = async () => {
  if (!info || pending) return;
  const diff = differences(), prompt = diff.length && promptText(diff);
  pending = true; el('save').disabled = true; host.disabled = el('detect').disabled = true;
  el('groups').inert = el('advanced').inert = true;
  try {
    info.profile = await request({action:'save',groups:[...groups],items:[...resolved()],revision:info.profile.revision});
    if (launcher) window.parent.dispatchEvent(new Event('work-preferences'));
    else { try { localStorage.setItem('studio.features.changed',String(Date.now())); } catch {} }
    el('preview').hidden = !prompt;
    if(prompt) { area.value = prompt; await copy(); } else message('界面设置已保存。');
  } catch(error) { message(String(error)); }
  finally { pending = false; host.disabled = el('detect').disabled = false; el('groups').inert = el('advanced').inert = false; render(); }
};
host.onchange = () => {try { localStorage.setItem('studio.featureHost',host.value); } catch {} load(true);};
el('detect').onclick = () => load(true);
el('preview').hidden = true;
if (launcher) {
  el('back').textContent = '返回启动器';
  el('back').onclick = event => {event.preventDefault();window.parent.document.getElementById('featureDlg').close();};
}
load();
