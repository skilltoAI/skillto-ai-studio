# 本地报表运行手册

报表服务只监听本机。工作台为 `http://127.0.0.1:8880`，Metabase 为 `http://127.0.0.1:3330`，PostgreSQL 映射端口为 `5434`。本机的 `3000` 端口已由其他服务使用，因此 Metabase 改用 `3330`。

## 首次部署

在仓库根目录执行：

```powershell
.venv\Scripts\python.exe skills\skillto-ai-studio-table\reporting\setup_local.py
.venv\Scripts\python.exe skills\skillto-ai-studio-table\reporting\sync_data.py
.venv\Scripts\python.exe skills\skillto-ai-studio-table\reporting\publish_reports.py
```

首次部署要求 Docker Desktop 正在运行。`setup_local.py` 将管理员凭据、数据库密码及嵌入签名密钥保存在 `%LOCALAPPDATA%\SkillToTable\reporting\config.json`，仓库不存密钥。部署后的 Metabase 应用数据库和查询数据库是同一 PostgreSQL 实例中的两个独立数据库。

默认使用 Metabase 官方 `v0.64.3.x` Docker 镜像。本机 Docker Hub 不可达时，`setup_local.py` 会校验 `runtime/reporting/metabase.jar` 的 SHA-256，以官方 0.64.3.6 发布 JAR 和固定 Java 21 基础镜像构建本地 `skillto/metabase-oss:v0.64.3.6`，再通过 `compose.jar.yaml` 启动。数据卷及数据库配置相同；构建后重启不依赖仓库内的 JAR 文件。

## 数据与备份

账号表 JSON 仍为名单和分类的权威来源。本次名单及 2026-11-07 的原始采集结果位于 `C:\Users\Administrator\skillto-table-data\reports\raw\2026-11-07`。`sync_data.py` 只从该冻结批次重建查询库；不会覆盖历史快照。补采使用 `collect_accounts.py`，应在确认采集日期与用户需求后单独运行，避免把后续观测值误称为 11 月 7 日值。

```powershell
.venv\Scripts\python.exe skills\skillto-ai-studio-table\reporting\export_review.py
.venv\Scripts\python.exe skills\skillto-ai-studio-table\reporting\backup.py
```

`backup.py` 将原账号表、报表目录及两个数据库备份到 `%LOCALAPPDATA%\SkillToTable\backups`。页面和新 skill 的 CRUD 都经 8880 的 `/api/reports`，不直接改目录或 Metabase 数据库。

## 统计口径

作品按北京时间发布时间归属 9 月或 10 月。作品数按作品 ID 去重；点赞、收藏是 2026-11-07 可取得的观测值。主页快照的累计获赞数来自账号主页 `total_favorited`，粉丝数来自 `follower_count`，与作品点赞和不同。缺失值保持空值，覆盖状态和采集时间单独记录。
