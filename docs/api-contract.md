# API 契约 v0

本文件用于约束前后端并行开发阶段的最小接口集合。除非明确同步，否则不要随意改字段名。

## 通用规则

- 基础前缀：`/api`
- 返回时间：统一为 UTC ISO 8601
- 分页能力：v0 阶段暂未强制，先支持基础列表接口
- 推送方式：v0 阶段默认 SSE
- 市场枚举：`hk` | `us` | `cn`
- 情绪枚举：`positive` | `negative` | `neutral` | `mixed` | `unknown`
- 正文提取状态枚举：`pending` | `success` | `failed` | `not_requested`
- 所有只读接口允许返回空数组或 `null` 字段，前端必须按降级状态展示

## 前端阶段补充说明

以下字段为前端桌面版 MVP 所需最小只读契约。若后端暂未完成，可先返回空值或空数组，但不要擅自替换字段名。

## 1. 健康检查

### `GET /api/health`

响应示例：

```json
{
  "status": "ok",
  "app_name": "News Caught Backend",
  "environment": "development",
  "now_utc": "2026-03-15T10:00:00Z",
  "database": "configured",
  "stream_mode": "sse",
  "ai_enabled": false,
  "x_bridge_enabled": true,
  "x_bridge_healthy": true
}
```

### `GET /api/health/sources`

响应示例：

```json
[
  {
    "source_name": "The Verge",
    "source_type": "rss",
    "last_success_at": "2026-03-16T07:10:36Z",
    "last_failure_at": null,
    "consecutive_failures": 0,
    "total_fetches": 1,
    "total_failures": 0,
    "avg_latency_ms": 1037.02,
    "is_disabled": false
  }
]
```

### `GET /api/health/x`

响应示例：

```json
{
  "enabled": true,
  "bridge_configured": true,
  "bridge_healthy": true,
  "bridge_status": "ok:grok.com",
  "provider_name": "grok-bridge",
  "last_success_at": "2026-03-16T07:10:36Z",
  "last_failure_at": null,
  "consecutive_failures": 0,
  "total_fetches": 2,
  "total_failures": 0,
  "avg_latency_ms": 2410,
  "last_error": null
}
```

## 2. 新闻列表

### `GET /api/news`

查询参数约定：

- `market`: `hk` | `us`
- `market`: `hk` | `us` | `cn`
- `q`: 关键词
- `source_name`: 来源名
- `sentiment_label`: 情绪标签
- `limit`: 返回条数，默认由后端决定

### `POST /api/news/refresh`

用于手动抓取内置公开源和自定义配置源。

响应示例：

```json
{
  "started_at": "2026-03-16T07:10:35Z",
  "finished_at": "2026-03-16T07:10:37Z",
  "fetched_count": 86,
  "inserted_count": 86,
  "results": [
    {
      "source_name": "WSJ World News",
      "source_type": "rss",
      "status": "ok",
      "fetched_count": 20,
      "inserted_count": 20,
      "error": null,
      "latency_ms": 835.29
    }
  ]
}
```

响应示例：

```json
[
  {
    "id": 1,
    "title": "Apple expands AI features for enterprise devices",
    "summary": "Apple extends AI features to enterprise device management.",
    "source_name": "Reuters",
    "canonical_url": "https://example.com/apple-ai",
    "market": "us",
    "sentiment_label": "positive",
    "published_at": "2026-03-15T09:50:00Z",
    "fetched_at": "2026-03-15T10:00:00Z"
  }
]
```

字段说明：

- `summary`、`canonical_url`、`published_at` 为前端新闻流展示必需字段
- 列表阶段不要求返回正文、主题和股票关联明细

## 2.1 新闻详情

### `GET /api/news/{id}`

响应示例：

```json
{
  "id": 1,
  "title": "Apple expands AI features for enterprise devices",
  "summary": "Apple extends AI features to enterprise device management.",
  "source_name": "Reuters",
  "canonical_url": "https://example.com/apple-ai",
  "market": "us",
  "sentiment_label": "positive",
  "sentiment_score": 0.72,
  "published_at": "2026-03-15T09:50:00Z",
  "fetched_at": "2026-03-15T10:00:00Z",
  "article": {
    "content_text": "Full article text",
    "extract_status": "success",
    "extract_error": null,
    "extracted_at": "2026-03-15T10:01:00Z"
  },
  "mentions": [
    {
      "symbol": "AAPL",
      "market": "us",
      "mention_type": "primary",
      "confidence": 0.93
    }
  ],
  "topic": {
    "id": 101,
    "topic_title": "Enterprise AI rollout",
    "importance_score": 0.81,
    "last_seen_at": "2026-03-15T10:00:00Z"
  }
}
```

## 3. 行情快照

### `GET /api/market/snapshots`

响应示例：

```json
[
  {
    "symbol": "AAPL",
    "market": "us",
    "display_name": "Apple",
    "price": 215.32,
    "change_amount": 3.01,
    "change_percent": 1.42,
    "volume": 18230000,
    "is_abnormal": true,
    "abnormal_reason": "price_breakout",
    "fetched_at": "2026-03-15T10:00:00Z"
  }
]
```

## 4. 自选股列表

### `GET /api/watchlist`

