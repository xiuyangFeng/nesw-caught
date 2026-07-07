# news-caught 优化清单(Master Lin Review)

> 范围:`backend/`(FastAPI + SQLAlchemy + SQLite)与 `frontend/`(Vue3 + Pinia)。
> 形式:每条 = 问题诊断 → 方案对比 → 核心代码片段 → 风险点。具体落地交由后续 agent 生成。
> 评分维度:**影响**(对性能/稳定性的收益)× **成本**(改动量/风险)。

## 0. 全局判断(先理解问题)

这是一个**单进程、多后台线程、SQLite 持久化**的实时管线系统:`NewsIngestScheduler / BackgroundQueueWorker / MarketQuoteProducer / cleanup / notification` 全部是 `BaseWorker` 派生的守护线程,共用一个 `SessionLocal`(同一个 SQLite 文件)。

```
                 ┌─────────────── 同一个 SQLite (单写者) ───────────────┐
 HTTP 请求(线程池) ─┤                                                      │
 IngestScheduler ──┤  写竞争点:refresh / pipeline / quote / cleanup       │
 QueueWorker ──────┤  全部串到一个 writer,WAL 也只允许 1 个写事务         │
 QuoteProducer ────┘                                                      │
```

**最大的系统性风险不是单点慢,而是“长事务 + 阻塞 I/O 占着写锁”导致的全局抖动。** 下面 P0 几条都围绕这个根因。备忘录已确认约束:**<20 个源继续留在 SQLite**,所以方向是"把阻塞 I/O 移出事务 + 补索引",而不是急着换 Postgres。

| # | 优化项 | 影响 | 成本 | 优先级 |
|---|--------|------|------|--------|
| 1 | pipeline 长事务里同步爬正文 | 高 | 中 | **P0** |
| 2 | 缺 (published_at, id) 复合索引 | 高 | 低 | **P0** |
| 3 | httpx.Client 每次调用新建 | 中 | 低 | **P0** |
| 4 | log_token_usage 每次开新 Session | 中 | 低 | P1 |
| 5 | 热路径内动态 import | 低 | 低 | P1 |
| 6 | 内存 analysis_queue 不持久 | 高 | 中 | P1 |
| 7 | 标题/摘要 LIKE 全表扫描(无 FTS) | 中 | 中 | P1 |
| 8 | 同步路由 + 阻塞网络占 DB 连接 | 中 | 中 | P1 |
| 9 | feed-layout / runtime 无缓存,每请求重算 | 中 | 低 | P2 |
| 10 | 前端首屏一次性拉 200~300 条 | 中 | 低 | P2 |
| 11 | classify/crawl 串行,未并发 | 中 | 中 | P2 |
| 12 | 宽泛 `except Exception` 吞错 | 中 | 低 | P2 |
| 13 | cleanup VACUUM 阻塞写 | 低 | 低 | P3 |
| 14 | 仓库层缺 selectinload,详情页多次往返 | 低 | 低 | P3 |
| 15 | 工程化:test_output.txt 入库、双份 AGENT 文档 | 低 | 低 | P3 |

---

## P0 — 先修这三条(根因)

### 1. pipeline 在写事务里同步爬全文,长时间占住 SQLite 写锁

`app/services/news_signal_pipeline.py::process_news_ids` 在**一个 session 内**,对每条无正文新闻 `crawl_and_extract_article(url)` 同步抓取(每条可能数秒),抓完 `flush`,再逐条 `classify`(可能含 LLM 调用)。整个过程事务未提交 → 这段时间内**所有其他 worker/请求的写操作都在排队**,这是 `database is locked` 的主要来源。

**方案对比**

| 方案 | 说明 | 适用 |
|------|------|------|
| A. 拆两阶段(推荐) | 阶段1:无事务并发爬正文写入(短事务/逐条提交);阶段2:再开事务做分类落库 | 当前规模最佳,改动可控 |
| B. 正文抓取下沉为独立 worker | 新增 `ArticleCrawlWorker`,pipeline 只消费已就绪正文 | 源增多后再上 |
| C. 全异步 + aiosqlite | 重写为 async,收益有限且 SQLite 仍单写 | 不建议现在做 |

**核心代码(方案 A 骨架)**

