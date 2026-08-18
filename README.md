# News Caught

后续优化和开发请先读 [docs/current-state.md](/Users/xiuyang/Desktop/news-caught/docs/current-state.md)。已完成的设计、启动期计划和旧优化清单在 `docs/archive/`，只读，不作为当前待办。

本项目包含：

- `backend/`: FastAPI + SQLAlchemy + 高性能并发抓取与行情引擎后端
- `frontend/`: Vue 3 + Vite 前端

### 核心抓取与后端架构特性
- 🚀 **高性能数据抓取引擎**：集成基于 `http_pool` 的全局 Keep-Alive 连接池、`lxml` 高速 DOM 解析引擎及 `apparent_encoding` 智能中文字符集解码（自动处理 GBK/GB2312/UTF-8 异构网页）。
- 🛡️ **高鲁棒性防封与容错**：具有 XML 非法控制字符自动清洗、多源降级兜底（Yahoo/腾讯）、段落密度提取去重及风控防护 User-Agent 策略。
- ⚡ **微秒级内存检索与并发多 Query 搜索**：集成全量 6000+ A 股内存索引服务及 `ThreadPoolExecutor` 并发在线新闻多路检索。
- 💾 **SQLite 批量事务与高并发锁优化**：行情快照批量处理单次 Commit，热股 alert 查询 60s 内存 Cache，消除高并发下的 DB 锁等待。

## 环境准备

推荐直接用根目录的 `environment.yml` 创建 conda 环境：

```bash
cd /Users/xiuyang/Desktop/news-caught
conda env create -f environment.yml
conda activate news-caught
```

如果环境已经存在，更新环境：

```bash
conda env update -f environment.yml --prune
conda activate news-caught
```

然后安装前端 Node 依赖：

```bash
npm --prefix frontend install
```

> Python 依赖以 `requirements.txt` 为唯一数据源（版本已锁定为 `==` 精确值），`environment.yml` 的 `pip` 段通过 `-r requirements.txt` 引用同一份文件。新增/升级 Python 依赖时只改 `requirements.txt` 一处即可，不要在 `environment.yml` 里另建一份依赖列表；改完后执行 `conda env update -f environment.yml --prune` 使其生效。

## 启动项目

启动后端：

```bash
conda run -n news-caught uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

自选股行情 producer 默认随后端进程一起启动（单进程模式，推荐，见下方“自选股真实行情”一节），无需单独拉起 worker。

启动新闻抓取调度 worker（按源 cadence 调度 + 失败指数退避）：

```bash
PYTHONPATH=backend conda run -n news-caught python -m app.workers.news_scheduler
```

也可以设置 `NEWS_SCHEDULER_ENABLED=true` 让调度器随后端进程一起启动（单进程部署推荐，SSE 事件无需 Redis 即可触达前端）。

### 可选：把重活 worker 拆到独立进程（多进程形态）

默认单进程形态下，爬正文 + LLM 评分（`BackgroundQueueWorker` / `TakeawayWorker`）
和 web 请求跑在同一个 Python 进程里，抢同一个 GIL。实测在后台爬取活跃期间，对
`/api/news/runtime` 连续采样 60 秒：

| 形态 | p50 | p95 | max |
|---|---|---|---|
| 进程内（默认） | 3.7ms | **528.6ms** | **735.2ms** |
| 独立进程 | 1.4ms | **2.8ms** | **20.0ms** |

收益几乎全在**尾延迟**——也就是"大多数点击都正常、偶尔卡一下"的那种体感。
对交互体验敏感时可以切到多进程：

```bash
# 一条命令拉起前后端 + 独立 pipeline worker
make dev-split