响应示例：

```json
[
  {
    "id": 1,
    "symbol": "0700.HK",
    "market": "hk",
    "display_name": "Tencent",
    "is_active": true,
    "alert_threshold": 3.0,
    "alert_mode": "fixed"
  }
]
```

## 4.1 自选股关联新闻

### `GET /api/watchlist/{symbol}/related-news`

响应示例：

```json
[
  {
    "id": 1,
    "title": "Tencent expands gaming pipeline",
    "summary": "Tencent continues to expand its game release schedule.",
    "source_name": "Bloomberg",
    "canonical_url": "https://example.com/tencent-gaming",
    "market": "hk",
    "sentiment_label": "positive",
    "published_at": "2026-03-15T09:30:00Z",
    "fetched_at": "2026-03-15T09:32:00Z"
  }
]
```

## 5. 主题列表

### `GET /api/topics`

响应示例：

```json
[
  {
    "id": 101,
    "topic_title": "Enterprise AI rollout",
    "topic_summary": "Multiple vendors are expanding enterprise AI capabilities.",
    "keywords": ["AI", "enterprise", "devices"],
    "market": "us",
    "sentiment_label": "positive",
    "importance_score": 0.81,
    "news_count": 6,
    "last_seen_at": "2026-03-15T10:00:00Z",
    "related_symbols": ["AAPL", "MSFT"]
  }
]
```

## 6. 推送状态

### `GET /api/stream/status`

响应示例：

```json
{
  "mode": "sse",
  "status": "planned",
  "last_event_at": null,
  "retry_interval_ms": 3000
}
```

## 7. X Monitor

### `GET /api/x/accounts`

响应示例：

```json
[
  {
    "id": 1,
    "handle": "DeItaone",
    "display_name": "Delta One",
    "market_focus": "us",
    "is_active": true,
    "priority": 100,
    "notes": "Macro and breaking market headlines"
  }
]
```

### `GET /api/x/posts`

查询参数约定：

- `account_handle`: 博主 handle
- `symbol`: 股票代码
- `market`: `hk` | `us` | `cn`
- `q`: 关键词
- `limit`: 返回条数

响应示例：

```json
[
  {
    "id": 1,
    "account_handle": "DeItaone",
    "account_display_name": "Delta One",
    "content_text": "NVIDIA suppliers remain in focus as AI infrastructure demand signals stay firm into the next quarter.",
    "canonical_url": "https://x.com/DeItaone/status/190001",
    "market": "us",
    "sentiment_label": "positive",
    "relevance_score": 0.92,
    "posted_at": "2026-03-16T07:00:00Z",
    "captured_at": "2026-03-16T07:05:00Z",
    "symbols": ["NVDA"]
  }
]
```

### `POST /api/x/refresh`

响应示例：

```json
{
  "started_at": "2026-03-16T07:10:35Z",
  "finished_at": "2026-03-16T07:10:38Z",
  "fetched_count": 6,
  "inserted_count": 3,
  "error": null,
  "latency_ms": 2634
}
```

## 7. SSE 事件流

### `GET /api/stream/events`

SSE 事件类型：

- `news.created`
- `topic.updated`
- `watchlist.movement`
- `stream.keepalive`

`data` 负载示例：

```json
{
  "type": "news.created",
  "occurred_at": "2026-03-15T10:02:00Z",
  "payload": {
    "id": 2,
    "title": "Nvidia supplier raises guidance",
    "summary": "Supplier outlook reinforces AI infrastructure demand.",
    "source_name": "Reuters",
    "canonical_url": "https://example.com/nvidia-supplier-guidance",
    "market": "us",
    "sentiment_label": "positive",
    "published_at": "2026-03-15T10:01:00Z",
    "fetched_at": "2026-03-15T10:02:00Z"
  }
}
```

```json
{
  "type": "topic.updated",
  "occurred_at": "2026-03-15T10:03:00Z",
  "payload": {
    "id": 101,
    "topic_title": "Enterprise AI rollout",
    "market": "us",
    "importance_score": 0.84,
    "news_count": 7,
    "last_seen_at": "2026-03-15T10:03:00Z"
  }
}
```

```json
{
  "type": "watchlist.movement",
  "occurred_at": "2026-03-15T10:04:00Z",
  "payload": {
    "symbol": "0700.HK",
    "market": "hk",
    "display_name": "Tencent",
    "price": 332.4,
    "change_percent": 3.3,
    "is_abnormal": true,
    "abnormal_reason": "volume_spike",
    "fetched_at": "2026-03-15T10:04:00Z"
  }
}
```

## 8. Mock 兼容层要求

- 当 `/api/topics`、`/api/news/{id}`、`/api/watchlist/{symbol}/related-news`、`/api/stream/events` 尚未可用时，前端可在本地 mock 兼容层中返回与上述契约一致的静态或空数据
- mock 兼容层不得引入未在本文件声明的新字段
- 后端接口落地后，前端应优先消费真实接口并自动退化到 mock

## 9. 后续准备中的接口

以下接口会在后续阶段继续扩展，但不影响当前桌面版 MVP：

- 新闻分页与游标
- 主题详情
- 自选股编辑接口
- 历史情绪时间窗统计
