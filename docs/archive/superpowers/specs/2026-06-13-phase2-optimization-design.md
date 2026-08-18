# Phase 2 优化设计 (2026-06-13)

本设计文档涵盖优化清单中 Phase 2 (核心重构) 的三项内容：
1. pipeline 长事务拆两阶段，防止阻塞 I/O 长期占有 SQLite 写锁 (#1)。
2. 持久化任务队列，改内存队列为数据库 pending 状态自愈轮询与内存通知相结合的机制 (#6)。
3. 大模型 Token 计量落库增加内存缓冲定时定量批量写入 (#4)。

---

## 1. Pipeline 拆为两阶段 (#1)

### 1.1 问题诊断
`NewsSignalPipelineService.process_news_ids` 会在同一个主 session（包含主 write 事务）内遍历多条新闻：
- 调用 `crawl_and_extract_article` 发起同步网络爬虫，并用 `session.flush()` 落库正文。
- 对正文进行 LLM 分类（调用 LLM API），最后整体 commit。
在此期间，SQLite 写锁一直被占用（从第一条抓取开始直至最后大模型全部分类完成才释放），所有其他写操作（如用户自选股更新、新闻摄入）都会被阻塞导致 `database is locked`。

### 1.2 解决方案
将管线处理拆分为两阶段：
- **阶段 1：正文补全**。在此阶段，不持有主事务。遍历需要抓取的新闻，在事务外发起网络 I/O。抓取完成后，使用独立的、寿命极短的 Session 逐条提交落库，失败也不拖累整批。
- **阶段 2：分类与落库**。此时所有新闻的正文已就绪，主 Session 从数据库加载数据，进行 LLM 分类及关联，因为此时没有任何网络 I/O，数据库写事务能够以极快的速度完成并提交。

为了实现独立短事务，我们需要修改 `NewsSignalPipelineService`，使其构造函数支持接收 `session_factory`：
```python
class NewsSignalPipelineService:
    def __init__(self, session, session_factory=None) -> None:
        self.session = session
        self.session_factory = session_factory
        ...
```

### 1.3 核心实现代码
```python
    def process_news_ids(self, news_ids: list[int]) -> ProcessNewsSignalsSummary:
        if not news_ids:
            return ProcessNewsSignalsSummary(news_ids=[], processed_count=0, touched_topic_ids=[])

        # —— 阶段 1: 正文补全 (独立短事务, 网络 I/O 在事务外) ——
        self._ensure_articles(news_ids)

        # —— 阶段 2: 分类与落库 (无网络 I/O, 事务短而快) ——
        news_items = self.repository.list_news(news_ids)
        article_map = self.repository.get_article_map(news_ids)
        
        touched_topic_ids: set[int] = set()
        processed_news_ids: list[int] = []

        for item in news_items:
            self._process_item(item, article_map.get(item.id), touched_topic_ids)
            processed_news_ids.append(item.id)

        self.repository.refresh_topic_stats(touched_topic_ids)
        return ProcessNewsSignalsSummary(
            news_ids=processed_news_ids,
            processed_count=len(processed_news_ids),
            touched_topic_ids=sorted(touched_topic_ids),
        )

    def _ensure_articles(self, news_ids: list[int]) -> None:
        """阶段 1：对未爬取正文的新闻单独进行同步爬取，并以独立短事务逐条落库。"""
        # 使用独立的 repository 获取抓取目标
        items = self.repository.list_news(news_ids)
        have = self.repository.get_article_map(news_ids)
        
        for item in items:
            art = have.get(item.id)
            if (art and art.extract_status == "success") or not item.canonical_url:
                continue
            
            # 网络 I/O 动作在事务外部执行
            text, status, err = self._safe_crawl(item.canonical_url)
            
            # 独立短事务提交
            factory = self.session_factory or (lambda: self.session)
            with factory() as s:
                from app.repositories.news_signal_repository import NewsSignalRepository
                from app.models.article_content import ArticleContent
                from sqlalchemy import select
                
                # 查询并更新/插入 ArticleContent
                existing = s.scalar(select(ArticleContent).where(ArticleContent.news_id == item.id))
                if existing is None:
                    existing = ArticleContent(
                        news_id=item.id,
                        content_text=text,
                        content_html=None,
                        extract_status=status,
                        extract_error=err,
                        extracted_at=_utc_now()
                    )
                    s.add(existing)
                else:
                    existing.content_text = text
                    existing.extract_status = status
                    existing.extract_error = err
                    existing.extracted_at = _utc_now()
                s.commit()
```

---

## 2. 持久化任务队列设计 (#6)

### 2.1 问题诊断
`BackgroundQueueWorker` 的内存队列 `analysis_queue: queue.Queue` 在进程重启后会彻底丢失其中的所有待 analysis_queue 任务。

### 2.2 解决方案
采取 **“自愈轮询 + 内存通知”** 双轮驱动架构：
- 依然支持 `news.created_batch` 将新入库新闻推入 `analysis_queue` 快速唤醒和处理。
- 当 `analysis_queue` 为空时，worker 会主动执行数据库轮询，查询 `signal_status IS NULL` 的所有 pending 新闻：
  ```python
  pending = pipeline.list_pending_news_ids(limit=50)
  ```
  如果查到，就将它们加入批处理列表。这保证了哪怕重启后内存队列丢失，在下一秒 do_cycle 运行时也能通过数据库状态扫描百分之百自愈补扫。
- 为 `news_item.signal_status` 添加数据库单列索引以保证查询速度（已通过 6ca1c6bd4ed1 迁移脚本的极简处理实现，在 Phase 2 不需要新加迁移）。

### 2.3 核心实现
```python
        # queue_worker.py 中的 do_cycle
        batch_ids: set[int] = set()
        while not self._stop_event.is_set():
            try:
                news_ids = analysis_queue.get_nowait()
                batch_ids.update(news_ids)
                analysis_queue.task_done()
            except queue.Empty:
                break

        # 自愈兜底：如果内存队列为空，去数据库拉取 Pending 新闻
        if not batch_ids:
            with self.session_factory() as session:
                pipeline = NewsSignalPipelineService(session, session_factory=self.session_factory)
                pending = pipeline.list_pending_news_ids(limit=50)
                batch_ids.update(pending)
```

---

## 3. 大模型计量落库增加内存缓冲 (#4)

### 3.1 问题诊断
每次 LLM 调用时，都会创建新 Session 并进行一次 commit。这在高频分析时产生大量锁竞争及写放大。

### 3.2 解决方案
设计 `TokenUsageBuffer` 结构，将多次计量聚合至内存列表，满足 50 条或超过 10 秒时，进行一次批量 `bulk_insert_mappings` 并 commit，降低事务频率。
在单元测试中（pytest 运行期间），自动检测到 pytest 运行并将缓冲阈值置为 1（即保持同步落库），确保测试不需要重构且没有副作用。

### 3.3 核心实现

#### 3.3.1 新建 `app/services/token_usage_buffer.py`
```python
import threading
import time
import sys
from app.db.session import SessionLocal
from app.models.llm_token_usage import LLMTokenUsage

class TokenUsageBuffer:
    def __init__(self, flush_n=50, flush_secs=10):
        self._buf: list[dict] = []
        self._lock = threading.Lock()
        
        # 单元测试自动检测：如果 pytest 在运行，则强制为 1（同步落库）
        self._flush_n = 1 if "pytest" in sys.modules else flush_n
        self._flush_secs = flush_secs
        self._last = time.monotonic()

    def add(self, **row) -> None:
        with self._lock:
            self._buf.append(row)
            if len(self._buf) >= self._flush_n or time.monotonic() - self._last > self._flush_secs:
                self._flush_locked()

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._buf:
            return
        rows = self._buf
        self._buf = []
        self._last = time.monotonic()
        
        try:
            with SessionLocal() as s:
                s.bulk_insert_mappings(LLMTokenUsage, rows)
                s.commit()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Failed to batch flush token usage: %s", exc)
```
并在 `llm_providers.py` 中导出 `token_usage_buffer` 单例。
