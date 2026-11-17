---
name: skillto-int-rewrite
description: Research source posts or videos, analyze manuscript rhetoric and video keyframes, and maintain source-backed second-creation drafts and versioned storyboards in the local 洗稿 workspace with human five-heart review.
---

# 洗稿与二创

Use this skill when a user asks to add, inspect, revise, or remove a manuscript in the local **洗稿** module, or asks for manuscript/traffic-mechanism analysis, video keyframe analysis, or a source-backed second-creation draft. The module lives in the Skill To Table workspace at `http://127.0.0.1:8880/?section=rewrites`. Its left tree is **知识库 > 项目 > 稿件**, and manuscripts are ordered by creation time, newest first.

## Research and writing

- Confirm the source format first: video, image note, or text. Capture the original URL, author, publication time, visible content, and the time of collection. For Douyin/Xiaohongshu, follow `skillto-int-douyin-xhs-crawler` session and access rules. Store source media URLs or already authorized screenshots.
- For a spoken video, obtain the actual oral content with ASR, or OCR its on-screen subtitles when ASR is unavailable. Put the complete timecoded result in the manuscript's inline **原视频的口播逐字稿** field (`transcript`) and record the method, limitations, and optional file link (`transcriptUrl`). Preserve the original wording; mark uncertain ASR terms instead of silently rewriting them. Do not infer speech from a cover, title, description, or sparse frames. For an image note, OCR the pages instead.
- Treat the source transcript as immutable **V0 原稿**. The page's **新增版本** button copies the selected version into V1, V2, and so on; edits to a new version's script and its Prompt belong to that version. Save both fields with `save_version`, and persist the selected version with `select_version` so refresh returns to the same version. Never write a rewrite over V0. Capture the source video's duration in `videoDurationSeconds` for timing estimates.
- The version editor automatically saves changes to the script and Prompt after a short pause and when the fields lose focus; it has no manual Save button. Show the save state and flush pending edits before switching versions or generating audio.
- The **小与AI语音** button reads only the selected version's saved spoken script, removes timecode labels from V0, and generates a local WAV with the fixed `xiaoyu-voice` profile. Do not include the version Prompt, line counts, time estimates, or stage directions in the spoken copy. Long scripts are split into manageable segments and joined into one WAV. Keep the audio associated with its source version and regenerate when that version's text changes; never substitute another voice profile.
- The browser editor shows **every line's** character count and estimated start/end time in a quiet, nonselectable gutter **to the left** of the script textarea. Keep the script on the right, one source line per visual line, and synchronize vertical scrolling in both directions so the gutter stays aligned while editing. Counts exclude whitespace, punctuation, and timecode labels. V0 shows its original ASR/OCR timestamps where available; rewritten versions allocate the full source-video duration across all lines in proportion to character count. The statistics are never inserted into the script textarea, so selecting and copying the full script copies only the manuscript text. These are drafting estimates, not measured speech timing or a guarantee that the new script fits the video. Review pacing before production.
- The right side of each script line has independent, multi-select **IP口播**, **案例**, and **Remotion** tags. Remotion exposes an **编辑** action that opens a per-line Prompt dialog. Save `lineAnnotations` with the selected transcript version, align them to source lines when lines are inserted or removed, and keep both side columns synchronized with the script scroll. Tags and Remotion Prompts are metadata and must not enter copied script text or generated voice. V0 text remains read-only, but its line annotations can be saved with `save_line_annotations`.
- When the analysis needs visual understanding, sample frames across the video, group them into **3×3 contact sheets**, and only then give those sheets to a vision model. Record sample times and gaps. Do not send standalone raw screenshots as the model's visual input.
- Fill the eight analysis areas: detailed core claims; field and real use scenario; counterintuitive points; audience value and actual entry barrier; **why the source attracts traffic**; **target audience, pain points, benefits, and low-barrier wording**; **specific cases, scenes, and screenshots**; similar source posts on 抖音、小红书、YouTube、X. List each claim separately and distinguish a creator's assertion, an AI suggestion, a demonstrable workflow, and independently verified outcomes.
- In the traffic area, quote or timecode the first 5 seconds and explain the hook, pacing, payoff, and calls to like, save, comment, or share. Capture visible likes, comments, saves, shares, and views with their collection time. Treat five-second retention, full-video completion, view-to-engagement ratios, and algorithmic distribution as **unknown** unless platform analytics provide them. Explain likely mechanisms as hypotheses, never as measured causal proof.
- In the audience area, separately identify who the video addresses, the concrete problem or fear, the promised payoff, and exact phrases that make the first action seem easy. Compare the rhetoric with the actual effort, cost, prerequisites, and limitations.
- In the cases/scenes area, list the source's concrete examples with timestamps and point each visual claim to a 3×3 contact sheet or other authorized evidence. Keep source scenes separate from external comparable cases. For external cases and screenshots, apply the recent, directly related, verifiable-hit rule below.
- When looking for comparable cases, scenes, or screenshots, prioritize material **directly related** to the source's specific claim and use scenario and published in the **last 7 days**, then the **last 30 days**, measured from the research date. Only call a recent post a “爆款” when a direct post and its visible engagement or reach metric support that label. Record the publication date, metric, metric capture time, exact shared claim or scene, and direct URL. Do not substitute an older viral example for a recent one or imply that a merely related post is viral. If recent direct evidence is unavailable on a platform, leave that platform's list empty, state the search window and gap, and optionally mark older material as separate background rather than a recent comparable.
- Search similar material by the source's specific claim and scenario. Save direct post links, the shared or differing point, and the evidence for any “爆款” label, including metric and capture time. If a platform has no verified direct post, leave its list empty and say so in the analysis. Do not turn search snippets into confirmed platform posts.
- Draft a new angle, structure, concrete example, and call to action in **二创稿**. The new draft must contribute its own reasoning or testable example; attribute source claims and do not present a proposed income target as earnings.
- Five-heart scores for the eight analysis areas belong to people. Leave each score `null` until a person chooses 1–5 in the page. Never generate or infer a rating from the analysis.

