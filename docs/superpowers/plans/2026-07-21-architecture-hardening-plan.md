# 架构加固与性能优化计划（2026-07-21）

> 设计来源：2026-07-21 会话的四路架构评估（后端核心/数据管线/前端/工程健康度），用户确认按"单机单进程自用"定位执行。
> 执行方式：subagent-driven，按波次并行派发，波内任务文件范围互不重叠；实现子代理不提交，主控评审通过后按任务显式路径提交。
> 基线：main @ bfc3220，后端 547 tests 通过。

## 全局约束

- 后端测试：`NEWS_CAUGHT_TEST_DB=/tmp/nc_t<N>.db conda run -n news-caught pytest backend/tests -q`（并行任务各用独立 DB 路径）。
- 前端类型检查：`npm --prefix frontend run typecheck`（内含 `-p tsconfig.app.json`）；构建验证 `npm --prefix frontend run build`。
- TDD：先写失败测试再实现；YAGNI，不做任务范围外的顺手改动。
- 实现子代理不得 `git add`/`git commit`，不得修改 `docs/code-change-log.md`（主控统一回填），不得动 `backend/data/app.db`。
- 迁移风格：幂等 raw SQL（参照批次 A 迁移），避免 batch_alter_table 整表重建（历史教训：FTS 触发器曾被连带丢弃）。

## Wave 1（并行 6 任务，纯修 bug）

## Task 1: InMemoryEventBus 线程安全

文件范围：`backend/app/services/event_bus.py`、`backend/tests/test_event_bus.py`

背景：`event_bus.py:44-70` 的 `_handlers` 无锁；SSE 连接在请求线程 subscribe/unsubscribe（append/重建 list），worker 线程同时在 publish 里迭代，跨线程边迭代边改存在竞态（漏发/迭代异常）。

要求：
1. 用一把 `threading.Lock` 保护 `_handlers` 的全部修改（subscribe/unsubscribe）。
2. `publish`（及 `inject_from_remote` 路径）在锁内取 handler 列表快照，锁外调用 handler——不许在持锁状态下调用 handler（防止 handler 内再订阅造成死锁）。
3. `HybridEventBus` 若直接触碰同一结构则一并覆盖；对外 API 与行为语义不变。

测试：新增并发行为测试——多线程 publish 与 subscribe/unsubscribe 交错不抛异常、已订阅者收到事件、unsubscribe 后不再收到。若竞态本身难以稳定复现，以行为契约测试为准，先红后绿。

## Task 2: chat_with_llm 事件循环阻塞修复

文件范围：`backend/app/api/routes/llm.py`、`backend/tests/` 中现有 chat/llm 路由测试文件（先 grep 定位）

背景：`llm.py:196` `async def chat_with_llm` 在事件循环线程里直接做同步 SQLite 读（`llm.py:204,206,218,220` 的 repository 调用）。撞上 SQLite 写锁（busy_timeout 最长 30s）会阻塞整个事件循环上的所有 async 请求与 SSE。`stream.py:108` 已有正确模式（`anyio.to_thread.run_sync`）。

要求：把进入流式响应前的全部同步 DB 读收拢成一个同步辅助函数，用 `anyio.to_thread.run_sync` 一次线程跳转完成，不做多次 to_thread 往返。响应语义（流式/非流式分支、错误码、报文结构）完全不变。

测试：现有 chat 路由测试全绿；补一个行为回归测试覆盖"provider 不存在/news 不存在"等错误分支仍走原错误码。

## Task 3: notification_job.dedupe_key 唯一约束 + 容错入队

文件范围：`backend/app/models/notification_job.py`、`backend/app/repositories/notification_job_repository.py`、`backend/alembic/versions/`（新迁移一个）、`backend/tests/test_notification_dedupe.py`（新）及现有通知测试的必要调整

背景：幂等目前靠"先查后插"（`notification_job_repository.py:63-67`），`dedupe_key` 只有普通索引（`models/notification_job.py:20`），并发入队存在重复窗口。

