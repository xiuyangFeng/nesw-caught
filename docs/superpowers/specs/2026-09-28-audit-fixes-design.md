# 审计问题修复设计（2026-09-28）

> **状态更新（2026-11-01，聚焦改造 P1 之后）**：本文（及配套计划/设计）写于量化台、AI 对话、X 监控下线之前，以下条目已随 P1 失效，执行时跳过：
> - §3.1 ruff 4 个错误：所在的量化测试文件已删除，`ruff check backend` 已通过。
> - §3.3 第 1 项"量化行情库无备份"：`market_data.db` 已下线。
> - §3.8 中量化相关的 N+1（成绩单、`list_runs`、`_volatility_20d`）与 `RadarEvent` / `AiCallAudit` / `DecisionLog` 索引及保留期清理：相关表已删除。
> - §3.9 中 `ChatMessageList` 记忆化、`XMonitorView` 搜索防抖：页面已删除。
> - §3.11 中"README 增补量化台说明"：已不适用。
>
> 仍然有效：§3.2 测试种子污染（当前恰好剩这 7 个失败）、§3.3 第 2、3 项备份保留位、§3.4 FTS 永久降级、§3.5 `/api/market/overview` 缓存击穿、§3.6 `/api/topics` 冷缓存、§3.7 K 线内存缓存、§3.8 腾讯映射/静默失败/线程预算、§3.9 其余前端项、§3.10 api-drift、§3.11 其余卫生项（含 `.gitignore` 加 `node_modules/`）。另：测试未隔离本机 Redis，开发服务器运行时可能干扰 K 线测试（P1 验证中发现）。

## 1. 背景与目标

2026-09-28 对仓库做了一次实测审计（后端跑通 `pytest backend/tests` 与 `ruff check backend`，前端跑通 vitest 与生产构建拆包，并对 `backend/data/app.db` 做只读 SQL 与 `EXPLAIN QUERY PLAN` 采样）。本设计覆盖审计确认的问题，目标是把「CI 红灯 / 测试红 / 数据安全 / 静默错误 / 明确的性能与资源浪费」一次性收敛。

**现状事实（实测）**：

- `ruff check backend` 报 4 个错误，而 CI 的 backend job 第一步就是它 → main 上的 CI 是红的。
- 全量后端测试 `7 failed, 1341 passed`；已用二分法定位到单一污染源。
- `market_data.db`（21,730 根日线 / 140 条财务事实 / 725 天交易日历）**没有任何备份**；主库备份保留策略存在前缀碰撞。
- FTS5 `MATCH` 查询语法错误会把 `_fts_available` 永久置为 `False`（实测 `AT&T`、`C++`、`10%`、`AI-chip` 均触发），且 `reset_fts_availability_cache()` 零调用。
- `/api/market/overview` 冷缓存时无 single-flight；`/api/topics` 冷缓存 hydrate 21,236 行只为算 count 与一个 market 字段。

## 2. 非目标

- 不重写 `docs/product-requirements.md` / `technical-architecture.md` / `api-contract.md` 三份第一阶段草稿。
- 不做 `quant_desk_service.py` 的按面拆分（内聚问题，非本次性能/正确性范围，风险大于收益）。
- 不接 6 个前端未使用的后端端点（属产品决策）。
- 不删除 `backend/data/backups/` 中已有的 745MB 历史文件（用户数据，只提供清理方式并修掉再生成的原因）。
- 不改 `/api/news/refresh` 的 `async_mode` 默认值（会改变已文档化的 HTTP 默认行为，属接口契约决策，单列建议不做）。

## 3. 修复项与方案

### 3.1 P0-a ruff / CI 红灯

删除/排序 4 处问题（3 处 `--fix` 可自动修）：`test_backtest_real.py:76` 未使用变量、`test_eastmoney_financials.py:3` 与 `test_phase_b_closure.py:10` 导入排序、`test_phase_b_closure.py:20` 未使用导入。验证：`ruff check backend` 无输出，且 CI 命令逐字一致。

### 3.2 P0-b 测试种子污染（7 个失败）

真因：`conftest.initialized_database` 是 session 级共享库，`initializer.py` 在 `seed_demo_data=True` 时插入两条种子新闻（`Reuters`/`hk` id=1、`Bloomberg`/`us`）；而 `test_market_sentiment_service.py` 的 `autouse` fixture 在**每个测试前**无范围 `delete()` 掉 `news_item`/`news_stock_mention`/`news_analysis_result`，且不恢复，于是后续 `test_news.py`（字母序在后）与 `test_news_analysis.py` 依赖种子的用例全部失败。

方案：把该 fixture 改成**只清理本文件自建的数据**——用本文件生成的 `url_hash` 前缀（沿用 `_url_counter`）逐个删除被测行，不再触碰种子行。同类第二处：`test_signal_backtest.py::_clean()` 无范围删 `PriceSnapshot`，改成只删本文件写入的 symbol 集合（若无法区分则改为按本文件创建时间窗删除并保留种子）。