## 文稿分析与关键帧分析：任务流程

用户要求文稿拆解、流量机制分析、关键帧分析或完善这两个 Tab 时，执行本节。按请求范围处理：只分析文稿时不强制重新采视频；只更新分析时不自动新增改写版本、生成配音、改写原稿或采集跨平台案例。原有八项分析作为已有背景保留；只有请求完整研究或需要纠正相关证据时才补充对应项。不要把某一篇视频的结论、情绪路径、27帧数量或抽帧间隔固定成所有稿件的模板。

### 1. 建立证据与任务范围

1. 从用户链接解析 `manuscript`，经 `GET /api/rewrites` 按稳定 ID 读取稿件，核对来源 URL、标题、作者和选定版本。记录两个分析的当前 `revision`，以及 V0、版本、Prompt、行标签、配音和人工评分的状态，供写后核验。
2. 优先复用同一来源已有的完整转写、原始采集记录和可访问的3×3拼图。说明资料采集日期与本次分析日期；复用旧数据不等于本次刷新。需要补采时遵守对应平台会话、访问和媒体授权规则。
3. 将用户粘贴稿、原视频ASR/OCR、改写版本分别标明。发现增删、专有名词识别误差或截断时列出差异；分析可注明规范名称，但不静默改动V0。只有段级ASR时使用口播区间，不声称获得了逐词时间。
4. 写明证据缺口：可见互动计数、播放/曝光分母、留存曲线、关注归因、连续动画是否可得。缺什么就标什么；缺少视频或可靠帧证据时，先完成可做的文稿分析，关键帧模块记录待补证据，不从文字想象画面。

### 2. 文稿分析：逐项解释写法如何影响观众

