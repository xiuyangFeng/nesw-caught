# Phase 4 体验打磨设计文档

## 1. 优化项 #12: 可观测性与有毒消息防范 (Poison Message Defense)
### 问题诊断
目前在 `NewsSignalPipelineService` 处理分类和主题生成的阶段（阶段 2），如果某一条新闻因特定格式或服务错误抛出 `Exception`，会导致这批 50 条新闻全部回滚。下一周期后台 worker 再次拉取这批新闻，形成无限重试的“有毒队列消息”死锁，导致管线长期堵塞。且吞掉的异常缺乏统一的计数指标暴露。

### 设计方案
1. **防范有毒消息 (逐条容错处理)**：
   In `NewsSignalPipelineService.process_news_ids` 的循环中，使用 `try...except Exception` 包裹每条新闻的 `_process_item` 分类和映射操作。
   - 如果某条新闻处理发生异常，不抛出异常打断整批，而是捕获该异常。
   - 将其 `sentiment_label` 设为 `None`，`sentiment_score` 设为 `None`。
   - 将其 `signal_status` 设为 `"failed"`，把异常字符串存入 `signal_error` 中，更新 `signal_updated_at`。
   - 在已处理的 `processed_news_ids` 列表中包含该 ID，使得它在这一轮中能够推进，而不是留在 pending 队列中。
2. **记录局部异常到 Metrics/Logs**：
   - 使用 `logger.exception` 详细记录包含堆栈的错误日志，方便运维排查。
   - 这能保证该批次中的其余正常新闻被成功提交，而损坏新闻也被持久化记录错误状态，不再重试，安全止血。

---

## 2. 优化项 #13: VACUUM 优化 (PRAGMA incremental_vacuum)
### 问题诊断
系统虽然在 cleanup 任务中使用了 `PRAGMA incremental_vacuum`，但 SQLite 能够允许 `incremental_vacuum` 的前提是数据库在没有任何表被创建之前通过 `PRAGMA auto_vacuum = INCREMENTAL` 进行了初始化，或者使用 `PRAGMA auto_vacuum = INCREMENTAL` 后手动执行了一次 `VACUUM` 转换。
若不执行该模式转换，调用 `PRAGMA incremental_vacuum` 是无效的。且不带参数的 `incremental_vacuum` 仍然会回收所有页，当空间极大时依然会产生长写锁。

### 设计方案
1. **自动转换 auto_vacuum 模式**：
   在 `app/services/cleanup.py` 里的 `_run_incremental_vacuum` 方法中：
   - 首先执行 `PRAGMA auto_vacuum` 获取当前模式。
   - 如果返回值不是 `2`（2 表示 `INCREMENTAL`），则执行一次 `PRAGMA auto_vacuum = INCREMENTAL;` 并紧跟着运行一次 `VACUUM;`。这会重组整个数据库页格式，将其完美转换为增量模式。
   - 这样能对已有生产数据库和测试数据库做自适应无缝升级。
2. **每次回收有限页**：
   - 当模式转换完成后，后续调用时，运行 `PRAGMA incremental_vacuum(1000)` 以限制每次回收的页数（例如最多回收 1000 个空闲页），从而杜绝耗时极长的独占写锁。
3. **连接层 pragma 注入**：
   - 在 `app/db/session.py` 的 SQLite 连接回调中，增加 `cursor.execute("PRAGMA auto_vacuum=INCREMENTAL")`，确保任何新创建的空白数据库文件直接以增量模式初始化。

---

## 3. 优化项 #14: 详情页 SQL 聚合 (Relationship + selectinload 优化)
### 问题诊断
当访问 `/api/news/{id}` 时，后端执行了 4 次独立的串行数据库查询以拼装详情视图：
1. `get_by_id` 查新闻主体 (news_item)
2. `get_article` 查正文 (article_content)
3. `list_mentions` 查股票提及 (news_stock_mention)
4. `get_topic_for_news` 查关联主题 (topic_cluster)
多次 SQL 往返开销在高吞吐下造成了性能损耗。

### 设计方案
1. **补充 Relationship 映射**：
   在 `app/models/news_item.py` 的 `NewsItem` 模型上声明单向关系（不需要双向以减少其它文件的变动）：
   ```python
   from sqlalchemy.orm import relationship
   
   article = relationship("ArticleContent")
   mentions = relationship("NewsStockMention")
   topics = relationship("TopicCluster", secondary="topic_news_link")
   ```
2. **实现聚合查询函数**：
   在 `NewsRepository` 中新增 `get_by_id_with_relations(self, news_id: int) -> NewsItem | None`：
   ```python
   from sqlalchemy.orm import selectinload
   
   def get_by_id_with_relations(self, news_id: int) -> NewsItem | None:
       stmt = (
           select(NewsItem)
           .options(
               selectinload(NewsItem.article),
               selectinload(NewsItem.mentions),
               selectinload(NewsItem.topics)
           )
           .where(NewsItem.id == news_id)
       )
       return self.session.scalar(stmt)
   ```
   该方法仅发出 3-4 次 IN 子查询，合并在一次查询处理中。
3. **路由重构**：
   In `backend/app/api/routes/news.py` 路由中，直接调用上述预加载方法，并从对象属性 `item.article`、`item.mentions` 和 `item.topics` 中快速组装并返回 `NewsDetailView`，完全消除原本 4 次独立查询的往返延迟。
