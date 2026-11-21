const ALL_SLIDES = [
  { tab: "表格", title: "多媒体表格", img: "studio-media-table", path: "table", desc: "知识库、项目、表三级管理素材。图片与视频直接入表，评分和标签供 AI 检索。" },
  { tab: "标签", title: "字段与标签", img: "studio-tables", path: "table", desc: "字段筛选、显示字段、标签与人工评分，并记录每条数据的采集来源与整理规则。" },
  { tab: "Motion", title: "Motion 模版", img: "studio-motion-gallery", path: "motion", desc: "模版库支持语义搜索、评分与收藏，按画幅和运行次数筛选后直接套用。" },
  { tab: "洗稿", title: "洗稿", img: "studio-rewrite", path: "rewrite", desc: "对标稿件按版本迭代，从原文亮点、视效亮点推进到配音与分镜。" },
  { tab: "分镜", title: "Motion 分镜表", img: "studio-storyboard", path: "rewrite", desc: "每个镜头的口播文案、画面动效与评分，在同一张表里协同完成。" },
];
let SLIDES = ALL_SLIDES;
const $ = id => document.getElementById(id);
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const hero = document.querySelector('.hero');
const dialog = $('pairDlg');
const tabs = $('tabs');
let state = {phase: 'starting', running: false, url: ''};
let slide = 0;
let slideTimer;
let toastTimer;
let pairTimer;
let pair;
let requestingPair = false;

function toast(message) {
  $('toast').hidden = false;
  $('toast').textContent = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, 4400);
}

function command(action) {
  return async () => {
    try { await action(); }
    catch (error) { toast(String(error?.message || error)); }
  };
}

