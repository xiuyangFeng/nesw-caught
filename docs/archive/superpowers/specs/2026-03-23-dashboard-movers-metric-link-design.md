# Dashboard Movers Metric Link Design

## Context

首页 `Dashboard` 顶部 `HeroMetrics` 区域已经把“偏利好”“偏利空”等指标做成整卡可点击入口，但右上角“异动股票”指标卡仍然只是静态展示。

这会造成两个问题：

- 同一排指标卡的交互模型不一致，用户难以预测哪些能点、哪些不能点
- “异动股票”文案本身已经明确是“自选股异动入口”，静态卡片会削弱入口语义

## Options

### Approach A: 保持静态，只保留下方 Watchlist 区块按钮

优点：

- 零改动

缺点：

- 指标卡与文案含义不一致
- 用户需要下滑到下面区域才能进入详情页

### Approach B: 整张指标卡跳转到 `/watchlist`

优点：

- 与同排其他指标卡交互一致
- 用户在 Dashboard 顶部就能进入自选股异动页
- 复用现有 `HeroMetrics` 路由卡片模式，改动最小

缺点：

- 顶部和下方 Watchlist 区块都会提供相同目标入口

### Approach C: 仅数字区域可点

优点：

- 保留部分静态外观

缺点：

- 点击区域不清晰
- 与现有整卡可点的指标卡模式不一致

## Recommended Design

采用 Approach B。

### Interaction

- `Dashboard` 顶部“异动股票”指标卡改成整卡可点击
- 点击后跳转到 `/watchlist`
- 视觉保持现有 `HeroMetrics` 路由卡片样式，不做额外图标或文案补充

### Testing

- `DashboardView` 测试覆盖“异动股票”指标卡链接到 `/watchlist`
- 保持已有情绪指标跳转测试，确保多入口并存不回退

## Expected Outcome

完成后，Dashboard 顶部四张指标卡的交互模型会更一致：有入口语义的卡片都能直接点击进入对应页面，其中“异动股票”会直接带用户进入 Watchlist 页面。
