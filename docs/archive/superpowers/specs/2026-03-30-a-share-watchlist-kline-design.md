# A-Share Watchlist & K-Line Expansion Design

## Context

当前 watchlist / K 线链路只真正支持港股与美股：

- 前端 `Market` 类型已经包含 `cn`，新闻流也已经接入 `36Kr`、`CLS Telegraph`、`Zhipu AI News` 等 `cn` 内容源
- 但后端 `normalize_symbol()` 只支持 `hk/us`
- watchlist 候选池没有 A 股
- A 股 symbol 不能进入行情抓取、K 线、sparkline、自选详情与新闻 marker 主链路

用户目标不是单点“能搜到 A 股新闻”，而是把 A 股完整纳入当前 watchlist 体验：

- 可把 A 股加入自选
- 可查看 A 股报价与 K 线
- K 线上可挂载该股票关联新闻 marker
- 默认候选与内容关注范围不再局限港股和美股

## Approaches Considered

### Approach A: 仅扩前端候选与展示

优点：

- 改动最小
- 很快能在界面看到 `cn`

缺点：

- 后端仍无法抓取 A 股行情
- K 线与报价接口依旧不可用
- 实际是“假支持”

### Approach B: 统一扩展 watchlist 主链路（推荐）

做法：

- 统一采用 `600519.SH` / `000001.SZ` 作为 A 股 canonical symbol
- 扩展后端 symbol 归一化、报价、sparkline、K 线接口
- 扩充 watchlist 默认候选池与前端展示
- 复用现有 `cn` 新闻市场做关联新闻与 K 线 marker

优点：

- 与现有 `0700.HK` 风格一致
- watchlist、quote、kline、news mention 使用同一主键
- 改动集中在既有链路，维护成本低

缺点：

- 需要同时修改后端与前端测试
- A 股 alias 规范要补齐

### Approach C: 单独为 A 股做新 provider / 新市场分支

优点：

- 可为未来指数、ETF、基金留专用通道

缺点：

- 当前需求只涉及个股，会过度设计
- 增加重复逻辑和额外维护面

## Recommended Design

采用 Approach B。

核心决策：

- A 股 canonical symbol 统一为交易所后缀格式：`600519.SH`、`000001.SZ`
- watchlist、行情缓存、K 线接口、新闻 mention 都以 canonical symbol 为主键
- 先支持沪深 A 股个股，不额外引入指数/ETF 特殊分支
- 持久化到 `watchlist_item.symbol` 的值必须始终是 canonical symbol，不保留别名输入

---

## 一、Symbol 与市场规范

### Canonical 规则

- 上海主板/科创板等上海市场：`6xxxxx.SH`
- 深圳主板/创业板等深圳市场：`0xxxxx.SZ` / `3xxxxx.SZ`
- 市场值统一为 `cn`

### 接受的输入别名

系统在创建 watchlist、查详情、抓 K 线时接受以下输入，并归一化为 canonical symbol：

- `600519.SH`
- `000001.SZ`
- `SH600519`
- `SZ000001`
- 在已知 `market=cn` 时接受纯 6 位数字，如 `600519` / `000001`

### 持久化规则

- `POST /api/watchlist` 收到 A 股别名输入时，必须先归一化，再写入数据库
- `watchlist_item.symbol`、行情缓存 key、相关新闻查询 key 全部使用 canonical symbol
- 明细查询路由可以保留用户原始输入作为返回里的 `symbol` 字段，但内部查库和 provider 访问都必须转 canonical symbol

这样可以避免 `600519`、`SH600519`、`600519.SH` 被当成三只不同股票。

### 非目标范围

本次不单独支持：

- 指数，如 `000001.SH`
- ETF / LOF / 基金的专门分类
- 北交所单独市场枚举

这些代码如果刚好满足沪深个股格式，先按 `cn` 普通 symbol 处理，不新增专门 UI 或分类逻辑。

---

## 二、后端行情与 K 线链路

### Quote / Sparkline / Kline

扩展 `normalize_symbol()`，让 `QuoteService` 与 `MarketChartService` 自动支持 `cn`：

- `YahooFinanceQuoteProvider` 继续作为统一 provider
- A 股 canonical symbol 与 provider symbol 分离：
  - canonical: `600519.SH`
  - provider: `600519.SS`
  - 深圳市场 canonical/provider 都使用 `.SZ`
