# 全链路性能优化设计（前端 + 后端 + 数据源抓取）

- 日期：2026-07-18
- 状态：已评审
- 依据：2026-07-18 三路只读摸底报告；docs/optimization-plan.md（旧清单状态核实）

## 1. 目标

在个人单用户、本地部署（FastAPI + SQLite WAL + 多后台线程 + Vue3）规模下：

1. 消除确定性浪费：重复 LLM 调用、重复网络下载、每请求全表物化
2. 防数据量增长的必然退化：补齐全表扫描点的索引/聚合
3. 前端 SSE 高频路径减负：去掉双更新路径与深响应遍历

不改 API 契约、不引入新基础设施、不换数据库。

## 2. 关键决策

### 2.1 信号 pipeline 单入口化（最高风险项，先定调）

现状：`signal_status IS NULL` 的 pending 集被三个入口消费——queue_worker（事件+30s 兜底）、scheduler `_drain_signal_backlog`（5s tick）、`refresh_all` 无插入分支。无认领机制 → 同批 id 被重复爬正文+重复 LLM；后两个入口不传 session_factory → 串行 LLM 期间持 SQLite 写锁（旧 #1 未闭环）。

决策：**pending 处理只留 queue_worker 一个入口**；scheduler drain 与 refresh_all else 分支改为仅把 pending id 放进 `analysis_queue`（内存队列已有），queue_worker 30s 兜底轮询保留作为重启自愈。queue_worker 处理前对选中 id 做原子认领（`UPDATE ... SET signal_status='processing' WHERE id IN (...) AND signal_status IS NULL`，只处理认领成功的 id），彻底消除并行重复。

### 2.2 K 线缓存命中即返回

`MarketChartService.get_kline` 现状：缓存只写不读，每次请求真实 yfinance 下载。改为：命中且未过 TTL 直接返回；异常路径仍用 stale 缓存兜底。行为差异：TTL 内行情数据不刷新——TTL（分钟级）本来就是为此设计。

### 2.3 查询层聚合下推

- `/news/runtime`：全表物化 → `MAX(fetched_at) GROUP BY source/market`，返回 schema 不变
- `price_snapshot`：最新价读取改 `MAX(fetched_at)` 回表取行 + `(symbol, fetched_at)` 复合索引；`/market/snapshots` 改每 symbol 最新一条（响应结构不变）
- `/topics`：N+1 → 批量 + count 聚合
- `list_pending_news_ids`：partial index `WHERE signal_status IS NULL`

### 2.4 前端高频路径

- SSE 新闻流：stream 区块信任 store 本地增量（upsert 已有），全量 layout 刷新从 500ms 防抖降为 60s 周期 + 结构性事件（topic.updated）触发
- NewsFeedView：`displayedFeedItems` 深拷贝+deep/sync watch → shallowRef + 引用/长度驱动 + flush post
- 字体：fontsource 全子集（92 文件 1.4MB）→ latin 子集（16 文件）
- markdown 解析按 (id, content) memo；StockSparkline 换 SVG 组件；http 层接通 AbortSignal

### 2.5 抓取链路

- 行情：`yf.Ticker.history(5d)` 单票 → `yf.download` 批量单次；腾讯兜底保留
- feed/X HTTP：新建 client → http_pool 共享 client
- MiniMax 水合：挪出串行落库段 + 失败冷却
- `load_sources()`：加 mtime 进程内缓存（persister 每重复 item 一次磁盘读、scheduler 每 5s 一次的浪费一并消除）
- X：逐账号容错 + 账号间默认小间隔

### 2.6 后端收口（低优先顺手项）

事件扇出批量化、redis publish 熔断、find_topic 批内预载、BaseWorker 心跳节流、分类缓存键改 title+summary、冗余索引清理。旧清单 #12（宽泛 except）维持现状。

## 3. 验证策略

每阶段：pytest backend 全绿 + vitest 全绿 + build 通过；行为变更项先写失败测试（TDD）；索引项 EXPLAIN QUERY PLAN 留证；kline/runtime 改前后计时对比。每阶段回填 docs/code-change-log.md；旧清单 #14 状态回填 docs/optimization-plan.md。