# 或者手动：web 进程关掉进程内 worker
PIPELINE_WORKERS_ENABLED=false conda run -n news-caught uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
# 另开一个终端跑重活
make pipeline-worker
```

> ⚠️ 两侧必须**互斥**：in-flight 租约是进程内内存、不跨进程。如果 web 进程没设
> `PIPELINE_WORKERS_ENABLED=false`，两个进程会各跑一套 worker，导致同一批新闻被
> **重复爬正文 + 双倍 LLM token**。独立入口启动时会自检并直接拒绝这种误配置
> （确知 web 进程未运行时可用 `--force` 越过）。
>
> 多进程形态下跨进程事件走 Redis stream，**需要 Redis 可用**；即使事件通路中断，
> queue worker 每 30 秒的 DB 兜底扫描仍会兜住，只是时效性下降。

### 性能基准（防回归）

```bash
make bench          # 需要先有一个在跑的后端，详见 backend/scripts/README-bench.md
make bench-save     # 存快照，之后用 --baseline 做回归对比
```

两个已知陷阱脚本里已内置防护，别绕过：**Python 压测客户端会被自身 GIL 卡住**、
把服务端优化整个掩盖掉；**鉴权失败（401）会让"零负载"看起来像"性能很好"**。

启动前端：

```bash
npm --prefix frontend run dev
```

前端开发服务器默认地址是 `http://127.0.0.1:5174`，并将 `/api` 代理到 `http://127.0.0.1:8000`。

## 常用命令

也可以直接使用根目录 `Makefile`：

```bash
make setup
make dev
make backend
make frontend
make test
```

如果你想一次启动前后端开发服务：

```bash
make dev
```

`make dev` 会同时启动：

- 后端 `http://127.0.0.1:8000`（自选股行情 producer 已内置于该进程的 lifespan，随其一起启停）
- 前端 `http://127.0.0.1:5174`

启动前，launcher 会主动终止本机 `8000` 和 `5174` 上现有的监听进程，然后在 backend 的 `GET /api/health` 真正可达后再继续启动其余进程。这样可以避免前端先起来、但后端端口仍不可用时出现整页 `ECONNREFUSED` 和 K 线加载失败。该 launcher 依赖本机提供 `lsof`、`pgrep` 和 `curl`。

按 `Ctrl+C` 会一起停止两个进程。

## 验证

后端测试：

```bash
conda run -n news-caught pytest backend/tests
```

> [!NOTE]
> 单元测试在运行时会自动重定向到专用的临时测试数据库（`backend/data/app_test.db`），并在测试结束后销毁。这可确保单元测试 100% 隔离，完全不会干扰或污染你的本地开发库（`app.db`）。


前端单元测试：

```bash
npm --prefix frontend run test
```

前端构建检查（含 TypeScript 类型检查）：

```bash
npm --prefix frontend run build
```

手动抓取公开新闻源：

```bash
make ingest-news
```

当前内置公开源包括 `WSJ`、`The Verge`、`36Kr`、`SEC Press Releases`、`财联社电报`。如果要补公司 IR 新闻页，可在环境变量 `NEWS_SOURCES_FILE` 指向的 JSON 文件中追加来源配置。

## 自选股真实行情与全量大A股票支持

自选股页面现已收录**全量 6,100+ 只中国 A 股（包含沪深主板、创业板、科创板、北交所）**，确保想添加任意一只 A 股均能瞬间查到并添加。

后端构建了**高性能内存单例索引查找服务**（`a_share_search_service.py`），支持按股票代码（如 `600519`, `000858`）、中文全称/简称（如 `贵州茅台`, `东山精密`）及**拼音首字母**（如 `gzmt`, `wly`, `payh`, `catl`）进行模糊与精确定位。全量模糊匹配单次耗时低于 **0.5 毫秒**（< 1ms）。前端防抖降至 100ms，在 `WatchlistAddModal.vue` 独立上下滑动的子窗口中提供无缝极速响应。

