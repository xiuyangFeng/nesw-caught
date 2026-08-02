# 多模块工作树集成设计

日期：2026-08-03

## 集成范围

- `feature/logging-optimization`：结构化日志、请求上下文、前端错误上报。
- `feature/llm-optimization`：推理流、模型预设、聊天内窗口滚动。
- `feature/frontend-optimization`：Latest Events 精简与手动新闻抓取。
- `feature/dashboard-optimization`：市场情绪面板与动态行情条。
- `feature/watchlist-optimization`：无提交、无工作区改动，按空分支处理。

## 合并策略

1. 从当前 `main` 创建本地保护分支。
2. 先合并影响面最广的日志分支，再合并 LLM、Latest Events 和 Dashboard。
3. `docs/code-change-log.md` 冲突采用并集，任何一侧记录都不得丢失。
4. 重叠生产代码必须同时保留两侧语义：LLM provider 同时保留日志上下文与 reasoning 事件；聊天会话同时保留前端 logger 与 reasoning 字段；AppShell 同时保留聊天桌面视口约束与顶部状态条移除。
5. 顶部状态条移除后，聊天主区使用单一 `minmax(0,1fr)` Grid 行，避免保留空的 auto 行压缩 RouterView。

## 验收

- 无冲突标记、`git diff --check` 通过。
- 后端专项与全量测试、Ruff、OpenAPI drift 检查通过或仅保留已确认的既有失败。
- 前端全量测试在低并发模式通过，生产构建通过。
- `main` 相对远端只包含本次明确集成提交，推送后远端引用与本地一致。
