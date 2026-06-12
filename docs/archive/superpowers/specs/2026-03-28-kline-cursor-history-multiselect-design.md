# K 线统一游标、撤销重做与多选工具条设计

## 背景

当前 watchlist K 线模块已经具备：

- 专业终端化布局、图内 HUD、基础 chart projector
- `trend_line` / `horizontal_line` / `price_range` / `fibonacci_retracement` / `price_note` 的基础编辑
- overlay 与底层 chart 的空白区手势让渡

但离“长期可用的分析工作台”仍有三块明显缺口：

- crosshair / HUD / 副图 / 事件提示还没有统一到一套 cursor 状态
- 所有对象编辑都是直接写状态，没有 `undo / redo`
- 仍是单对象选择，缺少多选和更像工作台的对象工具条

## 目标

本轮目标：

- 建立统一的 chart cursor 状态，驱动主图 HUD、crosshair 标签和副图读数
- 在 `watchlistChartStore` 中增加按 symbol 的撤销 / 重做
- 支持 `Shift+Click` 多选对象
- 将现有单对象浮层升级成对象工具条，覆盖单选与多选两种状态

非目标：

- 不做框选（marquee selection）
- 不做跨 symbol 历史恢复
- 不做右键菜单树或复杂层级面板
- 不接服务端持久化历史栈

## 方案比较

### 方案 A：继续在组件层用局部状态拼接

优点：

- 表面改动少

缺点：

- cursor、selection、history 会分散在 chart / overlay / popover 多处
- undo/redo 很难可信
- 测试边界不清晰

结论：不采用。

### 方案 B：store 提升为工作台状态核心，组件只消费契约

做法：

- `KlineChart.vue` 维护统一 cursor 输入源并下发给 HUD / overlay / subindicator 面板
- `watchlistChartStore` 新增 `selectedDrawingIds`、history 栈和 group actions
- `KlineDrawingOverlay` 只负责命中与交互事件，`Shift+Click` 发出加选语义
- `KlineDrawingSelectionPopover` 升级成对象工具条，根据 selection 数量切换动作集

优点：

- 历史和选择语义单一来源
- 测试可以先锁 store，再锁组件
- 后续加复制、隐藏、批量锁定都可复用

缺点：

- 需要修改 store 契约并同步现有 chart / overlay / popover

结论：采用。

## 设计总览

### 1. 统一 cursor 状态

新增一个轻量 `KlineCursorState`，包含：

- `time`
- `price`
- `source`：`chart` | `overlay`
- `candle`
- `subIndicatorValues`

规则：

- 优先消费 chart projector / chart crosshair 事件提供的坐标语义
- overlay 在绘图或编辑中仍可更新 cursor，作为 fallback
- HUD、crosshair 标签、副图读数、事件 hover 都从同一 cursor state 派生
- `mouseleave` 或 symbol 切换时回退到 latest candle

### 2. 撤销 / 重做

在 `watchlistChartStore` 中按 symbol 新增：

- `historyPastBySymbol`
- `historyFutureBySymbol`

记录粒度：

- 只记录 drawings 集合的稳定快照
- 下列动作进入 history：
  - 创建对象
  - 删除对象
  - anchor / body move
  - style update
  - label edit
  - lock / visible toggle
  - 批量动作

规则：

- `undo` 回到上一个 drawings 快照
- `redo` 重放 future 栈
- 每次新编辑都会清空 future 栈
- 非 drawings 状态（当前工具、hover、面板折叠）不进入 history

### 3. 多选

最小多选语义：

- 普通 click：单选对象
- `Shift+Click`：对命中对象做 add/remove toggle
- 点击空白：清空选择
- 删除、锁定、隐藏、复制支持对当前所有选中对象生效

保持兼容：

- 现有 `selectedDrawingId` 可保留为“主选中对象”兼容层
- 新增 `selectedDrawingIds`
- 单选时 `selectedDrawingId === selectedDrawingIds[0]`

### 4. 对象工具条

`KlineDrawingSelectionPopover` 升级为对象工具条：

- 无选择：不显示
- 单选：
  - 颜色
  - 线型
  - 线宽
  - 锁定 / 解锁
  - 隐藏 / 显示
  - 复制
  - 删除
- 多选：
  - 显示“已选 N 个对象”
  - 批量锁定 / 解锁
  - 批量隐藏 / 显示
  - 批量复制
  - 批量删除

本轮不做对象排列、吸附开关和分组命名。

### 5. Toolbar 与快捷动作

`KlineToolbar` 新增：

- `undo`
- `redo`

按钮在 history 不可用时 disabled。

键盘快捷键最小支持：

- `Meta/Ctrl + Z` => undo
- `Meta/Ctrl + Shift + Z` 或 `Meta/Ctrl + Y` => redo

## 组件影响

### `frontend/src/stores/watchlistChartStore.ts`

- 新增 selection 集合与 history 栈
- 提供 group actions 与 undo/redo actions

### `frontend/src/components/watchlist/KlineChart.vue`

- 统一 cursor 状态
- 连接 toolbar undo/redo
- 连接 overlay 多选事件
- 连接对象工具条 group actions

### `frontend/src/components/watchlist/KlineDrawingOverlay.vue`

- 发出带 `append` 语义的 selection 事件
- 多选时渲染多个对象高亮与 anchor（只给主对象渲染 anchors）

### `frontend/src/components/watchlist/KlineDrawingSelectionPopover.vue`

- 支持 selection 数量和 group actions

### `frontend/src/components/watchlist/KlineToolbar.vue`

- 增加 undo/redo controls

## 测试策略

先写失败测试：

- `watchlistChartStore.test.ts`
  - history push / undo / redo
  - shift 多选 toggle
  - group delete / duplicate / lock / visible
- `KlineToolbar.test.ts`
  - undo / redo 按钮状态与事件
- `KlineDrawingSelectionPopover.test.ts`
  - 单选样式动作
  - 多选 group actions
- `KlineDrawingOverlay.test.ts`
  - `Shift+Click` additive select
  - 空白点击清空
- `KlineChart.test.ts`
  - toolbar undo/redo 真正驱动 store
  - 多选工具条动作写回 drawings
  - cursor state 仍驱动 HUD 回退

最小验证包含相关 Vitest 文件和 `npm --prefix frontend run build`。

## 风险与后续

主要风险：

- history 若直接存引用，容易因后续 mutation 失效，因此必须做深拷贝快照
- 多选后 anchor 渲染和主选中对象定义要保持稳定，否则编辑体验会混乱

后续可继续推进：

- 框选
- 右键上下文菜单
- 图层列表
- 更完整的 cursor 驱动新闻/副图同步
