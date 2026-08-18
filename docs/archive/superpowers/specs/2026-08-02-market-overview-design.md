# 市场总览（Market Overview）设计

日期：2026-08-02
分支：feature/market-overview
状态：设计待评审

## 一、目标与边界

### 目标

在 Watchlist 页顶部新增"市场总览"区块（不新开页面、不改路由），展示全球大盘情况和情绪：

1. 覆盖市场：美股（us）、A 股（cn）、韩国（kr）、日本（jp）、欧洲（eu，泛欧）。
2. 每市场 1-3 个代表指数，用户可在页面上增删配置（单用户全局配置，无需多租户）。
3. 板块/热点：A 股接东方财富行业板块行情接口展示涨跌榜；美/欧用预置行业 ETF（走 Yahoo）近似；日/韩不做板块。
4. 情绪：每市场一个量化情绪标签（恐慌/中性/贪婪）+ 当日新闻情绪分数 + 近期重要信号列表（可点击跳转新闻）。
5. 独立低频轮询 worker 刷新指数/板块行情，复用 `price_snapshot` 落库机制。

### 明确不做（Out of Scope）

- 不新开页面、不改路由、不碰 `AppShell.vue` 导航结构。
- 不做历史趋势图、不落情绪/板块历史表（新闻情绪只算当日实时）。
- 日/韩不做板块区；港股不在覆盖范围内（现有 watchlist 的 hk 支持不受影响）。
- 不做指数的 K 线/分时图（点击指数不进入详情页，本期仅展示快照）。
- 不改动现有 `MarketQuoteProducer`（自选股 15s 轮询）的行为与配置。
- 不做用户级个性化（配置表是单用户全局的，无 user_id）。
- 不引入节假日日历（沿用 `market_hours.py` 的粗粒度时段判断思路）。

## 二、代码调研结论（与需求背景的出入已在文中标注）

1. **指数 ticker 不能走 `normalize_symbol`**：`backend/app/services/quote_provider.py:79` 的 `normalize_symbol` 对 `^GSPC`/`^IXIC`/`^VIX` 这类以 `^` 开头的 Yahoo 指数 ticker 会走到最后的 `clean_raw.isalnum()` 分支，`^` 不是字母数字，**直接抛 `ValueError("unsupported symbol")`**。`000300.SS` 可以被 normalize，但会被归一化为 `000300.SH`/`cn` 市场，若走 `QuoteService` 会被 `_TENCENT_PRIMARY_MARKETS` 路由到腾讯源。
   **结论**：市场总览的指数行情**不经过 `normalize_symbol` / `QuoteService` 的读路径**，由新的 `MarketOverviewService` 按配置表直接构造 `NormalizedSymbol(symbol=原始ticker, market=配置市场, provider_symbol=原始ticker)`，调用 `YahooFinanceQuoteProvider.fetch_quotes_batch`（`yf.download` 批量路径对 `^GSPC`/`^IXIC`/`^KS11`/`^N225`/`^STOXX50E`/`^VIX`/`000300.SS`/`XLK` 这类 ticker 天然支持，无需改 provider 代码），然后复用 `MarketRepository.save_snapshot` 落 `price_snapshot`。
