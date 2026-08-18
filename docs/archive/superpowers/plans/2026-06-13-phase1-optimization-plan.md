# Phase 1 优化计划 (2026-06-13)

本计划对应 [2026-06-13-phase1-optimization-design.md](file:///Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-06-13-phase1-optimization-design.md) 中设计方案的实施步骤。

## 1. 实施步骤

### 阶段 1: 准备与仓库整洁度清理 (#15)
- [ ] 备份相关文档，清理测试输出。
- [ ] 修改根目录 `.gitignore`，增加忽略 `test_output.txt` 和 `**/test_output.txt`。
- [ ] 从 git 中移除已提交的 `test_output.txt` 和 `frontend/test_output.txt`。
- [ ] 合并并更新 `AGENTS.md` 和 `ANGENT.md`，统一其内容，保持双向一致。

### 阶段 2: 消除动态 import 依赖 (#5)
- [ ] 修改 `backend/app/workers/queue_worker.py`，将 `get_notification_service` 的导入移到文件顶部。
- [ ] 修改 `backend/app/services/news_signal_pipeline.py`，将 `crawl_and_extract_article` 和 `ArticleContent` 的导入移到文件顶部。
- [ ] 运行测试，确保无导入错误和循环依赖问题。

### 阶段 3: 复合索引与数据库迁移 (#2)
- [ ] 修改 `backend/app/models/news_item.py`，引入复合索引 `ix_news_published_id` 和 `ix_news_market_published_id`。
- [ ] 运行 alembic 自动生成迁移文件：`conda run -n news-caught alembic -c backend/alembic.ini revision --autogenerate -m "add_news_item_composite_indexes"`。
- [ ] 检查并微调生成的迁移文件（确保其在 `news_item` 上正确创建了这两个索引）。
- [ ] 执行迁移：`conda run -n news-caught alembic -c backend/alembic.ini upgrade head`。
- [ ] 在测试环境中使用 `EXPLAIN QUERY PLAN` 验证游标分页确实使用了这两个复合索引。

### 阶段 4: 共享连接池 `httpx.Client` 重构 (#3)
- [ ] 修改 `backend/app/core/config.py`，在 `Settings` 中添加 `llm_timeout_seconds`（默认 60.0）。
- [ ] 新建 `backend/app/services/http_pool.py` 并实现 `get_llm_client()` 与 `close_llm_client()`。
- [ ] 修改 `backend/app/main.py` 的 `lifespan` 钩子，增加 `close_llm_client()` 的调用。
- [ ] 修改 `backend/app/services/llm_providers.py`，将 `_request_completion` 与 `embed_text` 重构为使用共享 client（注意密钥在 `post` 时动态传递，不写入默认连接池配置）。
- [ ] 运行后端测试，确保所有 LLM Provider 的单元测试和集成测试依然通过。

---

## 2. 验证方案

### 自动化测试
- 运行整个后端测试套件：`conda run -n news-caught pytest backend/tests`。
- 运行前端构建，确保静态资源可以正常编译：`npm --prefix frontend run build`。

### 手动验证与索引计划验证
- 验证 SQLite 中复合索引的使用：
  ```sql
  EXPLAIN QUERY PLAN SELECT * FROM news_item WHERE published_at < '2026-06-13' OR (published_at = '2026-06-13' AND id < 100) ORDER BY published_at DESC, id DESC LIMIT 50;
  ```
  应当能看到类似 `USING INDEX ix_news_published_id` 的输出。
