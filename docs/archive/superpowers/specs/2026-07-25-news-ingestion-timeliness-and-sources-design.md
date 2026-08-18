# 新闻抓取时效性修复 + 信息源扩容 设计文档

- 日期：2026-07-25
- 提出人：xiuyang（用户）
- 设计人：Claude

## 1. 背景与问题

用户反馈新闻抓取模块存在两个问题（brainstorming 阶段确认，均成立）：

1. **抓取延迟明显**
2. **信息源覆盖不够**

调查确认根因：`NewsIngestScheduler` 在应用生命周期内是否启动由 `settings.news_scheduler_enabled` 控制（`backend/app/core/config.py:47`），该值默认 `False`，且仓库根目录 `.env` 未显式打开它。日常运行下新闻只在手动执行一次性脚本 `make ingest-news`（`backend/app/workers/news_fetcher.py`）时批量入库一次，之后不会自动持续抓取。本地 `backend/data/logs/backend.log` 中只有反复的进程启动/迁移记录，没有任何一条 fetch/ingest 日志，印证了这一点。

信息源覆盖方面：当前生效的信息源只有 `app/services/ingestion/sources.py::_default_sources()` 里硬编码的 7 个（WSJ、The Verge、36Kr、SEC 新闻稿、财联社电报、MiniMax 新闻、智谱 AI 新闻）。`news_sources_file` 环境变量未配置，`backend/data/news_sources.example.json` 只是模板，未生效。

## 2. 目标与非目标

**目标**
- 让新闻抓取在后端进程运行期间自动持续进行，不依赖手动触发。
- 对市场敏感度更高的"快讯类"源缩短轮询间隔，降低捕获延迟。
- 扩充中文财经快讯与美股新闻通讯社/快讯类信息源，且必须是实测可用、内容与产品"低噪音"定位相符的源。

**非目标**
- 不引入独立守护进程/systemd 之类的部署形态变化（不符合"本地部署简单"的产品非功能需求）。
- 不实现港交所/上市公司 IR 公告抓取、不扩充 X/Twitter 监控账号列表（用户在澄清问题中明确未选择这两个方向，留待后续单独立项）。
- 不改动去重、优先级排序、信号管线等下游逻辑；只在采集层（sources / fetcher / parser / scheduler cadence）内变更。

## 3. 方案设计

### 3.1 常驻抓取开关

- 在仓库根目录 `.env` 新增一行 `NEWS_SCHEDULER_ENABLED=true`。选择根目录 `.env` 而非 `backend/.env`，是因为 `Settings.model_config.env_file=".env"` 在 `dev.sh` 以 `uvicorn ... --app-dir backend` 方式从仓库根目录启动时，相对路径 `.env` 解析到的就是根目录文件——现有 `X_MONITOR_ENABLED=true` 已经是这个模式的先例。
- **不修改** `config.py` 里 `news_scheduler_enabled: bool = False` 这个代码默认值。保留默认关闭，是为了不影响没有配置 `.env`（例如 CI、全新 clone 但未复制本地 `.env`）时的行为，避免测试环境或陌生环境意外发起真实网络抓取。
- 影响文件：`.env`（不进版本库，用户本地环境；如仓库 `.gitignore` 已忽略 `.env` 则无需额外处理，只需告知用户本地生效方式）。

### 3.2 Cadence 调整（时效性分层）

对"快讯/pulse"类信息源收紧轮询间隔，其余维持默认：

| 层级 | cadence_seconds | 适用源 |
|---|---|---|
| 快讯层 | 90~120s | 财联社电报（既有）、MarketWatch MarketPulse（新增）、华尔街见闻 7×24 快讯（新增）|
| 常规层 | 300s（默认不变） | 其余所有源 |

依据：抓取层已实现 ETag/If-Modified-Since 条件请求（`fetcher.py`），未变更的 feed 命中 304 时不计入失败/空批 streak、开销很低，因此收紧快讯类源的 cadence 不会显著增加负载或触发限流风险。

### 3.3 新增信息源

