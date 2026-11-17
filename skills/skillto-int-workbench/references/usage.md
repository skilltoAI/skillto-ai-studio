# 下载、拉片和接口

## 当前猫抓工作台的使用方式

在视频页播放后点击 **SKillto.ai|工作台**，资源列表只显示两个输出动作：**下载**、**同步到工作台**。两个动作都会打开独立的视频片段窗口，支持视频预览、拖动起止点、输入秒数、把当前画面设为起点/终点，以及播放选区。勾选“仅保留所选片段”才裁切，默认保存完整视频。必须确认当前视频的保存授权。

- **下载**：完整普通视频直接交给 Chrome，不依赖本机服务；片段由 Chrome 取回源视频，再交本机 FFmpeg 精确导出，最终由 Chrome 保存。片段临时任务保存在独立 exports 表/目录，不能出现在拉片列表。
- **同步到工作台**：自动连接同一表格工作台，将完整视频或选中片段保存到 `/breakdowns`，保留来源和片段起止点，可继续播放和写笔记。处理成功后自动打开对应拉片记录；已有工作台标签页时复用并聚焦，不重复开页。同步与片段处理通过插件分块传入同一本机服务，不依赖 Chrome 下载目录或用户选择保存位置。传输时保持编辑窗口打开，关闭会停止未完成的传输。

片段处理可能先下载完整源文件，并非只取区间对应网络数据。本机中转源文件和临时导出文件会保留。当前简化编辑窗口支持 MP4/WebM 等普通视频；HLS/DASH 清单暂不支持这两个导出操作，会明确提示。不会把清单、DRM 内容或不完整分片当成可用视频。原猫抓引擎保留，移除的是复杂下载选项，不是把成功的发现流程换回网页解析。

当前客户端先检查健康标记 `browserUpload`。经 Bearer 认证的 `POST /api/workbench/browser-upload?id=<id>&destination=<target>&offset=<bytes>` 按连续位置传入不超过 4 MiB 的数据块，空正文加 `final=1` 完成传输。任务路径由服务生成，限制总大小 2 GiB，完整性与时长检查后再处理；不接收 Cookie/Authorization 缓存或任意本地路径。旧的 `browser-finish` 文件导入仅为旧客户端保留。

`browser-start` 新增可选 `destination:"download"|"workbench"`、`clipStart`、`clipEnd`。只下载完整文件无需创建后端任务。`browser-finish` 带相同 destination，校验原文件后异步处理；`GET /api/workbench/transfers?id=<id>&destination=<target>` 读取单任务状态；`GET /api/workbench/export-media?id=<id>` 经同源或 Bearer 认证返回导出文件并支持 Range。源文件仍按每次任务随机名称校验，不能导入任意路径。旧版没有 clipExports/independentExports 健康标记时，客户端拒绝提交片段，防止旧服务忽略选区并保存全片。

以下“使用”段落是旧实验插件的行为参考。

## 使用

启动同一套本地工作台后，在有权保存的视频页面点击 Logo，勾选授权，点击 **浏览器下载当前视频到拉片**。插件通过 Chrome 原生下载保存普通视频，不再悄悄回退到服务器网页解析。首次点击会请求 Chrome 的可选下载权限。完成后，Chrome 下载目录的 `SkilltoWorkbench/` 保留原文件，本地拉片库导入一份独立副本。

当前视频优先从可见主播放器读取；blob 播放器不能把 MediaSource 本身当成视频文件，因此会在页面现有数据中按当前作品 ID 查找媒体地址。只在用户明确点击当前视频下载且被动扫描无匹配时，从该页面的原会话读取一次该作品详情，不导出 Cookie、不伪造签名、不在拒绝、挑战或限流后重试。没有当前作品对应资源时停止，不选择其他推荐/预加载视频。

页面解析失败时，可点击 **扫描页面视频** 读取 video/source 的 HTTP 链接。要发现 HLS/DASH，开启网络发现、人工授权站点权限、刷新播放后再扫描，选择正确资源提交。`blob:` 不是通用下载地址；播放器的单个音频/视频分流也不保证完整音画，优先网页解析。网络发现从授权后开始，不追溯旧请求；列表最多 60 个资源，刷新清空。不会自动下载推荐流中的所有视频。

主动页面扫描还读取当前页面 Resource Timing 中已加载的 MP4/WebM/HLS/DASH 和抖音 CDN 视频 URL 元数据，帮助发现 `blob:` 播放器背后的媒体；被动扫描本身不请求详情接口、不监听响应正文或读取 Cookie；明确下载操作的单次当前作品详情读取见上文。这与开启后监听的新网络请求不同，列表可能含预加载视频，必须人工核对选择，不自动批量下载。签名查询参数原样交给下载器，不在聊天或诊断报告中展示。抖音 `modal_id` / `vid` 页面地址会转换为 `/video/<id>`；直链及其签名保持原样。