2. **`price_snapshot` 模型可直接复用**：`backend/app/models/price_snapshot.py` 的字段（symbol/market/price/change_percent/.../provider_name/fetched_at）对指数快照完全够用；`market` 列是 `String(16)`，存 `kr`/`jp`/`eu` 无兼容问题。指数快照与自选股快照同表共存，现有 `GET /api/market/snapshots` 会把指数也带出来——需要在读路径按 symbol 归属区分（见 API 设计）。
3. **东财板块接口是新增数据源**：`quote_provider.py` 现有两个 provider 都是"逐 symbol 报价"语义，板块接口是"一次请求返回整榜"，形态不同，不宜塞进 `QuoteRecord`。新增独立的 `EastMoneyBoardProvider`（新文件 `backend/app/services/board_provider.py`），返回板块榜单数据结构。
4. **新闻归属市场有现成字段**：`news_item.market`（`backend/app/models/news_item.py:38`，由 ingestion 源定义填充，值为 `us`/`cn`/`hk` 等）和 `news_stock_mention.market`（`backend/app/models/news_stock_mention.py:17`，mention 时由 LLM 管线写入）都带市场信息，情绪归属方案以此为主，见第六节。
5. **`market_hours.py` 只有 cn/hk/us**：`backend/app/services/market_hours.py:22` 的 `_SESSIONS_UTC` 需为 overview worker 增加 kr/jp/eu 时段（新增独立的 session 表，不改现有函数语义，避免影响自选股 producer 的降频判断）。
6. **前后端契约链路**：后端 schema 改动后需跑 `python scripts/export_openapi.py` + `npm --prefix frontend run generate:api`（生成 `frontend/src/types/generated/api.d.ts`）。前端 `apiClient`（`frontend/src/api/client.ts`）是手写的，新方法需手写并配 mock fallback。
7. **鉴权**：所有 `/api/market` 路由挂在 `api_router` 下（`backend/app/main.py:328`），自动继承 `verify_app_token`，新增端点无需额外处理。

## 三、整体架构

### 数据流

```
┌─ MarketOverviewProducer (新 worker, BaseWorker 子类) ─────────────┐
│ 盘中 60s / 闭市 300s 轮询                                          │
│  1. 读 market_index_config(enabled=1)                             │
│  2. YahooFinanceQuoteProvider.fetch_quotes_batch(指数+ETF+^VIX)   │
│  3. MarketRepository.save_snapshot → price_snapshot               │
│  4. EastMoneyBoardProvider.fetch_industry_boards()                │
│     → 进程内 TTL 缓存(板块不落 price_snapshot,见五.4)              │
└──────────────────────────────────────────────────────────────────┘
                          │
GET /api/market/overview ─┘
  MarketOverviewService.build_overview(session):
    - price_snapshot 最新指数快照(按配置表 join)
    - 板块榜(读东财缓存; 缓存空则同步触发一次抓取)
    - 量化情绪标签(纯函数, 输入指数快照+VIX+涨跌家数)
    - 新闻情绪(news_item + news_stock_mention + news_analysis_result
               + news_signal_result 当日聚合)
        ↓
前端 WatchlistView 顶部 MarketOverviewPanel
  marketOverviewStore (Pinia) ← apiClient.getMarketOverview()
  60s 定时刷新 + 手动刷新按钮
  配置弹窗 MarketIndexConfigModal ← CRUD /api/market/index-config
```

### 后端分层落点

| 层 | 新增/修改 | 说明 |
|---|---|---|
| models | 新增 `models/market_index_config.py` | 指数配置表 |
| repositories | 新增 `repositories/market_overview_repository.py` | 配置表 CRUD；指数最新快照查询复用 `MarketRepository.list_latest_by_symbols` |
| services | 新增 `services/board_provider.py`（东财板块）、`services/market_sentiment_service.py`（量化+新闻情绪）、`services/market_overview_service.py`（聚合编排） | provider 只联网、service 编排、纯计算函数可单测 |
| workers | 新增 `services/market_overview_producer.py`（BaseWorker 子类）+ `workers/market_overview_producer.py`（独立进程入口，对齐既有模式） | main.py 增加 `build_market_overview_producer` 与 lifespan 启停 |
| api | 修改 `api/routes/market.py` | 新增 overview 聚合端点 + 配置 CRUD 端点 |
| schemas | 修改 `schemas/market.py` | 新增 Overview/IndexConfig 相关 View 模型 |
| core | 修改 `core/config.py` | 新增轮询/缓存/开关配置项 |

## 四、数据模型变更

