# Watchlist Page Split Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Watchlist 拆成独立列表页和独立 K 线详情页，收紧列表密度，并把详情页设置迁移到顶部螺丝按钮弹层中。

**Architecture:** 维持现有 Vue Router + Pinia `watchlistStore` 数据流，不改后端接口。通过路由指向修正和视图职责拆分，把 `/watchlist` 收口成纯列表页，把 `/watchlist/:symbol` 收口成纯详情页；细节组件通过 TDD 逐步重构为紧凑列表、主图下方新闻、顶部设置弹层。

**Tech Stack:** Vue 3, Vue Router, Pinia, TypeScript, Tailwind utility classes, Vitest, lightweight-charts

---

## Chunk 1: 路由与页面职责拆分

### Task 1: 先锁定列表页和详情页的职责边界

**Files:**
- Modify: `frontend/src/views/WatchlistView.test.ts`
- Create: `frontend/src/views/WatchlistDetailView.test.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/views/WatchlistDetailView.vue`
- Test: `frontend/src/views/WatchlistView.test.ts`
- Test: `frontend/src/views/WatchlistDetailView.test.ts`

- [ ] **Step 1: 写失败测试，锁定路由拆分后的页面职责**

在 `frontend/src/views/WatchlistView.test.ts` 中新增断言：
- 列表页不再渲染 `data-role="stock-detail-panel"`
- 列表页保留自选股列表与工具条
- 点击股票项后仍跳转 `{ name: 'watchlist-detail', params: { symbol } }`

创建 `frontend/src/views/WatchlistDetailView.test.ts`，至少覆盖：
- 详情页加载时调用 `loadQuoteDetail(symbol)` 和 `loadRelatedNews(symbol)`
- 详情页加载时调用 `selectSymbol(symbol)` 以装载 K 线
- 详情页存在返回按钮
- 详情页存在 `data-role="watchlist-detail-main"`
- 无效 symbol 时回退到 `/watchlist`

- [ ] **Step 2: 运行测试并确认按新职责失败**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts`
Expected: FAIL，提示列表页仍渲染旧详情结构或详情页结构缺失

- [ ] **Step 3: 写最小实现完成路由与视图拆分**

要求：
- `router/index.ts` 中 `/watchlist/:symbol` 改为 `WatchlistDetailView.vue`
- `WatchlistView.vue` 只保留列表页职责
- `WatchlistDetailView.vue` 收口为详情页容器并保留数据加载逻辑、无效 symbol 回退与返回导航

- [ ] **Step 4: 重新运行测试确认通过**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts`
Expected: PASS

## Chunk 2: 列表页紧凑化与添加入口收紧

### Task 2: 先锁定超紧凑列表和轻量工具条

**Files:**
- Modify: `frontend/src/views/WatchlistView.test.ts`
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/components/watchlist/WatchlistSidebar.vue`
- Modify: `frontend/src/components/watchlist/WatchlistAddModal.vue`
- Test: `frontend/src/views/WatchlistView.test.ts`

- [ ] **Step 1: 写失败测试，锁定列表页紧凑入口结构**

在 `frontend/src/views/WatchlistView.test.ts` 中新增断言：
- 列表页存在更聚焦的工具条，例如 `data-role="watchlist-toolbar"`
- 工具条存在搜索输入和添加按钮
- 列表区存在紧凑行项容器，例如 `data-role="watchlist-compact-list"`
- 列表页不再出现大而显眼的 “Trading Dashboard” 标题
- 列表页不再出现旧的详情区容器和厚重的 dashboard 式标题层级

- [ ] **Step 2: 运行测试并确认失败**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts`
Expected: FAIL，提示新工具条或紧凑列表结构不存在

- [ ] **Step 3: 写最小实现完成列表页紧凑化**

要求：
- `WatchlistView.vue` 头部和状态区同步收紧，形成真正独立的列表页
- `WatchlistSidebar.vue` 改成超紧凑 `A1` 密度
- 搜索框和添加按钮尺寸缩小
- 股票行项高度明显低于当前卡片
- `WatchlistAddModal.vue` 同步缩小标题和输入区视觉重量

