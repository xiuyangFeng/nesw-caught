# Watchlist Dashboard & K-Line Chart Design

## Context

当前自选股模块（`/watchlist`）是一个以管理为中心的纯表格页面：`WatchlistView` 展示价格、涨跌幅、OHLC、成交量等数字列；`WatchlistDetailView` 只有行情数字卡片和关联新闻列表。整个前端没有任何图表库，行情展示完全依赖数字和颜色标记。

用户核心诉求是将"自选股管理工具"升级为"交易仪表盘"：

- 左栏自选股概览（盯盘）+ 右侧单股详情面板（分析）的 Master-Detail 布局
- K 线图 + 技术指标（MA/MACD/KDJ/布林带）
- 新闻事件与 K 线走势的双向联动（图表标记 + 侧边栏新闻流）

## Approaches Considered

### Approach A: Lightweight Charts（推荐）

TradingView 官方开源的轻量金融图表库，专为 K 线设计。

优点：

- 包体积小（~40KB gzip），性能优秀
- 专为金融 K 线设计，candlestick + volume + marker API 开箱即用
- 原生深色主题与项目终端美学高度契合
- sparkline 可复用 line series，风格统一

缺点：

- 技术指标需自行计算（可后端完成）
- 多副图需多 chart 实例手动同步时间轴

### Approach B: ECharts

Apache 通用图表库，内建 candlestick 和丰富示例。

优点：

- 一个 chart 实例内可用 grid 分区做多副图，缩放同步开箱即用
- 技术指标社区示例丰富

缺点：

- 包体积大（按需引入 ~150KB+）
- 通用图表库，金融交互细节（十字光标、价格标尺）需额外调教
- 视觉风格偏"报表"，需要大量定制才能融入暗色终端 UI

### Approach C: ECharts + Lightweight Charts 混合

各取所长，sparkline 用 Lightweight Charts，K 线用 ECharts。

优点：

- 各场景最优引擎

缺点：

- 两套图表库增加包体积和维护复杂度
- 风格一致性需额外调教

## Recommended Design

采用 Approach A — Lightweight Charts，技术指标计算放在后端（pandas），前端只负责渲染。

---

### 一、整体布局架构

采用 Master-Detail 双栏布局，替代现有 `WatchlistView` 的全页表格：

```
┌─────────────────────────────────────────────────────────────┐
│  Watchlist Dashboard                              [刷新] [设置] │
├──────────────┬──────────────────────────────────────────────┤
│              │                                              │
│  自选股概览    │         详情面板（默认显示市场总览）            │
│  (左栏, ~320px│                                              │
│   可折叠)     │  ┌─────────────────────────────────────┐    │
│              │  │         K 线图 + 成交量               │    │
│ ┌──────────┐ │  │     [1D] [1W] [1M] [3M] [1Y]        │    │
│ │ MINIMAX  │ │  │     MA5 ── MA10 ── MA20 ── MA60     │    │
│ │ 916.5    │ │  │     📰 📰    (新闻事件标记)           │    │
│ │ -9.17%   │ │  │                                      │    │
│ │ ~~~~~~~~ │ │  ├─────────────────────────────────────┤    │
│ │(sparkline)│ │  │    副图: MACD / KDJ / 布林带 (切换)   │    │
│ └──────────┘ │  └─────────────────────────────────────┘    │
│ ┌──────────┐ │                                              │
│ │ 腾讯     │ │  ┌─────────────────┬────────────────────┐   │
│ │ 498.4    │ │  │   核心指标卡片    │    关联资讯侧栏     │   │
│ │ -1.89%   │ │  │  开/高/低/收/量   │   (时间倒序新闻流)  │   │
│ │ ~~~~~~~~ │ │  │  市值/PE/换手率   │   悬停K线标记联动   │   │
│ └──────────┘ │  └─────────────────┴────────────────────┘   │
│    ...       │                                              │
└──────────────┴──────────────────────────────────────────────┘
```

关键交互：

- 左栏自选股列表可滚动，点击某只股票 → 右侧详情面板切换到该股票
- 左栏可折叠（收起后只显示代码和涨跌色块），让 K 线图获得更大空间
- 默认未选中任何股票时，右侧显示市场总览摘要（复用现有 Dashboard 异动数据）
- 响应式：窄屏下左栏变为顶部横向滚动条