### 新表 `market_index_config`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | |
| symbol | String(32), not null | Yahoo 原始 ticker，如 `^GSPC`、`000300.SS`、`XLK` |
| market | String(16), not null, index | `us` / `cn` / `kr` / `jp` / `eu` |
| display_name | String(64), not null | 展示名，如"标普500" |
| kind | String(16), not null, default `"index"` | `index`（指数）/ `etf`（板块代理 ETF），区分展示与情绪计算是否计入 |
| sort_order | Integer, not null, default 0 | 同市场内排序 |
| enabled | Boolean, not null, default True | 软开关，删除之外的禁用手段 |
| created_at / updated_at | DateTime(tz) | 复用 `TimestampMixin` |

约束：`UniqueConstraint("symbol", "market", name="uq_market_index_config_symbol_market")`；普通索引 `(market, enabled, sort_order)` 支撑 overview 查询。

### Alembic 迁移要点

- `backend/alembic/versions/` 新增一个 revision（`alembic revision -m "add_market_index_config"`），`upgrade()` 建表 + 索引，`downgrade()` 删表。风格对齐现有版本（如 `d4b7e1f0c3a6_perf_read_path_composite_indexes.py`）。
- 迁移里**不 seed 数据**；默认指数清单由应用层负责：表为空时 `MarketOverviewService` 返回内置默认清单（见下），保证全新部署开箱可用、也避免迁移里硬编码业务数据。

### 内置默认清单（表为空时生效，也可作为"恢复默认"按钮的数据源）

| market | symbol | display_name | kind |
|---|---|---|---|
| us | ^GSPC | 标普500 | index |
| us | ^IXIC | 纳斯达克 | index |
| us | ^VIX | 恐慌指数 | index（仅情绪计算，不单独成行展示） |
| cn | 000300.SS | 沪深300 | index |
| cn | 000001.SS | 上证指数 | index |
| kr | ^KS11 | 韩国KOSPI | index |
| jp | ^N225 | 日经225 | index |
| eu | ^STOXX50E | 欧洲斯托克50 | index |
| eu | ^GDAXI | 德国DAX | index |
| us | XLK / XLE / XLF | 科技/能源/金融 ETF | etf |
| eu | SX5E 相关代理 ETF（如 FEZ） | 欧洲板块代理 | etf |

（`^VIX` 已评审定案入表：作为 us 市场的一条 `kind=index` 配置，代码按 `^VIX` 常量识别其在情绪计算中的特殊角色，不做额外字段；见十三.开放问题定案。）

## 五、东方财富板块数据源接入方案

### 接口

行业板块行情榜（clist）：

```
GET https://push2.eastmoney.com/api/qt/clist/get
    ?pn=1&pz=50&po=1&np=1&fltt=2&invt=2
    &fid=f3                       # 按涨跌幅排序
    &fs=m:90+t:2                  # m:90+t:2 = 行业板块（t:3 为概念板块，本期不接）
    &fields=f12,f14,f2,f3,f104,f105,f106,f62
```

响应 JSON：`data.diff[]` 每项字段含义：

| 字段 | 含义 |
|---|---|
| f12 | 板块代码（如 `BK0420`） |
| f14 | 板块名称（如"航天航空"） |
| f2 | 最新价（板块指数点位） |
| f3 | 涨跌幅（%） |
| f104 / f105 / f106 | 板块内上涨/下跌/平盘家数 |
| f62 | 主力净流入（元，可选展示） |

### 接入形态

- 新文件 `backend/app/services/board_provider.py`：`EastMoneyBoardProvider.fetch_industry_boards(limit=20) -> list[BoardQuote]`，`BoardQuote` 为新 dataclass（code/name/price/change_percent/advance_count/decline_count/flat_count/net_inflow/fetched_at）。
- HTTP 复用 `app.services.http_pool.get_feed_client()`（与腾讯 provider 相同的连接池机制），带 `Referer: https://quote.eastmoney.com/` 头与 5s 超时；响应做防御性解析（`data`/`diff` 缺失、字段类型异常都容忍，对齐 `quote_provider.py` 的 `_coerce_float` 风格）。
- **非官方接口，无 SLA**：字段名可能变化、可能被限流。解析失败视为整体失败，不做部分字段猜测。