function render(next) {
  state = next;
  const busy = ['starting', 'stopping'].includes(next.phase);
  $('win').dataset.state = next.phase;
  $('status').textContent = {
    starting: '正在启动服务…', stopping: '正在关闭服务…',
    running: '服务正在运行', stopped: '服务已关闭', error: '操作未完成',
  }[next.phase];
  const seconds = Math.max(0, next.uptime || 0);
  const elapsed = [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60]
    .map(value => String(value).padStart(2, '0')).join(':');
  $('detail').textContent = next.error || (next.running
    ? [next.url, 'PID ' + next.pid, elapsed].join(' · ')
    : busy ? '请稍候' : '数据保留在本地，可随时重新启动');
  $('detail').title = $('detail').textContent;
  $('powerText').textContent = next.running ? '关闭服务' : '启动服务';
  $('power').classList.toggle('danger', next.running);
  $('power').classList.toggle('go', !next.running && !busy);
  $('power').disabled = busy;
  for (const id of ['open', 'users', 'pairBtn']) $(id).disabled = !next.running || busy;
  $('copy').disabled = !next.running;
  document.querySelector('.top-meta').textContent = next.version ? 'STUDIO · v' + next.version : 'STUDIO';
  $('frameUrl').textContent = next.url && SLIDES.length ? (next.url + SLIDES[slide].path).replace(/^https?:\/\//, '') : '';
  if (!next.running && dialog.open) dialog.close();
}

function scheduleSlide() {
  clearTimeout(slideTimer);
  const paused = document.hidden || !document.hasFocus() || reducedMotion.matches || dialog.open ||
      hero.matches(':hover') || hero.contains(document.activeElement);
  hero.classList.toggle('paused', paused);
  if (paused || SLIDES.length < 2) return;
  slideTimer = setTimeout(() => selectSlide(slide + 1), 5000);
}

function selectSlide(index, focus = false) {
  slide = (index + SLIDES.length) % SLIDES.length;
  const item = SLIDES[slide];
  $('slideNo').textContent = String(slide + 1).padStart(2, '0');
  $('slideTitle').textContent = item.title;
  $('slideDesc').textContent = item.desc;
  $('slideImg').src = 'assets/' + item.img + '.png';
  $('slideImg').alt = item.title + '界面截图';
  if (!reducedMotion.matches) {
    $('frame').getAnimations().forEach(animation => animation.cancel());
    $('frame').animate([{opacity: 0.3}, {opacity: 1}], {duration: 240});
  }
  $('frameUrl').textContent = state.url ? (state.url + item.path).replace(/^https?:\/\//, '') : '';
  [...tabs.children].forEach((button, i) => {
    button.setAttribute('aria-selected', String(i === slide));
    button.tabIndex = i === slide ? 0 : -1;
  });
  if (focus) tabs.children[slide].focus();
  scheduleSlide();
}

function buildTabs() {
  tabs.replaceChildren();
  for (const [index, item] of SLIDES.entries()) {
    const button = document.createElement('button');
    button.type = 'button';
    button.setAttribute('role', 'tab');
    button.textContent = item.tab;
    button.onclick = () => selectSlide(index);
    button.onkeydown = event => {
      const next = {ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: SLIDES.length - 1}[event.key];
      if (next === undefined) return;
      event.preventDefault();
      selectSlide(next, true);
    };
    tabs.append(button);
  }
}
buildTabs();
for (const event of ['mouseenter', 'mouseleave', 'focusin', 'focusout']) {
  hero.addEventListener(event, () => setTimeout(scheduleSlide, 0));
}
document.addEventListener('visibilitychange', scheduleSlide);
window.addEventListener('focus', scheduleSlide);
window.addEventListener('blur', scheduleSlide);
reducedMotion.addEventListener('change', scheduleSlide);
selectSlide(0);

function updatePair() {
  const left = Math.max(0, Math.ceil((pair.until - Date.now()) / 1000));
  $('pairTime').textContent = left ? '剩余 ' + left + ' 秒' : '配对码已过期';
  $('copyPair').disabled = left === 0;
  dialog.querySelector('.expire span').style.setProperty('--p', left / pair.expiresIn);
  if (!left) {
    dialog.querySelector('.code').textContent = '请关闭后重新获取';
    pair.code = '';
    clearInterval(pairTimer);
  }
}

window.addEventListener('DOMContentLoaded', () => {
  const api = window.go?.main?.Launcher;
  const desktop = window.runtime;
  if (!api || !desktop) {
    render({...state, phase: 'error', error: '无法连接启动器，请重启程序'});
    return;
  }
  desktop.EventsOn('launcher:state', render);
  command(async () => render(await api.State()))();
  $('minimize').onclick = desktop.WindowMinimise;
  $('closeWindow').onclick = desktop.Quit;
  $('power').onclick = command(() => state.running ? api.Stop() : api.Start());
  $('open').onclick = command(api.OpenWorkbench);
  const featureDlg = $('featureDlg');
  $('features').onclick = () => {
    featureDlg.querySelector('iframe').src = 'features.html';
    featureDlg.showModal();
  };
  async function refreshFeatures() {
    const info = JSON.parse(await api.WorkPreferences(JSON.stringify({action:'navigation'})));
    const map = {table:'tables',motion:'motions',rewrite:'rewrites'};
    SLIDES = ALL_SLIDES.filter(item => info.groups === null || info.views.includes(item.tab === '分镜' ? 'storyboard' : map[item.path]));
    const recording = info.beam && (info.groups === null || info.views.includes('beam'));
    $('rec3d').hidden = !recording;
    hero.hidden = !SLIDES.length && !recording;
    buildTabs();
    if (SLIDES.length) selectSlide(0); else clearTimeout(slideTimer);
    $('users').hidden = info.groups !== null && !info.groups.includes('social');
  }
  command(refreshFeatures)();
  window.addEventListener('work-preferences', command(refreshFeatures));
  window.addEventListener('focus', command(refreshFeatures));
  $('users').onclick = command(api.OpenBrowserUsers);
  $('copy').onclick = command(async () => {
    if (!await desktop.ClipboardSetText(state.url)) throw new Error('无法复制地址');
    toast('已复制工作台地址');
  });
  $('rec3d').onclick = command(async () => {
    $('rec3d').disabled = true;
    try { await api.OpenBeam(); }
    finally { setTimeout(() => { $('rec3d').disabled = false; }, 1500); }
  });
  $('pairBtn').onclick = command(async () => {
    if (requestingPair || dialog.open) return;
    requestingPair = true;
    try {
      const result = await api.PairCode();
      if (!state.running) return;
      pair = {...result, until: Date.now() + result.expiresIn * 1000};
      const groups = pair.code.match(/.{4}/g);
      dialog.querySelector('.code').textContent = groups.slice(0, 3).join(' ') + '\n' + groups.slice(3).join(' ');
      updatePair();
      dialog.showModal();
      pairTimer = setInterval(updatePair, 250);
      scheduleSlide();
    } finally {
      requestingPair = false;
    }
  });
  $('copyPair').onclick = command(async () => {
    if (!pair?.code || Date.now() >= pair.until) return;
    if (!await desktop.ClipboardSetText(pair.code)) throw new Error('无法复制配对码');
    dialog.close();
    toast('已复制配对码');
  });
  dialog.querySelector('[data-close]').onclick = () => dialog.close();
  dialog.addEventListener('close', () => {
    clearInterval(pairTimer);
    dialog.querySelector('.code').textContent = '';
    pair = undefined;
    scheduleSlide();
  });
});
