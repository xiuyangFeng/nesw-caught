# 审计问题修复实施计划（2026-09-28）

> **状态更新（2026-11-01，聚焦改造 P1 之后）**：本文（及配套计划/设计）写于量化台、AI 对话、X 监控下线之前，以下条目已随 P1 失效，执行时跳过：
> - §3.1 ruff 4 个错误：所在的量化测试文件已删除，`ruff check backend` 已通过。
> - §3.3 第 1 项"量化行情库无备份"：`market_data.db` 已下线。
> - §3.8 中量化相关的 N+1（成绩单、`list_runs`、`_volatility_20d`）与 `RadarEvent` / `AiCallAudit` / `DecisionLog` 索引及保留期清理：相关表已删除。
> - §3.9 中 `ChatMessageList` 记忆化、`XMonitorView` 搜索防抖：页面已删除。
> - §3.11 中"README 增补量化台说明"：已不适用。
>
> 仍然有效：§3.2 测试种子污染（当前恰好剩这 7 个失败）、§3.3 第 2、3 项备份保留位、§3.4 FTS 永久降级、§3.5 `/api/market/overview` 缓存击穿、§3.6 `/api/topics` 冷缓存、§3.7 K 线内存缓存、§3.8 腾讯映射/静默失败/线程预算、§3.9 其余前端项、§3.10 api-drift、§3.11 其余卫生项（含 `.gitignore` 加 `node_modules/`）。另：测试未隔离本机 Redis，开发服务器运行时可能干扰 K 线测试（P1 验证中发现）。

设计稿：[../specs/2026-09-28-audit-fixes-design.md](../specs/2026-09-28-audit-fixes-design.md)

环境要点：本机 conda 位于 `/opt/miniconda3`，环境名 `news-caught`（不在默认 PATH，需 `export PATH=/opt/miniconda3/envs/news-caught/bin:$PATH`）；前端需 `export PATH=/opt/homebrew/bin:$PATH`（DSH 自带 node 加载 rollup 原生模块会因签名不匹配失败）。

## 批次 1：P0（CI、测试红、数据安全、FTS）

- [ ] 1.1 `ruff check backend --fix` + 手工处理 F841；验证 `ruff check backend` 无输出。
- [ ] 1.2 先写失败验证：`pytest backend/tests -q` 复现 7 failed（作为基线记录）。
- [ ] 1.3 收紧 `test_market_sentiment_service.py` 的 autouse 清理范围（按本文件自建 `url_hash` 前缀），不再删种子行。
- [ ] 1.4 收紧 `test_signal_backtest.py::_clean()` 的 `PriceSnapshot` 删除范围。
- [ ] 1.5 验证 `pytest backend/tests -q` → 0 failed；且 `test_market_sentiment_service.py test_news.py test_news_analysis.py` 组合全绿。
- [ ] 1.6 FTS：先写失败测试（`AT&T`/`C++`/`10%`/`random-term-1` 之后 `_fts_available is not False`，且 `AT&T` 查询不因语法错误丢结果）。
- [ ] 1.7 FTS：实现 token 转义 + 语法错误不永久 latch + 日志；`reset_fts_availability_cache` 加测试 fixture 调用。
- [ ] 1.8 备份：文件名格式加数据源标识 + prune 精确前缀；新增 market_data.db 备份 worker 并在 lifespan 挂接。
- [ ] 1.9 备份单测：主库 prune 不删测试库备份 / 测试库 prune 不删主库备份 / market 库被备份且遵守保留数。
- [ ] 1.10 批次 1 验证：`pytest backend/tests -q` + `ruff check backend`。

## 批次 2：P1（缓存与查询）

- [ ] 2.1 `/api/market/overview` single-flight（锁内二次检查 TTL，失败者读 stale）。
- [ ] 2.2 单测：N 并发冷缓存只触发 1 次上游 fetcher 调用；既有 stale/fetch_failed 测试仍绿。
- [ ] 2.3 先落 `/api/topics` golden 响应测试（字节级一致）。
- [ ] 2.4 新增窄聚合查询（count + 最新 market），`list_topics` 不再调用 `batch_news_for_topics`。
- [ ] 2.5 验证 golden 一致 + `EXPLAIN QUERY PLAN` 不再物化全表。
- [ ] 2.6 `MarketChartService._cache` 过期清理 + 容量上限；单测断言有界；命中/过期/stale 行为不变。
- [ ] 2.7 批次 2 验证：`pytest backend/tests -q`。

## 批次 3：P2（量化 N+1 / 索引 / 重复实现 / 静默失败 / 预算）

- [ ] 3.1 `get_report_card` 聚合查询（GROUP BY sleeve,state + SQL 时间窗）；`capture_sql` 断言 SELECT 数恒定。
- [ ] 3.2 `list_runs` 批量取 stages（一次 IN）。
- [ ] 3.3 `_volatility_20d` 批量取 bars（一次 IN）。
- [ ] 3.4 量化三列加索引 + Alembic 迁移；`EXPLAIN` 变 SEARCH；`test_migration_parity` 绿。
- [ ] 3.5 `cleanup.py` 增加量化表 retention（settings + 批删）。
- [ ] 3.6 腾讯代码映射 + 成交量比例三合一；优先级/实时性测试 + 表驱动一致性测试。
- [ ] 3.7 两处静默失败补 `logger.warning(exc_info=True)` 并保留降级契约；单测断言 caplog。
- [ ] 3.8 `server_threadpool_size` 与连接池上限对齐 + 修正过期注释。
- [ ] 3.9 批次 3 验证：`pytest backend/tests -q` + `ruff check backend`。

## 批次 4：前端（与批次 1–3 并行，写域仅 frontend/src）

- [ ] 4.1 `ChatMessageList` markdown 按 content 记忆化；流式期间只重解析变化项。
- [ ] 4.2 `KlineDrawingOverlay` 每渲染一次 rect + 一次投影，模板读缓存。
- [ ] 4.3 `watchlistChartStore` 待刷集合替代单 timer（防画线丢失）+ 单测。
- [ ] 4.4 `XMonitorView` q 防抖 + 请求序号/abort；`WatchlistView.performSearch` abort + 序号。
- [ ] 4.5 `WatchlistAddModal`/`MarketIndexConfigModal` 改 `v-if` + Escape 关闭。
- [ ] 4.6 统一 401 诊断（不再只提示「请检查后端服务」）。
- [ ] 4.7 验证：`npm --prefix frontend run test` + `npm --prefix frontend run build`。

## 批次 5：P2-f 与 P3（契约检查、文档、卫生）

- [ ] 5.1 `generate-api.mjs --check` 追加 client 层覆盖断言（6 个未接端点进 allow-list）。
- [ ] 5.2 修 `types/api.ts` 手写 Portfolio 镜像与生成类型的 required/optional 冲突 + `WatchlistView` 空值保护。
- [ ] 5.3 README 增补量化台与备份说明。
- [ ] 5.4 `requirements.txt` 失效注释改指归档路径；`.gitignore` 加 `node_modules/`。
- [ ] 5.5 `test_a_share_search_service.py` 绝对时间阈值改宽松/相对预算。
- [ ] 5.6 验证：`check:api-drift` + `build` + `pytest`。

## 批次 6：收尾

- [ ] 6.1 全量验证：`pytest backend/tests`、`ruff check backend`、`npm run test`、`npm run build`、`npm run check:api-drift`。
- [ ] 6.2 回填 `docs/code-change-log.md`（日期/修改人/范围/内容/影响文件/接口变化/验证/风险）。
- [ ] 6.3 设计与计划文档归档到 `docs/archive/superpowers/`。
