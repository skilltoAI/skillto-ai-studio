# 安装与升级（Codex / Claude Code）

本指引对应仓库的 **1 个父技能 + 18 个子技能**。完整清单及每项的依赖、配置、
验收见 [子技能安装表](child-setup.md)，能力差异见 [兼容性说明](compatibility.md)。
技能文件可在 Windows、macOS、Linux 安装；外部模型、浏览器会话、MCP 和部分
Studio 部署组件需另外配置。不能把“19 个技能已加载”当作“19 项业务已验证”。

## 1. 获取源码

先安装 Git、Python 3.10+ 和目标客户端，并用自己的账号获得 Codeup 仓库读取权限。
Windows 下若 `python` 不可用而 `py -3` 可用，可把以下 `python` 替换为 `py -3`；
macOS/Linux 通常使用 `python3`。不要依赖其他人的 Python 绝对路径。

```sh
git clone https://codeup.aliyun.com/6856a1da33ca8867a4350914/skillto-ai-studio.git
cd skillto-ai-studio
python --version
python scripts/install.py --list
```

仓库私有时，每位用户配置自己的 Codeup HTTPS 凭据或 SSH 密钥；公钥用于登记，
不能代替客户端的私钥认证。不要把维护者私钥分发给安装者，也不要把 Token 写在克隆 URL。
已有 SSH 权限的用户可使用：

```sh
git clone git@codeup.aliyun.com:6856a1da33ca8867a4350914/skillto-ai-studio.git
```

如团队规定固定版本，先 `git checkout <已审核的提交SHA或实际存在的标签>`，
再安装。插件清单的版本号不等于已经创建了同名 Git 标签。

## 2. 选择一个安装位置

| 客户端 / 范围 | 技能根目录 | 选择方式 |
| --- | --- | --- |
| Codex 当前用户（默认） | `~/.agents/skills` | `--agent codex` |
| Codex 项目 | `<project>/.agents/skills` | `--destination` 指向这个目录 |
| Codex 已有旧目录 | `$CODEX_HOME/skills`，未设置时 `~/.codex/skills` | 明确加 `--codex-legacy` |
| Claude Code 当前用户 | `$CLAUDE_CONFIG_DIR/skills`，未设置时 `~/.claude/skills` | `--agent claude` |
| Claude Code 项目 | `<project>/.claude/skills` | `--agent claude --destination ...` |
| Claude Code 插件 | 客户端管理的插件缓存内 `skills/` | 使用下文插件方式，不另行复制 |

`~` 是当前用户主目录，Windows 对应 `%USERPROFILE%`。`--destination` 优先于上述默认值；
它必须是客户端实际会发现的**技能根目录**。任意自定义文件夹并不会自动被客户端加载。
新 Codex 默认位置以官方文档为准；本机已有 `~/.codex/skills` 的旧部署可继续显式使用旧模式。
安装器不迁移、不删除旧副本；升级前检查两个位置，避免同名技能重复出现。

## 3. 直接安装整套技能

推荐先预检，再安装。三种入口调用同一个 Python 安装器。

Windows PowerShell（在仓库根目录）：

```powershell
.\install.ps1 -Agent codex -DryRun
.\install.ps1 -Agent codex
# Claude Code 用户改为：
.\install.ps1 -Agent claude
# 已有 Codex 旧目录的部署改为：
.\install.ps1 -Agent codex -CodexLegacy
```

若 PowerShell 的脚本策略阻止 `.ps1`，直接使用 Python 入口，无需修改全机执行策略。

macOS / Linux / Git Bash：

```sh
sh install.sh --agent codex --dry-run
sh install.sh --agent codex
# Claude Code 用户改为：
sh install.sh --agent claude
```

跨平台 Python 入口及项目安装例子：

```sh
python scripts/install.py --agent codex
python scripts/install.py --agent claude --destination /absolute/project/.claude/skills
python scripts/install.py --agent codex --destination /absolute/project/.agents/skills
```

装好后应是 `<技能根>/skillto-ai-studio/SKILL.md` 与 `<技能根>/skillto-ai-studio-table/SKILL.md`
这样的同级目录。不要把仓库的整个 `skills/` 再套进一个技能，也不要只复制 `SKILL.md`
而遗漏 `scripts/`、`references/`、`assets/`。

安装器自动发现全部技能、预检整批目标、排除运行数据并保留资源。已有同名目标时整批拒绝
覆盖。它不安装 pip/npm 依赖，不启动服务，不配置 MCP，不调用付费服务。

## 4. 按需安装父技能和子技能

所有子技能均使用同一命令；把名称替换为 [子技能安装表](child-setup.md) 的完整标识：

```sh
python scripts/install.py --agent codex --skill skillto-ai-studio
python scripts/install.py --agent codex --skill skillto-ai-studio-table
```

Claude Code 将两条命令中的 `codex` 改为 `claude`；旧 Codex 两条都加 `--codex-legacy`。
PowerShell 对应 `-Skill <名称>`；Shell 支持 `sh install.sh <名称> --agent claude`。
需要自定义目录时，每条都传同一个 `--destination`。

