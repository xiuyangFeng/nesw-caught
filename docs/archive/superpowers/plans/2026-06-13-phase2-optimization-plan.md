# Phase 2 优化计划 (2026-06-13)

本计划对应 [2026-06-13-phase2-optimization-design.md](file:///Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-06-13-phase2-optimization-design.md) 中设计方案的实施步骤。

## 1. 实施步骤

### 阶段 1: 大模型计量落库缓冲 (#4)
- [ ] 创建 `backend/app/services/token_usage_buffer.py`，实现 `TokenUsageBuffer` 类以进行内存合并与批量落库。
- [ ] 修改 `backend/app/services/llm_providers.py`：
  - 实例化全局单例 `token_usage_buffer = TokenUsageBuffer()`。
  - 在 `log_token_usage` 内调用该 buffer 进行异步批量缓冲写入。
- [ ] 修改 `backend/app/main.py` 的 lifespan，在应用退出时调用 `token_usage_buffer.flush()`，确保所有未刷盘数据落库。
- [ ] 运行测试验证 `pytest backend/tests/test_llm_stats.py`，确保在 pytest 环境下（测试自动识别为同步）能完全跑通。

### 阶段 2: 任务队列持久化与自愈 (#6)
- [ ] 修改 `backend/app/workers/queue_worker.py`：
  - 在 `BackgroundQueueWorker.do_cycle` 里，若从内存队列 `analysis_queue` 取得的数据为空，则调用数据库 API 主动获取 Pending 的新闻 ID 列表（`list_pending_news_ids`）。
  - 在实例化 `NewsSignalPipelineService` 时传入 `self.session_factory`，以便在阶段 1 启动短事务。
- [ ] 运行测试验证 `pytest backend/tests/test_news_ingestion.py`，确保对已有通知及后台任务没有破坏。

### 阶段 3: Pipeline 拆分为两阶段 (#1)
- [ ] 修改 `backend/app/services/news_signal_pipeline.py`：
  - 支持接收 `session_factory` 构造参数。
  - 增加 `_safe_crawl` 异常安全网络抓取方法。
  - 重构 `process_news_ids`，将其拆为 `_ensure_articles`（阶段 1 正文补全，使用 `session_factory` 的短生命周期 Session 逐条提交）和分类及主题分配（阶段 2 核心处理，使用主 Session 极快 commit）。
- [ ] 运行整个后端测试套件：`conda run -n news-caught pytest backend/tests`。
