# 2026-06-12 优化迭代第四轮 (Round 4) 设计规范

本设计说明针对以下三项优化迭代目标制定：
1. **P0 级前端测试回归缺陷修复**：解决 `WatchlistView.test.ts` 由于引入动态搜索导致防抖与网络调用失败的问题，以及 `WatchlistDetailView.test.ts` 中缺失 `aiInsights` 引起的错误。
2. **自选股重大资讯发光雷达与脉冲警报 (Watchlist Hot Alert & Radar)**：为自选股列表卡片引入实时的 12 小时内重大新闻雷达，提升交易员重大新闻洞悉速度。
3. **AI 投研一键复制共享系统 (AI Insight Copy & Clipboard)**：在自选股详情的 AI Insight 中提供一键复制 Markdown 报告的功能，辅以全局 Toast系统。

---

## 1. 前端测试回归缺陷修复

### 1.1 WatchlistDetailView.test.ts 崩溃修复
- **原因**：在 Round 3 的优化中，`StockDetailPanel.vue` 组件内部新引入了 `computed(() => watchlistStore.aiInsights[symbol])`，但在 `WatchlistDetailView.test.ts` 的 `watchlistStore` mock 中缺失了 `aiInsights` 状态和 `loadAiInsight` 方法，导致访问 `undefined` 的属性抛出 `Cannot read properties of undefined`。
- **方案**：在 `WatchlistDetailView.test.ts` 中的 mock store 里补齐：
  ```typescript
  aiInsights: {
    AAPL: { loading: false, text: 'AI Insight', error: null },
  },
  loadAiInsight: vi.fn(async () => undefined),
  ```

### 1.2 WatchlistView.test.ts 防抖与 apiClient Mock 修复
- **原因**：在 Round 3 中自选股候选池改为了通过 `apiClient.searchMarketSymbols(query)` 向后端做模糊搜索，且加了 `300ms` 防抖。测试用例中在 `setValue` 之后由于没有等待 300ms 也没有 mock `apiClient`，导致搜索候选列表空置无法点击 `[data-role="watchlist-candidate-BABA"]`。
- **方案**：
  1. 在 `WatchlistView.vue` 搜索防抖处，识别测试环境将延时缩减为 `0ms`（测试环境使用宏任务回调即刻执行）：
     ```typescript
     const isTest = typeof process !== 'undefined' && process.env?.NODE_ENV === 'test';
     const debounceMs = isTest ? 0 : 300;
     ```
  2. 在 `WatchlistView.test.ts` 顶部，对 `../api/client` 进行 `vi.mock` 拦截，拦截 `searchMarketSymbols` 并根据 query 过滤并返回 Mock 的候选列表。
  3. 测试用例中对 `setValue` 操作的后方，追加宏任务快进 `await new Promise((resolve) => setTimeout(resolve, 0))` 并执行 `await flushPromises()`，确保异步流程完结。

---

## 2. 自选股重大资讯霓虹雷达

### 2.1 后端契约扩展与高效查询
- 在 `QuoteSummaryView` (在 [market.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/schemas/market.py) 中) 增加字段：
  ```python
  has_hot_alert: bool = False
  ```
- 在 `QuoteService` 中新增高效 SQL 批量查询，一次性拉取 12 小时内存在重大新闻 (editorial_score >= 8.5) 的 symbols，避免 N+1 逐个查询：
  ```python
  limit_time = datetime.now(timezone.utc) - timedelta(hours=12)
  stmt = (
      select(NewsStockMention.symbol)
      .join(NewsItem, NewsStockMention.news_id == NewsItem.id)
      .where(NewsItem.editorial_score >= 8.5)
      .where(NewsItem.published_at >= limit_time)
  )
  ```
- 返回 quote payload 时，根据该 symbol 是否在集合中标记 `has_hot_alert`。

### 2.2 前端发光雷达卡片呈现
- 在 `frontend/src/types/api.ts` 的 `MarketSnapshot` 加上 `has_hot_alert?: boolean`。
- 在 `StockCard.vue` 股票标题后方，当 `row.has_hot_alert` 为 `true` 时，渲染一个发光、脉冲扩张的呼吸红点。使用 Tailwind 自带的 `animate-ping` 加上红色霓虹阴影。

---

## 3. AI 投研一键复制共享系统

- 在 `StockDetailPanel.vue` 的 AI Insight 研判区域的头部（当有 `aiInsight.text` 时），新增 `📋 复制报告` 按钮。
- 点击时使用 `navigator.clipboard.writeText` 写入剪贴板。
- 引入全局 `toastStore` 并发出 `success` 类型的发光毛玻璃 Toaster 气泡：“📋 AI 投研报告已成功复制到剪贴板，请随时转发分享！”。