---

### 二、K 线图表系统

#### 图表区域结构

采用 Lightweight Charts 多实例同步方案，分为主图和副图。主图驱动副图的时间轴缩放同步（v1 不含跨实例十字光标联动）。

**主图（上方，占 ~65% 高度）：**

- Candlestick Series：标准 K 线（红涨绿跌，适配港股/A股习惯）
- Volume Series：成交量柱状图叠在主图底部（半透明），与蜡烛同色 — 涨红跌绿，保持同一根 K 线的颜色语义一致
- MA 叠加线：MA5 / MA10 / MA20 / MA60，各有独立颜色，可逐条开关
- 新闻事件 Marker：K 线上方（利好/中性）或下方（利空）用小圆点标记，悬停弹出卡片。卡片内容通过 marker 的 `items[].id` 从 store 中的 `detailNews` 列表关联获取摘要，`news_events` 自身不携带摘要字段以保持轻量。若某 `id` 在 `detailNews` 中尚未加载或缺失（并发时序差异），卡片降级为仅显示 marker 自带的 title + sentiment，摘要区域留空

**副图（下方，占 ~35% 高度，可切换）：**

- 默认显示 MACD（DIF / DEA / 柱状图）
- 可切换为 KDJ 或布林带
- 与主图时间轴同步缩放/滚动：采用**主图驱动副图**的单向同步 — 父组件 `StockDetailPanel` 订阅主图的 `timeScale.subscribeVisibleLogicalRangeChange`，同步设置副图的 `setVisibleLogicalRange`。用户只在主图上操作缩放/滚动，副图被动跟随。十字光标联动在 v1 暂不实现（Lightweight Charts 跨实例十字光标同步较复杂），后续版本再补

#### 周期切换

支持 5 个周期按钮，前端按钮与后端 API 参数的固定映射如下：

| UI 按钮 | `interval` 参数 | `range` 参数 | 说明 |
|---------|-----------------|-------------|------|
| 1D | `1d` | `6mo` | 日 K，近 6 个月 |
| 1W | `1wk` | `1y` | 周 K，近 1 年 |
| 1M | `1mo` | `2y` | 月 K，近 2 年 |
| 3M | `1d` | `3mo` | 日 K，近 3 个月（短周期日线） |
| 1Y | `1d` | `1y` | 日 K，近 1 年（长周期日线） |

其中 `3M` 和 `1Y` 本质是日线的不同回看长度，不改变 K 线粒度。周期切换时前端按此映射表拼接查询参数，重新请求数据。

#### 技术指标计算

放在后端完成，理由：

- 后端已有 `yfinance` 拉取 OHLCV 原始数据的链路
- 指标计算是纯数学（pandas 几行代码），后端统一算好后和行情数据一起返回
- 避免前端重复计算，方便后续缓存

当数据量不足以计算某个指标时（如 `range=3mo` 时 MA60 仅有少量有效值），后端返回稀疏数组 — 数据不足的时间点不出现在数组中，前端按实际数组长度渲染线段。副图指标若整个序列为空（如周 K 下 KDJ 数据不足），对应切换按钮显示为禁用态，悬停提示"数据不足"

---

### 三、自选股概览列表（左栏）

#### 卡片化增强表格

每只股票是一个卡片行，兼顾表格的信息密度和卡片的视觉表现力：

```
┌─────────────────────────┐
│  MINIMAX          HK    │  ← 名称 + 市场标签
│  HK0100                 │  ← 代码（次要色）
│                         │
│  916.5      -9.17%      │  ← 价格（大字）+ 涨跌幅（色块徽章）
│  ~~~~~~~~~~~~~~~~~~~~~~~~│  ← sparkline 迷你走势（近30日）
│  Vol: 2.08M    异动: ⚡   │  ← 成交量缩写 + 异动标记
└─────────────────────────┘
```

设计细节：