```python
# news_signal_pipeline.py
def process_news_ids(self, news_ids: list[int]) -> ProcessNewsSignalsSummary:
    if not news_ids:
        return ProcessNewsSignalsSummary([], 0, [])

    # —— 阶段 1:正文补全(短事务,逐条提交,失败不拖累整批)——
    self._ensure_articles(news_ids)          # 内部对每条 url 抓取后单独 commit

    # —— 阶段 2:分类与落库(此时无网络 I/O,事务短而快)——
    news_items = self.repository.list_news(news_ids)
    article_map = self.repository.get_article_map(news_ids)
    touched: set[int] = set()
    for item in news_items:
        self._process_item(item, article_map.get(item.id), touched)
    self.repository.refresh_topic_stats(touched)
    self.session.commit()
    return ProcessNewsSignalsSummary(news_ids, len(news_items), sorted(touched))

def _ensure_articles(self, news_ids: list[int]) -> None:
    """阶段1:把"抓取+写库"做成一条新闻一个短事务,避免长写锁。"""
    items = self.repository.list_news(news_ids)
    have = self.repository.get_article_map(news_ids)
    for item in items:
        art = have.get(item.id)
        if (art and art.extract_status == "success") or not item.canonical_url:
            continue
        text, status, err = self._safe_crawl(item.canonical_url)   # 网络 I/O 在事务外
        with self.session_factory() as s:                          # 独立短事务
            ArticleContentRepository(s).upsert(item.id, text, status, err)
            s.commit()
```

**风险点:** `_ensure_articles` 需要自己的 `session_factory`(把工厂传进 pipeline,而不是只传一个长寿命 session);确保抓取超时(`http_timeout_seconds`)足够小,避免单条卡死整批阶段1。

---

### 2. 列表/分页缺 `(published_at, id)` 复合索引,游标查询走不动索引

`NewsRepository.list_recent_page` 排序是 `ORDER BY published_at IS NULL ASC, published_at DESC, id DESC`,游标 where 是 `published_at < ? OR (published_at = ? AND id < ?)`。模型里 `published_at`、`id` 各自有索引,但**没有复合索引**,SQLite 对这种 OR + 双列排序只能退化为扫描+排序。数据到几万行后首屏明显变慢。

**核心代码(模型 + 迁移)**

```python
# app/models/news_item.py
from sqlalchemy import Index

class NewsItem(TimestampMixin, Base):
    __tablename__ = "news_item"
    __table_args__ = (
        # 覆盖主排序/游标分页;market 常作为过滤前缀,再加一条带 market 的
        Index("ix_news_published_id", "published_at", "id"),
        Index("ix_news_market_published_id", "market", "published_at", "id"),
    )
    ...
```

```python
# alembic 新 revision
def upgrade() -> None:
    with op.batch_alter_table("news_item") as b:
        b.create_index("ix_news_published_id", ["published_at", "id"])
        b.create_index("ix_news_market_published_id", ["market", "published_at", "id"])
```

**风险点:** SQLite 对 `DESC` 索引方向不敏感(读取时可反向扫描),无需建 DESC 索引;`published_at IS NULL` 分支建议在游标编码里用一个**哨兵时间**(如 `datetime.min`)统一,消掉 `IS NULL` 特判,让索引完全可用。

---

### 3. LLM Provider 每次请求都新建 `httpx.Client`,无连接池/keep-alive 复用

`app/services/llm_providers.py::_request_completion` 里 `with httpx.Client(timeout=60.0, headers=...) as client:` —— 每次补全都新建并销毁客户端,丢失连接池与 TLS 复用,高频分类时握手开销显著,且 60s 硬编码超时无法配置。

**方案对比**

| 方案 | 说明 |
|------|------|
| A. 进程级共享 Client(推荐) | 模块级单例 + `httpx.Limits`,所有 provider 复用 |
| B. provider 实例级 Client | 复用度低于 A,但隔离不同 base_url 头部 |

**核心代码(方案 A)**

```python
# app/services/http_pool.py (新)
import httpx
from app.core.config import get_settings

_client: httpx.Client | None = None

def get_llm_client() -> httpx.Client:
    global _client
    if _client is None:
        s = get_settings()
        _client = httpx.Client(
            timeout=s.llm_timeout_seconds,                       # 新增可配置项
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            headers={"User-Agent": "news-caught/0.1"},
        )
    return _client
```

```python
# llm_providers.py 内
client = get_llm_client()
response = client.post(
    f"{base_url}/chat/completions",
    headers={"Authorization": f"Bearer {self.config.decrypted_api_key}"},  # 每请求带 key
    json={...},
)
```

**风险点:** Client 线程安全(httpx 同步 Client 可跨线程用),但**进程退出时记得 close**(在 lifespan 关闭钩子里 `_client.close()`);不要把含密钥的 Authorization 放进共享 Client 的默认 header,按请求传。

