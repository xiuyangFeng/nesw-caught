# Phase 4 体验打磨实施计划

根据 [docs/superpowers/specs/2026-06-13-phase4-polishing-design.md](file:///Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-06-13-phase4-polishing-design.md)，我们将执行如下步骤：

## 1. 任务拆解与待办清单
- [ ] 在 `backend/app/models/news_item.py` 中引入 `relationship` 并在 `NewsItem` 模型上声明 `article`、`mentions` 与 `topics` 关系。
- [ ] 在 `backend/app/repositories/news_repository.py` 中实现 `get_by_id_with_relations` 方法。
- [ ] 重构 `backend/app/api/routes/news.py` 路由中的 `get_news_detail`，改用 `get_by_id_with_relations` 进行聚合关联查询。
- [ ] 在 `backend/app/db/session.py` 的 SQLite 连接初始化 pragma 列表中追加 `cursor.execute("PRAGMA auto_vacuum=INCREMENTAL")`。
- [ ] 在 `backend/app/services/cleanup.py` 中重构 `_run_incremental_vacuum`，增加 auto_vacuum 转换判断，并将单次回收额度限制在 1000 页内。
- [ ] 重构 `backend/app/services/news_signal_pipeline.py` 中的 `process_news_ids`（阶段 2），加入逐条新闻 `try...except` 块以防有毒消息无限重试，并将处理失败状态标记为 `'failed'`。
- [ ] 执行 `make test-backend` 后端测试。
- [ ] 同步更新 `README.md` 与 `docs/code-change-log.md` 记录。

## 2. 验证方案
1. **测试用例验证**：
   运行所有测试以保证没有破坏原有的业务逻辑，且所有 mock 模型正确。
2. **VACUUM 增量状态检测**：
   数据库运行并清理完毕后，使用 SQLite 命令查询模式：
   ```sql
   PRAGMA auto_vacuum;
   ```
   应当返回值为 `2`，表明已经是增量模式。
3. **详情关联查询聚合验证**：
   启动后端服务，获取详情路由并验证数据正确返回。
