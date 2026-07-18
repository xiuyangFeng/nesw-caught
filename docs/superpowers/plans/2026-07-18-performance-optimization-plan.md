# 全链路性能优化实施计划

- 日期：2026-07-18
- 设计文档：docs/superpowers/specs/2026-07-18-performance-optimization-design.md

## 阶段 1：止血
1.1 pipeline 单入口化 + 原子认领（queue_worker.py / news_ingest_scheduler.py / ingestion/service.py / news_signal_repository.py）
1.2 K 线缓存命中即返回（market_chart_service.py）+ list_related_news 加 LIMIT
1.3 字体 latin 子集（frontend/src/main.ts）
1.4 pending partial index（Alembic 新 revision）

## 阶段 2：查询层防退化
2.1 /news/runtime SQL 聚合（news_runtime.py）
2.2 price_snapshot MAX/GROUP BY + 复合索引（market_repository.py + Alembic）
2.3 /topics N+1 批量化（topics.py / topic_repository.py）

## 阶段 3：前端高频路径
3.1 SSE layout 刷新降频（AppShell.vue）
3.2 NewsFeedView watch 浅化（NewsFeedView.vue）
3.3 markdown memo（ChatMessageList/StockDetailPanel/DigestView）
3.4 StockSparkline → SVG Sparkline
3.5 http 层 AbortSignal 接通（http.ts / NewsFeedView.vue）

## 阶段 4：抓取链路
4.1 行情 yf.download 批量（quote_provider.py）
4.2 feed/X 共享连接池（fetcher.py / http_pool.py / twitterapi_io_client.py）
4.3 MiniMax 水合挪并发段 + 失败冷却（persister.py）
4.4 load_sources mtime 缓存（sources.py）
4.5 X 逐账号容错 + 默认间隔（x_monitor/pipeline.py / config.py）

## 阶段 5：后端收口
5.1 事件扇出批量化 5.2 redis 熔断 5.3 find_topic 预载 5.4 心跳节流 5.5 分类缓存键 5.6 冗余索引清理

## 每阶段验证
pytest 全绿 + vitest 全绿 + build；行为变更 TDD；索引 EXPLAIN 留证；changelog 逐单元回填。
