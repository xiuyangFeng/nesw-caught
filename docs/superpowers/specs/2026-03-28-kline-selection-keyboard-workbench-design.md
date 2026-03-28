# K 线对象工作台键盘增强设计

## 背景

当前 watchlist K 线工作台已经具备：

- drawing store 级 `undo / redo`
- `Shift+Click` 多选与对象工具条
- `Ctrl/Meta + Z`、`Ctrl/Meta + Shift + Z`、`Ctrl/Meta + Y`
- `price_note` 轻量文本编辑

但对象编辑仍明显偏鼠标驱动，日常分析时有三处效率缺口：

- 选中对象后不能直接用 `Delete / Backspace` 删除
- 不能用 `Escape` 快速退出当前选择或取消草稿
- 多选对象后不能用方向键做细粒度批量位移

这轮要在不破坏现有 overlay 交互和 history 契约的前提下，把这些键盘工作台能力补齐。

## 目标

本轮目标：

- `Delete` / `Backspace` 删除当前全部选中对象
- `Escape` 优先取消 draft，其次清空当前选择
- 方向键对当前全部选中对象做批量微调移动
- `Shift + 方向键` 提供更大步长的快速微调
- 所有键盘位移都进入现有 `undo / redo` history
- 避免与 `price_note` 文本编辑和原生输入焦点冲突

非目标：

- 不做框选
- 不做对象缩放、旋转、吸附
- 不做更复杂的键盘连续加速曲线
- 不新增后端接口或持久化版本

## 方案比较

### 方案 A：把删除 / 清空 / 位移都直接堆在 `KlineChart.vue`

优点：

- 改动面表面最小

缺点：

- `undo / redo`、选择、批量位移语义继续散落在 chart 组件
- 后续再加框选或批量样式时，`KlineChart.vue` 会继续膨胀
- store 级测试无法先锁定核心行为

结论：不采用。

### 方案 B：键盘监听留在 chart，工作台语义下沉到 store

做法：

- `KlineChart.vue` 负责监听全局键盘事件和判断当前是否应响应
- `watchlistChartStore.ts` 新增批量删除与批量位移 action
- `KlineDrawingOverlay.vue` 保持 pointer / hit-test 单一职责，不承载键盘状态

优点：

- 选择和 history 的写路径继续单一收束到 store
- 先测 store，再测 chart 接线，边界清楚
- 与现有 undo/redo 架构一致

缺点：

- 需要补一个“按 symbol 批量位移 selected drawings”的新 action

结论：采用。

## 设计总览

### 1. 键盘行为优先级

在图表详情页存在可用 symbol 时，键盘规则如下：

- `Escape`
  - 若当前存在 drawing draft，调用 `cancelDraft()`
  - 否则若存在选中对象，调用 `clearSelection()`
- `Delete` / `Backspace`
  - 若存在选中对象，调用 `deleteSelectedDrawings(symbol)`
- `ArrowUp` / `ArrowDown` / `ArrowLeft` / `ArrowRight`
  - 若存在选中对象，调用新的批量位移 action
  - 默认步长为一个最小单位
  - `Shift` 修饰时使用更大步长

这些快捷键继续与现有 undo/redo 并存，不改变已有 `Ctrl/Meta + Z` 等路径。

### 2. 键盘守卫

以下场景必须直接跳过快捷键处理：

- `price_note` 正在编辑文本
- 当前焦点落在 `input`、`textarea`、`select` 或 `contenteditable`
- 当前无 `klineData.symbol`
- 当前无已选中对象，且本次按键不是 `Escape` + draft cancel

额外约束：

- 只拦截真正会被工作台消费的键，避免误伤浏览器默认行为
- 一旦消费删除或位移动作，应 `preventDefault()`，避免页面滚动或浏览器返回
- overlay 需要把 label 编辑开关显式同步给 chart，例如新增 `labelEditingChange(boolean)` 事件；chart 不能只依赖输入框焦点是否还在
- 当没有选中对象且没有 draft 时，`Backspace` / `Delete` 不应被工作台拦截，避免全局空操作误伤浏览器默认行为

#### `price_note` 编辑态的事件生命周期

`labelEditingChange(boolean)` 作为 chart 侧快捷键守卫的唯一编辑态来源，规则固定为：

- 打开编辑器时 emit `true`
- `Enter` 提交成功时 emit `false`
- `Escape` 关闭编辑器时 emit `false`
- 失焦关闭编辑器时 emit `false`

并明确 `Escape` 优先级：

- 当 `price_note` 编辑器打开时，第一次 `Escape` 只关闭编辑器
- 编辑器关闭后，后续新的 `Escape` 才重新回到“先 cancel draft，再 clear selection”的 chart 级规则

### 3. Store 批量位移契约

`watchlistChartStore.ts` 新增一个窄接口，例如：

- `nudgeSelectedDrawings(symbol, options)`

建议参数：

