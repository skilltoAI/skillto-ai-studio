# Changelog

## Unreleased

### 2026-11-18 · STASS-001 · Codeup 双向凭据配置

- 范围：开发入口、Git 协作规则、Codeup Git 客户端及离线测试。
- 增加独立的 `CODEUP_FETCH_*` / `CODEUP_PUSH_*` 环境变量契约，分别配置仓库地址、
  用户名、HTTPS 密码、SSH 私钥文件和认证方式；变量名称写入 AGENTS.md。
- Git 入口按操作读取同组凭据，不使用共享凭据助手或跨方向回退；SSH 显式选择私钥并验证主机。
  密码不出现在 Git 参数、仓库配置或输出；Windows 旧进程可读取当前用户环境配置。
- 本机验证：HTTPS 拉取认证及 SSH 远端读取通过；已 fetch Codeup main，隔离任务工作树
  采用该远端基线。没有执行推送；SSH 读取成功不代表写权限已验证。
- 验证：24 项单元测试通过（新增10项凭据隔离与命令契约测试），仓库结构检查及 diff 检查通过。
- 规范更新：AGENTS.md、CONTRIBUTING.md；全套 STASS 技术规范和程序迁移属于后续阶段，尚未完成。
- 兼容性：保留原 origin、工作区、现有工作台与业务数据；Codeup 网络操作须改用显式方向的脚本。
