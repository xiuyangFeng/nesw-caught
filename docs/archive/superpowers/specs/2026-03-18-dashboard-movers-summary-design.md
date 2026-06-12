# Dashboard Movers Summary Design

## Context

`Dashboard` 页的 `Live Movers` 模块当前直接把 `marketStore.abnormalMovers` 全量渲染成纵向卡片列表。异动股票一旦变多，模块高度会快速膨胀，挤压同页的主题聚合和新闻入口，也削弱了 Dashboard 作为总览页的入口属性。

## Problem

- 当前模块把“总览入口”和“完整列表”混在一起，页面信息密度失衡。
- 每条卡片只展示名称、代码和原因，单条价值有限，但会大量重复堆叠。
- 用户在 Dashboard 主要需要先判断“今天异动多不多、集中在哪、是否值得点进去”，不需要在这里读完整清单。

## Goals

- 把 `Live Movers` 从完整列表收敛成“摘要 + 少量代表项 + 入口”。
- 在不改后端接口和 store 契约的前提下，保留用户对异动规模和主因的快速判断能力。
- 维持当前终端化视觉语言，并显著压缩模块高度。

## Non-Goals

- 不在 Dashboard 内提供完整异动展开、排序或筛选能力。
- 不调整 `Watchlist` 页的完整行情表格和详情流转。
- 不新增后端聚合字段，摘要逻辑全部在前端本地计算。

## Approaches Considered

### 方案 A：只截断列表

默认显示前 3 到 5 条，剩余条目隐藏。

优点：实现最小。
缺点：用户只能看到“少了几条”，但不知道整体规模、市场分布和主要触发原因，入口价值不足。

### 方案 B：摘要条 + Top 3 + 查看全部

顶部用一句摘要交代异动总数、市场分布和主因；中间只显示 3 条代表项；底部提供跳转到 `Watchlist` 的入口。

优点：最符合 Dashboard 的总览定位，信息结构清楚，实现复杂度适中。
缺点：摘要信息需要前端额外聚合和文案整理。

### 方案 C：摘要 + 内部折叠展开

默认只展示 2 条，支持在 Dashboard 内展开更多。

优点：不用跳页即可多看几条。
缺点：会把 Dashboard 再次拉回半详情页定位，结构边界重新变模糊。

## Decision

采用方案 B，并加入轻量增强：

- 顶部显示一个紧凑摘要区，包含：
  - 异动总数
  - 市场分布（港股 / 美股 / A 股）
  - 当前出现次数最多的 `abnormal_reason`
- 中部只保留最多 3 条代表项。
- 底部增加“查看全部异动”入口，跳转到 `Watchlist`。

## Interaction

- 当异动数为 0 时，仍沿用 `LoadingBlock` 的空态，不显示摘要面板。
- 当异动数大于 0 时：
  - 先看到摘要和代表项，而不是长列表。
  - 点击底部入口，进入 `/watchlist` 查看完整表格和后续操作。

## Data and Rendering

- 继续使用 `marketStore.abnormalMovers` 作为单一数据源。
- 在 `DashboardView.vue` 内新增计算属性：
  - `moverPreviewItems`: 截取前 3 条代表项
  - `moverMarketSummary`: 统计不同市场数量
  - `topMoverReason`: 统计最常见异动原因并转换为展示文案
- 不修改 `marketStore`、`api client` 或接口类型定义。

## Testing

- 更新 `DashboardView.test.ts`，覆盖：
  - 异动面板显示摘要信息
  - 只渲染前 3 条代表项
  - 显示“查看全部异动”入口

## Risks

- `abnormal_reason` 目前是后端返回的原始字符串，前端需要做最小映射；未知值需要优雅降级，避免空文案。
- “代表项”默认沿用当前数组顺序；若后端未来改变排序规则，Dashboard 的预览顺序会随之变化。这是可接受的，因为完整排序职责仍在 Watchlist。
