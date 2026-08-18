# 后端 / 爬虫 / 信息源系统性重构计划（2026-07-25）

目标（用户原话）：**保证信息的快速抓取、准确性和及时更新；后端整体性能要很快，点击的时候反馈要快。**

本计划基于一次全量只读侦察（3 个并行侦察智能体 + 人工复核），所有问题均已在**本地实测复现**后才列入，不含推测项。

---

## 〇、侦察实测基线（2026-07-25 22:00）

| 项 | 实测值 |
|---|---|
| 后端测试基线 | **649 passed in 11.78s**（全绿） |
| news_item 行数 | 529 |
| app.db / app.db-wal | 8.8MB / **6.3MB**（WAL 与主库同量级） |
| 16 个信息源状态 | **全部 `http_error`，且 `last_error` 全部为空字符串** |
| CLS Telegraph | 连续失败 43 次，最近成功 **2026-07-16**（停摆 9 天），历史入库 **0 条** |
| Zhipu AI News | 连续失败 **472** 次，最近成功 **2026-03-19** |
| Wallstreetcn Live | 抓取 330 次，入库 **5 条** |
| 36Kr | 入库 202 条，**published_at 全部为 NULL** |

**实测直连各源的真实结果**（绕过 DB，直接跑 fetcher）：多数源其实 HTTP 200 且能解析出 10–20 条；真正坏掉的是 **CLS 解析出 0 条**（选择器失效）与 **Zhipu JSON parse_error**。
→ 说明库里"全部 http_error"是**故障不可观测**（`str(exc)` 为空）叠加历史网络中断留下的陈旧状态，而非所有源都真的挂了。

---

## 一、根因分类

### A. 点击反馈慢的三个全局机制

1. **SSE 常驻吃满线程池**（`api/routes/stream.py:108`）
   `await anyio.to_thread.run_sync(lambda: queue.get(timeout=1.0))` 循环 → 每条活跃 SSE 连接**常驻占用 1 个 anyio 线程池 token**（默认仅 40，且与所有同步 `def` 路由共享）。全仓 60+ 路由中只有 2 个是 `async def`。多开几个标签页 / HMR 重连堆积即可让**全站点击在 FastAPI 层就排队**，SQL 都还没发出去。
2. **SQLite 连接池只有 15 条**（`db/session.py:11`）
   `create_engine` 未显式配置池 → SQLAlchemy 对文件型 SQLite 默认 `QueuePool(pool_size=5, max_overflow=10)`。而 `get_db_session` 的 session **贯穿整个 handler**，于是任何一个慢请求全程霸占一条连接。
3. **请求线程内的同步外部 IO**：`POST /market/sparklines` 循环内串行 `yf.download`（30 标的 × 10s = 最坏 300s）、`GET /market/search` 直连 Yahoo、`GET /calendar` 逐 symbol 串行 yfinance、`GET /research/stock/{symbol}` 在 GET 里跑完整 LLM 链路、`GET /health` 触发最长 60s 的 twitterapi 外网调用（而 health 是前端轮询接口）。

### B. 抓取准确性

1. **CLS 选择器完全失效**：实测 `www.cls.cn/telegraph` 现在是 Next.js SSR 空壳，`__NEXT_DATA__` 里无任何新闻数据，旧选择器出现 0 次。
2. **CLS 时间 -24 小时**（`parser.py:131`）：用 **UTC 当天日期**拼 **`+08:00`** 时区 → 北京时间 00:00–08:00 的快讯全部早一天；且硬编码 `+08:00` 与 `source.market` 无关。
3. **中文相对时间无解析器**：`分钟前/小时前/今天/昨天` 在 `app/` 下零命中 → 静默 `published_at=None`（36Kr 202 条全 NULL）。
4. **Atom link 真值 bug**（`parser.py:82`）：`entry.find(...) or entry.find(...)`，而 `xml.etree` 的 `Element.__bool__` 判"有无子元素"，`<link/>` 自闭合恒为 False → 永远退化成"文档里第一个 link"。
5. **编码嗅探是空操作**（`article_crawler.py:20-34`）：用了 `response.apparent_encoding` —— 那是 **requests** 的属性，`httpx.Response` 没有 → 从不读取 `<meta charset>`，GBK 页面按 utf-8 解码成乱码却仍标 `success`。
6. **正文 body 兜底把垃圾标成 success**：登录墙/JS 空壳页的导航文字被判为成功，喂给 LLM 污染信号，且因 success 而**永不重试**，形成永久坏数据。

### C. 中文新闻被相关性闸门大面积误杀（最大的"抓得到但看不到"）

`predict_market_relevance_details` 的 token 化是 `re.findall(r"[a-z0-9]+", text)` → **纯中文标题 token 集为空**，所有英文词表全部失效，中文只剩一张 20 条硬编码短语表。
经逐条核对，"央行降准 / 美联储降息 / CPI 数据 / 证监会新规 / 加征关税 / OPEC+ 减产"**全部被拒绝入库**。这解释了 CLS 入库 0 条、见闻 330 抓 5 入。

### D. 时效性

- cadence 100s/300s + **失败退避放大 8×**（常规源最长 2400s = 40 分钟）；
- **整批栅栏**：`[f.result() for f in futures]` 整批等最慢源；
- **批尾才发事件**：第一个源的新闻要等最后一个源落库完；
- **跨轮重复消费**：scheduler 每 5s 无条件重投 `signal_status IS NULL` 的前 50 条，而该状态要到批次末尾 commit 才更新 → 重复爬正文 + 双倍 LLM token，无任何 in-flight 租约。

### E. 数据一致性 / 可观测性