先概括目标人群的知识水平、具体处境、痛点/担忧、期待收益和实际行动门槛，再追踪“开场如何命中 → 正文怎样推进和兑现 → 结尾如何引导行为”的变化。具体分析用户心智、心理暗示、情绪表达、共情代入感、认知负荷、可信度与自我效能；不得只写“制造焦虑”“引发共鸣”“干货很多”等标签。

深度分析默认分别覆盖以下八类指标。每类至少3项有独立解释价值的原文依据，证据充足时可给4项或更多；用户有其他范围或数量要求时按其要求。不要把同一句话换个说法凑数；不足3项时说明文本缺口，不虚构。没有显式行动口令时，可分析内容的隐含行动价值，但须写明没有直接口令。

| 指标 | 必须区分的分析任务 |
| --- | --- |
| 5秒留存／用户所称“5秒完播率” | 定位真实0–5秒的措辞、对象识别、情境和未完成句；将5秒以后的承诺、数据和目录单列为承接，不能倒算为前5秒已出现。 |
| 整体完播 | 看结构预告、悬念兑现、章节转场、难点减负、阶段进度、例子及结尾回顾；同时识别冗长、跳章与中途退出的可能原因。 |
| 整体互动 | 分析行动入口、利益承诺、参与成本与出现时机；与点赞、评论等分项分开，明确统计口径。 |
| 点赞 | 分析被理解、观点认同、突然听懂、情绪奖励、感谢等可能动机及相反反应。 |
| 转发／分享 | 分析接收者是谁、为何值得发给他、能否减少解释成本、关系价值和身份表达；不从总分享数推断私信/群聊/公开转发渠道。 |
| 收藏 | 分析复查、复用、暂时记不住、决策参考等未来价值；指出“先存后走”也可能发生，收藏不证明完播或学会。 |
| 关注 | 分析作者角色、可信度、一次收益如何转为持续内容预期、关注口令和下一期承诺；没有新增关注归因时不声称转化高。 |
| 评论 | 分析问题的具体性、回答成本、提问羞耻、讨论空间及回应预期；区分求知、求资料、认同、纠错和争论，不将争议数量等同于信任。 |

每项按以下证据链写成表格或等价的清晰条目：

| 原句／可靠时间或段落位置 | 写作处理 | 用户心智、心理暗示与情绪／共情机制 | 对目标行为的可能影响、局限与改进 |
| --- | --- | --- | --- |

解释中要交代“这句话对谁有效、触发什么理解或感受、为何可能促成该行为、什么条件下无效”。同一原句用于多个指标时必须解释不同的行为动机。优点与不足均落实到原文，重点检查：承诺是否兑现、类比是否过度简化、产品/模型/流程是否混类、统计和绝对化判断是否有出处、低门槛话术与真实成本/权限/验收是否相符。当前产品能力或外部事实需要核查时查直接来源；未核查的标为作者观点或待核实。

最后提出可执行的验证方式，如检查对应时段留存、分开读取各类互动和新增关注、抽样分类评论，或对后续作品做单变量开头对照。缺少后台数据时，写“可能有利于留存/互动的机制”，不接受“指标很高”的前提为已证事实。互动计数不等于互动率；动作总数不等于独立互动人数；收藏/点赞比不等于收藏率；观察关联不等于因果。

### 3. 关键帧分析：先看证据，再评价图文与动画