- **新闻即时抓取与强关联**：新增自选或持仓股票时，同步触发极速外部新闻检索（Google News / RSS / Tavily）并持久化绑定，在相关新闻列表中提供按需透明保底抓取，保证新闻更新的实时性与丰富度。
- **K线行情零延迟呈现**：添加新股票后自动预抓取第一笔行情快照；若点进 K 线详情发现快照缺失，系统透明发起实时抓取回填（含 Yahoo / 腾讯双源容灾），价格瞬间精准显示，无需手动点击“更新”。
- **财报日历即时联动与智能超窗口感知**：自选股变更（添加/删除）即时清空后端日历缓存，并在日历页智能识别超出当前窗口的未来财报（如 34 天后的阿里巴巴财报），自动高亮提示并提供一键【切换至未来 60 天/90 天】快速切换。

行情 producer 常驻轮询自选股、写入本地快照，并发布 `market.watchlist_refreshed`；前端接口只读取最近一次已生产的行情结果，不再在 HTTP 请求路径里同步触发刷新。首次更新环境时请确保已安装新增依赖：

```bash
conda env update -f environment.yml --prune
conda activate news-caught
```

**单进程模式（默认，推荐）**：`MARKET_QUOTE_PRODUCER_ENABLED=true`（默认值）时，producer 随后端 `uvicorn` 进程的 lifespan 一起启停，`make dev` / `scripts/dev.sh` 无需再单独拉起 worker 进程。

**多进程模式**：如需把 producer 拆到独立进程跑（例如后端要频繁 `--reload` 而不想打断行情轮询），先把 `MARKET_QUOTE_PRODUCER_ENABLED=false` 关掉进程内 producer（避免双跑重复轮询/重复发布事件），再单独启动：

```bash
PYTHONPATH=backend conda run -n news-caught python -m app.workers.market_quote_producer
```

可选环境变量：

```bash
MARKET_QUOTE_PROVIDER=yahoo_finance
MARKET_QUOTE_CACHE_TTL_SECONDS=180
MARKET_QUOTE_PRODUCER_ENABLED=true
MARKET_QUOTE_POLL_INTERVAL_SECONDS=15
```

新增接口与页面：

- `GET /api/market/watchlist`：批量返回自选股最近一次已生产的价格、涨跌、开盘、昨收、最高、最低、成交量、状态
- `GET /api/market/symbols/{symbol}`：返回单只股票最近一次已生产的详情行情
- `http://127.0.0.1:5174/watchlist/:symbol`：单股详情页

港/A/美股符号兼容规范：支持输入 `600519`、`600519.SH`、`000858.SZ`、`0700.HK`、`AAPL` 等格式。当前 producer 属于后端轮询型实时链路，已全面支持大A股票行情与分析展现。

## Redis 事件层

后端现在支持一个第一阶段的混合事件层：

- 默认 `EVENT_BUS_BACKEND=hybrid`
- 会尝试把增量新闻事件写入 Redis Streams
- Redis 不可用时自动降级回进程内事件总线
- 当前前端仍继续使用 `SSE`，不需要同步改造
- 第二阶段已将 `news.analysis_completed`、`news.signals_processed` 和 `market.watchlist_refreshed` 统一接入同一事件层；其中 `market.watchlist_refreshed` 现由后台行情 producer 主动发布
- 新闻通知批处理、自选股阈值提醒和分析卡片通知现在由本地事件订阅者驱动，而不是在 route 里直接调用

建议先确保本机 Redis 已启动：

```bash
brew services start redis
redis-cli ping
```

可选环境变量：

```bash
EVENT_BUS_BACKEND=hybrid
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_STREAM_NEWS_INGESTED=stream:news:ingested
REDIS_STREAM_NEWS_PROCESSED=stream:news:processed
REDIS_STREAM_MARKET_WATCHLIST=stream:market:watchlist
REDIS_STREAM_MAXLEN=1000
EVENT_BUS_PUBLISH_TIMEOUT_SECONDS=1.0
```

可通过以下接口查看当前事件层状态：

```bash
curl http://127.0.0.1:8000/api/stream/status
```

