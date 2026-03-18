# 自选股添加时自动关联新闻

## 背景

当前添加自选股（`POST /api/watchlist`）只创建 `WatchlistItem`，不触发新闻关联。`news_stock_mention` 表存在但生产代码从不写入，导致自选股详情页的"关联新闻"区块几乎总是空的。

## 目标

添加自选股时自动搜索并关联最新相关新闻，采用"同步快速 DB 匹配 + 异步外部搜索"策略。

## 设计

### 整体流程

```
POST /api/watchlist
  ├─ 创建 WatchlistItem
  ├─ 【同步】DB 关键词匹配
  │   └─ 用 symbol + display_name 在 news_item.title/summary 中 LIKE 匹配
  │   └─ 命中的写入 news_stock_mention
  ├─ 判断：实际命中的新闻数 < 阈值（默认 3 条）？
  │   └─ 是 → 启动后台线程
  │       ├─ 【可选】LLM 关键词扩展（如果已配置）
  │       ├─ Tavily Search API（如果 key 已配置）
  │       ├─ Google News RSS（免费兜底）
  │       └─ 新结果写入 news_item + news_stock_mention
  └─ 立即返回 WatchlistItemView
```

### 新增组件

#### 1. `TavilySearchClient` (`backend/app/services/tavily_client.py`)

- 调用 `https://api.tavily.com/search`
- 参数：`query`, `search_depth="basic"`, `max_results=5`, `topic="news"`
- 返回结构化结果列表（title, url, content, published_date）
- API key 从 Settings 读取（`tavily_api_key`）

#### 2. `GoogleNewsSearchClient` (`backend/app/services/google_news_search.py`)

- 调用 `https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en`
- 解析 RSS XML，提取 title, link, pubDate
- 无需 API key
- 中文搜索支持 `hl=zh-CN&gl=CN&ceid=CN:zh-Hans`

#### 3. `StockNewsSearchService` (`backend/app/services/stock_news_search.py`)

核心编排服务，职责：

**sync_match_existing(symbol, display_name, market) → int**
- 在 `news_item` 表中用 `symbol` 和 `display_name` 做 LIKE 匹配
- 对匹配到的新闻创建 `news_stock_mention` 记录（如果不存在）
- 返回实际命中的新闻数量

**async_search_external(symbol, display_name, market) → None**
- 构建搜索关键词：默认 `"{display_name} {symbol} stock news"`
- 如果 LLM 已配置，调用 LLM 扩展关键词（生成别名、中文名等）
- 依次尝试 Tavily（如果 key 配置了）→ Google News RSS
- 搜索结果去重后写入 `news_item`，同时创建 `news_stock_mention`

#### 4. 配置扩展 (`backend/app/core/config.py`)

新增字段：
- `tavily_api_key: str | None = None`
- `stock_news_min_count: int = 3`（触发外部搜索的阈值）

### 关键决策

1. **news_stock_mention 写入时机**：DB 匹配在同步阶段立即写入；外部搜索在后台线程中写入（使用独立 session）
2. **去重**：与 `_persist_item` 一致，用 `url_hash` 去重
3. **LLM 降级**：LLM 未配置时直接跳过关键词扩展，用规则关键词搜索
4. **Tavily 降级**：Tavily key 未配置或请求失败时，降级到 Google News RSS
5. **后台线程**：使用 `threading.Thread(daemon=True)` 启动，与请求生命周期解耦

### 不做的事

- 不改变现有 `POST /api/news/refresh` 抓取流程
- 不改变前端页面（前端已有关联新闻展示，数据补齐后自动生效）
- 不做定时批量更新（本轮只在添加时触发）

### 测试策略

- `test_stock_news_search.py`：测试 DB 匹配逻辑、news_stock_mention 创建、外部搜索结果入库
- 用 mock 替代真实 Tavily/Google News 外部请求
