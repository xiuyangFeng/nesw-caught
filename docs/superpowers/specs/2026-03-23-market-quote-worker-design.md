# Market Quote Worker Design

## Context

上一阶段已把自选股行情的生产者职责从 HTTP route 中移除，改为由 `MarketQuoteProducer` 后台循环主动拉取并发布 `market.watchlist_refreshed`。但当前 producer 仍由 FastAPI `lifespan` 启动和停止，这意味着：

- 行情生产仍绑定在 Web 进程生命周期上
- 本地热重载和未来多实例部署都会让 producer 运行语义变得含糊
- 之后切换成真正流式 provider 时，仍要先把 producer 从应用进程中剥离

本轮目标是把 producer 提取为独立 worker 进程，并保持现有 watchlist API 与通知语义。

## Approaches Considered

### Approach A: 独立 worker 入口，复用当前 producer

新增 `python -m app.workers.market_quote_producer` 入口，由 worker 初始化数据库、事件总线、watchlist 刷新订阅和 producer 循环。Web API 不再启动行情 producer。

优点：

- 改动面集中，复用当前 `MarketQuoteProducer`
- 与现有 `news_fetcher` worker 入口风格一致
- 为后续迁移到真正 streaming provider 打开路径

缺点：

- 本地开发需要额外启动一个 worker 进程
- 事件的“消费”和“发布”仍在同一 worker 内完成，不是完整的分布式消费体系

### Approach B: 保持 Web 进程拥有 producer，只增加 CLI 包装

让 worker 仅转发到应用内部的 producer 构造。

优点：

- 看起来修改更少

缺点：

- 实质上没有解除 Web 生命周期绑定
- 会同时保留两套启动路径，边界更混乱

## Recommended Design

采用 Approach A。

### Runtime Split

#### Web App

- 保留现有 API、新闻相关事件处理、通知批处理
- 不再在 `lifespan` 中启动 `MarketQuoteProducer`

#### Market Quote Worker

- 初始化数据库
- 构建事件总线
- 注册 `market.watchlist_refreshed` 的本地订阅者
- 启动 `MarketQuoteProducer.run_forever()` 或等价阻塞循环

### Event And Notification Handling

当前 `market.watchlist_refreshed` 的阈值提醒依赖本地事件订阅者，而不是 Redis 消费端。因此将 producer 提到独立 worker 后，需要把该订阅者也放进 worker 进程中注册，保证：

1. producer 产出 quotes
2. producer 发布 `market.watchlist_refreshed`
3. worker 内本地订阅者执行阈值提醒
4. 如果开启 Redis hybrid bus，事件仍可同步发布到 Redis Streams

这样无需引入新的 Redis consumer，也不会让 watchlist 提醒失效。

### Shared Wiring

为避免 `main.py` 和 worker 重复复制订阅逻辑，需要把 `market.watchlist_refreshed` 订阅者注册提取为可复用函数，例如：

- `register_market_event_handlers(event_bus)`

Web 进程是否需要注册该订阅者取决于职责边界。本轮推荐只在 worker 注册，避免双实例或双进程下重复通知。

### CLI / Run Path

新增：

- `backend/app/workers/market_quote_producer.py`
- `make market-worker`

运行方式与现有 `make ingest-news` 保持一致。

### Testing Strategy

按 TDD 覆盖：

- worker `main()` 会初始化数据库、注册 market 事件处理并启动 producer
- Web app `lifespan` 不再启动 producer
- 原有 `market.watchlist_refreshed` 阈值提醒测试改为由 worker runtime 注册的订阅者驱动

## Expected Outcome

完成后，行情生产将真正从 Web API 进程中抽离。Web 只负责读快照，worker 负责拉行情和触发 watchlist 提醒，现有事件名与接口契约保持稳定。