1. **抽样规划：**依据视频时长和章节覆盖开头、主内容、关键转场、例子、结尾；需要判断短时动画时在相应片段加密抽样。优先复用可核验的既有拼图，不固定帧数或秒数。新增抽样保留每帧源视频时间、采样方式、拼图编号及格位，必要时说明空白格；先合成为3×3拼图，再送视觉模型审看。
2. **覆盖校验：**列出各拼图覆盖内容、采样时间与间隔、缺失区段；逐格核对字幕/画面与转写。推荐位置格式为“图2-R3C1”。旧时间标签与字幕不一致时，不用均匀步长补出伪精确时间；记录冲突，使用可靠的帧时间或明确标记的口播主题区间。不能用抽帧数计算真实镜头数或平均镜头时长。
3. **逐格观察：**只记录实际可见的人物尺度、构图、背景、字号层级、颜色对比、字幕、卡片、图标、箭头、图表、界面、留白与前后状态。同一拼图多格可以合并为一项，但结论须能回到具体格位。源片场景、外部案例和二创建议分开。
4. **设计判断：**解释设计怎样服务信息理解、视线顺序、记忆、情绪和口播推进；同时指出阅读负担、手机可读性、小窗/字幕遮挡、信息密度、定义简化、来源不足及示意界面被误当实测等具体问题。未在手机播放器实测时标为风险，不捏造像素字号或设备结论。
5. **动画边界：**区分静帧直接可见的状态、由帧间差异推测的设计意图和连续片段实际验证的动态表现。稀疏帧不能证明运动方向、缓动、进出场时长、切镜频率、音画卡点或流畅度；变暗或空白的一帧不能证明长期可读性差。需要这些结论时补连续观看及带时间码的密集3×3采样，未取得则保留空缺。

关键帧模块至少包含一张具体设计分析表，列结构如下；不得用泛泛优缺点替代画面证据：

| 拼图链接／格位／可靠时间或口播区间 | 可见画面事实 | 图文或动画设计的可取之处及原因 | 可能的理解、情绪和行为机制 | 不足、证据边界与可执行改进 |
| --- | --- | --- | --- | --- |

按需要补充采样覆盖表、动画证据边界表和改进优先级表。结尾提炼可复用的方法与不宜照搬之处，并与文稿中的具体段落对应。将“原片看到了什么”和“建议二创怎么做”明确分开；画面设计的合理性不能代替后台效果数据。

### 4. 写入两个 Tab 并验收

- 文稿分析写入 `manuscriptAnalysis`，关键帧分析写入 `keyframeAnalysis`。使用下文 `save_analysis` 契约分别保存；正文包含来源、分析日期、证据时间/方法、缺口、逐项分析和改进。支持的Markdown子集以“稿件内分析 Tab”为准，表格单元内避免未转义的分隔竖线和HTML。
- 每次写入前读取目标模块最新 `revision`，携带 `expectedRevision`。遇修订冲突保留拟稿并重新读取差异，合并相关修改后再提交；不得只换新修订号强行覆盖他人内容。普通 `create/update` 不能代替 `save_analysis`，不要直接改 `rewrites.json`。
- 写后再次GET核对正文、修订号、时间和追加历史；确认V0、改写版本、Prompt、行标签、配音和人评没有被分析写入改变。已有人工评分保留，未评分维持 `null`。
- 打开目标稿件的两个Tab，检查表格排版、拼图/来源链接、空态或证据缺口、切换与刷新恢复。普通内容更新只做相关验收；未改变界面/后端时不重启服务、不重跑完整产品开发回归。完成后提供能直达相应Tab的链接，并说明未核实的指标和动态范围，不把“已保存”说成“结论已验证”。

## Local CRUD

The local page and API share `SKILLTO_TABLE_ROOT/rewrites.json`; the Windows launcher config supplies the actual root. Use `GET /api/rewrites` to read. For writes, send JSON to `POST /api/rewrites` with `action` and its business fields. Supported actions: `create_kb`, `rename_kb`, `delete_kb`, `create_project`, `rename_project`, `delete_project`, `create`, `update`, `delete`, `create_version`, `save_version`, `save_line_annotations`, `select_version`, `save_analysis`, `save_storyboard`, `create_storyboard_version`, `select_storyboard_version`, `rename_storyboard_version`, `link_motion_storyboard`, `create_motion_storyboard_version`, `select_motion_storyboard_version`, `rename_motion_storyboard_version`. The local implementation is [rewrite_system.py](../skillto-int-table/scripts/rewrite_system.py). For create/update, supply `knowledgeBaseId`, `projectId`, and `manuscript` with:

```json
{
  "title": "...", "status": "research", "sourceUrl": "https://...", "transcriptUrl": "/assets/rewrite-case/.../transcript.txt", "transcript": "[00:00] ...", "videoDurationSeconds": 702.4,
  "sourceAuthor": "...", "sourcePublishedAt": "...", "sourceNotes": "...",
  "sections": {
    "claims": {"text": "...", "score": null, "scoreNote": ""},
    "scenario": {"text": "...", "score": null, "scoreNote": ""},
    "counterintuitive": {"text": "...", "score": null, "scoreNote": ""},
    "value": {"text": "...", "score": null, "scoreNote": ""},
    "traffic": {"text": "...", "score": null, "scoreNote": ""},
    "audience": {"text": "...", "score": null, "scoreNote": ""},
    "cases": {"text": "...", "score": null, "scoreNote": ""},
    "similar": {"text": "...", "score": null, "scoreNote": ""}
  },
  "assets": [{"label": "第 1 页", "url": "https://...", "note": "..."}],
  "similar": {"douyin": [], "xiaohongshu": [], "youtube": [], "x": []},
  "secondCreation": "..."
}
```

The server adds `transcriptVersions` with immutable V0 and `activeTranscriptVersionId` when a manuscript is created or an older record is read. `create_version` takes the manuscript `id` and optional `baseVersionId`; `save_version` takes `id`, `versionId`, `text`, `prompt`, and `lineAnnotations` (V0 text is rejected); `save_line_annotations` takes `id`, `versionId`, and `lineAnnotations` and is allowed for V0; `select_version` takes `id` and `versionId`. `lineAnnotations` is an array aligned to text lines, each item shaped as `{"tags":["ip_voice","case","remotion"],"remotionPrompt":"..."}`. Only chosen tags belong in `tags`; the allowed tag IDs are `ip_voice`, `case`, and `remotion`. The selected version is stored in the manuscript, not just browser memory. The general manuscript form preserves the versions; use the version editor or these actions to edit a rewritten script or its Prompt.

Voice generation uses `POST /api/rewrites/voice` with `id` and `versionId`, then `GET /api/rewrites/voice-status` for its background job. The service writes the fixed-profile WAV under `E:\wwai\qwen3-tts\outputs\xiaoyu` and exposes only the resulting version file at `/assets/rewrite-audio/...`. A generated file is attached to the version as `voiceAudio`; editing the spoken text invalidates that attachment. Do not pass arbitrary voice references or output paths through the API.

Each similar entry has `title`, direct `url`, `point`, and `evidence`. Status is `research`, `draft`, or `reviewed`. Update a manuscript with its stable `id`; edits append history. Deletion requires an explicit user request, and the page confirms it. A nonempty project or knowledge base must be emptied first.

For the built-in Douyin note example, `work/note_7694608697625416674_research.md` records the source check and `work/seed_rewrite_case.py` imports it idempotently. That example is evidence for this one item, not a template whose conclusions should be reused for another source.


## 双版本多行编辑

稿件版本区使用「双版本编辑」打开左右两个完整的多行文本框，各自下拉选择版本。两框字号、行高、顶部内边距和初始高度一致，保留原有换行、空行和标点，不自动分句、不生成逐句表格、不插入对齐占位行；按原有换行逐行显示并双向同步垂直滚动。两侧非V0版本均可编辑，自动保存到各自版本；同版本同时显示时正文同步。V0正文只读。单版本编辑仍保留全文、Prompt和逐行标注能力。

左右切换版本、切换编辑模式及新增版本前刷新两侧待保存正文；失败保留草稿并阻止切换。保存沿用现有 save_version、版本 Prompt、逐行标签、历史和语音失效规则。对比开关与左侧选择为本浏览器按稿件隔离的视图偏好，右侧编辑版本仍通过 select_version 保存。

