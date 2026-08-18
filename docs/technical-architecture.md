# 技术架构说明

> **文档状态（2026-08-18）：** 本文是 2026-03 架构草稿。模块名、流水线和数据模型可能已落后于代码。
> 实现以 `backend/`、`frontend/`、Alembic 迁移和 `frontend/openapi.json` 为准。不要按本文重建已不存在的模块。当前能力见 [current-state.md](./current-state.md)。

## 1. 总体架构

采用单体应用架构：

- 后端负责采集、处理、存储、推送和 API
- 前端负责展示、筛选和实时更新
- SQLite 负责本地持久化
- 所有时间统一存 UTC，前端按市场时区展示

## 2. 处理流水线

1. 定时任务触发 RSS 抓取
2. 解析新闻元数据并生成唯一指纹
3. 去重后写入原始新闻表
4. 发布 `news.created` 进程内事件
5. 异步进行正文抓取和股票提及识别
6. 进行情绪打分和主题聚合
7. 生成推送事件
8. 前端通过 REST 拉历史，通过单向推送通道收增量

## 3. 模块划分

### 采集层

- `rss_fetcher`
- `article_extractor`
- `price_fetcher`
- `http_client`

### 处理层

- `dedup_service`
- `stock_mention_service`
- `sentiment_service`
- `topic_cluster_service`
- `signal_service`

### 接口层

- `news_api`
- `watchlist_api`
- `market_api`
- `stream_gateway`

### 基础设施层

- `scheduler`
- `event_bus`
- `settings`
- `logging`
- `database`

## 4. 数据模型建议

### news_item

- `id`
- `source_name`
- `source_url`
- `title`
- `summary`
- `canonical_url`
- `url_hash`
- `market`
- `language`
- `sentiment_label`
- `sentiment_score`
- `published_at`
- `fetched_at`
- `ingest_status`

### article_content

- `id`
- `news_id`
- `content_text`
- `content_html`
- `extract_status`
- `extract_error`
- `extracted_at`

### price_snapshot

- `id`
- `symbol`
- `market`
- `price`
- `change_amount`
- `change_percent`
- `volume`
- `fetched_at`

### watchlist_item

- `id`
- `symbol`
- `market`
- `display_name`
- `is_active`
- `alert_threshold`
- `alert_mode`

### news_stock_mention

- `id`
- `news_id`
- `symbol`
- `market`
- `mention_type`
- `confidence`
- `created_at`

### topic_cluster

- `id`
- `topic_title`
- `topic_summary`
- `keywords`
- `sentiment_score`
- `importance_score`
- `last_seen_at`

### notification_job（原 signal_event 设想已未采纳/已移除）

早期设计中曾计划以独立的 `signal_event` 表作为通知系统地基，但该表从未建表、无迁移、代码无引用，属于死模型，已删除。实际通知链路以 `notification_job` 表落地：

- `id`
- `channel`
- `event_type`
- `payload_json`
- `status`
- `attempt_count`
- `next_retry_at`
- `dedupe_key`
- `last_error`
- `lease_until`
- `lease_token`
- `sent_at`

投递由 `NotificationService` 轮询驱动，核心机制：300 秒租约防并发重复投递、失败按退避序列重试（最多 5 次）、`dedupe_key` 做幂等去重。详见 `backend/app/services/notification_service.py`。

### source_health

- `id`
- `source_name`
- `source_type`
- `last_success_at`
- `last_failure_at`
- `consecutive_failures`
- `total_fetches`
- `total_failures`
- `avg_latency_ms`
- `is_disabled`

## 5. 关键技术策略

### 去重

优先使用规范化 URL、标题哈希和时间窗口联合判定，避免只靠原始链接。

建议分三层实现：

- 精确去重：URL 哈希完全匹配
- 近似去重：标题 Simhash + 发布时间窗口
- 语义去重：后续 AI 阶段再接入

### 正文抓取

新闻元数据先入库，正文抓取异步补全。正文失败不影响主题展示。

正文提取采用双层策略：

- 关键站点定制选择器
- 通用正文抽取库兜底

### 主题聚合

先采用启发式聚合：

- 标题相似度
- 关键词重叠
- Simhash 邻近
- 发布时间窗口
- 同一股票命中

后续再考虑引入 embedding。

### 情绪分析

第一阶段使用轻量基线，统一映射到可比较分值。后续 AI 模块通过独立服务接口接入。

本地 LLM 通过可选增强层接入，默认不作为必需依赖。

### 实时推送

单向推送层只推三类事件：

- 新新闻
- 主题更新
- 自选股异动

第一阶段优先考虑 SSE。若未来出现双向交互需求，再切换到 WebSocket。

## 6. 调度和任务控制

- APScheduler 任务设置 `max_instances=1`
- 同类抓取任务按市场交易时段分级调度
- 正文抓取采用指数退避重试
- 定时清理和备份纳入统一调度器

## 7. 请求与事件机制

### 统一 HTTP 客户端

- 统一超时、User-Agent、重试和限流
- 按域名做速率控制
- 为未来代理配置预留入口

### 进程内事件总线

为避免处理链路硬编码串联，后端内部采用轻量级事件总线：

- `news.created` -> 正文抓取、股票提及识别
- `article.extracted` -> 情绪分析
- `sentiment.scored` -> 主题聚合
- `topic.updated` -> 推送事件
- `price.abnormal` -> 自选股异动事件

## 8. 检索与保留策略

- 为 `news_item` 和 `article_content` 建立 FTS5 全文索引
- 新闻正文和行情快照定义保留期
- 定期清理前先备份

## 9. 迁移预案

如果后续出现以下情况，应考虑从 SQLite 迁移到 PostgreSQL：

- 采集源明显增多
- 写入频率持续增加
- 需要更复杂查询和并发
- 需要多设备同步使用