父技能只负责路由，安装父技能不会拉取子技能。单装子技能也不会自动安装其兄弟技能或
外部依赖；按子技能安装表补齐需要的组合。已存在的父/子技能不用重复执行安装命令。

## 5. Claude Code 插件安装（二选一）

插件和直接复制方式任选其一。通过 Codeup 的 Git URL 注册 marketplace：

```sh
claude plugin marketplace add https://codeup.aliyun.com/6856a1da33ca8867a4350914/skillto-ai-studio.git
claude plugin install skillto-ai-studio@skillto-ai-studio-marketplace
claude plugin list
```

私有仓库认证复用当前机器的 Git 访问能力；先确认 `git ls-remote <仓库URL>` 成功。
HTTPS 不适用时，可改为自己有权限的 SSH Git URL。不要公开仓库来绕过权限问题。

离线/内网部署也可先复制完整审核过的仓库，再注册本地绝对路径：

```sh
claude plugin marketplace add /absolute/path/to/skillto-ai-studio
claude plugin install skillto-ai-studio@skillto-ai-studio-marketplace
```

仅试用当前源码而不持久安装：

```sh
claude plugin validate .claude-plugin/plugin.json
claude plugin validate .
claude --plugin-dir .
```

新会话中调用 `/skillto-ai-studio:skillto-ai-studio`，子技能用
`/skillto-ai-studio:skillto-ai-studio-table` 等完整命名空间。直接复制安装则调用 `/skillto-ai-studio`。
插件不会赋予 Claude Code Codex 专属工具，也不会安装外部技能或 MCP。

## 6. 首次验收

先新开会话，Codex 输入 `$skillto-ai-studio`，Claude Code 使用对应斜杠命令，请它：
“列出可路由的子技能，报告加载的绝对路径，只检查依赖，不启动采集或生成。”
整套应发现 19 个技能；按需安装只验收所选集合。通过父技能选一个离线能力（如风格检索）
确认相对参考文件可读，再按 [子技能验收项](child-setup.md) 验收业务依赖。

MCP 配置要显式指定本机 Python 与加载后的脚本路径。以表格为例，先设置独立数据目录，
然后按 [表格安装步骤](child-setup.md#skillto-ai-studio-table) 注册 stdio MCP。
不要把仓库、插件缓存或技能目录用作长期数据目录。

## 7. 升级、回滚、卸载

从旧 `skillto-int` / `skillto-int-*` 或其 Claude 插件升级到 0.3.0 时，先读
[改名迁移指引](rename-migration.md)。这次更换了技能与插件名称，普通的原名插件更新
不会自动切换到新名称。安装器遇到同一目标根目录中的旧名副本会停止，不删除旧副本。

直接安装的升级：记录当前提交与安装目录，将要更新的每个同名技能目录备份到
客户端发现目录以外；获取并审核新提交，先 `--dry-run`，再安装。整套升级保持父子
版本一致；有本地自定义时逐文件比较，不能用整目录覆盖解决冲突。
回滚时停止自己启动且空闲的相关服务，把新副本移到发现目录外，再恢复对应备份。
技能文件的回滚不等于业务数据回滚，运行数据另行备份。

插件升级使用客户端的 marketplace 更新与插件更新：

```sh
claude plugin marketplace update skillto-ai-studio-marketplace
claude plugin update skillto-ai-studio@skillto-ai-studio-marketplace
```

插件卸载用 `claude plugin uninstall skillto-ai-studio@skillto-ai-studio-marketplace`；直接安装
只移除本次安装的技能目录。不要删除用户数据、Cookie、MCP 凭据或其他技能。
需要移除本次新增的 MCP 时，先核对名称再单独移除；安装器不会处理这些状态。

## 8. 常见问题

| 现象 | 处理 |
| --- | --- |
| `Destination already exists` | 已有安装；按升级流程备份并比较，不增加强制覆盖参数 |
| Codex 列表没有技能 | 核对 `.agents/skills`、旧目录模式、项目启动目录与客户端实际加载路径；新开会话 |
| 技能重复 | 检查用户、项目、旧 Codex 目录或 Claude 插件中的同名副本，保留选定的一份 |
| Python 找不到 | 用 `python3` 或 `py -3` 检查版本；桌面客户端配置 Python 的绝对路径 |
| Claude 工具名不同或不存在 | 发现当前连接的实际能力；安装技能不会创造 MCP 或 `image_gen` |
| 新机器不能访问 `192.168.3.188` | 这是维护者 LAN 部署；按兼容性说明获得网络/服务，不能伪称已连接 |
| Studio 网页无法启动 | 检查外部 `douyin_tracker.review_web` 及研究页资源；本仓库的 stdio 表格 MCP 可独立运行，完整网页并非自包含安装包 |
| 私有 Codeup 无法克隆 | 请仓库管理员授予读取权限，配置本机 Git 认证；技能安装器不处理账号权限 |

2026-11-17 核对的官方说明：
[Codex skills](https://developers.openai.com/codex/skills/)、
[Claude Code skills](https://code.claude.com/docs/en/skills)、
[Claude marketplace](https://code.claude.com/docs/en/plugin-marketplaces)。
客户端版本变化时，以实际帮助和加载路径重新验收。
