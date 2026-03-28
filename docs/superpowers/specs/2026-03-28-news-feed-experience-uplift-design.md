# News Feed 体验提升设计

> 日期: 2026-03-28
> 范围: 跨 Topic 事件融合、编辑排序打分落地、NewsVirtualList 启用、历史新闻重分类

---

## 1. 跨 Topic 事件融合

### 问题

当前 `build_event_cards` 按 topic 一对一生成事件卡。同一真实事件（如"美联储降息"）可能被分到多个 topic（宏观 topic + 个股 topic），导致事件卡重复。

### 方案

在 `build_event_cards` 生成事件卡列表后、排序前，新增 **事件融合层** `fuse_event_cards`。

**融合规则**:
1. 按 `event_type` 分组（`general` 类型不参与融合，保持独立）
2. 同组内，如果两张卡的 `primary_symbol` 相同，或 `related_symbols` 交集 >= 2，或标题 token 重叠 >= 50% → 融合为一张
3. 融合时取 importance 较高的卡为 primary，合并 `news_items`（去重）、取并集 `related_symbols`、`source_count` 合计、`news_count` 合计
4. 融合后重新计算 `event_key`，格式为 `fused-{id1}-{id2}`

**实现位置**: `news_feed_layout.py` 新增 `fuse_event_cards()` 函数，在 `build_event_cards` 末尾排序前调用。

**不新增持久化**: 融合仍然是请求时派生计算。

## 2. 编辑排序打分落地

### 问题

前端已有 `EditorialStoryEntry.score` 和 `rankEditorialStories` / `getEditorialScore` 函数，但 `NewsFeedView.orderedEntries` 中 `score` 始终为 0，且未调用排序函数。

### 方案

**前端**:
- `orderedEntries` 改为调用 `rankEditorialStories(feedStreamItems, newsStore.detailMap)` 替代当前简单的 `map`
- 排序后按 editorial score 降序展示

**后端 stream 排序增强**:
- `news_feed_layout.py` 的 `NewsFeedLayoutService.build()` 中 stream 目前直接用 `news_repository.list_recent()` 返回的原始顺序（按 published_at desc）
- 新增 `score_stream_items()` 函数，为每条 stream item 计算一个服务端排序分数，综合考虑：
  - `importance_score`（来自关联 topic，0-1，权重 0.4）
  - 来源 tier 权重（primary 1.2 / secondary 1.0 / fallback 0.7，权重 0.25）
  - 新鲜度衰减（同事件的 DECAY_LAMBDA，权重 0.2）
  - 是否有 stock mentions（有则 +0.15，权重 0.15）
- stream 按 editorial_score 降序返回

**后端 schema 变更**: `NewsItemSummary` 新增可选字段 `editorial_score: float | None = None`。

## 3. NewsVirtualList 修复并启用

### 问题

`NewsVirtualList.vue` 存在但未使用，且 props 接口与当前 `NewsCard` 不匹配（传 `:item`/`:detail`/`:active`，但 `NewsCard` 期望 `:entry`）。

### 方案

**修复 NewsVirtualList**:
- Props 改为接受 `entries: EditorialStoryEntry[]` 而非 `items: NewsItem[]` + `detailMap`
- 内部传给 `NewsCard` 时使用 `:entry` prop
- 移除 `activeId` 和 `select` emit，改用 `open` emit（与 NewsCard 一致）
- 行高从固定 184px 改为更合理的估算值（~100px，因为 compact card 更矮），或使用 CSS variable

**启用位置**: `NewsFeedView.vue` 的 News Stream 部分，当 stream items > 30 时自动使用 `NewsVirtualList`，否则保持简单 `v-for`。

## 4. 历史新闻重分类脚本

### 问题

中文情绪/event_type 改进只对新摄入新闻生效，已入库旧新闻仍是 `neutral` + `general`。

### 方案

新增 `scripts/reprocess_news_signals.py`，一次性重跑所有 `signal_status IS NULL` 或 `signal_status = 'pending'` 的新闻：

1. 查询所有未处理新闻 ID
2. 分批调用 `NewsSignalPipelineService.process_news_ids(batch_ids)`（复用现有管线，每批 50 条）
3. 打印进度和统计
4. 支持 `--limit` 参数限制处理数量
5. 支持 `--all` 参数重跑全部新闻（包括已 processed 的）
6. 支持 `--dry-run` 只统计不执行

**不新增 API 端点**: 纯 CLI 脚本，不走 HTTP。

---

## 影响范围

| 改动 | 后端 | 前端 | 数据结构 |
|---|---|---|---|
| 跨 Topic 融合 | `news_feed_layout.py` | 无 | 无 |
| 编辑排序 | `news_feed_layout.py`, `news.py`(schema) | `NewsFeedView.vue` | `NewsItemSummary` +1 字段 |
| NewsVirtualList | 无 | `NewsVirtualList.vue`, `NewsFeedView.vue` | 无 |
| 重分类脚本 | `scripts/reprocess_news_signals.py` | 无 | 无 |

## 风险

1. 跨 Topic 融合是请求时计算，topic 数量极大时可能影响延迟 → 当前 topic 数量有限，暂可接受
2. stream editorial score 依赖 topic 关联，未关联 topic 的新闻 fallback 为 0 → 新鲜度仍能保底
3. VirtualList 固定行高可能与实际 card 高度不一致 → 后续可升级为动态行高
4. 重分类脚本一次性更新大量行 → 分批处理，每批 flush
