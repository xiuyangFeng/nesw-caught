# App Shell Status Indicator Alignment Design

## Context

`AppShell` 左下角 `System Status` 卡片目前用 `flex` + `justify-between` 排布标题和状态 badge。短文案时看起来正常，但当 badge 文案变长，例如 `SSE 已断开` 或 `MARKET_QUOTE_PRODUCER OK`，右侧内容会挤压左侧列，导致两行状态指标的起始位置和视觉基线不一致，出现“左侧没对齐”的问题。

这次需求只修正状态卡片内的排版稳定性，不调整状态来源、状态文案、颜色语义或其他页面布局。

## Options

### Approach A: 继续使用 `flex`，只增加宽度约束

给 badge 增加 `min-width`、`max-width`、`shrink-0` 或截断规则，尽量减轻挤压。

优点：

- 改动很小
- 不需要调整模板结构

缺点：

- 左侧标签和右侧 badge 仍共享一条弹性主轴
- 文案长度变化时，对齐仍可能漂移
- 只能缓解，不是彻底修复

### Approach B: 把状态头统一改成两列 grid

把 `System Status` 和 `Market worker` 这两行都改成统一的两列布局：左列固定放标签，右列放 badge，统一对齐规则。

优点：

- 左列起点稳定，不再受右侧 badge 长度影响
- 两行状态头可以复用同一排版约束
- 后续新增更长状态文案时更稳

缺点：

- 需要轻微调整模板 class

## Recommended Design

采用 Approach B。

### Layout

- 状态头统一使用两列 grid
- 左列使用 `minmax(0,1fr)` 承载标签文本
- 右列使用 `auto` 承载 badge
- 容器统一使用 `items-start`，badge 使用 `justify-self-end`

### Badge Behavior

- badge 保持现有 `.pill` 样式语义
- 允许 badge 在自己的格子内收缩或换行
- 右侧 badge 不再决定左列标签的位置

### Testing

更新 `AppShell` 测试，锁定：

- `System Status` 和 `Market worker` 两行都使用统一的 grid 头部布局
- 长 worker 状态文案仍会渲染，不会因为布局调整丢失

## Expected Outcome

完成后，左下角状态卡片里的 `System Status` / `Market worker` 指标行会保持一致的左侧起点和右侧 badge 对齐方式，`SSE 已断开` 之类较长文案也不会再把左侧指标挤歪。
