# 安装、更新和启动

## 当前产品：猫抓工作台修改版

用户已经确认猫抓发现/下载可用，日常产品以它为引擎，不再退回旧实验插件。名称为 **SKillto.ai|工作台**；源码 overlay 在 `assets/cat-workbench/`。保留上游 GPL-3.0 许可与署名，品牌页与版权页分开。

构建前明确选择官方源码和稳定运行目录，比较并备份已有改动；然后从加载的 skill 执行：

```powershell
& <python> <loaded-skill>/scripts/build_cat_extension.py --source <cat-catch-source> --destination <stable-extension-directory>
```

构建脚本固定并检查上游基线，复制自有 UI overlay 和指定集成片段，不替换工作台数据、不安装 Chrome。已加载旧的“猫抓 · 抖音本地版”时，在 Chrome 扩展管理对原卡片点击一次重新加载，更新后显示 **SKillto.ai|工作台**、版本 `2.7.4-skillto.3`。不要让用户重新配置地址/端口或安装第二份。首次加载则选择构建输出目录，不能选择 overlay 目录。

在启动器的本机配置中可设置 `catExtensionDirectory` 为该目录；这是部署者配置，服务启动时自动读取并用于安装页目录，不让终端用户填写。插件自行发现本地工作台并通过同源 content script 配对。CLI 控制 Go GUI 启动器须等待 stop/start 命令完成，再验证健康接口。

验证 `scripts/test_cat_workbench.py`，其中官方源码位置通过 `CAT_CATCH_SOURCE` 明确提供；仓库已有参考源码时可用默认位置。真实隔离 Chrome 测试覆盖欢迎页同意交互、只有两个下载目标、可视选段、普通下载不入库、片段导出不入库、正确画面与时长、保存至拉片并播放。当前片段导出仅支持普通 MP4/WebM 等视频；HLS/DASH 清单显示不支持，不冒充完整下载。

以下 0.2/0.3 说明保留为早期实验客户端参考；不要将它的目录当成当前猫抓产品的更新目录。

## 同一工作台

`skillto-int-table` 与本子技能共享本地 HTTP 服务、启动器和数据根。日常使用双击原工作台启动器，拉片入口为同源 `/breakdowns`；不要为用户另配第二个端口。升级前检查正在下载的任务、浏览器用户和其他活跃操作，空闲后通过现有启动器重启，使 `WorkbenchMixin` 的路由生效。数据目录不变，不通过删除锁文件启动多个实例。

本机旧的独立 8891 是历史过渡方案，不是插件的第二套必填配置。独立运行仅保留给明确需要的客户端：`<python> <loaded-skill>/scripts/workbench.py --port <port> --data-root <directory>`；在该本机工作台页面打开插件后会自动学习实际 origin。

## 自动连接

0.2.0 起没有地址、端口和连接码输入框。插件在本机工作台页面通过隔离 content script 校验健康标识，并同源读取已有 pairing 接口，将 origin 和连接信息交给自己的后台。首次使用或连接失效时，插件自动短暂打开本机工作台完成此流程。连接码不出现在 URL、页面广播事件或聊天中；服务继续拒绝扩展 Origin 和跨站直接读取 pairing。默认发现启动器的 8880；其他本机端口从打开的工作台页面学习，不要求用户填写。

插件只自动连接 127.0.0.1，不搜索浏览器档案、导出 Cookie 或选择采集身份。所有下载仍须用户确认保存授权；网络发现的额外站点权限仍由 Chrome 确认。

## 部署与依赖

以 `skills/` 为源码，只比较、备份、同步本次修改的文件到实际运行副本。脚本从加载的 skill 目录解析资源，不假设其他客户端的安装位置。服务 Python 环境运行：

```powershell
& <python> <loaded-skill>/scripts/setup_workbench.py --install-deps
```

该显式操作安装 `yt-dlp[default]`、`imageio-ffmpeg`，不把可执行文件纳入分发。FFmpeg 依次使用 `SKILLTO_FFMPEG_LOCATION`、PATH、imageio-ffmpeg。检查时不带 `--install-deps`。

## Chrome 安装和升级

用户要求安装或更新时，Agent 应先完成部署并尝试当前客户端可用的 Chrome UI 操作；有操作能力时直接完成已授权的安装/重新加载，不再要求用户重复安装。不能把文件复制成功、隔离测试浏览器加载成功说成普通 Chrome 已更新。不得编辑 Chrome 的 Preferences、强制安装策略或绕过其权限确认。

工作台提供 `/workbench-install` 图文步骤、版本、实际插件目录和复制按钮。「打开 Chrome 扩展管理与插件文件夹」调用本机固定安装入口；不会替 Chrome 批准安装。

如当前工具无法控制普通 Chrome，明确说明实际阻碍，并把以下最小步骤交给用户：

- 已安装：打开 `chrome://extensions`，找到 **Skillto.ai工作台**，点击该卡片的圆形刷新图标 **重新加载**；回视频页刷新一次，再点击绿色 Logo。
- 首次安装：在该页面开启开发者模式 → 加载已解压的扩展程序 → 选择安装页给出的、直接包含 manifest.json 的 `assets/extension` → 在工具栏拼图里固定插件。

用户不需要复制连接码、配置端口或下载其他项目。加载 0.2.0 后，后续源码升级时后台检查服务公布的扩展版本并调用自己的 `runtime.reload()`；重新打开插件验证实际版本。首次从旧 0.1.x 升级仍需要 Chrome 加载一次新后台代码。

## 权限与验证

必选 activeTab、scripting、storage、webRequest 以及既有 127.0.0.1 主机访问；同源自动连接不增加 cookies、debugger、management 或 nativeMessaging 权限。广泛 HTTP/HTTPS 权限仍可选，仅网络发现按钮申请。0.3.0 增加可选 downloads 权限，在用户首次点击浏览器下载按钮时请求，不新增 Cookie、debugger 或 management 权限；Chrome 自己处理媒体请求，扩展不提取会话凭据。

0.3.0 的普通视频保存由 Chrome 完成并自动导入；HLS/DASH 清单仍由本机 yt-dlp/FFmpeg 合并，不宣称浏览器已下载清单中的全部分片。

运行 `scripts/test_workbench.py`、`scripts/test_extension.py`，以及 Node 的 `scripts/test_connection.cjs`、`scripts/test_discovery.cjs`。真实扩展测试使用隔离用户目录和临时媒体，验证无手工配置的连接/失效恢复、资源属性、预览、下载状态和入库播放；不代表普通 Chrome 已安装，也不代表四个平台都已实测可用。