进入 **拉片**，左侧搜索和选择记录，右侧播放/拖动进度、打开来源、保存媒体副本、编辑笔记和分镜。点击 **保存笔记** 后显示磁盘保存反馈；未保存切换会提示。点击 **添加分镜** 自动取当前播放位置，再填写开始秒数、结束秒数和描述；可播放该分镜或移除。秒数非负，结束严格大于开始。接口中的分镜格式为 `[{"start":0,"end":3.5,"text":"开场钩子"}]`。导出 JSON 含记录及笔记历史，不包含视频二进制、连接码或临时签名 URL。

扫描后显示资源可得的分辨率、时长、大小，并提供 **预览所选视频**。大小只采用网络响应的完整 Content-Length 或 Content-Range 总量，无法确认时显示未知，不把分片大小或传输开销当作整片大小。流媒体及分轨可能需要下载合并后播放。入库后显示实际文件大小、容器、时长和分辨率；属性由 FFmpeg 读取最终文件，旧记录可在浏览器加载后补显分辨率。插件显示排队、下载、完成或脱敏失败原因，完成后链接直接打开该记录播放器。

## 接口与持久化

同源本机网页可使用接口；插件/AI 客户端通过 `Authorization: Bearer <pairing token>` 访问。仅对选定本机工作台读写，不注册或覆盖其他 MCP。此子 skill 当前提供 REST，没有新增或伪称已启用的 MCP 工具。

- `GET /api/workbench/health`：服务和依赖状态。
- `GET /api/workbench/records`：`{records:[...]}`，包含 ready/queued/downloading/failed 状态。
- `POST /api/workbench/records`：`{action:"create",url,sourceUrl?,title?,authorized:true}`；先验证公网 HTTP/HTTPS，再建立持久记录并入队。临时下载 URL 只在内存与 worker stdin 中，不写入记录。来源只保存规范化非敏感地址。
- `POST /api/workbench/records`：`action:"browser-start"` 先创建授权的浏览器下载任务，返回本任务随机文件名；`action:"browser-finish"` 只导入与之对应的新视频文件，不能用作任意路径导入。
- `POST /api/workbench/records`：`{action:"update",id,revision,notes,shots}`；原子更新笔记，保留旧版历史；revision 不匹配则拒绝。
- `GET /api/workbench/media?id=<id>`：仅下载完成的内部媒体，支持 Range 拖动播放。
- `GET /api/workbench/pairing`：仅同源本机页面能取连接码；本机 content script 同源读取并自动配对，扩展 Origin 仍不能直接读取。
- `/workbench-install`：Chrome 安装/更新帮助；同源 `GET /api/workbench/extension-info` 返回当前目录/版本，`POST /api/workbench/extension-setup` 只打开固定 Chrome 安装入口和目录。

SQLite 为 `workbench/records.sqlite3`，媒体 `workbench/media/<id>/video.<ext>`；本机解析任务单并发、最多 20 项未完成任务、单任务超时 20 分钟、目标单文件限额 2 GiB（实际流媒体预估大小可能不可知，不作硬磁盘配额保证）。失败不自动重试，不删除记录；可能保留未完成分片供人工排查/清理。下载时 stderr 丢弃，错误对外脱敏；无需把签名链接或 Cookie 粘贴给 AI。首次公网上游 URL 拒绝内网地址，但此服务并非供不可信远程用户使用的网络代理，不能把其 URL 检查当作隔离所有上游重定向/分片的沙箱。

## 故障

- 连接失败：先启动同一套工作台，点击插件的“重新连接工作台”；不要求用户填写地址或连接码。旧服务须由启动器空闲重启加载路由；插件首次升级须在 Chrome 扩展管理重新加载一次。
- FFmpeg 未配置：在服务所用 Python 环境运行 setup_workbench.py --install-deps，或设置 SKILLTO_FFMPEG_LOCATION 为真实 FFmpeg 路径后重启。
- 401/403、登录要求、验证码、限流：停止该任务，遵守采集子 skill 的授权与人工同会话验证流程，不轮换身份规避限制。
- 抖音“要求新鲜 Cookie”：表示 yt-dlp 的详情接口未取得可用详情，不代表浏览器未登录，也不能通过安装 FFmpeg 解决。该提示只适用于明确提交的服务器网页解析任务；当前视频按钮应优先走浏览器通道，不再自动制造这类失败。需要会话时按采集子 skill 流程明确选择授权身份，不自动读取或导出浏览器 Cookie。
- 明确选定 Cookie：仅在遵守 crawler 的所有边界后配置 SKILLTO_WORKBENCH_COOKIE_FILE，必须 Netscape 文件且不属于受限身份；不自动导出 Chrome Cookie，不从文件系统搜索其他身份。
- 新视频已入库但浏览器不播放：容器或编解码器可能不受当前 Chrome 支持；记录保留原文件，勿假装下载等于转码兼容，可用本机播放器验证，再按明确需求转码。
- 服务重启：已完成记录与笔记保留，排队/下载中任务标失败，用户手动重新提交。
