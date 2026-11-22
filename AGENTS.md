# Repository instructions

每次 vibe coding（规划、开发、修复、重构、验证）必须先读取并遵循本项目
[技术规范.md](技术规范.md)，再按唤醒词、修改路径和影响累加读取专项规范。
范围扩大必须补读；必要时同一变更更新相关规范和总索引。
所有完成的逻辑变更必须更新统一 CHANGELOG.md、执行检查并本地提交；
每48小时成功同步 Codeup，失败不得记为已同步。
工作台迁移必须保留全部模块功能、业务数据和多媒体数据，逐项验收。

`skills/` is the source of truth. Keep the parent `skills/skillto-ai-studio/SKILL.md`
in sync with the child capabilities. Preserve each child's authorization and
production boundaries. Do not silently replace required external tools.

Keep skills as sibling folders with matching `name` frontmatter. Use relative
paths for bundled resources; resolve scripts from the loaded skill directory,
not a hard-coded Codex or Claude installation. Host-specific MCP/tool names are
capabilities to discover, not a promise that another client provides them.

Read `CONTRIBUTING.md` for validation and Git conventions. Do not commit runtime
state, credentials, collected media, research outputs, or local executables.
Do not overwrite unrelated existing changes. Publication and Git pushes require
an explicit user request; local preparation is allowed.

Do not synchronize all installed skills automatically. If a task includes updating
an installed copy, compare it with the repository and copy only the intended files.

## 个人工作站的本机运维授权

这是用户个人维护的程序和网站。项目更新后，执行者已获授权直接在本机安装、升级、
复装、停止、启动和重启 STASS 个人工作站服务及其启动器，无需再次确认。
操作前核对目标实例并等待该实例的在途任务结束。使用项目安装器或共享管理器正常停启，
保留业务数据和配置，并在完成后验证服务健康、运行版本和受影响功能。
Git 推送、对外发布及远程网站部署仍须明确授权。

## GitHub 主干发布

- GitHub 远端 `github` 只保留默认主干 `main`。获得明确推送授权后，只更新 `refs/heads/main` 并回读 SHA。
- 本地保留 `anycom` 作为开发分支，可在本地工作树验证后将已审查的代码推进到 GitHub `main`。
- GitHub 发布不影响 `origin` 和 `codeup` 的分支与凭据。清理远端非主干分支前先确认 `main` 已存在且为默认分支，并保留旧分支的本地引用。

## Codeup：拉取与推送凭据必须分离

以下名称是所有开发客户端必须使用的本机环境变量契约；只在文档中记录名称，
禁止记录密码、私钥内容或维护者机器的具体私钥路径。本地 `git commit` 不需要远端凭据。

| 用途 | 拉取 / clone | 推送（须明确授权） |
| --- | --- | --- |
| 仓库 URL | `CODEUP_FETCH_BASE_URL` | `CODEUP_PUSH_BASE_URL` |
| 用户名 | `CODEUP_FETCH_USERNAME` | `CODEUP_PUSH_USERNAME` |
| HTTPS 密码 | `CODEUP_FETCH_PASSWORD` | `CODEUP_PUSH_PASSWORD` |
| SSH 私钥文件绝对路径 | `CODEUP_FETCH_SSH_KEY_FILE` | `CODEUP_PUSH_SSH_KEY_FILE` |
| 认证方式 | `CODEUP_FETCH_AUTH_MODE` | `CODEUP_PUSH_AUTH_MODE` |

- `BASE_URL` 是完整、不含凭据的 Codeup HTTPS 仓库 URL。即使两方向指向同一仓库，也分别配置。
- `AUTH_MODE=https-password` 只使用同组用户名与密码；`AUTH_MODE=ssh` 只使用同组
  SSH 用户名 `git` 与私钥文件。SSH 模式的密码可以为空。公钥文本或 `.pub` 文件不能代替私钥。
- SSH 模式由同组 HTTPS URL 的主机与仓库路径构造 SSH 地址，并显式指定该组私钥；
  不采用其他项目的 SSH IdentityFile，不关闭主机密钥校验。
- 拉取不读取推送凭据作为回退，推送不读取拉取凭据作为回退；任何认证失败必须停止。
  不将两组凭据写入共享 Git Credential Manager，不在 URL、命令参数或日志中展开密码。
- Windows 使用当前用户环境变量；已启动的客户端可能没有新变量。
  `scripts/codeup_git.py` 优先读取当前进程，缺失时读取 Windows 当前用户环境变量，
  不要求将密码放入 `.env`、Git 配置或仓库文件。
- Codeup 网络操作必须通过上述脚本明确选择操作方向：`probe --scope fetch`、
  `probe --scope push`、`fetch`、`clone --destination <目录>`、`push --branch codex/<任务>`。
  只有用户明确授权主分支合并和发布时，允许用 `release --tag vX.Y.Z` 原子推送 main 和已验证标签。
  `probe` 只检查远端读取，不能证明写权限；`fetch` 不等于已合并或成功同步。
- 保留原 `origin`，不把 Codeup 凭据用于 GitHub。不自动推送、合并主分支、打标签或发布。
  详细操作和两天同步规则见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## Windows 安装与 SSH 身份

- 每次涉及安装、构建、依赖或宿主集成，检查根 README 能否让另一台 Windows 机器的 Codex/Claude 完整安装程序和全部技能；按技术规范读取启动器与部署规范，更新安装步骤、限制及验收记录。
- 本仓库正式指令文件名为 `AGENTS.md`，不另建不同步的 `AGENT.md`。
- 本项目推送使用用户 SSH 公私钥：`CODEUP_PUSH_AUTH_MODE=ssh`、`CODEUP_PUSH_USERNAME=git`，`CODEUP_PUSH_SSH_KEY_FILE` 指向本机具有仓库写权限的用户私钥。`CODEUP_PUSH_PASSWORD` 可为空，不作为 SSH 认证的回退。
- 公钥登记在 Codeup 对应用户账号；私钥只保留在本人机器。部署公钥即使可读取仓库，也不代表用户有推送权限；不得误用只读部署身份。注释不参与授权，公钥文本不能代替私钥文件。
- 当前拉取独立使用 `CODEUP_FETCH_AUTH_MODE=https-password` 及对应 `BASE_URL`、`USERNAME`、`PASSWORD`；该模式不读取 FETCH 的私钥字段。配置值只在本机保存，每位安装者配置自己的认证，不分发维护者账号。
- 推送成功必须回读指定远端分支提交并与本地比较；读取探测不等于写权限验证。私钥文件名含其他项目名称不决定用途，以环境变量显式选择和 Codeup 授权为准。