### 缓存与失败降级

- **不落 `price_snapshot`**：板块榜单一次 50 条、语义与逐 symbol 报价不同，落库会造成表膨胀且无消费方。选择：进程内 TTL 缓存（模式对齐 `QuoteService._hot_symbols_cache`：模块级缓存 + `threading.Lock` + `cached_at`），TTL 走配置 `market_board_cache_ttl_seconds`（默认 60s）。
- worker 每轮刷新缓存；`GET /api/market/overview` 只读缓存，缓存为空时同步触发一次抓取（对齐 `get_cached_symbol_quote` 的零延迟保底思路）。
- 抓取失败：返回上一份缓存并在 payload 标 `stale: true`；无缓存则板块区返回空列表 + `status: "fetch_failed"`，前端板块区显示"暂不可用"，不影响指数/情绪区。

## 六、新闻情绪按市场聚合方案

### 归属映射（具体实现）

按优先级三级归属，产出 `{market: [news_id, ...]}`：

1. **mention 市场优先**：`news_stock_mention` 按 `news_id` 分组，取该新闻全部 mention 的 `market` 值集合，映射到目标市场（`us→us`、`cn→cn`、`hk→cn`，见下）；若 mention 市场高度集中（≥60% 的 mention 落在同一目标市场），归属该市场。`news_stock_mention.market` 字段已存在且有索引（`ix_news_stock_mention_symbol_news` 覆盖 symbol+news_id，市场聚合需全扫描当日 mention——单用户本地库当日量级可接受，必要时加 `(market)` 已有单列索引）。
2. **`news_item.market` 兜底**：无 mention 或 mention 分散时，用 `news_item.market`（ingestion 源定义自带，`us`/`cn`/`hk` 等）直接映射。
3. **不归属**：两级都得不到目标市场的新闻不进入任何市场的情绪分数（宁可缺数据也不错配）。

市场映射表（代码常量）：

```python
_NEWS_MARKET_MAP = {
    "us": "us",
    "cn": "cn",
    "hk": "cn",   # 港股新闻对 A 股情绪影响强于其它市场，并入 cn
    "kr": "kr",
    "jp": "jp",
    "eu": "eu",
}
```

### 情绪分数计算

- 输入：当日（UTC 自然日切片，`news_item.effective_at` 或 `published_at` 落在当日）归属该市场的新闻。
- 单条新闻分数：优先 `news_item.sentiment_score`（float，管线已产出）；缺失时回退 `news_analysis_result.sentiment` 标签映射（positive→+1 / neutral→0 / negative→-1）。
- 市场当日情绪分数 = 归属新闻分数的简单平均，归一到 [-1, 1]；新闻数 < 3 时返回 `score: null, status: "insufficient_data"`，前端显示"样本不足"。
- 重要信号列表：该市场当日 `news_signal_result` join `news_item`，按 `signal_confidence` 降序取前 5 条，返回 `{news_id, title, summary, signal_confidence, source_name, published_at, canonical_url}`；前端点击跳 `/news/{id}`（NewsDetailView 已存在）或外链原文。

### 局限（必须在文档与 UI 中如实说明）

- **kr/jp/eu 大概率无数据**：现有 ingestion 源（`services/ingestion/sources.py`）基本都是 us/cn/hk 英文/中文源，几乎没有日韩欧本地语新闻源。这三个市场的新闻情绪区常态为"无数据"，属于预期行为，UI 需要优雅降级而不是报错。
- **宏观新闻归属粗糙**：未提及具体股票的宏观新闻（如"美联储加息"）只能靠 `news_item.market`（即来源站归属），英文源全归 us 会高估 us 样本、漏掉对 eu 的影响。本期接受该偏差。
- **hk→cn 合并是近似**：港股与 A 股情绪相关但不等同，属设计取舍。

## 七、量化情绪指标计算规则

