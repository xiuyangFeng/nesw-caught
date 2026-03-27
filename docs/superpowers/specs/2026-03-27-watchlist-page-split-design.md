# Watchlist Page Split Design

## 背景

当前 `watchlist` 已经有两套路由：

- `/watchlist`
- `/watchlist/:symbol`

但两者实际上都渲染 `WatchlistView.vue`，仍然维持“左侧自选股 + 右侧详情”的 master-detail 单页结构。上一轮改造已经把右侧详情区重做成更像交易台的 K 线面板，但用户现在希望继续收紧 Watchlist 的信息架构：

1. 自选股列表和搜索/添加入口单独成页。
2. 页面中的股票项更小、更紧凑，不要再像大卡片。
3. “搜索”“添加”等入口字样也要缩小，弱化大按钮感。
4. 点击股票后跳转到专门的 K 线详情页。
5. K 线下方只放相关新闻/事件，不再继续堆叠其他摘要卡。
6. 设置不要把页面越撑越长，而要放在固定容器内滚动。

本轮目标不是新增后端能力，而是把 Watchlist 从“一个页面里拼所有东西”改成“清晰的列表页 + 详情页”。

## 目标

1. 把 `/watchlist` 改成纯入口页，只负责浏览、搜索、添加和删除自选股。
2. 把 `/watchlist/:symbol` 改成纯详情页，只负责顶部行情、K 线主图、下方相关新闻和设置弹层。
3. 把自选股列表收紧为超紧凑 `A1` 密度，明显缩小每一项高度。
4. 把设置入口改成顶部行情条右上角的螺丝按钮，并采用弹层承载设置项。
5. 设置项内容限制在弹层内部滚动，不让主页面无限下滑。
6. 继续沿用现有 store / API / K 线 / 新闻数据流，不引入新的后端字段和路由。

## 非目标

1. 不新增后端接口或调整现有 watchlist API 契约。
2. 不实现新的专业交易工具，如画线、盘口、深度等。
3. 不做全站 UI 风格重构，仅聚焦 Watchlist 页面分工和局部交互。
4. 不重新设计 K 线绘图库能力，继续基于现有 `lightweight-charts` 封装。

## 推荐方案

采用“Watchlist 分页拆分 + 详情页轻设置”的方案。

### 1. `/watchlist` 变成独立列表页

页面职责：

- 渲染自选股超紧凑列表
- 提供轻量搜索
- 提供轻量添加入口
- 支持删除
- 点击某一项后路由跳转到 `/watchlist/:symbol`

具体布局：

- 页面顶部只保留简洁标题和状态信息，不再强调“大 Dashboard”
- 搜索框与添加按钮放在同一工具条里，字号与按钮尺寸明显缩小
- 列表项采用紧凑单行/双列布局，优先显示：
  - 股票名
  - 代码
  - 市场
  - 最新价
  - 涨跌幅
- 每项高度压缩到接近终端列表，而不是独立大卡片

### 2. `/watchlist/:symbol` 变成独立详情页

页面职责：

- 顶部行情条
- K 线主图
- K 线下方相关新闻 / 事件流
- 顶部右上角设置按钮与设置 popover

具体布局：

- 顶部行情条展示股票名、代码、价格、涨跌、开高低收、成交量、更新时间
- 右上角提供螺丝按钮，点击后打开设置 popover
- K 线作为页面最大视觉区域
- K 线下方只放相关新闻 / 事件时间流，不再追加第二块摘要面板

### 3. 设置改为 popover，而不是常驻侧栏

用户明确要求取消右侧工具带，因此设置采用 popover：

- 触发方式：顶部行情条右上角螺丝按钮
- 内容：周期切换和必要的轻量设置入口
- 容器形态：锚定在顶部行情条右上角按钮附近的轻量 popover，而不是抽屉、侧栏或整页下沉区
- 滚动：popover 内部 `max-height + overflow-y-auto`
- 关闭方式：点击关闭按钮、popover 外部区域或完成操作后保留当前状态

这样能同时满足：

- 主图横向空间最大化
- 设置项不把主页面撑长
- 设置工具仍然就近可达

## 组件边界

### `frontend/src/views/WatchlistView.vue`

改成纯列表页容器：

- 不再直接渲染 `StockDetailPanel`
- 保留自选股候选搜索、添加、删除与刷新动作
- 列表项点击后只做路由跳转
- 页面结构更接近“Watchlist List”

### `frontend/src/views/WatchlistDetailView.vue`

改成纯详情页容器：

- 加载单股 quote / related news
- 复用或承接现有 `watchlistStore.selectSymbol()` 产生的 K 线数据
- 负责 symbol 路由切换、无效 symbol 回退和页面级骨架
- 负责返回 `/watchlist` 的页面级导航
- 只负责装载数据并向详情组件传递状态，不负责详情内部设置项编排