---

## P1

### 4. `log_token_usage` 每次 LLM 调用开一个新 Session 提交一行,写放大

`app/services/llm_providers.py::log_token_usage` 每次 `with SessionLocal() as session: session.add(usage); session.commit()`。高频分类时,这是叠加在 #1 写锁上的**额外独立写事务**。

**方案:** 内存聚合 + 定时/批量落库(复用 BaseWorker),或至少做"每 N 条/每 T 秒 flush 一次"。

```python
# app/services/token_usage_buffer.py (新)
import threading, time
from app.db.session import SessionLocal
from app.models.llm_token_usage import LLMTokenUsage

class TokenUsageBuffer:
    def __init__(self, flush_n=50, flush_secs=10):
        self._buf: list[dict] = []
        self._lock = threading.Lock()
        self._flush_n, self._flush_secs = flush_n, flush_secs
        self._last = time.monotonic()

    def add(self, **row) -> None:
        with self._lock:
            self._buf.append(row)
            if len(self._buf) >= self._flush_n or time.monotonic() - self._last > self._flush_secs:
                self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._buf:
            return
        rows, self._buf, self._last = self._buf, [], time.monotonic()
        with SessionLocal() as s:                     # 一次事务写一批
            s.bulk_insert_mappings(LLMTokenUsage, rows)
            s.commit()
```

**风险点:** 进程崩溃会丢失未 flush 的计量;对计费类数据可接受少量丢失则用此法,否则保留同步写但合并进主事务。

---

### 5. 热路径内动态 import(循环依赖的临时绕法)

`queue_worker.do_cycle` 里 `from app.main import get_notification_service`、`news_signal_pipeline` 循环里 `from app.services.ingestion.article_crawler import ...`。动态 import 每次走 import lock,且 `from app.main import` 是**反向依赖**(worker 依赖 main),架构上是味道。

**核心代码:** `get_notification_service` 本就定义在 `app.services.notification_service`,直接从那里导入即可,删掉 main 里的转发:

```python
# queue_worker.py 顶部
from app.services.notification_service import get_notification_service
from app.services.ingestion.article_crawler import crawl_and_extract_article
# 删除函数体内的 from app.main import ...
```

**风险点:** 确认 `app.main` 没有反过来依赖 worker 的导入时副作用(目前 `analysis_queue` 是 worker 里的模块级全局,main 从 worker 导入,方向正确,无环)。

---

### 6. `analysis_queue` 是进程内 `queue.Queue`,重启即丢、无法水平扩展

`app/workers/queue_worker.py` 顶部 `analysis_queue: queue.Queue[list[int]] = queue.Queue()`。系统已经为**通知**做了持久化队列(`notification_job` 表 + `lease_token` 租约),但**分析任务**还停在内存队列——一旦进程重启,已入库未分析的新闻丢失触发信号,只能靠 `signal_status` 兜底补扫。

**方案对比**

| 方案 | 说明 | 适用 |
|------|------|------|
| A. 用 `signal_status` 做持久队列(推荐) | 入库即 `signal_status='pending'`,worker 轮询 `list_pending_news_ids` 拉取(已有此方法!) | 当前最省事,去掉内存队列 |
| B. 复用 Redis Stream | 已有 `stream:news:ingested`,worker 改消费 Stream | hybrid 模式打开时 |
| C. 复用 notification_job 那套租约表 | 一致性最好,改动最大 | 长期 |

**核心代码(方案 A,自愈轮询)**

```python
# queue_worker.py
def do_cycle(self) -> int:
    with self.session_factory() as session:
        pipeline = NewsSignalPipelineService(session)
        pending = pipeline.list_pending_news_ids(limit=200)   # 已存在的方法,直接用
    if not pending:
        return 0
    # ...复用现有处理逻辑(把内存队列那段删掉)
```

**风险点:** 需要保证入库时把 `signal_status` 置为 `'pending'`(目前默认 `ingest_status='ingested'`,`signal_status=None`);轮询要 `LIMIT + 按 id 升序`,避免每轮全表扫——配合 `signal_status` 上加 partial index。

---

### 7. 全文检索用 `LOWER(title) LIKE '%kw%'`,无法命中索引

`NewsRepository.list_recent_page` 的 `q` 过滤是双 `LIKE '%...%'`,前置通配符 → 必然全表扫描;数据量上来后搜索是 O(N)。

**方案:** SQLite FTS5 虚表 + 触发器同步,或对中文用 `unicode61`/`signal_keywords` 维度检索。