该接口现在除了事件层状态外，也会返回自选股行情 `market-worker` 的运行状态（单进程模式下即后端进程内的 producer，多进程模式下为独立进程），包括最近 heartbeat、最近成功/失败时间、最近错误和轮询计数，便于确认自选股行情 producer 是否仍在持续生产数据。

当前已经使用的事件名包括：

- `news.created_batch`
- `news.signals_processed`
- `news.analysis_completed`
- `market.watchlist_refreshed`

## X Monitor 增强模块

项目已新增一个可选的 `X Monitor` 模块，用于通过 `twitterapi.io` 拉取关注账号的近期市场相关推文，并提供关键词搜索能力。它是独立增强层，不参与现有 `news` 主采集链路。

1. 在项目根目录 `.env` 中开启模块并配置 API key：

```bash
X_MONITOR_ENABLED=true
TWITTERAPI_IO_API_KEY=your_api_key_here
TWITTERAPI_IO_TIMEOUT_SECONDS=60
X_MONITOR_ACCOUNTS_FILE=/Users/xiuyang/Desktop/news-caught/backend/data/x_monitor_accounts.example.json
```

2. 启动后端和前端后，可使用以下接口或页面：

```bash
curl http://127.0.0.1:8000/api/health/x
curl http://127.0.0.1:8000/api/x/accounts
curl http://127.0.0.1:8000/api/x/posts
curl "http://127.0.0.1:8000/api/x/search?q=NVDA"
curl -X POST http://127.0.0.1:8000/api/x/refresh
```

前端入口：

- `http://127.0.0.1:5174/x-monitor`

账号白名单文件格式参考：

- [backend/data/x_monitor_accounts.example.json](/Users/xiuyang/Desktop/news-caught/backend/data/x_monitor_accounts.example.json)

## 多模型配置管理与流式 AI 对话助手 (Multi-Model Management & AI Chat)

项目已升级大模型（LLM）配置体系，支持多模型配置同时接入与切换，并新增了一个面向终端用户的流式 AI 聊天问答页面。

1. **多模型接入与状态管理**：
   - 数据库与 Repository 层已升级，允许同时存储和配置多套大模型参数（包括 Provider 名称、显示名称、Base URL、Model 名称和 API Key）。
   - 支持设置单个模型为**默认模型**，并在列表上进行“启用/禁用”、“设为默认”、“编辑”和“删除”的精细化状态控制。
   - 配置列表配备状态呼吸指示灯，提升操作过程中的 Terminal 科技感。

2. **流式 AI 对话室 (`ChatView.vue`) 与会话持久化**：
   - **多会话历史管理**：支持左侧历史会话抽屉列表。提供新建对话、重命名会话、一键删除会话功能，对话记录和所选模型均保存在浏览器的 `localStorage` 中，刷新或切页不会丢失历史。
   - **Markdown 渲染与金融数据表格**：内置轻量级、零依赖的高性能 Markdown 渲染，支持粗体、斜体、列表、段落划分、代码块与“一键复制”功能，并专门适配渲染 LLM 输出的金融对比数据表格。
   - **流式输出中止控制 (Abort Stream)**：引入 `AbortController` 绑定流式请求，前端提供“停止生成”按钮。同时后端支持异步捕捉客户端 TCP 断开事件（`request.is_disconnected()`），及时中止上游大模型请求以达到双向省流效果。
   - **快捷追问选项**：提供了预设的金融投资分析快捷追问选项（如“简述股票影响”、“分析潜在风险”等）。

3. **全局高科技质感毛玻璃消息反馈系统 (Toaster)**：
   - 引入全局 Pinia Toast 管理，适配支持 Success、Error、Warning、Info 四种高对比度发光呼吸指示灯 Toast 反馈。
   - 全局界面（如模型测试连接、配置删除等）均已接入，提供一致的高品质操作交互反馈。