- `quote_service.py` 的"零延迟保底"分支引用了**未 import 的 `SessionLocal` 与 `logger`** → 该路径必抛 `NameError` 后 500（不是慢，是坏的）；
- `_save_live_quote` 开启写事务后才发起腾讯 fallback 的**串行网络抓取**，每 15 秒一次让 SQLite 写锁跨越 N×5s 网络；
- 抓取失败 `error=str(exc)`，httpx 超时类异常字符串为空 → 16 个源 `last_error` 全空，故障无法诊断；
- 无 prometheus/OTel，pipeline 全链路零耗时埋点。

---

## 二、执行编排（6 个并行工单，文件范围互不重叠）

并行约束（依据既往教训）：各工单**文件范围严格互斥**；配置项由主控**预先统一加入 `core/config.py`**，避免 6 个智能体同时改同一文件；**所有 git 提交由主控串行执行**，子智能体一律禁止 `git add/commit`（此前发生过共享 git index 竞态）。

| 工单 | 主题 | 文件范围 |
|---|---|---|
| WS-1 | 读路径并发与连接池 | `db/session.py`、`api/routes/stream.py`、`main.py`、`core/simple_cache.py` |
| WS-2 | 重读接口与查询优化 | `api/routes/news.py`、`api/routes/topics.py`、`services/news_feed_layout.py`、`services/news_runtime.py`、`repositories/news_repository.py`、`repositories/topic_repository.py` |
| WS-3 | 行情/市场路由阻塞与崩溃 | `services/quote_service.py`、`services/market_chart_service.py`、`services/calendar_service.py`、`api/routes/market.py`、`api/routes/health.py` |
| WS-4 | 抓取解析准确性 | `ingestion/parser.py`、`ingestion/utils.py`、`ingestion/fetcher.py`、`ingestion/article_crawler.py` |
| WS-5 | 去重 / 相关性闸门 / 信息源 | `ingestion/dedup_gate.py`、`ingestion/sources.py`、`ingestion/persister.py`、`services/news_dedup.py`、`services/news_priority.py`、`services/news_relevance_evaluator.py` |
| WS-6 | 调度器与后台 worker | `services/news_ingest_scheduler.py`、`ingestion/service.py`、`ingestion/types.py`、`services/news_signal_pipeline.py`、`services/http_pool.py`、`services/event_bus.py`、`workers/queue_worker.py` |
| WS-7（主控） | 索引与迁移、配置项、文档、提交 | `models/**`、`alembic/versions/**`、`core/config.py`、`docs/**` |

### 跨工单契约

- CLS 新解析器 key 统一为 **`cls_telegraph_json`**：WS-4 实现 parser + 签名/Referer（`fetcher.py`），WS-5 只在 `sources.py` 填 `url` 与 `parser` 字段。
- WS-5 需要扩展 `SourceFetchResult` 时不得改 `types.py`（属 WS-6），改为结构化日志表达并在报告中说明。

---

## 三、CLS 官方 JSON API（已实测可用，替代失效的 HTML 选择器）

- endpoint：`https://www.cls.cn/v1/roll/get_roll_list`（必须带 `Referer: https://www.cls.cn/telegraph`）
- 参数：`app=CailianpressWeb, os=web, sv=8.4.6, rn=20, last_time=, category=`
- 签名：参数按 key 升序拼 `k=v&...` → `sha1` hexdigest → 对该 hexdigest 再 `md5` hexdigest，作为 `sign`
- 响应：`{"errno":0,"data":{"roll_data":[...]}}`，实测 20 条
- 关键字段：`id`、`title`（**可能为空，需回退 brief/content**）、`brief`/`content`、**`ctime`（epoch 秒，准确时间戳）**、`shareurl`、`level`（A/B/C 重要性）、`stock_list`、`subjects`

相比 HTML 抓取的收益：时间戳精确到秒（直接消灭 -24h 与相对时间两类问题）、附带重要性分级与个股关联、体积小且稳定。

---

## 四、新增配置项（已由主控写入 `core/config.py`）

连接池与并发：`db_pool_size=20`、`db_max_overflow=30`、`db_pool_timeout=10.0`、`db_pool_recycle=1800`、`sqlite_wal_autocheckpoint_pages=2000`、`server_threadpool_size=128`
SSE：`stream_queue_maxsize=500`、`stream_keepalive_seconds=15.0`
抓取：`news_fetch_max_workers=16`、`news_crawl_max_workers=8`、`news_classify_max_workers=4`、`news_signal_backlog_batch_size=50`、`crawl_timeout_seconds=15.0`、`http_connect_timeout_seconds=5.0`、`news_scheduler_startup_jitter_seconds=8.0`、`news_inflight_lease_seconds=600.0`
worker：`queue_worker_poll_interval_seconds=1.0`、`queue_worker_fallback_scan_interval_seconds=30.0`
读路径：`route_cache_max_entries=512`、`event_detail_cache_ttl_seconds=15.0`、`market_chart_max_workers=8`

## 五、新增索引（迁移 `d4b7e1f0c3a6`）

`ix_news_sentiment_effective_id`、`ix_news_source_effective_id`、`ix_news_source_market_fetched`、`ix_topic_news_link_topic_news`、`ix_news_stock_mention_symbol_news`、`ix_topic_cluster_importance_seen`

---

## 六、验收标准

1. **全量回归 649 → 更多测试全绿**：`NEWS_CAUGHT_TEST_DB=/tmp/nc.db conda run -n news-caught pytest backend/tests -q`
2. 每个工单必须携带**修复前会失败**的回归测试（TDD），重点：CLS -24h、Atom link、中文闸门 6 条样本、`quote_service` NameError、跨轮重复消费。
3. 端到端实测：起后端 → 观察 `source_health` 的 `last_status`/`last_error`/`last_inserted_count`，CLS 与见闻应从"0 入库"变为持续入库。
4. `docs/code-change-log.md` 按仓库规范回填。