```sql
-- 迁移:建 FTS5 影子表
CREATE VIRTUAL TABLE news_fts USING fts5(
  title, summary, content='news_item', content_rowid='id'
);
-- 用触发器保持同步(insert/update/delete 三个)
CREATE TRIGGER news_ai AFTER INSERT ON news_item BEGIN
  INSERT INTO news_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
END;
```

```python
# 仓库层:有 q 时走 FTS,否则走原查询
if query:
    ids = session.execute(
        text("SELECT rowid FROM news_fts WHERE news_fts MATCH :q LIMIT 500"),
        {"q": _to_fts_query(query)},
    ).scalars().all()
    stmt = stmt.where(NewsItem.id.in_(ids))
```

**风险点:** 中文分词 FTS5 默认按 unicode 码点切,效果一般,可接 `jieba` 预切词写入;迁移要回填存量数据(`INSERT INTO news_fts(...) SELECT ...`);保留 LIKE 作为 fallback。**注意:这条与备忘录"<20 源留 SQLite"不冲突,FTS5 是 SQLite 原生能力。**

---

### 8. 39 个路由仅 4 个 async,同步路由里跑阻塞网络会占满线程池 + 占住 DB 连接

`/news/refresh`、`/news/{id}/analyze` 是 `def`(同步),内部做网络抓取/LLM 调用,运行在 FastAPI 默认线程池(40 线程)。同步路由通过 `Depends(get_db_session)` 在**整个请求周期持有一个 DB 连接**,阻塞网络期间连接空占。

**方案:** 把"触发"和"执行"分离——重活交给已有 worker,路由只入队即返回 `202`。

```python
@router.post("/refresh", status_code=202)
def refresh_news_sources() -> dict:
    # 不在请求线程里跑抓取;发事件让 scheduler/worker 立即跑一轮
    get_event_bus().publish("news.refresh_requested", {})
    return {"status": "accepted"}
```

**风险点:** 前端要从"同步等结果"改为"轮询 runtime 状态/或 SSE 推送完成事件"(项目已有 SSE,`stream.py`),交互需配套调整。

---

## P2

### 9. `feed-layout` / `runtime` 每次请求全量重算,无缓存

`NewsFeedLayoutService.build`(616 行,最大的 service)每次请求重新聚合 events/topics/stream;Dashboard 轮询会反复打这条重查询。

**方案:** 进程内 TTL 缓存(秒级),数据由 `news.signals_processed` 事件失效。

```python
from cachetools import TTLCache
_layout_cache = TTLCache(maxsize=64, ttl=10)

def get_news_feed_layout(market, ...):
    key = (market, limit_events, limit_topics, limit_stream)
    if key in _layout_cache:
        return _layout_cache[key]
    view = NewsFeedLayoutService(session).build(...)
    _layout_cache[key] = view
    return view
# 在 event_bus 订阅 news.signals_processed -> _layout_cache.clear()
```

**风险点:** 多 worker 进程时进程内缓存不一致(当前单进程,OK);事件失效要覆盖所有写 topic 的路径。

---

### 10. 前端首屏一次性拉 200(dashboard)/300(feed)条

`newsStore` 默认 `dashboardQuery {limit:200}`、`feedQuery {limit:300}`。后端有游标分页、前端有 `useVirtualList`,但初始负载仍偏大,首屏 TTFB/解析变慢。

**方案:** 首屏拉 50,滚动用已有 `loadMoreFeedNews` 增量;dashboard 概览类只取聚合数,不拉明细列表。

```ts
const feedQuery = ref<NewsQuery>({ limit: 50 });   // 300 -> 50,靠游标续拉
```

**风险点:** 确认依赖"客户端已有全量"做本地过滤的逻辑(`matchesQuery`)在分页下仍正确;否则过滤需下推到后端(后端已支持 market/sentiment/source/q 过滤,直接传参更优)。

---

### 11. pipeline 内 classify / crawl 串行,未利用并发

阶段1 抓正文(I/O 密集)逐条串行;一批 50 条就是 50 次串行网络。

**方案:** 抓取阶段用 `ThreadPoolExecutor` 并发(纯 I/O,GIL 不阻塞),分类阶段保持串行落库。

```python
from concurrent.futures import ThreadPoolExecutor
def _ensure_articles(self, news_ids):
    items = [i for i in self.repository.list_news(news_ids) if i.canonical_url]
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda it: (it.id, self._safe_crawl(it.canonical_url)), items))
    for nid, (text, status, err) in results:          # 落库回到主线程短事务
        with self.session_factory() as s:
            ArticleContentRepository(s).upsert(nid, text, status, err); s.commit()
```

