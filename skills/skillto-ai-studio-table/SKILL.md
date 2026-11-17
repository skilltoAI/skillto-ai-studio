---
name: skillto-ai-studio-table
description: Build and maintain local or AMD-PAD remote multimedia tables organized by knowledge base and project, with shared report storage, human review pages and authenticated semantic MCP operations for AI.
---

# Skillto-AI-Studio · 表格工作台

Child capability of [`skillto-ai-studio`](../skillto-ai-studio/SKILL.md). Canonical skill name and directory: `skillto-ai-studio-table`; skill-picker display name: **Skillto-AI-Studio · 表格工作台**. The parent routes Studio/workbench/table requests here; sibling skills own reports, rewrites and video breakdown behavior.

Product display names: **Skillto-AI-Studio** / **Skillto-AI-Studio**. Keep `skillto-ai-studio-table` as the compatible skill, directory and MCP identifier.

Before changing the UI, adding modules or developing new capabilities, read [技术规范.md](技术规范.md). It records the existing architecture, data-driven extension rules, shared visual and interaction contracts, branding and acceptance criteria. Ordinary content additions must use existing schemas and semantic operations rather than table-specific frontend code. The design direction is white with black/gray/green, top-level modules in the header, and the supplied horizontal logo with the subtitle **个人工作台**. The selected Codex-like minimal UI is implemented by the shared studio-theme.css and studio-shell.js: 14px document titles, near-white gray surfaces, regular-weight navigation, and green confined to the wordmark. Keep all module APIs and real media colors intact.

Turn a user's business or product data-maintenance request into a usable local or remote review workspace. The hierarchy is **knowledge base > project > table**. People navigate and edit it in the browser; AI uses the bundled MCP tools for ordinary data operations. Read [the data contract](references/schema.md) when creating or converting data, and [the semantic mapping guide](references/semantic-workflow.md) when translating a business request.

## Existing capability

Preserve the former multimedia review-table behavior: import JSON arrays or objects with `rows`, preserve unknown fields, edit text and numbers with append-only row history, search and filter, score 1-5 with rationale, preview images and videos on hover and in a dialog, add/remove/replace media, autosave to project JSON, and export/import JSON with history. A static gallery or browser storage alone is insufficient.

For every `video` field in the table, show a small video window in the cell by default. On pointer hover or keyboard focus, show a medium-sized playing preview; clicking the cell opens a full-screen player with controls. Keep touch devices able to open the full-screen player with a tap. Stop and release preview playback when hover/focus ends, the table rerenders, or the player closes. Use a related poster/cover image when available, and keep the interaction in the common table component rather than coding it for one table ID.

## Workspace and navigation

- The **Motion 模版** section is owned by sibling `skillto-ai-studio-motion`: public .motion collection, inspection, local paths, tags/ratings and supported production tasks. It shares Studio navigation and the loopback service at `/api/motions/*`, with independent SQLite/runtime storage under `SKILLTO_TABLE_ROOT/motions/`. Use its semantic CLI for AI operations, not table row MCP. Source run counts are independent from personal scores. Wait for or explicitly cancel owned production tasks before restart.
- The local 8880 workspace includes a **洗稿** section with a knowledge base > project > manuscript tree, V0 source transcript and versioned rewrite editor with automatically saved per-version Prompts, per-line timing estimates, and fixed-profile 小与 AI voice generation, eight analysis areas with human ratings, cross-platform references, and a second-creation draft. Use `skillto-ai-studio-rewrite` for that section's research and CRUD workflow. The top navigation includes 表格 / 报表 / 拉片 / 洗稿 / 文档 / 排稿 / 工具.
- Show a persistent three-level navigation tree: knowledge bases, their projects, and each project's tables. Support create, rename, and delete at each level. Require confirmation before deletion; deleting a nonempty parent must explicitly name its descendants. Keep stable IDs when names change.
- Breadcrumbs and the selected table must stay in sync with the tree. Show an empty state with a create action at each level. Keep navigation usable on narrow screens.
- Each table owns its fields, rows, media, ratings, history, and tag definitions. Never share tag definitions implicitly between tables. Support tag create, rename, and delete in that table's page, plus assign/remove on each row. Renaming a tag must preserve row assignments; deletion removes those assignments and records history.
- Every row must expose an obvious **edit tags** action in its table cell, including when no tags exist yet. Open a multi-select control showing all of this table's tags and the row's current selection; let a person check several, uncheck to remove, create a new table tag without leaving the row, then save the complete selection with immediate disk persistence and visible feedback. Keep tags separate from ratings. Show assigned tag names in the row, and make the action usable by keyboard and on mobile. Never replace a row's other fields when changing tags.
- Provide field filters appropriate to the column type, including date ranges, plus text search, score status/range, and tag filters. Combine filters predictably, show active filters, and offer clear/reset.
- Support `short_video_info` as a compact table cell containing recent videos. Show cover, title, publish date, available interaction metrics, and a play icon linking to the original video page. Keep row height stable and reveal the full list on demand. Read [the schema](references/schema.md) for its data contract.
- For image comparison, mark image fields as candidates with a `candidateGroup` and optional `promptField`. Show a separate keyboard-accessible **select / selected** control beside each populated candidate image, without replacing the image-preview action. Let a person select multiple images in one row, including multiple images from the same group, and click again to remove a choice. Save the complete selection to the table immediately, make selected cells visually distinct, and expose the choice through the semantic MCP tool. Never infer a human choice from a score or tag, and never carry a choice onto a regenerated replacement image.
- Use the user's existing dataset as the default. Convert CSV columns into fields, retaining original image/video URLs while also making media entries. Preserve unknown input columns.