3. **新闻上下文融合问答**：
   - 在新闻详情页 (`NewsDetailView.vue`) 添加了紫粉色渐变发光的 **“关于此新闻问 AI”** 按钮。
   - 点击可直达 AI Chat 页面，自动将新闻详情（包含标题、摘要、来源、时间以及爬取到的**文章正文完整内容**）装载为首条 System 上下文。
   - 支持随时在聊天顶部面板中一键清除新闻上下文，随时切换至普通聊天模式。

新增接口：
- `GET /api/llm/config/all`：获取所有已配置的 LLM 配置列表
- `DELETE /api/llm/config/{id}`：删除指定的 LLM 配置
- `POST /api/llm/config/{id}/default`：将指定配置设为系统默认模型
- `POST /api/llm/config/{id}/active`：启用/禁用特定配置
- `POST /api/llm/chat`：异步对话核心端点（支持 `stream=true` 实时流式响应）

## 大仪表盘与新闻可见性增强 (Dashboard View Upgrade)

前端仪表盘（Dashboard）已升级为高表现力、高响应性的中央交互控制台：

- **舆情偏好罗盘 (`SentimentGauge.vue`)**：自绘半圆 SVG 情绪指针罗盘，增加精密仪表盘刻度 Tick 与指针头部科技发光小点，直观反映利好比率。
- **24小时舆情波动趋势 (`SentimentTrendChart.vue`)**：自绘霓虹双色 SVG 折线图与渐变半透明填充面积图，展示过去 24 小时内利好与利空新闻的时间分布和多空力量博弈走势。
- **突发快讯横幅 (`BreakingNewsSpotlight.vue`)**：顶部聚光灯雷达 Banner 升级为多条突发/高价值新闻（`editorial_score >= 8.5`）的淡入淡出自动轮播（鼠标悬停时暂停），并配备多层心跳声纳雷达光晕与左右手动控制键。
- **全局控制联动**：市场范围与舆情过滤按钮能通过 Computed 响应式纯本地（0ms 延迟）联动罗盘角度偏转、趋势图重绘、四个核心大指标、聚合主题及自选股异动列表。
- **突发新闻高显性卡片**：主 News Feed 列表中，凡是 `editorial_score >= 8.5` 的新闻将被标记为特制卡片，配有红/绿流光渐变左侧边框、霓虹背景发光和前置闪烁警报呼吸灯，以在滑动扫描时提供最强的注意力指引。
- **极速阅览抽屉 (`NewsDetailDrawer.vue`)**：右侧滑出的半透明高斯模糊抽屉。点击新闻即可 0ms 展开全文、关联股票及 AI 深度研判（Top Pick首选影响、事件摘要与潜在风险），并在当前过滤集合中支持上一篇/下一篇滑动翻页。

## 自选股重大资讯雷达与 AI 投研复制共享 (Watchlist Radar Alerts & One-Click Copy)

在看盘/投研模块中，提供了更强大的情绪警报和内容分享功能：

1. **自选股重大新闻发光雷达 (Watchlist Radar Alert)**：
   - 当自选股在过去 12 小时内存在重大新闻（判定标准为极端情感 `sentiment_score >= 0.8 / <= -0.8` 或高权重主题 `importance_score >= 8.0`）时，自选股侧栏卡片上会动态呈现闪烁的红色雷达警报灯（支持心跳向外扩散的脉冲声纳动画），强化用户的注意力警示。
   - 后端在 `QuoteSummaryView` 中扩展了 `has_hot_alert` 属性，并在 `QuoteService` 中通过高效的 SQL 联合查询获取该状态，不影响原有数据表结构。

2. **AI 投研研判一键复制与毛玻璃 Toaster 联动**：
   - 个股详情面板的 AI 投研报告生成后，面板正上方新增了 `📋 复制报告` 按钮。
   - 点击可一键提取 Markdown 文本并复制到系统剪贴板，同时联动全局 Toaster 在右上角弹出带微动效的呼吸毛玻璃消息反馈，提升报告转发分享的便利性。

## 大模型故障容灾降级感知与 Token 审计时序看板 (LLM Failover Perception & Token Trend Chart)

