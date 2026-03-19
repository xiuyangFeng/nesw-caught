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

按 `Ctrl+C` 会一起停止两个进程。

## 验证

后端测试：

```bash
conda run -n news-caught pytest backend/tests
```

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

自选股页面已切换为真实行情接口，默认通过 `yfinance` 拉取港股和美股报价，并保留本地快照缓存作为短时兜底。首次更新环境时请确保已安装新增依赖：

```bash
conda env update -f environment.yml --prune
conda activate news-caught
```

可选环境变量：

```bash
MARKET_QUOTE_PROVIDER=yahoo_finance
MARKET_QUOTE_CACHE_TTL_SECONDS=180
```

新增接口与页面：

- `GET /api/market/watchlist`：批量返回自选股价格、涨跌、开盘、昨收、最高、最低、成交量、状态
- `GET /api/market/symbols/{symbol}`：返回单只股票详情行情
- `http://127.0.0.1:5174/watchlist/:symbol`：单股详情页

港股符号目前兼容 `0700.HK` 和 `HK253` 这类输入，后续如需补 A 股或切换付费行情源，可继续在 provider 层扩展。

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

## 变更记录要求

项目根目录下的 [ANGENT.md](/Users/xiuyang/Desktop/news-caught/ANGENT.md) 已生效。

另外，项目已新增 [AGENTS.md](/Users/xiuyang/Desktop/news-caught/AGENTS.md) 作为基于 `obra/superpowers` 的开发流程约束。后续若使用 Codex 协作开发，需要先确保相关 superpowers skills 已安装到 `~/.codex/skills`，并在安装后重启 Codex 使其生效。

从现在开始，任何代码、配置、文档、脚本、接口或测试修改，都必须同步回填到：

- [docs/code-change-log.md](/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md)

如果修改完成但没有更新该记录文件，则该修改视为不完整。