- **涨跌幅色块**：跌用红/粉色系，涨用绿色系，带圆角背景色块
- **Sparkline**：用 Lightweight Charts Line Series 渲染最近 30 个交易日收盘价，无坐标轴。涨区间填充浅绿，跌区间填充浅红
- **异动标记**：复用现有 `watchlistStore` 异动检测逻辑，有异动的卡片显示闪电图标
- **选中态**：当前查看的股票卡片左侧加亮边框（琥珀/橙色主题色）
- **悬停态**：微微提亮背景，光标变为 pointer
- **排序**：默认按涨跌幅绝对值降序，可切换为名称、价格等

#### 顶部操作区

搜索添加精简为搜索框 + 添加按钮，弹出 modal 完成添加流程：

```
┌─────────────────────────┐
│  🔍 搜索/添加自选股...    │  ← 点击展开搜索 modal
├─────────────────────────┤
│  排序: [涨跌幅▼] [名称]   │  ← 排序切换
├─────────────────────────┤
│  (股票卡片列表)           │
└─────────────────────────┘
```

---

### 四、资讯系统与新闻-K线联动

#### K 线上的新闻事件标记

- 有关联新闻的交易日，K 线蜡烛上方（利好/中性）或下方（利空）放置小圆点标记
- 颜色编码：🟢 正面 / 🟡 中性 / 🔴 负面（复用现有 sentiment 体系）
- 同一天多条新闻合并为一个标记，角标显示数量。标记采用该日新闻中最强情感倾向的颜色（优先级：负面 > 正面 > 中性）
- **悬停**：弹出浮动卡片，显示该日所有新闻标题列表 + 情感标签
- **点击**：右侧资讯侧栏自动滚动定位到该日第一条新闻，并高亮该日所有新闻

#### 右侧资讯侧栏

位于 K 线图下方右侧，与核心指标卡片并排，宽度约 40%：

```
┌──────────────────────────┐
│  关联资讯           全部 → │
├──────────────────────────┤
│  🟢 03/22  MINIMAX发布..  │
│     来源: Reuters | 正面   │
│     摘要前两行文字...       │
├──────────────────────────┤
│  🔴 03/20  监管部门关注..  │
│     来源: SCMP | 负面      │
│     摘要前两行文字...       │
└──────────────────────────┘
```

- **数据来源（单一数据源）**：`GET /api/watchlist/{symbol}/related-news` 是新闻数据的唯一来源。K 线接口 `kline` 返回的 `news_events` 字段由后端从同一查询逻辑派生，仅包含落在 K 线时间范围内的新闻 id + 标题 + 情感（不含摘要），用于渲染标记位置。侧栏使用完整的 `related-news` 响应。注意：两个并发请求之间不保证字节级一致（中间可能有新数据写入），但实际影响极小 — 最多在标记数量和侧栏列表之间出现一条差异，下次切换周期即同步
- 默认展示最近 20 条，滚动加载更多
- 每条：情感色点 + 日期 + 标题（单行截断）+ 来源 + 摘要（两行截断）
- **双向联动**：点击新闻 → K 线平移到对应日期并高亮标记；主图十字光标移到有新闻的日期 → 侧栏对应新闻卡片高亮（仅主图十字光标参与资讯联动，不涉及主/副图十字光标对齐，与第二节 v1 范围一致）

#### 核心指标卡片

与资讯侧栏并排左侧（约 60% 宽度），3×3 网格：

| 开盘 | 最高 | 最低 |
|------|------|------|
| 昨收 | 成交量 | 成交额 |
| 市值 | PE | 换手率 |

---

### 五、后端 API 新增与改造

#### 新增接口

**`GET /api/market/symbols/{symbol}/kline`**

K 线历史数据 + 技术指标 + 关联新闻事件。

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `interval` | string | `1d` | `1d` / `1wk` / `1mo` |
| `range` | string | `6mo` | `3mo` / `6mo` / `1y` / `2y` |

返回结构：

