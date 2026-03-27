# K 线十字光标与画线编辑增强设计

## 背景

当前 K 线工作台已经完成了专业终端化的第一轮重排，主图内已有 HUD 读数带、图内角标和更紧凑的工具/侧栏结构。

但用户在真正使用时，仍会遇到两个明显短板：

- 主图只有 hover HUD，没有真正的十字光标和图内读数标签，读盘仍偏“看摘要”而不是“贴图读数”
- 画线对象虽然可创建、可选中、可锁定/删除，但还不能直接拖动锚点或整体移动对象，编辑闭环不完整

在当前架构下，继续往“专业看盘软件”逼近的最高价值切片，就是把这两块补起来。

## 目标

在不引入新图表库、不重写 store 持久化结构的前提下，补齐主图十字读数和基础画线编辑体验。

本轮目标：

- 为主图增加合成十字光标，包括横纵参考线和价格/时间读数标签
- 让 HUD 与十字光标共享同一套 hover 数据，不再只是静态 hover HUD
- 为已选中的基础画线对象增加锚点拖拽和对象整体移动
- 锁定对象仍可选中，但不可拖动

非目标：

- 不实现完整 TradingView 级别的价格轴/时间轴原生联动
- 不实现撤销/重做
- 不在本轮支持所有工具的高保真编辑，优先覆盖趋势线、水平线、矩形区间

## 方案选择

### 方案 A：直接接 `lightweight-charts` 原生 crosshair 事件并重做读数层

优点：

- 理论上最接近原生图表交互

缺点：

- 当前工作台大量交互依赖 overlay，直接切原生 crosshair 会让 hover、选中、绘图、标签层割裂
- 测试和 mock 成本明显抬高

结论：本轮不采用。

### 方案 B：继续以 overlay 为交互主入口，构建合成十字光标与对象编辑

做法：

- overlay 继续负责 pointer 事件
- 在 overlay 内绘制十字光标参考线和价格/时间标签
- 扩展 geometry 工具，加入锚点命中、对象拖拽和 anchor 更新逻辑
- `KlineChart` 继续只消费 hover anchor 和 drawing edit 事件

优点：

- 与现有画线架构一致
- 可测试性高
- 能最快补齐“读数 + 编辑”闭环

缺点：

- 价格/时间标签仍是前端合成层，不是图表库原生轴标签

结论：采用。

## 设计总览

### 合成十字光标

当主图可用且鼠标在 overlay 内移动时：

- 显示一条竖向虚线，穿过最近 candle 的时间槽
- 显示一条横向虚线，穿过当前 hover price
- 在左下角显示时间标签
- 在右上或右侧边缘显示价格标签
- HUD 读数同步切到该 candle

当鼠标离开 overlay 时：

- 十字光标和标签消失
- HUD 回退到最新 candle

### 画线编辑规则

首轮支持编辑的对象：

- `trend_line`
- `horizontal_line`
- `price_range`

本轮不进入编辑态但必须继续正常显示/命中的对象：

- `fibonacci_retracement`
- `price_note`

这两类对象保持只读：

- 仍可被选中
- 仍保留现有浮层样式能力
- 不渲染可拖拽锚点
- 不响应 anchor/body drag

交互规则：

- 选中对象后显示锚点圆点
- 鼠标按下锚点进入 `dragging-anchor`
- 鼠标按下对象本体进入 `dragging-object`
- `mousemove` 实时预览拖拽
- `mouseup` 提交新的 anchors
- 被锁定对象可选中但不能进入拖拽

拖拽细则：

- 锚点拖拽时，时间吸附到最近 candle
- 整体移动时，趋势线/矩形保留相对时间跨度，水平线整体只改 price
- 拖拽只在选中对象上生效，不做多选

时间/价格增量映射固定如下：

- 锚点拖拽：直接把目标锚点替换为“最近 candle 时间 + 当前 hover price”
- 趋势线/矩形整体移动：以拖拽起点和当前 hover 点之间的 candle 索引差作为 `timeDelta`，以 price 差作为 `priceDelta`，两个 anchor 一起平移
- 水平线整体移动：忽略 `timeDelta`，只按 `priceDelta` 更新唯一 anchor 的 price
- 超出 candle 范围时，时间钳制到首尾 candle

### 事件契约

`KlineDrawingOverlay` 新增：

- `drawing-anchor-preview`
- `drawing-anchor-commit`
- `drawing-move-preview`
- `drawing-move-commit`

其中预览事件只用于父层本地 UI 响应；本轮可直接复用 commit 路径，优先保证最终提交。

为了控制范围，本轮实际最小落地要求是：

- overlay 至少发出 `drawing-anchor-commit`
- overlay 至少发出 `drawing-move-commit`
- `KlineChart` 接到后调用现有 store 的 `updateDrawingAnchors` 或 `moveDrawing`
- commit 事件负载固定为 `(drawingId: string, anchors: KlineDrawingAnchor[])`

## 模块影响

### `klineOverlayGeometry.ts`

新增纯函数：

- anchor 命中检测
- 计算最近 candle 索引
- 根据拖拽目标重算 anchors
- 生成十字光标投影点与标签值

### `KlineDrawingOverlay.vue`

负责：

- 绘制十字光标线和时间/价格标签
- 渲染选中对象锚点
- 管理拖拽状态
- 发出对象编辑提交事件

### `KlineChart.vue`

负责：

- 接 overlay 编辑事件并写入 store
- 用 hover/crosshair 数据驱动 HUD
- 保持切换 symbol/period 时清理 hover/drag 状态

## 测试策略

- 新建 `klineOverlayGeometry.test.ts`，覆盖锚点命中、对象移动、锚点更新和 crosshair 投影
- 扩展 `KlineDrawingOverlay.test.ts`，覆盖十字光标显示、锚点渲染、拖拽提交和锁定对象不可拖动
- 扩展 `KlineChart.test.ts`，只覆盖 mock overlay 发出的编辑事件确实写回图表状态；真实 crosshair DOM 覆盖放在 `KlineDrawingOverlay.test.ts`
- 最小回归验证继续包含 `StockDetailPanel.test.ts`、`WatchlistDetailView.test.ts` 和 `frontend build`

## 风险与后续

主要风险：

- 当前 overlay 仍基于本地近似投影，不是真实价格轴像素，因此 crosshair 标签精度依赖本地 high/low 映射
- 拖拽对象时若后续加入更多工具，geometry 分支会继续增长，需要再抽象

后续可继续推进：

- 真正对齐图表库 crosshair API
- 支持 fib / price note 的细粒度编辑
- 撤销/重做与多对象操作
