# 维护与 Git 规范

## 修改范围

`skills/` 是分发源；已安装的 `~/.agents/skills`、旧 `~/.codex/skills`、
`~/.claude/skills` 或客户端插件缓存是运行副本。
新增技能使用 `skills/<name>/SKILL.md`，目录名与 YAML `name` 一致，保留简洁、
可区分的 `description`。脚本、参考文档、资源跟随各自技能；按需读取参考文档。
新增/移除子技能时，同时更新父技能路由、README 清单和兼容性说明。
安装器自动发现技能，不维护第二份硬编码名单。

保留子技能真实的业务边界和用户授权范围。部署地址、品牌和历史数据集若只属于
维护者环境，应明确标识；不能把安装成功写成功能已经可用。不要给其他客户端
虚构工具，也不要为了通用安装修改现有账号或覆盖 MCP 配置。

## 分支与提交

- 分支默认 `codex/<topic>`；团队人工分支可用 `feat/<topic>`、`fix/<topic>`、`docs/<topic>`。
- 提交格式建议 `type(scope): summary`，例如 `fix(install): include all discovered skills`。
  类型使用 `feat`、`fix`、`docs`、`refactor`、`test`、`chore`。
- 一次提交围绕一个可说明的变更；不要混入其他任务已有修改。按具体路径暂存，
  查看 `git diff --cached` 后再提交，不直接 `git add .` 收集工作目录。
- 不在共享分支 force push，不擅自 reset/clean 用户工作区。上传和发布须有明确请求。
- 未获用户明确上传指令时仅本地准备；获得指令后只推送其指定仓库和范围。

## 可以提交什么

提交技能说明、可复用代码、必要品牌参考和经过脱敏的例子。任务产物放在根目录的
`work/`、`research/`、`data/`、`runtime/`，这些目录不进入 Git。
Cookie、API Key、浏览器档案、`.env`、数据库、本机配置、构建 EXE 和缓存不提交。
可分发代码需要的静态数据应放入具体技能的 `assets/`，不要放在被忽略的 `data/`。
`.gitignore` 不会移除已跟踪文件；提交前仍需审查暂存清单。不要在检查输出中打印密钥。

文本使用 UTF-8 与 LF，由 `.gitattributes` 统一。Shell 入口保留可执行位；
不要只为换行符批量重写无关文件。

## 验证

在仓库根目录运行（安装与仓库检查只依赖 Python 3.10+ 标准库）：

```sh
python scripts/validate_repo.py
python -m unittest discover -s tests -v
git diff --check
```

技能结构修改后，如果装有 Codex skill-creator，再用其 `scripts/quick_validate.py`
逐个检查技能（该验证器需要 PyYAML；Windows 用 `python -X utf8` 避免系统编码干扰）；
它不能替代真实能力验证。修改业务代码时运行
对应技能已有测试，不对本次未改动的联网采集、远程服务或收费生成做真实调用。

Claude Code 本机可用时，检查两份清单：

```sh
claude plugin validate .claude-plugin/plugin.json
claude plugin validate .
```

本地查看插件：`claude --plugin-dir .`，在会话中检查技能列表并调用
`/skillto-ai-studio:skillto-ai-studio`。这是人工交互验收，不需要为验证自动运行外部工作流。

## 发布到 Codeup

1. 确定代码许可和品牌素材的再分发范围；当前仓库未声明开源许可证，不推定 MIT 等许可。
2. 审查变更、暂存清单和敏感信息；确认所需新技能/参考资源均已纳入提交。
3. 运行上述检查，并从干净提交导出/克隆到临时目录验证安装。
4. 插件版本使用 SemVer，同一次功能发布更新 `.claude-plugin/plugin.json`，
   完成可追踪提交后再打对应 `vX.Y.Z` 标签；正式发布前不要宣称已有 release。
5. 用户明确要求上传后，再推送约定分支/标签。当前分发地址为
   `https://codeup.aliyun.com/6856a1da33ca8867a4350914/skillto-ai-studio.git`；
   若仓库更名，同时更新 README、安装指引和插件元数据。私有仓库的用户各自配置认证，
   不随安装包分发维护者凭据。上传后回读远端提交，确认与本地一致。
6. 工作区有其他任务未提交内容时，保留原工作区与索引。可在隔离目录整理本次需要分发的
   源码快照，明确记录源提交和纳入范围，再验证、提交与推送；不把整个工作目录打包上传。

`.github/workflows/validate.yml` 是可选 GitHub 镜像的跨系统 CI，Codeup 不会自动执行它。
Codeup 流水线可运行同样的三条基础检查；本地测试无需任何服务凭据。