```json
{
  "symbol": "HK0100",
  "interval": "1d",
  "candles": [
    { "time": "2026-03-20", "open": 995, "high": 1048, "low": 900, "close": 916.5, "volume": 2078996 }
  ],
  "indicators": {
    "ma5": [{ "time": "2026-03-20", "value": 950.2 }],
    "ma10": [],
    "ma20": [],
    "ma60": [],
    "macd": [{ "time": "2026-03-20", "dif": 12.3, "dea": 8.7, "histogram": 3.6 }],
    "kdj": [{ "time": "2026-03-20", "k": 45.2, "d": 38.1, "j": 59.4 }],
    "bollinger": [{ "time": "2026-03-20", "upper": 1050, "middle": 980, "lower": 910 }]
  },
  "news_events": [
    {
      "time": "2026-03-18",
      "items": [
        { "id": "xxx", "title": "MINIMAX发布新模型", "sentiment": "positive" },
        { "id": "yyy", "title": "行业分析报告", "sentiment": "neutral" }
      ]
    }
  ]
}
```

**`POST /api/market/sparklines`**

批量获取多只股票的迷你走势数据。

请求体：

```json
{ "symbols": ["HK0100", "HK0700", "HK2513"] }
```

返回：

```json
{
  "HK0100": { "prices": [920, 935, 910, ...] },
  "HK0700": { "prices": [500, 498, 502, ...] }
}
```

固定返回近 30 个交易日收盘价，轻量接口专门服务左栏 sparkline。单次请求最多 30 个 symbol，超出返回 400 错误。

#### 现有接口复用（无需改动）

| 接口 | 用途 |
|------|------|
| `GET /api/watchlist` | 自选股列表 |
| `GET /api/market/watchlist` | 自选股行情快照 |
| `GET /api/watchlist/{symbol}/related-news` | 关联新闻 |
| `GET /api/watchlist/candidates` | 搜索候选 |

#### 后端实现要点

- **Symbol 规范化**：复用现有 `normalize_symbol` 逻辑，前端传入 `HK0100` 格式，后端转换为 `yfinance` 需要的 `0100.HK` 格式
- **K 线数据**：`yfinance.download(symbol, period=range, interval=interval)` 获取 OHLCV，pandas 计算指标后序列化返回
- **缓存策略**：按 `{symbol}:{interval}:{range}` 缓存到 Redis；日 K 缓存 5 分钟（盘中），周/月 K 缓存 1 小时
- **新闻事件对齐**：从 `related-news` 结果中提取 `published_at` 日期，映射到**最近的前一个交易日**（向前对齐，即周末新闻映射到周五），确保标记不出现在非交易日。交易日判断基于 K 线蜡烛数据中实际存在的日期集合
- **接口鉴权**：与现有 `/api/market/*` 接口保持一致（当前无认证）。`kline` 和 `sparklines` 接口仅允许查询已加入 watchlist 的 symbol，非自选股 symbol 返回 404
- **yfinance 降级**：yfinance 请求超时 10 秒，失败时返回 Redis 中上一次缓存数据（若有），响应中附加 `stale: true` 标记；若无缓存则返回 503
- **限流**：`kline` 和 `sparklines` 共享同一个 `market_heavy` 限流桶，单 IP 每分钟合计最多 60 次请求。超限返回 429 + `Retry-After` 头。限流实现复用现有中间件（若无则按 FastAPI `slowapi` 集成）

---

### 六、前端组件架构

```
views/
  WatchlistDashboardView.vue    ← 新页面（替代现有 WatchlistView）

components/watchlist/
  WatchlistSidebar.vue          ← 左栏：搜索 + 排序 + 股票卡片列表
  StockCard.vue                 ← 单只股票卡片（sparkline + 价格 + 涨跌）
  StockSparkline.vue            ← Lightweight Charts line series 封装
  
  StockDetailPanel.vue          ← 右侧详情面板容器，负责主图/副图时间轴同步
  KlineChart.vue                ← 主图：K线 + MA + 成交量 + 新闻标记渲染与悬停浮动卡片（标记数据注入 series，浮动卡片 UI 内聚在此组件）
  IndicatorChart.vue            ← 副图：MACD / KDJ / 布林带（可切换）
  StockMetricsGrid.vue          ← 核心指标卡片网格
  RelatedNewsSidebar.vue        ← 关联资讯侧栏（接收联动事件，滚动定位）
```

保留现有 `WatchlistTable.vue` 不删除，新页面独立开发。路由 `/watchlist` 指向新的 `WatchlistDashboardView`，旧详情页 `/watchlist/:symbol` 可保留作为 fallback 或后续移除。

#### Pinia Store 扩展

