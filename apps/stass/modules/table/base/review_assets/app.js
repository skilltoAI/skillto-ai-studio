const state = {catalog: null, table: null, selected: null, sort: {field: "followerCount", direction: -1}, row: null, entity: null};
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[char]);
const safeUrl = (value) => { try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) ? url.href : ""; } catch { return ""; } };
const formatNumber = (value) => value === null || value === undefined || value === "" ? "—" : Number(value).toLocaleString("zh-CN", {maximumFractionDigits: 1});
const formatDate = (value) => value ? String(value).slice(0, 10) : "—";
const rowName = (row) => isOmniTable() ? row.fields.beatName : isFusionTable() ? `${row.fields.techniqueTitle || "太极拳"} · ${row.fields.sceneLocation || "场景"}` : (isVideoTable() ? row.fields.title : row.fields.accountName) || row.fields.title || "未命名记录";
const isVideoTable = () => state.table?.fields.some((field) => field.name === "videoFile");
const isEditTable = () => state.table?.fields.some((field) => field.name === "sequence");
const isFusionTable = () => state.table?.fields.some((field) => field.name === "fusionPrompt");
const isOmniTable = () => state.table?.fields.some((field) => field.name === "omniPrompt");
const candidateDefinitions = () => state.table?.fields.filter((field) => field.type === "image" && field.candidateGroup) || [];
const candidateImageUrl = (value) => /^\/generated\/[0-9a-f-]{36}\/[a-z0-9_-]+\.(?:png|jpg|webp)$/.test(value || "") || /^\/artifacts\/omni_depth\/(?:white_model_reference|white_model_reference_latest|omni_first_clip_storyboard)\.png$/.test(value || "") ? value : safeUrl(value);
const cacheKey = (tableId) => `skillto-table-cache:${tableId}`;

function cacheTable(table) {
  try { localStorage.setItem(cacheKey(table.id), JSON.stringify(table)); } catch {}
}

async function readTable(tableId) {
  try {
    const table = await api(`/api/table?id=${encodeURIComponent(tableId)}`);
    cacheTable(table);
    return {table, cached: false};
  } catch (error) {
    const cached = localStorage.getItem(cacheKey(tableId));
    if (!cached) throw error;
    return {table: JSON.parse(cached), cached: true};
  }
}

async function api(path, payload) {
  const response = await fetch(path, payload === undefined ? undefined : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "请求失败");
  return body;
}

function notify(message, error = false) {
  $("#notice").textContent = message;
  $("#notice").style.color = error ? "var(--err)" : "var(--ok)";
  $("#saveStatus").dataset.state = error ? "error" : "saved";
  $("#saveStatus").textContent = error ? "保存失败，请重试" : "已保存到本地文件";
}

function showCatalogState(kind, message, actionLabel, onAction) {
  $(".main").dataset.tableState = kind;
  const box = $("#catalogState");
  box.hidden = false;
  box.querySelector("p").textContent = message;
  const action = box.querySelector("button");
  action.textContent = actionLabel || "";
  action.hidden = !onAction;
  action.onclick = onAction || null;
}

async function openCatalog() {
  showCatalogState("loading", "正在读取表格…");
  try {
    await loadCatalog(new URLSearchParams(location.search).get("table"));
  } catch (error) {
    showCatalogState("error", "读取表格失败：" + error.message, "重试", openCatalog);
  }
}

async function loadCatalog(preferredId) {
  state.catalog = await api("/api/catalog");
  renderTree();
  const tables = state.catalog.knowledgeBases.flatMap((base) => base.projects.flatMap((project) => project.tables.map((table) => ({base, project, table}))));
  const selected = tables.find((entry) => entry.table.id === (preferredId || state.selected?.table.id)) || tables.find((entry) => entry.table.name === "账号表现") || tables[0];
  if (selected) await selectTable(selected);
  else {
    state.table = null;
    state.selected = null;
    $("#tableTitle").textContent = "内容资料库";
    $("#breadcrumb").textContent = "";
    $("#tableSubtitle").textContent = "";
    const base = state.catalog.knowledgeBases[0];
    const project = base?.projects[0];
    const level = project ? "table" : base ? "project" : "knowledge_base";
    showCatalogState("empty", "资料库中还没有表格。", project ? "新建表" : base ? "新建项目" : "新建知识库",
      () => openEntity(level, "create", null, {base, project}));
  }
}

function treeLine(item, level, parents) {
  const line = document.createElement("div");
  line.className = "tree-line" + (level === "table" && state.selected?.table.id === item.id ? " active" : "");
  const icon = document.createElement("span");
  icon.className = "tree-icon";
  icon.textContent = level === "knowledge_base" ? "▦" : level === "project" ? "▤" : "≡";
  line.append(icon);
  const select = document.createElement("button");
  select.className = "tree-select";
  select.textContent = item.name;
  select.title = item.name;
  select.addEventListener("click", () => level === "table" ? selectTable({base: parents.base, project: parents.project, table: item}) : line.nextElementSibling?.classList.toggle("collapsed"));
  line.append(select);
  if (level !== "table") {
    const add = document.createElement("button");
    add.className = "icon-button";
    add.textContent = "＋";
    add.title = level === "knowledge_base" ? "新建项目" : "新建表";
    add.setAttribute("aria-label", add.title);
    add.addEventListener("click", () => openEntity(level === "knowledge_base" ? "project" : "table", "create", null, {...parents, [level === "knowledge_base" ? "base" : "project"]: item}));
    line.append(add);
  }
  const more = document.createElement("button");
  more.className = "icon-button nav-more";
  more.textContent = "⋯";
  more.title = "重命名或删除";
  more.setAttribute("aria-label", `${item.name}的操作`);
  more.addEventListener("click", () => openEntity(level, "edit", item, parents));
  line.append(more);
  return line;
}

