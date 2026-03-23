# Market Worker Observability Design

## Context

自选股行情 producer 已被提取为独立 worker。这样职责边界更清晰，但也带来一个新问题：Web API 进程无法再直接知道 worker 是否仍在运行、最近一次成功刷新是什么时候、最近一次失败原因是什么。

当前 `/api/stream/status` 只返回事件层状态，仍然看不到独立 `market-worker` 的运行情况。

## Approaches Considered

### Approach A: 进程内内存状态

让 worker 在进程内维护状态对象，再尝试由 Web 读取。

缺点：

- Web 和 worker 已经是独立进程，内存无法共享
- 只有单进程时才成立，不满足当前架构

### Approach B: Redis 作为状态存储

worker 将运行状态写入 Redis，Web 再读取 Redis 并展示。

优点：

- 与现有事件层方向一致

缺点：

- 当前项目允许 `memory` / `hybrid` 两种运行方式，不能把 worker 可观测性绑定在 Redis 可用上
- 会把“运行状态暴露”问题扩大成“强依赖 Redis”

### Approach C: 数据库存储 worker 运行状态

新增一个很小的运行状态表，由 worker 每轮刷新时更新，Web API 直接从数据库读取。

优点：

- Web 与 worker 天然共享数据库
- 不依赖 Redis
- 对 SQLite 本地开发和未来单库部署都成立

缺点：

- 增加一个轻量状态表和少量写放大

## Recommended Design

采用 Approach C。

### Data Model

新增 `worker_runtime_status` 表，至少保存以下字段：

- `worker_name`
- `status`：`idle` / `running` / `ok` / `degraded`
- `last_heartbeat_at`
- `last_success_at`
- `last_failure_at`
- `last_error`
- `cycle_count`
- `success_count`
- `failure_count`
- `last_quotes_count`

本轮只服务于 `market_quote_producer`，但表设计保持可复用，后续新闻 worker 或其他后台任务也可复用。

### Producer Write Semantics

`MarketQuoteProducer.run_cycle()` 每轮都更新状态：

- 进入刷新前：写入 `running`
- 刷新成功：
  - `status=ok`
  - 更新 `last_success_at`
  - `cycle_count += 1`
  - `success_count += 1`
  - `last_quotes_count = 本轮产出 quotes 数`
- 刷新失败：
  - `status=degraded`
  - 更新 `last_failure_at`
  - `last_error = 异常文本`
  - `cycle_count += 1`
  - `failure_count += 1`

若 watchlist 为空，也视为一次成功 heartbeat，但 `last_quotes_count = 0`。

### API Exposure

扩展 `/api/stream/status` 返回 `market_worker` 区块，包含：

- `name`
- `status`
- `last_heartbeat_at`
- `last_success_at`
- `last_failure_at`
- `last_error`
- `cycle_count`
- `success_count`
- `failure_count`
- `last_quotes_count`

这样用户只需查看一个状态接口，就能同时看到事件层健康和行情 worker 健康。

### Testing Strategy

按 TDD 覆盖：

- producer 成功刷新后写入 worker 运行状态
- producer 失败后写入 `degraded` 和错误信息
- `/api/stream/status` 会返回 `market_worker` 状态区块

## Expected Outcome

完成后，独立 `market-worker` 的运行状态将被持久化并暴露到 API，开发和运维都能直接判断它是否在工作、最近一次成功/失败时间是什么、最近错误是什么。
