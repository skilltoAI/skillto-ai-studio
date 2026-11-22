# 19 个子技能：安装、依赖与验收

所有技能由仓库 `skills/` 分发；不从维护者已安装副本批量回拷。父入口是
`skillto-ai-studio`。2026-11-17 盘点时，用户提供的已安装父入口列出 17 项；仓库多出
`skillto-ai-studio-explainer-storyboard`，此后新增 AI 资产专题库，当前父入口共包含 19 项。

先完成 [统一安装](installation.md)。每节标题就是 `--skill` 参数，例如：

```sh
python scripts/install.py --agent codex --skill skillto-ai-studio-style-library
```

Claude Code 改 `--agent claude`；整套安装无需逐条重装。下面 `<skill-root>` 指
**当前加载的这个子技能目录**，`<python>` 指实际用于运行它的 Python；占位符必须
替换为本机路径，路径有空格时加引号。依赖装在独立虚拟环境，不写入插件缓存。
“验收”是安装者需要执行的检查，不代表分发时已访问了你的账号、模型或服务。

## skillto-ai-studio-workbench

用途：Chrome 视频发现、下载/选段、拉片笔记。安装兄弟 `skillto-ai-studio-table` 用于共享
Studio 服务；浏览器完整普通视频下载可独立，选段和同步需要本地服务与 FFmpeg。

1. 使用 Chrome 116+，先解决下文表格的 Studio 网页依赖。安装器只携带自有 overlay，
   不包含完整 Cat Catch 源码，也不自动安装浏览器扩展。
2. 服务的 Python 环境执行 `python <skill-root>/scripts/setup_workbench.py --install-deps`，
   安装声明的 yt-dlp/imageio-ffmpeg；不带参数为依赖检查。完整 FFmpeg 可由 PATH 或
   `SKILLTO_FFMPEG_LOCATION` 指定。
3. 按 [安装指引](../../skillto-ai-studio-workbench/references/install.md) 与
   [NOTICE](../../skillto-ai-studio-workbench/assets/cat-workbench/NOTICE.md)，获取自己审核的
   `xifangczy/cat-catch` 上游源码并检出基线 `019c465794b5871701383e4485c0e9ee7be2f840`。
   执行 `python <skill-root>/scripts/build_cat_extension.py --source <上游目录> --destination <稳定运行目录>`。
4. Chrome 加载构建后的目录（直接含 `manifest.json`），不能加载 overlay。已有扩展则
   按原卡片重新加载；把输出目录配置给服务的 `catExtensionDirectory`，通过工作台同源自动配对。

验收：真实 Chrome 显示品牌与两个下载目的地；用获授权测试视频检查下载、选段和同步后的
可播放记录。下载文件不能误入拉片库。当前简化选段不支持 HLS/DASH；保留登录与限流边界。

## skillto-ai-studio-douyin-xhs-crawler

用途：获授权抖音/小红书采集、账号验证、近期指标。Python 3.10+、Playwright 和浏览器：

```sh
python -m pip install playwright
python -m playwright install chromium
python <skill-root>/scripts/configure_cookie.py --path <仓库外的私有Cookie文件>
python <skill-root>/scripts/configure_cookie.py --path <同一文件> --check
python <skill-root>/scripts/crawl_recent_douyin_videos.py --help
```

通过隐藏输入配置自己的会话。实际采集显式传 `--cookies <文件>` 或 `DOUYIN_COOKIE_FILE`；
Windows 内置 `E:\wwai\...` 是维护者默认路径，新机器不要照搬。
遵循 [Cookie 配置](../../skillto-ai-studio-douyin-xhs-crawler/references/cookie-setup.md)。
`--check` 只检查格式；验收需在获授权的小样本中验证作者 ID 与目标一致。
内置 CLI 是抖音账号列表实现，小红书还需对应项目实现与授权会话，不能承诺装好即通用下载。
受限“小与AI”账号的每任务授权规则不变。

## skillto-ai-studio-tiktok-crawler

用途：账号/关键词采集、排名与快照。Python 3.10+，按随附依赖安装：

```sh
python -m pip install -r <skill-root>/scripts/requirements.txt
python -m playwright install chromium
python <skill-root>/scripts/run.py doctor
python <skill-root>/scripts/configure_cookie.py --path <仓库外的私有Cookie文件>
python <skill-root>/scripts/configure_cookie.py --path <同一文件> --check
```

也可在 doctor/采集时指定 `--browser-channel chrome` 或 `msedge`。
设置 `TIKTOK_COOKIE_FILE` 或传 `--cookies`；参考
[会话配置](../../skillto-ai-studio-tiktok-crawler/references/cookie-setup.md)。
需要表格交付时安装 `skillto-ai-studio-table`。验收先 doctor，再在当前授权范围内核对单条页面的
作者与视频 ID；doctor 不证明登录有效。验证码需要同一会话人工处理，不更换身份绕过。

