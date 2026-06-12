# Enhanced Dashboard 实施计划 (Plan)

本项目将为前端 DashboardView 落地四大优化模块。本计划明确了改动的组件列表、验证方式及开发路径。

## 1. 计划改动文件列表

### [NEW] [SentimentGauge.vue](file:///Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/SentimentGauge.vue)
- **内容**：实现一个半圆（180度）SVG 指针仪表盘。
- **Props**：`positiveCount: number`, `negativeCount: number`。
- **逻辑**：计算 `ratio = positive / (positive + negative)`。用 CSS transform transition 实现指针旋转，左半区域绿色代表偏空占比，右半区域红色代表偏好占比，支持 0 值的兜底渲染。

### [NEW] [BreakingNewsSpotlight.vue](file:///Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/BreakingNewsSpotlight.vue)
- **内容**：渲染顶部心跳脉冲式的高价值新闻快讯横幅。
- **Props**：`newsItems: NewsItem[]`, `topics: TopicItemView[]`。
- **事件**：`@select-news(id: number)`。
- **逻辑**：检索 12 小时内最重要（importance_score >= 8.5）的新闻，或极端情绪新闻，向用户滚动高亮推荐。

### [NEW] [NewsDetailDrawer.vue](file:///Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsDetailDrawer.vue)
- **内容**：极速右侧滑出式新闻阅览抽屉，融合完整正文展示与 AI 解读。
- **Props**：`newsId: number | null`, `visible: boolean`, `filteredNewsIds: number[]`（用于上一篇/下一篇在当前过滤范围内的导航）。
- **Events**：`@close`，`@change-news(id: number)`。
- **逻辑**：在挂载或 `newsId` 变更时触发 `newsStore.loadDetail(id)` 和 `loadAnalysis(id)`。展示新闻核心内容，并提供 AI 魔棒分析操作和上下翻页操作。

### [MODIFY] [DashboardView.vue](file:///Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue)
- **内容**：
  - 接入 `BreakingNewsSpotlight` 到页面顶部；
  - 在仪表盘第一行（HeroMetrics 和 新版 SentimentGauge 并排展示）；
  - 引入全局控制页签（MarketSelector：全部 / A股 / 港股 / 美股，及只看利好/利空过滤器）；
  - 拦截 Feed 中的新闻点击事件，触发拉起 `NewsDetailDrawer` 抽屉；
  - 重构 `metrics` 计算逻辑、`dashboardFeedItems` 和 `moverPreviewItems`，使其完美联动当前选中的市场过滤态。

---

## 2. 验证计划

### 自动化验证
- 前端 TypeScript 编译检查：
  ```bash
  npm --prefix frontend run build
  ```
- 运行现有的前端测试，确保主流程未被破坏：
  ```bash
  npm --prefix frontend run test
  ```

### 手动验证
1. 启动 `make dev` 服务；
2. 访问 Dashboard 页，确认顶部突发快讯横幅发光显眼；
3. 点击市场过滤器（如“港股”），确认四个核心指标、情绪折线、下方新闻 Feed、聚合主题和 Movers 列表全部实时联动更新，且 SVG 罗盘偏转动效流畅；
4. 点击新闻，确认右侧 0 毫秒滑出半透明抽屉，加载并显示正文与 AI 解析，点击“下一篇”在当前过滤范围内正确流转；
5. 点击遮罩层，抽屉平滑收回。
