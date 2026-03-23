# Market Quote Producer Design

## Context

当前自选股行情链路仍以 `GET /api/market/watchlist` 为触发点：请求进入 route 后同步调用 `QuoteService` 拉取上游报价、写入 `price_snapshot`，再发布 `market.watchlist_refreshed`。这让事件契约已经稳定，但生产者位置仍然错误，导致：

- 行情更新频率取决于前端请求，而不是后端主动产出
- 路由时延直接受上游行情源影响
- 后续切换到真正流式 provider 时，仍需要先拆掉 route 内的“生产者职责”

本轮目标是把“请求触发刷新”替换为“后台常驻行情 producer”，同时保留现有事件名、通知订阅者和前端接口。

## Approaches Considered

### Approach A: 后台轮询 producer，HTTP 只读缓存

应用启动时注册一个后台循环任务，按固定间隔读取 watchlist、批量拉取行情、写入快照并发布 `market.watchlist_refreshed`。`/api/market/watchlist` 和 `/api/market/symbols/{symbol}` 仅从最近快照返回数据，不再触发上游拉取。

优点：

- 与现有 `yfinance` provider 兼容，不需要引入新上游协议
- 能立刻把 producer 职责从 route 中移走
- 事件、通知、前端接口基本不变

缺点：

- 本质仍是 polling，不是交易所级流式实时
- 需要处理后台循环的生命周期、容错和空 watchlist 场景

### Approach B: 独立 worker 进程轮询 producer

新增单独 worker 进程负责拉行情并发布 Redis 事件，Web API 只消费数据库/缓存。

优点：

- 与 Web 生命周期彻底隔离，更接近未来分布式形态
- 更容易水平扩展或独立部署

缺点：

- 当前仓库还没有 worker 进程管理约定，启动方式和本地开发复杂度都会上升
- 本轮改动面更大，不适合作为阶段性落地

### Approach C: 直接切流式 provider

直接接 WebSocket 或 streaming provider，让外部流入事件层。

优点：

- 形态最接近终局

缺点：

- 现有 provider 仍是 `yfinance`，仓库里没有稳定的流式行情源配置、认证、重连和订阅管理
- 会把这轮任务从“替换 producer 位置”膨胀为“重做 provider 层”

## Recommended Design

采用 Approach A，并把 provider/producer 边界显式化，为后续切到流式 provider 预留替换点。

### Architecture

新增一个 `MarketQuoteProducer`，由应用生命周期在后台启动。它的职责只有三件事：

1. 读取当前 watchlist symbol 集合
2. 通过 quote provider 批量产出最新行情并写入 `price_snapshot`
3. 发布 `market.watchlist_refreshed` 事件，沿用现有通知订阅者

`QuoteService` 则从“兼顾拉取与读取”的混合服务，收敛成两类职责：

- producer 路径：显式执行刷新，返回最新 payload
- route 路径：仅读取最近快照并转换成 API payload；没有快照时返回 `delayed` / `unavailable` 状态，而不是临时去拉上游

### Component Boundaries

#### `QuoteService`

- 保留 symbol 规范化、快照转 payload 和 provider 结果落库逻辑
- 新增显式刷新入口，例如 `refresh_watchlist_quotes(session)`，供 producer 调用
- 新增只读缓存入口，例如 `get_cached_watchlist_quotes(session)` 和 `get_cached_symbol_quote(...)`
- route 不再走 `_get_quote_payload()` 中的“缓存失效就立刻 fetch”路径

#### `MarketQuoteProducer`

- 按配置间隔循环运行
- 每轮使用新建数据库 session，避免持有长生命周期 session
- watchlist 为空时跳过，不发布空事件
- provider 局部失败时仍尽可能返回可用 quotes，并发布实际结果，保持现有“部分失败可见”的 API 语义
- 捕获异常并记录日志，失败不应终止后台循环

#### App Lifespan

- 在 `lifespan` 启动 producer
- 在关闭阶段停止 producer，避免测试或热重载留下悬挂线程/任务

### Data Flow

1. 应用启动
2. `MarketQuoteProducer` 后台循环开始
3. 每轮读取 watchlist
4. 通过 provider 拉取最新报价，写入 `price_snapshot`
5. 发布 `market.watchlist_refreshed`
6. 本地订阅者继续执行阈值通知
7. 前端通过 `/api/market/watchlist` 读取最近快照，获得“后台 producer 已生成”的行情

### Error Handling

- 单只 symbol 拉取失败：保留该 symbol 的失败状态 payload；若有旧快照，可标记为 `delayed`
- 整轮刷新异常：记录日志，不中断下一轮调度
- Redis 发布失败：继续走本地事件总线，保持当前 hybrid bus 语义
- 无快照场景：route 返回结构化不可用状态，而不是同步拉上游

### Configuration

新增配置：

- `MARKET_QUOTE_PRODUCER_ENABLED`：默认开启
- `MARKET_QUOTE_POLL_INTERVAL_SECONDS`：后台 producer 轮询间隔
- 可选 `MARKET_QUOTE_PRODUCER_RUN_ON_STARTUP`：启动后立即跑一轮，避免首屏长期空缓存

保留现有：

- `MARKET_QUOTE_PROVIDER`
- `MARKET_QUOTE_CACHE_TTL_SECONDS`

其中 `CACHE_TTL` 继续用于“快照是否可视为新鲜”的展示/状态判断，不再决定 route 是否临时触发上游拉取。

### Testing Strategy

本轮按 TDD 落地，重点覆盖：

- producer 每轮刷新后发布 `market.watchlist_refreshed`
- producer 局部失败不影响其他 symbol 和事件发布
- `/api/market/watchlist` 改为只读缓存，不再直接调用刷新型逻辑
- `/api/market/symbols/{symbol}` 在无缓存和有缓存时的状态行为
- app 生命周期会启动和停止 producer

## Expected Outcome

完成后，watchlist 行情的生产者将从 HTTP 请求路径迁移到后台常驻任务。前端仍通过相同接口读取行情，通知链继续复用 `market.watchlist_refreshed`，而后续若接入 WebSocket/streaming provider，只需要替换 `MarketQuoteProducer` 的输入侧，而无需再改 route、通知和事件契约。