**风险点:** 并发抓取需对目标站点限速/设 UA,避免被封;`max_workers` 配置化;SQLAlchemy 对象不可跨线程,故只在线程里做"抓取"返回纯数据,落库回主线程。

---

### 12. 大量宽泛 `except Exception:` 静默吞错,问题不可观测

`event_bus`、`queue_worker`、`pipeline`、`llm_providers` 等多处 `except Exception` 仅 log warning/继续。后台线程出错被吞,表现为"数据莫名不更新"。

**方案:** 区分**可恢复**(记 metric + 退避重试)与**不可恢复**(标记数据状态 + 告警);至少把吞掉的异常计数暴露到 `worker_runtime_status`(已有该表)。

```python
except Exception as exc:
    self.logger.exception("crawl failed news=%s", item.id)
    self._metrics.incr("pipeline.crawl_error")        # 可观测
    item_status = "failed"                              # 不要无声跳过
```

**风险点:** 不要把所有 except 都改成抛出,后台线程抛出会被 `run_cycle` 兜底但丢一整轮;按"单条失败不影响整批"的粒度收敛。

---

## P3(快速清理 / 工程化)

### 13. cleanup 的 `VACUUM` 会拿独占锁,阻塞所有写
`data_cleanup_vacuum_interval_seconds=604800`(周级)。VACUUM 期间 SQLite 全库加锁。建议改用 `PRAGMA incremental_vacuum` + `auto_vacuum=INCREMENTAL`,或仅在低峰窗口执行并设 `PRAGMA busy_timeout`。

```python
# 替代整库 VACUUM
session.execute(text("PRAGMA auto_vacuum=INCREMENTAL"))  # 建库时设
session.execute(text("PRAGMA incremental_vacuum(1000)")) # 每次回收有限页,不长锁
```

### 14. 详情页 `get_news_detail` 顺序 4 次查询,可合并
`news.py` 里 `get_by_id` + `get_article` + `list_mentions` + `get_topic_for_news` 串行 4 次往返。可用 `selectinload` 关系一次取,或并入一个聚合查询。收益不大但顺手。

```python
stmt = (select(NewsItem)
        .options(selectinload(NewsItem.article),
                 selectinload(NewsItem.mentions),
                 selectinload(NewsItem.topic_links))
        .where(NewsItem.id == news_id))
```
(前提:在模型上补 `relationship` 定义。)

### 15. 仓库整洁度
- `test_output.txt`(42KB)与 `frontend/test_output.txt` 像是测试快照被误入库 —— 应进 `.gitignore`。
- 同时存在 `AGENTS.md` / `ANGENT.md` / `AGENT.md` 三份近似文档(含拼写错误版),建议合并为单一 `AGENTS.md`,避免 agent 读到过期指令。
- `requirements.txt` 与 `environment.yml` 双依赖源,建议统一(pin 版本 + 锁文件)。

---

## 落地路线(分阶段)

```
Phase 1 (本周,止血):  #2 索引  + #3 httpx 池  + #5 去动态import  + #15 清理
                       → 低风险、立即见效,先把"明显慢"和"明显脏"清掉
Phase 2 (核心重构):    #1 pipeline 拆两阶段 + #6 持久化任务队列 + #4 计量缓冲
                       → 解决 SQLite 写锁根因,系统稳定性质变
Phase 3 (体验/扩展):   #7 FTS + #8 异步触发 + #9 缓存 + #10/#11 前端与并发
                       → 搜索与吞吐,面向数据量增长
Phase 4 (打磨):        #12 可观测 + #13 VACUUM + #14 详情聚合
```

**验证清单(每阶段必做):**
1. `pytest`(后端)+ `vitest`(前端)全绿,新增索引/迁移要有回归测试。
2. 用 `EXPLAIN QUERY PLAN` 验证 #2/#7 确实命中索引(看到 `USING INDEX ix_news_published_id`)。
3. 压测脚本:并发触发 refresh + 列表查询,观测 `database is locked` 次数归零(改 #1 前后对比)。
4. `worker_runtime_status` 表里各 worker 的 failure 计数趋势作为长期监控基线。

> 信息缺口(需你确认再细化):①生产实际数据量级(news_item 行数);②是否已出现 `database is locked` 报错(决定 #1/#6 的紧迫度);③feed/dashboard 的真实 QPS(决定 #9 缓存收益)。这三项会直接影响 Phase 1/2 的排序,缺这些我不会拍脑袋给绝对优先级。