- [ ] **Step 4: 重新运行测试确认通过**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts`
Expected: PASS

## Chunk 3: 详情页主图下方新闻与设置弹层

### Task 3: 先锁定详情页的新结构和设置交互

**Files:**
- Modify: `frontend/src/views/WatchlistDetailView.test.ts`
- Modify: `frontend/src/views/WatchlistDetailView.vue`
- Modify: `frontend/src/components/watchlist/StockDetailPanel.vue`
- Modify: `frontend/src/components/watchlist/RelatedNewsSidebar.vue`
- Test: `frontend/src/views/WatchlistDetailView.test.ts`

- [ ] **Step 1: 写失败测试，锁定详情页结构**

在 `frontend/src/views/WatchlistDetailView.test.ts` 中新增断言：
- 顶部行情条存在设置按钮，例如 `data-role="watchlist-settings-trigger"`
- K 线主图区存在
- K 线下方新闻区存在，例如 `data-role="watchlist-detail-news"`
- 页面中不再出现常驻右侧工具带
- 点击设置按钮后出现 popover，例如 `data-role="watchlist-settings-popover"`
- `WatchlistDetailView.vue` 负责把 quote / kline / news 状态传给详情组件

- [ ] **Step 2: 运行测试并确认失败**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistDetailView.test.ts`
Expected: FAIL，提示设置弹层或新闻下沉结构缺失

- [ ] **Step 3: 写最小实现完成详情页改造**

要求：
- `WatchlistDetailView.vue` 组装 dedicated detail page，而不是继续沿用列表页骨架
- `StockDetailPanel.vue` 改成顶部行情条 + 主图 + 下方新闻
- 顶部右上角新增螺丝设置按钮
- 设置内容进入 popover，并提供内部滚动容器
- `RelatedNewsSidebar.vue` 适配详情页下方全宽场景
- 不再渲染旧的副图区常驻工具布局

- [ ] **Step 4: 重新运行测试确认通过**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistDetailView.test.ts`
Expected: PASS

## Chunk 4: 设置内容和图表联动细化

### Task 4: 锁定弹层内容和图表联动不回退

**Files:**
- Modify: `frontend/src/views/WatchlistDetailView.test.ts`
- Modify: `frontend/src/components/watchlist/StockDetailPanel.vue`
- Modify: `frontend/src/components/watchlist/IndicatorChart.vue`
- Modify: `frontend/src/components/watchlist/KlineChart.vue`
- Test: `frontend/src/views/WatchlistDetailView.test.ts`

- [ ] **Step 1: 写失败测试，锁定设置弹层内容和联动存活**

至少覆盖：
- 设置 popover 内可见周期切换入口
- 设置 popover 内可见指标相关入口
- 设置滚动容器存在 `overflow` 对应类或 `data-role`
- 点击新闻项后图表高亮联动仍可用

- [ ] **Step 2: 运行测试并确认失败**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistDetailView.test.ts`
Expected: FAIL，提示 popover 内容或联动结构缺失

- [ ] **Step 3: 写最小实现保持功能完整**

要求：
- 周期切换从 `StockDetailPanel.vue` 现有顶部区迁移到设置 popover 中
- 指标相关控制由 `IndicatorChart.vue` 与 `StockDetailPanel.vue` 配合迁移到设置 popover 中
- 继续保留新闻事件与图表高亮联动
- K 线主图仍保持视觉中心

- [ ] **Step 4: 重新运行测试确认通过**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistDetailView.test.ts`
Expected: PASS

## Chunk 5: 集成验证、记录、评审和集成

### Task 5: 完成验证与交付

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: 运行本轮相关测试**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts src/components/watchlist/KlineChart.test.ts src/stores/watchlistStore.test.ts`
Expected: PASS

- [ ] **Step 2: 运行构建验证**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 3: 更新变更记录**

在 `docs/code-change-log.md` 顶部追加记录，明确写出：
- Watchlist 列表页/详情页拆分
- 超紧凑列表和轻量添加入口
- 顶部螺丝按钮设置弹层
- K 线下方相关新闻区
- 验证命令

- [ ] **Step 4: 进行 code review 并修复问题**

要求：
- 审核页面职责是否清晰
- 审核设置弹层是否真的内部滚动
- 审核列表密度是否实现，而不是只改文案
- 审核路由指向和测试覆盖

- [ ] **Step 5: 合并与推送**

要求：
- 先把工作分支合并回本地 `main`（按用户明确要求执行）
- 在 `main` 上重跑最小验证
- 再推送到远程 `origin/main`