在现有 `watchlistStore` 中新增以下状态字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `selectedSymbol` | `string \| null` | 当前选中的股票代码 |
| `currentInterval` | `string` | 当前 K 线周期（默认 `1d`） |
| `currentRange` | `string` | 当前 K 线回看范围（默认 `6mo`） |
| `klineData` | `KlineResponse \| null` | 当前选中股票的 K 线 + 指标数据 |
| `klineLoading` | `boolean` | K 线数据加载中 |
| `klineError` | `string \| null` | K 线数据加载错误 |
| `sparklines` | `Record<string, number[]>` | 各股票的 sparkline 数据 |
| `detailNews` | `NewsItem[]` | 当前选中股票的关联新闻完整列表 |

`selectSymbol(symbol)` action 负责：设置 `selectedSymbol`，重置 `klineData`/`detailNews`，并发请求 `kline` 和 `related-news`。`switchPeriod(interval, range)` action 负责：仅重新请求 `kline`，不刷新新闻。子组件通过 store 读状态，不自行发请求。

---

### 七、数据流总览

```
用户点击股票卡片
  → watchlistStore.selectSymbol(symbol)
  → 并发请求:
      1. GET /api/market/symbols/{symbol}/kline?interval=1d&range=6mo
      2. GET /api/watchlist/{symbol}/related-news
  → KlineChart 渲染 candles + indicators
  → IndicatorChart 渲染 MACD (默认)
  → RelatedNewsSidebar 渲染新闻列表
  → KlineChart 上叠加 news_events markers

用户切换周期
  → GET /api/market/symbols/{symbol}/kline?interval=1wk&range=1y
  → 重新渲染主图 + 副图

用户悬停 K 线新闻标记
  → 显示浮动卡片（标题 + 情感 + 摘要）
  → 侧栏对应新闻高亮

用户点击侧栏新闻
  → K 线平移到对应日期
  → 标记高亮闪烁

页面加载
  → GET /api/watchlist (自选股列表)
  → GET /api/market/watchlist (行情快照)
  → POST /api/market/sparklines (批量 sparkline)
  → 渲染左栏卡片列表
```

---

### 八、错误处理

- K 线接口失败：详情面板显示重试按钮 + 错误提示，不影响左栏
- Sparkline 批量请求部分失败：对应卡片隐藏 sparkline 区域，仅显示数字
- 新闻关联接口失败：侧栏显示"暂无资讯"占位，K 线不叠加标记
- 左栏行情快照失败：卡片显示"--"占位价格
- 页面加载态：左栏先渲染骨架屏（skeleton），sparkline 异步填充；右侧未选中股票时显示市场总览占位，选中后显示加载动画直到 K 线数据就绪
- 自选股列表为空：右侧显示引导提示"添加自选股开始使用仪表盘"

### 九、测试策略

- **后端**：
  - K 线接口返回结构与 schema 一致
  - MA5/10/20/60 计算结果与 pandas `rolling().mean()` 参考值对比（允许浮点误差 1e-6）
  - MACD/KDJ/布林带公式正确性
  - 缓存命中返回相同数据、TTL 过期后重新拉取
  - 新闻日期向前对齐到最近交易日：周六/周日新闻映射到周五，节假日类推
  - 非 watchlist symbol 请求返回 404
  - yfinance 超时降级返回 stale 缓存或 503
  - sparklines 批量请求超过 30 个 symbol 返回 400
- **前端**：
  - 组件挂载与 store 数据绑定
  - 周期切换按映射表拼接正确的 interval + range 参数
  - 联动交互：标记点击→侧栏滚动、新闻点击→图表平移
  - 指标数据不足时副图按钮禁用
- **集成**：完整链路 — 选中股票→K线渲染→切换指标→新闻联动

## Expected Outcome

完成后，`/watchlist` 将从纯表格管理页升级为 Master-Detail 交易仪表盘。用户可以在左栏快速浏览所有自选股的实时行情和迷你走势，点击任意股票后在右侧深入查看 K 线走势、技术指标和关联资讯，新闻事件与价格走势在视觉上强关联。整体视觉风格延续项目现有的暗色终端美学，图表引擎 Lightweight Charts 天然契合。