## Automatic Field Controls

These are built-in program responsibilities for every existing and newly generated table, not per-table AI work. Creating a table should require only field definitions and rows; never ask AI to add individual filter controls or hand-code visible columns.

- Build filter controls from every declared field's type. Retain undeclared imported fields and make them available too; infer a conservative type until explicitly defined.
- Numbers: optional minimum/maximum inputs with inclusive boundaries and decimal support. Dates: optional start/end date pickers. Text: substring search. Single/multiple choice: option selection (membership for an array). Boolean: all/yes/no. Image, video, and short video lists: all/has media/no media, rather than matching URLs.
- Combine active field filters, text search, and table-local tag filters with AND. Blank bounds are unrestricted; null/missing values never become numeric zero. Reject inverted ranges with a visible message. Show active-filter and result counts and provide one clear-all action. Hidden columns remain filterable.
- Provide a **显示字段** control listing all fields with checkboxes, select-all, and restore-default actions. A user decides which columns to display without changing the stored schema, rows, media, or export data. Keep choices scoped by stable table ID and retain them after reload. Browser-local view preferences are acceptable, but must not be described as shared table data.
- Adding fields, importing a schema, refreshing, and switching tables must rebuild available controls automatically without leaking another table's filters or column choices.
- Reuse the bundled `assets/schema-controls.js` and `assets/schema-controls.css` for the existing local review page; load them after the base page script/styles. This adapter uses the page's `state`, semantic API, render, media, and tag handlers. Other frontends must implement the same contract in their common table component, not copy table-ID-specific code.
- Verify numeric/date boundaries, choices, boolean and media presence, filter combination/reset, column hide/show persistence, independent table preferences, and a newly created table requiring no custom controls.

## Business request workflow

First identify the user's entities, relationships, fields, row identity, and desired CRUD actions in their own terminology. Choose field types and controls (text, number, date, boolean, image, video, single choice, multiple choice, or short video information), then map requested search, field filters, date ranges, ratings, and tags to concrete table interactions. Ask only when an ambiguity would change the data model or risk data loss. Expose business nouns and actions in the page; keep IDs, JSON paths, scripts, and protocol details out of user-facing controls.

For AI operations, use the bundled `skillto-ai-studio-table` MCP server and its semantic tools. The server owns storage, IDs, history, validation, and query mechanics; agents should not edit the JSON directly for routine CRUD. Use direct file conversion only for bulk import/migration, then validate through MCP. See [MCP usage](references/mcp.md). If MCP is unavailable in the current client, launch/register it or report that limitation explicitly; do not claim the semantic wrapper is active.

## Account Benchmark Tag Standard

For the account table `56fa8754-8d40-4225-8541-0be4729ade73`, assign the table-local tag **AI教学赛道对标账号** when all three conditions hold:

