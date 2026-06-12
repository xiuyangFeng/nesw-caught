# 事件层第二阶段设计：信号完成、通知批处理与行情事件统一

## 背景

第一阶段已经把新增新闻接到统一事件层，并提供了 Redis Streams 发布与本地总线降级能力。但当前仍有三类重要行为散落在 route 内部：

- `POST /api/news/refresh` 直接调用通知服务缓冲新闻
- `POST /api/news/{id}/analyze` 直接调用通知服务发送分析卡片
- `GET /api/market/watchlist` 直接在路由里做自选股阈值提醒

这会让通知、行情和后续实时源接入继续依赖 HTTP 路径，而不是依赖统一事件契约。

## 目标

本轮把以下能力迁到同一事件层：

1. 在信号流水线完成后发布 `news.signals_processed`
2. 将新闻批处理通知和分析通知改为事件订阅驱动
3. 将自选股行情刷新和阈值提醒改为事件订阅驱动
4. 为后续实时行情 provider 预留统一事件名和 stream 命名，而不在本轮直接引入新的行情源

## 非目标

- 不在本轮引入 WebSocket 行情 provider
- 不改前端页面或 `SSE` 消费逻辑
- 不把通知服务改造成独立 worker
- 不重构数据库模型

## 方案

### 事件名

- `news.created_batch`
  - 已存在，表示一批新增新闻已入库
- `news.signals_processed`
  - 新增，表示一批新闻已完成情绪/主题处理
- `news.analysis_completed`
  - 新增，表示单条新闻的 LLM 分析已完成
- `market.watchlist_refreshed`
  - 新增，表示一批自选股行情已刷新

### 路由职责收缩

路由只负责：

- 调用服务
- 返回 API 响应
- 发布领域事件

不再直接调用通知服务做副作用。

### 本地订阅者职责

#### `news.created_batch`

- 继续由本地订阅者运行 `NewsSignalPipelineService`
- 处理完成后再发布 `news.signals_processed`
- 通知服务也可订阅该事件，将新增新闻按现有批处理逻辑写入 buffer

#### `news.analysis_completed`

- 由通知服务订阅并发送分析卡片

#### `market.watchlist_refreshed`

- 由通知服务订阅
- 结合当前 watchlist 阈值配置决定是否触发提醒
- 后续如果接入实时行情 WebSocket，只要继续发布同名事件即可复用

### 数据载荷设计

#### `news.created_batch`

```json
{
  "news_ids": [1, 2, 3]
}
```

#### `news.signals_processed`

```json
{
  "news_ids": [1, 2, 3],
  "processed_count": 3
}
```

当前只保留最小必要字段，避免过早把大块业务载荷塞进 stream；本地消费者需要详情时再查库。

#### `news.analysis_completed`

```json
{
  "news_id": 10,
  "news_title": "Tencent AI expansion",
  "top_pick": {...},
  "candidates": [...],
  "summary": "...",
  "risk_notes": "..."
}
```

#### `market.watchlist_refreshed`

```json
{
  "quotes": [...],
  "symbols": ["0700.HK", "AAPL"]
}
```

### 服务边界

- `NewsSignalPipelineService`
  - 改为返回处理摘要，供事件发布方使用
- `NotificationService`
  - 保留卡片构建和 batch/threshold 状态机
  - 新增基于事件载荷与仓储查询的适配方法
- `main.py`
  - 集中注册事件订阅者，不把订阅逻辑散在 route
- `market.py` / `news.py`
  - 路由内只发布事件，不直接访问通知服务

## 测试策略

1. 流水线测试
   - `process_news_ids` 返回处理摘要
   - `news.created_batch` 订阅者会发布 `news.signals_processed`

2. 新闻分析路由测试
   - 分析成功后发布 `news.analysis_completed`
   - 不再直接依赖通知服务

3. 行情路由测试
   - `/api/market/watchlist` 返回行情同时发布 `market.watchlist_refreshed`
   - 通知服务通过事件消费阈值提醒，原有阈值进出边界行为保持不变

4. 通知服务测试
   - 关键词过滤仍生效
   - 事件订阅入口能驱动新闻批处理与分析通知

## 风险与后续

- 这一轮后，事件层会承担更多后端副作用编排职责，`main.py` 的订阅注册需要保持克制，避免长成巨型装配器
- `market.watchlist_refreshed` 暂时还是由请求触发，并非真正实时推送；但后续新行情源只要发布同名事件即可接入同一处理链