## skillto-ai-studio-table

用途：本地或认证远端多媒体表格。已安装 Windows STASS 时，使用其共享实例
和宿主专属配对配置。默认健康地址为 `http://127.0.0.1:8080/STASS/health`。

用已选定发行版本的 `runtime/python.exe` 运行 `program/client.py list --profile <宿主配对配置>`，
核对已发现的 MCP 工具。Claude Code 使用自己的配对配置；如果尚未注册，
在确认配置范围后，用该版本的 Python 运行 `program/mcp_bridge.py --profile <Claude 配对配置>`
作为 stdio MCP，再新开会话验收。保留既有连接，按实际目标选择工具。
配对文件和两个脚本的路径均来自本机安装，凭据留在本机。

### 旧版独立表格部署

以下步骤仅适用于明确选择的旧版独立表格部署。stdio MCP 核心使用 Python 标准库。
先选仓库外数据目录，例如用户主目录的 `skillto-table-data`。客户端分别注册，以下路径是占位：

```sh
codex mcp add skillto-ai-studio-table --env SKILLTO_TABLE_ROOT=/absolute/data -- /absolute/python /absolute/skillto-ai-studio-table/scripts/server.py
claude mcp add --scope user --transport stdio --env SKILLTO_TABLE_ROOT=/absolute/data skillto-ai-studio-table -- /absolute/python /absolute/skillto-ai-studio-table/scripts/server.py
```

Windows 用带引号的 `C:/.../python.exe`、脚本和数据绝对路径替换。这些命令会新增客户端
MCP 配置；已有同名连接先比较，不覆盖。父技能和子技能的安装目录不是 MCP 数据目录。
新会话中发现 `table_workspace`、`table_query` 等实际工具，先做读取验收；在指定测试数据根
创建测试表、写入后回读，确认重启仍存在。工具前缀由宿主决定。

远端模式显式设置 `SKILLTO_TABLE_API_URL` 与 `SKILLTO_TABLE_API_KEY_FILE`（后者是保护文件
路径），先验证读权限，再按任务确认写权限。维护者 AMD-PAD 地址不是其他机器的公共服务。
见 [MCP 合同](../../skillto-ai-studio-table/references/mcp.md) 与
[远端设置](../../skillto-ai-studio-table/references/amd-pad.md)。

**旧版独立表格网页和启动器需要额外部署。**
`reporting/serve_local.py` 依赖仓库外的 `douyin_tracker.review_web`，并引用维护者
`runtime/pet_refresh_20261028/research-adapter.js`、`table-lineage.*` 等资源。
表格存储与兄弟模块从当前加载的技能目录解析；仅复制技能仍不足以在全新机器启动完整 Studio。
需要部署者提供同一外部组件及其版本、适配加载路径和数据目录后独立验收；不能偷偷替换成
一个不同网页。缺少这些资源时可使用本地 stdio MCP，依赖网页的功能应报告未就绪。

Windows 启动器需 Go 与现有服务；按
[启动器指引](../../skillto-ai-studio-table/references/windows-launcher.md) 显式指定本机 Python、
ServiceScript、WorkingDirectory、DataRoot、InstalledSkill；默认历史路径不适用于新机器。
EXE 和 `launcher.local.json` 均不随仓库分发；macOS/Linux 使用部署完成的 Python HTTP 服务，
不运行 Windows EXE。不要把“安装完成”描述成“桌面启动器可用”。

## skillto-ai-studio-reports

用途：Metabase 报表/图表 CRUD。已安装 STASS 时，先确认其报表模块和配置的 Metabase、PostgreSQL 可用。旧版独立部署使用表格 HTTP 服务，另需 Docker/Compose、Metabase 与 PostgreSQL。按
[报表部署手册](../../skillto-ai-studio-table/reporting/README.md) 在专用环境安装
`reporting/requirements.txt`。维护者的冻结数据集、镜像/JAR 和凭据不在分发包中。

`setup_local.py` 是服务部署操作，会启动容器、生成本机凭据；先检查 Docker 与所需镜像。
不要在新用户机器无条件运行 `collect_accounts.py`、`sync_data.py`、`publish_reports.py`：
它们包含维护者历史名单/批次逻辑，不是通用安装步骤。新数据源由部署者单独配置。
验收 `python <skill-root>/scripts/report_cli.py --help`，服务就绪后读取报表 catalog，
以测试项目核对可见图表与回读。Metabase 不可用时不能只写本地注册表假装成功。

## skillto-ai-studio-style-library