在系统管理和大模型（LLM）配置层，实现了高可靠的大模型弹性接管及用量可视化：

1. **LLM 主备故障自愈的前端可视化感知 (Failover Alert)**：
   - **机制**：当默认的“主大模型”发生网络超时、不可达或认证失败等故障时，后端会自动调用备用模型配置进行请求重试。
   - **流式感知**：在 SSE 流式接口 `/api/llm/chat` 中，当触发切换时，后端先下发一帧包含切换源、备选模型及异常原因的 failover 元数据；普通 JSON 接口则在响应 Payload 中附加该元数据。
   - **UI 呈现**：前端捕获到该事件后，右上角会弹出毛玻璃警告 Toast，并且在聊天对话框顶部或 AI 研报板块上方，呈现出带呼吸灯发光动效的橙黄色**“降级接管横幅”**（如：`⚡ 降级接管中：由于默认模型 ... 访问异常，已无缝切换至备选模型 ...`），极大提升了系统异常自愈的透明度与交互体验。

2. **LLM 额度审计控制台 SVG 历史时序消耗看板 (Token Trend Chart)**：
   - **后端统计**：升级了 `GET /api/llm/stats` 接口，数据库 `llm_token_usage` 聚合统计过去 7 天内每天产生的 Token 时序用量。
   - **SVG 自绘看板**：在“模型额度审计控制台”中引入纯前端自绘、高响应的 SVG 折线趋势图。采用暗黑 Terminal 终端风，配备横向网格虚线、霓虹青色发光折线与半透明渐变面积阴影。
   - **微动效交互**：支持在图表上进行鼠标 Hover 交互，拉出十字垂直定位线，并在光标位置浮现显示当天 Prompt / Completion / Total 精细 Token 消耗及日期的毛玻璃 Tooltip，用量走势一目了然。

## 本地与网络安全加固 (Security Hardening)

为了满足密钥绝对本地化且防窃取的高安全标准，项目实施了多维度的安全重构：

1. **临时认证令牌 (App Token) 机制**：
   - 后端启动生命周期（`lifespan`）中在本地安全数据目录 `data/.app_token` 自动产生一个 32 字节的强随机令牌（使用 `secrets` 库并应用 `600` 权限仅限自己读写）。
   - 前端通过 Vite 构建在编译阶段通过 Node.js 读入该 Token，并通过 `define` 机制注入到全局常量 `__APP_TOKEN__`。
   - 前端在入口处对 `window.fetch` 进行全局劫持代理包装，所有发出的 `/api/*` 请求都会自动在 Headers 中携带 `X-App-Token` 认证头。
   - 后端使用 FastAPI 依赖注入拦截并校验该 Token。任何未经授权的外来/恶意网页跨站伪造调用将直接被返回 401 拦截。

2. **本地绑定与接口回环限制**：
   - 修改 `Makefile` 和启动脚本 `scripts/dev.sh`，强制将前端 Vite 和后端 FastAPI 默认绑定的 Host 设为 `127.0.0.1` 本地回路，从网络物理层面屏蔽了来自局域网或外网未授权主机的直接 API 请求与敏感信息抓取。
   - 放行探活接口 `/api/health`。

3. **API 基址被篡改劫持 Key 防御 (Base URL Hijack Defense)**：
   - 升级了 `LLMProviderConfigRepository.upsert_config` 方法的强安全校验。
   - 当大模型配置被修改，且提交的参数中更改了 `base_url` 时，系统强制校验用户必须重新输入明文 API Key，拒绝重用或省略已有的加密 Key（不允许保留带 `*` 掩码星号值）。这杜绝了攻击者试图通过配置注入恶意基址，配合已有 Key 在向新目标地址发包时窃取 Key 的严重漏洞风险。

4. **敏感密钥本地 Fernet 加密存储**：
   - 升级了飞书推送通知模块。将原本明文保存在数据库中的飞书推送 API `app_secret`，重构为大模型 API Key 相同的 Fernet 本地加密机制。
   - 数据库存储一律使用密文，并在服务发送与测试时在内存中实时解密（`config.decrypted_app_secret`）。