验收使用隔离稿件：两个完整文本框、相同垂直行几何、同步滚动、两侧独立落盘、换行空行保留、Prompt/标签保留、V0只读、编辑后立即切换和刷新恢复。

## 稿件内分析 Tab

每篇稿件顶部提供「文案版本」「原文亮点」「原视效亮点」「前12秒分镜」「12分镜表」「motion分镜表」六步导航；切换前保存待写入的版本和分析，失败保留草稿并阻止切换。支持方向键、Home/End、窄屏表格横向滚动。当前 Tab 是按稿件隔离的浏览器视图偏好，可用 `rewriteTab` URL 参数直接定位。已有稿件读取时补齐空分析，新稿件直接提供相同入口，不需要为单篇定制页面。

分析属于稿件，不属于某个口播版本，不能进入配音或逐字稿。字段 `manuscriptAnalysis`、`keyframeAnalysis` 均为 `{"text":"","revision":0,"updatedAt":""}`，正文支持安全子集 Markdown（标题、段落、列表、表格、HTTP(S)及既有素材链接；不执行 HTML）。人工通过「编辑分析」「保存分析」修改；切换前也会保存，状态明确区分未保存、保存中、已保存到磁盘与失败。刷新前若有未保存修改会提示。

AI 通过 `POST /api/rewrites` 的 `save_analysis` 动作写入：`id` 为稿件ID，`analysisKey` 为上述二者之一，`text` 为正文（最多100000字符），`expectedRevision` 为刚读取的整数修订号。修订冲突拒绝覆盖，写入追加历史；一般 `update` 保留服务端现有分析，旧表单不得擦除它。保存分析不改变V0、改写版本、Prompt、行标签、配音或人评。

分析内容按前文「文稿分析与关键帧分析：任务流程」执行。直达链接使用 `?section=rewrites&manuscript=<稿件ID>&rewriteTab=manuscriptAnalysis` 或 `rewriteTab=keyframeAnalysis`。

保存分析的请求示例（先GET读取实际ID和该模块的revision）：

```json
{
  "action": "save_analysis",
  "id": "<稿件ID>",
  "analysisKey": "manuscriptAnalysis",
  "text": "<完整分析正文>",
  "expectedRevision": 0
}
```

示例中的0仅适用于刚读取的修订号确为0；保存另一模块时换为 `keyframeAnalysis` 并读取它自己的修订号。接口返回稿件对象，随后重新读取验证。

验收覆盖隔离数据的旧稿补齐、两分析独立保存、刷新恢复、修订冲突、一般表单保护、历史、HTML注入转义、版本编辑切换落盘、保存失败保留、键盘与手机宽度。原八项分析与人工五心评分继续保留。


## 分镜步骤与版本管理

「motion分镜表」是当前稿件**整个视频**的分镜方案，一个表格对应一个分镜版本；它与「前12秒分镜」独立管理，也不取代既有「12分镜表」。文案版本、开场分镜版本、motion分镜版本分别编号，不按相同数字推定一一对应。motion版本记录 `sourceTranscriptVersionId`，作为方案来源，不随当前文案切换自动改变。