取舍：不改测试里的 `/api/news/1` 硬编码（种子行 id=1 本身是稳定的，因为 seeds 只在空表时插入）；不动 session 级共享库结构（改动面更大）。

验证：`pytest backend/tests -q` → 0 failed；并要求 `test_market_sentiment_service.py` + `test_news.py` + `test_news_analysis.py` 组合也全绿。

### 3.3 P0-c 备份三处漏洞

1. **量化行情库无备份**：`build_backup_worker` 只认 `settings.database_url`。方案：新增 `build_market_backup_worker`（或让 BackupWorker 支持多源），对 `MARKET_DATABASE_URL` 指向的库用同一套 `sqlite3.Connection.backup()` 在线备份；沿用 `backup_dir` 但在文件名前缀上区分数据源，避免与主库互相挤占保留位。
2. **保留位前缀碰撞**：`_prune_old_backups` 用 `f"{stem}_*.db"`，主库 stem=`app` 时会匹配到测试库备份 `app_test_*.db`。方案：备份文件名改为带来源标识的确定性格式（如 `{stem}__{source}__{timestamp}.db`），prune 用**精确前缀匹配**（含分隔符），使 `app` 不再吞掉 `app_test`。
3. **外来 stem 永不清理**：历史验证跑留下的 `nc_*`/`integ*` 等文件各成一组、永不被 prune。方案：prune 时以「当前数据源自己的精确前缀」为准（配合 §2 不改旧文件），并在文档/README 给出清理命令。

验证：新增单测覆盖「主库 prune 不会删除测试库备份」「测试库 prune 不会删除主库备份」「market 库会被备份且遵守保留数」。

### 3.4 P0-d FTS 永久降级

方案（三层）：
1. **不永久 latch**：区分「语法/查询类错误」与「FTS 表真不可用」。语法类 `OperationalError`（`fts5: syntax error`、`no such column`）只降级本次查询并 `logger.warning(..., exc_info=True)`，不写 `_fts_available = False`；只有确认表缺失/损坏才 latch。
2. **转义用户输入**：把用户查询拆 token，去掉 FTS5 元字符，每个 token 用双引号包成 phrase 再拼（`"at" "t"` 之类），使 `AT&T`、`C++`、`10%`、`AI-chip` 变成合法查询；同时保住「多 token 全包含」的既有语义。
3. **可恢复**：`reset_fts_availability_cache()` 增加测试 fixture 调用点；latch 为 False 时按时间窗口重新探测，而不是永久关闭。

语义兼容：转义后必须保证现有搜索测试（`q=Tencent` 命中、CJK 分词回退 LIKE）不变；FTS 语法错误时仍回退 LIKE。

验证（TDD）：先写失败测试——`q=AT&T`/`q=C++`/`q=10%`/`q=random-term-1` 之后断言 `news_repository._fts_available is not False`，且 `q=AT&T` 不因语法错误丢结果；再实现。

### 3.5 P1-a `/api/market/overview` 缓存击穿

方案：在 `get_cached_industry_boards` 增加 single-flight：独立 `_board_fetch_lock`，进入后在锁内**二次检查 TTL**；拿不到锁的请求若存在（可过期）缓存则直接返回 stale 结果，不发起第二次外呼。保留既有 `stale=True` / `fetch_failed` 语义与 `clear_board_cache()` 行为。

验证：单测用可控 fetcher 计数，N 个并发线程冷缓存只触发 1 次上游调用；`stale` 与失败降级路径的既有测试保持绿。

### 3.6 P1-b `/api/topics` 冷缓存全量 hydrate

方案：为列表路由新增窄查询——
- `SELECT topic_cluster_id, COUNT(*) ... GROUP BY topic_cluster_id` 出 `news_count`；
- 「每个 topic 最新一条新闻的 market」用窗口函数或「按 (topic, published_at desc, fetched_at desc) 取第一条」的窄查询（不能用 `MIN(market)`，语义是「最新一条的 market」）。

`list_topics` 不再调用 `batch_news_for_topics`；feed-layout 侧（有 `TOPIC_CANDIDATE_LIMIT=60` 上限）保持不动。

验证：先落一个 golden 响应测试（同一数据集下 `/api/topics` 字节级一致）再替换实现；`EXPLAIN QUERY PLAN` 不再出现全表 `news_item` 物化。

### 3.7 P1-c K 线内存缓存无上限

`MarketChartService._cache` 是类级 dict，只写不删（过期项仍持有完整 payload JSON）。方案：写入时清理已过期项；再加容量上限（按条目数 LRU 式淘汰），命中路径不变。Redis 路径不受影响。

验证：单测填充超过上限后断言条目数有界；`get_kline` 命中/过期/`allow_stale` 既有行为不变。

### 3.8 P2 量化与行情路径

