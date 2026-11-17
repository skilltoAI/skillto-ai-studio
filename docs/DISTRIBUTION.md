# 0.2.0 分发记录 · 2026-11-17

本次整理 1 个父技能与 18 个子技能，发布目标为
[Codeup skillto-ai-studio](https://codeup.aliyun.com/6856a1da33ca8867a4350914/skillto-ai-studio)。
此版本号是 Claude 插件版本，不代表创建了 Git 标签或官方插件目录条目。

## 来源与范围

以维护仓库提交 `4750869` 所在工作区的 `skills/` 当前源码为来源，纳入当前父子技能、
可复用脚本、必要品牌资源、参考文档和既有源码测试，并更新安装文档和安装器。
这是向空 Codeup 仓库导入的分发快照，不重写原维护仓库历史，不提交原工作区的其他任务产物。

已安装的父入口在盘点时列出 17 个子技能，仓库新增的
`skillto-int-explainer-storyboard` 已包含在本次 18 项清单中。未批量同步本机安装副本。

主要变更：

- 提供 [统一安装指引](../skills/skillto-int/references/installation.md) 与
  [全部子技能配置/验收表](../skills/skillto-int/references/child-setup.md)。
- Codex 默认使用 `.agents/skills`；保留 `--codex-legacy` 显式旧目录模式。
- 增加 `--list`，继续支持单技能、自定义目录、预检和拒绝覆盖。
- 排除备份、缓存、本机配置与运行状态；使用 Codeup URL 与 Claude 插件版本 0.2.0。
- 维护规则、父路由、兼容性表与文档覆盖检查同步更新。

## 验证证据

在 Windows、Python 3.13.13、Codex CLI 0.167.0-alpha.3.2、Claude Code 2.1.326 环境执行：

- 仓库结构、父子路由、19 个 README 链接、18 个安装章节、相对资源链接与 Python 语法检查通过。
- 安装行为 13 项测试通过，包括冲突时不写入、复制失败不暴露残缺技能、实际资源内容比对、
  新/旧默认目录、显式目录覆盖默认值、单技能安装及敏感运行文件排除。
- PowerShell 分别实际安装 19 项到隔离 Codex/Claude 目录；Git Bash 的 Shell 入口实际安装通过，
  目标路径含空格；未改动用户实际安装目录。
- Codex skill-creator 的 quick_validate 对 19 个技能通过。
- Claude 插件和 marketplace 默认清单验证均通过，发现全部 19 项命名空间技能。
- `git diff --check` 通过；分发源码按文件清单审查并检查凭据模式，未包含私钥、Token、
  Cookie、数据库、本机 EXE、浏览器会话、采集媒体或研究产物。

Claude 的额外官方目录上架检查会提示缺少整个插件的许可证声明和目录图标；这不影响
默认清单验证或私有 Git marketplace 使用。本次只上传 Codeup，不提交官方插件目录，
不替权利人擅自添加开源许可证。

## 验证边界

本机没有执行 macOS/Linux 原生客户端验收；Git Bash 和标准库安装测试不能替代这些验收。
仓库保留可选 GitHub 三系统 CI 配置，Codeup 不会自动执行 GitHub Actions。
未触发真实账号采集、收费生成、远端业务写入或维护者服务重启。

完整 Studio 网页依赖未分发的外部模块和历史资源，Qwen 是固定 LAN 部署，
部分配音为维护者 Windows 环境，封面和角色库指定的 `image_gen` 并非通用客户端能力。
具体缺项和可用阶段已在安装表标明。本次交付是可安装的技能分发与如实的部署指引，
不声称完整 Studio 产品已经成为自包含、全平台的一键运行包。
