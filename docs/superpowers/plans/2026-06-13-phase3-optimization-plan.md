# Phase 3 优化计划 (2026-06-13)

本计划对应 [2026-06-13-phase3-optimization-design.md](file:///Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-06-13-phase3-optimization-design.md) 中设计方案的实施步骤。

## 1. 实施步骤

### 阶段 1: SQLite FTS5 虚拟全文检索表 (#7)
- [ ] 运行 alembic 新增一个空 revision 迁移文件：`conda run -n news-caught alembic -c alembic.ini revision -m "add_sqlite_fts5_fulltext_search"`。
- [ ] 编写该迁移文件，创建 `news_fts` 表并绑定插入、删除、更新的触发器，并执行历史数据回填。
- [ ] 应用迁移：`conda run -n news-caught alembic -c alembic.ini upgrade head`。
- [ ] 修改 `backend/app/repositories/news_repository.py` 的 `list_recent_page`，在 query 查询时首选走 FTS 检索，并以 LIKE 作为 fallback。

### 阶段 2: 刷新路由异步化 (#8)与热点 TTL 缓存 (#9)
- [ ] 在 `backend/app/api/routes/news.py` 内部实现 `SimpleTTLCache` 原生缓存类。
- [ ] 实例化 `_feed_layout_cache` 和 `_runtime_cache`。
- [ ] 修改 `get_news_feed_layout` 与 `get_news_runtime` 以在其最外层优先命中缓存。
- [ ] 在 `routes/news.py` 底部捕获 event_bus 事件以在数据变化时清空缓存。
- [ ] 修改 `/news/refresh` 接口签名，加入 `async_mode` 与 `BackgroundTasks`，在 `async_mode=True` 时非阻塞 202 提交。

### 阶段 3: 并发抓取 (#11)与前端首屏限制 (#10)
- [ ] 修改 `backend/app/services/news_signal_pipeline.py` 的 `_ensure_articles`，使用 `ThreadPoolExecutor` 并发抓取网页正文，然后在主线程落库。
- [ ] 修改 `frontend/src/stores/newsStore.ts` 将 feed 默认限制设为 50，dashboard 设为 50。
- [ ] 验证全量编译及自动化测试：运行 `make test-backend` 并且运行 `npm --prefix frontend run build`。