- **N+1 三处**：`get_report_card` 改 `GROUP BY sleeve,state` 聚合 + SQL 侧时间窗过滤；`list_runs` 改一次 `IN` 批量取 stages；`_volatility_20d` 改一次 `IN` 批量取 bars。验证：`capture_sql()` 断言 SELECT 数恒定（成绩单 2 条），输出视图不变。
- **索引与 retention**：`RadarEvent.created_at`、`AiCallAudit.created_at`、`DecisionLog.action` 加索引 + 一个 Alembic 迁移（主库）；`cleanup.py` 增加 `ai_call_audit`/`radar_event`/`research_snapshot` 保留期清理（复用 `_delete_expired_*` 批删范式与 settings）。验证：`EXPLAIN QUERY PLAN` 变 `SEARCH ... USING INDEX`；迁移可在空库与既有库上 `upgrade head` 且 `test_migration_parity` 绿。
- **腾讯映射三合一**：抽出 `tencent_code_for(...)` 与成交量手数比例常量，`fetch_quote`/`fetch_quotes_batch`/`_to_tencent_kline_symbol` 共用；各调用点保留自己的错误行为（raise / fetch_failed / None）。验证：三处优先级测试 + 表驱动一致性测试。
- **静默失败补日志**：`quote_provider.py:523` 批量解析、`quote_service.py:509` 热股子查询，改为 `logger.warning(..., exc_info=True)` 并把解析错误带进 `message`；保持「逐 symbol 隔离」与「热股失败仍返回可用响应」的既有契约。
- **线程/连接预算**：`server_threadpool_size`(128) 与 `db_pool_size+max_overflow`(50) 对齐（默认降到 ≤50 或显式抬池并注释理由），修正 `config.py:55` 与实际值不符的注释。

### 3.9 前端批次

- `ChatMessageList`：按 `content` 字符串做 markdown 记忆化，打字机期间只重解析变化的那条。
- `KlineDrawingOverlay`：每次渲染只做一次 `getBoundingClientRect()` 与一次锚点投影，模板改读缓存；在 `overlaySize`/`candles`/`drawings` 变化时失效。
- `watchlistChartStore`：待刷 symbol 集合替代单一 timer，避免 150ms 内先后改两只股票导致前一只画线只留内存。
- 搜索取消：`XMonitorView` 的 `q` 加防抖 + 请求序号/abort；`WatchlistView.performSearch` 加 abort + 请求序号，防止旧结果覆盖新结果。
- 弹窗可达性：`WatchlistAddModal` / `MarketIndexConfigModal` 改 `v-if` + Escape 关闭（对齐 `LlmConfigModal` 既有实现）。
- 错误诊断：至少补一个统一 401 处理（提示 App Token 失效），不再把后端 `detail` 丢掉。

验证：`npm --prefix frontend run test`（vitest，用 homebrew node）+ `npm --prefix frontend run build`（含 vue-tsc）。

### 3.10 P2-f api-drift 覆盖不到 client 层

`generate-api.mjs --check` 只比对生成产物。方案：追加「`openapi.json` 里每个 path+method 必须能在 `src/api/client.ts` 找到引用」的断言，未接的 6 个端点进显式 allow-list（附注释说明是待接）。同时修 `types/api.ts` 与生成类型冲突的手写 `Portfolio*` 镜像（`positions` 必需 vs 生成类型可选），并让 `WatchlistView` 依据可选语义做空值保护。

验证：`npm --prefix frontend run check:api-drift`；故意加一个假 path 应使检查失败。

### 3.11 P3 文档与卫生

- README 增补量化台（`/desk` 默认路由、`make quant-backfill`、覆盖率前提、多进程形态）与本次安全/备份说明。
- `requirements.txt` 注释里的 `docs/optimization-plan.md` 改为归档路径。
- `.gitignore` 增加通用 `node_modules/`。
- `test_a_share_search_service.py` 的绝对时间阈值改为相对/宽松预算，消除负载下的 flaky。

## 4. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 改 `/api/topics` 响应语义漂移 | 先落 golden 字节一致测试再替换实现 |
| FTS 转义改变命中集合 | 保留 LIKE 兜底；先写 `Tencent` 命中与 CJK 回退的回归测试 |
| 备份文件名格式变更导致旧文件不被 prune | 只影响新格式；旧文件保留并给出清理命令，不做删除 |
| 迁移在既有库上失败 | 迁移只加索引（additive），跑 `test_migration_parity` 与空库/既有库两条路径 |
| 前端记忆化导致流式内容冻结 | 按 `content` 字符串比较而非对象引用；保留既有测试 |
| 线程池默认值下调可能影响吞吐 | 保持「线程 ≤ 连接」不变式，并在 README/changelog 记录理由 |

## 5. 验证总清单

1. `conda run -n news-caught pytest backend/tests` → 0 failed（当前 7 failed）。
2. `conda run -n news-caught ruff check backend` → 无输出。
3. `npm --prefix frontend run test` → 全绿。
4. `npm --prefix frontend run build` → 通过（含 vue-tsc）。
5. `npm --prefix frontend run check:api-drift` → 通过且能捕获未接端点。
6. `EXPLAIN QUERY PLAN` 对比：量化三表由 SCAN 变 SEARCH；`/api/topics` 不再物化 `news_item` 全表。
7. 回填 `docs/code-change-log.md`；设计与计划归档到 `docs/archive/superpowers/`。
