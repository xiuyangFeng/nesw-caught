# App Shell Status Badge Stacking Design

## Context

前一轮修复把 `System Status` 卡片中的状态头改成了双列 grid，解决了短 badge 把左侧标签起点挤歪的问题。但 `market_quote_producer` 这类长 badge 仍然需要和左侧标签共享同一行宽度，在 272px 侧栏中会继续把 `Market worker` 标签压成两行，视觉上仍然是不对齐。

这说明根因不是“左右两列没有对齐规则”，而是“窄侧栏里不应该让长 badge 和标签争抢同一行空间”。

## Options

### Approach A: 继续保留横向两列，限制 badge 宽度

给 badge 加更激进的 `max-width`、截断或更小字号。

优点：

- 改动小

缺点：

- 只是压缩问题，不解决横向竞争
- worker 名称信息会被截断或继续难看换行

### Approach B: 状态头改成纵向堆叠

每个状态单元先显示标签，再显示 badge；badge 独占下一行宽度，不再和标签共享一行。

优点：

- 完全消除标签与 badge 的横向挤压
- 更适合窄侧栏和长运行态文案
- 后续更长的 worker 名称也稳定

缺点：

- 卡片垂直高度略增

## Recommended Design

采用 Approach B。

### Layout

- `System Status` 与 `Market worker` 头部统一改为纵向 stack
- 第一行放标签
- 第二行放 badge
- badge 使用 `w-full`，文本左对齐，允许自然换行

### Badge Behavior

- 保留现有颜色语义和 `.pill` 基础视觉
- 在状态卡内通过额外 class 让 badge 变成块级、整宽、顶部对齐的状态条
- 长 worker 名称允许在 badge 内换行，但不会再影响标签位置

### Testing

更新 `AppShell` 测试，锁定：

- 两个状态单元使用统一的 stack 布局标记
- worker badge 带有整宽展示约束
- 长 worker 状态文案仍可见

## Expected Outcome

完成后，状态卡里的左侧标签不会再被长 badge 压缩成异常换行，绿色 worker 提示会在自己的整宽区域内显示，整体对齐稳定。