- 「前12秒分镜」与「motion分镜表」复用文案版本的横向紧凑按钮样式：V1、V2……，当前版浅灰高亮，`aria-pressed` 表明选择；版本名称显示在按钮下方并作为提示。方向键、Home/End可切换，窄屏横向滚动。文案区仍显示只读的「V0 原稿」；分镜没有原稿证据时不伪造V0，也不重排已有版本ID。
- 「前12秒分镜」保留旧 `openingStoryboard` 的全部版本、名称、关键帧、台词、动画、提示词与人工意见。新版本复制当前版本，切换前先保存；失败保留草稿并阻止切换。顶层 `rows` 是当前版本的兼容视图，`revision` 是全模块并发修订号。旧数据首次读取补V1原方案，原内容不变。每版最多200行，每行最多4张关键帧，空意见不等于人工通过。`fullStoryboard` 仍沿用原有分镜保存接口。
- 「motion分镜表」通过「关联已有表格」把用户指定的全片表格加入为一个新版本；首次为V1。关联只保存关系，不重写原表。各版本完整复用通用表格的字段、媒体预览、行编辑、标签、评分、字段显隐和历史。表格内容仍由表格语义接口管理，不压缩成开场分镜行，也不复制进逐字稿或配音。
- motion「新增版本」复制当前表到同一项目下的独立表格，保留未知字段、媒体、标签、已有人工评分及历史，新增表拥有新的稳定ID；此后编辑互不覆盖。不推断新评分，不生成新媒体。版本的当前选择和重命名持久化在稿件中，刷新恢复。两类分镜均最多30个版本。
- motion表内编辑窗口未保存/关闭、写入仍在进行或保存失败时，阻止切换版本或步骤；先完成保存或明确取消。离开motion步骤释放内嵌播放器，返回时重新载入当前表。表被移除或服务不可用时显示错误，不静默关联其他表。

### 分镜API

使用同一 `POST /api/rewrites`；写前GET读取当前修订号。开场版本动作 `create_storyboard_version` / `select_storyboard_version` / `rename_storyboard_version` 传 `id`、`expectedRevision`；新增可传 `baseVersionId`、`label`，切换/改名传 `versionId`，改名加 `label`。`save_storyboard` 传 `id`、`storyboardKey`（openingStoryboard或fullStoryboard）、`rows`、`expectedRevision`；开场另传当前 `versionId`，防止写错版本。

`motionStoryboard` 为 `{versions:[],activeVersionId:"",revision:0,updatedAt:""}`。每版含 `id/label/tableId/tableTitle/sourceTranscriptVersionId/createdAt/updatedAt`，正文在对应表格中。动作均传稿件 `id` 和 **motionStoryboard自己的** `expectedRevision`：

| action | 业务参数 |
| --- | --- |
| `link_motion_storyboard` | `tableId` 为核对过的已有表；可传 `label`、`sourceTranscriptVersionId`（默认当前文案版本）。同一表不能重复关联成该稿件的另一版本。 |
| `create_motion_storyboard_version` | 可传 `baseVersionId`、`label`；默认复制当前表并选中新版，继承来源文案版本。 |
| `select_motion_storyboard_version` | `versionId`；只切换motion选择，不切换口播版本。 |
| `rename_motion_storyboard_version` | `versionId`、`label`；只改版本名称，不改原表标题。 |

实现由兄弟表格技能的 [rewrite_motion.py](../skillto-int-table/scripts/rewrite_motion.py) 使用正在运行的表格服务；缺少表格依赖时明确报错，不自动改用其他客户端或远程存储。一般稿件 `update` 保留这些模块。冲突后保留草稿、读取差异再合并，不只更换修订号强行覆盖。

直达入口：`?section=rewrites&manuscript=<稿件ID>&rewriteTab=motionStoryboard`；开场为 `rewriteTab=openingStoryboard`。用户提供带 `table` 和 `manuscript` 的链接时分别核对两者身份，通过关联动作建立关系；不要把某一表ID写死进技能或前端。

验收使用隔离稿件与表格，覆盖旧稿兼容、关联、复制、独立编辑、重命名、刷新恢复、修订冲突、复制失败回滚、保存失败阻止切换、键盘与窄屏；再核对用户目标表完整可见。确认V0、文案版本、Prompt、配音、两项分析、原分镜和人工评分未被关联操作改变。分镜管理授权不等于生成配音、图片、视频、运行Motion模板或外部发布授权，制作仍遵循对应子技能的工具与授权边界。