- sparkline 继续读取最近 30 个收盘价
- K 线继续复用现有 OHLCV + MA/MACD/KDJ/BOLL 计算方式

原因：

- 系统内需要保持 `600519.SH` 这种更贴近国内语义的 canonical 格式
- 但当前统一 provider 是 Yahoo Finance，上海市场实际需要 `.SS` 才能取到数据

### Watchlist 约束

保留现有规则：K 线与报价详情仍要求 symbol 先存在于 watchlist。

原因：

- 当前缓存、详情页、相关新闻、手动刷新都围绕 watchlist 运转
- 不扩大接口语义，避免本次需求顺带引入“任意 symbol 查询”新职责

### 新闻 marker

K 线 marker 继续从 `NewsMentionsRepository.list_related_news(symbol)` 派生。

只要：

- watchlist 中存的是 canonical A 股 symbol
- 新闻 mention 中保存的也是同一 canonical symbol

那么 A 股 marker 不需要新接口，只需要主链路打通。

---

## 三、A 股内容源与候选池

### 内容源

项目已经有 `cn` 新闻源：

- `36Kr`
- `CLS Telegraph`
- `Zhipu AI News`

本次不新增新爬虫，而是把“系统支持的市场范围”从“港股/美股主导”扩展为“港股/美股/A 股并行”，并确保 watchlist 加入 A 股后能消费已有 `cn` 内容。

### 候选池

扩展 `WATCHLIST_CANDIDATES`，补一组默认 A 股高频观察标的，并给出固定顺序。首批默认候选：

- `600519.SH` 贵州茅台
- `300750.SZ` 宁德时代
- `000001.SZ` 平安银行
- `600036.SH` 招商银行
- `601318.SH` 中国平安
- `002594.SZ` 比亚迪
- `688041.SH` 海光信息
- `688981.SH` 中芯国际

候选展示仍沿用现有字段：

- `symbol`
- `display_name`
- `market`
- `aliases`

搜索命中应支持中文名、英文名、代码别名和纯数字别名。

候选顺序要求：

- 保留现有 HK/US 候选
- A 股候选追加到静态默认池中
- 因为添加 modal 默认显示前 8 个命中项，所以前端 mock/fallback 也必须同步补 A 股，避免降级模式下出现“后端有 A 股、前端 mock 没有”的分叉

---

## 四、前端 watchlist 与 K 线体验

前端不做新的 A 股专属视图，直接扩展既有 watchlist 体验：

- 添加自选 modal 中出现 A 股候选
- 选中后可进入现有 detail panel
- 价格、振幅、区间位置、新闻侧栏、K 线 marker 全部复用已有组件

UI 上只需要保证：

- 市场标签中的 `cn` 在现有文案里继续显示为 `A股/国内` 或 `A股`
- A 股 symbol 在紧凑卡片和详情标题里按 canonical 格式展示

不新增新的周期、交易时段说明或中国市场专属颜色规则。

---

## 五、测试策略

### Backend

先写失败测试，再实现：

- `normalize_symbol()` 支持 `.SH/.SZ`、`SHxxxxxx/SZxxxxxx`、`market=cn + 纯数字`
- quote / detail 路由能返回 A 股 canonical provider symbol
- K 线接口能对 A 股 watchlist symbol 返回 candles / indicators / news_events
- sparkline 能包含 A 股数据

### Frontend

先写失败测试，再实现：

- A 股候选在添加自选流程中可见并可创建
- store 获取 A 股 K 线时沿用既有周期映射
- 详情面板与 K 线组件能渲染 A 股 symbol 和新闻数据

---

## 六、风险与边界

### 风险

- `yfinance` 对部分 A 股代码可能存在临时不可用或延迟，行为会和现有港股/美股一样落到 `fetch_failed/delayed`
- 现有新闻 mention 是否总是规范成 `.SH/.SZ` 取决于上游抽取链路；若历史数据中存在裸代码或其他别名，旧数据的相关新闻召回可能不完整

### 本次不解决

- 历史新闻 mention 的批量回填归一化
- A 股指数/ETF 专门候选池
- 中国市场交易时区、节假日或涨跌停的专门 UI 规则
- 新增 A 股专属新闻源或行情 provider