- `candles`: `KlineCandle[]`
- `timeStep`: `-1 | 0 | 1 | ...`
- `priceDelta`: number

语义：

- 对 `selectedDrawingIds` 命中的所有对象统一做位移
- store 不自行缓存 candles，调用方在当前 symbol 上显式传入本次图表的 candles 快照
- 时间方向通过现有 `moveDrawingByDelta()` 的 candle index 映射推进
- 价格方向直接加减固定 delta
- 结果作为一次单独 history 记录写入，确保一次按键对应一次 undo

这样能复用当前 geometry move 语义，避免在 store 内重新实现不同工具类型的位移逻辑。

### 4. 微调步长

为了兼顾不同工具和当前 K 线尺度，采用“两轴分离”的固定步长：

- 左右方向键：时间轴按 candle 槽位移动
  - 默认 `1` 根 candle
  - `Shift` 时 `5` 根 candle
- 上下方向键：价格轴按当前 `klineData.candles` 全量范围的价格跨度比例移动
  - 默认使用 `(maxHigh - minLow) * 0.01`
  - `Shift` 时使用 `(maxHigh - minLow) * 0.03`
  - 若价格跨度不可得，则 fallback 到 `1`

原因：

- 时间轴用 candle 槽位移动更符合当前 drawing anchor 的离散时间模型
- 价格轴若用固定绝对值，在高价股和低价股上的手感会严重失衡
- 当前实现层还没有稳定暴露 visible-range candles，直接使用当前 `klineData.candles` 全量范围可以保持规则稳定且测试明确
- 1% / 3% 虽然是近似值，但与当前 overlay 的价格映射模型兼容，足够做细调

### 5. 特定工具的左右位移语义

并非所有 drawing 都同等消费 `timeDelta`，本轮明确如下：

- `trend_line` / `price_range` / `fibonacci_retracement` / `price_note`
  - 左右方向键正常沿 candle 槽位平移
- `horizontal_line`
  - 左右方向键视为 no-op
  - 上下方向键仍可调整价格

这样保持与当前 geometry 语义一致，不额外重写水平线的时间含义。

### 6. 图表集成层职责

`KlineChart.vue` 新增键盘集成层，职责保持克制：

- 注册 / 注销 `window` 级 `keydown`
- 判断是否应响应工作台快捷键
- 计算方向键对应的 `timeStep` / `priceDelta`
- 调用 store action
- 订阅 overlay 透出的 label-editing 状态

`KlineChart.vue` 不直接改 drawing anchors，只消费 store 暴露的工作台动作。

额外优先级约束：

- 只要当前存在 draft，除 `Escape` 外的删除和方向键快捷键一律失效
- 这样可以避免“正在创建新对象时误删或误移旧对象”

### 7. 历史与选择一致性

删除和微调都必须保留以下契约：

- 每次批量删除或单次方向键微调都对应一次 history push
- 删除后清空失效 selection
- 微调后保持当前 selection 不变
- undo / redo 后 selection 仍按现有 snapshot 恢复逻辑过滤无效 id

## 组件影响

### `frontend/src/stores/watchlistChartStore.ts`

- 新增 `nudgeSelectedDrawings(symbol, options)`
- 复用 `pushHistory()`、`cloneDrawings()`、现有 selection 管理

### `frontend/src/components/watchlist/KlineChart.vue`

- 增加键盘事件监听与守卫逻辑
- 连接 `Escape` / 删除 / 位移动作
- 保持现有 undo/redo 快捷键和 overlay 编辑契约不变

### `frontend/src/utils/klineOverlayGeometry.ts`

- 若当前 `moveDrawingByDelta()` 已满足所有工具，可不改
- 若批量位移需要更稳定的 helper，可只做最小辅助扩展，不改现有行为

## 测试策略

先写失败测试，再实现：

- `watchlistChartStore.test.ts`
  - `deleteSelectedDrawings()` 删除多选对象后清空选择
  - `nudgeSelectedDrawings()` 对多个对象统一位移
  - 每次 nudge 能被 `undo / redo` 正确回放
- `KlineChart.test.ts`
  - `Delete / Backspace` 删除当前多选并清空选择
  - `Escape` 优先取消 draft，否则清空选择
  - 方向键触发批量位移
  - `Shift + 方向键` 使用更大步长
  - 焦点在输入框或 `price_note` 编辑中时不触发
  - `horizontal_line` 的左右方向键为 no-op
- `KlineDrawingOverlay.test.ts`
  - `labelEditingChange(true/false)` 在打开、提交、取消、失焦时正确发出

最小验证仍包括相关 Vitest 文件和 `npm --prefix frontend run build`。

## 风险与后续

主要风险：

- 方向键绑定在 `window` 后，若守卫不严，会与浏览器默认滚动或输入框编辑冲突
- 价格步长使用当前 candles 范围比例，属于工作台级近似值，不是 tick 级精调

后续可继续推进：

- 框选 `marquee selection`
- 批量样式编辑
- 更精细的对象吸附与键盘加速
