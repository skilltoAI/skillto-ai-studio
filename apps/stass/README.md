# STASS 程序迁移工作区

当前状态：开发中，不能替换生产入口。程序源码已集中到 modules，保留原实现作为迁移测试基线；旧技能副本尚未移除。

已实现：标准 Streamable HTTP MCP、12项语义工具、共享业务API、身份/令牌/Host/Origin检查、独立MCP客户端、短ID存储、不可变视图、SQLite一致性快照与文件校验。

尚未完成：网页与短路由的完整集成、浏览器本机工具接入新MCP、配对界面、素材分块MCP、资源引用转换、启动器切换、技能客户端替换、生产切换与完整新入口端到端验收。不得把旧模块测试通过描述为新工作台已交付。

## 开发运行

Windows 环境依赖锁在 requirements-windows.lock.txt。服务需要 STASS_DATA_ROOT 指向隔离数据目录，STASS_TOKEN_FILE 指向受保护令牌文件（至少32字符），STASS_ALLOWED_HOSTS 明确列出允许访问的主机与端口。不得将生产数据用于开发测试。

从本目录运行：`python -m uvicorn service:app --host 127.0.0.1 --port 8080`。局域网部署须显式配置监听地址与允许主机；当前不执行生产部署。

客户端 `python client.py pair --url <STASS-URL> --token-file <受保护文件> --profile <本机配对配置>`；`list` 和 `call --tool <名称> --arguments <JSON文件>` 使用已配对实例，身份变化拒绝发送凭据。

## 验证

`python run_regression.py <仓库外或忽略目录的日志目录>` 使用隔离数据根目录运行各模块。报表数据库、原采集快照和猫抓上游需显式配置，缺失时跳过必须单独列出。

`python -m unittest discover -s . -p test_migration_routing.py -v` 验证快照、WAL、短ID和URL；`python -m unittest discover -s . -p test_service.py -v` 验证MCP与API共享数据和访问边界。

`migration.py --source <旧数据根> --destination <空目标>` 仅生成演练副本；其 manifest 明确列出尚未迁移的浏览器档案、外部资源及数据库。它不是正式切换命令。
