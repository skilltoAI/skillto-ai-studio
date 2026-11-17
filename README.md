# SkillTo INT / Skillto.ai Studio

面向 Codex 与 Claude Code 的内容采集、媒体分析、视觉工作流和本地内容工作台技能集。
仓库分发 **1 个父技能 + 18 个子技能**，以 `skills/` 为源码；支持 Windows、macOS、Linux
复制安装和 Claude Code 插件安装。外部服务、生成工具与完整 Studio 网页有独立运行依赖。

代码仓库：[Codeup · skillto-ai-studio](https://codeup.aliyun.com/6856a1da33ca8867a4350914/skillto-ai-studio)。
私有仓库需要每位使用者获得读取权限并配置自己的 Git 认证。

- [统一安装、升级、回滚与故障排查](skills/skillto-int/references/installation.md)
- [18 个子技能逐项配置与验收](skills/skillto-int/references/child-setup.md)
- [宿主兼容性与外部依赖](skills/skillto-int/references/compatibility.md)

## 技能清单

| 技能 | 用途 | 安装与验收 |
| --- | --- | --- |
| [skillto-int](skills/skillto-int/SKILL.md) | 父入口，按任务路由到所需子技能 | [指引](skills/skillto-int/references/installation.md) |
| [skillto-int-douyin-xhs-crawler](skills/skillto-int-douyin-xhs-crawler/SKILL.md) | 获授权的抖音/小红书采集、账号验证与近期内容分析 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-douyin-xhs-crawler) |
| [skillto-int-tiktok-crawler](skills/skillto-int-tiktok-crawler/SKILL.md) | TikTok 账号/关键词采集、多语言扩展、快照和热门分析 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-tiktok-crawler) |
| [skillto-int-workbench](skills/skillto-int-workbench/SKILL.md) | 基于猫抓的工作台插件、双下载入口、视频选段预览导出、拉片播放与笔记 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-workbench) |
| [skillto-int-table](skills/skillto-int-table/SKILL.md) | Skillto INT Table（工作台）子技能；Skillto.ai Studio 的多媒体表格、人工评审与语义 MCP CRUD | [指引](skills/skillto-int/references/child-setup.md#skillto-int-table) |
| [skillto-int-reports](skills/skillto-int-reports/SKILL.md) | 本地 Metabase 报表、图表及归档/恢复 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-reports) |
| [skillto-int-style-library](skills/skillto-int-style-library/SKILL.md) | 14 类可拆解美术风格的场景检索、规范录入、元素独立动效与 Remotion/Motion 技术指南 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-style-library) |
| [skillto-int-motion](skills/skillto-int-motion/SKILL.md) | Motion 模板库、.motion 工程检查、标签评分及已支持模板的实际预览与 MP4 制作 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-motion) |
| [skillto-int-rewrite](skills/skillto-int-rewrite/SKILL.md) | 有来源证据的稿件研究、逐字稿、二创版本和人工评审 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-rewrite) |
| [skillto-int-qwen38-media-analysis](skills/skillto-int-qwen38-media-analysis/SKILL.md) | 内网 Qwen3.8 图像理解、OCR、抽帧与分镜分析 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-qwen38-media-analysis) |
| [skillto-int-talking-head-edit](skills/skillto-int-talking-head-edit/SKILL.md) | 粗剪口播与 SRT 的 HyperFrames 规划、Remotion 编辑及渲染 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-talking-head-edit) |
| [skillto-int-explainer-storyboard](skills/skillto-int-explainer-storyboard/SKILL.md) | 知识、科普、新闻类短视频的证据清单、节拍图、视觉系统、分镜与审片 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-explainer-storyboard) |
| [skillto-int-xiaoyu-cover](skills/skillto-int-xiaoyu-cover/SKILL.md) | 小与封面图，含品牌参考及独立构图的 3:4 / 4:3 PNG | [指引](skills/skillto-int/references/child-setup.md#skillto-int-xiaoyu-cover) |
| [skillto-int-workflow-mcp](skills/skillto-int-workflow-mcp/SKILL.md) | Creator MCP 工作流编辑、素材绑定、校验、运行与结果读取 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-workflow-mcp) |
| [skillto-int-character-card](skills/skillto-int-character-card/SKILL.md) | 新角色定妆照/三视图提示词与直接引用核验 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-character-card) |
| [skillto-int-depth-gray-replica](skills/skillto-int-depth-gray-replica/SKILL.md) | 原片采集、硬切核验和逐秒拆解；执行范围止于采集与分析 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-depth-gray-replica) |
| [skillto-int-depth-gray-workflow](skills/skillto-int-depth-gray-workflow/SKILL.md) | 原片到本地深度视频、音频、分镜和 SaaS 替换工作流 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-depth-gray-workflow) |
| [skillto-int-h3-workflow](skills/skillto-int-h3-workflow/SKILL.md) | 原片直驱 H3 角色替换工作流及服饰道具证据 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-h3-workflow) |
| [skillto-int-ip-store](skills/skillto-int-ip-store/SKILL.md) | 角色卡、干净场景图及跨视频素材库 | [指引](skills/skillto-int/references/child-setup.md#skillto-int-ip-store) |

## 快速安装

需要 Git、Python 3.10+ 和目标客户端。在终端运行（macOS/Linux 可用 `python3`）：

```sh
git clone https://codeup.aliyun.com/6856a1da33ca8867a4350914/skillto-ai-studio.git
cd skillto-ai-studio
python scripts/install.py --list
python scripts/install.py --agent codex --dry-run
python scripts/install.py --agent codex
```

新 Codex 默认安装到 `~/.agents/skills`。已部署到旧 `$CODEX_HOME/skills` / `~/.codex/skills`
的用户显式加 `--codex-legacy`；安装器不自动迁移旧副本。Claude Code 改用：

```sh
python scripts/install.py --agent claude
```

Windows 也可运行 `.\install.ps1 -Agent codex`，macOS/Linux 可用
`sh install.sh --agent codex`。按需安装传 `--skill <完整技能名>`；项目安装用
`--destination <project>/.agents/skills` 或 `<project>/.claude/skills`。
现有同名目录会阻止覆盖，升级前按安装指引备份并比较。安装器不自动安装业务依赖或配置 MCP。

新开会话后，Codex 调用 `$skillto-int`，Claude Code 直接安装调用 `/skillto-int`。

## Claude Code 插件安装

与直接复制方式二选一；先确保本机 Git 能读取该仓库：

```sh
claude plugin marketplace add https://codeup.aliyun.com/6856a1da33ca8867a4350914/skillto-ai-studio.git
claude plugin install skillto-int@skillto-int-marketplace
claude plugin list
```

在新会话调用 `/skillto-int:skillto-int`，子技能如 `/skillto-int:skillto-int-table`。
离线注册、本地试用、升级和卸载见[统一安装指引](skills/skillto-int/references/installation.md)。

## 可用范围

技能文件安装与真实业务就绪分开验收。风格库、角色提示词和分镜规划可以离线使用；
表格 stdio MCP 只需 Python 标准库，另外注册到客户端。采集需要授权会话与浏览器；
SaaS 工作流需要 Creator MCP、自己的 Key 和对应权限。

目前完整 Studio HTTP 网页仍依赖未打包的 `douyin_tracker.review_web` 与研究页资源；
Qwen 客户端固定维护者局域网部署；小与配音依赖外部 Windows 部署；封面与角色库指定的
`image_gen` 不由本仓库提供，普通 Claude Code 无法仅靠此插件获得它。
各项准备、支持边界和验收条件均列在[子技能安装表](skills/skillto-int/references/child-setup.md)。
不能把整套安装成功描述成所有业务已经跨平台验证。

## 维护与验证

```text
skills/                  可安装父技能和全部子技能
scripts/install.py       跨平台安装器（自动发现技能）
scripts/validate_repo.py  结构、路由、文档覆盖、链接和分发检查
tests/                   安装行为测试
.claude-plugin/          Claude 插件和 marketplace 清单
install.ps1 / install.sh 平台入口
AGENTS.md / .claude/CLAUDE.md  仓库协作规则
CONTRIBUTING.md           验证与发布约定
```

```sh
python scripts/validate_repo.py
python -m unittest discover -s tests -v
git diff --check
claude plugin validate .claude-plugin/plugin.json
claude plugin validate .
```

维护约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。运行数据、Cookie、API Key、浏览器档案、
数据库与 EXE 不进入分发。安装不授予采集、远端写入、付费运行或发布权限。
当前未声明整个仓库的开源许可证，不推定 MIT 等授权；品牌资源和 Cat Catch 等外部项目
保留各自权利与许可约束。

本次验证范围与已知部署限制见 [0.2.0 分发记录](docs/DISTRIBUTION.md)。