function renderTree() {
  const nav = $("#tree");
  nav.replaceChildren();
  for (const base of state.catalog.knowledgeBases) {
    nav.append(treeLine(base, "knowledge_base", {}));
    const projectGroup = document.createElement("div");
    projectGroup.className = "tree-children";
    for (const project of base.projects) {
      projectGroup.append(treeLine(project, "project", {base}));
      const tableGroup = document.createElement("div");
      tableGroup.className = "tree-children";
      for (const table of project.tables) tableGroup.append(treeLine(table, "table", {base, project}));
      projectGroup.append(tableGroup);
    }
    nav.append(projectGroup);
  }
}

async function selectTable(entry) {
  state.selected = entry;
  const loaded = await readTable(entry.table.id);
  state.table = loaded.table;
  const url = new URL(location.href);
  url.searchParams.set("table", entry.table.id);
  history.replaceState(null, "", url);
  const videoTable = isVideoTable();
  const editTable = isEditTable();
  const fusionTable = isFusionTable();
  const omniTable = isOmniTable();
  state.sort = {field: editTable ? "sequence" : videoTable ? "likeCount" : "followerCount", direction: editTable ? 1 : -1};
  $("#dataTable").classList.toggle("video-table", videoTable);
  $("#dataTable").classList.toggle("edit-table", editTable);
  $("#dataTable").classList.toggle("fusion-table", fusionTable);
  const candidateHeaders = candidateDefinitions().map((field) => `<th>${escapeHtml(field.label || field.name)}</th>`).join("");
  $("#tableHead").innerHTML = omniTable
    ? '<tr><th>一次提交</th><th>场景服饰 A</th><th>场景服饰 B</th><th>场景服饰 C</th><th>白模参考</th><th>彩色 / 深度灰视频</th><th>单条 Omni 提示词</th><th>生成视频 / 状态</th></tr>'
    : fusionTable
    ? '<tr><th><button data-sort="sequence">顺序 ↕</button></th><th>拳段 / 原视频</th><th>垫图1·人物服饰</th><th>垫图2·场景空镜</th><th>时段 / 用光</th><th>双图融合提示词</th><th>9:16融合图</th><th>状态</th><th>评分</th></tr>'
    : editTable
    ? `<tr><th><button data-sort="sequence">顺序 ↕</button></th><th>封面</th><th>视频 / 账号</th><th>剪映片段</th><th>来源标签</th><th>打分</th><th><button data-sort="likeCount">点赞 ↕</button></th><th>互动数据</th><th>发表时间</th><th>完整视频</th><th>原视频</th>${candidateHeaders}</tr>`
    : videoTable
    ? `<tr><th>封面</th><th>视频 / 账号</th><th>视频标签</th><th><button data-sort="likeCount">点赞 ↕</button></th><th>打分</th><th><button data-sort="likeRatio">均值倍数 ↕</button></th><th><button data-sort="collectCount">收藏 ↕</button></th><th><button data-sort="shareCount">转发 ↕</button></th><th><button data-sort="commentCount">评论 ↕</button></th><th><button data-sort="playCount">播放 ↕</button></th><th><button data-sort="publishedAt">发表时间 ↕</button></th><th>视频文件</th><th>原视频</th>${candidateHeaders}</tr>`
    : `<tr><th class="account-col">账号</th><th>标签</th><th><button data-sort="followerCount">粉丝数 ↕</button></th><th><button data-sort="videoCount30d">近30天视频 ↕</button></th><th><button data-sort="averageLikes">平均点赞 ↕</button></th><th><button data-sort="averageCollects">平均收藏 ↕</button></th><th><button data-sort="averageShares">平均分享 ↕</button></th><th><button data-sort="averageLikeCollectRatio">平均赞藏比 ↕</button></th><th class="videos-col">最近10条视频</th><th>评分</th><th></th>${candidateHeaders}</tr>`;
  $("#minVideos").closest("label").hidden = videoTable || fusionTable || omniTable;
  $("#addRowButton").hidden = videoTable || fusionTable || omniTable;
  $("#searchInput").placeholder = omniTable ? "搜索节拍或场景" : fusionTable ? "搜索拳段或场景" : videoTable ? "搜索视频或账号" : "搜索账号或视频";
  $("#dateFrom").closest("label").hidden = fusionTable || omniTable;
  $("#dateTo").closest("label").hidden = fusionTable || omniTable;
  $("#dateFrom").closest("label").querySelector("span").textContent = videoTable ? "发表时间自" : "视频发布自";
  $("#breadcrumb").textContent = `${entry.base.name} / ${entry.project.name}`;
  $("#tableTitle").textContent = entry.table.name;
  $("#tableSubtitle").textContent = state.table.subtitle || "";
  renderTree();
  renderTagFilter();
  renderMetrics();
  renderRows();
  $(".main").dataset.tableState = "ready";
  $("#catalogState").hidden = true;
  $("#saveStatus").dataset.state = "";
  $("#saveStatus").textContent = "已连接本地文件";
  if (loaded.cached) {
    notify("磁盘读取失败，正在显示浏览器恢复缓存", true);
    $("#saveStatus").dataset.state = "cached";
    $("#saveStatus").textContent = "仅浏览器恢复缓存";
  }
  $("#sidebar").classList.remove("open");
  $("#scrim").classList.remove("open");
}

function ratingBlocks(score) {
  if (score == null) return "未评分";
  const blocks = Array.from({length: 5}, (_, index) =>
    `<i class="${index < score ? "filled" : ""}"></i>`).join("");
  return `<span class="score-blocks" aria-hidden="true">${blocks}</span><span class="score-label">${escapeHtml(score)} / 5</span>`;
}

function tagColor(value) {
  return /^#[0-9a-f]{6}$/i.test(value) ? value : "var(--muted)";
}

