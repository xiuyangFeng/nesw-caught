# K 线 Fib / 价格标注编辑与轴联动十字光标设计

## 背景

当前 watchlist K 线工作台已经具备：

- 专业终端化重排、图内 HUD 与侧栏工作台
- overlay 合成 crosshair
- `trend_line` / `horizontal_line` / `price_range` 的锚点拖拽与对象整体移动
- overlay stale drag 清理和 `ResizeObserver` 尺寸刷新

但仍有两个直接影响可用性的缺口：

- `fibonacci_retracement` 和 `price_note` 仍只能创建和显示，不能完成后续编辑
- crosshair 的价格 / 时间标签仍完全依赖 overlay 自行按 high-low 比例换算，不够接近图表库原生价格轴与时间轴

用户已经明确本轮直接继续开发，不再要求中途停下来确认，因此本设计以现有约束直接收敛为可交付切片。

## 目标

本轮目标：

- 让 `fibonacci_retracement` 支持锚点拖拽和对象整体移动
- 让 `price_note` 支持对象整体移动、标签文本编辑入口与空文本回退
- 让 overlay crosshair 的价格标签改用主图 price scale 坐标映射
- 让 overlay crosshair 的时间标签尽量跟随主图当前可视时间范围和 candle 槽位
- 保持现有本地持久化结构兼容，不改后端接口

非目标：

- 不实现 fib level 自定义集合
- 不实现 price note 富文本、多行文本或箭头标注
- 不把 crosshair 完全替换为 `lightweight-charts` 原生渲染
- 不引入撤销 / 重做

## 方案比较

### 方案 A：继续只靠 overlay 近似映射补更多 if/else

优点：

- 改动表面最小

缺点：

- price label 精度仍依赖本地 high-low 压缩
- 时间标签仍不了解 chart 当前可视范围，缩放后保真度差
- 后续继续往原生轴靠拢时会重复返工

结论：不采用。

### 方案 B：overlay 继续持有交互，但接入 chart 坐标投影能力

做法：

- pointer 事件仍由 `KlineDrawingOverlay` 统一接管
- `KlineChart` 把主图的 `timeScale` / `priceToCoordinate` / `coordinateToPrice` 能力通过轻量投影器传给 overlay
- geometry 模块继续负责 drawing hit test 和 anchors 变换，但 crosshair 投影优先消费 chart 提供的坐标结果
- 在 overlay 内补齐 fib / price note 的编辑入口和提交事件

优点：

- 保持现有 overlay 架构和测试方式
- crosshair 标签更贴近原生轴
- 后续若继续加更多工具，仍可复用统一交互层

缺点：

- 需要在 chart 和 overlay 之间新增一层投影契约
- 测试 mock 稍复杂

结论：采用。

## 设计总览

### 1. Crosshair 轴联动契约

`KlineChart` 新增一个传给 overlay 的 `chartViewport` / `chartProjector` 契约，至少暴露：

- `getXForTime(time)`：优先使用 `timeScale().timeToCoordinate`
- `getTimeForX(x)`：优先使用 `timeScale().coordinateToTime`，若不可得则退回最近 candle
- `getYForPrice(price)`：优先使用 candle series `priceToCoordinate`
- `getPriceForY(y)`：优先使用 candle series `coordinateToPrice`
- `plotWidth` / `plotHeight`

overlay 的 crosshair 规则改为：

- 横线 y 坐标优先取 `getYForPrice`
- 纵线 x 坐标优先取 `getXForTime`
- price label 优先显示 `getPriceForY` 对应的值，fallback 才用原 anchor.price
- time label 优先显示 `getTimeForX` 吸附后的时间，fallback 才用最近 candle time

这样价格 / 时间标签会更贴近图表当前缩放和 price scale，而不是只看整包 candles 的静态最大最小值。

### 2. Fib 编辑规则

`fibonacci_retracement` 从只读升级为可编辑对象：

- 被选中后显示两个端点锚点
- 拖拽锚点时更新对应 anchor
- 拖拽对象本体时整体平移两个端点
- 现有默认 levels 仍固定为 `0 / 0.236 / 0.382 / 0.5 / 0.618 / 0.786 / 1`
- level 文本继续只读显示，不可单独拖拽

拖拽语义与趋势线一致：

- anchor drag：目标点替换为最近 candle 时间 + 当前 hover price
- body drag：按起点与当前点的 `timeDelta + priceDelta` 平移全部 anchors

### 3. Price Note 编辑规则

`price_note` 从“只能显示”升级为“可移动 + 可改文案”的轻编辑对象：

- 选中后显示唯一 anchor handle
- 拖拽 anchor 或对象本体都等价为移动该 price note 到新的时间 / 价格
- 保持短水平标记线 + 右侧文本标签的渲染
- 双击文本标签或选中后按 `Enter` 进入 `editing-label`
- 编辑通过一个定位在 overlay 上方的轻量 input 完成
- `Enter` 提交，`Escape` 取消
- 提交空文本时回退为当前 anchor price 的默认价格文本
- 文本仍限制 24 个字符

### 4. Overlay 事件扩展

在现有事件基础上补：

- `drawing-label-edit-request`：请求父层开始某个 `price_note` 的 label 编辑
- `drawing-label-commit`：提交 `(drawingId, text)`

实际落地可以直接由 `KlineChart` 调用已有 store `commitLabelEdit`，不新增 store 结构。

### 5. Store 与持久化

`watchlistChartStore` 只做最小扩展：

- 复用现有 `commitLabelEdit`
- 若 price note 的 anchor 被移动，提交后 payload 为空时仍自动回退为新的价格文本
- 不新增持久化版本；保持向后兼容

## 组件影响

### `frontend/src/components/watchlist/KlineChart.vue`

- 构造 chart 投影器并传给 overlay
- 接收 `drawing-label-commit`
- 在 symbol / candles 切换时清理 hover 与 label edit 状态

### `frontend/src/components/watchlist/KlineDrawingOverlay.vue`

- 使用 chart 投影器替代纯静态 high-low 投影
- 把 fib 加入 editable drawing 范围
- 为 price note 增加 anchor / body 拖拽与 label 编辑输入层
- 保持已存在的 stale drag 清理逻辑

### `frontend/src/utils/klineOverlayGeometry.ts`

- 增加更通用的 crosshair projection 输入
- 支持 fib / price note 的 move 逻辑
- 提供 price note 默认文本回退辅助

## 测试策略

先写失败测试，再实现：

- `KlineDrawingOverlay.test.ts`
  - fib anchor / body drag commit
  - price note 拖拽与 label 编辑提交流程
  - crosshair label 使用 chart projector 投影结果而不是静态 high-low
- `KlineChart.test.ts`
  - overlay 新的 label commit 事件能写回 store
  - chart props 变更会清空 hover / 编辑态
- `klineOverlayGeometry.test.ts`
  - fib / price note move 逻辑
  - crosshair projection 的 projector 优先路径与 fallback 路径

最小验证仍包括相关 Vitest 文件和 `npm --prefix frontend run build`。

## 风险与后续

主要风险：

- `lightweight-charts` 某些坐标 API 在测试 stub 下需要显式 mock，否则容易退回 fallback 分支
- overlay 内加入 label input 后，需要避免它与 chart pointer 事件互相抢焦点

后续可继续推进：

- 用 chart 真正的 visible range / crosshair move 事件进一步对齐时间标签
- price note 更完整的浮层样式编辑
- fib level 标签的右轴价格联动显示