纯函数 `compute_market_sentiment(indices: list[IndexQuote], vix: float | None, board_stats: BoardStats | None) -> MarketSentiment`，输入全部为已抓取数据，可脱离网络单测。

每市场产出：`score ∈ [-1, 1]` + `label ∈ {panic, fear, neutral, greed, greed_extreme}`（UI 文案：恐慌/偏慌/中性/贪婪/极度贪婪，可归并展示为三档）+ `inputs`（参与计算的输入摘要，便于调试）。

规则：

1. **指数动量分**（权重 0.6）：市场内 `kind=index`（排除 ^VIX）指数 `change_percent` 的等权平均 `avg_chg`，分段映射：`avg_chg <= -2 → -1`；`-2 ~ -0.5 → -0.5`；`-0.5 ~ +0.5 → 0`；`+0.5 ~ +2 → +0.5`；`>= +2 → +1`，区间内线性插值。
2. **波动率调整**（权重 0.25，仅 us 市场有 ^VIX 时启用；其它市场该项缺省并把权重让渡给指数动量）：`VIX >= 30 → -1`；`20~30 → -0.5`；`13~20 → 0`；`<13 → +0.5`（低波贪婪），线性插值。
3. **涨跌家数调整**（权重 0.15，仅 cn 市场有东财板块数据时启用）：全板块上涨家数占比 `adv_ratio = Σf104 / (Σf104+Σf105+Σf106)`，`adv_ratio >= 0.7 → +0.5`；`<= 0.3 → -0.5`；中间线性插值。
4. 缺数据降级：任一输入缺失则按剩余输入重新归一权重；全部缺失返回 `label: "unknown"`。

标签阈值：`score <= -0.6 → panic`；`-0.6 ~ -0.2 → fear`；`-0.2 ~ +0.2 → neutral`；`+0.2 ~ +0.6 → greed`；`> +0.6 → greed_extreme`。

阈值先作为 `market_sentiment_service.py` 模块常量，不进配置表（单用户本地应用，调参直接改代码 + 单测即可）。

## 八、轮询 worker 设计

### `MarketOverviewProducer`（`services/market_overview_producer.py`）

- 继承 `BaseWorker`，`worker_name = "market_overview_producer"`，心跳/异常记账全部复用基类。
- `do_cycle()`：
  1. 读 `market_index_config`（enabled=1，含 ^VIX）；表为空用内置默认清单。
  2. 构造 `NormalizedSymbol` 列表 → `YahooFinanceQuoteProvider.fetch_quotes_batch`（一次 `yf.download` 批量请求；批量失败的 ticker 由 provider 内部回退逐票并发）。
  3. 网络抓取全部完成后才开写事务，`MarketRepository.save_snapshot` 批量 flush + 单次 commit（对齐 `QuoteService.refresh_watchlist_quotes` 的"先联网后写库"两阶段纪律，不夹带网络调用）。
  4. 调用 `EastMoneyBoardProvider` 刷新板块进程内缓存（失败仅记日志，不影响指数落库）。
- `get_interval()`：盘中 `market_overview_poll_interval_seconds`（默认 60s）；全部相关市场闭市时 `market_overview_idle_poll_interval_seconds`（默认 300s）。
- 不发布 event_bus 事件（前端走定时轮询即可，不需要 SSE 推送；如后续要推再加，避免本次扩 scope）。
- **与 `MarketQuoteProducer` 完全独立**：不共享调用、不改其配置；两者都会写 `price_snapshot` 但 symbol 集合不同（自选股 vs 指数），无冲突。

### 交易时段扩展

`market_hours.py` 新增 `_OVERVIEW_SESSIONS_UTC`（不动现有 `_SESSIONS_UTC`，避免改变自选股 producer 行为）：

- cn/hk/us：复用现有时段。
- kr：09:00-15:30 KST(UTC+9) → 00:00-06:30 UTC。
- jp：09:00-15:00 JST(UTC+9) → 00:00-06:00 UTC（午休粗粒度忽略）。
- eu：09:00-17:30 CET 粗粒度取 07:30-16:30 UTC（覆盖伦敦 08:00-16:30 与法兰克福，DST 取并集思路同美股）。