function renderMetrics() {
  const rows = state.table?.rows || [];
  if (isOmniTable()) {
    $("#metrics").innerHTML = [["Omni 任务", rows.length], ["独立参考图", "4 张"], ["深度灰视频", rows.some((row) => row.fields.depthVideo) ? "已生成" : "待生成"], ["Omni 成片", rows.some((row) => row.fields.resultVideo) ? "已生成" : "待提交"]].map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
    return;
  }
  if (isFusionTable()) {
    const generated = rows.filter((row) => row.fields.fusionImage).length;
    $("#metrics").innerHTML = [["已选搭配", rows.length], ["涉及拳段", new Set(rows.map((row) => row.fields.sourceRowId)).size], ["已生成融合图", generated], ["待生成", rows.length - generated]].map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`).join("");
    return;
  }
  if (isVideoTable()) {
    if (isEditTable()) {
      const duration = rows.reduce((sum, row) => sum + Number(row.fields.clipDurationSec || 0), 0);
      const newCount = rows.filter((row) => row.fields.clipOrigin === "新增片段").length;
      $("#metrics").innerHTML = [["时间轴片段", rows.length], ["新增片段", newCount], ["保留原剪辑", rows.length - newCount], ["成片时长", `${duration.toFixed(1)} 秒`]].map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`).join("");
      return;
    }
    const available = rows.filter((row) => row.fields.videoFile).length;
    const unclassifiedId = state.table.tags.find((tag) => tag.name === "未分类")?.id;
    const unlabeled = rows.filter((row) => !(row.tagIds || []).length || (unclassifiedId && row.tagIds.includes(unclassifiedId))).length;
    $("#metrics").innerHTML = [["爆款视频", rows.length], ["涉及账号", new Set(rows.map((row) => row.fields.accountSecUid)).size], ["本地视频文件", available], ["待复核标签", unlabeled]].map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`).join("");
    return;
  }
  const totalVideos = rows.reduce((sum, row) => sum + Number(row.fields.videoCount30d || 0), 0);
  const scored = rows.filter((row) => row.rating?.score !== null && row.rating?.score !== undefined).length;
  const last = rows.map((row) => row.fields.lastCrawledAt).filter(Boolean).sort().at(-1);
  const failed = rows.filter((row) => row.fields.crawlError).length;
  $("#metrics").innerHTML = [["账号", rows.length], ["近30天视频", totalVideos], ["采集失败", failed], ["已评分", scored], ["最近采集", formatDate(last)]].map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
}

function renderTagFilter() {
  const select = $("#tagFilter");
  const previous = select.value;
  select.innerHTML = '<option value="">全部标签</option>' + state.table.tags.map((tag) => `<option value="${escapeHtml(tag.id)}">${escapeHtml(tag.name)}</option>`).join("");
  select.value = state.table.tags.some((tag) => tag.id === previous) ? previous : "";
}

function filteredRows() {
  if (!state.table) return [];
  const search = $("#searchInput").value.trim().toLocaleLowerCase();
  const tag = $("#tagFilter").value;
  const minimum = $("#minVideos").value;
  const from = $("#dateFrom").value;
  const to = $("#dateTo").value;
  const rows = state.table.rows.filter((row) => {
    const fields = row.fields;
    if (isOmniTable()) {
      if (search && !`${fields.beatName || ""} ${fields.sceneLocation || ""} ${fields.beatPrompt || ""}`.toLocaleLowerCase().includes(search)) return false;
      return !tag || (row.tagIds || []).includes(tag);
    }
    if (isFusionTable()) {
      if (search && !`${fields.title || ""} ${fields.techniqueTitle || ""} ${fields.sceneLocation || ""} ${fields.wardrobeChoice || ""} ${fields.wardrobeDirection || ""} ${fields.sceneChoice || ""}`.toLocaleLowerCase().includes(search)) return false;
      return !tag || (row.tagIds || []).includes(tag);
    }
    if (isVideoTable()) {
      if (search && !`${fields.accountName || ""} ${fields.title || ""}`.toLocaleLowerCase().includes(search)) return false;
      if (tag && !(row.tagIds || []).includes(tag)) return false;
      const date = String(fields.publishedAt || "").slice(0, 10);
      return (!from || date >= from) && (!to || date <= to);
    }
    const videos = fields.recentVideos || [];
    if (search && !`${fields.accountName || ""} ${videos.map((video) => video.title).join(" ")}`.toLocaleLowerCase().includes(search)) return false;
    if (tag && !(row.tagIds || []).includes(tag)) return false;
    if (minimum && Number(fields.videoCount30d || 0) < Number(minimum)) return false;
    if ((from || to) && !videos.some((video) => { const date = String(video.publishedAt || "").slice(0, 10); return date && (!from || date >= from) && (!to || date <= to); })) return false;
    return true;
  });
  const {field, direction} = state.sort;
  rows.sort((left, right) => {
    const first = left.fields[field], second = right.fields[field];
    if (first == null) return second == null ? 0 : 1;
    if (second == null) return -1;
    return direction * (typeof first === "number" ? first - second : String(first).localeCompare(String(second), "zh-CN"));
  });
  return rows;
}

function videoPreview(row) {
  const videos = row.fields.recentVideos || [];
  if (!videos.length) return '<span class="muted">暂无视频</span>';
  const first = videos[0];
  const cover = safeUrl(first.coverUrl);
  const link = safeUrl(first.videoUrl);
  return `<div class="video-preview">${cover ? `<img class="video-thumb" src="${escapeHtml(cover)}" alt="${escapeHtml(first.title)}的封面" loading="lazy">` : '<span class="video-thumb"></span>'}<div class="video-info"><span class="video-title" title="${escapeHtml(first.title)}">${escapeHtml(first.title)}</span><span class="video-meta">${formatDate(first.publishedAt)} · 赞 ${formatNumber(first.likeCount)} · 藏 ${formatNumber(first.collectCount)}</span><button class="video-more" data-action="videos">查看全部 ${videos.length} 条</button></div>${link ? `<a class="play-link" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer" title="在抖音播放" aria-label="播放${escapeHtml(first.title)}">▶</a>` : ""}</div>`;
}

function renderRows() {
  const rows = filteredRows();
  $("#resultCount").textContent = `${rows.length} ${isOmniTable() ? "个 Omni 任务" : isFusionTable() ? "组搭配" : isVideoTable() ? "条视频" : "个账号"}`;
  if (isOmniTable()) {
    renderOmniRows(rows);
    return;
  }
  if (isFusionTable()) {
    renderFusionRows(rows);
    return;
  }
  if (isVideoTable()) {
    renderVideoRows(rows);
    return;
  }
  $("#rows").innerHTML = rows.length ? rows.map((row) => {
    const fields = row.fields;
    const avatar = safeUrl(fields.avatarUrl);
    const profile = safeUrl(fields.profileUrl);
    const assigned = (row.tagIds || []).map((id) => state.table.tags.find((tag) => tag.id === id)).filter(Boolean);
    const name = escapeHtml(rowName(row));
    return `<tr data-id="${escapeHtml(row.id)}"><td><div class="account-identity">${avatar ? `<img class="avatar" src="${escapeHtml(avatar)}" alt="${name}头像" loading="lazy">` : `<span class="avatar avatar-fallback">${name.slice(0, 1)}</span>`}<div>${profile ? `<a class="account-name" href="${escapeHtml(profile)}" target="_blank" rel="noopener noreferrer" title="${name}">${name}</a>` : `<strong class="account-name" title="${name}">${name}</strong>`}<span class="account-meta">${formatDate(fields.lastCrawledAt)}</span></div></div></td><td><div class="tag-list">${assigned.map((tag) => `<span class="tag" style="--tag-color:${tagColor(tag.color)}" title="${escapeHtml(tag.name)}">${escapeHtml(tag.name)}</span>`).join("")}</div><button class="tag-edit" data-action="assign" aria-label="维护${name}的多个标签">${assigned.length ? "编辑标签" : "＋ 添加标签"}</button></td><td class="num">${formatNumber(fields.followerCount)}</td><td class="num">${formatNumber(fields.videoCount30d)}</td><td class="num">${formatNumber(fields.averageLikes)}</td><td class="num">${formatNumber(fields.averageCollects)}</td><td class="num">${formatNumber(fields.averageShares)}</td><td class="num">${fields.averageLikeCollectRatio == null ? "—" : `${formatNumber(fields.averageLikeCollectRatio)}:1`}</td><td>${videoPreview(row)}</td><td><button class="score-button" data-action="review" title="评分和理由">${ratingBlocks(row.rating?.score)}</button></td><td><button class="icon-button" data-action="edit" title="编辑账号" aria-label="编辑${name}">⋯</button></td>${renderCandidateCells(row)}</tr>`;
  }).join("") : `<tr><td colspan="${11 + candidateDefinitions().length}" class="empty">没有符合条件的账号</td></tr>`;
  document.querySelectorAll("#rows tr[data-id]").forEach((line) => {
    const row = rows.find((item) => item.id === line.dataset.id);
    if (row.fields.crawlError) {
      const metadata = line.querySelector(".account-meta");
      metadata.textContent = "采集失败";
      metadata.title = row.fields.crawlError;
      metadata.classList.add("error-text");
    }
    const button = document.createElement("button");
    button.className = "mobile-video-link";
    button.dataset.action = "videos";
    button.textContent = `视频 ${row.fields.recentVideos?.length || 0} 条`;
    line.querySelector(".account-identity > div").append(button);
  });
}

function renderSceneDesign(fields) {
  const items = [
    ["构图", fields.shotComposition],
    ["布光", fields.lightingPlan],
    ["实拍动态", fields.practicalMotion],
    ["调色", fields.lookDirection],
  ];
  return `<span class="edit-scene"><b>场地：</b>${escapeHtml(fields.sceneLocation || "待设计")}</span><span class="edit-scene">${escapeHtml(fields.sceneBeat || "")}</span><details class="edit-scene-details"><summary>查看摄影设计</summary>${items.map(([label, value]) => `<p><b>${label}：</b>${escapeHtml(value || "待设计")}</p>`).join("")}</details>`;
}

function renderCandidateCell(row, definition) {
  const fields = row.fields;
  const label = definition.label || definition.name;
  const image = candidateImageUrl(fields[definition.name]);
  const selected = Array.isArray(fields.selectedCandidateImages) && fields.selectedCandidateImages.includes(definition.name);
  const promptField = definition.promptField;
  const prompt = promptField ? fields[promptField] || "" : "";
  return `<td class="prompt-cell candidate-cell${selected ? " is-selected" : ""}">${image ? `<img class="candidate-thumb" src="${escapeHtml(image)}" alt="${escapeHtml(label)}候选图" loading="lazy" title="点击放大${escapeHtml(label)}候选图"><button class="candidate-select" data-action="select-candidate" data-field="${escapeHtml(definition.name)}" aria-pressed="${selected}" aria-label="${selected ? "取消选中" : "选中"}${escapeHtml(label)}候选图">${selected ? "✓ 已选" : "○ 选中"}</button>` : '<span class="muted">待生成</span>'}${promptField ? `<details class="prompt-details"><summary>查看${escapeHtml(label)}</summary><p class="prompt-text">${escapeHtml(prompt)}</p></details><button class="button quiet prompt-copy" data-action="copy-prompt" data-field="${escapeHtml(promptField)}" aria-label="复制${escapeHtml(label)}">复制</button>` : ""}</td>`;
}

const renderCandidateCells = (row) => candidateDefinitions().map((definition) => renderCandidateCell(row, definition)).join("");

function renderOmniRows(rows) {
  const thumbnail = (value, label) => {
    const url = candidateImageUrl(value);
    return url ? `<img class="candidate-thumb" src="${escapeHtml(url)}" alt="${escapeHtml(label)}" loading="lazy" title="点击放大${escapeHtml(label)}">` : "—";
  };
  const videoLink = (value, label) => /^\/artifacts\/omni_depth\/(?:timeline_first_clip_0000_0450|jianying_clip1_t000000_004633)_(?:color|depth)\.mp4$/.test(value || "") ? `<a class="report-file-link" href="${escapeHtml(value)}" target="_blank" rel="noopener">▶ ${escapeHtml(label)}</a>` : "—";
  $("#rows").innerHTML = rows.length ? rows.map((row) => {
    const fields = row.fields;
    const result = safeUrl(fields.resultVideo);
    return `<tr data-id="${escapeHtml(row.id)}"><td><strong class="report-title">${escapeHtml(fields.beatName)}</strong><span class="edit-range">${escapeHtml(fields.beatRange)}</span><span class="report-account">按实际出拳落点换景；最后白模</span></td><td>${thumbnail(fields.referenceImageA, "场景服饰 A")}</td><td>${thumbnail(fields.referenceImageB, "场景服饰 B")}</td><td>${thumbnail(fields.referenceImageC, "场景服饰 C")}</td><td>${thumbnail(fields.whiteModelImage, "白模风格")}</td><td>${videoLink(fields.colorVideo, "彩色原片")}<br>${videoLink(fields.depthVideo, "深度灰")}</td><td class="prompt-cell"><details class="prompt-details"><summary>查看唯一提示词</summary><p class="prompt-text">${escapeHtml(fields.omniPrompt || "")}</p></details><button class="button quiet prompt-copy" data-action="copy-prompt" data-field="omniPrompt">复制提示词</button></td><td>${result ? `<a class="report-file-link" href="${escapeHtml(result)}" target="_blank" rel="noopener">▶ 查看成片</a>` : "—"}<span class="report-account">${escapeHtml(fields.generationStatus || "待提交")}</span></td></tr>`;
  }).join("") : '<tr><td colspan="8" class="empty">暂无 Omni 分镜</td></tr>';
}

function renderFusionRows(rows) {
  const thumbnail = (value, label) => {
    const url = candidateImageUrl(value);
    return url ? `<img class="candidate-thumb" src="${escapeHtml(url)}" alt="${escapeHtml(label)}" loading="lazy" title="点击放大${escapeHtml(label)}">` : '<span class="muted">待生成</span>';
  };
  $("#rows").innerHTML = rows.length ? rows.map((row) => {
    const fields = row.fields;
    return `<tr data-id="${escapeHtml(row.id)}"><td class="edit-sequence">${formatNumber(fields.sequence)}</td><td><strong class="report-title">${escapeHtml(fields.techniqueTitle || "太极拳")}</strong><span class="report-account" title="${escapeHtml(fields.title)}">${escapeHtml(fields.title || "")}</span></td><td class="prompt-cell">${thumbnail(fields.wardrobeImage, "人物服饰参考图")}<small>${escapeHtml(fields.wardrobeChoice || "")}</small><details class="prompt-details"><summary>服饰差异化</summary><p class="prompt-text">${escapeHtml(fields.wardrobeDirection || "")}</p></details></td><td class="prompt-cell">${thumbnail(fields.sceneImage, "场景空镜参考图")}<small>${escapeHtml(fields.sceneLocation || "")}</small><span class="report-account">${escapeHtml(fields.sceneChoice || "")}</span></td><td class="fusion-light"><strong>${escapeHtml(fields.timeWeather || "")}</strong><span>${escapeHtml(fields.sceneAccent || "")}</span><span>${escapeHtml(fields.lightingDirection || "")}</span><small>${escapeHtml(fields.poseDirection || "")}</small></td><td class="prompt-cell"><details class="prompt-details"><summary>查看双图提示词</summary><p class="prompt-text">${escapeHtml(fields.fusionPrompt || "")}</p></details><button class="button quiet prompt-copy" data-action="copy-prompt" data-field="fusionPrompt">复制提示词</button></td><td class="prompt-cell">${thumbnail(fields.fusionImage, "9:16人物场景融合图")}</td><td>${escapeHtml(fields.generationStatus || "待生成")}</td><td><button class="score-button" data-action="review">${ratingBlocks(row.rating?.score)}</button></td></tr>`;
  }).join("") : '<tr><td colspan="9" class="empty">暂无已选的服饰与场景搭配</td></tr>';
}

function renderVideoRows(rows) {
  if (isEditTable()) {
    $("#rows").innerHTML = rows.length ? rows.map((row) => {
      const fields = row.fields;
      const cover = safeUrl(fields.coverUrl);
      const source = safeUrl(fields.videoUrl);
      const file = /^\/media\/\d{15,22}\.mp4$/.test(fields.videoFile || "") ? fields.videoFile : "";
      const assigned = (row.tagIds || []).map((id) => state.table.tags.find((tag) => tag.id === id)).filter(Boolean);
      return `<tr data-id="${escapeHtml(row.id)}"><td class="edit-sequence">${formatNumber(fields.sequence)}</td><td>${cover ? `<img class="video-thumb" src="${escapeHtml(cover)}" alt="${escapeHtml(fields.title)}封面" loading="lazy">` : "—"}</td><td><strong class="report-title" title="${escapeHtml(fields.title)}">${escapeHtml(fields.title)}</strong><span class="report-account">${escapeHtml(fields.accountName)}</span></td><td><strong>${escapeHtml(fields.techniqueTitle || "沿用原片")}</strong><span class="edit-range">原片 ${formatNumber(fields.sourceStartSec)}s 起 · ${formatNumber(fields.clipDurationSec)}s</span><span class="edit-range">成片 ${formatNumber(fields.timelineStartSec)}s · ${escapeHtml(fields.transitionAfter || "")}</span>${renderSceneDesign(fields)}</td><td><div class="tag-list">${assigned.map((tag) => `<span class="tag">${escapeHtml(tag.name)}</span>`).join("")}</div><button class="tag-edit" data-action="assign">编辑标签</button></td><td><button class="score-button" data-action="review">${ratingBlocks(row.rating?.score)}</button></td><td class="num">${formatNumber(fields.likeCount)}</td><td class="edit-interactions">藏 ${formatNumber(fields.collectCount)}<br>转 ${formatNumber(fields.shareCount)}<br>评 ${formatNumber(fields.commentCount)}</td><td>${formatDate(fields.publishedAt)}</td><td>${file ? `<button class="button video-file-button" data-action="play-file">▶ 播放文件</button><a class="report-file-link" href="${file}" download="${escapeHtml(fields.awemeId)}.mp4">下载 MP4</a>` : "—"}</td><td>${source ? `<a class="report-file-link" href="${escapeHtml(source)}" target="_blank" rel="noopener noreferrer">抖音原视频 ↗</a>` : "—"}</td>${renderCandidateCells(row)}</tr>`;
    }).join("") : `<tr><td colspan="${11 + candidateDefinitions().length}" class="empty">暂无剪辑片段</td></tr>`;
    return;
  }
  $("#rows").innerHTML = rows.length ? rows.map((row) => {
    const fields = row.fields;
    const cover = safeUrl(fields.coverUrl);
    const source = safeUrl(fields.videoUrl);
    const file = /^\/media\/\d{15,22}\.mp4$/.test(fields.videoFile || "") ? fields.videoFile : "";
    const assigned = (row.tagIds || []).map((id) => state.table.tags.find((tag) => tag.id === id)).filter(Boolean);
    const needsReview = !assigned.length || assigned.some((tag) => tag.name === "未分类");
    return `<tr data-id="${escapeHtml(row.id)}"><td>${cover ? `<img class="video-thumb" src="${escapeHtml(cover)}" alt="${escapeHtml(fields.title)}封面" loading="lazy">` : "—"}</td><td><strong class="report-title" title="${escapeHtml(fields.title)}">${escapeHtml(fields.title)}</strong><span class="report-account">${escapeHtml(fields.accountName)}</span></td><td><div class="tag-list">${assigned.map((tag) => `<span class="tag">${escapeHtml(tag.name)}</span>`).join("")}</div><button class="tag-edit" data-action="assign" aria-label="维护${escapeHtml(fields.title)}的视频标签">${assigned.length ? "编辑标签" : "＋ 添加标签"}</button>${needsReview ? `<span class="report-note" title="${escapeHtml(fields.classificationNote)}">待人工复核</span>` : ""}</td><td class="num">${formatNumber(fields.likeCount)}</td><td><button class="score-button" data-action="review" aria-label="给${escapeHtml(fields.title)}打分" title="${escapeHtml(row.rating?.note || "评分和理由")}">${ratingBlocks(row.rating?.score)}</button></td><td class="num">${formatNumber(fields.likeRatio)}×</td><td class="num">${formatNumber(fields.collectCount)}</td><td class="num">${formatNumber(fields.shareCount)}</td><td class="num">${formatNumber(fields.commentCount)}</td><td class="num">${formatNumber(fields.playCount)}</td><td>${formatDate(fields.publishedAt)}</td><td>${file ? `<button class="button video-file-button" data-action="play-file">▶ 播放文件</button><a class="report-file-link" href="${file}" download="${escapeHtml(fields.awemeId)}.mp4">下载 MP4</a>` : '<span class="muted">文件获取中/不可用</span>'}</td><td>${source ? `<a class="report-file-link" href="${escapeHtml(source)}" target="_blank" rel="noopener noreferrer">抖音原视频 ↗</a>` : "—"}</td>${renderCandidateCells(row)}</tr>`;
  }).join("") : `<tr><td colspan="${13 + candidateDefinitions().length}" class="empty">没有符合条件的视频</td></tr>`;
}

async function refreshTable() {
  if (!state.selected) return;
  state.table = await api(`/api/table?id=${encodeURIComponent(state.selected.table.id)}`);
  cacheTable(state.table);
  renderTagFilter(); renderMetrics(); renderRows();
  notify("已保存");
}

function openVideos(row) {
  $("#videosTitle").textContent = rowName(row);
  const videos = row.fields.recentVideos || [];
  $("#videosList").innerHTML = videos.map((video) => {
    const cover = safeUrl(video.coverUrl), link = safeUrl(video.videoUrl);
    const stats = [["播放", video.playCount], ["点赞", video.likeCount], ["收藏", video.collectCount], ["转发", video.shareCount], ["评论", video.commentCount]];
    return `<div class="video-detail">${cover ? `<img class="video-thumb" src="${escapeHtml(cover)}" alt="${escapeHtml(video.title)}的封面" loading="lazy">` : '<span class="video-thumb"></span>'}<div><strong>${escapeHtml(video.title)}</strong><small>${formatDate(video.publishedAt)}</small><div class="stats">${stats.map(([label, value]) => `<span>${label} ${formatNumber(value)}</span>`).join("")}</div></div>${link ? `<a class="play-link" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer" title="在抖音播放" aria-label="播放${escapeHtml(video.title)}">▶</a>` : ""}</div>`;
  }).join("") || '<div class="empty">暂无视频</div>';
  $("#videosDialog").showModal();
}

function openImage(image) {
  $("#largeImage").src = image.src;
  $("#largeImage").alt = image.alt;
  $("#imageTitle").textContent = image.alt || "图片预览";
  $("#imageDialog").showModal();
}

function openVideoFile(row) {
  const file = row.fields.videoFile;
  if (!/^\/media\/\d{15,22}\.mp4$/.test(file || "")) return;
  $("#videoFileTitle").textContent = row.fields.title;
  const player = $("#videoFilePlayer");
  player.src = file;
  player.poster = safeUrl(row.fields.coverUrl);
  $("#videoFileDialog").showModal();
}

function renderTagManager() {
  $("#tagsList").innerHTML = state.table.tags.map((tag) => `<div class="tag-manager-row" data-id="${escapeHtml(tag.id)}"><input type="color" value="${escapeHtml(tag.color || "#2d7d69")}" aria-label="${escapeHtml(tag.name)}颜色"><input type="text" value="${escapeHtml(tag.name)}" aria-label="标签名称"><button data-action="save" title="保存标签">保存</button><button class="danger-text" data-action="delete" title="删除标签">删除</button></div>`).join("") || '<p class="muted">还没有标签</p>';
}

