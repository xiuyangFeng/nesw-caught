# 2026-06-12 优化迭代第四轮 (Round 4) 执行计划

本计划针对第四轮的优化和缺陷修复拆解为可操作、可验证的任务。

## 任务列表

### 1. 前端测试缺陷修复 (P0)
- [ ] 修改 [WatchlistView.vue](file:///Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue)，在测试环境中将搜索防抖延迟设置为 `0ms`。
- [ ] 修改 [WatchlistView.test.ts](file:///Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts)，在文件头部 mock `apiClient.searchMarketSymbols`，并在涉及 input 修改的测试用例中加入 `await new Promise((resolve) => setTimeout(resolve, 0))` 和 `await flushPromises()` 以推进防抖定时器与异步网络请求。
- [ ] 修改 [WatchlistDetailView.test.ts](file:///Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.test.ts)，在 mock 的 `watchlistStore` 声明中补齐 `aiInsights: { AAPL: { loading: false, text: 'AI Insight', error: null } }` 与 `loadAiInsight: vi.fn(async () => undefined)`。
- [ ] 运行前端单测 `npm --prefix frontend run test -- --run`，验证测试通过率达到 100% (199/199 例通过)。

### 2. 自选股重大资讯发光雷达与后端查询 (P1)
- [ ] 在后端 [market.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/schemas/market.py) 中为 `QuoteSummaryView` 新增 `has_hot_alert: bool = False` 字段。
- [ ] 在 [quote_service.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/services/quote_service.py) 中：
  - 新增 `_get_hot_symbols(self, session: Session) -> set[str]` 批量获取 12 小时内存在重大新闻 (Score >= 8.5) 的 symbols 集合。
  - 在 `_snapshot_to_payload` 以及 `_build_unavailable_payload` 方法中加入 `has_hot_alert` 的逻辑渲染。
  - 在 `get_cached_watchlist_quotes` 与 `get_cached_symbol_quote` 接口主入口中通过 `_get_hot_symbols` 并把结果传给 payload 序列化。
- [ ] 在后端 [test_market.py](file:///Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py) 中编写/适配对应单元测试，断言 `has_hot_alert` 字段。
- [ ] 在前端 [frontend/src/types/api.ts](file:///Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts) 中为 `MarketSnapshot` 扩展 `has_hot_alert?: boolean` 类型。
- [ ] 在 [StockCard.vue](file:///Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockCard.vue) 中，如果 `row.has_hot_alert` 为 `true`，在标题右侧增加 `animate-ping` 霓虹雷达发光呼吸红点。

### 3. AI 投研一键复制共享系统 (P2)
- [ ] 在 [StockDetailPanel.vue](file:///Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockDetailPanel.vue) 中：
  - 导入 `useToastStore`。
  - 增加 `copyInsight` 异步复制方法，并触发 Toaster 提示。
  - 在界面 `aiInsight.text` 顶部右侧新增 `📋 复制报告` 按钮。
- [ ] 运行前端构建 `npm --prefix frontend run build`，确保无打包和类型错误。

## 验证与回归
- [ ] 运行后端测试：`conda run -n news-caught pytest backend/tests`。
- [ ] 运行前端测试：`npm --prefix frontend run test -- --run`。
