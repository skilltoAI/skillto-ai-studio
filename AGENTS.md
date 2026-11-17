# Repository instructions

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
  `probe` 只检查远端读取，不能证明写权限；`fetch` 不等于已合并或成功同步。
- 保留原 `origin`，不把 Codeup 凭据用于 GitHub。不自动推送、合并主分支、打标签或发布。
  详细操作和两天同步规则见 [CONTRIBUTING.md](CONTRIBUTING.md)。