function openAssignment(row) {
  state.row = row;
  $("#assignTitle").textContent = `${rowName(row)} · 标签`;
  renderAssignment(new Set(row.tagIds || []));
  $("#assignDialog").showModal();
}

function renderAssignment(selected) {
  $("#assignList").innerHTML = state.table.tags.map((tag) => `<label class="assign-row"><input type="checkbox" value="${escapeHtml(tag.id)}" ${selected.has(tag.id) ? "checked" : ""}><span class="color-swatch" style="background:${/^#[0-9a-fA-F]{6}$/.test(tag.color || "") ? tag.color : "#2d7d69"}"></span><span>${escapeHtml(tag.name)}</span></label>`).join("") || '<p class="muted">还没有标签，可在下方新建。</p>';
  $("#assignmentCount").textContent = `已选 ${$("#assignList").querySelectorAll("input:checked").length} 个`;
}

function openReview(row) {
  state.row = row;
  $("#reviewTitle").textContent = `${rowName(row)} · 评分`;
  $("#scoreInput").value = row.rating?.score ?? "";
  $("#scoreNote").value = row.rating?.note || "";
  $("#reviewDialog").showModal();
}

function openRow(row = null) {
  state.row = row;
  $("#rowDialogTitle").textContent = row ? "编辑账号" : "添加账号";
  $("#deleteRow").hidden = !row;
  const form = $("#rowForm");
  form.reset();
  for (const name of ["accountName", "profileUrl", "avatarUrl", "followerCount"]) form.elements[name].value = row?.fields[name] ?? "";
  $("#rowDialog").showModal();
}