新增 `any_overview_market_open(now=None)` 供 producer 的 `get_interval()` 使用。

### `core/config.py` 新增配置项

| 配置 | 默认 | 说明 |
|---|---|---|
| `market_overview_producer_enabled` | True | 对齐 `market_quote_producer_enabled` 的单机单进程默认形态 |
| `market_overview_poll_interval_seconds` | 60.0 | 盘中轮询间隔 |
| `market_overview_idle_poll_interval_seconds` | 300.0 | 全市场闭市降频 |
| `market_board_cache_ttl_seconds` | 60 | 东财板块进程内缓存 TTL |
| `market_overview_news_lookback_hours` | 24 | 新闻情绪"当日"窗口（用滚动窗口而非自然日，避免跨时区切割问题） |

### main.py 接线

- 新增 `build_market_overview_producer()`（对齐 `build_market_quote_producer` 形态）。
- lifespan 启动段：`if settings.market_overview_producer_enabled: market_overview_producer = build_market_overview_producer(); market_overview_producer.start()`；关停段对应 `stop()`。
- 新增 `workers/market_overview_producer.py` 独立进程入口（对齐既有 `workers/market_quote_producer.py`，多进程部署场景用）。

## 九、API 契约变更

全部挂在既有 `api/routes/market.py`，自动继承 `verify_app_token`。

### `GET /api/market/overview`

聚合返回，一次请求喂饱整个总览区块：

```json
{
  "generated_at": "2026-08-02T08:00:00Z",
  "markets": [
    {
      "market": "us",
      "display_name": "美股",
      "is_open": true,
      "indices": [
        {
          "symbol": "^GSPC", "display_name": "标普500", "kind": "index",
          "price": 6450.12, "change_percent": 0.82, "previous_close": 6397.6,
          "status": "ok", "fetched_at": "..."
        }
      ],
      "quant_sentiment": {
        "score": 0.45, "label": "greed",
        "inputs": {"avg_change_percent": 0.82, "vix": 14.2, "adv_ratio": null}
      },
      "boards": {
        "status": "ok", "stale": false, "source": "preset_etf",
        "items": [{"code": "XLK", "name": "科技ETF", "change_percent": 1.2}]
      },
      "news_sentiment": {
        "status": "ok", "score": 0.31, "sample_count": 12,
        "top_signals": [
          {"news_id": 123, "title": "...", "summary": "...",
           "signal_confidence": 0.9, "source_name": "...", "published_at": "...",
           "canonical_url": "..."}
        ]
      }
    }
  ]
}
```

- `markets` 固定返回 5 个市场（us/cn/kr/jp/eu），即使某市场无配置指数也返回空 `indices` 骨架，前端无需处理缺 key。
- `boards.source`：`eastmoney`（cn）/ `preset_etf`（us/eu）/ `none`（kr/jp，`items` 为空）。
- 读路径只查库 + 读进程内缓存，不阻塞等待外网（板块缓存为空的零延迟保底抓取除外，带 5s 超时）。

### 指数配置 CRUD（`schemas/market.py` 新增对应 View）

| 端点 | 说明 |
|---|---|
| `GET /api/market/index-config` | 返回全部配置（含 disabled），按 (market, sort_order) 排序 |
| `POST /api/market/index-config` | 新增。body：`{symbol, market, display_name, kind?, sort_order?, enabled?}`；服务端校验 market ∈ {us,cn,kr,jp,eu}、symbol 非空去空白大写、同 (symbol, market) 唯一冲突返回 409 |
| `PATCH /api/market/index-config/{id}` | 更新 display_name / sort_order / enabled / kind；symbol 与 market 不允许改（改了就当删除+新增，语义更清晰） |
| `DELETE /api/market/index-config/{id}` | 物理删除（单用户本地应用，不做回收站） |