5. **本地密钥防泄露静态扫描**：
   - 强化了 `.gitignore` 规则以阻止 `.env` 各种子版本、`.secret_key`、`.app_token` 被无意中提交到 Git 仓库。
   - 新增静态密钥扫描工具 `scripts/check_secrets.py`。可在本地通过 `python scripts/check_secrets.py` 进行一键离线检测以确认没有明文泄漏。

## 新闻抓取效能感知与全交互无缝丝滑度优化 (Smart Ingestion Caching & Ultra-Smooth UX)

为了使项目在数据摄入开销、页面呈现连贯性、流式内容渲染和增量通知交互上实现极致流畅与丝滑感，系统实施了以下深度重构：

1. **HTTP 304 智能缓存感知 (Ingestion Caching)**：
   - 升级 `SourceHealth` 模型和数据底座以记录每个抓取源的 `last_etag` 与 `last_modified` 头。
   - 改造 `fetcher.py`，在发起拉取请求时自动携带 HTTP 缓存校验头。如服务端返回 `304 Not Modified` 则以零数据库及网络解包开销快速返回，极大地缩减后台轮询 IO 并消除了未更新源的计算损耗；仅在 200 响应时解析并同步更新缓存标头。
   - 针对测试沙箱环境的 Mock 请求和模拟响应对象实施了优雅降级（`TypeError` 与 `getattr` 容灾），实现 100% 测试集向后兼容。

2. **异步新闻正文爬虫 (Article Crawler)**：
   - 引入 HTML 文本密度识别算法爬虫 `article_crawler.py`。对摘要源新闻在后台静默异步拉取其链接，提取无杂质的纯净核心正文填入 `ArticleContent`，为后续 AI 会话和投研分析提供完美的本地语料。

3. **1:1 专属呼吸骨架屏与交叉淡入淡出转场**：
   - 新增 `SkeletonFeed.vue` 专属骨架屏，并为 `NewsFeedView.vue`、`DashboardView.vue`、`WatchlistView.vue` 显式分发与其最终渲染卡片高度一致的 `skeletonType`（如新闻卡片、多指标仪表盘和自选股列表卡片样式）。
   - 结合全局 `<transition name="fade-cross">`，使页面加载与真实内容就绪之间实现 300ms 交叉淡入淡出（Cross-fade）转场，杜绝了数据展现时的生硬闪跳。

4. **AI 对话打字机匀速缓动与智能滚动锁定**：
   - 升级 `ChatView.vue`。对大模型 SSE 流式输出进行前端 30ms 分段吐字缓动处理（当缓冲区积压过大时动态调速防延迟），实现流水般打字动效，消除包大小不均引发的卡顿。
   - 监听窗口滚动事件，智能判定用户行为。一旦用户向上拉阅历史记录（距离底部超过 50px），自动释放强制置底锁，并在右下角淡入毛玻璃高斯模糊的“⬇ 回到底部”浮动玻璃按钮，点击或重新触底时重置锁定。

5. **Delta 增量新闻顶部浮条与平滑置入效果**：
   - 在 `NewsFeedView.vue` 引入 `displayedFeedItems` 本地缓冲状态。
   - 在 SSE 监听到 `news.created` 背景新增时，不再强刷引起页面跳动，而是在证据流顶部浮现优雅的高斯模糊 Delta 提示条。用户点击更新时，新资讯通过 `transition-group` 动画平滑展开向下置入，阅读心流不受打扰。

## 后端高并发性能与连接池重构优化 (Performance & Connection Pool Optimization)

为了解决长事务、阻塞 I/O 带来的 SQLite 写锁竞争（如 `database is locked` 报错），以及降低大模型请求频繁握手带来的网络延迟与系统开销，系统完成了以下优化：