function openEntity(level, mode, item, parents) {
  state.entity = {level, mode, item, parents};
  const label = {knowledge_base: "知识库", project: "项目", table: "表"}[level];
  $("#entityTitle").textContent = `${mode === "create" ? "新建" : "维护"}${label}`;
  $("#entityForm").elements.name.value = item?.name || "";
  $("#entityForm").elements.description.value = item?.description || "";
  $("#deleteEntity").hidden = mode === "create";
  $("#entityDialog").showModal();
}

function entityArgs() {
  const {level, parents} = state.entity;
  return {level, knowledgeBaseId: parents.base?.id, projectId: parents.project?.id};
}

document.addEventListener("DOMContentLoaded", () => {
  openCatalog();
  $("#openSidebar").onclick = () => { $("#sidebar").classList.add("open"); $("#scrim").classList.add("open"); };
  $("#closeSidebar").onclick = $("#scrim").onclick = () => { $("#sidebar").classList.remove("open"); $("#scrim").classList.remove("open"); };
  document.querySelectorAll(".close-modal").forEach((button) => button.onclick = () => button.closest("dialog").close());
  for (const selector of ["#searchInput", "#tagFilter", "#minVideos", "#dateFrom", "#dateTo"]) $(selector).addEventListener("input", renderRows);
  $("#clearFilters").onclick = () => { for (const selector of ["#searchInput", "#tagFilter", "#minVideos", "#dateFrom", "#dateTo"]) $(selector).value = ""; renderRows(); };
  $("#tableHead").onclick = (event) => { const button = event.target.closest("button[data-sort]"); if (!button) return; const field = button.dataset.sort; state.sort = {field, direction: state.sort.field === field ? -state.sort.direction : -1}; renderRows(); };
  $("#rows").onclick = async (event) => {
    if (event.target.matches("img.avatar,img.video-thumb,img.candidate-thumb")) return openImage(event.target);
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const row = state.table.rows.find((item) => item.id === button.closest("tr").dataset.id);
    if (button.dataset.action === "copy-prompt") {
      navigator.clipboard.writeText(row.fields[button.dataset.field] || "").then(() => notify("提示词已复制")).catch(() => notify("复制失败，请展开后手动复制", true));
      return;
    }
    if (button.dataset.action === "select-candidate") {
      const field = button.dataset.field;
      const valid = new Set(candidateDefinitions().map((definition) => definition.name));
      const selected = new Set((row.fields.selectedCandidateImages || []).filter((name) => valid.has(name) && row.fields[name]));
      if (selected.has(field)) selected.delete(field);
      else selected.add(field);
      button.disabled = true;
      try {
        await api("/api/candidates", {tableId: state.table.id, rowId: row.id, imageFields: [...selected]});
        await refreshTable();
        notify("候选图片选择已保存");
      } catch (error) {
        button.disabled = false;
        notify(error.message, true);
      }
      return;
    }
    if (button.dataset.action === "videos") openVideos(row);
    if (button.dataset.action === "assign") openAssignment(row);
    if (button.dataset.action === "review") openReview(row);
    if (button.dataset.action === "edit") openRow(row);
    if (button.dataset.action === "play-file") openVideoFile(row);
  };
  $("#videoFileDialog").addEventListener("close", () => { const player = $("#videoFilePlayer"); player.pause(); player.removeAttribute("src"); player.load(); });
  $("#videosList").onclick = (event) => { if (event.target.matches("img.video-thumb")) openImage(event.target); };
  $("#manageTags").onclick = () => { if (!state.table) return; renderTagManager(); $("#tagsDialog").showModal(); };
  $("#addTagForm").onsubmit = async (event) => { event.preventDefault(); const form = event.target; try { await api("/api/tags", {tableId: state.table.id, action: "create", name: form.elements.name.value, color: form.elements.color.value}); form.reset(); await refreshTable(); renderTagManager(); } catch (error) { notify(error.message, true); } };
  $("#tagsList").onclick = async (event) => { const button = event.target.closest("button[data-action]"); if (!button) return; const line = button.closest(".tag-manager-row"); const action = button.dataset.action; if (action === "delete" && !confirm("删除此标签，并从所有账号移除？")) return; try { await api("/api/tags", {tableId: state.table.id, action: action === "save" ? "rename" : "delete", tagId: line.dataset.id, name: line.querySelector('input[type="text"]').value, color: line.querySelector('input[type="color"]').value}); await refreshTable(); renderTagManager(); } catch (error) { notify(error.message, true); } };
  $("#assignList").onchange = () => { $("#assignmentCount").textContent = `已选 ${$("#assignList").querySelectorAll("input:checked").length} 个`; };
  $("#quickAddTagForm").onsubmit = async (event) => { event.preventDefault(); const form = event.target; const selected = new Set([...$("#assignList").querySelectorAll("input:checked")].map((input) => input.value)); try { const tag = await api("/api/tags", {tableId: state.table.id, action: "create", name: form.elements.name.value}); selected.add(tag.id); form.reset(); await refreshTable(); renderAssignment(selected); } catch (error) { notify(error.message, true); } };
  $("#saveAssignment").onclick = async () => { try { await api("/api/review", {tableId: state.table.id, rowId: state.row.id, tagIds: [...$("#assignList").querySelectorAll("input:checked")].map((input) => input.value)}); $("#assignDialog").close(); await refreshTable(); } catch (error) { notify(error.message, true); } };
  $("#saveReview").onclick = async () => { try { await api("/api/review", {tableId: state.table.id, rowId: state.row.id, score: $("#scoreInput").value ? Number($("#scoreInput").value) : null, note: $("#scoreNote").value}); $("#reviewDialog").close(); await refreshTable(); } catch (error) { notify(error.message, true); } };
  $("#addRowButton").onclick = () => state.table && openRow();
  $("#rowForm").onsubmit = async (event) => { event.preventDefault(); const form = event.target; const fields = {accountName: form.elements.accountName.value.trim(), profileUrl: form.elements.profileUrl.value.trim() || null, avatarUrl: form.elements.avatarUrl.value.trim() || null, followerCount: form.elements.followerCount.value ? Number(form.elements.followerCount.value) : null}; if (!state.row) fields.secUid = `manual:${crypto.randomUUID()}`; try { await api("/api/row", {tableId: state.table.id, action: state.row ? "update" : "create", rowId: state.row?.id, fields}); $("#rowDialog").close(); await refreshTable(); } catch (error) { notify(error.message, true); } };
  $("#deleteRow").onclick = async () => { if (!confirm(`删除账号“${rowName(state.row)}”？`)) return; try { await api("/api/row", {tableId: state.table.id, action: "delete", rowId: state.row.id}); $("#rowDialog").close(); await refreshTable(); } catch (error) { notify(error.message, true); } };
  $("#addBase").onclick = () => openEntity("knowledge_base", "create", null, {});
  $("#entityForm").onsubmit = async (event) => { event.preventDefault(); const form = event.target, {mode, item} = state.entity; try { const result = await api("/api/workspace", {...entityArgs(), action: mode === "create" ? "create" : "rename", id: item?.id, name: form.elements.name.value.trim(), description: form.elements.description.value.trim()}); $("#entityDialog").close(); await loadCatalog(state.entity.level === "table" ? result.id : state.selected?.table.id); notify("已保存"); } catch (error) { notify(error.message, true); } };
  $("#deleteEntity").onclick = async () => { const {item, level} = state.entity; if (!confirm(`删除“${item.name}”及其中全部内容？此操作无法撤销。`)) return; try { await api("/api/workspace", {...entityArgs(), action: "delete", id: item.id, cascade: true}); $("#entityDialog").close(); state.selected = null; await loadCatalog(); notify("已删除"); } catch (error) { notify(error.message, true); } };
  $("#syncButton").onclick = async () => { const button = $("#syncButton"); button.disabled = true; try { const result = await api("/api/sync", {}); await loadCatalog(result.tableId); notify(`本地数据已同步：新增 ${result.added}，更新 ${result.updated}`); } catch (error) { notify(error.message, true); } finally { button.disabled = false; } };
  $("#exportButton").onclick = () => { if (!state.table) return; const blob = new Blob([JSON.stringify(state.table, null, 2)], {type: "application/json"}); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = "review-state.json"; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); };
  $("#importButton").onclick = () => state.table && $("#importFile").click();
  $("#importFile").onchange = async (event) => { const file = event.target.files[0]; if (!file || !confirm("导入将替换本表所有账号行，继续吗？")) return; try { const data = JSON.parse(await file.text()); const result = await api("/api/import", {tableId: state.table.id, data}); await refreshTable(); notify(`已导入 ${result.imported} 行`); } catch (error) { notify(error.message, true); } finally { event.target.value = ""; } };
});
