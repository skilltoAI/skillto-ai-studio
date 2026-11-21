# STASS 程序迁移工作区

## Windows 单文件安装候选

维护端按下文从固定提交构建离线目录，再用同一份清单摘要生成安装 EXE：

```powershell
python apps/stass/build_setup.py --package <离线包目录> --manifest-sha256 <清单摘要> --output <输出目录>/Setup.exe
```

安装 EXE 默认安装 Codex Skills，并尝试打开桌面窗口。带 `--result-file <路径>` 获取机器可读回执，包含版本、提交、清单摘要、启动入口、配置绑定命令、服务 URL 和各步骤状态。显式授权本机 Codex MCP 配置时可加 `--register-mcp`。已有实例升级应先确认后台任务完成并从原工作台停止服务。发行说明公开安装器 SHA-256、签名状态及实机验收范围。

当前状态：开发中，不能替换生产入口。程序源码已集中到 modules，保留原实现作为迁移测试基线；旧技能副本尚未移除。

已实现：标准 Streamable HTTP MCP、12项语义工具、共享业务API、身份/令牌/Host/Origin检查、独立MCP客户端、短ID存储、不可变视图、SQLite一致性快照与文件校验。

尚未完成：网页与短路由的完整集成、浏览器本机工具接入新MCP、配对界面、素材分块MCP、资源引用转换、启动器切换、技能客户端替换、生产切换与完整新入口端到端验收。不得把旧模块测试通过描述为新工作台已交付。

## 开发运行

Windows 环境依赖锁在 requirements-windows.lock.txt。服务需要 STASS_DATA_ROOT 指向隔离数据目录，STASS_TOKEN_FILE 指向受保护令牌文件（至少32字符），STASS_ALLOWED_HOSTS 明确列出允许访问的主机与端口。不得将生产数据用于开发测试。

从本目录运行：`python -m uvicorn service:app --host 127.0.0.1 --port 8080`。局域网部署须显式配置监听地址与允许主机；当前不执行生产部署。

客户端 `python client.py pair --url <STASS-URL> --token-file <受保护文件> --profile <本机配对配置>`；`list` 和 `call --tool <名称> --arguments <JSON文件>` 使用已配对实例，身份变化拒绝发送凭据。

## 验证

`python run_regression.py <仓库外或忽略目录的日志目录>` 使用隔离数据根目录运行各模块。报表数据库、原采集快照和猫抓上游需显式配置，缺失时跳过必须单独列出。

`python -m unittest discover -s . -p test_migration_routing.py -v` 验证快照、WAL、短ID和URL；`python -m unittest discover -s . -p test_service.py -v` 验证MCP与API共享数据和访问边界。

`migration.py --source <旧数据根> --destination <空目标>` 仅生成演练副本；其 manifest 明确列出尚未迁移的浏览器档案、外部资源及数据库。它不是正式切换命令。

## 共享实例开发验证

新增用户级共享状态、Windows命名互斥锁、服务监督器和按宿主独立凭据。
`runtime_control.register_development` 仅用于显式隔离开发目录，不是正式安装命令。
服务的启动/复用/停止通过共享根配置管理，三个stdio桥接客户端访问同一HTTP MCP。
根目录可运行 `npx --yes --package=. stass status` 或 `doctor`；已经注册开发程序时支持 `start`、`stop`。
尚未提供 install/update/rollback/uninstall，未实现命令明确失败；不能把npx帮助或诊断通过当作一行完整安装通过。

新增测试：`test_runtime_state.py`、`test_runtime_control.py`、`test_multi_client.py`，分别验证跨进程状态、真实服务生命周期及三个独立凭据的stdio/HTTP读写与撤销。

## 网页接入进度

`/STASS/` 已连接原生页面和共享模块适配；首次访问进入 `/STASS/pair`。本机管理令牌可通过 `/STASS/api/v1/pair-code` 获取一次性配对码，手动POST后建立网页会话。完整启动器配对入口仍待接入；不将此开发页面作为生产替换入口。真实Chromium测试覆盖导航、品牌资产与表格基本读写，短链和模块全功能仍需验收。

## 构建离线 Windows x64 候选包

在 Windows x64 构建机准备 Go 1.25+、Python 3.13 x64、Node.js 22+、Bun 1.4.2、Rust stable MSVC 及 Visual Studio C++ Build Tools。启动器用 Wails v2.17.0 和原生 HTML/CSS/JS。Beam 使用上游锁文件及固定 0.6.2 提交，通过 Electron 原生打包。

准备官方 Python 3.13.17 amd64 嵌入式 ZIP、锁定 requirements 的 Windows wheels，以及微软签名的 [WebView2 Evergreen Standalone x64 安装程序](https://developer.microsoft.com/microsoft-edge/webview2/#download-section)。选择 Standalone Installer，在线 Bootstrapper 无法用于离线安装。

```powershell
.\apps\stass\build_launcher.ps1
python apps/stass/build_beam.py --output runtime/beam-0.6.2
python apps/stass/build_offline.py --output runtime/stass-candidate --version 0.4.8 `
  --python-zip <官方Python压缩包> --wheels <wheel目录> `
  --launcher 'runtime/Skillto.ai Studio.exe' --beam-build runtime/beam-0.6.2 `
  --webview2 <WebView2独立安装程序>
```

若已下载源码，可将 [固定提交 ZIP](https://codeload.github.com/BeamRecorder/Beam/zip/808c3b2c091a3270f1417974ea16b5f16ad00159) 通过 `--archive` 传给 Beam 构建脚本。使用可信的微软及 GitHub 官方构建输入。Beam 构建从上游保留录屏、编辑和导出，应用工作台品牌补丁并关闭独立自动更新。候选包包含 Beam 完整运行目录、许可证、对应源码和 WebView2 离线安装程序，全部计入发行清单摘要。交付时保留对应源码和第三方声明。候选包及摘要不提交 Git。

安装后，启动器相册右上角的「3D 录屏」打开独立 Beam 窗口。工作台服务停止时仍可使用该入口。录像及工程默认位于当前用户「视频」目录下的 `Skillto.ai Studio Beam`，导出位置可在 Beam 中选择。原有 Beam 安装和工程保留在其既有目录。用户只需 WebView2 Runtime 和包内运行环境。未下载的字幕模型等资源需要联网获取。真实录屏、全套设备和干净机器验收必须单独记录。

管理员测试先设置 `STASS_TEST_OFFLINE_PACKAGE` 指向解压目录，再运行 `python -m unittest discover -s apps/stass -p test_offline_package.py -v`。该测试会建立隔离目录，从包内运行时启动真实程序，重复安装并检查数据，最后调用已安装 EXE 停止实例。当前包不覆盖生产数据迁移、宿主自动注册及升级回退。

## AI资产与飞书视频

顶部 AI资产 包含 Motion 模版、AI红白模库和暂空的剪映AI模版库。红白模卡片同时显示提示词与可播放视频，支持复制提示词、下载视频及搜索。旧 Motion 链接和数据保持兼容。

飞书视频需要公开分享权限、可访问飞书的网络和服务端 Playwright 的 Chromium（`python -m playwright install chromium`）或已安装 Chrome；离线包含 Playwright Python 依赖，不捆绑浏览器。服务使用全新匿名访客上下文取得临时访问授权，只在内存保存请求头；视频分段在线转发，不落本地缓存。用户主动下载才写入浏览器下载位置。公开权限变化时显示失败并保留来源链接。

通过已连接 STASS 的 MCP 发现 `ai_assets_action`，先 dryRun 再录入元数据；详见 [AI资产 Skill](../../skills/skillto-ai-studio-assets/SKILL.md)。
