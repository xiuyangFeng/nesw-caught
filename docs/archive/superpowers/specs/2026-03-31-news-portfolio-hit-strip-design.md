# News Portfolio Hit Strip Design

## Summary

新闻首页继续保持 `Latest Events` 的全市场发现定位，但每张事件卡增加一条极薄的 `命中持仓` 信息条，帮助用户在不抬高卡片高度的前提下，快速判断该事件是否命中自己的自选股。

本次只做轻量命中层，不新增新页面、不引入大块解释面板、不改首页主排序、不扩 event detail 契约。

## Goals

- 首页事件卡可直接展示命中的持仓股名字。
- 卡片纵向高度只做轻量增加，保持当前紧凑扫描节奏。
- 后端在现有事件聚合契约里输出稳定的 watchlist hit 数据，避免前端二次拼接。

## Non-Goals

- 不做首页长摘要或额外的说明区块。
- 不做直接/间接命中的复杂因果解释文案。
- 不新增单独的“与你持仓相关”首页分栏。
- 不接入新的 AI 排序或个性化模型。
- 不修改 `NewsEventDetailView` 或事件详情页展示。
- 不调整事件的现有排序分数。

## UX Design

### Event Card

事件卡保留现有四层结构：

1. 顶部元信息：事件类型、情绪、市场、时间
2. 标题
3. 新增一条超短 `命中持仓` 行
4. 原有 meta / stats / evidence

`命中持仓` 行规则：

- 仅在当前事件命中至少一只持仓股时显示。
- 文案形态固定为 `命中持仓：股票名 · 股票名 +N`。
- 最多展示 2 个股票名字，其余收口到 `+N`。
- 不显示 ticker，只显示 watchlist 里的 `display_name`。
- 不展示解释文案，不展示图标按钮，不新增额外交互。
- 整条命中行强制单行显示，超出卡片宽度时使用 CSS `text-overflow: ellipsis`，不允许换行把卡片继续抬高。

### Height Control

- 命中条使用比正文更弱的颜色和更小字号。
- 与标题间距收紧，避免形成“第二个内容块”。
- 无命中事件不占位，保证列表整体密度不被稀释。
- 命中条最多占用 1 行高度；长股票名截断，不因为中文长名称换成两行。

## Data Design

### API Contract

为 `NewsFeedEventCardView` 新增：

- `watchlist_hits: string[]`

语义：

- 来自当前 watchlist 的命中股票显示名列表。
- 顺序严格按事件 symbol 命中顺序决定，遍历顺序为 `primary_symbol` -> `related_symbols`。
- 去重后返回。
- `display_name` 为空时跳过该命中项，不回退 ticker。

### Hit Matching

事件命中依据仅使用现有事件聚合出的 symbol 信号：

- `primary_symbol`
- `related_symbols`

匹配逻辑：

- 若事件 symbol 与 watchlist item.symbol 相同，则记为命中。
- 命中后输出该 watchlist item.display_name。
- 同一股票即使命中多次也只展示一次。
- 命中输出顺序以事件 symbol 出现顺序为准，不按字母表或 watchlist 排序。

本期不区分直接/间接命中，只提供轻量命中名单。

## Implementation Notes

- 后端命中计算放在 `NewsFeedLayoutService` 内部，复用数据库 session 拉取 watchlist。
- 只改 `feed-layout` 返回链路。
- 前端只消费后端给出的 `watchlist_hits`，不在组件里重新拼 symbol->name 映射。

## Testing

- 后端单测覆盖事件命中字段生成、去重、稳定顺序和 `display_name` 为空时跳过。
- 后端接口测试覆盖 `GET /api/news/feed-layout` 返回新字段。
- 前端 API/store 测试覆盖新字段透传。
- 前端组件测试覆盖命中条显示/隐藏与 `+N` 收口。
- 新闻首页视图测试覆盖命中持仓文案出现在事件卡中。

## Risks

- 当前命中基于 symbol 直接匹配，无法解释产业链间接影响，后续可能需要 research brief 风格的第二层解释。
- watchlist 很大时，首页多事件都命中可能降低命中条的区分度；本期通过只显示前 2 个名字来控制噪音。
