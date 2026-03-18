# News Feed Unified Horizontal List Design

## 背景

上一轮首页改造虽然压暗了终端配色，但仍保留了 editorial 分层结构：`Primary Signal` 把首条新闻放大，`Signal Queue` 再抽出 3 条作为独立组。实际阅读上，这会人为打断新闻原有顺序，也让中间三张卡继续呈现偏竖向的大卡效果，不符合“快速横向扫读”的目标。

## 目标

- 取消 `Primary Signal` 和“重要新闻放大”逻辑。
- 首页新闻按当前数据顺序直接展示，不再根据 importance 或 score 重新排序。
- 所有新闻使用同一种横向信息卡样式，避免出现竖向高卡。
- 保持现有筛选、详情跳转、数据加载与 mock 降级逻辑不变。

## 非目标

- 不修改后端返回顺序。
- 不新增新的排序选项。
- 不改动新闻详情页、Dashboard 或 Watchlist 结构。

## 设计方案

### 1. 首页改成单一列表

`NewsFeedView` 不再从 `groupEditorialStories` 中拆出 lead / supporting / stream，而是直接把 `newsStore.items` 映射成统一的渲染数组。详情 hydration 继续存在，但只作为补充 topic / mentions / summary 的来源，不再参与排序。

### 2. 统一横向卡片

首页每条新闻都使用同一套横向终端卡：

- 顶部一行：情绪、市场、来源。
- 中间主体：左侧标题和摘要，右侧时间与主题。
- 整卡高度受控，摘要限制在 2 行，避免出现海报式长卡。

这套卡同时替代当前的 `supporting` 和 `stream` 视觉差异，确保中间三张卡也和其他卡一样横向紧凑。

### 3. 信息结构

- 页面头部保留 `Signal Desk` 作为页面名，不再出现 `Primary Signal` / `Signal Queue`。
- 内容区改成单个 `SectionCard`，例如 `News Stream` 或等价统一列表标题。
- 列表桌面端为 1 列堆叠，每张卡内部横向布局；较窄宽度下卡内信息区允许换行或折叠成单列。

## 组件边界

- `frontend/src/views/NewsFeedView.vue`
  - 移除 editorial 分组使用，改渲染统一列表。
- `frontend/src/components/news/NewsCard.vue`
  - 统一首页卡片样式为横向终端卡。
- `frontend/src/views/NewsFeedView.test.ts`
  - 验证首页不再渲染 `Primary Signal`，且保留原始顺序。

## 测试与验证

- 先写测试验证：
  - 页面不再出现 `Primary Signal`
  - 新闻按输入顺序渲染
  - 首页列表存在统一卡片容器
- 跑针对性 Vitest。
- 跑 `npm --prefix frontend run build`。

## 风险

- 取消 editorial 分组后，首页失去“主编辑推荐”层次，这是本轮明确需求。
- 统一卡片后，如果摘要过长，需要靠 clamp 保证高度稳定。
