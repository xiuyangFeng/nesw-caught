# News Caught

本项目包含：

- `backend/`: FastAPI + SQLAlchemy 后端
- `frontend/`: Vue 3 + Vite 前端

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

## 启动项目

启动后端：

```bash
conda run -n news-caught uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
```

启动自选股行情 worker：

```bash
PYTHONPATH=backend conda run -n news-caught python -m app.workers.market_quote_producer
```

启动新闻抓取调度 worker（按源 cadence 调度 + 失败指数退避）：

```bash
PYTHONPATH=backend conda run -n news-caught python -m app.workers.news_scheduler
```

也可以设置 `NEWS_SCHEDULER_ENABLED=true` 让调度器随后端进程一起启动（单进程部署推荐，SSE 事件无需 Redis 即可触达前端）。

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

- 后端 `http://127.0.0.1:8000`
- 前端 `http://127.0.0.1:5174`
- 自选股行情 `market-worker`

启动前，launcher 会主动终止本机 `8000` 和 `5174` 上现有的监听进程，然后在 backend 的 `GET /api/stream/status` 真正可达后再继续启动其余进程。这样可以避免前端先起来、但后端端口仍不可用时出现整页 `ECONNREFUSED` 和 K 线加载失败。该 launcher 依赖本机提供 `lsof`、`pgrep` 和 `curl`。

按 `Ctrl+C` 会一起停止三个进程。

## 验证

后端测试：

```bash
conda run -n news-caught pytest backend/tests
```

> [!NOTE]
> 单元测试在运行时会自动重定向到专用的临时测试数据库（`backend/data/app_test.db`），并在测试结束后销毁。这可确保单元测试 100% 隔离，完全不会干扰或污染你的本地开发库（`app.db`）。


前端构建检查：

```bash
npm --prefix frontend run build
```

手动抓取公开新闻源：

```bash
make ingest-news
```

当前内置公开源包括 `WSJ`、`The Verge`、`36Kr`、`SEC Press Releases`、`财联社电报`。如果要补公司 IR 新闻页，可在环境变量 `NEWS_SOURCES_FILE` 指向的 JSON 文件中追加来源配置。

## 自选股真实行情

自选股页面已切换为真实行情接口，支持批量与容灾拉取。默认通过 `yfinance` 批量并发拉取港股、美股和A股报价。同时，为了提高可用性并抗限流，本模块实现了国内备用行情源：当港股/A股在 `yfinance` 批量拉取失败或超时被限流时，会自动透明地降级，无缝切换至国内腾讯财经的轻量行情接口。

当前行情 producer 已从 Web 应用进程中拆出，需通过独立 worker 常驻轮询自选股、写入本地快照，并发布 `market.watchlist_refreshed`；前端接口只读取最近一次已生产的行情结果，不再在 HTTP 请求路径里同步触发刷新。首次更新环境时请确保已安装新增依赖：

```bash
conda env update -f environment.yml --prune
conda activate news-caught
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

港股符号目前兼容 `0700.HK` 和 `HK253` 这类输入。当前 producer 仍属于后端轮询型实时链路，后续如需补 A 股或切换真正流式/付费行情源，可继续在独立 worker 的 producer/provider 层扩展，而无需改动现有 watchlist API 或通知事件名。

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

该接口现在除了事件层状态外，也会返回独立 `market-worker` 的运行状态，包括最近 heartbeat、最近成功/失败时间、最近错误和轮询计数，便于确认自选股行情 worker 是否仍在持续生产数据。

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

2. **流式 AI 对话室 (`ChatView.vue`)**：
   - 提供了基于 Markdown 的精美聊天对话气泡，支持打字机样式的流式 SSE 渲染（基于 `fetch` + `ReadableStream` 接收）。
   - 支持选择不同的活动模型进行对话。
   - 提供了预设的金融投资分析快捷追问选项（如“简述股票影响”、“分析潜在风险”等）。

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

## 变更记录要求

项目根目录下的 [ANGENT.md](/Users/xiuyang/Desktop/news-caught/ANGENT.md) 已生效。

另外，项目已新增 [AGENTS.md](/Users/xiuyang/Desktop/news-caught/AGENTS.md) 作为基于 `obra/superpowers` 的开发流程约束。后续若使用 Codex 协作开发，需要先确保相关 superpowers skills 已安装到 `~/.codex/skills`，并在安装后重启 Codex 使其生效。

从现在开始，任何代码、配置、文档、脚本、接口或测试修改，都必须同步回填到：

- [docs/code-change-log.md](/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md)

如果修改完成但没有更新该记录文件，则该修改视为不完整。
