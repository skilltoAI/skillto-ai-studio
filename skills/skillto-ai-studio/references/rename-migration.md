# 0.3.0 改名与迁移

项目显示名统一为 **Skillto-AI-Studio**。技能目录、YAML `name`、命令与插件标识
按技能格式使用小写 **`skillto-ai-studio`**。共 1 个父技能和 18 个子技能，原后缀保留：

| 对象 | 旧名称 | 新名称 |
| --- | --- | --- |
| 父技能 | `skillto-int` | `skillto-ai-studio` |
| 全部子技能 | `skillto-int-<后缀>` | `skillto-ai-studio-<同一后缀>` |
| Claude 插件 | `skillto-int` | `skillto-ai-studio` |
| Marketplace | `skillto-int-marketplace` | `skillto-ai-studio-marketplace` |
| Codex 调用例 | `$skillto-int-table` | `$skillto-ai-studio-table` |
| Claude 直接安装调用例 | `/skillto-int-table` | `/skillto-ai-studio-table` |
| Claude 插件调用例 | `/skillto-int:skillto-int-table` | `/skillto-ai-studio:skillto-ai-studio-table` |

全部新名称见 [18 项清单](child-setup.md)。仓库 URL 仍为
`https://codeup.aliyun.com/6856a1da33ca8867a4350914/skillto-ai-studio.git`。
0.3.0 不分发旧名称的重复技能，也不自动迁移客户端已有安装。

## 直接复制安装的升级

1. 找到客户端实际加载的旧技能根目录，比较旧副本中的本机修改。Codex 同时检查
   `.agents/skills` 与旧 `.codex/skills`，Claude 检查个人、项目技能和插件，避免重复。
2. 等待自己启动的服务/下载/渲染空闲，再停止要升级的实例。将旧父技能和本次替换的
   子技能移到发现目录以外的备份位置，保留自定义修改；不要把 `SKILL.md` 留在备份子目录
   里供客户端继续发现。安装器在同一目标根遇到对应旧名时会拒绝写入，不删除旧文件。
3. 按 [安装指引](installation.md) 将新技能装到选定位置；需要的父子技能一起升级。
   运行配置、脚本路径、引用技能的用户提示词等改用新名称与实际新路径。
4. MCP 业务工具名（如 `table_query`）不变，客户端配置的启动脚本路径需指向
   `skillto-ai-studio-table/scripts/server.py`。连接标签可以采用新名称；比较现有配置后
   只更新该连接，不覆盖其他 MCP，也不复制或打印密钥。
5. 在新会话调用 `$skillto-ai-studio` 或 `/skillto-ai-studio`；确认新父技能能读取所需子技能。

不要只改 `SKILL.md` 的 `name` 而保留旧目录：资源和兄弟依赖已同步采用新路径。
回滚时停止自己的相关实例，将新副本移出发现目录，恢复旧副本及其配置路径。

## Claude 插件的升级

原名称属于不同插件标识，不能只对原插件运行 update。确认旧插件确实是本套件后，
用同一安装范围移除旧注册，再注册新名称（以下为默认用户范围）：

```sh
claude plugin uninstall skillto-int@skillto-int-marketplace --scope user --keep-data
claude plugin marketplace remove --scope user skillto-int-marketplace
claude plugin marketplace add https://codeup.aliyun.com/6856a1da33ca8867a4350914/skillto-ai-studio.git
claude plugin install skillto-ai-studio@skillto-ai-studio-marketplace
claude plugin list
```

首次安装者只执行最后三条。项目级安装须在原项目使用对应 scope，组织管理的插件由管理员
按其策略更新。旧 marketplace 移除只针对本套件；不要删除其他市场或直接改插件缓存。
新调用为 `/skillto-ai-studio:skillto-ai-studio`；子技能如
`/skillto-ai-studio:skillto-ai-studio-rewrite`。

## 服务和数据兼容性

健康接口采用新的 `skillto-ai-studio-table` / `skillto-ai-studio-workbench` 标识。
新启动器与扩展也识别旧健康标识，支持分阶段升级；旧客户端可能不认识新服务，
应先更新客户端/扩展，再重启升级后的服务。Chrome 需重新构建并重载扩展，文件改名不等于
正在运行的扩展已更新。Windows 启动器重新构建后，明确配置新脚本路径。

已有 `SKILLTO_TABLE_ROOT`、`SKILLTO_TABLE_*` 等环境变量、数据库位置、URL、稳定 ID、
浏览器存储键、Windows 互斥锁/关闭事件及 `SkillToTable.exe` 兼容文件名保持不变。
它们用于找回现有状态，不是新技能名称；本次不迁移数据、凭据或浏览器会话。
SkillTo.ai SaaS 的真实域名、`@skilltoai/creator-mcp` 和第三方工具名称也不随项目改名。

品牌参考图片、角色身份和封面中的“小与封面图”署名仍属于其创作合同。
技能选择器与项目页面使用新项目名称；改名不会为任何客户端补齐缺失的外部运行能力。
