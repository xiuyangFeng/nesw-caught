# K 线 Overlay 与 Chart 手势让渡设计

## 背景

主 K 线图最近持续增强了 overlay 交互，当前十字光标、画线创建和对象编辑都通过 `KlineDrawingOverlay` 接管鼠标事件。

问题是 overlay 现在完整覆盖在主图之上，导致 `lightweight-charts` 原本依赖鼠标拖拽 / 滚轮接收的交互链路被挡住，用户无法再通过鼠标拖拽或滑动在主图中进行缩放 / 平移。

## 目标

- 恢复主图在非编辑态下的鼠标拖拽 / 滚轮交互
- 不破坏现有 overlay 的 crosshair、画线创建和对象编辑
- 只修根因，不重做整个 crosshair 或 overlay 架构

## 根因

`KlineDrawingOverlay` 是绝对定位全覆盖层，并持续接收 `mousemove / click / mousedown / mouseup`。当用户在空白区域做图表操作时，底层 `lightweight-charts` 根本拿不到原始事件，因此图表自己的手势逻辑失效。

## 方案

采用“空白区域手势让渡”：

- overlay 继续保留在最上层，负责 hover、绘图和编辑
- 仅当满足以下条件时，把事件临时让渡给底层 chart：
  - 当前是 `select` 模式
  - 不在 anchor / object drag 中
  - 不在 label edit 中
  - 鼠标按下位置没有命中可编辑对象本体或锚点
- 让渡方式：
  - `mousedown` 时临时把 overlay 切成 `pointer-events: none`
  - 找到底层元素并转发一份等价 `mousedown`
  - 直到全局 `mouseup` 再恢复 overlay
  - `wheel` 在非编辑态下直接转发到底层 chart，让滚轮缩放恢复

## 非目标

- 不把 hover 改成 chart 原生 crosshair 订阅
- 不改变对象命中、拖拽或绘图模式逻辑
- 不处理多指触控 / 复杂手势

## 测试策略

- 在 `KlineDrawingOverlay.test.ts` 增加失败测试：
  - 空白区域 `mousedown` 会把事件转发给底层元素
  - `wheel` 会在非编辑态下转发
  - 命中 drawing body 时不转发，仍由 overlay 接管

最小验证仍包括目标 Vitest 文件和前端 build。
