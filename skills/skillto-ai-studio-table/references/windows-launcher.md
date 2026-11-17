# Windows 双击启动器（Go）

双击本技能根目录的 **SkillToTable.exe**，或桌面的 **启动本地报表.exe**。
它会启动本机 HTTP 报表服务，等待就绪后通过 Windows 默认浏览器打开
http://127.0.0.1:8880/。已有健康服务时直接复用；不会重复启动后台进程。
启动器会保留一个 **Windows 任务栏控制窗口**。点击任务栏图标可显示窗口，
使用“启动服务”“关闭服务”“打开报表”按钮控制本地服务。
最小化窗口或关闭浏览器时，服务继续运行；关闭控制窗口（右上角 ×、Alt+F4、
或任务栏右键“关闭窗口”）会先停止服务，再退出程序。
固定到任务栏后，点击固定图标即可再次启动。重复启动会激活现有控制窗口。

## 本机配置

EXE 先读取其旁边的 `launcher.local.json`；没有时读取
`%USERPROFILE%\.codex\skills\skillto-ai-studio-table\launcher.local.json`。
因此桌面 EXE 可以独立复制，配置保留在已安装技能目录。
配置是本机路径，不能用于其他电脑，不能包含 Cookie、API Key 或其他凭据。

配置项：

| 字段 | 含义 |
| --- | --- |
| pythonExecutable | 现有 Python 环境的 python.exe 绝对路径 |
| serviceScript | 提供 Handler 类的现有本地 HTTP 服务脚本绝对路径 |
| workingDirectory | 本地项目工作目录 |
| dataRoot | 已存在的本地报表目录，不能误指向其他数据副本 |
| url | 默认 http://127.0.0.1:8880/，仅允许 127.0.0.1 |
| bridgeScript | 可选；默认配置目录下 scripts/launcher_service.py |
| catExtensionDirectory | 可选；本机已构建的猫抓工作台扩展目录。服务自动读取，用于安装/更新入口；不要求用户在插件配置端口或连接码。 |

启动器使用 Go 标准库编译；运行 EXE 不需要安装 Go。
当前版本是**服务启动器**，仍需要配置的 Python 环境、报表服务脚本及其资源。
它不会把 Python、报表数据和研究图片封装进 EXE，也不会自动采集视频。
从已安装技能目录重新构建时，应显式传入本机的 Python、服务脚本和项目路径。

## 构建和安装

在仓库中执行（需已安装 Go，Windows amd64）：

```powershell
.\skills\skillto-ai-studio-table\scripts\build_windows_launcher.ps1 -Install -Desktop
```

可通过参数指定 `-PythonExecutable`、`-ServiceScript`、`-WorkingDirectory`、
`-DataRoot` 和 `-InstalledSkill`。构建脚本运行 go fmt、go vet 和 go build，
使用 `-H=windowsgui` 生成无控制台 EXE。`-Install` 将启动器及其源码、桥接脚本、
本机配置复制到已安装的技能；`-Desktop` 将 EXE 复制到用户桌面。
源码位于 `scripts/windows/main.go`、`window.go` 和 `stop.go`，
使用 Go 标准库调用 Win32，启动器运行代码不依赖第三方 Go 模块。
构建时使用固定版本 `github.com/tc-hib/go-winres@v0.3.3` 生成图标资源；
首次构建需要联网下载该工具。Logo 未改动时复用已有资源文件，避免重复联网。
Logo 原图保存在 `scripts/windows/winres/logo.png`，
配置位于同目录 `winres.json`，重建会自动嵌入多个尺寸的 Windows 图标，
并通知资源管理器刷新 EXE 图标。
本机生成文件 `SkillToTable.exe` 与 `launcher.local.json` 不提交 Git；
部署技能源码后在目标 Windows 主机重新构建。

## 启动、复用与故障处理

- 首次启动：使用 Windows 进程接口隐藏启动 Python，最多等待 35 秒。
- 检测 `/api/launcher-health` 的服务标识和数据目录；同一服务会复用。
- 旧服务没有该健康端点时，仅在其 catalog 数据结构和现有页面资源标记均匹配时复用。
  旧接口不报告数据目录和进程号，日志明确记录为 legacy；需要严格目录验证时重启为新入口。
- 同时双击：使用同一端口的 Windows 互斥锁，避免重复启动。
- 端口被其他程序占用、数据目录不匹配、依赖文件丢失、启动失败：显示中文错误框并写日志。
  不关闭占用端口的其他程序；超时只结束本启动器创建的进程。
- 启动的 Python 子进程明确使用本地数据根目录，并清除远程 MCP 地址和 Key 文件环境变量。
- 本地桥接入口加载既有 Handler，保留图片、研究文档、schema 控件和原有表格接口。

日志：`%LOCALAPPDATA%\SkillToTable\logs\launcher.log`、`service.log`。
健康检查：http://127.0.0.1:8880/api/launcher-health。
使用控制窗口的“关闭服务”按钮停止后台服务；窗口会保留，可随时重新启动。
关闭控制窗口会停止服务并退出。关闭浏览器不会停止服务。
新服务通过随机命名的 Windows 事件接收关闭请求，等待当前 HTTP 请求完成后退出；
没有开放网页关闭接口。关闭操作核对服务标识、数据目录、进程号和事件名，
不结束其他占用端口的程序。旧版服务需要升级并重启一次才支持这一功能。

## 自动验收参数

```powershell
.\SkillToTable.exe --no-browser --quiet-errors --result-file C:\Temp\launcher-result.json
```

`--config <绝对路径>` 可测试独立配置；`--no-browser` 单次启动服务，不打开浏览器或控制窗口；
`--headless` 单次启动服务并打开浏览器，不保留控制窗口；
`--stop` 关闭匹配的本地服务后退出；
`--quiet-errors` 仅记录错误；`--result-file` 写入本次操作结果
（started/reused/error、服务 pid、浏览器调用结果、日志位置）。
这些是诊断参数，正常双击无需参数。控制窗口模式下，结果文件会随服务状态变化更新。