用途：14 类风格检索、归类、元素动效设计。安装目录后即可读取，无 Python、网络或 MCP
要求。验收能读取本目录 `references/style-index.md`、`style-details.md`，按抽象需求返回
S001–S014 中有依据的选择。Remotion/Motion/Three.js 是按项目另配的实现路线，未随技能安装。
Studio 模板库 CRUD 属于 `skillto-ai-studio-motion`。

## skillto-ai-studio-assets

用途：AI资产分类、AI红白模库提示词与视频资料录入，剪映AI模版库预留。依赖运行中的 STASS 及可发现的资产 MCP 操作；飞书播放另需服务的 Playwright 和可用 Chromium 或 Chrome。不得复用已登录浏览器档案。

按 [技能说明](../../skillto-ai-studio-assets/SKILL.md) 验证公开页面和视频，dryRun 后幂等录入；验收卡片同时展示提示词与视频、复制/下载图标、拖动播放、导航和窄屏。服务仅保存元数据，视频在线转发。公开权限可能改变，安装成功不代表来源永久可访问；Motion 制作仍交由原子技能。

## skillto-ai-studio-motion

用途：Studio Motion 模板库、包检查和指定适配器制作。安装 `skillto-ai-studio-table` 并先完成
其完整 HTTP 服务部署；导入前读
[录入规范](../../skillto-ai-studio-motion/references/intake.md)。静态包检查用 Python 标准库。

制作另需 Python 3.11+、Node.js 22+、Chrome、包含要求滤镜的完整 FFmpeg/ffprobe。
按 [运行依赖](../../skillto-ai-studio-motion/references/operations.md) 执行
`python <skill-root>/scripts/setup_motion.py --ffmpeg-directory <bin目录> --chrome <浏览器可执行文件>`，
该操作会在运行目录安装依赖；不是整套安装器的隐式步骤。

验收 `python <skill-root>/scripts/motion_cli.py catalog` 和 `doctor`；制作必须另外核验
真实预览/MP4。目前只有明确固定的 Kinetic Tech 版本适配器获得执行支持，不把任意
`.motion` 包当可执行代码，不自动安装包内指令为技能。

## skillto-ai-studio-rewrite

用途：来源研究、不可变 V0、改写版本与分镜审阅。安装 `skillto-ai-studio-table`，版本 CRUD
需要其完整 HTTP 服务。视频来源另配授权采集子技能，语音转录需 ASR，截图文字需 OCR。
读取本子技能的 `/api/rewrites` 合同；不用直接改数据库代替服务操作。

验收 `/api/rewrites/catalog` 可读；在测试稿件核对 V0 保持不变、版本切换和修订冲突。
配音按钮依赖未打包的 `xiaoyu-voice`、模型及维护者 Windows 路径，当前不能视为跨机器已就绪。
缺失时仍可研究和写稿，不能静默换声音、生成配音或宣称已配音。

## skillto-ai-studio-qwen38-media-analysis

用途：Qwen3.8 图像、OCR、抽帧与分镜。Python HTTP 客户端仅用标准库；抽帧优先
FFmpeg/ffprobe，无 FFmpeg 时可装 OpenCV 后走现有回退。

```sh
python <skill-root>/scripts/extract_frames.py --help
python <skill-root>/scripts/qwen38_cli.py --help
```

当前客户端固定 `http://192.168.3.188:8080/v1` 与 `qwen3.8-35b-a3b-q6`；
**没有 `QWEN38_BASE_URL` / `--base-url` 配置项**，不要发明命令参数。
`QWEN38_API_KEY` 是已有凭据入口，使用客户端保护配置传入。
局域网或明确授权的 VPN 可达后才运行 `status` 和自有测试图；状态成功还需图像结果验收。
独立部署者需明确适配 Python/PowerShell 客户端常量并验证 Responses 协议与模型，不能声称
仅安装技能就已部署 Qwen。不可达时本地抽帧仍可用，远端理解不可用。

## skillto-ai-studio-talking-head-edit

用途：粗剪 A-roll + SRT 的规划、编辑和渲染。外部 `hyperframes`、相关 Remotion 技能
与运行环境、`video-talkcraft` 必须另行安装；本仓库不包含这些项目。
来源见 [本子技能](../../skillto-ai-studio-talking-head-edit/SKILL.md) 的 Source projects，
按各自安装文档和项目锁文件配置，不假定全局 npm 包等于可用工程。
验收读取全部指定外部技能、解析时间码、渲染一个已确认的短预览。
保留分镜确认及关键帧/风格确认两道制作门槛，不因安装测试自动做完整成片。

## skillto-ai-studio-explainer-storyboard