**契约兼容性**：全部为新增端点，无既有端点变更。注意 `price_snapshot` 同表混入指数后，`GET /api/market/snapshots` 的返回集会多出指数条目——前端 `marketStore` 目前全量消费该接口用于异常波动卡片，需评估是否按 symbol 白名单过滤或接受展示（倾向：overview 的指数不额外过滤，异常波动提醒把指数大涨大跌也报出来是合理行为；若用户反馈噪音再加 `exclude_kinds` 参数）。

schema 变更后执行契约同步：`python scripts/export_openapi.py` + `npm --prefix frontend run generate:api`。

## 十、前端组件拆分与交互

### 新增文件

- `frontend/src/stores/marketOverviewStore.ts`：overview 数据、loading/error/lastLoadedAt、`loadOverview()`、60s 定时器（对齐 `marketStore` 风格）；配置 CRUD action 也放这里（`loadIndexConfig/saveIndexConfig/deleteIndexConfig`），保存成功后触发一次 `loadOverview()`。
- `frontend/src/components/watchlist/MarketOverviewPanel.vue`：区块容器，横向滚动/网格排列 5 张市场卡片 + 右上角"配置"按钮。
- `frontend/src/components/watchlist/MarketOverviewCard.vue`：单市场卡片——市场名 + 开闭市徽标、指数行列表（名称/点位/涨跌幅红绿色，A 股红涨绿跌、其余绿涨红跌需注意配色约定）、量化情绪标签 chip、新闻情绪分数 + 信号列表（点击 `router.push('/news/{id}')`）、板块区（cn 东财榜 / us/eu ETF 列表 / kr/jp 不渲染）。
- `frontend/src/components/watchlist/MarketIndexConfigModal.vue`：配置弹窗，按市场分组的表格（启用开关、排序、编辑名称、删除）+ 底部新增表单（市场下拉、symbol、名称、kind）；校验失败就地提示，对齐 `WatchlistAddModal.vue` 的交互模式。
- `apiClient` 新增 `getMarketOverview / getMarketIndexConfig / createMarketIndexConfig / updateMarketIndexConfig / deleteMarketIndexConfig`（手写，风格对齐现有方法；overview 配 mock fallback 进 `api/mock`）。

### 集成点

- `WatchlistView.vue` 模板顶部、Tab 切换之上挂 `<MarketOverviewPanel />`；`onMounted` 调 `marketOverviewStore.loadOverview()` 并启动 60s 定时器，`onUnmounted` 清理。
- 不改路由、不改 `AppShell.vue`。

### 配色与文案约定

- 涨跌色：沿用现有 `StockCard.vue` 的配色工具（检查 `utils/format.ts` 的 `formatPercent` 及现有涨跌 class 约定，保持一致）。
- 情绪 chip：panic→红、fear→橙、neutral→灰、greed→浅绿、greed_extreme→深绿；`unknown`/`insufficient_data`→灰色"数据不足"。

## 十一、测试策略

### 后端（pytest，`conda run -n news-caught pytest backend/tests`）

- `test_market_index_config_repository.py`：CRUD、唯一约束、排序。
- `test_board_provider.py`：mock httpx 响应（对齐现有腾讯 provider 测试的 mock 方式）——正常解析、字段缺失容错、HTTP 失败降级、缓存 TTL 与 stale 语义。
- `test_market_sentiment_service.py`：量化情绪纯函数全分支（各阈值边界、VIX 缺失、涨跌家数缺失、全缺）；新闻归属映射（mention 集中/分散、news_item.market 兜底、不归属）与情绪聚合（样本不足、分数平均）。
- `test_market_overview_api.py`：`/api/market/overview` 聚合结构（五市场骨架、无数据市场降级）、配置 CRUD 端点（校验 400/409、PATCH 禁改 symbol）。
- `test_market_overview_producer.py`：worker 周期（mock provider，断言先联网后写库、批量落库、闭市降频 `get_interval`）。
- `test_market_hours.py` 增补：kr/jp/eu 时段与 `any_overview_market_open`。
- 回归：既有 `test_market_*`、`test_quote_*` 全绿（重点确认 `market_hours` 新增内容不影响既有 cn/hk/us 判断）。

