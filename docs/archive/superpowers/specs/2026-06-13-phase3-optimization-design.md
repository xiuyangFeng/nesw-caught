# Phase 3 优化设计 (2026-06-13)

本设计文档涵盖优化清单中 Phase 3 (体验/扩展) 的内容，包括：
1. 引入 SQLite FTS5 虚拟全文检索表，取代 SQL `LOWER(title) LIKE '%kw%'` 前置通配符扫描优化 (#7)。
2. 将 `/news/refresh` 慢路由改造为支持 `async_mode` 异步非阻塞执行，避免高并发下耗尽连接池 (#8)。
3. 在 `feed-layout` 与 `runtime` 等热门路由中，引入进程内非阻塞带有过期时效的自研 TTL 缓存以提高响应力 (#9)。
4. 前端首屏请求大小进行缩减（200/300 -> 50）(#10)，同时在后端使用线程池 `ThreadPoolExecutor` 对正文抓取阶段进行并发网络 I/O 重构以缩短耗时 (#11)。

---

## 1. 全文检索 FTS5 设计 (#7)

### 1.1 问题诊断
`NewsRepository.list_recent_page` 在传入 `q` 查询词时，使用的是 `LIKE` 前置通配符进行全局扫描，SQLite 在百万量级数据时必须每次做全表遍历，极度低效。

### 1.2 解决方案
- 通过 Alembic 新增迁移，在 SQLite 中创建名为 `news_fts` 的 FTS5 虚表，并将现存的 `news_item` 中的数据全量回填。
- 绑定三个触发器（AFTER INSERT, AFTER DELETE, AFTER UPDATE），在主表更新、写入或删除时，实时且自动同步至虚表。
- 在后端 `list_recent_page` 路由实现里，如果是中文或含有检索词，首先在 FTS 虚表中做 MATCH 查询，获取命中的 `id` 列表；如果有匹配的 id，则通过 `.where(NewsItem.id.in_(fts_ids))` 进行快速聚簇索引检索；如果 FTS 没匹配到，采用原本的 `LIKE` 机制作为 Fallback 兜底，实现高兼容度和零漏匹配。

### 1.3 Alembic SQL 实现
```sql
CREATE VIRTUAL TABLE news_fts USING fts5(
  title, summary, content='news_item', content_rowid='id'
);

CREATE TRIGGER news_fts_ai AFTER INSERT ON news_item BEGIN
  INSERT INTO news_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
END;

CREATE TRIGGER news_fts_ad AFTER DELETE ON news_item BEGIN
  INSERT INTO news_fts(news_fts, rowid, title, summary) VALUES('delete', old.id, old.title, old.summary);
END;

CREATE TRIGGER news_fts_au AFTER UPDATE OF title, summary ON news_item BEGIN
  INSERT INTO news_fts(news_fts, rowid, title, summary) VALUES('delete', old.id, old.title, old.summary);
  INSERT INTO news_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
END;
```

---

## 2. 刷新路由异步化 (#8)

### 2.1 解决方案
在 `backend/app/api/routes/news.py` 里的 `refresh_news_sources` 接口：
- 增加 `async_mode: bool = False` 参数以保证与原有单元测试和同步逻辑的完美向前兼容。
- 当传入 `async_mode=True` 时，使用 FastAPI 提供的 `BackgroundTasks`，在独立的后台线程中执行慢摄入任务并立即返回 `202 Accepted` 和状态 JSON，释放该工作线程持有的 DB 链接。

---

## 3. 热点路由 TTL 缓存设计 (#9)

### 3.1 解决方案
在 `routes/news.py` 内部实现一个零依赖的原生 `SimpleTTLCache` 类：
- 针对 `feed-layout` 设置缓存周期为 10 秒。
- 针对 `runtime` 接口设置缓存周期为 5 秒。
- 在 `routes/news.py` 底部自动订阅 `news.signals_processed` 与 `news.created_batch` 等 Event Bus 事件，只要有新闻摄入或分析完成，自动调用 `clear()` 清空缓存以实现主动失效和最终一致性。

---

## 4. 并发抓取与前端限制重构 (#10, #11)

### 4.1 前端默认拉取限制
在 `frontend/src/stores/newsStore.ts` 中，将 `feedQuery` 和 `dashboardQuery` 的默认 `limit` 从 300/200 下调为 50。当首屏打开时将首屏 TTFB 压缩至极限，滚动时自动使用游标续拉加载更多。

### 4.2 阶段 1 的 ThreadPoolExecutor 并发抓取
在 `NewsSignalPipelineService._ensure_articles` 里：
- 子线程中绝对不传递或操作 SQLAlchemy Session 对象。
- 使用 `ThreadPoolExecutor` 并发发起 `_safe_crawl(canonical_url)`。
- 在所有抓取工作全部结束后，回到主线程中使用主 Session 逐个执行事务的合并落库。