用途：知识/新闻/科普的证据清单、节拍、分镜与审片。纯规划读取技能及三份 references
即可；参考视频需要 FFmpeg/OpenCV 和真实画面检查，关键帧生成需要当前宿主实际可用的
设计/渲染工具。按任务可联用 rewrite、qwen38-media-analysis、talking-head-edit。
验收以已有稿件做一段证据清单与分镜，并能引用本目录模板。保留结构与关键帧的确认步骤；
不把规划交付称为已渲染成片。

## skillto-ai-studio-workflow-mcp

用途：SkillTo.ai 工作流 CRUD、上传、预检、运行。需有自己有权限的 SkillTo.ai 账号、
Creator API Key 和 `@skilltoai/creator-mcp` 能力；远端 Streamable HTTP 地址是
`https://skillto.ai/api/skillto-v2/creator-mcp`，也可使用该服务提供的 stdio bridge。
按服务提供方的当前接入方式配置，不能把其他宿主的 MCP 工具前缀硬抄过来。

Codex 可用 `codex mcp add <连接名> --url <地址> --bearer-token-env-var <受保护环境变量名>`；
Claude Code 使用其 HTTP MCP 配置与服务要求的认证头，通过保护配置提供 Key，不把密钥写
入命令历史或仓库。最小只读验收发现工具、读取本人草稿和模型选项。
编辑需要 `workflow:write`，上传需 `asset:write`，运行需 `workflow:run`，仍须当前任务授权。
安装验收不创建、修改或收费运行草稿。

## skillto-ai-studio-character-card

用途：新主体定妆/多视图角色卡提示词。纯提示词编写不需后端；实际节点提示词回写需安装
`skillto-ai-studio-workflow-mcp` 并配置 Creator MCP。验收能读取 `references/prompt-contract.md`，
把真实引用顺序、必要道具和身份约束写清。生图后端与收费授权不是本技能安装的附带结果。

## skillto-ai-studio-depth-gray-replica

用途：原片获取、逐秒证据拆解与替换提示文档。按平台安装采集子技能，准备 FFmpeg、
ffprobe、Pillow；指定外部 `scrapling`/`scrapling-stream` 路线需另行安装。
播放器采集脚本另需 Playwright 和其支持的 Edge 浏览器。

验收 `sample_timeline.py --help`、`make_contact.py --help`，再以授权本地短片检查采样覆盖。
本子技能当前边界止于获取、分析和提示文档，不输出深度视频或角色替换成片。

## skillto-ai-studio-depth-gray-workflow

用途：原片→真实深度视频、音轨、分析和 SaaS 替换草稿。安装相应采集子技能和
`skillto-ai-studio-workflow-mcp`；准备 FFmpeg、Pillow、帧检查与 Creator MCP。
必须另装 `make-expression-depth-video` 及其真实深度后端；本仓库无此模型或安装包，
需由该技能提供方交付。缺失即阻断深度阶段，不能用去饱和滤镜冒充。
验收本地短样本深度方向、画幅/时长与音轨；有草稿权限后校验图，不自动付费运行。

## skillto-ai-studio-h3-workflow

用途：原片直驱 H3 角色迁移。安装相应采集子技能、`skillto-ai-studio-depth-gray-replica`、
`skillto-ai-studio-character-card`、`skillto-ai-studio-workflow-mcp`；准备 FFmpeg/ffprobe、画面分析。
需 Creator MCP 当前模型目录提供可用的 H3 和角色卡模型；内置 TikTok 播放器脚本另需
Playwright/Edge 及获授权会话。无需深度灰后端。
验收只读模型选项和节点合同；实际草稿编辑、素材上传按任务授权，报价和运行分开。
不自动裁短原片，也不由提示词推断成片音轨已经正确。

## skillto-ai-studio-xiaoyu-cover

用途：小与品牌封面，3:4 与 4:3 独立构图。品牌参考图片随包安装；需要宿主提供指定
`imagegen` 技能和 `image_gen` 能力。普通 Claude Code 不自带该能力，装本插件不能补上；
能力缺失时报告阻碍，不静默替换其他模型。视频模式还需获授权采集、抽帧与必要 ASR。
验收两张品牌参考可读、工具支持本地参考图；实际生成需当前任务授权，输出后检查像素与文字。

## skillto-ai-studio-ip-store

用途：原片角色卡与场景图、两张跨视频素材库表。需要指定外部 `scrapling`、FFmpeg/ffprobe、
原帧检查和内置 `image_gen` 参考图生成能力；展示到工作台时再安装 `skillto-ai-studio-table`。
Codex/Claude 能读取流程，但没有 `image_gen` 的宿主不能完成其指定生图阶段。
验收先确认取得真实媒体及抽帧，产物写到用户工作目录的 `research/ip-scene-library/`，
不写到技能目录。卡片生成需核对身份、风格和精确灰背景；不把补全视角说成原片证据。
