# Redis 事件层第一阶段设计

## 背景

当前后端事件机制仍是进程内 `EventBus`，实现极轻，但只能覆盖单进程内同步分发。它适合本地串联，不适合后续的多数据源接入、异步处理、失败重试和消费解耦。与此同时，前端已经围绕 `SSE` 状态和增量展示组织了体验，本轮不应同时重做前端协议。

## 目标

第一阶段只完成后端事件层升级：

1. 为后端提供一个可选的 Redis 事件发布通道
2. Redis 不可用时自动降级回当前进程内事件总线
3. 保持现有新闻刷新、信号处理、通知和前端 `SSE` 展示不被迫一起改造
4. 让健康检查和 `stream status` 能反映当前事件层状态

## 非目标

- 不在本轮引入 PostgreSQL
- 不重做前端 `SSE` 消费方式
- 不在本轮把新闻刷新完全拆成独立 worker
- 不改动现有新闻源、X 监控源或行情 provider

## 方案备选

### 方案 A：仅替换为纯 Redis Streams

- 所有事件只写 Redis
- 消费者也只从 Redis 读
- Redis 不可用则直接失败

优点：

- 架构最干净
- 最接近后续长期形态

缺点：

- 第一阶段风险过高
- Redis 立即变成强依赖
- 需要连带改造现有同步调用点和生命周期管理

### 方案 B：双通道发布，Redis 优先，进程内总线兜底

- 对外暴露统一事件发布接口
- 正常情况下同时具备 Redis 发布能力和本地订阅能力
- Redis 异常时自动回退到进程内分发
- 当前同步链路仍可继续工作

优点：

- 风险最低
- 可以逐步把生产者和消费者迁到 Redis
- 不要求前端和 API 同步改协议

缺点：

- 第一阶段会出现两套通道并存
- 代码抽象会比纯进程内总线稍复杂

### 方案 C：保持当前总线，只给个 Redis 封装备用

- 保持现有逻辑不动
- 新增 Redis 工具类，但不接入主链路

优点：

- 改动最小

缺点：

- 产品收益极低
- 不能真实验证 Redis 事件层设计
- 后续基本还得重做

## 选型

采用 **方案 B：双通道发布，Redis 优先，进程内兜底**。

原因：

- 这是当前阶段最稳妥的过渡形态
- 符合用户明确要求：Redis 不可用时自动回退而不是阻断系统
- 能在不撕裂现有 `refresh_all -> pipeline -> notification` 链路的前提下，把发布入口和状态模型先做对

## 设计

### 核心边界

新增统一事件层服务，职责拆成三块：

1. **本地总线**
   - 保留当前 `subscribe` / `publish`
   - 负责当前进程内同步处理

2. **Redis 发布器**
   - 负责把事件写入 Redis Streams
   - 不承担本轮的消费编排

3. **混合事件总线**
   - 对上游暴露统一 `publish` / `subscribe`
   - 发布时先尝试 Redis，再总是执行本地分发
   - 记录最近一次 Redis 成功/失败状态，供健康和状态接口读取

### 第一阶段事件流

```text
NewsIngestionService.refresh_all()
  ├─ 入库新闻
  ├─ 调用统一事件总线发布 news.created_batch
  ├─ 统一事件总线：
  │   ├─ 尝试写入 Redis stream:news:ingested
  │   └─ 同步分发给本地订阅者
  └─ 本地订阅者继续调用 NewsSignalPipelineService
      └─ 后续可继续发布 news.signals_processed / news.analysis_completed
```

### 配置

新增配置：

- `event_bus_backend`: `memory` / `redis` / `hybrid`
- `redis_url`
- `redis_stream_news_ingested`
- `redis_stream_news_processed`
- `redis_stream_maxlen`
- `event_bus_publish_timeout_seconds`

默认采用 `hybrid`，避免新装 Redis 后还要额外切换才能验证。

### Stream 命名

首期只定义两条 stream：

- `stream:news:ingested`
- `stream:news:processed`

避免过早拆太细，先把生产入口和状态打通。

### 状态与可观测性

`/api/stream/status` 不再固定返回 `planned`，而是返回：

- 当前前端模式仍是 `sse`
- 事件层后端类型
- Redis 是否可用
- 最近一次 Redis 发布时间
- 最近一次 Redis 错误摘要

这样前端即使暂时不消费这些字段，后端和调试层也能先看到真实状态。

### 失败与降级策略

- Redis 发布失败：
  - 记录日志
  - 更新状态为 degraded
  - 继续执行本地同步订阅者
- Redis 未配置：
  - 自动视为 memory/hybrid 降级
- 本地订阅者抛错：
  - 维持现有语义，由调用链决定是否捕获
  - 不因为 Redis 成功就吞掉本地处理错误

### 文件边界

- `backend/app/services/event_bus.py`
  - 保留内存总线，并扩展成混合事件层入口或拆成更清晰的类
- `backend/app/services/redis_stream_bus.py`
  - Redis 写入与状态读取
- `backend/app/core/config.py`
  - 新增 Redis 事件层配置
- `backend/app/api/routes/stream.py`
  - 暴露真实状态
- `backend/app/main.py`
  - 初始化统一事件总线并绑定需要的本地订阅者
- `backend/app/services/news_ingestion.py`
  - 在刷新后通过统一事件层发布增量事件，而不是只直接内联执行

## 测试策略

1. 事件总线单测
   - 混合总线在 Redis 可用时会写入 stream 且执行本地订阅者
   - Redis 失败时仍执行本地订阅者
   - `memory` 模式下不触发 Redis

2. 状态单测
   - `stream status` 返回真实事件层状态
   - Redis 失败后状态切到 degraded

3. 刷新集成测试
   - `refresh_all` 发布增量事件
   - 本地订阅者仍驱动现有信号流水线，不改变已有业务结果

## 风险与后续

- 第一阶段只做 Redis 发布不做 Redis 消费，因此严格意义上仍是“过渡态”
- `hybrid` 会保留一段时间双路径逻辑，但这正是第一阶段稳定性的来源
- 下一阶段若要把 pipeline 或通知改成独立 worker，可在不改生产者接口的前提下推进
