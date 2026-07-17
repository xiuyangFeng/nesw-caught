# 2026-07-17 优化清单设计（P0/P1）

> 状态：按用户优化清单优先方案锁定；先前同任务会话中断，本设计复用清单结论后直接进入实现。
> 日期：2026-07-17

## 1. 背景与目标

独立 `news_scheduler` 部署时，新闻可入库但前端 SSE 收不到更新；抓取健康判定把 HTTP 304 当失败、把解析 0 条当成功。同时存在中文新闻因 `published_at` 空/时区错误系统性沉底、页面启动自动全源抓取、虚拟列表高度失效、市场相关性门槛偏弱等问题。

本轮目标：

1. **P0 必须完成**：跨进程事件链路 + 抓取健康判定
2. **P1 尽量完成**：`effective_at`、页面生命周期只读、虚拟列表、市场相关性/主题可读性

## 2. 方案选型（已锁定）

### P0-1：独立 scheduler → Redis → Web SSE

| 方案 | 说明 | 结论 |
|------|------|------|
| A. 保留独立 worker + Redis consumer 注入 Web EventBus + 断线快照对账 | 最小改动，匹配现有 HybridEventBus | **采用** |
| B. 强制单进程内嵌 scheduler | 与 README 独立 worker 模式冲突 | 否 |
| C. SSE 直接读 Redis | 改动面大，绕开现有 EventBus 订阅 | 否 |

**设计要点：**

- `news.created` / `news.updated` 加入 Redis stream_map（与 batch 事件共用或专用 stream；默认：created→`redis_stream_news_ingested`，updated→`redis_stream_news_processed`）。
- 新增 `RedisStreamConsumer`：Web lifespan 在 hybrid/redis 后端下启动；`XREADGROUP`/`XREAD` 消费 stream，按信封还原 `event_name`+payload，调用 `local_bus.publish`（**不再二次写 Redis**，避免环）。
- Publisher 侧信封需携带 `event_name`（或 consumer 按 stream→事件名映射）；推荐 payload 外包一层 `{event_name, payload}` 以支持同 stream 多事件。
- 前端：SSE 断线重连成功后触发一次新闻/layout 快照拉取（对账漏事件），不自动触发全源 refresh。

### P0-2：抓取健康判定

状态枚举：`ok | not_modified | empty | parse_error | http_error`。

| 状态 | 退避 | 健康记账 |
|------|------|----------|
| ok | 清零失败 streak | success |
| not_modified | 清零失败 streak，按 cadence | success（非失败） |
| empty | 连续空批计数+1；达阈值进入低频探测 | 非硬失败，记 last_error |
| parse_error / http_error | 指数退避 | failure |

`source_health` 扩展：`last_status`、`last_error`、`last_http_status`、`last_fetched_count`、`last_inserted_count`、`consecutive_empty_batches`。熔断：连续 empty/error 超过阈值后拉长探测间隔（复用 backoff 机制，不禁用源除非已有 `is_disabled`）。

### P1-1：effective_at

- 列 `effective_at = published_at ?? fetched_at`，入库/更新时维护；索引 `(effective_at, id)` / `(market, effective_at, id)`。
- 列表/游标排序改用 `effective_at`。
- RSS `dc:date` 正确解析；无时区中文源按 Asia/Shanghai 解释后转 UTC。
- API/UI 保留 `published_at`/`fetched_at`，UI 标注「原文时间 / 抓取时间」。

### P1-2：页面生命周期

- 移除 AppShell 启动时的 `refreshDashboardNews()`（全源抓取）。
- 抓取仅由 scheduler + 显式手动刷新；手动刷新带 cooldown（前端节流 + 后端若已有 lease 则复用）。
- SSE layout 刷新 250–1000ms trailing debounce；搜索防抖 + AbortController（store 已有部分能力则补齐）。
- 仅 market 变化才强制重算 layout 查询参数。

### P1-3：虚拟列表

- 固定/视口高度滚动根；保证 `clientHeight` 有效。
- 测试：100 条时 DOM 行数有限（现有 vitest + 必要时强化断言）。

### P1-4：相关性与主题

- 入库/候选阶段提高市场相关性门槛；官方/IR/监管/财报源优先（复用 `news_priority`）。
- 主题中文别名与可读显示名。
- 无 LLM 时结构化摘要：主体、事件、影响对象（规则模板，写入 summary/takeaway 降级路径）。

## 3. 非目标

- 不更换 Postgres；不重写 EventBus 为纯 Redis。
- 不强制取消独立 worker 模式。
- 不做无关大重构；不主动写 quick-run 文档。

## 4. 测试策略

- TDD：每个修改单元先写失败测试。
- 后端：`conda run -n news-caught pytest backend/tests` 相关文件。
- 前端：涉及 UI 时 `npm --prefix frontend run build` 与相关 vitest。

## 5. 风险

- Redis 不可用时：hybrid 降级本地；独立 worker 场景 SSE 仍可能断，需文档说明依赖 Redis。
- `effective_at` 迁移后游标语义变化，旧 cursor 可能失效（可接受，客户端重拉）。
- 健康字段迁移需防御式 alembic。
