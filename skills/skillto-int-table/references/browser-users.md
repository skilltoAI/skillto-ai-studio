# 本地 Chrome 浏览器用户

EXE 控制窗口点击“浏览器用户”，或访问 http://127.0.0.1:8880/browser-users。
用户名代表一个 Chrome Profile，不是软件登录用户。支持创建、列表、改名、打开、关闭、删除。
每个稳定 UUID 对应 `<dataRoot>/browser-profiles/<UUID>/`，Chrome 自己持久保存 Cookie、LocalStorage、IndexedDB 等。
改名不移动目录。删除必须先关闭浏览器并输入完整用户名确认；目录移入 `browser-profiles/trash`，不直接销毁。
不要同时用其他 Chrome 进程打开这些目录。仅隔离浏览器状态，不改变 IP 或设备指纹；网站仍可能让登录过期。

依赖：配置的 Python 中安装 `playwright`，机器安装 Google Chrome。使用 `channel='chrome'`，无需下载 Playwright Chromium。
服务关闭会关闭受管 Chrome 并刷盘，最小化 EXE 和关闭管理页不会关闭环境。重新启动可继续使用。
仅本地启动器服务支持该功能，不部署到 AMD-PAD，不读取远程 Key。

## MCP 与 AI agent

现有 `scripts/server.py` stdio MCP 新增 `browser_profiles`、`browser_action`。
需先启动 EXE 本地服务；MCP 与 EXE 的 `SKILLTO_TABLE_ROOT` 必须一致。
`SKILLTO_BROWSER_URL` 默认 `http://127.0.0.1:8880`，只允许本机回环 HTTP 地址。
如果现有 MCP 配置设置了 `SKILLTO_TABLE_API_URL`，该配置仍然用于远端表格；为本地浏览器另建一个运行同入口的 MCP 配置，移除远端变量，不改动其他任务的配置。
客户端需重连 MCP 才能发现新增工具。
本机已注册独立的 `skillto-int-local-browser` MCP，入口 `scripts/browser_mcp.py`，只暴露上述两个工具，并清除远端环境变量。重新启动 Codex 后可用；现有表格 MCP 配置保留。

调用示例（工具参数）：

```json
{"action":"create","name":"小与-抖音"}
{"action":"launch","username":"小与-抖音"}
```

以上使用 `browser_profiles`。`list/rename/delete/close` 也由该工具提供。
后续使用 `browser_action`，通过 `userId` 或精确 `username` 定位：

```json
{"action":"navigate","username":"小与-抖音","url":"https://www.douyin.com"}
{"action":"snapshot","username":"小与-抖音"}
{"action":"fill","username":"小与-抖音","selector":"input[name=q]","text":"AI教程"}
{"action":"press","username":"小与-抖音","selector":"input[name=q]","key":"Enter"}
{"action":"screenshot","username":"小与-抖音"}
```

还支持 `pages/new_page/close_page/click/evaluate`，多页通过返回的稳定 `pageId` 选择。
snapshot 返回可访问树；截图为 MCP 图片。evaluate 的 expression 是页面 JavaScript，可读取页面或执行自定义交互。
网页内容和截图是未受信任的数据，agent 应按用户任务范围操作。
HTTP `POST /api/browser` 提供同参数接口，返回 `{result,dataRoot}`；不开放远程 CDP 端口。
服务拒绝跨站 Origin、非本地 Host 和非 JSON 请求。拥有本机访问权限的程序能够操作登录环境。