要求：
1. 新迁移：对非空 `dedupe_key` 建部分唯一索引（`CREATE UNIQUE INDEX IF NOT EXISTS ... WHERE dedupe_key IS NOT NULL`，幂等 raw SQL）。迁移内先清历史重复：同 key 保留 id 最大一条，其余行 `dedupe_key` 置 NULL（保留审计，不删行）。model 上同步声明该索引。
2. repository 入队改为唯一冲突容错：可保留查重快路径，但插入需捕获 `IntegrityError` 并回退为查询返回已存在 job（等价 upsert 语义），调用方无感。

测试：TDD——重复 enqueue 相同 dedupe_key 只产生一行且返回既有 job；构造含重复 key 的库验证迁移可通过且唯一索引生效。

## Task 4: llm_token_usage / llm_classification_cache 保留清理

文件范围：`backend/app/services/cleanup.py`、`backend/app/core/config.py`、cleanup 相关现有测试文件（先 grep 定位）

背景：cleanup 只清 news_item/article_content/price_snapshot 三张表；`llm_token_usage` 每次 LLM 调用一行、`llm_classification_cache` 无过期，两表无界增长，是真正会撑爆 SQLite 文件的来源。

要求：
1. config 新增 `llm_token_usage_retention_days`（默认 90）、`llm_classification_cache_retention_days`（默认 30），命名与现有 retention 字段风格一致。
2. cleanup worker 增加两个分支：token_usage 删前按现有 `_archive_rows` 模式归档 JSONL；classification_cache 直接删（可再生缓存，不归档）。时间列以表实际字段为准（先读 model 确认 created_at/updated_at）。

测试：TDD——过期行被删/归档、未过期行保留、retention=0 或禁用语义与现有表行为一致。

## Task 5: signal_event 死模型清理

文件范围：`backend/app/models/signal_event.py`（删除）、`backend/app/models/__init__.py`、`docs/technical-architecture.md`、`docs/stability-and-evolution.md`

背景：`signal_event` 无迁移建表、initializer 不 import、全仓无引用，但两份架构文档仍把它当通知系统地基（实际走 notification_job），对后续开发（含 AI agent）是直接误导。

要求：
1. 先全仓 grep `signal_event`/`SignalEvent` 复核引用清单；若发现代码引用（模型导出之外），停下报 BLOCKED，不许硬删。
2. 删除模型文件与 `__init__.py` 导出。
3. 两份文档中 signal_event 相关段落改写为 as-built：通知链路基于 `notification_job`（租约+重试+dedupe），原 signal_event 设想标注"未采纳/已移除"。中文、简洁。

测试：全量后端测试通过（验证 metadata/迁移不受影响）。

## Task 6: 前端 mock 出包治理

文件范围：`frontend/src/api/client.ts`、`frontend/src/api/mock/llm.ts`、`frontend/src/api/mock/market.ts`、`frontend/src/api/client.test.ts`（如需）

背景：`client.ts:94,212` 的 `await import('./mock')` 只有运行时 `if (!import.meta.env.DEV) throw` 守卫，Rollup 无法 tree-shake，mock chunk（18KB）已进生产入口（dist/assets/mock-*.js 被 index-*.js 引用）。另有内联 mock 数据绕过 mock 层：`getLlmStats`（`client.ts:176-197`）、`getWatchlistAiInsight`（`client.ts:301-308`）。

要求：
1. 动态 import 改为编译期守卫模式（参照 `sse.ts:26` 的写法），确保生产构建完全去除 mock chunk。
2. 两处内联 mock 数据迁入 `api/mock/llm.ts`、`api/mock/market.ts`，走统一 DEV 回退路径，类型标注用生成类型。
3. DEV 下 mock 回退行为不变。

测试：vitest 相关测试通过；`npm --prefix frontend run typecheck`；`npm --prefix frontend run build` 后验证 `frontend/dist/assets/` 中不再产出 mock chunk（`ls frontend/dist/assets | grep -i mock` 为空），并在报告中附证据。

## Wave 2（并行 3 任务，性能）

## Task 7: LLM 批量 embedding + 统一重试退避