1. **数据库复合索引设计**：
   - 在 `NewsItem` 模型上为 `(published_at, id)` 和 `(market, published_at, id)` 建立了两个复合索引，使得游标分页查询能够直接走索引查找，避免了在 SQLite 中进行全表扫描加排序。
   - 迁移脚本在生成时剔除了 SQLite 在 batch schema 修改时冗余检测出的外键操作，保证了迁移的绝对安全可靠。

2. **进程级共享连接池 (httpx.Client Pool)**：
   - 移除 `llm_providers.py` 在进行评分分类和嵌入调用时每次新建和销毁 `httpx.Client` 实例的逻辑。
   - 新增 `http_pool.py` 以实现进程级单例共享的 `httpx.Client` 池，最大空闲连接 20 个，总连接上限 50 个。
   - 将密钥从 Client 初始化默认配置中剥离，改成在每次 `client.post` 时动态传递，确保大模型接口在高并发请求时无需重复进行 TCP 与 TLS 握手，同时保持多模型账户的安全性。
   - 在主程序 `main.py` 的 lifespan 生命钩子退出时，增加自动释放共享 Client 的逻辑。

3. **热路径消除动态 import 依赖**：
   - 清除了 `queue_worker.py` 的 `do_cycle` 中由于导入 `get_notification_service` 产生的对 `app.main` 的动态反向依赖，并移入顶部静态导入。
   - 清除了 `news_signal_pipeline.py` 中 `process_news_ids` 里的局部动态 `import`，进一步减少函数内高频导入开销。

4. **仓库整洁度工程优化**：
   - 移除了根目录和前端目录下无意中被提交的临时测试日志 `test_output.txt`。
   - 升级 `.gitignore` 规则，将 `test_output.txt` 及所有子文件夹内的测试快照输出加入黑名单。

5. **两阶段管线重构 (Two-Phase Pipeline)**：
   - 将 `NewsSignalPipelineService.process_news_ids` 的大事务过程重构为两个阶段。
   - **阶段 1 (正文补全)**：所有网络抓取 I/O 均在主事务外部执行，且抓取后的落库使用独立的、寿命极短的 Session 逐条提交，避免单条抓取失败阻塞整批。
   - **阶段 2 (分类与关联)**：利用已就绪的本地数据，以极快的速度在主事务内完成大模型分类和主题映射，降低 SQLite 写锁被长期占有的几率。

6. **自愈轮询与内存通知相结合的持久化队列 (#6)**：
   - 移除原有纯内存的 `analysis_queue` 丢失隐患。
   - 升级 `BackgroundQueueWorker`，采用“自愈轮询 + 内存通知”双轮驱动机制。在内存任务队列清空或进程重启后，自动通过数据库检索 `signal_status IS NULL` 的 pending 记录进行自愈补偿扫尾。

7. **Token 计量批量缓冲落库 (#4)**：
   - 增加线程安全的 `TokenUsageBuffer` 类，内存聚合多次大模型 token 使用情况。
   - 在正常部署环境下采用 50 条或 10 秒缓冲策略以 `bulk_insert_mappings` 批量写入，大幅降低 SQLite 日志事务写入的并发写放大。
   - 自动感应测试环境并自降阈值为 1，保证原有测试套件 100% 同步执行无破坏。

## 变更记录要求

协作规范见根目录 [AGENTS.md](/Users/xiuyang/Desktop/news-caught/AGENTS.md)。仓库不要求安装 Superpowers 套件；历史上曾因拼写错误存在 `ANGENT.md`，现仅保留指向 `AGENTS.md` 的占位说明。

后续优化和开发请先读 [docs/current-state.md](/Users/xiuyang/Desktop/news-caught/docs/current-state.md)。`docs/archive/` 中的旧计划、优化清单和已完成设计稿都是只读历史，不构成当前待办。

任何代码、配置、文档、脚本、接口或测试修改，都必须同步回填到：

- [docs/code-change-log.md](/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md)

如果修改完成但没有更新该记录文件，则该修改视为不完整。