均已用 `curl`（带常规浏览器 UA）实测验证 HTTP 200 + 有效 RSS/JSON 结构，写入 `_default_sources()`（与现有 7 个源保持同一硬编码约定，免配置开箱可用）。

**美股新闻通讯社/快讯（RSS，复用现有 `_parse_rss_or_atom`，无需新解析器）**

| name | url | market/language | 说明 |
|---|---|---|---|
| MarketWatch Top Stories | `http://feeds.marketwatch.com/marketwatch/topstories/` | us/en | 综合财经头条 |
| MarketWatch MarketPulse | `http://feeds.marketwatch.com/marketwatch/marketpulse/` | us/en | 盘中快讯，快讯层 cadence |
| CNBC Finance | `https://www.cnbc.com/id/100003114/device/rss/rss.html` | us/en | 综合财经 |
| Yahoo Finance News | `https://finance.yahoo.com/news/rssindex` | us/en | 综合财经 |
| PR Newswire · Financial Services | `https://www.prnewswire.com/rss/financial-services-latest-news/financial-services-latest-news-list.rss` | us/en | 上市公司新闻稿（已用细分 feed 而非全站 firehose，降噪）|
| GlobeNewswire · Earnings | `https://www.globenewswire.com/RssFeed/subjectcode/9-Earnings%20Releases%20and%20Operating%20Results/feedTitle/GlobeNewswire%20-%20Category%20News` | us/en | 财报发布 |
| Nasdaq Press Releases | `https://www.nasdaq.com/feed/rssoutbound?category=Press-Release` | us/en | 公司新闻稿 |

**中文财经快讯**

| name | url | market/language | parser | 说明 |
|---|---|---|---|---|
| Investing.com 中文资讯 | `https://cn.investing.com/rss/news.rss` | cn/zh | 默认 `rss` | 标准 RSS，零新代码 |
| 华尔街见闻 7×24 快讯 | `https://api-one-wscn.awtmt.com/apiv1/content/lives?channel=global-channel&client=pc&limit=20` | cn/zh | 新增 `wallstreetcn_live_json` | JSON 直播流，快讯层 cadence |

**评估后放弃的候选**（记录以避免后续重复调研）：
- 东方财富快讯 JSON API（`newsapi.eastmoney.com/kuaixun/...`）：接口可用，但抓取样本里混入地质灾害预警等与股票市场无关内容，与产品"低噪音"定位冲突，暂不接入。
- AAStocks、etnet.com.hk、格隆汇、同花顺（10jqka）：所谓 RSS 端点已下线（404/500）或返回的是需要 JS 渲染的完整页面（GBK 编码、纯 HTML 壳），非可直接解析的 feed。
- 华尔街见闻自身 `rss.xml` / `feed.xml` 静态文件已下线（对象存储 404），故改用其站内真实使用的 JSON 直播接口。
- Benzinga：RSS 端点被 Cloudflare 拦截（403），不可用。

### 3.4 新解析器：`wallstreetcn_live_json`

新增文件位置：`backend/app/services/ingestion/parser.py`（追加函数，与现有 `_parse_zhipu_news_inline_json` 同构）。

字段映射（基于实测响应结构 `data.items[]`）：
- `canonical_url` ← `item["uri"]`（如 `https://wallstreetcn.com/livenews/3139744`），经 `_canonicalize_url` 规整。
- `published_at` ← `item["display_time"]`（Unix epoch 秒），用 `datetime.fromtimestamp(value, tz=UTC)` 直接转换（该字段是绝对时间戳，不需要走 `_parse_feed_datetime` 的 market 时区兜底路径）。
- `title` ← 优先取 `item["title"]`；该字段在"快讯"类条目里经常为空字符串（只有正文没有独立标题），此时按项目内既有约定（财联社电报解析同样把正文当标题）改用 `content_text` 清洗后的前缀（约 60 字）作为兜底标题。
- `content_text` ← `item["content_text"]`（`_clean_text` 清洗）；`content_html` ← `item["content"]`。
- 缺少 `id`/`uri`/(`title` 与 `content_text` 都为空) 的条目跳过。
- 遵循 `source.item_limit` 截断条数。

