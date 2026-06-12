# K 线触摸手势滚动穿透修复设计

## 背景

`KlineDrawingOverlay` 目前已经支持把空白区域的鼠标 `mousedown` 和 `wheel` 让渡给底层 `lightweight-charts`，因此桌面端的拖拽和平移已经恢复。

但触摸链路还没有覆盖。用户在 K 线区域单指滑动时，overlay 没有把触摸手势交给底层图表，也没有阻止浏览器默认滚动，于是页面容器会跟着上下滚动，这和交易终端里“图表区域优先消费手势”的预期不一致。

## 目标

- 在 K 线区域单指滑动时，页面不再跟着滚动
- 空白区域的触摸手势可以继续交给底层 chart 处理平移
- 不破坏现有 drawing 的命中、拖拽、标签编辑和绘图模式
- 尽量复用现有 overlay 手势让渡模型，避免扩大改动范围

## 根因

当前 overlay 只处理鼠标事件：

- 空白区 `mousedown` 让渡到底层图表
- 空白区 `wheel` 让渡到底层图表

但没有对应的 `touchstart` / `touchmove` / `touchend` 链路，也没有显式约束触摸默认滚动行为。结果是：

- 触摸命中空白区时，图表没有拿到完整触摸序列
- 浏览器默认把垂直滑动解释成页面滚动
- 用户感觉像是“滑 K 线时整个窗口被带着走”

## 方案

采用“沿用现有空白区手势让渡模型，补齐触摸版”的最小修复：

- overlay 仍然保持顶层交互层，不改现有 hover / drawing / edit 架构
- 在 `select` 模式、非拖拽、非标签编辑、且命中空白区域时：
  - `touchstart` 临时把 overlay 切成 `pointer-events: none`
  - 找到触点下方底层元素并转发等价的 `touchstart`
  - 后续 `touchmove` 继续转发到同一个底层目标，保证 chart 拿到完整触摸序列
  - `touchend` / `touchcancel` 也转发到底层目标，然后恢复 overlay 所有权
- 同时在 overlay 上增加明确的非被动触摸处理：
  - 仅在“空白区让渡已激活”的触摸序列里，对 `touchmove` 调用 `preventDefault()`
  - 目的不是替代图表手势，而是阻止浏览器把图表区滑动继续解释成页面滚动
  - 非让渡状态不阻止默认行为，避免误伤 drawing 编辑或其它交互
- 如果命中 drawing body / anchor，或者当前处于绘制编辑态，则 overlay 继续持有手势，不做让渡

## 取舍

不采用纯 CSS `touch-action: none` 的粗暴方案，因为那会把 drawing 编辑和底层图表自己的触摸能力一起压掉，副作用太大。

也不把 overlay 全量重写成 Pointer Events 统一模型，因为这轮只是一个明确的触摸穿透 bug，重构范围会明显超出问题本身。

## 非目标

- 不新增双指缩放、自定义 pinch 识别等复杂手势
- 不重写 overlay 的鼠标拖拽编辑模型
- 不把 hover/crosshair 改成 lightweight-charts 原生事件订阅

## 测试策略

在 `KlineDrawingOverlay.test.ts` 中新增失败回归测试：

- 空白区域完整 `touchstart` / `touchmove` / `touchend` 序列会转发到底层元素
- 空白区域在触摸让渡激活时，`touchmove` 会阻止默认页面滚动
- `touchend` / `touchcancel` 后 overlay 会恢复自身所有权
- 命中 drawing body 时不转发，仍由 overlay 接管

最小验证仍包括：

- `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts`
- `npm --prefix frontend run build`