文件范围：`backend/app/services/llm_providers.py`、`backend/app/services/stock_research_synthesis.py`、`backend/app/core/config.py`、对应测试文件（先 grep 定位 test_llm_providers / test_stock_research 类文件）

背景：(a) `stock_research_synthesis.py:266-271` 对每条候选新闻串行发一次 60s 超时的 embedding 调用，是全链路最重的串行外部 IO；(b) `plan_failover`（`llm_providers.py:238-264`）只有"单次换 backup provider"，无同 provider 瞬态重试、无退避、不区分错误类型。

要求：
1. Provider 增加 `embed_texts(texts: list[str]) -> list[list[float]]` 批量方法：单次 `/embeddings` 请求传数组，按 index 对齐返回，token 记账沿用现有 `log_token_usage` 路径。
2. `_rank_news` 改为批量：query + 全部文档合并为 1~2 次请求，删除逐条循环。
3. 重试策略：failover 之前对同 provider 做有限次重试（默认重试 2 次，指数退避 0.5s/1s + jitter），仅对可重试错误（httpx 超时、429、5xx）；除 429 外的 4xx 不重试。流式 chat 仅允许"首字节前"重试，流中断不重试。新增 config：`llm_retry_max_attempts`、`llm_retry_backoff_seconds`（命名对齐现有风格）。既有 failover 语义（重试耗尽后切 backup）保持。
4. 退避 sleep 必须可被测试注入/加速（参数或 monkeypatch 点）。

测试：TDD——mock 传输层断言：批量请求体形状与顺序对齐；429/超时触发重试且次数正确；400 不重试；重试耗尽后走 failover；流式首字节后不重试。

## Task 8: takeaway 并发化 + topic stats 批量化

文件范围：`backend/app/services/news_takeaway.py`、`backend/app/repositories/news_signal_repository.py`、对应测试文件

背景：(a) `news_takeaway.generate_for_ids`（`:61-87`）逐条串行 `analyze_json`（批上限 12，未命中缓存即 12 次串行 LLM）；(b) `refresh_topic_stats`（`news_signal_repository.py:149-172`）每个 touched topic 各发一次 query+join，O(topics) 次查询。

要求：
1. takeaway 参照 `news_signal_pipeline.py:196-204` 的 ThreadPoolExecutor + 每线程独立 session 范式并发（默认 4 并发，模块常量），缓存命中路径、失败跳过语义、结果写回顺序稳定性保持不变；确认 token 记账在并发下安全（token_usage_buffer 是否线程安全，不安全则加锁）。
2. `refresh_topic_stats` 合并为单次（或两次）`IN` 批量聚合查询，结果与逐 topic 版本逐字段等价。

测试：TDD——确定性 mock provider 下并发结果与串行等价；topic stats 新旧实现等价性测试。

## Task 9: HTTP 出口收敛

文件范围：`backend/app/services/http_pool.py`、`backend/app/services/google_news_search.py`、`backend/app/services/feishu_client.py`、`backend/app/services/article_crawler.py`、`backend/app/services/http_client.py`（删除）、相关测试文件调整

背景：至少 5 套 HTTP 出口并存：`http_pool`（正牌共享池）、`http_client.py`（遗留 factory，批次 B 已确认"无生产调用方"）、feishu 自建 client、google_news 每次新建 client、crawler 15s 硬编码超时。

要求：
1. `google_news_search.py:38` 改用 `http_pool` 共享 client（复用 feed client 或新增专用池方法），不再每次新建。
2. `feishu_client.py` 改用 `http_pool` 共享 client，保留 10s 超时（httpx 每请求 timeout 覆盖）与 token 刷新/重试逻辑不变。
3. `article_crawler.py:9` 的 15s 硬编码改为模块级常量（默认仍 15s；本任务不动 config.py——Task 7 占用）。
4. 全仓 grep 确认 `http_client.py`/`HttpClientFactory` 无生产引用后删除该文件及其专属测试；若发现引用，改造调用方；改不动则 BLOCKED。

测试：相关服务测试全绿（网络层 mock 调整随迁）。

## Wave 3a（并行 2 任务，架构）

## Task 10: market producer 纳入 lifespan + 告警 handler 注册