`fetcher.py` 的 parser 分发 `if/elif` 链中新增一支：`elif source.parser == "wallstreetcn_live_json": items = _parse_wallstreetcn_live_json(response.text, source)`。

`SourceDefinition` 沿用 `source_type="html"` + 自定义 `parser` 字符串这一既有模式（和 `zhipu_news_inline_json`、`anchor_list_html` 完全一致），不触碰 `_validate_source_definition`（该函数只对 `source_type == "api"` 强校验 parser 必须是 `the_news_api_json`，`html` 类型没有这个限制）。

### 3.5 错误处理

不新增错误处理机制，完全复用现有分层：
- 网络/HTTP 错误 → `error_kind="http_error"`，调度器指数退避。
- 新解析器内部结构异常（字段缺失、JSON 结构变化）→ 抛出异常，由 `fetcher.py` 现有 try/except 捕获为 `error_kind="parse_error"`，同样进入调度器退避,不影响其他源。
- 空批（`items=[]` 但 HTTP 200）→ 现有 `SOFT_STATUSES` empty-streak 探测逻辑，无需改动。

### 3.6 测试计划

- `backend/tests/test_news_ingestion.py`（已确认这里是 `_parse_zhipu_news_inline_json`/`_parse_anchor_list_html` 等现有 parser 单测的落地文件，新用例按同一约定追加，不新建文件）：
  - `_parse_wallstreetcn_live_json` 正常条目解析（title 非空场景）。
  - `_parse_wallstreetcn_live_json` title 为空、走 content_text 兜底场景。
  - `_parse_wallstreetcn_live_json` epoch 时间正确转换为 UTC。
  - `_parse_wallstreetcn_live_json` 对缺字段的脏数据条目做丢弃而非抛异常导致整批失败。
- `test_news_ingestion.py`：新增/扩展对 `_default_sources()` 的校验型测试，确认新增的 9 个源都能通过 `_validate_source_definition`（type/tier/priority/cadence 均合法），且新增源的 `name` 唯一、不与既有 7 个重名。
- 不新增 scheduler 测试：cadence 分层只是数据取值变化，现有 `test_news_ingest_scheduler.py` 已经覆盖 due/backoff 的通用逻辑，无需为具体数值重复覆盖。
- 验证命令：`conda run -n news-caught pytest backend/tests -q`；手动执行 `make ingest-news` 观察 16 个源的抓取结果（重点看新增源的 `status=ok` 与 `inserted_count`）。

## 4. 影响范围

- `backend/app/services/ingestion/sources.py`：`_default_sources()` 增加 9 条定义。
- `backend/app/services/ingestion/parser.py`：新增 `_parse_wallstreetcn_live_json`。
- `backend/app/services/ingestion/fetcher.py`：parser 分发新增一个 `elif` 分支。
- `backend/tests/`：新增/扩展上述测试。
- `.env`（根目录，本地环境，非代码变更）：新增 `NEWS_SCHEDULER_ENABLED=true`。
- `docs/code-change-log.md`：按 AGENTS.md 要求回填本次变更记录。

## 5. 风险与后续事项

- MarketWatch/CNBC/Yahoo/PR Newswire/GlobeNewswire/Nasdaq 这些公开 RSS 端点长期稳定性未知，后续若某个源持续 `http_error`，调度器退避机制会自动降频，不会拖累其他源；建议后续通过 `/api/health/sources`（如存在）观察一段时间的成功率。
- 华尔街见闻直播接口是站内未公开文档的接口（非官方开放 API），后续该接口 URL 或响应结构如有变化，会导致该源解析失败并被退避，不影响系统其他部分；属于可接受风险，与现状 CLS 电报页面解析同属"未公开接口/页面结构"性质。
- 东方财富、格隆汇、同花顺等中文源本次评估后未接入，留作后续如果需要更大覆盖面时的候选（需要专门解决噪音过滤或 JS 渲染问题）。