### `frontend/src/components/watchlist/WatchlistSidebar.vue`

重定位为列表页主内容区，而不是“左侧边栏”：

- 样式改为超紧凑 `A1` 密度
- 工具条中的搜索和添加按钮变小
- 股票行项高度压缩

如有必要，可进一步拆分出更聚焦的 `WatchlistListPanel` / `WatchlistToolbar` / `WatchlistRow`，但只在当前文件过于混杂时才拆。

### `frontend/src/components/watchlist/WatchlistAddModal.vue`

保留其核心功能，但视觉上收紧：

- 标题字样缩小
- 搜索输入区更轻
- 结果列表项更紧凑
- 避免整个 modal 再走“大卡片”风格

### `frontend/src/components/watchlist/StockDetailPanel.vue`

继续作为 K 线详情页主控组件，但需要从“交易台三段式里还带副图区和信号卡”改成更聚焦的版本：

- 顶部行情条
- 主图
- 下方新闻时间流
- 顶部设置按钮 + popover

不再在 K 线下方放 `signal summary` 卡片，也不再保留常驻设置区。
`StockDetailPanel.vue` 只负责详情内容编排、设置 popover 开关和图表/新闻联动，不承接路由跳转、无效 symbol 判断或页面级回退逻辑。

### `frontend/src/components/watchlist/RelatedNewsSidebar.vue`

继续承担相关新闻时间流，但布局要适配“位于 K 线下方”的场景：

- 宽度改为主列全宽而不是侧栏宽度
- 保留事件高亮联动
- 视觉密度控制在次级层级

## 数据流与状态

不新增后端字段，尽量沿用现有 store：

1. `/watchlist`：
   - `loadCandidates()`
   - `loadWatchlist()`
   - `quotes`
   - `sparklines`

2. `/watchlist/:symbol`：
   - `selectSymbol(symbol)` 负责加载 K 线
   - `loadQuoteDetail(symbol)` 负责顶部行情条
   - `loadRelatedNews(symbol)` 负责下方新闻

3. 设置弹层状态：
   - 新增前端局部状态，例如 `settingsOpen`
   - 周期切换尽量复用现有内部状态

## 交互设计

1. 列表页点击整行股票，立即跳转详情页，由详情页自己加载 K 线与新闻，而不是在列表页预拉详情数据。
2. 列表页搜索只过滤已添加股票；添加入口仍可搜索候选股票。
3. 若 `/watchlist/:symbol` 中的 `symbol` 缺失或返回 404，详情页立即回退到 `/watchlist`。
4. 详情页右上角螺丝按钮打开设置 popover。
5. 设置 popover 内部使用固定高度滚动。
6. 周期切换放进设置 popover，不再常驻占据版面。
7. 相关新闻位于 K 线下方，点击新闻仍可高亮相关事件日期。
8. 详情页返回按钮固定回到 `/watchlist`。

## 响应式策略

桌面端：

- 列表页保持高密度滚动浏览
- 详情页保持大主图 + 下方新闻

窄屏端：

- 列表页继续单列，但维持紧凑行高
- 详情页顶部行情条允许折行
- 设置弹层改为更宽或更高的移动端弹层，但仍必须内部滚动

## 测试策略

遵循 TDD：

1. 先写 `WatchlistView.test.ts` 的失败测试，锁定“列表页不再渲染详情区”以及新的紧凑入口结构。
2. 再写 `WatchlistDetailView.test.ts` 或扩充现有详情测试，锁定“详情页主图 + 下方新闻 + 右上角设置按钮/设置 popover”。
3. 对 `StockDetailPanel.vue` / `WatchlistSidebar.vue` / `WatchlistAddModal.vue` 需要的关键结构补单测。
4. 最终至少执行：
   - `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts`
   - `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts src/stores/watchlistStore.test.ts`
   - `npm --prefix frontend run build`

## 风险与缓解

1. 当前 `watchlist` store 同时服务列表页和详情页，拆页后更容易出现重复加载。
   - 缓解：优先复用已有 action，避免引入第二套状态。

2. 详情页容器与详情组件的职责若不切清，容易重新出现重复路由/状态控制。
   - 缓解：由 `WatchlistDetailView.vue` 负责页面级装载与回退，由 `StockDetailPanel.vue` 负责内容编排与 popover 交互。

3. 设置从常驻按钮改到弹层后，可能导致测试选择器失效。
   - 缓解：新增稳定 `data-role`，锁定弹层打开/关闭和内部滚动容器。

4. 列表压缩过头可能损失可读性。
   - 缓解：优先压缩垂直留白和按钮尺寸，不牺牲价格、代码与涨跌的可读性。