- `averageLikeCollectRatio < 6` (the table's average likes-to-collections ratio).
- `averageCollects > 200` (average collections per video).
- `videoCount30d > 4` (at least five videos in the recent 30-day collection window).

Use strict inequalities: values equal to 6, 200, or 4 do not qualify. Missing or nonnumeric values do not qualify. Use the account's stored recent-30-day statistics, and retain the collection timestamp when reporting results. This is a numeric benchmark selection rule; do not add an LLM-category condition unless the user requests it. It does not independently verify that the account teaches AI.

Create or reuse the tag by exact name within this table. Query the qualifying rows through `table_query`, then apply strict boundary checks before writing. Append the tag using `table_review`, preserving each row's existing tags, ratings, fields, media, and history. Repeated application must not create duplicate tags or assignments. On later refreshes, recalculate qualification from refreshed recent-30-day statistics; do not silently remove previously assigned benchmark tags unless the user requests synchronization/removal.

## Persistence and verification

### Local and AMD-PAD targets

- Before operating AMD-PAD reports, read [AMD-PAD synchronization and CRUD](references/amd-pad.md). It includes target selection, key configuration, semantic tool examples, media upload, explicit copy/import procedures, verification, and concrete report URLs.
- Local mode: run `scripts/server.py` with `SKILLTO_TABLE_ROOT`. Existing local reports remain independent and are never deleted during remote migration.
- Remote mode: the **canonical credential environment variable is `SKILLTO_TABLE_API_KEY_FILE`**. Its value is the absolute path of a protected runtime file containing the Bearer API Key; the key itself is not stored in the skill or repository. Set `SKILLTO_TABLE_API_URL=http://192.168.3.188:5173/api/report-tables/mcp`. If a user provides a new key, first validate it with authenticated `GET /api/report-tables/catalog`, save it outside the repository in the current user's protected application-data directory, then set `SKILLTO_TABLE_API_KEY_FILE` to that absolute file path. On Windows, persist the path in the user environment and also pass it explicitly to the current process because an already-running Codex process may not inherit a new user variable. Do not print the key or include it in commands, logs, URLs, or generated files. The same stdio entry delegates to `scripts/remote_client.py`, an authenticated Streamable HTTP MCP client. Remote errors must not fall back to local writes.
- The skill knows the credential **variable name and lookup procedure**, not a secret value. Before each remote write, verify that `SKILLTO_TABLE_API_KEY_FILE` resolves to a readable file and that the key has `reports:write` access; read-only operations require `reports:read`. If no valid key is available, check the configured runtime path or ask for one; do not assume the skill text contains a key.
- AMD-PAD display is integrated into videoDeepInsight at `/report-tables`, not a second port-8765 service. Keys are managed at `/settings/api-keys`; only store hashes server-side and never put real keys in skill files or URLs.
- Remote storage is the shared `data/report_tables/` workspace: all authenticated collaborators see the same reports. Key ownership is only for key management, not report isolation. A read-only Key cannot mutate reports or media.
- Local and remote copies have stable IDs but no automatic synchronization. Explicitly identify the selected target before CRUD. Do not modify other tasks' MCP configuration.
- For AMD-PAD operations, query and mutate the remote workspace through its MCP/REST interfaces; editing the local 8765 table does not update AMD-PAD. "Refresh" rereads the selected workspace, not synchronization between machines. Do not describe the existing initial-copy script as an incremental merge tool.
- Share AMD-PAD links as `http://192.168.3.188:5173/report-tables?table=<tableId>`, not the bare workspace URL. The report workspace fills the viewport; selection updates the outer URL and reload/back/forward restores that report. Browser login is still required; never include credentials in a link.
- Follow the project's `技术规范.md` and `docs/多媒体报表与MCP技术规范.md` for backups, deployment, authentication and migration. Missing local media must be reported rather than replaced with broken host paths.

Use the same workspace data contract for the page and MCP. With a local page server, autosave edits to the project-side table JSON after every change. Label whether the last save reached disk or only browser recovery storage. Export/import a portable JSON copy. Keep row and table histories append-only, including deleted row snapshots. Use accessible URLs/paths for local media unless a self-contained export is requested.

Before handoff, verify three-level navigation, one field edit, date or field filtering, tag CRUD, creating a tag from a row, assigning at least two tags to one row and removing one without losing the other, scoring, media preview, selecting and unselecting multiple candidate images, export/import history, and an MCP query that sees a browser-side change. Give the page entrypoint and data location.

## Local Metabase reports

The local 8880 workspace includes a **报表** section with a knowledge base > project > report tree. Its implementation is in `reporting/serve_local.py`, `scripts/report_system.py`, and the `assets/report-system.*` and `assets/workspace-nav.*` files. Metabase runs separately on local port 3330; reports use a PostgreSQL query database derived from the source table JSON. For report and chart CRUD, use the separate `skillto-ai-studio-reports` skill and the 8880 report API. Do not write the report registry or Metabase application database directly.

The `reporting/` scripts provision Metabase, collect the frozen 2026-11-07 teaching-account roster, sync report data, publish two dashboards, and back up both databases and the source files. Collection and refresh are explicit operations; the table JSON and AMD-PAD workspace are not automatically updated.

## Windows local launcher (Go)

Local Chrome browser users: the EXE's **浏览器用户** button opens `/browser-users` for username CRUD and launch/close. Each stable user ID owns an independent persistent Chrome directory and cookies, separate from software users. Local only; never sync these profiles to AMD-PAD. Use `browser_profiles` and `browser_action` MCP tools for AI browser operations via the running local launcher service. Read [browser users and MCP](references/browser-users.md) for setup, actions, storage and deletion recovery.

For a local Windows workspace, double-click **SkillToTable.exe** in this skill or **启动本地报表.exe** on the desktop. It starts the configured loopback HTTP service on **127.0.0.1:8880**, waits for readiness, and opens the default browser. It stays in the Windows taskbar with Start service, Stop service and Open report buttons. Minimizing keeps the service running; closing the controller window gracefully stops the service and exits. Repeated launches focus the existing controller and reuse the healthy service. The EXE is a Go launcher for the existing Python service; its machine paths live in `launcher.local.json`. Read [Windows launcher setup, build, logs and verification](references/windows-launcher.md) before rebuilding, relocating dependencies or diagnosing startup. The stdio MCP entry `scripts/server.py` is not the HTTP page server.

## Local video breakdown workspace

Use the sibling `skillto-ai-studio-workbench` for the Skillto-AI-Studio Chrome popup, authorized MP4/HLS/DASH video downloads and the independent `/breakdowns` page. The top navigation includes 拉片; the page has searchable records at left and video, source, notes, timestamped shots and revision history at right. It uses a separate SQLite store and media directory under `SKILLTO_TABLE_ROOT/workbench/`, not table rows or AMD-PAD storage. Its `WorkbenchMixin` is loaded from the sibling directory by `reporting/serve_local.py`; restart an idle service after installing. Download and note operations use its own REST interface, not this table MCP. The plugin automatically pairs through the same local workspace; do not ask users to configure ports or copy connection codes. The Cat Catch client syncs selected media bytes directly to this service using authenticated, ordered chunks, without depending on Chrome download paths; processing completion opens/focuses its breakdown record and reuses an existing workspace tab. Read that child’s installation reference for deploying/updating the Chrome extension, built-in installation guidance and runtime dependencies.

## 稿件内分析 Tab

每篇稿件顶部提供「文案版本」「原文亮点」「原视效亮点」「前12秒分镜」「12分镜表」「motion分镜表」六步导航；切换前保存待写入的版本和分析，失败保留草稿并阻止切换。支持方向键、Home/End、窄屏表格横向滚动。当前 Tab 是按稿件隔离的浏览器视图偏好，可用 `rewriteTab` URL 参数直接定位。已有稿件读取时补齐空分析，新稿件直接提供相同入口，不需要为单篇定制页面。

分析属于稿件，不属于某个口播版本，不能进入配音或逐字稿。字段 `manuscriptAnalysis`、`keyframeAnalysis` 均为 `{"text":"","revision":0,"updatedAt":""}`，正文支持安全子集 Markdown（标题、段落、列表、表格、HTTP(S)及既有素材链接；不执行 HTML）。人工通过「编辑分析」「保存分析」修改；切换前也会保存，状态明确区分未保存、保存中、已保存到磁盘与失败。刷新前若有未保存修改会提示。

AI 通过 `POST /api/rewrites` 的 `save_analysis` 动作写入：`id` 为稿件ID，`analysisKey` 为上述二者之一，`text` 为正文（最多100000字符），`expectedRevision` 为刚读取的整数修订号。修订冲突拒绝覆盖，写入追加历史；一般 `update` 保留服务端现有分析，旧表单不得擦除它。保存分析不改变V0、改写版本、Prompt、行标签、配音或人评。

文稿分析按指标分别写原句/时间、写法、心智与情绪机制、局限；不得把可见互动数当作完播率或互动率的分母。关键帧分析先审看3×3拼图，再以表格记录画面事实、设计优点、可能机制、不足和改进；提供拼图格位与可靠时间，采样记录不一致时保留说明，不把静帧推测成已确认的连续动画。

验收覆盖隔离数据的旧稿补齐、两分析独立保存、刷新恢复、修订冲突、一般表单保护、历史、HTML注入转义、版本编辑切换落盘、保存失败保留、键盘与手机宽度。原八项分析与人工五心评分继续保留。

## 洗稿步骤与分镜审阅

稿件顶部使用六步图标导航：文案版本 → 原文亮点 → 原视效亮点 → 前12秒分镜 → 12分镜表 → motion分镜表。沿用 rewriteTab 的旧 script/manuscriptAnalysis/keyframeAnalysis 标识；新增 openingStoryboard/fullStoryboard。黑灰为主、当前步骤深石墨绿，连线浅灰；不引入旧版 Ant Design 运行依赖。原稿信息折叠进标题旁 ⓘ，支持悬浮、聚焦、点击及 Escape。

两种分镜均属于稿件，以 {rows,revision,updatedAt} 保存。每行 id/title/time/narration/description/animation/prompt/feedback/frames；frames 最多4项 {url,label}，只接受 HTTP(S) 或 /assets/ 素材地址。空 feedback 表示暂时不用修改，不自动写成“通过”。12秒是模块名称，已有约10秒设计不自动伸长。AI 用 POST /api/rewrites 的 save_storyboard，传 id/storyboardKey/rows/expectedRevision；保存冲突不得覆盖。旧稿自动补空，不进入逐字稿或配音。原有八项分析、人评和版本保留。修改、添加、删除分镜后显式保存或切换步骤前保存，失败留草稿；刷新未保存提示。通用编辑 UI 不绑定稿件ID。

## 前12秒分镜版本

显示名改为“前12秒分镜”，openingStoryboard URL/机器标识保持兼容。保留原 rows/revision/updatedAt 并增加 versions 与 activeVersionId；首次读取旧数据建立 V1 原方案，逐行人工意见与图均原样保留。每个版本独立保存 rows/revision/createdAt/updatedAt/id/label，顶层 rows 为当前版兼容视图，顶层 revision 用作全局并发保护。新增版本复制当前版（含意见），切换前先保存，失败保留草稿并阻止切换，支持重命名。上限30版，所有操作记录历史。POST /api/rewrites 新增 create_storyboard_version / select_storyboard_version / rename_storyboard_version，必传 id/expectedRevision；创建可传 label/baseVersionId，切换和改名传 versionId，改名还传 label。save_storyboard 可传 versionId，拒绝与当前版本不符；旧客户端的 expectedRevision 同样防止跨版本误覆盖。不改变文案版本、原亮点分析和完整分镜表。

美术约束：纯矿物白底、黑灰少量锈红；可独立拆分的3D白模图例、3D线稿和矢量信息图，不用大面积写实云海或全景。小幅IP图片可作为明确边界的独立图像层。PNG是审阅快照，SVG源文件的分组才是本次可拆解图层；不得把2.5D矢量图例宣称为已交付三维网格模型。


## motion分镜表与统一版本按钮

洗稿增加 `rewriteTab=motionStoryboard`，表示稿件全片分镜的表格版本；与前12秒分镜、既有12分镜表及口播版本独立。「前12秒分镜」和motion采用与文案一致的横向V1/V2按钮，保留原版本ID和自定义名，不伪造分镜V0。切换持久化、失败阻止切换；旧稿无损补空模块。

motionStoryboard只持有带修订号的表格版本引用；正文使用原通用表格组件，以同源 `rewriteEmbed=1` 内嵌并隐藏重复导航。只在选中步骤时载入，离开释放媒体；未完成编辑、正在保存或保存失败时阻止切换。原表关联为首版；新增版本在同项目复制整表到新ID，保留schema、未知字段、媒体、评分、标签和历史，独立编辑。复制和表格CRUD共享存储锁，登记失败回滚本次新表，不动原表。服务将当前表格store注入rewrite模块，不新增硬编码安装路径。

API为 `link_motion_storyboard` / `create_motion_storyboard_version` / `select_motion_storyboard_version` / `rename_motion_storyboard_version`，均携带id和expectedRevision；详细参数、人工评分与制作边界见 [洗稿技能](../skillto-ai-studio-rewrite/SKILL.md#分镜步骤与版本管理)。此关联不执行生成、渲染或发布。验收需验证版本隔离、刷新恢复、失败草稿保护和原表数据不变。