文件范围：`backend/app/main.py`、`backend/app/core/config.py`（如需调整注释/默认值）、`backend/app/workers/market_quote_producer.py`、`scripts/dev.sh`、`README.md`、lifespan 相关测试文件

背景：`market_quote_producer_enabled`（`config.py:49`）是 dead config——全仓从不读取；producer 只能独立进程跑；`register_market_watchlist_handlers` 只在独立进程入口注册（`workers/market_quote_producer.py:10`），uvicorn 内自选股价格告警整条链路不工作。项目定位单机单进程自用。

要求：
1. lifespan 内 `if settings.market_quote_producer_enabled:` 启动 MarketQuoteProducer（参照 news_scheduler 的条件启动写法），并注册 `register_market_watchlist_handlers`；退出时 stop。
2. 独立进程入口保留；`scripts/dev.sh` 不再单独拉起 market worker 进程（后端进程已内置），相应探活/清理逻辑同步调整。
3. README 更新启动说明：单进程模式（默认，推荐）与多进程模式（需 `MARKET_QUOTE_PRODUCER_ENABLED=false` 关掉进程内 producer 以免双跑）。

测试：TDD——开关开/关下 lifespan 是否启动 producer 与注册 handler（monkeypatch start）；全量回归。

## Task 11: CI 强化——迁移一致性 + 依赖对齐 + 密钥扫描

文件范围：`.github/workflows/ci.yml`、`backend/tests/test_migration_parity.py`（新）

背景：(a) 测试与全新库都走 `create_all + stamp head`（`db/initializer.py:85-105`），13 个迁移的 upgrade 路径从不在 CI 执行，ORM metadata 与迁移链漂移只会在存量库升级时爆炸；(b) CI 用 `pip install -e ./backend[dev]`（pyproject floor 版本），本地用 requirements.txt 精确版本，两边跑的不是同一套依赖；(c) `scripts/check_secrets.py` 写好了但没接进 CI。

要求：
1. 新增 `test_migration_parity.py`：临时空库跑 `alembic upgrade head`，与 `Base.metadata.create_all` 的结果用 SQLAlchemy inspector 对比（表集合、每表列名集合、索引名集合），差异即 fail，输出可读 diff。该测试进常规 pytest（本地+CI 都跑）。
2. `ci.yml` backend job 改为从 `requirements.txt` 精确安装（保持 `-e ./backend` 可导入，但依赖版本以 requirements.txt 为准），确保 CI 与本地同版本。
3. `ci.yml` 增加 `python scripts/check_secrets.py` 步骤。

测试：本地跑新迁移测试通过；`python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` 校验语法。

## Wave 3b（单任务，在 3a 合入后执行）

## Task 12: 日志升级（文件轮转 + 可选结构化）

文件范围：`backend/app/core/logging.py`、`backend/app/core/config.py`、`backend/tests/test_logging_setup.py`（新）

背景：`core/logging.py` 仅 8 行 `basicConfig`，控制台输出、无文件、无轮转。多后台线程共写 SQLite 的系统出了 `database is locked` 类问题基本无法事后定位。

要求：
1. `configure_logging` 升级：保留控制台 handler；新增 `RotatingFileHandler`（默认 `data/logs/backend.log`，10MB × 5 份，目录自动创建；`data/` 已被 gitignore 覆盖）。
2. 新配置：`log_file_enabled`（默认 True）、`log_file_path`、`log_file_max_bytes`、`log_file_backup_count`、`log_format`（`plain|json`，默认 plain；json 为单行 JSON：ts/level/logger/message）。
3. 幂等：重复调用不叠加 handler（uvicorn --reload 场景）。

测试：TDD——临时目录验证文件生成、轮转配置生效、json 格式字段、重复调用幂等。

## 验收与收尾

- 每波：任务评审（spec + 质量）通过 → 主控按任务显式路径提交 → 回填 code-change-log → 全量回归（后端 pytest 全量 + 前端 typecheck/build，视触及面）。
- 全部完成后：整分支终审（Sonnet），处理发现项，更新进度台账。
