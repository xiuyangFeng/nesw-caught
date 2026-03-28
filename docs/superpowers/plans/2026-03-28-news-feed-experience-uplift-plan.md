# News Feed 体验提升实现计划

> 日期: 2026-03-28
> 设计文档: `docs/superpowers/specs/2026-03-28-news-feed-experience-uplift-design.md`

---

## Task 1: 后端跨 Topic 事件融合

### 前置
- 无

### 步骤
1. 在 `news_feed_layout.py` 新增 `_title_overlap(a, b) -> float` 标题 token 重叠度计算
2. 新增 `_should_fuse(card_a, card_b) -> bool` 融合判断
3. 新增 `fuse_event_cards(cards) -> list[NewsFeedEventCardView]` 融合函数
4. 在 `build_event_cards` 排序前调用 `fuse_event_cards`
5. 新增后端测试：同 symbol 融合、标题重叠融合、general 不融合、多卡链式融合

### 验证
- `conda run -n news-caught pytest backend/tests/test_news_feed_layout.py`

## Task 2: 后端 stream 编辑排序

### 前置
- 无

### 步骤
1. `schemas/news.py` 的 `NewsItemSummary` 新增 `editorial_score: float | None = None`
2. `news_feed_layout.py` 新增 `score_stream_items()` 函数
3. `build()` 方法中调用 `score_stream_items` 对 stream 排序
4. 新增后端测试：primary source 排前、有 mention 排前、时间衰减

### 验证
- `conda run -n news-caught pytest backend/tests/test_news_feed_layout.py`

## Task 3: 前端编辑排序接入

### 前置
- Task 2 完成后 `stream` 返回带 `editorial_score` 的数据

### 步骤
1. `types/api.ts` 的 `NewsItem` 新增 `editorial_score?: number | null`
2. `NewsFeedView.vue` 的 `orderedEntries` 改为调用 `rankEditorialStories`
3. 更新 `NewsFeedView.test.ts`

### 验证
- `npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts`
- `npm --prefix frontend run build`

## Task 4: 修复并启用 NewsVirtualList

### 前置
- Task 3 完成后 editorial 排序已生效

### 步骤
1. 重写 `NewsVirtualList.vue`：props 改为 `entries: EditorialStoryEntry[]`，传 `:entry` 给 NewsCard，emit `open`
2. `NewsFeedView.vue` News Stream 区域：当 entries > 30 时使用 `NewsVirtualList`，否则保持 `v-for`
3. 更新相关测试

### 验证
- `npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts`
- `npm --prefix frontend run build`

## Task 5: 历史新闻重分类脚本

### 前置
- 无（可与其他任务并行）

### 步骤
1. 新建 `scripts/reprocess_news_signals.py`
2. 支持 `--limit`, `--all`, `--dry-run` 参数
3. 分批调用现有 pipeline

### 验证
- 手动 `conda run -n news-caught python scripts/reprocess_news_signals.py --dry-run`

## Task 6: 集成验证 + 变更记录

### 步骤
1. 运行全部后端测试
2. 运行全部前端测试
3. 前端 build
4. 更新 `docs/code-change-log.md`