### 前端

- `npm --prefix frontend run build` 为最小验证。
- 新增 `marketOverviewStore.test.ts`（加载/错误态/CRUD 后刷新）与 `MarketOverviewCard.test.ts`（情绪 chip 映射、板块区按市场渲染/不渲染、信号点击跳转），对齐现有 store/组件测试风格。

## 十二、分阶段实现建议

1. **Phase 1 — 数据与轮询底座**：`market_index_config` 模型 + Alembic 迁移 + repository + `MarketOverviewProducer` + `market_hours` 扩展 + config 项 + main.py 接线。验收：worker 跑起来，`price_snapshot` 能看到指数快照。
2. **Phase 2 — API**：`GET /api/market/overview`（量化情绪 + 指数）+ 配置 CRUD + openapi 导出/前端类型生成。验收：curl 拿到五市场聚合结构。
3. **Phase 3 — 东财板块 + 新闻情绪**：`board_provider` + 缓存降级 + `market_sentiment_service` 新闻聚合接入 overview payload。
4. **Phase 4 — 前端**：store + 三个组件 + WatchlistView 集成 + apiClient/mock + 配置弹窗。
5. **Phase 5 — 收尾**：单测补齐、change log、README/AGENTS 涉及处同步。

每个 Phase 独立可验证、独立可回滚；Phase 3 的两个子项可并行。

## 十三、风险与开放问题

### 风险

1. **东财是非官方接口**：字段（f12/f14/f3...）可能静默变化、push2 域名可能限流。缓解：防御性解析 + 缓存降级 + stale 标记；接受"板块区偶发不可用"。
2. **Yahoo 对日韩欧指数的延迟与可用性**：yfinance 对 `^KS11`/`^N225`/`^STOXX50E` 的报价通常延迟 15-30 分钟，且偶发限流（429）。缓解：批量 `yf.download` 一次请求取全部 ticker 已把请求数降到最低；payload 有 `status/fetched_at`，前端可展示延迟。
3. **`price_snapshot` 表增长**：指数 ~10 个 symbol × 每分钟一条 ≈ 1.4 万行/天，与现有自选股快照同量级，既有清理机制（data_cleanup）需确认覆盖该表（若现有清理只按 symbol 白名单，需要把指数 symbol 纳入）。
4. **新闻情绪对 kr/jp/eu 常态无数据**：产品层面需接受，UI 优雅降级。

### 开放问题（2026-08-02 评审定案）

1. ~~`^VIX` 是入配置表（用户可删）还是代码常量（永远参与 us 情绪计算）？~~ **已定案**：`^VIX` 作为美股默认配置项入 `market_index_config`（kind=index，随默认清单写入），用户可删可禁用；代码按 `^VIX` 常量识别其在量化情绪计算中的特殊角色（见七.2），不在指数行列表单独展示。
2. ~~美/欧板块 ETF 清单（XLK/XLE/XLF/FEZ...）是入 `market_index_config`（kind=etf，用户可配）还是硬编码预设？~~ **已定案**：入表（kind=etf），与指数统一 CRUD，默认清单随应用层内置（见四.内置默认清单）。
3. ~~指数落入 `price_snapshot` 后 `GET /api/market/snapshots` 与异常波动提醒（`is_abnormal`，±3% 阈值）会把指数算进去，是否接受？~~ **已定案**：接受。指数大涨大跌纳入异常波动提醒视为合理行为，不加过滤参数；现有清理机制（data_cleanup）对 `price_snapshot` 的覆盖在实现 Phase 1 时顺带确认。
4. ~~新闻情绪"当日"窗口用滚动 24h 还是按市场本地时区自然日？~~ **已定案**：滚动 24 小时窗口（`market_overview_news_lookback_hours`，默认 24），不按自然日、不按市场本地时区切割。
