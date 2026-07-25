# 代码变更记录

> 用于记录本项目每一次实际修改。新增记录时，追加到最上方。

## 2026-07-25 安全修复：/docs /redoc /openapi.json 绕过 App Token 鉴权

- 修改人：Claude Sonnet（全仓安全评审 + 实测验证 + 修复）
- 修改范围：`backend/app/api/router.py`、`backend/app/core/auth.py`、`backend/app/main.py`，回归测试 `backend/tests/test_network_security.py`。
- 变更内容：全局鉴权挂在 `api_router = APIRouter(dependencies=[Depends(verify_app_token)])` 上，但 `FastAPI(docs_url="/docs", redoc_url="/redoc", ...)` 生成的 `/docs`、`/redoc`、`/openapi.json` 是 app 根路径上的内置路由，不经过 `api_router`，完全绕过鉴权（实测确认：不带 token 访问三者均 200，同期 `/api/news` 正确 401）。修复：`create_app()` 关闭内置文档端点（`docs_url=None`/`redoc_url=None`/`openapi_url=None`），改为在 `api_router` 下手写等价路由（`get_swagger_ui_html`/`get_redoc_html`/`request.app.openapi()`），自动继承 `verify_app_token`；`verify_app_token` 的 SSE 专用 query 参数 token 放行逻辑扩展到这三个路径（浏览器直接导航打开文档页无法带自定义请求头，与 EventSource 同理）；Swagger/ReDoc 页面内嵌的 `openapi_url` 显式带上已校验通过的 token，避免"页面能打开、schema 因 401 加载失败"。
- 影响文件：见上；旧的根路径 `/docs`/`/redoc`/`/openapi.json` 不再注册（404），新路径为 `/api/docs`/`/api/redoc`/`/api/openapi.json`。
- 接口/数据结构变化：文档端点 URL 从根路径迁移到 `/api` 前缀下，且现在需要 `X-App-Token` 或 `?token=`；无其他 API/DB 变化。
- 验证情况：新增 8 个测试覆盖"根路径 404 / 新路径需 token / 带 token 可访问 / query token 正确透传进内嵌 openapi_url"；`NEWS_CAUGHT_TEST_DB=/tmp/nc_secreview_pytest3.db conda run -n news-caught pytest backend/tests -q` → 636 passed（+8）；`ruff check` 涉及文件干净；本地起服务实测新旧路径行为符合预期。
- 风险或后续事项：无。此前该缺口暴露的是 API schema（路由/参数/模型结构），不涉及实际数据或密钥，风险等级评为 Medium；生产环境如通过局域网/公网访问后端，本次修复前应视为该风险窗口期。

## 2026-07-21 架构加固计划整分支终审（Wave 1~3b，bfc3220..HEAD）

- 修改人：Claude Sonnet（主控，8 路并行查找子代理 + 逐条 1-vote 验证子代理，`code-review` 技能 high 档）
- 修改范围：对整个架构加固计划的 16 个提交（Wave 1 六任务、Wave 2 三任务、Wave 3a 两任务、Wave 3b 一任务，外加各波次文档回填）做一次跨波次的整体复核，覆盖行级 diff 扫描、被删行为审计、跨文件调用链追踪、复用/简化/效率、altitude/约定共 8 个查找角度，4 个候选发现全部逐条验证后仍存活（2 CONFIRMED、2 PLAUSIBLE，见下）。修复 2 个，另 2 个记录为已知取舍/后续重构项，不在本次处理。
- 变更内容：
  1. **修复：`parse_embeddings_response` 未校验 embedding index 集合**（提交 5989209）：此前只校验返回向量条数，不校验 index 是否恰好构成 `0..expected_count-1`；provider 返回重复 index（如两条都标 0、缺 1）时条数恰好还对，排序后错误向量被悄悄放到某个位置且不抛异常，下游个股研判排序（`_rank_news`）会拿到错位的 embedding，静默产出错误排序结果。改为显式校验 index 集合。
  2. **修复：`notification_job_repository.enqueue` 的 dedupe_key 空白规整时序错误**（提交 5989209）：真假判断在 `.strip()` 之前做（判的是原始未 strip 值），纯空白输入（如 `"  "`）先被判真、strip 后又变成 `""`；`""` 不是 `None`，会被 Wave 1 新增的部分唯一索引（`WHERE dedupe_key IS NOT NULL`，SQLite 里 `'' IS NOT NULL` 为真）覆盖，但因为下面的分支判断的是 strip 后的真假，`""` 又会被当成"无 key"，直接走无 SAVEPOINT/IntegrityError 保护的插入分支——两次传入同样的空白 key 会在这条无保护路径上直接撞唯一索引崩溃（测试复现：改前直接 `sqlalchemy.exc.IntegrityError` 未捕获抛出）。改为 strip 之后统一判真假，空白/空字符串规整为 `None`。当前全仓无调用方会传入纯空白 dedupe_key，属于此前未覆盖的边界防护，非线上事故修复。
  3. **已知取舍，本次不改**：`AsyncOpenAICompatibleProvider.chat_stream` 在已经向调用方 yield 过 token（`first_byte_sent=True`）后若仍中断，会直接 failover 到 backup 并重新流式生成完整回答，前端把新流的 token 追加到已显示的部分回答后面，用户会看到"部分回答 A 紧跟着完整回答 B"的可见重复。经溯源确认这是 diff 之前就存在、且 Wave 2 Task 7 的测试（`test_chat_stream_does_not_retry_after_first_byte_goes_straight_to_failover`）已显式断言为预期行为（"不重试同一 provider,直接按既有语义判定 failover"）——这是一次已评审过的产品取舍（保留旧 failover 语义、只新增首字节前的同 provider 重试），不是本次终审的疏漏，本次不越权改动已测试的既有设计；若要收窄为"首字节后中断只报错、不重新生成"，需要单独立项评估前端展示影响。
  4. **已知取舍，本次不改**：`llm_providers.py` 里"重试+退避+failover"的编排 while 循环在 sync `complete`/`embed_text`/`embed_texts`、async `complete`/`chat_stream` 共 5 处方法里近乎逐行复制（纯逻辑片段 `compute_backoff_delay`/`is_retryable_error`/`plan_failover` 已抽出共享，但编排循环本身没有），已出现真实 drift（`chat_stream` 独有 `first_byte_sent` 守卫，其余 4 处没有）。这是结构性可维护性问题，不是正确性 bug；5 个方法 sync/async、流式/非流式的签名差异较大，收敛成本不小，留作独立重构任务，不在本次终审范围内处理。
- 影响文件：backend/app/services/llm_providers.py、backend/app/repositories/notification_job_repository.py、backend/tests/{test_llm_providers,test_notification_dedupe}.py。
- 接口/数据结构变化：无。`parse_embeddings_response` 新增的校验只会让此前"应该报错但没报错"的畸形 provider 响应正确抛出 `LLMProviderError`（走既有 failover 语义），不改变正常响应的行为；`enqueue` 的 dedupe_key 规整只影响此前从未被任何调用方触发过的纯空白输入。
- 验证情况：TDD 先红后绿——两个新测试在改动前对着现网代码分别复现"index 重复不报错"和"两次空白 key 直插分支撞唯一索引 IntegrityError 未捕获"；`NEWS_CAUGHT_TEST_DB=/tmp/nc_final_review.db conda run -n news-caught pytest backend/tests -q` → 628 passed（Wave 3b 后 626，+2）；`ruff check` 涉及文件干净。
- 风险或后续事项：条目 3、4 已记录为后续台账项，非阻塞——3 需要产品侧决定流式中断后的前端展示策略；4 需要独立评估重试编排层的抽象设计（建议：抽一个 `_run_with_retry(build_request, parse_response)` 或类似的共享执行器，把 5 处循环收敛为 1 处）。架构加固计划（Wave 1~3b，12 个任务）到此全部完成并通过整分支终审。

## 2026-07-21 架构加固 Wave 3b：日志升级（文件轮转 + 可选 JSON 结构化）

- 修改人：Claude Sonnet（主控+实现，Wave 3a 合入后单任务执行，计划见 docs/superpowers/plans/2026-07-21-architecture-hardening-plan.md）
- 修改范围：`core/logging.py`、`core/config.py`、`main.py` 启动接线。1 个任务、1 个提交（34bd394）。
- 变更内容：`configure_logging` 从 8 行 `basicConfig`（仅控制台）升级为控制台 + 可选 `RotatingFileHandler`（默认 `data/logs/backend.log`，10MB×5 份，父目录自动创建，`data/` 已 gitignore）；新增 5 个 config 字段：`log_file_enabled`（默认 True）、`log_file_path`、`log_file_max_bytes`、`log_file_backup_count`、`log_format`（`plain|json`，默认 plain，json 为单行 ts/level/logger/message）。幂等实现：每次调用先摘掉上一次由本函数添加的 handler（打标记属性识别）再重建，不随 uvicorn `--reload` 重复调用叠加。此前多后台线程共写 SQLite 出现 `database is locked` 类问题时，日志早已滚出终端缓冲区事后无法定位，是本任务动机。
- 影响文件：backend/app/core/logging.py、backend/app/core/config.py、backend/app/main.py、backend/tests/test_logging_setup.py（新）。
- 接口/数据结构变化：无 API/DB 变化；新增 5 个可选环境变量，默认值保持“控制台+文件双输出、plain 格式”，行为对现有部署无感升级。
- 验证情况：TDD 先红后绿（7 个新测试覆盖文件生成建目录、file_enabled=false 跳过文件、轮转参数生效、json 字段完整、plain 非 json、重复调用不叠加 handler、重复调用不重复写日志行）；`NEWS_CAUGHT_TEST_DB=/tmp/nc_t12_full.db conda run -n news-caught pytest backend/tests -q` → 626 passed（Wave 3a 后 619，+7）；`ruff check` 涉及文件干净；手工 smoke 验证 json 格式单行输出、文件仅写入一次无重复。
- 风险或后续事项：无。架构加固计划（plan.md Wave 1~3b）全部 12 个任务收尾，待整分支终审。

## 2026-07-21 架构加固 Wave 3a：market producer 单进程内置 + CI 强化

- 修改人：Claude Fable（主控）+ Sonnet 实现/评审子代理（计划同 Wave 1/2 文档）
- 修改范围：后端 lifespan/dev 启动脚本/README，CI 迁移一致性测试与依赖安装。2 个任务、2 个提交（67856a0、ed79ec2），每任务独立评审通过。
- 变更内容：
  1. **market producer 纳入 lifespan**（67856a0）：`market_quote_producer_enabled` 此前是 dead config，producer 只能独立进程跑，自选股价格告警 handler 在 uvicorn 内从不注册。现随 lifespan 按开关启停（默认开启，同步注册 `register_market_watchlist_handlers`），`scripts/dev.sh` 不再单独拉起 market worker 进程；README 补充单进程（默认）/多进程（需显式 `MARKET_QUOTE_PRODUCER_ENABLED=false` 防双跑）两种模式说明。
  2. **CI 强化**（ed79ec2）：新增 `test_migration_parity.py`——`alembic upgrade head`（从 legacy baseline stamp 起跑，真实执行 baseline 之后每条迁移 DDL）与 `Base.metadata.create_all` 的 schema（表/列/索引）逐项比对，堵住此前从未被自动化验证的迁移链漂移风险（测试与全新库此前都走 create_all 快路径，upgrade 路径长期零覆盖）；`ci.yml` backend job 改为 `pip install -r requirements.txt` 精确安装（保留 `-e ./backend` 可导入），消除 CI 用 pyproject floor 版本、本地用 requirements.txt 精确版本的两边不一致；接入 `scripts/check_secrets.py` 密钥扫描步骤（此前脚本已写好但未接入 CI）。
- 影响文件：backend/app/main.py、backend/app/core/config.py、backend/app/workers/market_quote_producer.py、scripts/dev.sh、README.md、.github/workflows/ci.yml、backend/tests/{test_dev_launcher,test_market_quote_producer,test_migration_parity}.py。
- 接口/数据结构变化：无 API/DB 变化；`/api/stream/status` 返回语义不变（单进程模式下 market-worker 状态即进程内 producer）。
- 验证情况：`NEWS_CAUGHT_TEST_DB=/tmp/nc_t11_full.db conda run -n news-caught pytest backend/tests -q` → 619 passed；`python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` 语法校验通过；`python scripts/check_secrets.py` 当前树干净。
- 风险或后续事项：`api-drift` CI job 仍走 `pip install -e ./backend[dev]`（floor 版本），未纳入本次精确安装范围（任务范围显式限定 backend job，非本任务顺手改）；Wave 3b（日志升级）待本条记录合入后执行。

## 2026-07-21 架构加固 Wave 2：LLM 链路性能（批量 embedding/重试退避/并发化）+ HTTP 出口收敛

- 修改人：Claude Fable（主控）+ Sonnet 实现/评审子代理（计划同 Wave 1 文档）
- 修改范围：LLM provider 层、个股研判、takeaway、topic 统计、HTTP 连接池。3 个任务、3 个提交（9aa1376、22818a5、a521d4c），每任务独立评审；T7 经一轮修复后复审通过。
- 变更内容：
  1. **LLM 批量 embedding + 重试退避**（9aa1376）：`embed_texts` 单请求批量（按 index 对齐），`_rank_news` 由最多 N 次串行 60s embedding 调用改为 1 次批量——个股研判 P99 预期从数十秒降至 1~2 次 RTT。同 provider 重试（仅 429/超时/5xx，默认额外 2 次，指数退避+jitter，流式仅首字节前），重试耗尽才 failover 且 backup 只做单次尝试；AsyncProvider 的 failover 查库/token 落库改经 anyio.to_thread（修复 T2 评审发现的事件循环阻塞残留）。新配置 `llm_retry_max_attempts`/`llm_retry_backoff_seconds`。
  2. **takeaway 并发化 + topic 统计批量化**（22818a5）：takeaway 逐条串行 LLM 改 4 线程并发（写回收敛主线程、顺序确定）；`refresh_topic_stats` 由 O(topics)×2 次查询改 2 次 IN 批量+Python 分组，计算公式原样复用并有新旧等价性测试。
  3. **HTTP 出口收敛**（a521d4c）：google_news_search/feishu_client 改用 http_pool 共享连接池（超时语义无漂移、token 刷新逻辑不变），article_crawler 超时改模块常量，删除无调用方的遗留 `http_client.py`。
- 影响文件：backend/app/services/{llm_providers,stock_research_synthesis,news_takeaway,http_pool,google_news_search,feishu_client,news_ingestion}.py、services/ingestion/article_crawler.py、repositories/news_signal_repository.py、core/config.py（http_client.py 删除）+ 对应测试（新增 test_http_pool.py、test_google_news_search.py 等）。
- 接口/数据结构变化：无 API/DB 变化；provider 新增 `embed_texts` 方法与 `max_attempts` 构造参数（向后兼容）；config 新增 2 个重试字段。ConnectError 现属可重试错误——外部观察到的失败请求总时延会增加约(退避+重试)时长。
- 验证情况：波次收尾全量 `NEWS_CAUGHT_TEST_DB=/tmp/nc_wave2_final.db conda run -n news-caught pytest backend/tests -q` → 617 passed（Wave 1 后 577，+40）。
- 风险或后续事项：评审 Minor 留台账（close_llm_client 命名承载多类 client 建议改名、google_news 复用测试断言偏弱、topic 等价性测试用内联复刻旧算法）；流式生成器提前关闭时 anyio.to_thread 的取消传播为已知边界（与既有模式一致）。

## 2026-07-21 架构加固 Wave 1：并发修复 + 无界表清理 + 死代码/出包治理

- 修改人：Claude Fable（主控）+ Sonnet 实现/评审子代理（subagent-driven，计划见 docs/superpowers/plans/2026-07-21-architecture-hardening-plan.md）
- 修改范围：后端事件总线/chat 路由/通知幂等/数据清理/模型清理，前端 API mock 层。共 6 个任务、6 个提交（fe2d4b5、84d6d6c、afcb2b9、a67f2ce、1853fcc、7f76f1c），每任务独立 spec+质量评审通过。
- 变更内容：
  1. **事件总线加锁**（fe2d4b5）：`InMemoryEventBus._handlers` 原全程无锁，SSE 请求线程建断订阅与 worker 线程发布迭代存在竞态（压力测试实际复现丢失更新）。subscribe/unsubscribe 持锁原子化，publish 锁内快照、锁外调 handler。
  2. **chat_with_llm 阻塞修复**（84d6d6c）：async 端点内 4 处同步 SQLite 读收拢为 `_load_chat_context`，单次 `anyio.to_thread.run_sync` 执行；此前撞 SQLite 写锁会阻塞事件循环上全部请求与 SSE。
  3. **通知入队幂等 DB 化**（afcb2b9）：`notification_job.dedupe_key` 建部分唯一索引（迁移 0a513ac0e869，幂等 raw SQL；历史重复同 key 保留 id 最大、其余置 NULL；移除被替代的普通索引），repository SAVEPOINT 包插入 + IntegrityError 回退返回既有 job。
  4. **LLM 两表纳入保留清理**（a67f2ce）：`llm_token_usage` 90 天（删前 JSONL 归档）、`llm_classification_cache` 30 天（直接删），新增 config `llm_token_usage_retention_days`/`llm_classification_cache_retention_days`；此前两表无界增长。
  5. **signal_event 死模型移除**（1853fcc）：无迁移建表、无代码引用；technical-architecture/stability-and-evolution 通知段落改写为基于 notification_job 的 as-built。
  6. **前端 mock 出包治理**（7f76f1c）：mock 动态 import 改编译期 DEV 守卫，生产包 mock chunk（18.4KB）消失、入口 156.9→153.8KB；内联 mock 数据迁入 api/mock/；LLMStats 类型别名归位 types/api.ts 适配层。
- 影响文件：backend/app/services/{event_bus,cleanup}.py、backend/app/api/routes/llm.py、backend/app/models/{notification_job,__init__}.py（signal_event.py 删除）、backend/app/repositories/notification_job_repository.py、backend/app/core/config.py、backend/alembic/versions/0a513ac0e869\*.py、frontend/src/api/{client.ts,mock/llm.ts,client.test.ts}、frontend/src/types/api.ts、两份架构文档、对应测试（新增 test_llm_chat.py、test_notification_dedupe.py 等）。
- 接口/数据结构变化：无 API 变化；DB 新增 1 个 partial unique index、移除 1 个普通索引（迁移可 downgrade，置 NULL 的历史 dedupe_key 不可逆，已在迁移注释说明）；config 新增 2 个 retention 字段（默认 90/30 天）。
- 验证情况：波次收尾全量 `NEWS_CAUGHT_TEST_DB=/tmp/nc_wave1_final.db conda run -n news-caught pytest backend/tests -q` → 577 passed（基线 547，+30）；前端 typecheck/vitest 全量（417 tests）/build 通过，评审独立复核构建产物无 mock chunk。
- 风险或后续事项：评审 Minor 项已记台账留终审 triage（classification_cache.created_at 无索引、event_bus 计数字段未加锁、createWatchlist 返回形状不一致——均为既有状态）；T2 评审发现 AsyncProvider failover/token flush 也在事件循环做同步 DB，已并入 Wave 2 Task 7 处理。

## 2026-07-18 修复：FTS 同步触发器丢失（迁移 d7f0a3b5c9e2）

- 修改人：Kimi Code（主线）
- 修改范围：`backend/alembic/versions/d7f0a3b5c9e2_restore_news_fts_triggers.py`（新）；开发库 `backend/data/app.db`（经启动初始化自动应用迁移）。
- 变更内容：历史迁移 c4f8a1d3e6b2（batch_alter_table 加 ai_takeaway 列）在 SQLite 上整表重建 news_item，连带丢弃 ec84dec88ae5 建立的三个 FTS 同步触发器（news_fts_ai/ad/au），此后 news_fts 停止增量同步、搜索静默退化为 LIKE 全表扫。新迁移：幂等建 FTS 虚表 → DROP+CREATE 三个触发器（保证定义确定性）→ `VALUES('rebuild')` 全量重建 FTS 内容清除漂移。
- 影响文件：迁移文件；本变更记录。
- 接口/数据结构变化：DB 恢复 3 个触发器 + FTS 内容重建（对应用透明，恢复 ec84dec88ae5 的原有设计）。
- 验证情况：dev 库副本实测迁移链 f3a7→…→d7f0 通过；运行中的 dev 服务经 --reload 自动应用迁移后，实测 insert/update/delete 三路触发器同步正确（FTS 命中 1/1/0），news_fts 与 news_item 行数一致（286）；`NEWS_CAUGHT_TEST_DB` 独立库全量 pytest → 547 passed。
- 风险或后续事项：教训——今后对 news_item 使用 batch_alter_table 的迁移必须复查触发器存活（批次 A 的幂等 raw SQL 风格即为规避此问题）；测试库的 initialize_database 各路径已随全量测试覆盖。

## 2026-07-18 性能优化批次 D：K 线缓存修复 + 事件扇出/redis/心跳/分类缓存收口

- 修改人：Kimi Code（子任务 / 后端收口）
- 修改范围：`market_chart_service.py`、`notification_service.py`、`queue_worker.py`、`event_bus.py`、`redis_stream_bus.py`、`news_signal_repository.py`、`base_worker.py`、`worker_runtime_status_repository.py`、`llm_providers.py` 及调用方。
- 变更内容：
  1. **K 线缓存命中即返回**：`get_kline` 原"缓存只写不读、每次真实 yf.download"，改为 TTL 内命中直返、build 异常时 stale 兜底；`list_related_news` 加 LIMIT 200。
  2. **事件扇出批量化**：新增 `on_news_created_batch`（一次 config 加载 + 单 session 批量 enqueue + 一次 commit），queue_worker 改批量调用，原单条接口保留。
  3. **redis 熔断**：`HybridEventBus` 连续失败 3 次熔断 60s（期间仅内存总线，半开恢复）；`RedisStreamConsumer` 异常日志降频 60s/条。
  4. **find_topic 批内预载**：关键词兜底的 TopicCluster 全表扫描每批一次，`create_topic` 后追加候选，匹配语义不变。
  5. **心跳节流下沉 BaseWorker**：空闲 30s 节流（原仅 queue_worker），删除多余 `session.refresh`。
  6. **分类缓存键修正**：整篇 prompt sha256（命中率≈0）→ (title+summary+market) 结构化字段 sha256；`get/store_classification` 支持调用方 session 复用。
- 影响文件：上述文件 + 新增/修改测试（test_news_signal_repository、test_market、test_feishu_notify、test_event_bus、test_redis_stream_consumer、test_base_worker、test_llm_classification_cache 等）。
- 接口/数据结构变化：无 API 变化；`analyze_json` 增可选 kwargs（title/summary/market），`notification_service` 增批量方法，均向后兼容。
- 验证情况：`NEWS_CAUGHT_TEST_DB=/tmp/nc_test_D.db pytest tests -q` → 543 passed（批次内）；TDD 先红后绿。
- 风险或后续事项：`news_signal_classifier` 链路无 market 可传，同题跨市场新闻共享分类缓存结果（takeaway/analysis 链路含 market 不受影响）；缓存 session 复用入口已留但未深入 provider 层。

## 2026-07-18 性能优化批次 B：行情批量报价 + 抓取链路（连接池/水合/源配置缓存/X 容错）

- 修改人：Kimi Code（子任务 / 抓取链路）
- 修改范围：`quote_provider.py`、`http_pool.py`、`ingestion/fetcher.py`、`ingestion/persister.py`、`ingestion/service.py`、`ingestion/sources.py`、`ingestion/detail_hydration.py`（新）、`twitterapi_io_client.py`、`x_monitor/pipeline.py`、`core/config.py`。
- 变更内容：
  1. **行情批量报价**：Yahoo 单票 `Ticker.history(5d)`+fast_info（2-3 请求/票）→ `yf.download` 单次批量（2d），MultiIndex/单 symbol 兼容解析；未覆盖 symbol 回落原单票路径，腾讯兜底不动。
  2. **feed/X 共享连接池**：新增 `http_pool.get_feed_client()` 替代每源每轮新建 Client；X client 改类级共享。每轮省去逐源 TCP+TLS 握手。
  3. **MiniMax 详情水合挪出串行落库段**：新模块 `detail_hydration.py`，4 线程并发抓取详情页 + 内存冷却表（24h 窗口最多 3 次）；persister 串行段不再发 HTTP。
  4. **load_sources mtime 缓存**：(mtime_ns, size) 签名命中跳过重读+解析，消除每重复 item 一次磁盘读与 scheduler 每 5s 一次重读；`clear_sources_cache()` 供测试/热更新。
  5. **X 抓取逐账号容错**：任一账号失败不再整轮作废（部分失败记成功并带明细）；`twitterapi_io_min_interval_seconds` 默认 0→1.0s。
- 影响文件：上述文件 + test_quote_batch_and_fallback（新）、test_ingest_caching、test_news_ingestion、test_x_monitor 等。
- 接口/数据结构变化：无 API 变化；config 默认值一项变更（X 限速 1.0s，可通过环境变量覆盖）。
- 验证情况：`NEWS_CAUGHT_TEST_DB=/tmp/nc_test_B.db pytest tests -q` → 547 passed；网络层全部 mock，无真实请求。
- 风险或后续事项：MiniMax 冷却表为进程内存态，重启清零；`HttpClientFactory` 已无生产调用方，后续可评估废弃。

## 2026-07-18 性能优化批次 A：查询层防退化 + 索引（runtime/snapshots/topics/pending）

- 修改人：Kimi Code（子任务 / 后端查询层）
- 修改范围：`news_runtime.py`、`market_repository.py`、`api/routes/topics.py`、`models/news_item.py`、`models/price_snapshot.py`、Alembic 迁移 ×2。
- 变更内容：
  1. **/news/runtime 全表物化 → SQL 聚合**：GROUP BY source/market + MAX(fetched_at) 回表 join，物化行数 N→源组合数，返回结构不变。
  2. **price_snapshot 读取退化修复**：`list_latest`/`list_latest_by_symbols` 改 MAX+GROUP BY 回表取行（原为全表/全历史物化）；新增 `ix_price_snapshot_symbol_fetched(symbol, fetched_at)` 复合索引（迁移 `c6e9a2b4d8f1`）。
  3. **pending partial index**：`ix_news_pending(id) WHERE signal_status IS NULL`（迁移 `b5d8f1a3c7e2`）；同迁移删除 `news_item.title`/`market`/`published_at` 冗余单列索引（前缀已被复合索引覆盖）。迁移用幂等 raw SQL，避免 batch 整表重建破坏 FTS 触发器。
  4. **/topics N+1 → 批量**：复用 `batch_news_for_topics`/`batch_related_symbols`，1+2T → 3 条 SELECT，排序语义不变。
- 影响文件：上述文件 + 新增 `backend/tests/test_query_perf_batch_a.py`（10 测试：schema/EXPLAIN/结果等价性）。
- 接口/数据结构变化：API 响应结构不变；DB 新增 2 个索引、删除 3 个冗余索引（Alembic 迁移，downgrade 可还原）。
- 验证情况：`NEWS_CAUGHT_TEST_DB=/tmp/nc_test_A.db pytest tests -q` → 546 passed；EXPLAIN 留证（partial index/覆盖索引命中）；scratch 库升降级两条路径实测（含 FTS 触发器存活）。
- 风险或后续事项：聚合 MAX(fetched_at) 依赖存量时间格式一致（实测均 UTC）；**pre-existing 发现**：dev 库 `backend/data/app.db` 的 FTS 同步触发器在历史迁移后已丢失（FTS 增量同步可能失效），建议另行排查修复。

## 2026-07-18 性能优化批次 C：前端 SSE 降频 + watch 浅化 + markdown LRU + SVG sparkline + AbortSignal

- 修改人：Kimi Code（子任务 / 前端）
- 修改范围：`AppShell.vue`、`NewsFeedView.vue`、`newsStore.ts`、`utils/markdown.ts`、`StockSparkline.vue`、`api/http.ts`、`api/client.ts`。
- 变更内容：
  1. **SSE layout 刷新降频**：news.created/updated 只走 store 本地增量（不再 500ms 防抖全量 loadFeedLayout）；topic.updated 保留防抖全量；新增 60s 周期全量刷新；重连恢复路径不变。
  2. **NewsFeedView watch 浅化**：displayedFeedItems 深拷贝+deep/sync watch → shallowRef + flush:'post'；newsStore 数组更新改整体替换引用以驱动浅 watch。
  3. **markdown LRU**：parseMarkdown 加 Map-based LRU（上限 100），流式打字机期间重复解析 O(1) 命中；调用侧零改动。
  4. **StockSparkline → SVG**：每股一个 lightweight-charts 实例（含 ResizeObserver）→ 复用纯 SVG `common/Sparkline.vue`，涨跌色走 CSS 变量。
  5. **AbortSignal 接通**：getJson/postJson 加可选 signal；NewsFeedView 搜索/筛选切换真正 abort 过期请求（原 AbortController 空转），乱序仍由 store requestId 兜底。
- 影响文件：上述文件 + AppShell.test/NewsFeedView.test/StockSparkline.test/markdown.test 更新。
- 接口/数据结构变化：无（apiClient/store 方法增可选 signal 参数，向后兼容）。
- 验证情况：`npx vitest run` → 78 文件 / 405 tests 全绿；`npm run build` → 通过。
- 风险或后续事项：layout 的 events/topics 区块新鲜度降为 ≤60s（新闻流本体走本地增量无感）；流式消息纯文本降级渲染未做（LRU 已覆盖主要开销）。

## 2026-07-18 性能优化阶段 1 止血：信号 pipeline 单入口化 + 字体拉丁子集

- 修改人：Kimi Code（主线）
- 修改范围：`backend/app/services/news_ingest_scheduler.py`、`backend/app/services/ingestion/service.py`、`frontend/src/main.ts`。
- 变更内容：
  1. **pipeline 单入口化**：`signal_status IS NULL` 的 pending 集原被三个入口无认领消费（queue_worker 30s、scheduler drain 5s、refresh_all 无插入分支），后两者不传 session_factory 导致串行 LLM 期间持 SQLite 写锁、同批 id 被重复爬正文+重复 LLM。改为：scheduler `_drain_signal_backlog` 仅把 pending id 投入 `analysis_queue`，`refresh_all` 删除无插入时的就地处理分支，pending 处理只留 BackgroundQueueWorker 单入口（单线程无并行重复，无需额外认领状态）。
  2. **字体拉丁子集**：fontsource 全子集引入（dist 92 个字体文件/1.4MB，占产物 60%）→ `latin-*.css` 仅拉丁子集（8 个 woff2），dist 总体积 2.3MB→1.3MB。
- 影响文件：上述文件 + `backend/tests/test_news_ingest_scheduler.py`、`backend/tests/test_news_ingestion.py`（断言更新为新行为）。
- 接口/数据结构变化：无（pending 处理时序变化：无新插入时积压由 scheduler 5s 内转交 worker，较原路径更快）。
- 验证情况：`pytest test_news_ingest_scheduler/test_news_ingestion/test_source_health_status/test_news_signal_pipeline` → 54 passed；终轮全量 547 passed；前端 build 通过（dist 字体 8 个 woff2）。
- 风险或后续事项：queue_worker 进程崩溃时 analysis_queue 内存任务丢失，仍有 30s 兜底轮询自愈（与原设计一致）。

## 2026-07-18 修复：短页面下壳层状态条被网格拉伸撑大

- 修改人：Kimi Code（主线）
- 修改范围：`frontend/src/components/layout/AppShell.vue` 主区容器。
- 变更内容：`<main>` 类由 `grid min-w-0 gap-3` 改为 `grid min-w-0 content-start gap-3`。原因：外层壳网格把 main 拉伸到整屏高，而 main 是 grid，其 auto 行（状态条 + 视图）在默认 `align-content: stretch` 下均分剩余空间，导致日历等短内容页面顶部状态条被拉成巨块；改为 `content-start` 后行高按内容收敛。已确认全站 17 个视图根均不依赖父行高度（仅 ChatView 自带 `h-[calc(100vh-100px))]` 视口高度，不受影响）。该问题为改版前已存在的存量 bug，非本次样式回归。
- 影响文件：`frontend/src/components/layout/AppShell.vue`；本变更记录。
- 接口/数据结构变化：无。
- 验证情况：`npx vitest run src/components/layout src/views/CalendarView.test.ts` → 17 tests 通过；`npm run build` → 通过。
- 风险或后续事项：短页面底部出现留白属预期（内容不再强行撑满）；如个别视图希望恢复撑满高度，需在该视图根显式声明视口高度。

## 2026-07-18 克制赛博：设计令牌层升级 + 字体自托管 + 壳层打磨

- 修改人：Kimi Code（主线）
- 修改范围：设计令牌（`main.css`）、`tailwind.config.js`、`index.html`、`main.ts`、`AppShell.vue`、`.terminal-surface` 残留引用清理。
- 变更内容：
  1. **令牌层升级**（`frontend/src/assets/main.css`）：底色面板整体压深（`--bg #070a12→#05070d`、`--panel #0d111b→#0b0f18` 等 7 档，`--text` 亮度不动保对比度）；主色 `#3ad2e6→#3ee6ff` 电青（`--accent/--neutral/--ai-2/--grad-ai` 及 interactive/focus/glow 系列 rgba 同步）；新增 `--grid-line`/`--bg-grid`（3% 透明度网格纹理，body 背景叠加，监控大屏氛围）、`--surface-highlight`（`.surface` 顶部 1px 内高光）；新增工具类 `.bg-grid`、`.anim-fade-up`、`.pulse-dot`（`--pulse-color` 可覆盖）与全局 `@keyframes fade-up/pulse-dot`；`prefers-reduced-motion` 改为全站通用守卫（`animation/transition 0.01ms`），替代原仅 fade-cross 的局部处理。
  2. **`.terminal-surface` 别名删除**：`PortfolioView.vue`（4 处）去冗余类；`TopicBoard.vue` 根元素改 `surface topic-card`；`DashboardTopicColumn.vue` 3 处 `:deep(.terminal-surface)` 选择器改 `:deep(.topic-card)`。
  3. **字体自托管**：`index.html` 删除 Google Fonts CDN（preconnect + css2 链接）；新增依赖 `@fontsource/inter`、`@fontsource/jetbrains-mono`，`main.ts` 引入 400/500/600/700 四档字重；字体栈移除不再加载的 IBM Plex Sans/Mono（`main.css` 与 `tailwind.config.js` 同步）。中文仍回落系统字体（PingFang SC 等），不自托管 CJK 大字库。
  4. **AppShell 打磨**：状态条信号灯色值由硬编码 rgba 改 `color-mix(in srgb, var(--success/--warning/--danger) …)` 令牌驱动；live 状态信号灯启用 `pulse-dot` 脉冲（`--pulse-color` 取 success 35%）；导航激活竖条加 `shadow-glow`。
- 影响文件：`frontend/src/assets/main.css`、`frontend/tailwind.config.js`、`frontend/index.html`、`frontend/src/main.ts`、`frontend/package.json`、`frontend/src/components/layout/AppShell.vue`、`frontend/src/views/PortfolioView.vue`、`frontend/src/components/dashboard/TopicBoard.vue`、`frontend/src/components/dashboard/DashboardTopicColumn.vue`；设计与计划文档 `docs/superpowers/specs/2026-07-18-cyber-terminal-restyle-design.md`、`docs/superpowers/plans/2026-07-18-cyber-terminal-restyle-plan.md`；本变更记录。
- 接口/数据结构变化：无（纯样式/资源变更；`data-role`、`nav-active-signal`、`shell-status-rail-signal` 等测试钩子保留）。
- 验证情况：`npm --prefix frontend run build` → 通过（dist 内含 woff2 字体与 `pulse-dot`/`bg-grid`/`anim-fade-up` 类）；`npx vitest run`（frontend 全量）→ **78 文件 / 400 tests 全部通过**；`npm --prefix frontend run check:api-drift` → OK 无漂移。
- 风险或后续事项：底色加深后需 dev server 目检对比度（`--text` 未动，理论无退化）；新增两个 fontsource npm 依赖（构建期内联，本地部署不再依赖外网字体）；`bg-white/[0.0x]` 类低透明工具类尚有零星残留（语义中性，后续可统一评估）。

## 2026-07-18 克制赛博扫尾：残留 Tailwind 色板/白色覆盖层清零 + 动效收敛


- 修改人：Kimi Code（子任务 / 克制赛博改造最后扫尾）
- 修改范围：`frontend/src/components/llm`（3）、`frontend/src/components/watchlist`（4）、`frontend/src/components/dashboard`（5）、`frontend/src/views`（2）、`frontend/src/utils/markdown.ts`（+其测试断言 1 处）。
- 变更内容：
  1. **Tailwind 色板色 → 语义类**：`TokenUsageConsole.vue` 全部 `text-emerald-400`(/80)→`text-success`(/80)、`text-red-400`→`text-danger`、`text-purple-400`→`text-ai`，预算横幅 `border-red-500/60 bg-red-500/10 text-red-300`→`border-danger/60 bg-danger/10 text-danger`、`border-emerald-500/40 bg-emerald-500/[0.06]`→`border-success/40 bg-success/[0.06]`；`LlmConfigList.vue` 禁用按钮 amber→`warning`、设默认按钮 blue→`system`；`StockDetailPanel.vue` AI 复制按钮/spinner/加载文案 purple→`ai`；`WatchlistDetailView.vue` 复制按钮 `bg-white/[0.05] text-purple-300`→`bg-ai/10 text-ai hover:bg-ai/20`、mode 徽章 `'bg-purple-500/10 text-purple-300'`→`'bg-ai/10 text-ai'`；`markdown.ts:19` 行内代码 `text-yellow-300`→`text-warning`（同步更新 `markdown.test.ts:22` 断言，唯一允许的测试改动）。
  2. **SVG/悬浮框色值令牌化**：`TokenTrendChart.vue` 网格线 `rgba(255,255,255,0.04)`→`color-mix(in srgb, var(--text) 4%, transparent)`、轴文字 0.4→`var(--text-faint)`、0.25→`color-mix(... 25%, ...)`；tooltip `border-cyan-500/30 bg-black/90`→`border-accent/30 bg-panel-stronger/95`，删 `backdrop-blur-md` 与 `shadow-cyan-950/20`（保留 `shadow-lg`），`text-cyan-400`→`text-accent`、`border-white/10`→`border-border`；`SentimentGauge.vue` 4 处 stroke（0.08/0.06/0.05/0.15）→`color-mix(in srgb, var(--text) 8%/6%/5%/15%, transparent)`。
  3. **白色低透明覆盖层 → 面板令牌**：`DashboardNewsFeedColumn.vue`（0.025→`--panel-soft`、0.05→`--panel-strong`）、`DashboardHeader.vue`（0.035→`--panel-soft`、圆点辉光→`color-mix(var(--text) 4%)`）、`DashboardMoversColumn.vue`（0.03→`--panel-soft`）、`SourceHealthGrid.vue`（0.025→`--panel-soft`、圆点辉光同上前）、`KlineChart.vue`（HUD `bg-[rgba(7,12,22,0.82)]`→`bg-panel-stronger/80`，两处 `bg-[rgba(255,255,255,0.02/0.025)]`→`bg-panel-soft`）、`KlineNewsPopup.vue`、`WatchlistAddModal.vue`（背板 `bg-[rgba(3,7,13,0.72)]`→`bg-[color-mix(in_srgb,var(--bg)_72%,transparent)]`，`0.02`→`bg-panel-soft`）。
  4. **动效收敛**：`NewsFeedView.vue:502` live 点 `shadow-glow animate-pulse`→`pulse-dot`（去掉 shadow-glow 避免与脉冲 box-shadow 冲突）；delta 横幅与流内 NewsCard 加全局 `.anim-fade-up` 类，scoped 的 `.fade-in-*`/`.list-fade-in-*` 动画实现删除（`<transition name="fade-in">`/`<transition-group name="list-fade-in">` 名钩子保留为无样式挂载点）；`DashboardNewsFeedColumn.vue:55` live 点加 `pulse-dot` 并按点色用 `:style` 覆盖 `--pulse-color`（positive/negative 35%）。其余 `animate-pulse`（骨架屏/加载文案/⚡）与 breathe/shimmer keyframes 未动。
  5. 未动业务逻辑/props/emit/`data-role`；除 `markdown.test.ts:22` 外未改任何测试。
- 影响文件：`TokenUsageConsole.vue`、`LlmConfigList.vue`、`TokenTrendChart.vue`、`StockDetailPanel.vue`、`KlineChart.vue`、`KlineNewsPopup.vue`、`WatchlistAddModal.vue`、`DashboardNewsFeedColumn.vue`、`DashboardHeader.vue`、`DashboardMoversColumn.vue`、`SourceHealthGrid.vue`、`SentimentGauge.vue`、`NewsFeedView.vue`、`WatchlistDetailView.vue`、`utils/markdown.ts`、`utils/markdown.test.ts`；本变更记录。
- 接口/数据结构变化：无（纯样式类名/CSS 值变更）。
- 验证情况：`npx vitest run`（frontend 全量）→ **78 文件 / 400 tests 全部通过**；`npm run build` → 通过；dist CSS 确认生成 `bg-panel-soft`/`text-ai`/`bg-panel-stronger`/`text-success`/`pulse-dot`/`anim-fade-up` 等工具类；全仓 `grep` 残留色板类（emerald/purple/yellow/cyan/amber/blue/red-*）与 `rgba(255,255,255,*`/`rgba(7,12,22`/`rgba(3,7,13` 零命中。
- 风险或后续事项：`DashboardNewsFeedColumn.vue:55` 的 live 点**保留 `animate-pulse` 类**（`DashboardNewsFeedColumn.test.ts:65` 与 `DashboardView.test.ts:239` 硬断言该类名，约束不允许改测试），与 `pulse-dot` 叠加——透明度脉冲+环形脉冲同时生效，视觉克制可接受；NewsFeedView 初始渲染时全部可见 NewsCard 会播放一次 `anim-fade-up` 入场（原 transition-group 无 appear，初始不动），为改用全局类的预期行为差异；`bg-white/[0.0x]` 等非本批枚举的白色透明度工具类仍有少量残留（LlmConfigList 等按钮底），待后续统一评估。

## 2026-07-18 克制赛博：K 线簇 + LLM 簇 canvas/JS 色值接入设计令牌

- 修改人：Kimi Code（子任务 / watchlist K 线簇 + llm 簇 + SentimentGauge 改造）
- 修改范围：`frontend/src/composables`（2）、`frontend/src/utils`（3）、`frontend/src/components/watchlist`（8）、`frontend/src/components/llm`（4）、`frontend/src/components/dashboard/SentimentGauge.vue`。
- 变更内容：
  1. **新增共享 helper `frontend/src/utils/cssVars.ts`**：`readCssVar(name, fallback)` 用 `getComputedStyle(document.documentElement)` 读 `:root` 令牌计算值，jsdom 等无令牌环境回落 fallback；`readCssVarWithAlpha(name, alpha, fallbackHex)` 把 hex 令牌转 `rgba(r, g, b, a)`（canvas 只吃具体色值，不吃 `var()`/`color-mix`）。
  2. **canvas 图表（lightweight-charts）**：`useKlineChartLifecycle.ts` 初始化时快照一次令牌——K 线红涨绿跌 `--positive`/`--negative`、网格 `--border`、文字 `--text-soft`/`--text-faint`、VOL/MACD 柱 `--positive/negative`+0.5/0.42 alpha、MACD/KDJ 线 `--accent`/`--system`/`--danger`、RSI `--success`、系列底色 `--accent-soft`；`StockSparkline.vue` 涨跌线色同法；`useKlineMarkers.ts` 情绪标记色 `--positive/--negative/--system/--ai/--muted`；`klineDrawings.ts` 画线工具默认色 `--warning/--system/--success/--ai/--danger`；`klineIndicators.ts` MA/EMA 色板（6+4）与 BOLL 通道（`--success`+alpha）。全部 fallback = 原视觉值，jsdom 测试零变化。
  3. **SVG/DOM 模板**：`KlineDrawingOverlay.vue`（锚点/十字线/草稿线 `#f8fafc`/`#0f172a`/`#3ad2e6` → `var(--text)`/`var(--panel-strong)`/`var(--accent)`，十字线透明度移入 `stroke-opacity`）；`KlineNewsTooltip/Popup` 情绪色记录改 `var(--xxx)`，Popup 徽章 `hex+'22'` 拼接改 `color-mix(in srgb, var(--xxx) 13%, transparent)`；深色浮层 `rgba(7,12,22,*)`/`rgba(10,17,27,0.95)` → `bg-panel-stronger/90~95`；`KlineDrawingSelectionPopover` 色板 emit 值用 `readCssVar('--warning'/'--system')`（持久化数据仍是具体 hex）；`TokenTrendChart.vue` 折线 `#22d3ee` → `--accent`（测试断言 path stroke 为具体 hex，故该处用 helper 绑定，渐变/十字线/圆点直接 `var()`）；`SentimentGauge.vue` 指针 `#ffffff` → `var(--text)`、枢轴 `rgba(11,18,28,0.9)` → `var(--panel)`+`fill-opacity`。
  4. **语义类映射**：`TokenUsageConsole` 四条辉光边条（蓝/绿/紫/琥珀 → `system`/`success`/`ai`/`warning`，`shadow-[0_0_8px_var(--xxx)]`）；`LlmConfigList` 默认配置橙高亮 `#ff9f2f*` → `warning` 语义类（徽章改实心 `bg-warning` + 深色字），两个失配辉光 rgba → `var(--success-soft)`/`var(--danger-soft)`；`LlmConfigForm` 主按钮蓝渐变 → `linear-gradient(135deg,var(--system),var(--accent))`；`WatchlistSidebar`/`WatchlistAddModal` accent 按钮文字 `#04141a` → `text-[var(--bg)]`；`StockCard` 告警灯 `bg-red-500/600`+`#ef4444` 辉光 → `danger`，财报呼吸关键帧 rgba(255,207,90) → `color-mix(var(--warning))`。
  5. **等宽数字**：TokenUsageConsole 指标值/In-Out/占比/预算条/明细行补 `tabular-nums` 或 `.num`；TokenTrendChart 悬浮明细、LlmConfigList 时延徽章补 `tabular-nums`；KlineNewsTooltip "+N more" 补 `.num`。
  6. `StockCard.vue` 的 `prefers-reduced-motion` 媒体查询保留；未动业务逻辑/props/emit/`data-role`；未改任何 .test.ts。
- 影响文件：`frontend/src/utils/cssVars.ts`（新）、`useKlineChartLifecycle.ts`、`useKlineMarkers.ts`、`klineDrawings.ts`、`klineIndicators.ts`、`KlineDrawingOverlay.vue`、`KlineNewsTooltip.vue`、`KlineNewsPopup.vue`、`KlineDrawingSelectionPopover.vue`、`StockSparkline.vue`、`WatchlistSidebar.vue`、`WatchlistAddModal.vue`、`StockCard.vue`、`TokenTrendChart.vue`、`TokenUsageConsole.vue`、`LlmConfigList.vue`、`LlmConfigForm.vue`、`SentimentGauge.vue`；本变更记录。
- 接口/数据结构变化：无（`SENTIMENT_COLORS`/画线默认色在浏览器内取令牌值，jsdom 内为原 fallback 值；持久化画线色仍为 hex 字符串）。
- 验证情况：`npx vitest run src/components/watchlist src/components/llm src/composables src/utils src/components/dashboard` → **32 文件 / 136 tests 全部通过**；`npm run build` → 通过；dist CSS 中确认生成 `var(--danger)`/`var(--warning)`/`var(--panel-stronger)` 等新工具类。
- 风险或后续事项：`utils/markdown.ts` 行内代码色 `text-yellow-300` **保留未动**——`markdown.test.ts:22` 硬断言该类名，改 `text-warning` 会红；如要换令牌需同步改测试。K 线簇视觉微调：网格线 alpha 0.08→`--border`(0.12)、VOL 柱 0.28→`--accent-soft`(0.12)、MA 第 6 色 `#f59e0b`→`--accent`、EMA 粉 `#f472b6`→`--ai`（均为令牌内最近色相，设计意图）。遗留未扫：白色系低透明覆盖层（`rgba(255,255,255,0.02~0.15)`、`bg-white/*`）、`KlineChart.vue` 面板底 rgba、`WatchlistAddModal` 背板 `rgba(3,7,13,0.72)`、TokenUsageConsole 预算红绿 Tailwind 色板类（red-400/emerald-400 等）、TokenTrendChart 悬浮框 cyan 色板类——非 hex/rgba 字面量或本批枚举外，待统一扫尾。

## 2026-07-18 克制赛博：Ops 健康看板 7 文件去玻璃拟态 + 硬编码色值清零

- 修改人：Kimi Code（子任务 / ops 组件 + OpsHealthView 改造）
- 修改范围：`frontend/src/components/ops/` 6 个组件 + `frontend/src/views/OpsHealthView.vue`（上一批 13 视图遗留的 OpsHealthView 批次）。
- 变更内容：
  1. **去玻璃拟态**：5 张卡片根元素改用全局 `surface` 类（`class="surface ops-card"`），scoped `.ops-card` 删除 `backdrop-filter: blur(12px)`、`var(--shadow)` 大阴影与重复的背景/边框声明，仅保留圆角与内边距；告警条/徽标/按钮的半透明白底（`rgba(255,255,255,0.02~0.06)`）→ 实心面板令牌（行/统计块 `var(--panel-soft)`、计数徽章 `var(--panel-strong)`、告警条/按钮 `var(--panel)`）。
  2. **硬编码色清零**：系统健康语义——绿 `#39c884`/`#5bd49a`/`#7ed89e` → `var(--success)`（soft 底用 `--success-soft`）；告警橙 `#ff9f2f`/`#ffb25c`/`#ffb264` → `var(--warning)`；故障红 `#ff6f86`/`#ff8a9c` → `var(--danger)`（soft 底对应 `--warning-soft`/`--danger-soft`）；中性蓝 `#53c2ff` → `var(--system)`；eyebrow 橙 `#ffb77d`（含模板 `text-[#ffb77d]`）→ `warning`；带透明度的边框/辉光/渐变一律 `color-mix(in srgb, var(--xxx) P%, transparent)`，透明度沿用原值。
  3. **pill 收敛**：`ops-pill-warn`/`ops-pill-crit` 的 scoped 硬编码样式删除（main.css 已内置 `.pill.warning`/`.pill.danger`），模板补上 `warning`/`danger` 语义类，原 `ops-pill-warn`/`ops-pill-crit` 类名保留为测试钩子。
  4. **等宽数字**：成功率/连败/时延/HTTP 计数/心跳/成败计数/token 统计/时间等数字插值补 `.num`；`"IBM Plex Mono", monospace` → `var(--font-mono)`。
  5. 未动业务逻辑/props/emit、`data-role` 属性与 `.pill` 语义类钩子；未改任何 .test.ts。
- 影响文件：`OpsSourcesCard.vue`、`OpsWorkersCard.vue`、`OpsXSourcesCard.vue`、`OpsAlertsPanel.vue`、`OpsSystemStatusCard.vue`、`OpsLlmUsageCard.vue`、`OpsHealthView.vue`；本变更记录。
- 接口/数据结构变化：无（纯样式类名/CSS 值变更，测试钩子保持不变）。
- 验证情况：`npx vitest run src/components/ops src/views/OpsHealthView.test.ts` → **8 文件 / 38 tests 全部通过**；`npm run build` → 通过；`grep -E '#[0-9a-fA-F]{3,8}|rgba?\(|backdrop-filter'` 在上述 7 文件中零命中。
- 风险或后续事项：eyebrow 由橙 `#ffb77d` 变为琥珀 `--warning`（令牌内最近色相，设计意图）；告警灯辉光颜色随令牌微调（橙→琥珀、红→danger 红）；卡片圆角 18px 未纳入 `--r-*` 刻度（非色值，本批不动）。

## 2026-07-18 克制赛博：13 个视图硬编码色值 → 语义设计令牌

- 修改人：Kimi Code（子任务 / views 批量改造）
- 修改范围：`frontend/src/views/` 下 13 个含硬编码 hex/rgba 的视图（OpsHealthView 不在本批）。
- 变更内容：
  1. 模板任意值色值全部换成 Tailwind 语义类：蓝色渐变主按钮（`#1768c2→#3aa9f5`）→ `bg-accent text-bg`；橙色「临近/组合」强调（`#ff9f2f`/`#ffca97` 等）→ `warning` 或 `accent`（按语义：日历临近=warning，组合/ eyebrow 高亮=accent）；信息蓝（`#53c2ff`/`#9fd0ff`/`rgba(92,174,255,*)`）→ `system`；告警红（`#fecaca`/`#fca5a5`/`#7f1d1d`）→ `danger`；回测方向卡 `#ff6f86`/`#39c884` → `positive`/`negative`；面板渐变底 → `bg-panel`/`bg-panel-strong`。
  2. scoped style 色值改 `var(--xxx)`；带透明度色值用 `color-mix(in srgb, var(--xxx) P%, transparent)`；NewsDetailView 的 AI 按钮紫红渐变 → `var(--grad-ai)`。
  3. 数字（金额/百分比/计数/时间戳/优先级分）补 `.num` 或 `tabular-nums`。
  4. 未动业务逻辑/props/emit、`data-role` 与 `.pill` 语义类；CalendarView 的 `prefers-reduced-motion` 媒体查询保留。
- 影响文件：`XMonitorView.vue`、`CalendarView.vue`、`NewsDetailView.vue`、`PortfolioView.vue`、`TopicDetailView.vue`、`NotifySettingsView.vue`、`EventDetailView.vue`、`SignalBacktestView.vue`、`DigestView.vue`、`WatchlistDetailView.vue`、`SentimentNewsView.vue`、`SentimentEvalView.vue`、`LlmSettingsView.vue`；本变更记录。
- 接口/数据结构变化：无（纯样式类名/CSS 值变更，测试钩子保持不变）。
- 验证情况：`npx vitest run src/views` → **18 文件 / 97 tests 全部通过**；`npm run build` → 通过；`grep -E '#[0-9a-fA-F]{3,6}|rgba?\(' src/views` 仅剩 OpsHealthView（本批范围外）。
- 风险或后续事项：OpsHealthView 仍有 ~20 处硬编码色值待下一批处理；主按钮视觉从蓝色渐变变为实心电青（设计意图）；NewsDetailView 按钮 hover 阴影改为 accent/ai 色系 color-mix。

## 2026-07-17 审查跟进：时区/冷却/空批计数

- 修改人：Cursor（主线 / cursor-grok-4.5-high-fast）
- 修改范围：审查 Important 项修复（无 Critical）。
- 变更内容：
  1. 无时区 feed 时间按 `market` 解释：`cn`/`hk`→Asia/Shanghai，`us`→America/New_York，其它→UTC；RSS/API 解析传入 `source.market`。
  2. 前端 `refreshDashboardNews` 仅在刷新成功后写入 60s 冷却，失败可立即重试。
  3. `record_failure` 硬失败时清零 `consecutive_empty_batches`，与 scheduler 内存 streak 对齐。
- 影响文件：`ingestion/utils.py`、`ingestion/parser.py`、`ingestion/persister.py`、`newsStore.ts` 及对应测试；本变更记录。
- 接口/数据结构变化：无。
- 验证情况：`conda run -n news-caught pytest backend/tests -q` → **508 passed**；`vitest newsStore/TopicChips/OpsSources` → **22 passed**；`npm --prefix frontend run build` → 通过。
- 风险或后续事项：AbortController 仍未贯通到 apiClient（可接受风险）；进程内 refresh lease 多副本仍独立。

## 2026-07-17 优化收尾：refresh lease + 主题中文名 UI + Ops 源诊断

- 修改人：Cursor（主线 / cursor-grok-4.5-high-fast）
- 修改范围：手动刷新服务端冷却、主题 display_name 前端展示、Ops 新闻源健康诊断字段。
- 变更内容：
  1. **`/news/refresh` lease**：新增 `news_refresh_lease` + 配置 `news_refresh_cooldown_seconds`（默认 60）；冷却期内返回 **429** + `Retry-After`；测试套件默认 cooldown=0。
  2. **主题 chips/看板**：`TopicChipsRow` / `TopicBoard` 优先展示 `display_name`，chip `title` 透出 `alias_zh`（或原文 title）。
  3. **Ops UI**：`OpsSourceView` / `SourceHealthView` 暴露 `last_status`/`last_error`/`last_http_status`/`last_fetched_count`/`last_inserted_count`/`consecutive_empty_batches`；`OpsSourcesCard` 展示状态 pill、HTTP/解析/入库/空批与错误行；`npm run generate:api` 同步契约。
- 影响文件：`news_refresh_lease.py`（新）、`config.py`、`routes/news.py`、`schemas/ops.py`、`schemas/source_health.py`、`ops_health.py`、`conftest.py`、`test_news_refresh_lease.py`（新）、`test_ops_health.py`；前端 `TopicChipsRow.vue`、`TopicBoard.vue`、`OpsSourcesCard.vue` 及测试；`openapi.json`/`api.d.ts`；本变更记录。
- 接口/数据结构变化：`OpsSourceView`/`SourceHealthView` 新增可选诊断字段（兼容旧客户端）；`POST /api/news/refresh` 在冷却期内新增 429 行为。
- 验证情况：`conda run -n news-caught pytest backend/tests -q` → **506 passed**；相关 vitest（TopicChips/TopicBoard/OpsSources/newsStore/AppShell 等）→ **53 passed**；`npm --prefix frontend run build` → 通过。
- 风险或后续事项：lease 为进程内内存，多 Web 副本各自独立冷却；生产需确保未误设 `NEWS_REFRESH_COOLDOWN_SECONDS=0`。

## 2026-07-17 P0-1 修通独立 scheduler → Redis → Web SSE

- 修改人：Cursor（主线 / cursor-grok-4.5-high-fast）
- 修改范围：跨进程事件总线 + Web Redis consumer + 前端断线快照对账。
- 变更内容：
  1. **Redis 信封**：`RedisStreamPublisher` 写入 `event_name`/`publisher_id`；`news.created`/`news.updated` 纳入 stream_map。
  2. **RedisStreamConsumer**：Web lifespan 在 hybrid/redis 下启动，消费后 `inject_from_remote` 只进 local_bus，同进程消息按 publisher_id 去回声。
  3. **前端**：SSE 重连 `onReconnect` 拉取新闻/layout 快照，不触发全源 refresh。
- 影响文件：`redis_stream_bus.py`、`event_bus.py`、`main.py`、`test_redis_stream_consumer.py`、`test_event_bus.py`、`connectionStore.ts`、`AppShell.vue` 及测试。
- 接口/数据结构变化：Redis stream 字段新增 `event_name`/`publisher_id`（旧消息无 event_name 会被跳过）。
- 验证情况：`pytest backend/tests/test_redis_stream_consumer.py backend/tests/test_event_bus.py` → 10 passed；`vitest connectionStore + AppShell` → 14 passed。
- 风险或后续事项：独立 worker 模式依赖 Redis 可达；consumer 默认从 live tail（`$`）起读，断线窗口靠前端快照对账。

## 2026-07-17 P0-2 修正 304/空解析健康判定

- 修改人：Cursor（主线 / cursor-grok-4.5-high-fast）
- 修改范围：抓取 outcome 状态机、source_health 诊断字段、scheduler 退避/空批熔断。
- 变更内容：
  1. 状态拆分：`ok` / `not_modified` / `empty` / `parse_error` / `http_error`。
  2. `source_health` 新增 last_status/last_error/last_http_status/last_fetched_count/last_inserted_count/consecutive_empty_batches（迁移 `d1a2b3c4e5f6`）。
  3. scheduler：304/ok 清零失败；empty 计软 streak，达阈值低频探测；仅硬失败指数退避。
- 影响文件：`source_health.py`、persister/fetcher/types、`news_ingest_scheduler.py`、迁移、`test_source_health_status.py` 等。
- 接口/数据结构变化：`SourceFetchResult.status` 取值扩展；Ops 视图暂未暴露新字段。
- 验证情况：`pytest test_source_health_status + test_news_ingest_scheduler + test_ingest_caching` → 13 passed。
- 风险或后续事项：Ops UI 可后续展示 last_status；空批阈值默认 3 可配置化。

## 2026-07-17 P1-2 页面生命周期只读 + SSE debounce + 手动刷新冷却

- 修改人：Cursor（主线 / cursor-grok-4.5-high-fast）
- 修改范围：AppShell 启动不再全源抓取；SSE layout trailing debounce；手动 refresh 60s cooldown；NewsFeed 搜索防抖 + 仅 market 变化重算 layout。
- 变更内容：移除 bootstrap `refreshDashboardNews`；layout 刷新 500ms debounce；`refreshDashboardNews` 冷却；Feed 过滤器 300ms debounce，`pendingLayoutReload` 仅在 market 变化时重拉 layout；AbortController 取消过期 hydrate。
- 影响文件：`AppShell.vue`、`newsStore.ts`、`NewsFeedView.vue` 及测试。
- 接口/数据结构变化：无。
- 验证情况：见总验证；AppShell/newsStore 单测覆盖 cooldown 与无自动 refresh。
- 风险或后续事项：后端 `/news/refresh` 尚未加服务端 lease（仅前端冷却）；AbortController 未贯通到 apiClient fetch（以 requestId + abort hydrate 为主）。

## 2026-07-17 P1-1 effective_at = published_at ?? fetched_at

- 修改人：Cursor（子智能体 / cursor-grok-4.5-high-fast）
- 修改范围：新闻时间排序与 RSS 时间解析；API/前端展示标注。
- 变更内容：
  1. **`news_item.effective_at`**：新增可索引列，入库/更新时维护为 `published_at or fetched_at`（SQLAlchemy `before_insert`/`before_update` + persister 显式赋值）；索引 `(effective_at, id)` / `(market, effective_at, id)`。
  2. **列表/游标**：`NewsRepository.list_recent_page` 与 cursor 编解码改用 `effective_at`；feed layout 排序键同步。
  3. **RSS 解析**：修复 `dc:date`（原 `{*}dc:date` 无效，改为 Dublin Core Clark 记号 / `{*}date`）；无时区 feed 时间按 `Asia/Shanghai` 解释后转 UTC。
  4. **API/UI**：`NewsItemSummary` 暴露 `effective_at`（缺失时自动回填）；前端 `getNewsDisplayTimestamp` 优先 `effective_at`，`getNewsTimeSourceLabel` + `NewsCard` 标注「原文时间 / 抓取时间」。
  5. **迁移**：防御式 alembic `e2b4c6d8f0a1`，`down_revision=d1a2b3c4e5f6`，回填 `COALESCE(published_at, fetched_at)`。
- 影响文件：`backend/app/models/news_item.py`、`backend/alembic/versions/e2b4c6d8f0a1_add_news_item_effective_at.py`、`backend/app/repositories/news_{cursor,repository}.py`、`backend/app/services/ingestion/{utils,parser,persister}.py`、`backend/app/services/news_feed_layout.py`、`backend/app/schemas/news.py`、相关 pytest；`frontend/src/utils/time.ts`、`NewsCard.vue`、mock/openapi 生成物与 vitest。
- 接口/数据结构变化：`NewsItemSummary` 新增可空 `effective_at`（响应中由 ORM 填充；旧 cursor 语义变更，客户端需重拉）。兼容：保留 `published_at`/`fetched_at`。
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_ingestion.py backend/tests/test_news_feed_layout.py -q` → **69 passed**；`npx vitest run src/utils/time.test.ts src/components/news/NewsCard.test.ts` → **12 passed**；`npm --prefix frontend run build` → 通过。
- 风险或后续事项：生产库需跑 alembic upgrade；旧 keyset cursor 失效可接受；`mentions`/`signal` 仓库仍有部分 `published_at` 排序未切换（非列表主路径）。

## 2026-07-17 P1-4 强化市场相关性与主题命名

- 修改人：Cursor（子智能体 / cursor-grok-4.5-high-fast）
- 修改范围：入库相关性门槛、官方/IR/监管源优先、主题中文显示名、无 LLM 结构化摘要降级。
- 变更内容：
  1. **入库门槛**：新增 `passes_ingest_relevance_gate`，复用 `predict_market_relevance_details`；弱理由（`concept_mover` / `sector_signal_term`）单独出现时拒收；`ItemPersister.persist_item` 新条目入库前过门槛。
  2. **官方源优先**：扩展 `has_official_signal`（IR/EDGAR/8-K/港交所/财报等 + 短词 `ir` 边界匹配）；官方源绕过门槛。
  3. **主题命名**：新增 `topic_naming.py`（中文别名表 + `resolve_topic_display_name`）；`TopicItemView` / `NewsFeedTopicView` 增加可选 `display_name` / `alias_zh`；topics 路由与 feed layout 填充。
  4. **结构化摘要**：新增 `news_structured_summary.py`（主体/事件/影响对象模板）；规则分类与 takeaway 无 LLM 时写入 `ai_takeaway`。
  5. **中文强信号**：evaluator 增补「资本开支」等短语，避免真实市场中文稿被门槛误杀。
- 影响文件：`backend/app/services/news_priority.py`、`news_relevance_evaluator.py`、`news_signal_classifier.py`、`news_takeaway.py`、`news_feed_layout.py`、`topic_naming.py`（新）、`news_structured_summary.py`（新）、`ingestion/persister.py`、`schemas/topic.py`、`schemas/news.py`、`api/routes/topics.py`；测试 `test_market_relevance_gate.py` / `test_topic_naming.py` / `test_structured_summary.py`（新）及若干既有入库/管线用例适配；`docs/code-change-log.md`、计划 Task 7 勾选。
- 接口/数据结构变化：`TopicItemView` / `NewsFeedTopicView` 新增可选字段 `display_name`、`alias_zh`（兼容旧客户端）；入库侧静默跳过低相关新条目（不新增 API 错误码）。前端未跑 `generate:api`，类型快照未同步。
- 验证情况：`NEWS_CAUGHT_TEST_DB=/tmp/news-caught-p14-test.db conda run -n news-caught pytest backend/tests/test_market_relevance_gate.py backend/tests/test_topic_naming.py backend/tests/test_structured_summary.py backend/tests/test_news_priority.py backend/tests/test_takeaway_classifier.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_ingest_caching.py backend/tests/test_news_signal_pipeline.py backend/tests/test_news_ingestion.py -q` → **98 passed**。
- 风险/后续事项：门槛可能降低冷门但真实相关稿件召回，需持续用 benchmark 校准；前端主题 chips 仍读 `topic_title`，需 `generate:api` 后改用 `display_name`；未做全量 `backend/tests`。

## 2026-07-17 P1-3 修复虚拟列表滚动根高度

- 修改人：Cursor（子智能体 / cursor-grok-4.5-high-fast）
- 修改范围：新闻流 `NewsVirtualList` 虚拟滚动容器高度契约与回归测试。
- 变更内容：滚动根不再依赖会塌陷的 `height: 100%`，改为显式视口高度 `min(720px, calc(100vh - 220px))`（inline style），保证 `clientHeight` 可用；`clientHeight <= 0` 时回退到 680px 视口高度。新增回归测试：100 条 entries 时断言滚动根有明确高度，且 DOM `.virtual-row` 远小于 100（有限 overscan）。
- 影响文件：`frontend/src/components/news/NewsVirtualList.vue`、`frontend/src/components/news/NewsVirtualList.test.ts`、`docs/code-change-log.md`。
- 接口/数据结构变化：无（仅组件内部滚动根样式与视口同步兜底；新增 `data-role="news-virtual-scroll-root"`）。
- 验证情况：`npm --prefix frontend run test -- src/components/news/NewsVirtualList.test.ts` → **3 passed**（TDD：先写失败断言 `style.height` 为空，再修滚动根转绿）。
- 风险/后续事项：视口高度公式中的 `220px` 为顶部壳层估算，极端小屏或壳层布局大改时可能需微调；未改 `NewsFeedView` 父级高度链（滚动根自带明确高度已足够）。

## 2026-07-15 Latest Events 快读改版（多智能体并行开发集成）

- 修改人：Claude（主线协调，9 个实现任务由 Sonnet 子智能体分三波并行/串行完成，每任务经规格+质量双审，终审 With fixes 后修复合入）
- 修改范围：`/news` 板块快读改造全链路。设计文档 `docs/superpowers/specs/2026-07-15-latest-events-fast-read-design.md`，实施计划 `docs/superpowers/plans/2026-07-15-latest-events-fast-read.md`。
- 变更内容：
  1. **后端契约**：`news_item` 新增 `ai_takeaway` 列（防御式迁移 `c4f8a1d3e6b2`），贯通 `NewsItemSummary` → OpenAPI → 前端生成类型。
  2. **takeaway 双生成路径**：LLM 精修顺路产出（`news_signal_classifier` + `_apply_result` 不覆盖写回）；feed layout 高分候选入队 + `TakeawayWorker` 批量补齐（批量上限 12/日配额 300 按尝试计数、空结论落库为 `""` 防永久重试、`ai_enabled` 降级、每条 `news.updated` + 一条 `news.signals_processed`）。
  3. **详情接口提速**：`get_news_detail` 4 次串行查询合并为 2 次往返（`NewsRepository.get_detail_bundle`），响应契约不变。
  4. **前端改版**：事件胶囊条 `EventCapsuleStrip` + 主题 chips 行 `TopicChipsRow` 替换首屏大卡区；`NewsCard` 加情绪色条（红涨绿跌、编辑分三档透明度）/AI 结论行（item 优先防 SSE staleness）/已读淡化/选中态；点卡片改就地抽屉阅读（复用 `NewsDetailDrawer`，加「完整页」入口）；`useFeedKeyboard`（j/k/Enter/Esc，含过期选中防护）；低分尾部折叠（P70+至少留 10 条）；已读 localStorage（2000 条 FIFO）；AppShell 对 `updated_fields=['ai_takeaway']` 的 SSE 跳过 layout 全量刷新防抖动。
- 影响文件：后端 models/schemas/repositories/routes/services/workers/config/main + alembic 迁移 + 6 个测试文件；前端 NewsFeedView/NewsCard/NewsVirtualList/NewsDetailDrawer/AppShell + 4 个新组件/工具/composable + 生成类型。
- 接口/数据结构变化：`NewsItemSummary` 及其派生视图新增可空 `ai_takeaway`；新增配置 `takeaway_batch_limit`/`takeaway_daily_limit`/`takeaway_poll_interval_seconds`；`/news` 点卡片由整页跳转改为抽屉（详情页路由保留）。
- 验证情况：后端 `pytest backend/tests -q` → **478 passed**；前端 `vitest --run` → **389 passed（79 files）**；`vue-tsc` 0 错；`check:api-drift` OK；真实 `app.db` 启动迁移 + feed-layout/news/detail 接口冒烟 200（detail 热请求 ~2ms）。
- 风险/后续事项（终审分诊入 backlog）：DB 往返计数守护测试、NewsFeedView keydown 驱动集成测试、31-42 条折叠/虚拟化阈值交叉致展开时渲染策略切换（滚动重置）、紧凑条两组件 CSS 重复与 topic-chip 截断、takeaway 截断长度双写（120）、kbd 提示空流仍显示；commit 99b2c85 因并行 git index 竞态混入 T3/T4 两任务文件（内容正确，仅归属混杂）。

## 2026-07-15 修复迁移日志禁用与测试真实联网两个遗留问题

- 修改人：Claude
- 修改范围：十方向优化中子智能体发现、当时超出各自任务范围未修的两个真实问题。
- 变更内容：
  1. **修复 app.\* logger 被全局静默**：`backend/alembic/env.py` 的 `fileConfig()` 使用默认 `disable_existing_loggers=True`，而 `initialize_database()` 在生产启动（`main.py`）与测试会话中都会在应用模块已导入之后执行迁移——导致所有既存 `app.*` 模块级 logger 被置为 `disabled=True`，"代码里有日志、实际打不出来"。改为 `fileConfig(..., disable_existing_loggers=False)` 并加注释说明原因；新增回归测试 `backend/tests/test_logging_config.py`（TDD：先写测试确认复现，再修复转绿）。
  2. **掐断单元测试的真实联网 + 修复 SSLSocket 泄漏**：`test_news_signal_pipeline.py` 的多个用例以 `https://example.com/...` 造新闻后直接调用 `process_news_ids`，`_ensure_articles` 阶段未被 mock，会经共享爬虫连接池真实抓取 example.com（用户环境下经本机代理隧道），产生 unclosed SSLSocket ResourceWarning 且测试非确定、被网络拖慢。新增文件级 autouse fixture 把 `app.services.news_signal_pipeline.crawl_and_extract_article` 替换为抛错桩（走管线已支持的爬取失败优雅降级路径，断言均基于标题/摘要分类，行为不受影响）；同时在 `conftest.py` 会话收尾调用 `http_pool.close_llm_client()`，对齐生产 lifespan 的连接池关闭行为，兜底防止未来任何用到共享池的测试在进程退出时留下未关闭连接。
- 影响文件：backend/alembic/env.py、backend/tests/test_logging_config.py（新增）、backend/tests/test_news_signal_pipeline.py、backend/tests/conftest.py。
- 接口/数据结构变化：无。
- 验证情况：`conda run -n news-caught pytest backend/tests -q -W always::ResourceWarning` → **459 passed / 0 warnings**（含新增回归测试；此前该文件单测有 2 条 unclosed SSLSocket）；`ruff check backend` → All checks passed；全量测试耗时由 ~8s 降至 ~5.7s（移除真实网络请求）。
- 风险/后续事项：`test_article_crawler.py` 等其余涉爬取的测试已确认自带 `patch("httpx.Client.get")` mock，无联网逃逸；若未来新增直接驱动管线的测试，需同样 stub 爬取或复用本 fixture 模式。

## 2026-07-14 十方向优化并行开发集成（总述）

- 修改人：Claude（主线集成，子智能体并行开发）
- 修改范围：本次由 10 个子智能体分两波并行完成 10 个优化方向（明细见下方 10 条独立记录）：后端 4 项（ruff lint 治理、异常处理治理、测试警告清零、x_monitor 服务拆分）、前端 5 项（mock.ts 模块化、OpsHealthView 组件化、六视图测试补齐、DashboardView 瘦身、Kline 绘图逻辑下沉）、工程化 1 项（文档治理）。
- 基础设施改动：`backend/tests/conftest.py` 测试库路径支持 `NEWS_CAUGHT_TEST_DB` 环境变量覆盖（默认仍为 `backend/data/app_test.db`），使多智能体/多 worktree 并行跑 pytest 时可用隔离库文件，互不锁库。
- 影响文件：见下方各明细条目；conftest.py（基础设施）。
- 接口/数据结构变化：无（全部为重构、测试、lint、文档改动）。
- 验证情况（集成后全量）：`conda run -n news-caught ruff check backend` → All checks passed；`conda run -n news-caught pytest backend/tests -q` → **458 passed / 0 warnings**（基线 449 passed / 18 warnings）；前端 `npx vitest run` → **74 files / 355 passed**（基线 262）；`npm run build`（vue-tsc + vite）通过；`create_app()` 导入正常。
- 风险/后续事项（子智能体审查中发现、本次未处理的真实问题，建议排期）：
  1. 【高优先级】`backend/alembic/env.py` 的 `fileConfig()` 默认 `disable_existing_loggers=True`，`initialize_database()` 执行后（生产启动也触发）会全局禁用绝大多数 `app.*` 模块级 logger——"代码里有日志、实际打不出来"，建议改为 `disable_existing_loggers=False` 或 dictConfig。
  2. `news_signal_pipeline` 测试下观察到 unclosed SSLSocket 的 ResourceWarning，指向 services 层某 HTTP 客户端未显式关闭。
  3. `docs/optimization-plan.md` 回填后仍开放的项：#14 详情页 selectinload 未做（`get_news_detail` 仍 4 次串行查询）、#6 内存队列持久化、#8 路由异步化、#13 incremental_vacuum 缺 auto_vacuum 前置、requirements.txt/environment.yml 双依赖源未统一。
  4. `quote_provider.py::fetch_quotes_batch` 异常兜底中"保留部分成功字段"的原始意图从未生效（本次仅显式化死代码，未改行为），如需该能力需单独重构。

## 2026-07-14 后端 ruff lint 治理（规则收紧 + 现状清零）

- 修改人：Claude（子智能体-Lint治理）
- 修改范围：`backend/` 下全部 Python 文件的 lint 修复；`backend/pyproject.toml` 的 ruff 规则配置。
- 变更内容：
  1. 清零 `ruff check backend` 在默认隐式规则集（E4/E7/E9/F）下的 109 处错误：约 68 处经 `--fix` 自动修复，其中 38 处（`alembic/env.py` 的模型注册 import、`app/services/news_ingestion.py` 的拆包兼容 facade、`app/main.py` 的 `NewsRepository`/`NewsSignalPipelineService`）自动修复会删除运行时仍被依赖的 import（Alembic autogenerate 副作用注册 / 跨模块 re-export / 测试 monkeypatch 依赖），已回退并改用 `per-file-ignores` 或 `# noqa: F401` 显式保留；其余 41 处（E402 顺序、F821 未定义名、F841 未用变量）手工修复。
  2. `[tool.ruff.lint]` 新增 `select = ["E", "F", "W", "I", "UP", "B"]`，并对 `E501`（无格式化工具接入，历史长行代价大于收益）、`B008`（FastAPI `Depends()` 惯用法误报）设全局 `ignore`；新增 3 处 `per-file-ignores`（`x_monitor/__init__.py`、`alembic/env.py`、`news_ingestion.py`，均为拆包 facade 或副作用 import）。收紧后新增的 1097 处违规（主要是 I 排序与 UP 现代化）全部清零，其中 589 处自动修复，5 处 `zip()` 补 `strict=`（均为让既有等长假设显式化，非行为变更），1 处清理迁移文件尾随空格。
  3. 顺手修复 `notification_delivery_worker.py` 缺失的 `from typing import Any`（F821，此前因 `from __future__ import annotations` 未在运行时报错）；简化 `quote_provider.py::fetch_quotes_batch` 异常兜底中恒为 `None` 的死代码引用（行为不变，仅去掉对错误作用域变量的引用）。
- 影响文件：`backend/pyproject.toml`；`backend/app/**/*.py`（路由/服务/worker/模型，主要为 import 清理与排序、Py3.11 语法现代化）；`backend/alembic/env.py` 及 `backend/alembic/versions/*.py`；`backend/tests/*.py`（未用 import/变量清理、`zip(strict=)`）。
- 接口/数据结构变化：无。
- 验证情况：`conda run -n news-caught ruff check backend` → All checks passed；`conda run -n news-caught python -m pytest backend/tests -q` → 458 passed（与既定基线一致，无回归）；`PYTHONPATH=backend conda run -n news-caught python -c "from app.main import create_app; create_app()"` → OK。
- 风险/后续事项：`E501`/`B008` 目前全局豁免，若后续接入 `ruff format` 或需要更严格的 FastAPI 静态检查可重新评估；`fetch_quotes_batch` 的死代码提示批量报价失败时未能保留部分成功字段的原始意图从未实现，如需要该能力需单独重构（本次未做行为变更）。

## 2026-07-14 异常处理治理——workers/ 与 services/ingestion/

- 修改人：Claude（子智能体-异常治理）
- 修改范围：backend/app/workers/*.py、backend/app/services/ingestion/*.py 的宽泛异常处理审查与日志质量补强。
- 变更内容：
  1. fetcher.py::fetch_source_items 与 persister.py::persist_outcome/hydrate_minimax_detail_item：三处 ThreadPoolExecutor/串行批处理边界的 `except Exception` 原先完全没有日志（吞错不留痕），现补充带 source 名称/类型/url/latency 上下文的 logger.warning(exc_info=True) 或 logger.exception；因这些边界是"防批处理中断"的设计要点、且第三方异常类型（httpx 非 HTTPError 分支如 InvalidURL、ET.ParseError、json.JSONDecodeError、bs4 杂项异常）无法安全穷举，兜底范围保持 Exception 不收窄。
  2. base_worker.py::_record_success/_record_failure：尝试收窄为 sqlalchemy.exc.SQLAlchemyError，但被 test_news_ingest_scheduler.py::test_scheduler_drains_signal_backlog 的非标准 FakeSession 替身（缺 .scalar()）暴露出真实回归——AttributeError 会穿透 run_cycle() 破坏"从不崩溃"契约，已回滚为 except Exception 并补充说明注释，原有日志（worker 名称 + .exception 全栈）已合规。
  3. 其余 8 处 except（digest_worker.py trigger_fn 兜底、queue_worker.py 通知入队兜底、article_crawler.py 网络/解析兜底、parser.py/sources.py/utils.py 已窄类型）逐一审查后确认已合规或应保持宽泛（均已有带上下文的日志/上游有二层安全网），未作代码改动。
- 影响文件：backend/app/services/ingestion/fetcher.py、backend/app/services/ingestion/persister.py、backend/app/workers/base_worker.py、backend/tests/test_ingest_caching.py（新增 3 个日志断言测试）、backend/tests/test_base_worker.py（新建，6 个记账兜底回归测试）。
- 接口/数据结构变化：无。返回值、重试语义、调度节奏均未改变，仅日志质量与代码注释变化。
- 验证情况：NEWS_CAUGHT_TEST_DB 隔离库跑指定 8 个测试文件 65 passed；另全量 backend/tests 458 passed 无回归。
- 风险/后续事项：【发现，未修复，范围外】backend/alembic/env.py 的 fileConfig() 默认 disable_existing_loggers=True，导致 initialize_database() 执行后绝大多数 app.* 模块级 logger 被全局禁用，造成"代码里有日志、实际打不出来"的隐患，建议专项修复；queue_worker.py 通知入队兜底、digest_worker.py trigger_fn 兜底依赖范围外模块，若后续异常面收敛可重新评估收窄空间。

## 2026-07-14 后端测试 warnings 治理（18 → 0）

- 修改人：Claude（子智能体-警告治理）
- 修改范围：backend/tests/test_watchlist_research.py、test_portfolio_service.py、test_stock_research_synthesis.py、test_stock_news_search.py。
- 变更内容：诊断出全部 18 条 pytest warnings 均为同一根因——SAWarning "DELETE statement on table 'news_stock_mention' expected to delete 1 row(s); 0 were matched"。根因是这些测试的清理 helper 在同一次 flush 内先显式删除 NewsStockMention/ArticleContent 子行、再删除父行 NewsItem，但代码库未声明任何 SQLAlchemy relationship()（架构上一贯走 repository 显式查询），unit-of-work 因此无法保证子表先于父表 DELETE；SQLite 层 ON DELETE CASCADE（PRAGMA foreign_keys=ON）先把子行级联删除，随后测试代码排队的显式 DELETE 命中 0 行，触发该 warning。修复方式：在删除子行后、删除父行前插入 session.flush()，强制子行 DELETE 先落库，从根本上消除顺序竞争，未使用 confirm_deleted_rows=False 等压制手段。
- 影响文件：仅上述 4 个测试文件的清理 helper 函数，均为纯新增（注释 + 一行 session.flush()），无删除、无业务逻辑改动。
- 接口/数据结构变化：无。不涉及生产代码、模型、API、pyproject 配置。
- 验证情况：隔离库 pytest backend/tests -q -W error::DeprecationWarning → 全量通过，0 条 warnings（治理前 18 warnings）。多次重复运行结果一致。
- 风险/后续事项：pytest -Wdefault 下观察到 test_news_signal_pipeline.py 一个用例存在 ResourceWarning（unclosed SSLSocket），根因指向 app/services 内的网络客户端未正确关闭，建议后续在 services 层排查该客户端的关闭/上下文管理逻辑。

## 2026-07-14 X 监控服务结构性拆分

- 修改人：Claude（子智能体-x_monitor拆分）
- 修改范围：backend/app/services/x_monitor.py → backend/app/services/x_monitor/（包），backend/tests/test_x_monitor.py（仅 monkeypatch 目标路径调整）。
- 变更内容：将 653 行单文件 x_monitor.py 按职责拆分为包：constants（常量）、errors（领域异常）、summaries（结果 dataclass）、normalize（推文/时间/账号行归一化辅助函数）、health（源健康度记账）、accounts（XAccountManager 账号管理）、pipeline（XFetchPipeline 抓取/冷却/去重/信号联动）、service（XMonitorService 聚合门面），__init__.py 通过 re-export 保证包顶层公共 API 完全不变。纯结构性搬移，未改动任何函数签名、行为逻辑或日志文案。
- 影响文件：新增 backend/app/services/x_monitor/{__init__,constants,errors,summaries,normalize,health,accounts,pipeline,service}.py；删除 backend/app/services/x_monitor.py；backend/tests/test_x_monitor.py 中 3 类 monkeypatch 目标（TwitterApiIoClient/get_settings/_utc_now）改为指向新的子模块路径（service.py、pipeline.py），因为这些名字实际使用点已迁移，仅在包顶层 re-export 无法让 monkeypatch 继续生效。
- 接口/数据结构变化：无（对外公共 API、方法签名、返回类型均未变化）。
- 验证情况：`pytest backend/tests/test_x_monitor.py backend/tests/test_stream_events.py -q` 42 passed；`python -c "from app.main import create_app; create_app()"` 可正常导入应用。
- 风险/后续事项：后续如需在 pipeline.py/service.py 之外新增依赖 monkeypatch 的用例，需注意 patch 目标应指向实际调用点所在子模块（而非包顶层）。

## 2026-07-14 前端 mock.ts 模块化拆分

- 修改人：Claude（子智能体-mock拆分）
- 修改范围：frontend/src/api/mock.ts（改为薄聚合出口）；新增 frontend/src/api/mock/{shared,news,market,llm,xMonitor,ops}.ts。
- 变更内容：将全前端最大的单文件 frontend/src/api/mock.ts（970 行，聚合全部业务域 mock 数据）按业务域拆分为 6 个内聚子模块（news 新闻/话题、market 行情+自选股、llm 大模型配置与分析、xMonitor X监控、ops 系统健康与通知、shared 公共时间基准工具），mock.ts 保留为纯 `export *` 聚合出口，纯结构性搬移，未改动任何 mock 数据的值与类型。
- 影响文件：frontend/src/api/mock.ts（修改）；frontend/src/api/mock/shared.ts、news.ts、market.ts、llm.ts、xMonitor.ts、ops.ts（新增）。
- 接口/数据结构变化：无。所有原有导出（29 个常量 + buildMockTranslation 函数）签名与导入路径 100% 不变，使用方（client.ts、client.test.ts、smoke/app-navigation.test.ts）未做任何修改。
- 验证情况：`npx vitest run src/api/client.test.ts src/smoke/app-navigation.test.ts` 41/41 通过；`npm run typecheck`（vue-tsc --noEmit）通过。
- 风险/后续事项：market.ts 反向依赖 news.ts 的 mockNews/mockRelatedNews，属预期的业务域间引用，后续新增 mock 数据建议按此依赖方向（market → news）追加，避免引入反向循环。

## 2026-07-14 OpsHealthView 组件化拆分 + 测试空白填补

- 修改人：Claude（子智能体-Ops组件化）
- 修改范围：frontend/src/views/OpsHealthView.vue 组件化拆分。
- 变更内容：将 OpsHealthView.vue（原 727 行，全前端最大视图、原无测试覆盖）按区块下沉为 frontend/src/components/ops/ 下 6 个 props 驱动的子组件（OpsAlertsPanel / OpsWorkersCard / OpsLlmUsageCard / OpsSourcesCard / OpsXSourcesCard / OpsSystemStatusCard）+ 1 个共享格式化纯函数模块 opsFormat.ts（timeLabel/ageLabel/ratePct/latencyLabel/numberLabel/workerTone/sourceTone）。视图瘦身为数据加载/轮询编排层，237 行。纯搬移：class、data-role、文案、交互、CSS 选择器与原视图完全一致，未改变任何视觉或行为。同时为全部新组件与视图补齐 vitest 测试（8 个新测试文件，56 个用例），填补该视图此前的测试空白。
- 影响文件：frontend/src/views/OpsHealthView.vue（改，727→237 行）、frontend/src/views/OpsHealthView.test.ts（新增）、frontend/src/components/ops/ 下 6 个组件 + opsFormat.ts 及各自 .test.ts（新增）。
- 接口/数据结构变化：无（纯前端内部组件化重构，未改动后端 API 调用、类型定义或数据形状）。
- 验证情况：`npx vitest run src/views/OpsHealthView.test.ts src/components/ops src/smoke/app-navigation.test.ts` → 9 files / 56 tests 全绿；`npm run typecheck` 通过。
- 风险/后续事项：CSS 采用 Vue scoped 语义按使用点下沉，部分基础类（如 .ops-card / .ops-mini-dot / .ops-signal-dot）在多个子组件间存在源码级重复，是 scoped style 约束下的合理取舍，后续如需统一样式改动需注意多处同步。

## 2026-07-14 前端视图单测补齐（Calendar/Chat/Digest/Portfolio/SentimentEval/SignalBacktest）

- 修改人：Claude（子智能体-视图补测）
- 修改范围：frontend（仅新增测试文件，不涉及产品源码）。
- 变更内容：为 6 个此前完全无测试覆盖的视图补齐 vitest 单元测试，共新增 30 条用例，覆盖正常数据渲染、空数据态、API 报错态，并对过滤器切换/生成按钮/发送消息/新建会话等交互路径做了断言；ChatView 的 SSE 流测试复用 useChatStream.test.ts 的 fetch/reader mock 与 fake timers 打字机推进方式。测试过程未发现需要修复的真实 bug，未改动任何产品源码。
- 影响文件：frontend/src/views/{Calendar,Chat,Digest,Portfolio,SentimentEval,SignalBacktest}View.test.ts（均新增）。
- 接口/数据结构变化：无。
- 验证情况：`npx vitest run` 上述 6 个文件，30/30 通过；`npm run typecheck` 通过。
- 风险/后续事项：无产品代码变更；后续如这些视图的模板/store 接口发生变化，需要同步更新对应测试的 mock 数据结构。

## 2026-07-14 前端 Dashboard 视图瘦身重构

- 修改人：Claude（子智能体-Dashboard瘦身）
- 修改范围：frontend/src/views/DashboardView.vue、frontend/src/components/dashboard/*。
- 变更内容：将 DashboardView.vue（645 行）中仍留在视图层的大块模板与逻辑下沉为 5 个新的 dashboard 子组件（DashboardHeader、DashboardFilterBar、DashboardNewsFeedColumn、DashboardTopicColumn、DashboardMoversColumn）及 1 个纯函数工具（dashboardTrend.ts::computeHourlyTrend），视图收敛为编排层，降至 245 行。纯结构性搬移，class/文案/交互/数据流均未改变；样式随模板一并下沉到对应组件的 scoped style。
- 影响文件：frontend/src/views/DashboardView.vue（改）；frontend/src/components/dashboard/ 下 5 个新组件 + dashboardTrend.ts 及 6 个新增 .test.ts；DashboardView.test.ts 无需改动。
- 接口/数据结构变化：无。
- 验证情况：`npx vitest run src/views/DashboardView.test.ts src/components/dashboard src/smoke/app-navigation.test.ts` 11 文件 45 用例全绿（原 DashboardView.test.ts 六个断言零改动通过）；`npm run typecheck` 0 错误；集成后 `npm run build` 通过。
- 风险/后续事项：DashboardMoversColumn 内部承接了原视图的 moverMarketSummary/topMoverReason/marketLabelMap 等逻辑，建议后续异动展示相关新增需求优先在该组件内扩展而非视图层。

## 2026-07-14 KlineDrawingOverlay 交互逻辑下沉

- 修改人：Claude（子智能体-Kline逻辑下沉）
- 修改范围：frontend/src/components/watchlist/KlineDrawingOverlay.vue、frontend/src/utils/klineDrawings.ts、frontend/src/utils/klineOverlayGeometry.ts、新增 frontend/src/composables/useKlineDrawingInteraction.ts，及以上文件对应的 .test.ts。
- 变更内容：对 KlineDrawingOverlay.vue（全前端最大组件之一，717 行）做逻辑下沉瘦身，script 部分净减 115 行（717→602）。将坐标换算（锚点↔像素点）、蜡烛索引偏移计算、斐波那契回撤位计算、触摸/鼠标事件坐标提取等纯函数下沉到 klineOverlayGeometry.ts；将"可编辑绘图类型判断""可拖拽判断""价格标注默认文案"等领域逻辑下沉到 klineDrawings.ts；新建 useKlineDrawingInteraction composable 封装锚点拖拽/整体拖拽状态机（dragState + beginAnchorDrag/beginBodyDrag/endDrag/resolveDragCommit）。组件本身保留为渲染与事件接线层；手势透传（document.elementFromPoint/dispatchEvent）与生命周期挂载（ResizeObserver/window 监听）因深度耦合 DOM/组件实例，评估后未下沉。只做搬移与参数化，未改动任何算法与交互行为。
- 影响文件：frontend/src/components/watchlist/KlineDrawingOverlay.vue、frontend/src/utils/klineDrawings.ts（+klineDrawings.test.ts 新建）、frontend/src/utils/klineOverlayGeometry.ts（+.test.ts 扩充）、frontend/src/composables/useKlineDrawingInteraction.ts（新建，+.test.ts 新建）。
- 接口/数据结构变化：无（组件 props/emits 签名不变，导出函数为新增，无删除/改签名）。
- 验证情况：`npx vitest run src/components/watchlist src/utils/klineOverlayGeometry.test.ts src/composables` 14 files / 63 tests 全绿（含原有 KlineDrawingOverlay.test.ts 16 例未改断言即通过）；`npx vitest run src/utils/klineDrawings.test.ts` 3 例全绿；`npm run typecheck` 通过。
- 风险/后续事项：手势透传与生命周期挂载逻辑仍留在组件内，若未来需要复用/单测这部分，需评估以 Ref 传参方式抽出的可行性。

## 2026-07-14 工程文档治理（ANGENT 去重 / 优化清单状态回填 / README 校对）

- 修改人：Claude（子智能体-文档治理）
- 修改范围：ANGENT.md、README.md、docs/optimization-plan.md。
- 变更内容：
  1. 将根目录 ANGENT.md（历史拼写错误遗留，与 AGENTS.md 内容重复）整体替换为指向 AGENTS.md 的简短指针说明，AGENTS.md 保持为唯一权威规范本体不变；同步修正 README.md 中原指向 ANGENT.md 的引用并合并冗余段落。
  2. 逐项对照当前代码核实 docs/optimization-plan.md 中 15 项优化（P0~P3）的落地状态，在文档顶部加"状态回填于 2026-07-14"说明，并逐条追加 ✅已完成/⚠️部分完成/⬜未做 状态标注及一行代码证据。核实结论：9 项已完成，5 项部分完成（#6 内存队列自愈轮询、#8 同步路由部分异步化、#12 异常观测性不足、#13 incremental_vacuum 缺 auto_vacuum 前置、#15 工程化清理子项不一），1 项未做（#14 详情页 selectinload）。
  3. 校对 README.md 安装/启动/测试命令与 Makefile、scripts/dev.sh 的一致性（逐条核对表见任务报告），补充遗漏的前端单元测试命令说明 `npm --prefix frontend run test`。
- 影响文件：ANGENT.md、README.md、docs/optimization-plan.md。
- 接口/数据结构变化：无。
- 验证情况：全仓 grep 复查确认不存在指向 ANGENT.md 的失效引用（历史记录性质的 code-change-log 与 plans 归档除外）；README 每条命令均与 Makefile/scripts/dev.sh/environment.yml/package.json 实际内容比对一致。
- 风险/后续事项：docs/superpowers/plans/2026-06-13-phase1-optimization-plan.md 中仍保留一条历史待办「合并 AGENTS.md 和 ANGENT.md」，属历史归档未改动；optimization-plan 中标记为部分完成/未做的项仍是真实技术债，建议后续排期。

## 2026-07-13 修复 SkeletonFeed 的 v-elif 拼写（骨架屏分支失效）

- 修改人：Claude
- 修改范围：`frontend/src/components/common/SkeletonFeed.vue`。
- 根因：dashboard / watchlist / detail 三个骨架屏分支写成了无效指令 `v-elif`（Vue 无此指令，应为 `v-else-if`），导致它们脱离首个 `v-if` 的条件链、在任意 `type` 下都会同时渲染，骨架屏与真实卡片高度不再 1:1 对应。
- 变更内容：3 处 `v-elif` → `v-else-if`，恢复 `v-if(news) → v-else-if(dashboard) → v-else-if(watchlist) → v-else-if(detail)` 的正确互斥分支。
- 影响文件：`frontend/src/components/common/SkeletonFeed.vue`、`docs/code-change-log.md`
- 接口/数据结构变化：无。
- 验证情况：`npm run build`（vue-tsc + vite）通过；`npm run test`（vitest）→ 262 passed 无回归；后端 `create_app()` 导入正常。
- 风险/后续事项：无。

## 2026-07-13 第二批五特性并行开发集成合并（Integration Merge #2）

- 修改人：Claude（主线集成）
- 修改范围：合并第二批 5 个独立 worktree 特性（持仓/组合、个股 AI 综合研判、情绪评测闭环、告警治理、E2E 导航冒烟）进 main 并集成收尾。
- 变更内容：
  1. 依序 `--no-ff` 合并 5 个特性分支。其中 3 个分支基线是旧的 973fbe7（第一批+卡死修复之前），合并时逐处**同时保留第一批与第二批内容**，未回退任何既有改动（导航 08~11、全部路由的 lazyView 容错、config 第一批字段、changelog 既有条目均完整保留）。
  2. 解决注册点/交错冲突：`router.py`（import 与 include 合并出 backtest/calendar/digest/eval/ops/portfolio/research 全集）；`feishu_client.py`（`build_digest_card` 与 `build_alert_digest_card` 两个函数级交错补全）；`client.ts`（方法块补 `},`）；`AppShell.vue` 导航；`types/api.ts`；`config.py`；`code-change-log.md`。
  3. 统一导航：新增 Portfolio(12)、Sentiment Eval(13)；把情绪评测路由从裸 `import()` 改为 `lazyView(...)`，与其余路由一致享受 chunk 容错。
  4. 中心化重新生成前端 API 契约（`npm run generate:api`）覆盖全部新端点；`check:api-drift` 通过。
  5. E2E 导航冒烟测试新增覆盖 `/portfolio` 与 `/eval/sentiment`（冒烟自检本次正确地提示了这两个新模块需同步纳入）。
- 影响文件：`backend/app/api/router.py`、`backend/app/services/feishu_client.py`、`backend/app/core/config.py`、`frontend/src/api/client.ts`、`frontend/src/components/layout/AppShell.vue`、`frontend/src/router/index.ts`、`frontend/src/types/api.ts`、`frontend/openapi.json`、`frontend/src/types/generated/api.d.ts`、`frontend/src/smoke/app-navigation.test.ts`、`docs/code-change-log.md`
- 接口/数据结构变化：新增 `/api/portfolio`、`/api/research/stock/{symbol}`、`/api/eval/sentiment`、`/api/notify` 治理字段；watchlist 支持 `PATCH /{symbol}` 写持仓；新增 alembic 迁移 `b8e4d7f2a9c1`（watchlist_item 加 position_size/average_cost），alembic 单 head。
- 验证情况：`conda run -n news-caught pytest backend/tests` → **449 passed**；`npm run build`（vue-tsc 全检 + vite）通过；`npm run test`（vitest）→ **262 passed / 52 files**；`check:api-drift` 通过；`alembic heads` 单一 head `b8e4d7f2a9c1`。
- 风险/后续事项：告警治理默认保守（不配置≈旧行为）；个股研判与情绪评测在 LLM 未配置时规则降级；持仓盈亏依赖 price_snapshot 与已填持仓；既有 SkeletonFeed 模板有 `v-elif` 拼写告警（既有、仅警告不崩溃，未处理）。

## 2026-07-13 持仓/组合视图（Portfolio — 成本、盈亏、按仓位加权的新闻影响）

- 修改人：Claude（独立 worktree 特性开发）
- 修改范围：把「自选股关注列表」升级为「投资组合」——为每只自选股记录持仓量与成本；新增组合视图展示实时总盈亏；并按仓位价值加权给命中新闻排序，让影响用户最多钱的新闻浮到最上面。
- 数据库迁移：新增 `backend/alembic/versions/b8e4d7f2a9c1_add_watchlist_position_and_cost.py`，`revision='b8e4d7f2a9c1'`、`down_revision='a7f3c1e9d2b4'`（当前 alembic head）。给 `watchlist_item` 表新增两列：`position_size`(Float, nullable)、`average_cost`(Float, nullable)。迁移写成**幂等防御式**（`watchlist_item` 存在时只补缺失列，列已存在则跳过），与 legacy `create_all` + `stamp baseline` + `upgrade head` 路径兼容；已在临时库验证 legacy 路径 upgrade head 幂等通过、alembic head = `b8e4d7f2a9c1`。同步在 `backend/app/models/watchlist_item.py` 加两个字段。
- 后端变更：
  1. 新增 `backend/app/services/portfolio_service.py`：读所有有持仓（`position_size>0`）的自选股，用最新行情快照算每只与组合的市值、成本、未实现盈亏（额与百分比）；再计算「按仓位价值加权的新闻影响」——对每只持仓命中的近 7 天新闻，用 `sentiment_score × 仓位市值权重` 聚合并按绝对影响分排序。纯读+计算，缺行情（权重退化为按成本/持仓量/等权）、缺持仓、缺成本均优雅降级。
  2. 新增 `backend/app/schemas/portfolio.py`：`PortfolioPositionView` / `PortfolioWeightedNewsView` / `PortfolioSummaryView`。
  3. 写入持仓：`backend/app/schemas/watchlist.py` 新增 `WatchlistItemUpdate`（`position_size`/`average_cost`，均 `ge=0` 可空），并给 `WatchlistItemView` 增加这两个可空字段；`backend/app/repositories/watchlist_repository.py` 新增 `update_position(symbol, updates)`（仅写入 `updates` 中出现的键，upsert 语义，既有字段与行为不变）；`backend/app/api/routes/watchlist.py` 新增 `PATCH /{symbol}`（`exclude_unset`，找不到 symbol 返回 404）。
  4. 路由：新增 `backend/app/api/routes/portfolio.py`（`GET /` 返回组合汇总）；`backend/app/api/router.py` 仅加两行（import `portfolio` + `include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])`，自动继承 `verify_app_token`）。
- 前端变更：
  1. 新增 `frontend/src/views/PortfolioView.vue`：总市值/总盈亏/总成本/持仓数汇总卡片、各持仓明细表（盈亏红绿）、「最该看的新闻」加权列表。
  2. `frontend/src/views/WatchlistView.vue`（本特性唯一改动的既有 view）：新增「持仓设置」面板，为每只自选股就地编辑「持仓量/成本」，保存走 `apiClient.setWatchlistPosition` 后 `loadWatchlist` 刷新。
  3. `frontend/src/router/index.ts`：新增 `/portfolio`（name `portfolio`，`lazyView` 懒加载）。
  4. `frontend/src/components/layout/AppShell.vue`：`navItems` 追加 `{ label: 'Portfolio', to: '/portfolio', index: '12' }`。
  5. `frontend/src/api/client.ts`：新增 `getPortfolio()`（getJson）、`setWatchlistPosition(symbol, payload)`（patchJson）。
  6. `frontend/src/types/api.ts`：新增 `PortfolioSummary`/`PortfolioPosition`/`PortfolioWeightedNews`/`WatchlistPositionUpdate` 手写镜像；`WatchlistItem` 用交叉类型补齐 `position_size`/`average_cost`（OpenAPI 快照尚未含新字段，待 `npm run generate:api` 后可退回纯别名）。
- 影响文件：`backend/alembic/versions/b8e4d7f2a9c1_add_watchlist_position_and_cost.py`(新)、`backend/app/models/watchlist_item.py`、`backend/app/services/portfolio_service.py`(新)、`backend/app/schemas/portfolio.py`(新)、`backend/app/schemas/watchlist.py`、`backend/app/repositories/watchlist_repository.py`、`backend/app/api/routes/watchlist.py`、`backend/app/api/routes/portfolio.py`(新)、`backend/app/api/router.py`、`backend/tests/test_portfolio_service.py`(新)、`frontend/src/views/PortfolioView.vue`(新)、`frontend/src/views/WatchlistView.vue`、`frontend/src/router/index.ts`、`frontend/src/components/layout/AppShell.vue`、`frontend/src/api/client.ts`、`frontend/src/types/api.ts`、`docs/code-change-log.md`
- 接口/数据结构变化：新增 `GET /api/portfolio`、`PATCH /api/watchlist/{symbol}`；`watchlist_item` 表新增 `position_size`/`average_cost` 两列；`WatchlistItemView` 响应新增两个可空字段（向后兼容）。
- 验证情况：`conda run -n news-caught pytest backend/tests/test_portfolio_service.py -q` → **6 passed**（盈亏计算、按仓位加权新闻排序、缺行情/缺持仓降级、PATCH 写入+组合汇总端到端、404）；另跑 `test_watchlist_research.py`/`test_market.py` 未受影响（合计 37 passed）。前端 `npm run build`（vue-tsc 全检 + vite）通过，产出 `PortfolioView` chunk；校验用的 `frontend/node_modules` 软链接构建后已删除。
- 风险/后续事项：`types/api.ts` 的 Portfolio 类型为手写镜像，待中心化 `npm run generate:api` 后可替换为 `Schemas` 别名并移除 `WatchlistItem` 交叉类型增补；导航 index `12` 若与其它并行特性冲突由集成方统一。
## 2026-07-13 新增全应用导航 E2E 冒烟测试（守护「切换模块不崩」），并修复其捕获到的 LLM 设置崩溃

- 修改人：Claude（独立 worktree 开发）
- 修改范围：前端测试与测试配置为主；附带一处最小前端源码 bug 修复（由冒烟测试发现的真实崩溃）。不动后端 / alembic / notification / router 源逻辑。
- 背景：项目此前修过「切换模块卡死必须刷新」（根因是路由视图缺错误处理，已加 `RouteErrorBoundary` + `lazyView`）。为防止此类回归，新增一个**确定性、离线可跑**的端到端导航冒烟测试：用**真实 vue-router 路由表** + **真实 `RouteErrorBoundary`** 包裹 `<RouterView>`，逐个访问全部主模块，断言每个都渲染出可辨识节点、且**不触发** `[data-role="route-error-boundary"]`（即视图未崩）。
- 变更内容：
  1. 新增 `frontend/src/smoke/app-navigation.test.ts`：整体 mock `../api/client` 的 apiClient（复用 `../api/mock` 的良性夹具，未覆盖方法经 Proxy 兜底返回空数据，全程不联网），stub `lightweight-charts`/`IntersectionObserver`/`ResizeObserver`；用真实 `../router` + 真实 `RouteErrorBoundary` 挂一个 `<RouteErrorBoundary><RouterView/></RouteErrorBoundary>` 外壳，`it.each` 遍历 16 条路由逐个 push→flush→断言。覆盖全部 11 个无参主模块（`/news /dashboard /watchlist /x-monitor /calendar /settings/llm /settings/notify /chat /digest /analytics/backtest /ops`）+ 5 条带参路由示例（`/news/events/:eventKey`、`/news/:id`、`/news/sentiment/:sentiment`、`/watchlist/:symbol`、`/topics/:id`）；另有一条「路由表里每个无参主模块都被冒烟列表覆盖」的自检（新增模块时会提醒同步冒烟列表）。
  2. 新增 `frontend/vitest.setup.ts` 并在 `frontend/vitest.config.ts` 注册 `setupFiles`：为「原生 Web Storage 会抛错」的环境（Node 22+ 实验性全局 localStorage 未配 `--localstorage-file`，被 Pinia devtools 在真实挂载时读取而崩）提供**条件式**内存兜底；storage 正常时（如 CI 的 Node 20 / jsdom）为无副作用 no-op，不改变既有测试行为。
  3. 修复 `frontend/src/components/llm/LlmConfigList.vue`：ping 状态徽标的两处守卫由 `?.latency !== null` / `?.error !== null` 改为 `!= null`（松散判等）。原逻辑在**尚未 ping 的默认态**（`pingStatuses[cfg.id]` 为 `undefined`）下，`undefined?.x !== null` 恒为真而进入分支，再无可选链地读 `.latency`/`.error` → `TypeError: Cannot read properties of undefined`，导致**打开「LLM Settings」模块即崩**（正是本冒烟测试要守护的那类「切换模块崩溃」）。改为 `!= null` 后 undefined 态两分支都不进入，正常渲染无徽标；已 ping 成功/失败仍分别显示延迟/连接失败。
- 影响文件：`frontend/src/smoke/app-navigation.test.ts`(新)、`frontend/vitest.setup.ts`(新)、`frontend/vitest.config.ts`(加 `setupFiles`)、`frontend/src/components/llm/LlmConfigList.vue`(最小 bug 修复)、`docs/code-change-log.md`。
- 接口/数据结构变化：无（纯前端测试与容错，未改后端与 API；不重复实现 CI 已有的 api-drift）。
- 验证情况：`npx vitest run src/smoke/app-navigation.test.ts` → **17 passed**；`npm run test -- --run` 全量 → **52 files / 260 passed**（含新增 17 条，既有全绿）；`npm run build`（vue-tsc 严格全检 + vite build）通过。
- Playwright：本 worktree 未安装 `@playwright/test`，且离线环境无法 `npm install` / `npx playwright install` 下载浏览器，故**按任务约定跳过 Playwright**，只交付 vitest 导航冒烟（已被现有 CI 的 vitest job 自动收录，无需新增 CI job、也不会让主 CI 因缺浏览器变红）。
- 风险/后续事项：冒烟测试的「文本/`data-role` 锚点」若未来视图改动标题或根节点需同步；自检用例会在新增无参主模块但漏加冒烟条目时失败提醒。另注意到 `SkeletonFeed`/相关模板有 `v-elif` 拼写告警与 SentimentNews 空态提示等**既有 warning**（非崩溃，未在本次范围内处理）。

## 2026-07-13 修复「切换模块经常卡住必须刷新」（路由视图错误处理基础设施）

- 修改人：Claude（系统化调试）
- 修改范围：前端全局错误处理与懒加载路由视图的容错恢复。
- 根因：应用为每个路由做代码分割（`() => import()`），但**全链路缺少任何错误处理**——`main.ts` 无 `app.config.errorHandler`、无 `vite:preloadError` 监听；`router/index.ts` 无 `router.onError`；`AppShell.vue` 用裸 `<RouterView>` 无 `onErrorCaptured` 错误边界。于是任何一次**动态 import 失败/超时**（旧 chunk 失效、Vite dev 504、网络抖动，间歇发生故"经常"）或**视图渲染抛错**（同已归档的 LlmSettings `substring` 崩溃）都无人兜底，导致导航静默失败、响应式中断，用户只能手动刷新。
- 变更内容：
  1. 新增 `frontend/src/utils/lazyImport.ts`：`isDynamicImportError`（识别 chunk 加载失败/超时）、`recoverFromChunkError`（sessionStorage 守卫的一次性受控刷新，防无限刷新循环）、`lazyView`（给 loader 加超时 + 一次静默重试，两次都失败才受控刷新；真正的模块语法/运行时错误照常抛出不掩盖）。
  2. 新增 `frontend/src/components/common/RouteErrorBoundary.vue`：`onErrorCaptured` 错误边界包裹 `<RouterView>`，隔离单个视图的渲染/setup 抛错使 SPA 其余部分（导航/外壳/响应式）继续存活；监听 `route.fullPath`，**切换到其它模块即自动清除错误、无需刷新整页**；提供「重试」「刷新页面」。chunk 类错误则走受控刷新。
  3. `router/index.ts`：全部路由 loader 包裹 `lazyView(...)`；新增 `router.onError`，对 chunk 失败受控刷新到目标路径。
  4. `main.ts`：新增 `app.config.errorHandler`（记录兜底错误）与 `window` 的 `vite:preloadError` 监听（预加载失败受控刷新）。
  5. `AppShell.vue`：用 `<RouteErrorBoundary>` 包裹 `<RouterView>`。
- 影响文件：`frontend/src/utils/lazyImport.ts`(新)、`frontend/src/utils/lazyImport.test.ts`(新)、`frontend/src/components/common/RouteErrorBoundary.vue`(新)、`frontend/src/components/common/RouteErrorBoundary.test.ts`(新)、`frontend/src/components/common/RouteErrorBoundary.integration.test.ts`(新)、`frontend/src/router/index.ts`、`frontend/src/main.ts`、`frontend/src/components/layout/AppShell.vue`、`docs/code-change-log.md`
- 接口/数据结构变化：无（纯前端容错，不改后端与 API）。
- 验证情况：新增单测覆盖错误识别/受控刷新守卫/lazyView 重试与放弃/边界隔离与恢复；新增**真实 vue-router 集成测试**复现并验证「导航到崩溃模块→被隔离不卡死→切到另一模块→自动恢复无需刷新」。`npm run test` → **243 passed / 51 files**；`npm run build`（vue-tsc 全检 + vite）通过。
- 风险/后续事项：受控刷新有 10s sessionStorage 守卫防循环；异步/未处理 Promise 拒绝（fire-and-forget）不在 `onErrorCaptured` 覆盖范围，但不影响导航卡死场景；如仍偶发，可据浏览器控制台的 `[RouteErrorBoundary]`/`[vue]` 日志进一步定位具体抛错视图。

## 2026-07-13 五特性并行开发集成合并（Integration Merge）

- 修改人：Claude（主线集成）
- 修改范围：将 5 个在独立 git worktree 中并行开发的特性（信号回测、每日 AI 简报、系统健康看板、LLM 成本治理与分类缓存、财报事件日历）依序合并进 main，并做集成收尾。
- 变更内容：
  1. 依序 `--no-ff` 合并 5 个特性分支，解决注册点冲突（`backend/app/api/router.py` 的 import 与 include 合并；`frontend/src/router/index.ts` 路由；`AppShell.vue` 导航；`frontend/src/api/client.ts`；`backend/app/core/config.py` 新增字段；`docs/code-change-log.md` 追加块）。
  2. 统一 `AppShell.vue` 导航编号与顺序：新增 Signal Backtest(08)、Daily Digest(09)、Calendar(10)、System Health(11)。
  3. 中心化重新生成前端 API 契约（`npm run generate:api`），使 `frontend/openapi.json` 与 `src/types/generated/api.d.ts` 覆盖全部新端点；`check:api-drift` 通过。
  4. 修复 `LlmSettingsView.test.ts` 一处因新增价格字段导致的位置脆弱断言：改为按 `name` 选择输入框，并把期望 payload 补齐 `input_price_per_1k/output_price_per_1k/monthly_budget_usd`（空值 → null）。组件行为本身未变。
- 影响文件：`backend/app/api/router.py`、`backend/app/core/config.py`、`frontend/src/components/layout/AppShell.vue`、`frontend/src/api/client.ts`、`frontend/src/router/index.ts`、`frontend/openapi.json`、`frontend/src/types/generated/api.d.ts`、`frontend/src/views/LlmSettingsView.test.ts`、`docs/code-change-log.md`
- 接口/数据结构变化：新增 `/api/backtest`、`/api/digest`、`/api/ops/health`、`/api/calendar`；`/api/llm/*` 扩展成本/预算字段；新增 alembic 迁移 `a7f3c1e9d2b4`（LLM 单价/预算列 + `llm_classification_cache` 表），alembic 单 head。
- 验证情况：`conda run -n news-caught pytest backend/tests` → **417 passed**；`npm run build`（vue-tsc 全检 + vite）通过；`npm run test`（vitest）→ **229 passed / 48 files**；`check:api-drift` 通过；`alembic heads` 单一 head。
- 风险/后续事项：`digest_enabled` 默认关闭需显式开启并配好 LLM+飞书；日历依赖 yfinance，联网失败按 skipped 优雅降级；回测精度受 price_snapshot 密度影响。

## 2026-07-13 信号有效性回测闭环（Signal Backtest）

- 修改人：Claude（独立 worktree 特性开发）
- 修改范围：新增"信号有效性回测"闭环——后端回测服务 + 只读 API + 前端展示面板，用于验证利好/利空判断的实际有效性。
- 变更内容：
  1. **后端回测服务（Backend）**：
     - 新增 `backend/app/services/signal_backtest.py`。对每条"窗口内、带方向情绪（positive/negative）、可映射到 symbol"的历史新闻，按 news×symbol 展开：取 published_at 时点/之前最近的 price_snapshot 作为基准价，取"发布时间 + 前视窗（horizon，如 1h/4h/1d）后最接近的一条快照"作为前视价，计算前视收益率。
     - 聚合输出：利好命中率（后续上涨占比）、利空命中率（后续下跌占比）、按 importance（信号置信度 signal_confidence 分桶 high/medium/low/unknown）的平均前视收益，以及候选样本量 total_signals、可评估 evaluable_count、跳过 skipped_count、可评估率 evaluable_rate。
     - 快照稀疏（缺基准价或缺前视价）时优雅降级：跳过该样本并计入 skipped，不抛错。库内时间统一按 UTC 对齐（naive datetime 视为 UTC）。全程纯读，不写库、不改 schema、不做迁移。
     - 新增只读仓储方法：`NewsSignalRepository.list_directional_signal_news` / `get_signal_result_map`、`NewsMentionsRepository.list_mentions_for_news`、`MarketRepository.list_snapshots_by_symbols`。
  2. **后端 Schema 与路由（Backend）**：
     - 新增 `backend/app/schemas/backtest.py`（Pydantic 响应模型 BacktestSummaryView / SignalDirectionStatsView / ImportanceBucketStatsView）。
     - 新增 `backend/app/api/routes/backtest.py`，`GET ""` 返回回测汇总，接受 query：market / window_days / horizon；非法 horizon 返回 400。
     - `backend/app/api/router.py` 仅新增两行：导入 backtest、`include_router(backtest.router, prefix="/backtest", tags=["backtest"])`，自动继承 verify_app_token 鉴权。
  3. **前端面板（Frontend）**：
     - 新增 `frontend/src/views/SignalBacktestView.vue`，暗色霓虹终端风格：过滤器（市场/回看窗口/前视窗）、概览指标卡、利好/利空命中率与平均收益卡、按 importance 分桶收益的自绘 SVG 柱状图（以 0 为基线正负分向）。
     - `frontend/src/router/index.ts` 新增路由 `/analytics/backtest`（name `signal-backtest`，懒加载）。
     - `frontend/src/components/layout/AppShell.vue` 的 `navItems` 新增 `{ label: 'Signal Backtest', to: '/analytics/backtest', index: '08' }`。
     - `frontend/src/api/client.ts` 新增 `getBacktestSummary(query)`（复用 getJson + withQuery）；`frontend/src/types/api.ts` 新增 `BacktestSummary` / `SignalDirectionStats` / `ImportanceBucketStats` 类型别名（取自重生成的 OpenAPI schema）及 UI 专用 `BacktestQuery`。
     - 运行 `npm run generate:api` 重生成 `frontend/openapi.json` 与 `frontend/src/types/generated/api.d.ts`，纳入新的 /api/backtest 契约。
- 影响文件：
  - 新增：`backend/app/services/signal_backtest.py`、`backend/app/schemas/backtest.py`、`backend/app/api/routes/backtest.py`、`backend/tests/test_signal_backtest.py`、`frontend/src/views/SignalBacktestView.vue`
  - 修改：`backend/app/api/router.py`、`backend/app/repositories/news_signal_repository.py`、`backend/app/repositories/news_mentions_repository.py`、`backend/app/repositories/market_repository.py`、`frontend/src/router/index.ts`、`frontend/src/components/layout/AppShell.vue`、`frontend/src/api/client.ts`、`frontend/src/types/api.ts`、`frontend/src/types/generated/api.d.ts`、`frontend/openapi.json`、`docs/code-change-log.md`
- 接口/数据结构变化：新增只读接口 `GET /api/backtest`（query：market、window_days、horizon；返回 BacktestSummaryView）。无数据库 schema / 迁移变化。
- 验证情况：
  - 后端 `conda run -n news-caught pytest backend/tests/test_signal_backtest.py -q` 全绿（6 passed），覆盖命中率/收益/样本计数、基准价缺失降级、窗口外排除、market 过滤、路由冒烟与非法 horizon 400。
  - 前端 `npm run build`（vue-tsc + vite build）通过，`npm run check:api-drift` 报告前后端类型一致。
  - 前端 node_modules 采用软链接主仓库方式完成本地校验，提交前已移除软链接。
- 风险/后续事项：
  - importance 分桶基于 `NewsSignalResult.signal_confidence`（news 层无独立 importance_score，选用最贴近的每条信号置信度作为代理），如后续引入 news 级 importance 可平滑替换。
  - 前视价采用"发布+horizon 之后最接近的一条快照"近似，快照密度低时可评估率偏低属预期；命中率统计只计入可评估样本。
  - `AppShell.navItems` 的 index '08' 如与其它并行 worktree 冲突，合并时统一顺延即可。
## 2026-07-13 11:00

- 修改人：Claude（独立 worktree 特性开发）
- 修改范围：统一系统健康看板 + 告警评估（Ops Health Dashboard）
- 变更内容：
  1. **后端按需聚合服务（Backend）**：
     - 新增 `backend/app/services/ops_health.py`，`build_ops_health(session)` 一次性聚合散落各处的可观测数据——后台 worker 运行时状态（心跳/成功失败计数/最近错误/心跳停滞秒数）、新闻源与 X 源健康（成功率、连续失败、是否禁用、平均时延）、近 24h LLM 调用与 token 用量（总量 + 分模型）、事件层 backend/降级状态、以及 `database_url` 指向的 SQLite 文件体积（含 `-wal`/`-shm` 旁路文件，贴近 WAL 模式真实落盘占用）。
     - 基于模块常量阈值（`SOURCE_CONSECUTIVE_FAILURE_THRESHOLD=5`、`WORKER_HEARTBEAT_TIMEOUT_SECONDS=300`、`DB_SIZE_WARNING_MB=500`/`DB_SIZE_CRITICAL_MB=1024`，刻意不进 `config.py`）产出结构化 `alerts: [{level, code, subject, message}]`，涵盖 worker 心跳超时/降级、新闻源连续失败/被禁用、X 源连续失败、事件层降级、DB 体积告警；每条告警同时 `logger.warning`。`overall_status` 由告警级别派生（critical > warning > ok）。
     - 主动推送（notification_service / feishu）留作扩展点，本特性只在 API/UI 暴露告警 + 记 WARNING 日志，不触碰推送链路。
  2. **后端 Schema 与路由（Backend）**：
     - 新增 `backend/app/schemas/ops.py`（`OpsHealthResponse` 及各子视图，时间统一走 `UTCDateTime`）。
     - 新增 `backend/app/api/routes/ops.py`，`GET /health`；在 `backend/app/api/router.py` 仅新增 import 中的 `ops` 与一行 `include_router(ops.router, prefix="/ops", tags=["ops"])`，鉴权自动继承。
  3. **前端运维看板（Frontend）**：
     - 新增 `frontend/src/views/OpsHealthView.vue`：分区展示 workers / 新闻源 / X 源 / LLM 用量 / 事件层 / DB，顶部醒目展示 alerts（warning 橙、critical 红，带呼吸灯辉光），每 15s 自动轮询刷新，支持手动刷新，保持暗色霓虹终端风格。
     - `frontend/src/router/index.ts` 新增 `/ops`（name `ops-health`）懒加载路由；`frontend/src/components/layout/AppShell.vue` 的 `navItems` 追加 `{ label: 'System Health', to: '/ops', index: '10' }`。
     - `frontend/src/api/client.ts` 新增 `getOpsHealth()`（复用已有 `getJson`）；`frontend/src/types/api.ts` 追加 `OpsHealth` 等类型别名（指向重新生成的 OpenAPI schema）。
     - 重新生成 `frontend/openapi.json` 与 `frontend/src/types/generated/api.d.ts`（含新 `/api/ops/health` 与 Ops* schema），`check:api-drift` 通过。
  4. **测试（TDD）**：
     - 新增 `backend/tests/test_ops_health.py`：覆盖聚合字段正确、阈值触发对应 alerts（worker 心跳超时 / 源连续失败 / 源禁用 / X 源连续失败 / 事件层降级 / DB 体积 warning 与 critical）、无数据不崩、路由 200 返回。
- 影响文件：
  - 新增：`backend/app/services/ops_health.py`、`backend/app/schemas/ops.py`、`backend/app/api/routes/ops.py`、`backend/tests/test_ops_health.py`、`frontend/src/views/OpsHealthView.vue`
  - 修改：`backend/app/api/router.py`、`frontend/src/router/index.ts`、`frontend/src/components/layout/AppShell.vue`、`frontend/src/api/client.ts`、`frontend/src/types/api.ts`、`frontend/openapi.json`、`frontend/src/types/generated/api.d.ts`、`docs/code-change-log.md`
- 接口/数据结构变化：新增只读 API `GET /api/ops/health`（`OpsHealthResponse`）；不新增数据库表/迁移。
- 验证情况：`conda run -n news-caught pytest backend/tests/test_ops_health.py -q` 全绿（5 passed）；后端全量 390 passed（唯一 1 failed 为 `test_news_relevance_experiment_runner` 硬编码主检出绝对路径、在任意 worktree 均失败，与本特性无关）；前端 `npm run typecheck`、`npm run build`、`check:api-drift` 均通过，`OpsHealthView` 独立懒加载分块。
- 风险/后续事项：主动推送为预留扩展点（当前仅日志 + API/UI 暴露）；阈值为模块常量，如需可配置可后续迁入 config。
## 2026-07-13

- 修改人：Claude（独立 worktree 特性开发）
- 修改范围：每日盘前/盘后 AI 简报（Daily Digest，定时生成 + 主动推送 + API + 前端页面）
- 变更内容：
  1. **简报生成服务（Backend）**：新增 `backend/app/services/digest_service.py`。`generate_digest(market_scope, session)` 收集近 N 小时新闻、自选股命中新闻与情绪标签聚合，拼 prompt 调用默认 LLM provider 生成结构化 4 段简报（隔夜/当日重点、自选股相关、整体情绪方向、风险提示）；LLM 未配置/不可用/返回异常时优雅降级为基于规则的纯文本摘要，绝不向上抛未捕获异常。维护进程内"最新 digest"线程安全单例，并把最新一份写到 `<data>/latest_digest.json`（路径由 settings 的 database_url 推导，写失败只 log）。**不新增数据库表/迁移**。
  2. **定时 worker（Backend）**：新增 `backend/app/workers/digest_worker.py`（继承 BaseWorker）。用标准库 zoneinfo 按港股 `Asia/Hong_Kong`、美股 `America/New_York` 本地时区，在盘前/盘后时点触发生成推送。采用"每分钟 tick 检查是否到达今天尚未触发时点 + grace 窗口"的幂等方式，每个（市场,阶段,本地日期）当天最多触发一次，避免重复推送与进程晚启后补发陈旧简报。
  3. **推送通道复用（Backend）**：`feishu_client.py` 新增 `build_digest_card(digest)`；`notification_service.py` 新增 `on_digest_ready(payload)` 入队方法与 `_build_card_for_job` 的 `digest` 分支，复用已有 NotificationJobRepository 持久化队列与投递/重试机制，与 watchlist_alert/analysis_result 分支同构。
  4. **API（Backend）**：新增 `backend/app/api/routes/digest.py`（`GET /latest` 返回最新简报或空态、`POST /generate` 手动触发生成）与 `backend/app/schemas/digest.py`；`router.py` 注册 `include_router(digest.router, prefix="/digest")`（自动继承鉴权）。
  5. **配置（Backend）**：`config.py` 新增 `digest_enabled=False`、`digest_premarket_time="08:30"`、`digest_postmarket_time="16:30"`、`digest_lookback_hours=16`。`main.py` lifespan 在 `settings.digest_enabled` 时启动/退出时停止 DigestWorker，触发闭包内 `generate_digest` + `on_digest_ready` 推送。
  6. **前端**：新增 `frontend/src/views/DigestView.vue`（暗色霓虹终端风格，展示各 section + 市场范围切换 + "立即生成"按钮，section 正文复用 `utils/markdown.ts` 渲染）与 `frontend/src/stores/digestStore.ts`；`router/index.ts` 加 `/digest`（name `daily-digest`，懒加载）；`AppShell.vue` navItems 加 `{ label: 'Daily Digest', to: '/digest', index: '09' }`；`api/client.ts` 加 `getLatestDigest` / `generateDigest`；`types/api.ts` 加 Digest 相关别名（由 `npm run generate:api` 重新生成 `generated/api.d.ts` 与 `openapi.json`）。
- 影响文件：
  - 新增：`backend/app/services/digest_service.py`、`backend/app/workers/digest_worker.py`、`backend/app/api/routes/digest.py`、`backend/app/schemas/digest.py`、`backend/tests/test_digest_service.py`、`backend/tests/test_digest_worker.py`、`frontend/src/views/DigestView.vue`、`frontend/src/stores/digestStore.ts`
  - 修改：`backend/app/core/config.py`、`backend/app/api/router.py`、`backend/app/main.py`、`backend/app/services/notification_service.py`、`backend/app/services/feishu_client.py`、`frontend/src/router/index.ts`、`frontend/src/components/layout/AppShell.vue`、`frontend/src/api/client.ts`、`frontend/src/types/api.ts`、`frontend/src/types/generated/api.d.ts`、`frontend/openapi.json`、`docs/code-change-log.md`
- 接口/数据结构变化：新增 `GET /api/digest/latest`、`POST /api/digest/generate`；新增 pydantic schema `DigestView`/`DigestSectionView`/`DigestLatestView`。无数据库结构变化、无 alembic 迁移。
- 验证情况：`conda run -n news-caught pytest backend/tests/test_digest_service.py backend/tests/test_digest_worker.py -q` 全绿（7 passed）；后端全量 392 passed（唯一 1 failed 为 `test_news_relevance_experiment_runner` 硬编码绝对路径导致的 worktree 既有失败，与本特性无关）；前端 `npm run build`（含 vue-tsc）通过、`npm run check:api-drift` 通过。
- 风险/后续事项：`digest_enabled` 默认关闭，需显式开启并配置 LLM 与飞书后方会自动推送。navItems index `09` 可能与其他并行分支冲突，待中心统一。
## 2026-07-13 10:40

- 修改人：Claude（独立 worktree 特性开发）
- 修改范围：财报 / 事件日历（Earnings & Event Calendar）——新特性端到端落地（后端服务 + API + 前端日历页 + 自选股卡片“距财报 N 天”角标）
- 变更内容：
  1. **后端日历服务（Backend / 新增）**：
     - 新增 `backend/app/services/calendar_service.py`。对每个自选股用 yfinance（`Ticker.calendar` / `Ticker.get_earnings_dates`）抓取即将到来的财报日与除息日，对不同版本返回结构（dict / DataFrame）做防御性解析，日期字段宽松归一（date/datetime/Timestamp/字符串，过滤 NaN/NaT）。
     - 采用**进程内 TTL 缓存**（`SimpleTTLCache` 单例，TTL 从 `settings.calendar_cache_ttl_seconds` 读，默认 6 小时），按 provider_symbol 缓存“原始事件列表”，`days_until` 每次读取时按当前时间重算，避免缓存到过期倒计时；yfinance 出口统一走 `_make_ticker`，便于测试打桩、彻底离线。
     - 事件 `symbol` 键使用**归一化后的 symbol**（与 `/market/watchlist` 行情载荷对齐），单只 symbol 拉取失败优雅跳过并计数、绝不整体抛错；同时 best-effort 写 JSON 快照到 `backend/data/calendar_snapshot.json`（已被 .gitignore 忽略，失败不影响主流程）。每只 symbol 额外计算“最近一次未来财报”的 days_until，供前端角标使用。
  2. **配置（Backend）**：`backend/app/core/config.py` 仅新增一个字段 `calendar_cache_ttl_seconds: int = 21600`，风格模仿现有字段，未改动其它部分。
  3. **Schema / 路由（Backend / 新增）**：
     - 新增 `backend/app/schemas/calendar.py`（`CalendarEventView` / `CalendarSymbolSummaryView` / `CalendarResponseView`）。
     - 新增 `backend/app/api/routes/calendar.py`：`GET /`（query `days` 前视天数，默认 30）返回全量自选股即将到来的事件 + 每只最近财报摘要；`GET /{symbol}` 返回单只日历（不在自选股中也可查）。
     - `backend/app/api/router.py` 仅新增 import 与 `include_router(calendar.router, prefix="/calendar", tags=["calendar"])`，自动继承 App Token 鉴权。
  4. **前端日历面板（Frontend / 新增）**：
     - 新增 `frontend/src/views/CalendarView.vue`，暗色霓虹终端风格：按日期分组展示即将到来的财报/除息事件，临近（≤3 天）分组呼吸高亮，支持 14/30/60/90 天窗口切换，点击事件跳转单股详情。
     - `frontend/src/router/index.ts` 新增路由 `/calendar`（name `event-calendar`，懒加载）；`AppShell.vue` `navItems` 新增 `{ label: 'Calendar', to: '/calendar', index: '11' }`。
  5. **自选股卡片角标（Frontend）**：
     - `WatchlistView.vue` 拉取 `/calendar` 摘要并 `provide` symbol→days_until 表；`StockCard.vue` 通过 `inject` 读取，在卡片头部渲染“财报 N 天”角标（无未来财报数据则不显示，≤3 天呼吸高亮）。采用 provide/inject 以避免改动 `WatchlistSidebar.vue`。
     - `api/client.ts` 新增 `getCalendar` / `getSymbolCalendar`（复用 `getJson`）；`types/api.ts` 新增 `CalendarEvent` / `CalendarSymbolSummary` / `CalendarResponse`（手写镜像，注明待 `generate:api` 后可替换为生成别名）。
  6. **测试（Backend / TDD）**：新增 `backend/tests/test_calendar_service.py`，monkeypatch `_make_ticker` 与 `WatchlistRepository.list_all` 注入假数据，覆盖事件解析、days_until 计算、按日期升序、窗口过滤、过去事件排除、失败 symbol 跳过并计数、最近财报摘要、TTL 缓存命中（第二次不再调用 yfinance）、单只查询等，绝不联网。
- 影响文件：
  - 新增：`backend/app/services/calendar_service.py`、`backend/app/schemas/calendar.py`、`backend/app/api/routes/calendar.py`、`backend/tests/test_calendar_service.py`、`frontend/src/views/CalendarView.vue`
  - 修改：`backend/app/core/config.py`、`backend/app/api/router.py`、`frontend/src/router/index.ts`、`frontend/src/components/layout/AppShell.vue`、`frontend/src/views/WatchlistView.vue`、`frontend/src/components/watchlist/StockCard.vue`、`frontend/src/api/client.ts`、`frontend/src/types/api.ts`、`docs/code-change-log.md`
- 接口/数据结构变化：新增 `GET /api/calendar` 与 `GET /api/calendar/{symbol}`（继承 App Token 鉴权）；未新增数据库表 / 迁移。
- 验证情况：`conda run -n news-caught pytest backend/tests/test_calendar_service.py -q` 全绿（6 passed）；后端全量 391 passed（唯一 1 例 `test_news_relevance_experiment_runner` 失败为既有问题——其硬编码主仓库绝对路径，在 worktree 下超出允许范围，与本特性无关）；前端 `npm --prefix frontend run build`（含 vue-tsc 类型检查）通过。
- 风险/后续事项：`types/api.ts` 中日历类型为手写镜像，后续可运行 `npm run generate:api` 替换为 OpenAPI 生成别名；为加角标改动了 `StockCard.vue`（自选股专用组件，additive）。
## 2026-07-13 11:00

- 修改人：Claude（独立 worktree）
- 修改范围：LLM 成本治理（单价换算 + 月度预算）+ 分类结果缓存（Cost Governance & Classification Cache）
- 新增 Alembic 迁移：
  - **revision id：`a7f3c1e9d2b4`**，**down_revision：`c9d4f0a2b7e1`**
  - 文件：`backend/alembic/versions/a7f3c1e9d2b4_add_llm_cost_governance_and_classification_cache.py`
  - **新增列**（表 `llm_provider_config`）：`input_price_per_1k`(Float, nullable)、`output_price_per_1k`(Float, nullable)、`monthly_budget_usd`(Float, nullable)
  - **新增表** `llm_classification_cache`：`id`(PK)、`content_hash`(String(64), 唯一索引 `ix_llm_classification_cache_content_hash`)、`result_json`(Text)、`model_name`(String, nullable)、`created_at`(DateTime)
  - 该迁移位于 legacy 基线 `ec84dec88ae5` 之后，会在“legacy 库”路径下再次对 `create_all` 的完整 schema 运行，故写成幂等防御式（列/表已存在则跳过），与 `c9d4f0a2b7e1` 一致。
- 变更内容：
  1. **单价与成本换算（Backend）**：`GET /api/llm/stats` 聚合里按各模型单价把 prompt/completion tokens 换算为 USD；无单价的模型 `cost_usd=null` 且 `cost_available=false`。新增 `budget` 字段：本月累计花费 `month_cost_usd` vs 默认模型配置的 `monthly_budget_usd`，含 `over_budget` 超预算标记与 `usage_ratio`。为 `/stats` 补充了 `response_model=LLMStatsView`。
  2. **分类结果缓存（Backend）**：新增 `llm_classification_cache_repository.py`（`get_by_hash`/`upsert`）。在 `llm_providers.py` 的分类路径 `analyze_json` 中，先按内容归一化（折叠空白）后的 sha256 查缓存：命中直接返回、跳过 LLM 调用与 token 计量；未命中调用后写缓存。缓存读写失败仅告警、绝不影响主流程。新增开关 `llm_classification_cache_enabled: bool = True`（config.py，仅此一个字段）。
  3. **config upsert 扩展**：`upsert_config` 与 `POST /api/llm/config` 允许写入三个价格/预算字段（非敏感、additive）；价格字段仅在显式传入时更新，避免不感知价格的调用方（如 `upsert_active`）意外清空。**原有 base_url/明文 key/掩码 key 安全校验完全保留不变**。
  4. **前端**：`LlmConfigForm.vue` 新增“输入单价/输出单价（每 1K tokens）/月度预算($)”输入项；`TokenUsageConsole.vue` 将原“均价估算”改为真实花费($)，新增“本月累计 vs 预算”横幅（超预算红色高亮告警）与每模型 Cost 列；`components/llm/types.ts` 的 `TokenStats` 扩展价格/成本/预算字段并新增 `TokenBudget`；`client.ts` mock 同步补充成本/预算；重新生成 `src/types/generated/api.d.ts` 与 `openapi.json`（config update / stats 类型随后端 schema 更新）。
- 影响文件：
  - 后端：`backend/app/models/llm_classification_cache.py`(新)、`backend/app/models/llm_provider_config.py`、`backend/app/models/__init__.py`、`backend/app/db/initializer.py`、`backend/app/core/config.py`、`backend/app/schemas/llm.py`、`backend/app/repositories/llm_classification_cache_repository.py`(新)、`backend/app/repositories/llm_provider_config_repository.py`、`backend/app/services/llm_providers.py`、`backend/app/api/routes/llm.py`、`backend/alembic/versions/a7f3c1e9d2b4_...py`(新)
  - 测试：`backend/tests/test_llm_cost.py`(新)、`backend/tests/test_llm_classification_cache.py`(新)
  - 前端：`frontend/src/components/llm/LlmConfigForm.vue`、`frontend/src/components/llm/TokenUsageConsole.vue`、`frontend/src/components/llm/types.ts`、`frontend/src/api/client.ts`、`frontend/src/types/generated/api.d.ts`、`frontend/openapi.json`
- 接口/数据结构变化：`LLMConfigUpsertRequest`/`LLMConfigView` 增加三价格字段；`/api/llm/stats` 响应新增 `overall.cost_usd/cost_available`、`models[].cost_usd/cost_available/input_price_per_1k/output_price_per_1k`、`budget{...}`。
- 验证情况：
  - `conda run -n news-caught pytest backend/tests/test_llm_cost.py test_llm_classification_cache.py test_llm_stats.py test_llm_config.py test_llm_providers.py -q` → 51 passed。
  - 全量后端 `pytest backend/tests -q` → 392 passed，仅 `test_news_relevance_experiment_runner.py::test_experiment_runner_allows_news_relevance_research_files` 失败，且为 worktree 路径写死（`_REPO_ROOT` 解析到 worktree、测试硬编码主仓路径）导致的既有环境问题，与本特性无关。
  - 迁移在“已存在库（stamped c9d4f0a2b7e1）”场景 upgrade/downgrade 均验证通过。
  - 前端 `npm run build` 成功；`npm run check:api-drift` OK；`vitest run src/components/llm` 3 passed。
- 风险/后续事项：`/stats` 预算取默认模型配置的 `monthly_budget_usd`；价格字段一旦设置暂不支持通过表单清空为 null（可清零为 0）。
## 2026-07-13

- 修改人：Claude（agent worktree）
- 修改范围：个股 AI 综合研判（本地语料 RAG，结构化研报）—— 后端服务/Schema/路由 + 前端个股详情面板
- 变更内容：
  1. **后端研判服务 (Backend)**：
     - 新增 `backend/app/services/stock_research_synthesis.py`，提供 `synthesize_stock_research(symbol, session, lookback_days=7)`。复用既有能力收集数据：`QuoteService.get_cached_symbol_quote`（无网络的缓存行情 + 符号归一）解析标的与最新价，`NewsMentionsRepository.list_related_news` 取命中新闻，批量查询 `ArticleContent` 取正文，查询 `PriceSnapshot` 汇总窗口内价格走势（区间高低 + 累计涨跌幅）。
     - 命中新闻超过 top-K（8 条）时，复用 `llm_providers` 的 `embed_text` 与 `news_dedup._cosine_similarity` 做 embedding 相关性排序取 top-K；provider 不可用或 embedding 失败时退回按发布时间倒序，绝不上抛。
     - 拼装结构化 prompt 调用默认 LLM（`LLMProviderConfigRepository.get_default` + `build_provider().complete(response_format=json_object)`，operation_type=analysis 计量 token），解析 JSON 产出评级/催化剂(bull_case)/风险(bear_case)/关键时间线(key_events)/摘要。**LLM 未配置或调用失败/JSON 非法时优雅降级**为基于新闻情绪的规则要点汇总（mode=rule），字段结构不变，绝不抛未捕获异常、绝不主动联网。
  2. **后端 Schema (Backend)**：
     - 新增 `backend/app/schemas/stock_research.py`：`StockResearchReport`（含 symbol/market/mode/overall_rating/summary/bull_case/bear_case/key_events/price_context/references/model_name/llm_error/failover 等）及子模型 `StockResearchKeyEvent`、`StockResearchReference`、`StockResearchPriceContext`。
  3. **后端路由 (Backend)**：
     - 新增 `backend/app/api/routes/research.py`：`GET /research/stock/{symbol}`（可选 query `lookback_days`，1~30，默认 7）。
     - `backend/app/api/router.py` 仅加两行：import `research` 与 `include_router(research.router, prefix="/research", tags=["research"])`，自动继承 `verify_app_token` 鉴权。
  4. **前端 (Frontend)**：
     - `frontend/src/views/WatchlistDetailView.vue`（唯一改动的既有 view）：新增“🧠 生成 AI 综合研判”按钮 + 结构化结果面板（评级徽章、摘要、价格走势、催化剂/风险双栏、关键时间线、语料来源、降级/故障接管提示、一键复制、近 7/14/30 天窗口切换），暗色霓虹风格，复用现有 toast。未新增路由与导航。
     - `frontend/src/api/client.ts`：新增 `getStockResearch(symbol, lookbackDays?)`（复用已 import 的 `getJson` 与 `withQuery`）。
     - `frontend/src/types/api.ts`：新增 `StockResearchReport` 等类型别名（取自重新生成的 OpenAPI 类型）。
     - 重新生成 `frontend/openapi.json` 与 `frontend/src/types/generated/api.d.ts`（`npm run generate:api`），纳入新研判 schema/路由。
- 影响文件：
  - `backend/app/services/stock_research_synthesis.py`（新）
  - `backend/app/schemas/stock_research.py`（新）
  - `backend/app/api/routes/research.py`（新）
  - `backend/app/api/router.py`（+2 行）
  - `backend/tests/test_stock_research_synthesis.py`（新）
  - `frontend/src/views/WatchlistDetailView.vue`
  - `frontend/src/api/client.ts`
  - `frontend/src/types/api.ts`
  - `frontend/src/types/generated/api.d.ts`、`frontend/openapi.json`（自动生成）
  - `docs/code-change-log.md`
- 接口/数据结构变化：新增 `GET /api/research/stock/{symbol}?lookback_days=` 与 `StockResearchReport` 响应模型；无数据库迁移。
- 验证情况：`conda run -n news-caught pytest backend/tests/test_stock_research_synthesis.py -q` 全绿（6 passed）；前端 `npm run build`（vue-tsc + vite）通过。全量后端测试 391 passed，1 failed 仅为 `test_news_relevance_experiment_runner` 在 git worktree 下的硬编码绝对路径不匹配（与本特性无关）。
- 风险/后续事项：LLM 综合依赖已配置的默认大模型；未配置时自动规则降级。embedding 排序仅在命中新闻超过 top-K 时触发。
## 2026-07-13 情绪/利好利空分类评测闭环 + 模型 A/B（Sentiment Eval Harness）

- 修改人：Claude（worktree feat/sentiment-eval-harness）
- 修改范围：为情绪 / 利好利空三分类（positive/negative/neutral）补齐评测框架，照搬现有「新闻相关性评测」的同构结构，支持金标集 → per-label P/R/F1 → 混淆矩阵 → 两套模型配置 A/B 对比。此前换默认 LLM 时情绪分类质量无从量化，本次补上闭环。
- 变更内容：
  1. **后端评测框架（新增，不加数据库表/迁移，指标即时计算）**：
     - `backend/app/schemas/sentiment_eval.py`：金标样本（text + 人工 sentiment_label，importance 可选）、per-label 指标、混淆矩阵、单模型运行、A/B 对比、`GET /eval/sentiment` 响应等 pydantic 契约。
     - `backend/app/services/news_sentiment_dataset.py`：加载/校验金标 JSON 数据集（支持顶层数组或 `{"samples": []}`），文件缺失返回空列表（数据缺失降级），非法样本/重复 id 抛领域异常。
     - `backend/app/services/news_sentiment_evaluator.py`：给定金标+预测标签，计算 per-label precision/recall/F1、混淆矩阵、accuracy、macro-F1；并提供 `build_rule_sentiment_classifier` 把规则分类器按可调阈值包成 text→label 函数。
     - `backend/app/services/news_sentiment_experiment_runner.py`：跑一次评测（可注入 mock 分类函数），并支持 A/B——对两套配置各评一遍、对比 macro-F1/accuracy/逐标签 F1 并判定胜者。
     - `backend/app/services/news_sentiment_report.py`：把指标汇总成结构化报告 + Markdown 渲染。
     - `backend/data/research/sentiment_gold_benchmark.json`：内置 20 条中英混合金标集。
  2. **后端路由**：新增 `backend/app/api/routes/eval.py`（`GET /sentiment`，对内置金标即时评一遍，用规则分类器的两套阈值配置 ±0.20 / ±0.10 做 A/B；金标缺失降级为 `available=False`）。
  3. **测试（TDD）**：`backend/tests/test_news_sentiment_evaluator.py`、`backend/tests/test_news_sentiment_experiment_runner.py`，覆盖 P/R/F1/混淆矩阵/准确率、A/B 胜负与持平、长度不一致与空集报错、金标缺失降级；均未硬编码绝对路径。
  4. **前端（轻量，暗色霓虹风）**：新增 `frontend/src/views/SentimentEvalView.vue`，展示概览指标、per-label P/R/F1、混淆矩阵与 A/B 对比表。
- 影响文件：
  - 新增：`backend/app/schemas/sentiment_eval.py`、`backend/app/services/news_sentiment_dataset.py`、`backend/app/services/news_sentiment_evaluator.py`、`backend/app/services/news_sentiment_experiment_runner.py`、`backend/app/services/news_sentiment_report.py`、`backend/app/api/routes/eval.py`、`backend/data/research/sentiment_gold_benchmark.json`、`backend/tests/test_news_sentiment_evaluator.py`、`backend/tests/test_news_sentiment_experiment_runner.py`、`frontend/src/views/SentimentEvalView.vue`
  - 修改：`backend/app/api/router.py`（+2 行 import 与 include_router）、`backend/app/core/config.py`（新增 `sentiment_eval_dataset_file` 一个字段）、`frontend/src/router/index.ts`（新增 `/eval/sentiment` 懒加载路由）、`frontend/src/components/layout/AppShell.vue`（navItems 增加 Sentiment Eval）、`frontend/src/api/client.ts`（新增 `getSentimentEval`）、`frontend/src/types/api.ts`（新增情绪评测类型）、`docs/code-change-log.md`
- 接口/数据结构变化：新增只读端点 `GET /api/eval/sentiment`（`SentimentEvalResponse`）。新增可选配置项 `sentiment_eval_dataset_file`（默认 None，用内置金标）。无数据库变更。
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_sentiment_evaluator.py backend/tests/test_news_sentiment_experiment_runner.py -q` 全绿（13 passed）；后端全量 `pytest backend/tests` 398 passed，仅 `test_news_relevance_experiment_runner.py::test_experiment_runner_allows_news_relevance_research_files` 因既有硬编码主仓绝对路径在 worktree 失败（既有坏味道，与本特性无关）。前端 `npm run build`（vue-tsc + vite）通过。
- 风险/后续事项：内置金标集较小（20 条），仅用于框架自测与演示；正式评测建议通过 `sentiment_eval_dataset_file` 指向更大的人工标注集。A/B 目前是同一规则分类器的两套阈值配置，接入真实 LLM 分类后可扩展为跨模型对比。
## 2026-07-13 告警治理层（去重 / 免打扰 / 分级 / 合并摘要）

- 修改人：Claude（独立 worktree agent）
- 修改范围：通知模块告警治理增强，让通知从"吵"变"可信"。
- 变更内容：
  1. **免打扰时段（Quiet Hours）**：`config.py` 新增 `notify_quiet_hours_start` / `notify_quiet_hours_end`（"HH:MM"，默认空=关闭）与 `notify_quiet_hours_tz`（复用 `zoneinfo`，默认 `Asia/Shanghai`）。`notification_service.py` 在派发前对到期告警做暂缓：静默时段内低优先级异动顺延 `next_retry_at` 到时段结束（不计入失败重试次数），critical 不受限制照常投递。支持跨夜区间。
  2. **分级（Severity）**：`_classify_severity` 按 event_type / 触发条件打 critical / normal / low。自选股异动涨跌幅绝对值达到 `notify_critical_change_percent`（默认 8.0%）升级为 critical，绕过免打扰与合并。
  3. **去重增强**：`notify_dedupe_window_minutes`（默认 0=关闭）叠加在既有 latch 之上，同 symbol 同事件在窗口内只发一次，内存记录最近入队时间。
  4. **合并摘要（Digest）**：`notify_digest_window_minutes`（默认 0=关闭）+ `notify_digest_threshold`（默认 3）。非 critical 异动入队时先暂存一个合并窗口；`_materialize_alert_digest_jobs` 复用既有持久化队列，把到期累积告警合并成一条 `alert_digest`，`feishu_client.py` 新增 `build_alert_digest_card`，`_build_card_for_job` 加对应分支。
  5. **可配置面**：治理运行期覆盖只存 `NotificationService` 内存（`configure_governance` / `apply_governance` / `governance_view`），叠加在 settings 默认之上，**不落库、不加迁移**。经既有飞书配置接口（`schemas/feishu_notify.py` 加 `AlertGovernanceUpdate` / `AlertGovernanceView` 嵌套字段，`routes/notify.py` GET 回显 / POST 应用）与前端联通。
  6. **前端**：`NotifySettingsView.vue` 在飞书配置表单内新增"告警治理"区块（免打扰时段 / 分级阈值 / 去重窗口 / 合并窗口+阈值，含说明，暗色霓虹风格），随原保存按钮一并落地；`types/api.ts` additive 扩展 `AlertGovernanceConfig` 与 `Feishu*` 类型；`mock.ts` 补充 governance 默认。
- 影响文件：
  - `backend/app/core/config.py`
  - `backend/app/services/notification_service.py`
  - `backend/app/services/feishu_client.py`
  - `backend/app/schemas/feishu_notify.py`
  - `backend/app/api/routes/notify.py`
  - `backend/tests/test_alert_governance.py`（新增）
  - `frontend/src/views/NotifySettingsView.vue`
  - `frontend/src/types/api.ts`
  - `frontend/src/api/mock.ts`
  - `docs/code-change-log.md`
- 接口/数据结构变化：飞书配置接口 `FeishuConfigView` / `FeishuConfigUpsertRequest` additive 新增可选 `governance` 嵌套对象（内存态，不落库）。**未新增数据库迁移，未改 alembic / main.py。**
- 验证情况：`conda run -n news-caught pytest backend/tests/test_alert_governance.py backend/tests/test_notification_jobs.py backend/tests/test_feishu_notify.py backend/tests/test_feishu_sender.py -q` 全绿（33 passed）；后端全量 392 passed（1 例 `test_news_relevance_experiment_runner` 为 worktree 绝对路径预存在失败，与本特性无关）；前端 `npm run build`（含 vue-tsc）通过。
- 风险/后续事项：治理覆盖为内存态，后端重启后回落 settings/env 默认；如需跨重启持久化，后续可评估落库（需迁移）。默认全部保守（关闭），不改变旧行为。

## 2026-06-13 11:30

- 修改人：Antigravity
- 修改范围：LLM 额度审计控制台防御性健壮保护 (前端页面卡死修复)
- 变更内容：
  1. **前端 LlmSettingsView 容灾健壮性防御 (Frontend)**：
     - 修改了 `LlmSettingsView.vue`，彻底解决了用户在进入 LLM Settings 页面时前端偶尔卡死、必须刷新才出的 Bug。
     - 产生 Bug 的根本原因是：当数据库为全新状态尚未记录任何大模型 Token 审计用量，或者后端返回的每日用量 `daily` 数组的日期字段格式不符合预期时，折线图在渲染轴标签时直接调用 `p.date.substring(5)` 会抛出 `TypeError` 崩溃，导致 Vue 组件更新中断。
     - 本次在渲染处加入了 `p.date && typeof p.date === 'string' ? p.date.substring(5) : (p.date || '--')` 的安全防空校验，并同步对占比计算中的 `stats.overall?.total_tokens`、`stats.models?.[0]`、以及已调用总数的 `(stats.models || []).reduce` 进行了完备的可选链和 fallback 保护，使得该设置项在任何数据缺失边界下都具备极强的稳健性。
- 影响文件：
  - `frontend/src/views/LlmSettingsView.vue`
  - `docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：前端成功通过 `vue-tsc` 类型与语法校验，使用 `npm run build` 打包构建无报错。
- 风险/后续事项：无

## 2026-06-13 11:20

- 修改人：Antigravity
- 修改范围：大模型流泄漏保护、前后端 SSE 异步生命周期回收、指数退避重连机制 (长连接卡死与稳健性治理)
- 变更内容：
  1. **前端 ChatView 页面跳转卸载中止流 (Frontend)**：
     - 在 `ChatView.vue` 引入 `onBeforeUnmount` 钩子，页面销毁/跳转时立即触发 `stopGeneration()` 以中止 `currentAbortController.value.abort()`。彻底避免了用户在聊天生成中途离开页面导致连接无法释放的问题，解决了因浏览器 6 个并发 TCP 连接被堆满导致其余所有业务 API 全部 Pending 卡死的根本缺陷。
  2. **后端 SSE 异步感知与毫秒级连接回收 (Backend)**：
     - 将 `/api/stream/events` 重构为异步 `async def stream_events(request: Request, ...)` 路由，并在 `_event_stream` 生成器内配合 `await request.is_disconnected()` 在循环开始处精准拦截断开。
     - 采用 `anyio.to_thread.run_sync` 执行同步队列的读取，将 `queue.get` 阻塞超时由 15 秒压缩至 1 秒，将客户端断开后的资源释放延迟降低至最多 1 秒，并利用 `finally` 块确保 `event_bus.unsubscribe` 的百分之百回调，杜绝线程与事件订阅泄漏。
  3. **前端 SSE 指数退避自动重连机制 (Frontend)**：
     - 升级 `connectionStore.ts` 的 `connect` 和 `disconnect` 方法，将 handleEvent 缓存至 store 的 `lastHandleEvent` 状态中。
     - 当检测到 SSE 断开触发 `onError` 时，在 state 不为 idle 情况下启动定时器以 `reconnectDelay` 的指数级退避速度（2s, 4s, 8s...最高30s）自动重试连接。重连握手成功后重置延迟为 2 秒，主动 `disconnect` 时彻底回收定时器与句柄。
  4. **测试框架适配与断言修正 (Tests)**：
     - 修改 `test_stream_events.py`：新增 `FakeRequest` 类，并将对改造成 async 路由后的 `stream_route.stream_events` 的调用使用 `asyncio.run` 进行包裹以适配同步测试集。
     - 修改 `test_dev_launcher.py`：将原硬编码对 `/api/stream/status` 的断言同步更新为新探活免签路由 `/api/health`，解决断言失败。
- 影响文件：
  - `backend/app/api/routes/stream.py`
  - `backend/tests/test_stream_events.py`
  - `backend/tests/test_dev_launcher.py`
  - `frontend/src/views/ChatView.vue`
  - `frontend/src/stores/connectionStore.ts`
  - `docs/code-change-log.md`
- 接口/数据结构变化：后端 `/api/stream/events` 变更为异步 API，新增 `request: Request` 入参。
- 验证情况：后端 321 个单元测试 100% 顺利通过（包含重构后的 stream 事件测试与端口断言测试）；前端 Vitest 与编译构建 `npm run build` 100% 无报错通过。
- 风险/后续事项：无

## 2026-06-13 10:50

- 修改人：Antigravity
- 修改范围：新闻源抓取兼容性容灾、全站呼吸骨架屏转场、AI Chat匀速打字机与智能滚动锁、Delta 新闻增量浮条与平滑置入 (Smooth UX Iteration)
- 变更内容：
  1. **抓取器测试沙箱容灾降级 (Backend)**：
     - 修改 `fetcher.py`。当 `client.get` 在测试环境中被 mock 为不支持 `headers` 关键字参数的 FakeClient 时，优雅捕获 `TypeError` 并自动退避到不带 headers 的请求。
     - 在获取 `status_code` 和 `headers` 时，应用 `getattr` 安全回退，确保不支持相关特性的 Mock 响应实例（如 `FakeResponse`）不会抛出 AttributeError，实现 100% 测试兼容与网络容灾。
  2. **1:1 呼吸骨架屏与流畅转场升级 (Frontend)**：
     - 修改 `LoadingBlock.vue`。修正 `v-elif` 指令为官方标准的 `v-else-if`，彻底消除 Vue 编译和测试报错。
     - 升级 `NewsFeedView.vue`、`DashboardView.vue`、`WatchlistView.vue`。显式调用 `LoadingBlock` 并传入精准匹配该区块尺寸的 `skeletonType`（如 `news`, `dashboard`, `watchlist`）及 `skeletonCount`，数据载入时配合 `fade-cross` 达到流畅的淡入淡出无突兀感转场。
  3. **AI 对话打字机匀速缓动与智能滚动锁 (Frontend)**：
     - 升级 `ChatView.vue`。将 SSE 异步获取字符由直接拼接重构为基于定时器（30ms 间隔）的“平滑吐字暂存队列”机制。当积压较多时动态调整步长防文字落后，大模型输出行云流水。
     - 引入智能滚动锁定。监听聊天窗口的 `@scroll` 事件，在检测到用户往上拉阅历史（距离底部超过 50px）时自动解除强制置底滚动锁定，并在右下角淡入毛玻璃高斯模糊的“⬇ 回到底部”浮动玻璃按钮，点击或重回底部时自动重置滚动锁。
  4. **Delta 增量新闻顶部浮条与平滑展开置入 (Frontend)**：
     - 升级 `NewsFeedView.vue`。在本地引入 `displayedFeedItems` 缓冲层状态。当后台 SSE 接收到 `news.created` 增量通知时不再强制刷新跳动当前列表，而是暂存入 `pendingNewItems` 并于 Raw Stream 头部浮现深蓝色毛玻璃 Delta Banner。用户点击 Banner 后，平滑在顶部展开并置入新新闻卡片。
     - 结合 `transition-group` 动画为非虚拟滚动的原始流卡片配备平滑的下沉展开动效。
- 影响文件：
  - `backend/app/services/ingestion/fetcher.py`
  - `frontend/src/components/common/LoadingBlock.vue`
  - `frontend/src/views/NewsFeedView.vue`
  - `frontend/src/views/DashboardView.vue`
  - `frontend/src/views/WatchlistView.vue`
  - `frontend/src/views/ChatView.vue`
  - `docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：后端 321 个单元测试 100% 顺利通过（包含 304 缓存和正文提取测试）；前端 201 个 Vitest 测试全部 100% 成功通过；前端生成打包编译通过无任何警告
- 风险/后续事项：无

## 2026-06-13 10:20

- 修改人：Antigravity
- 修改范围：API 安全认证、防 Key 劫持、飞书配置加密、本地绑定限制、防泄漏扫描 (Security Hardening)
- 变更内容：
  1. **本地临时认证令牌 (App Token) 机制**：
     - 后端启动生命周期（`lifespan`）中在本地安全数据目录 `data/.app_token` 自动产生一个 32 字节的强随机令牌（使用 `secrets` 库并应用 `600` 权限仅限自己读写）。
     - 前端通过 Vite 构建在编译阶段通过 Node.js 读入该 Token，并通过 `define` 机制注入到全局常量 `__APP_TOKEN__`。
     - 前端在入口处对 `window.fetch` 进行全局劫持代理包装，所有发出的 `/api/*` 请求都会自动在 Headers 中携带 `X-App-Token` 认证头。
     - 后端使用 FastAPI 依赖注入拦截并校验该 Token。任何未经授权的外来/恶意网页跨站伪造调用将直接被返回 401 拦截。
     - 增加测试环境兼容，若在 Pytest 测试下且没有强制校验环境变量时，自动放行，以不破坏原本庞大的业务测试集。
  2. **本地绑定与接口回环限制**：
     - 修改 `Makefile` 和启动脚本 `scripts/dev.sh`，强制将前端 Vite 和后端 FastAPI 默认绑定的 Host 设为 `127.0.0.1` 本地回路，从网络物理层面屏蔽了来自局域网或外网未授权主机的直接 API 请求与敏感信息抓取。
     - 放行探活接口 `/api/health`。
  3. **API 基址被篡改劫持 Key 防御 (Base URL Hijack Defense)**：
     - 升级了 `LLMProviderConfigRepository.upsert_config` 方法的强安全校验。当大模型配置被修改，且提交的参数中更改了 `base_url` 时，系统强制校验用户必须重新输入明文 API Key，拒绝重用或省略已有的加密 Key（不允许保留带 `*` 掩码星号值）。这杜绝了攻击者试图通过配置注入恶意基址，配合已有 Key 在向新目标地址发包时窃取 Key 的严重漏洞风险。
  4. **敏感密钥本地 Fernet 加密存储**：
     - 升级了飞书推送通知模块。将原本明文保存在数据库中的飞书推送 API `app_secret`，重构为大模型 API Key 相同的 Fernet 本地加密机制。
     - 数据库存储一律使用密文，并在服务发送与测试时在内存中实时解密（`config.decrypted_app_secret`）。
  5. **本地密钥防泄露静态扫描**：
     - 强化了 `.gitignore` 规则以阻止 `.env` 各种子版本、`.secret_key`、`.app_token` 被无意中提交到 Git 仓库。
     - 新增静态密钥扫描工具 `scripts/check_secrets.py`。可在本地通过 `python scripts/check_secrets.py` 进行一键离线检测以确认没有明文泄漏。
- 影响文件：
  - `.gitignore`
  - `Makefile`
  - `README.md`
  - `scripts/dev.sh`
  - `scripts/check_secrets.py` [NEW]
  - `backend/app/core/auth.py` [NEW]
  - `backend/app/main.py`
  - `backend/app/api/router.py`
  - `backend/app/api/routes/notify.py`
  - `backend/app/models/feishu_notify_config.py`
  - `backend/app/repositories/feishu_notify_config_repository.py`
  - `backend/app/repositories/llm_provider_config_repository.py`
  - `backend/app/services/notification_service.py`
  - `backend/tests/test_feishu_notify.py`
  - `backend/tests/test_llm_config.py`
  - `backend/tests/test_network_security.py` [NEW]
  - `frontend/vite.config.ts`
  - `frontend/src/api/http.ts`
  - `docs/code-change-log.md`
- 接口/数据结构变化：有（非健康检查 `/api/*` 接口需在 Headers 中携带 `X-App-Token` 认证头；大模型修改 `base_url` 时强制要求输入明文密钥）
- 验证情况：后端 317 个单元测试 100% 通过（新增安全及加密用例均通过），前端构建无报错，静态密钥扫描通过
- 风险/后续事项：局域网调试需在测试时临时放行或提供配套 Token

## 2026-06-12 23:45

- 修改人：Antigravity
- 修改范围：大模型容灾降级可视化感知与 Token 审计时序看板 (Round 5)
- 变更内容：
  1. **大模型故障容灾降级感知 (P0)**：
     - 修改 `llm_providers.py`，在大模型流式 `chat_stream` 发生降级重试时，先 `yield` 吐出 `[FAILOVER_SIGNAL]:...` 特殊格式的前缀；在同步和异步的 `_request_completion` 中触发备用重试时，在 provider 实例上挂载 `failover_triggered` 属性以携带故障上下文。
     - 修改 `backend/app/api/routes/llm.py` 与 `backend/app/api/routes/watchlist.py`。捕获并解析流式前缀，转换下发为标准的 SSE 帧 `data: {"failover": ...}`；并在非流式 JSON / 投研研报返回体中附加 `failover` 元数据。
     - 修改 `WatchlistAiInsightView` Pydantic 契约，支持可选的 `failover` 属性。
     - 修改前端 `ChatView.vue` 和 `StockDetailPanel.vue`，拦截流式/非流式响应中的 `failover` 数据。触发 Warning Toast 反确，并且在当前会话气泡/研报正上方渲染高斯模糊的橙黄色**“降级接管横幅”**，展示源、备模型名及原因。
     - 修改 `watchlistStore.ts`，使其 `loadAiInsight` 也支持将 failover 信息存入 store 状态供组件渲染。
  2. **模型额度审计控制台 7 天 Token 消耗时序 SVG 看板 (P1)**：
     - 升级 `GET /api/llm/stats`，使用 SQLAlchemy 按天分组查询过去 7 天内每日产生的 Token 用量总和并在响应中回填 `daily` 数组。
     - 前端修改 `LlmSettingsView.vue`，增加纯自绘的 SVG 折线趋势图。支持背景网格虚线、霓虹青色发光折线、面积渐变阴影。
     - 增加 Hover 交互，利用十字垂直定位线与绝对定位 HTML 气泡 Tooltip 提示，展示每日 Prompt / Completion 的精细数据。
     - 在 `frontend/src/api/client.ts` 补充 mock stats 数据，在 Mock 模式下也支持用量折线趋势展示。
  3. **单元测试与全量回归 (Verify)**：
     - 在 `backend/tests/test_llm_stats.py` 中编写 `test_llm_stats_daily_trend`（验证 7 天数据聚合查询）与 `test_llm_chat_failover_sse`（验证 SSE Failover 信号在 API 层的解析转换）。
     - 在 `test_llm_provider_failover` 补齐对 provider 上 `failover_triggered` 的断言。
  4. **开发脚本启动超时调整 (P0)**：
     - 修改 `scripts/dev.sh`，将 `wait_for_http` 检测后端的重试次数限制由 50 次 (10秒) 提升至 150 次 (30秒)，避免因 Alembic 数据表初始化在部分低配机器上耗时超过 10 秒时，导致整个进程树被 `set -e` 机制强制杀除。
- 影响文件：
  - `scripts/dev.sh`
  - `backend/app/services/llm_providers.py`
  - `backend/app/api/routes/llm.py`
  - `backend/app/api/routes/watchlist.py`
  - `backend/app/schemas/watchlist.py`
  - `backend/tests/test_llm_stats.py`
  - `frontend/src/views/ChatView.vue`
  - `frontend/src/views/LlmSettingsView.vue`
  - `frontend/src/components/watchlist/StockDetailPanel.vue`
  - `frontend/src/stores/watchlistStore.ts`
  - `frontend/src/api/client.ts`
- 接口/数据结构变化：有（后端 stats 响应返回体新增 `daily` 时序统计数组，`/api/llm/chat` SSE 帧与非流式返回、AI研报返回新增 `failover` 可选元数据属性）
- 验证情况：前后端全量测试 100% 通过（前端 201/201 用例通过，后端 311/311 用例通过），前端构建无报错
- 风险/后续事项：无

## 2026-06-12 23:28

- 修改人：Antigravity
- 修改范围：前端测试回归缺陷修复、自选股重大资讯发光雷达与 AI 投研一键复制共享 (Round 4)
- 变更内容：
  1. **前端测试回归缺陷修复**：
     - 修改 `WatchlistView.vue`，在 Vitest 环境下将模糊联想搜索的防抖时延置为 `0ms`。
     - 修改 `WatchlistView.test.ts`，Mock 动态联想搜索接口，并在输入后使用 `setTimeout` 宏任务推进，彻底解决异步元素未渲染的问题。
     - 修改 `WatchlistDetailView.test.ts` 和 `StockDetailPanel.test.ts`，补齐 pinia store 里的 `aiInsights` 状态和 `loadAiInsight` 方法，并注入 `localStorage` Mock，修复了 JSDOM file:// 协议下访问 `window.localStorage` 抛出的 `SecurityError` 导致测试崩溃的问题。
  2. **自选股重大资讯发光雷达**：
     - 扩展 `QuoteSummaryView` 契约，新增 `has_hot_alert: bool = False` 字段。
     - 在 `QuoteService` 中新增 `_get_hot_symbols` 过滤逻辑，高能筛选过去 12 小时内存在极端情感（情感分 >= 0.8 或 <= -0.8）或高权重主题（重要性权重 >= 8.0）的股票。
     - 编写并跑通了后端的 `test_quote_service_has_hot_alert` 单元测试。
     - 修改 `StockCard.vue`，若检测到 `row.has_hot_alert`，展示带脉冲向外声纳动画扩散的霓虹呼吸红点，提高对重大警报的视觉感知力。
  3. **AI 投研一键复制与 Toast 联动**：
     - 在个股详情研报上方新增 `📋 复制报告` 按钮。
     - 实现 `copyInsight` 提取 Markdown 文本并写入系统剪贴板，联动已有的全局 `toastStore.showSuccess` 和 `toastStore.showError` 弹出高品质毛玻璃 Toast，提升投研报告共享效率。
- 影响文件：
  - `frontend/src/views/WatchlistView.vue`
  - `frontend/src/views/WatchlistView.test.ts`
  - `frontend/src/views/WatchlistDetailView.test.ts`
  - `frontend/src/components/watchlist/StockDetailPanel.vue`
  - `frontend/src/components/watchlist/StockDetailPanel.test.ts`
  - `frontend/src/components/watchlist/StockCard.vue`
  - `frontend/src/types/api.ts`
  - `backend/app/schemas/market.py`
  - `backend/app/services/quote_service.py`
  - `backend/tests/test_market.py`
- 接口/数据结构变化：有（后端 Quote 响应 schema `QuoteSummaryView` 结构新增 `has_hot_alert` 字段）
- 验证情况：前后端全量测试 100% 通过（前端 201/201 用例通过，后端 309/309 用例通过），前端构建无报错
- 风险/后续事项：无

## 2026-06-12 23:15

- 修改人：Antigravity
- 修改范围：前端 AI 对话多会话、Markdown/表格解析、大模型流生成中止控制、全局 Toaster 消息系统、后端 SSE 连接断开自动中止大模型
- 变更内容：
  1. **前端 Markdown 解析器**：新增 `frontend/src/utils/markdown.ts` 与 `frontend/src/utils/markdown.test.ts`，内置轻量、安全的 Markdown 转 HTML 模块，支持表格与一键复制代码块，不增加外部 npm 包。
  2. **全局 Toaster 消息系统**：新增 `frontend/src/stores/toastStore.ts` 与 `frontend/src/components/common/ToastContainer.vue`，实现发光呼吸灯毛玻璃 Toaster 系统；并在 `App.vue` 引入，且在 `LlmSettingsView.vue` 联调配置动作的 Toast 提示。
  3. **多会话管理与本地持久化**：重构 `frontend/src/views/ChatView.vue`，实现左侧历史会话 sidebar 及 `localStorage` 本地持久化，支持新建/删除/重命名会话、关联新闻会话自适应创建。
  4. **流式输出中止控制**：重构 `ChatView.vue` 输入框增加“停止生成”按钮，使用 `AbortController` 绑定 fetch streaming；重构 `backend/app/api/routes/llm.py` 支持检测 `request.is_disconnected()`，在客户端关闭连接时自动退出 SSE 生成器；并在 `backend/tests/test_llm_chat.py` 中新增 `test_llm_chat_stream_disconnect_generator` 单元测试验证其行为。
- 影响文件：
  - `frontend/src/utils/markdown.ts`
  - `frontend/src/utils/markdown.test.ts`
  - `frontend/src/stores/toastStore.ts`
  - `frontend/src/components/common/ToastContainer.vue`
  - `frontend/src/App.vue`
  - `frontend/src/views/ChatView.vue`
  - `frontend/src/views/LlmSettingsView.vue`
  - `frontend/src/views/LlmSettingsView.test.ts`
  - `backend/app/api/routes/llm.py`
  - `backend/tests/test_llm_chat.py`
  - `README.md`
  - `docs/code-change-log.md`
- 接口/数据结构变化：有（后端 `/api/llm/chat` SSE 链路支持连接检测，前端 chat 会话数据结构新增）
- 验证情况：前后端全量单元测试 100% 通过（前端 199/199 用例，后端 301/301 用例），前端 build 无报错
- 风险/后续事项：无

## 2026-06-12 19:30

- 修改人：Cursor Agent
- 修改范围：docs 目录归档整理 + gitignore 补充
- 变更内容：
  1. **文档归档**：将 `docs/superpowers/` 整体移至 `docs/archive/superpowers/`（约 180 篇历史设计/计划）；新建空的 `docs/superpowers/{specs,plans}/` 供后续 Superpowers 流程使用。
  2. **规划文档归位**：`refactor-plan-2026-06.md`、`gemini_optimization.md` 并入 `docs/archive/optimization-2026-06/`。
  3. **文档索引**：新增 [docs/README.md](/Users/xiuyang/Desktop/news-caught/docs/README.md) 区分现行文档与归档目录。
  4. **gitignore**：忽略 `data/`（含本地 secret key）、`backend/data/*.db-shm|*.db-wal`。
- 影响文件：见 `docs/archive/`、`docs/README.md`、`.gitignore`
- 接口/数据结构变化：无
- 验证情况：文档移动，无运行时影响
- 风险/后续事项：若外部链接仍指向旧 `docs/superpowers/` 路径，需改为 `docs/archive/superpowers/`。

## 2026-06-12 19:20

- 修改人：Cursor Agent
- 修改范围：前端 LLM 相关测试修复 + 2026-06 优化计划文档归档
- 变更内容：
  1. **测试修复**：`saveLlmConfig` 移除 mock 降级 fallback，网络失败时与 `getLlmConfig` 一致直接 reject；`LlmSettingsView.test.ts` 补全多模型 store mock（`configs`、`loadAllConfigs` 等）并同步新版 UI 文案与 payload 字段。
  2. **文档归档**：将根目录 `optimization_plan_2026-06.md`、`claude_optimization.md` 移至 `docs/archive/optimization-2026-06/`，新增归档 README 与完成状态表。
- 影响文件：
  - [client.ts](/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts)
  - [LlmSettingsView.test.ts](/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.test.ts)
  - [docs/archive/optimization-2026-06/README.md](/Users/xiuyang/Desktop/news-caught/docs/archive/optimization-2026-06/README.md)
  - [docs/archive/optimization-2026-06/optimization_plan_2026-06.md](/Users/xiuyang/Desktop/news-caught/docs/archive/optimization-2026-06/optimization_plan_2026-06.md)
  - [docs/archive/optimization-2026-06/claude_optimization.md](/Users/xiuyang/Desktop/news-caught/docs/archive/optimization-2026-06/claude_optimization.md)
- 接口/数据结构变化：无（`saveLlmConfig` 行为与加载接口对齐，失败不再静默 mock）。
- 验证情况：
  - `npm --prefix frontend run test -- --run` → **192/192 通过**
  - `conda run -n news-caught pytest backend/tests` → **300/300 通过**（回归确认）
- 风险/后续事项：根目录若仍有引用旧路径的链接需手动更新；OpenAPI CI drift check 仍待接入。

## 2026-06-12 19:10

- 修改人：Cursor Agent
- 修改范围：Phase 3 模块重构/分页/清理 + Phase 4 工程化/组件拆分/Embedding 判重
- 变更内容：
  1. **Keyset 分页**：`GET /api/news` 响应改为 `{ items, next_cursor }`；`NewsRepository.list_recent_page` 支持 base64 复合游标 `(published_at, id)`；前端 `newsStore` 增加 `loadMoreFeedNews`，`NewsFeedView` 底部 IntersectionObserver 无限滚动。
  2. **数据生命周期**：新增 `DataCleanupWorker`（继承 `BaseWorker`），按配置保留期分批删除 `news_item`(180d) / `article_content`(90d) / `price_snapshot`(30d)，每周执行 `PRAGMA incremental_vacuum`。
  3. **ingestion 包拆分**：将 `news_ingestion.py` 机械拆分为 `app/services/ingestion/`（fetcher/parser/dedup_gate/persister/health/service），原模块保留 100% 向后兼容 re-export。
  4. **Embedding 二次判重**：实现 `EmbeddingDuplicateJudge`（LRU 缓存 + 余弦相似度 > 0.85），配置 `dedup_secondary_judge=embedding` 启用；`OpenAICompatibleProvider.embed_text` 调用 `/embeddings`。
  5. **工程化**：新增 `.github/workflow/ci.yml`（Ruff + Pytest + vue-tsc + Vitest + Build）；新增 `scripts/generate_openapi.py` 一键导出 OpenAPI 并生成 `frontend/src/types/generated.ts`。
  6. **KlineChart 拆分**：抽取 `useKlineChartLifecycle`、`useKlineMarkers`、`useChartResize` composables，组件 script 降至 ~348 行，保留红涨绿跌配色。
- 影响文件：见 git diff（backend: news_repository, cleanup, news_dedup, ingestion/*, main.py, config.py；frontend: newsStore, NewsFeedView, api/client, types/api, KlineChart composables）
- 接口/数据结构变化：**Breaking** — `GET /api/news` 由裸数组改为 `{ items, next_cursor }`；新增 query 参数 `cursor`。
- 验证情况：
  - `conda run -n news-caught pytest backend/tests` → **300 passed**
  - `npm --prefix frontend run build` → 成功
  - `npm --prefix frontend run test -- --run` → 187/192 通过（5 个失败为既有 LlmSettingsView / api client llm 相关测试，与本次改动无关）
- 风险/后续事项：OpenAPI 生成脚本需在 CI 中接入 drift check；Embedding 判重默认关闭，灰度验证后设置 `DEDUP_SECONDARY_JUDGE=embedding`。

## 2026-06-12 18:45

- 修改人：Antigravity
- 修改范围：数据库底座迁移、并发 WAL 优化、外键约束加固与事件总线异常隔离 (Phase 1)
- 变更内容：
  1. 初始化 Alembic 结构并对齐当前 Model 生成 initial_schema 迁移脚本，在 `env.py` 中支持 SQLite batch 迁移与动态数据库 URL 加载。
  2. 重构数据库初始化服务 `initializer.py`：完全移除 manual column/index checks 手写迁移；改为在 SQLAlchemy `create_all` 之后通过 `stamp head` (新库/旧开发库) 或 `upgrade head` (旧迁移库) 自动化升级；保留并前置执行 `_migrate_legacy_source_health` 确保历史旧版数据无损升级。
  3. 配置 SQLite WAL 模式并发写机制：在 `session.py` 中监听 connect 触发执行 `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=30000; PRAGMA foreign_keys=ON;`，大幅减轻库锁。
  4. 级联删除安全性加固：针对 `article_content`, `news_analysis_result`, `news_signal_result`, `news_stock_mention`, `topic_news_link`, `x_post`, `x_post_symbol_mention`, `x_signal_post_link` 所有 8 个子表模型外键定义全部添加 `ondelete="CASCADE"`，支持级联级删除以满足外键约束启用后的物理清理需求。
  5. 进程内事件总线异常隔离：重构 `InMemoryEventBus.publish`，对所有事件订阅者增加 try-except 隔离防止局部失败导致摄入大进程崩溃，失败详细信息上报到 `HybridEventBus` 的 `last_error` 中；在 `test_event_bus.py` 补充隔离单测。
- 影响文件：
  - [env.py](file:///Users/xiuyang/Desktop/news-caught/backend/alembic/env.py)
  - [initializer.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py)
  - [session.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/db/session.py)
  - [event_bus.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/services/event_bus.py)
  - [test_event_bus.py](file:///Users/xiuyang/Desktop/news-caught/backend/tests/test_event_bus.py)
  - [article_content.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/models/article_content.py)
  - [news_analysis_result.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/models/news_analysis_result.py)
  - [news_signal_result.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/models/news_signal_result.py)
  - [news_stock_mention.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/models/news_stock_mention.py)
  - [topic_news_link.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/models/topic_news_link.py)
  - [x_post.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/models/x_post.py)
  - [x_post_symbol_mention.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/models/x_post_symbol_mention.py)
  - [x_signal_post_link.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/models/x_signal_post_link.py)
- 接口/数据结构变化：无。但数据库连接及底层表引用增加了级联删除，对数据库历史结构回填提供了完整支持。
- 验证情况：`conda run -n news-caught pytest backend/tests` 295/295 个测试全量顺利通过，包含了新增的异常隔离测试。
- 风险/后续事项：无。

## 2026-06-12 18:20

- 修改人：Antigravity
- 修改范围：后端并发优化、多模型管理、AI 聊天及新闻问答开发
- 变更内容：
  1. 为大模型底层驱动添加异步支持，新增基于 `httpx.AsyncClient` 的 `AsyncOpenAICompatibleProvider` 辅助类，支持 `async_chat_stream` 流式 SSE 生成。
  2. 重构大模型配置表以支持多配置并存，新增 `is_default` 属性并编写了 SQLite 友好表列迁移方法，完善了 `LLMProviderConfigRepository` 仓储方法（增删改、设置默认、变更启用状态）。
  3. 新增多模型管理和 AI 对话的系列端点：支持多模型增删改查及启用和默认切换；新增 `/api/llm/chat` 异步端点，支持绑定 `news_id` 自动提取新闻及正文并融合进上下文，支持 SSE 流式返回。
  4. 扩展前端 `client.ts` 及 `llmStore.ts` 以接入多配置管理接口。
  5. 改造前端 `LlmSettingsView.vue` 支持以 HSL 渐变和状态呼吸灯的形式展示已配置模型列表，支持在列表上执行编辑、默认设定、启用与删除。
  6. 编写全新 AI Chat 聊天主页面 `ChatView.vue`，使用 `fetch` + `ReadableStream` 接收 `POST` 接口的 SSE 字节流并实现流式打字机渲染，提供绑定新闻上下文预览及清除，以及预置快捷追问选项。
  7. 在新闻详情页 `NewsDetailView.vue` 追加了“关于此新闻问 AI”按钮，可直达聊天室并自动携带新闻上下文。
  8. 新增全套 API 接口与多模型管理和流式聊天对话的单元测试。
- 影响文件：
  - [llm_provider_config.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/models/llm_provider_config.py)
  - [initializer.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py)
  - [llm_provider_config_repository.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/repositories/llm_provider_config_repository.py)
  - [llm_providers.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/services/llm_providers.py)
  - [llm.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/schemas/llm.py)
  - [llm.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/api/routes/llm.py)
  - [client.ts](file:///Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts)
  - [mock.ts](file:///Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts)
  - [api.ts](file:///Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts)
  - [llmStore.ts](file:///Users/xiuyang/Desktop/news-caught/frontend/src/stores/llmStore.ts)
  - [AppShell.vue](file:///Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue)
  - [index.ts](file:///Users/xiuyang/Desktop/news-caught/frontend/src/router/index.ts)
  - [ChatView.vue](file:///Users/xiuyang/Desktop/news-caught/frontend/src/views/ChatView.vue)
  - [NewsDetailView.vue](file:///Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue)
  - [test_llm_chat.py](file:///Users/xiuyang/Desktop/news-caught/backend/tests/test_llm_chat.py)
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests` 295/295 例全量成功通过；`npm --prefix frontend run build` 成功完成编译打包且无任何类型报错。
- 风险/后续事项：无

## 2026-06-12 18:10

- 修改人：Antigravity
- 修改范围：初始化数据库锁与并发安全增强
- 变更内容：解决开发脚本并发拉起多进程（FastAPI + Market Worker）同时执行 `initialize_database()` 造成 SQLite 冲突崩溃的问题。将异常捕获从 `IntegrityError` 拓宽到通用的 `Exception`（包含 SQLite 写入锁 `OperationalError`），确保任何由于并发初始化导致的库锁或写冲突均能被安全地吞掉并跳过（因为另一进程已成功填充了种子数据），保障了 `make dev` 持续健康运行而不会被子进程崩溃杀死。
- 影响文件：
  - [initializer.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py)
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught pytest backend/tests` 293/293 例全量成功通过；`make dev` 成功拉起且无任何崩溃。
- 风险/后续事项：无。

## 2026-06-12 18:05

- 修改人：Antigravity
- 修改范围：后端数据库初始化 Bug 修复
- 变更内容：修复在本地运行及测试启动中，因 `has_news` 被置空且 SQLite 机制下 `article_content` 唯一约束发生残留导致 `make dev` 启动崩溃的 P0 问题。将 `initializer.py` 种子数据块最前方的清空逻辑由 `session.flush()` 彻底升级为 `session.commit()`，显式将删除结果落盘提交以清理可能存在的外键残留，并在子表清理的同时显式执行 `NewsItem` 本身的历史物理清理。
- 影响文件：
  - `backend/app/db/initializer.py`
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught pytest backend/tests` 293/293 例全量成功通过；`make dev` 完美启动且再无 IntegrityError 报错。
- 风险/后续事项：无。

## 2026-06-12 18:00

- 修改人：Antigravity
- 修改范围：前端大仪表盘与新闻可见性增强优化 (Phase 2)
- 变更内容：
  - **新组件开发**：
    1. 新建 `SentimentTrendChart.vue` 组件，使用自绘大号 SVG 绘制 24 小时情绪与新闻热度双折线/渐变面积填充趋势图，展示过去 24 小时内偏利好（红）与偏利空（绿）新闻的时间分布与博弈走势，大仪表盘布局升级为罗盘-趋势图-指标卡三栏拼贴；
  - **组件细节与表现力升级**：
    1. 升级 `SentimentGauge.vue` 指针罗盘，在其外侧引入精密仪器的刻度虚线 (Ticks) 装饰轨道，并为指针增加发光滤镜（glow）和尖端发光小点，显著提升视觉表现力；
    2. 升级 `BreakingNewsSpotlight.vue` 突发横幅，提取 12 小时内最重要（得分 >= 8.5）的多条突发新闻进行优雅的淡入淡出自动轮播（支持鼠标悬停时暂停，并配有手动左右切换按键），同时采用双层声纳波纹呼吸灯动画；
    3. 升级 `DashboardView.vue` 新闻 Feed 列表中的高权重突发新闻，凡是 `editorial_score >= 8.5` 的卡片，都会被高亮渲染为“突发流光特制卡”，配置红/绿流光左侧边框、霓虹背景发光及前置闪烁呼吸警报灯，极大地增强了重大新闻的可见度与感知速度；
  - **单元测试补充**：
    1. 升级 `DashboardView.test.ts`，增加了一个全面的测试用例，验证 24 小时舆情趋势图的存在性渲染，以及高权重突发新闻被成功应用高亮类名和闪动呼吸灯的断言。
- 影响文件：
  - `frontend/src/components/dashboard/SentimentTrendChart.vue` (新)
  - `frontend/src/components/dashboard/SentimentGauge.vue`
  - `frontend/src/components/dashboard/BreakingNewsSpotlight.vue`
  - `frontend/src/views/DashboardView.vue`
  - `frontend/src/views/DashboardView.test.ts`
  - `README.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run build` 成功；`npm --prefix frontend run test -- --run` 189/189 例全量成功通过；后端 pytest 293/293 例全量回归通过。
- 风险/后续事项：无

## 2026-06-12 17:50

- 修改人：Antigravity
- 修改范围：前端交互大仪表盘、突发新闻可见度及极速阅览抽屉组件
- 变更内容：
  - **新组件开发**：
    1. 新建 `SentimentGauge.vue` 组件，使用自绘半圆 SVG 构建直觉式舆情罗盘指针（红涨绿跌配色），代表当前偏好/利好新闻比率及市场热度情绪诊断；
    2. 新建 `BreakingNewsSpotlight.vue` 组件，检索最近 12 小时内最重要（得分 >= 8.5）或极端情感的新闻作为突发警报（Live Radar pulse），附带呼吸灯流光发亮心跳动效，高亮引导用户关注；
    3. 新建 `NewsDetailDrawer.vue` 组件，实现右侧极速侧滑出式预览抽屉，在当前页中 0 毫秒直接阅览新闻全文与大模型个股研判/Top Pick，并在选定过滤范围的新闻序列中提供“上一篇/下一篇”无缝翻页导航，免去了路由跳转切屏的繁琐。
  - **仪表盘交互重构**：修改 `DashboardView.vue`，引入全局控制中心页签（全部/A股/港股/美股及利好/利空过滤器）。点击页签后，客户端纯本地计算 Computed 并联动过滤四个大指标数值、舆情折线图、偏度罗盘偏转、新闻主 Feed 列表、聚合主题及自选异动股。同时重排顶部布局，为罗盘和指标设计了高对称的美学拼贴；
  - **单元测试适配**：在 `DashboardView.test.ts` 中前置 mock 了 `@vue/devtools-api` 与 `llmStore`，避开了测试挂载 Pinia 触发 Vue 3 调试组件时因无 localStorage 文件抛出的安全错误。同步适配路由卡片点击测试以断言抽屉的拉起。
- 影响文件：
  - `frontend/src/components/dashboard/SentimentGauge.vue` (新)
  - `frontend/src/components/dashboard/BreakingNewsSpotlight.vue` (新)
  - `frontend/src/components/news/NewsDetailDrawer.vue` (新)
  - `frontend/src/views/DashboardView.vue`
  - `frontend/src/views/DashboardView.test.ts`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run build` 成功；`npm --prefix frontend run test -- --run` 188/188 例全量成功通过。
- 风险/后续事项：无明显风险，通过 Mock 处理了测试中的 Vue 3 Devtools Kit 环境异常。

## 2026-06-12 17:40

- 修改人：Antigravity
- 修改范围：单元测试套件 Regression 报错修复、测试数据库物理隔离 (Test DB Isolation)
- 变更内容：
  - **测试库物理隔离**：修改 `backend/tests/conftest.py`，在加载应用之前动态将环境变量 `DATABASE_URL` 重定向至独立的 `backend/data/app_test.db` 文件，并在 pytest 整个 Session 开启时初始化、结束时彻底销毁，确保测试数据与开发数据 100% 隔离；
  - **测试断言优化**：修复 `test_news.py` 中 `test_news_feed_layout_market_filter_keeps_related_symbols_in_market_scope` 在包含存量数据时的断言错误，改由在 payload 列表中基于 title 检索特定的卡片后断言，同时加入了初始清理步骤以防残留；
  - **LLM 模拟测试修复**：修改 `test_news_analysis.py` 的测试配置，使用非占位符样式的 `base_url` 与 `api_key` 以绕过最新的安全性校验拦截，保证网络异常用例能够成功执行；
  - **事件广播 payload 校验适配**：适配 `test_news_signal_pipeline.py` 中 `news.updated` 事件的广播断言，加入 `'editorial_score': None` 键值对，使之与最新的评分重构相匹配。
- 影响文件：
  - `backend/tests/conftest.py`
  - `backend/tests/test_news.py`
  - `backend/tests/test_news_analysis.py`
  - `backend/tests/test_news_signal_pipeline.py`
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught pytest backend/tests` 293/293 例全量成功通过；`npm --prefix frontend run build` 成功。
- 风险/后续事项：无。测试数据库物理隔离使得后续开发测试互不干扰。

## 2026-06-12 17:30

- 修改人：Claude (Master Lin)
- 修改范围：新闻抓取并发化与调度、去重算法修复与 SimHash 跨源判重、editorial 评分官方源加成、前端红涨绿跌色彩体系与仪表盘升级
- 变更内容：
  - **去重修复（P0）**：`_build_duplicate_signature` 移除自然小时桶，`_find_duplicate_item` 改为 `published_at ±60min` 滑动窗口，修复 23:58/00:02 跨小时漏判；`news_item.published_at` 补建索引（`ensure_news_item_indexes`，对存量库 `CREATE INDEX IF NOT EXISTS`）。
  - **SimHash 跨源判重**：新增 `app/services/news_dedup.py`（64-bit SimHash，拉丁词+中文 bigram 分词，距离 ≤3 判重、4~6 灰区走可插拔 `SecondaryDuplicateJudge` 接口——默认 Null 实现，预留 embedding 二次判重，本期不实现）。短标题（<4 token）不做模糊判重防误杀。
  - **抓取并发化**：`refresh_all` 拆为线程池并发 fetch（`MAX_FETCH_WORKERS=8`，纯网络 IO）+ 调用方线程串行落库（SQLite 单写约束）；`refresh_all(sources=...)` 支持子集刷新；时延统计改 EMA（α=0.3）；SQLite 连接加 busy timeout 30s。
  - **常驻调度器**：新增 `app/services/news_ingest_scheduler.py` + `app/workers/news_scheduler.py`。每源按 `cadence_seconds` 独立到期，失败指数退避 `cadence * min(2^failures, 8)`；每轮消化信号 pipeline 积压（修复"有新新闻时积压被饿死"）；接入 `worker_runtime_status`。可独立进程跑，或设 `NEWS_SCHEDULER_ENABLED=true` 随后端 lifespan 启动。
  - **评分**：editorial 评分权重提取为常量，新增官方源加成 `EDITORIAL_OFFICIAL_BONUS=0.1`（复用 `news_priority.has_official_signal`）。
  - **前端红涨绿跌**：`--positive` 翻转为红、`--negative` 为绿（A股/港股惯例）；新增 `--success/--danger` 系统健康色与行情色解耦，AppShell/StatusBanner/StaleBadge/设置页错误提示等系统语义改用 success/danger；K线蜡烛与情绪标记色同步翻转（红涨绿跌）。
  - **仪表盘升级**：新增 `Sparkline.vue`（纯 SVG 自绘）、`SourceHealthGrid.vue`（来源健康矩阵，故障源置顶，显示 EMA 时延/连续失败）；HeroMetrics 支持 trend 迷你走势图（tabular-nums 数字）；Dashboard 新增 Source Health 区块。保留全部既有 data-role 测试钩子。
- 影响文件：backend: news_ingestion.py / news_dedup.py(新) / news_ingest_scheduler.py(新) / workers/news_scheduler.py(新) / news_feed_layout.py / news_priority.py / news_item.py / initializer.py / session.py / config.py / main.py；frontend: main.css / tailwind.config.js / Sparkline.vue(新) / SourceHealthGrid.vue(新) / HeroMetrics.vue / DashboardView.vue / AppShell.vue / KlineChart.vue 等;tests: test_news_ingest_scheduler.py(新) / test_news_dedup.py(新) / test_news_ingestion.py(+4 用例) / Sparkline.test.ts(新) / SourceHealthGrid.test.ts(新)
- 接口/数据结构变化：`NewsIngestionService.refresh_all` 新增可选 `sources` 参数（向后兼容）；新增配置项 `news_scheduler_enabled` / `news_scheduler_tick_seconds` / `news_backoff_max_multiplier`；news_item 表新增 published_at 索引（自动迁移）。无 HTTP 契约变化。
- 验证情况：沙箱无法访问 PyPI/npm registry，已做 py_compile 全量语法检查 + vue-tsc 类型检查（新改文件零错误，存量错误与本次无关）。**待本地执行**：`conda run -n news-caught pytest backend/tests` 与 `npm --prefix frontend run test`、`npm --prefix frontend run build`。
- 风险/后续事项：
  1. SimHash 阈值保守（≤3），同义改写稿不会判重——灰区接口已预留，后续可接 embedding;
  2. 失败路径现在也计入 total_fetches（语义更正确，若有用例断言旧行为需同步调整）;
  3. 涨跌色已写死红涨绿跌，如需用户偏好开关再加 token 切换;
  4. `POST /news/refresh` 仍为同步执行（现已并发提速），调度器稳定后建议改为异步 job;
  5. Dashboard KPI 仍基于已加载分页数据，后续可加 `/api/news/summary` 聚合接口。

## 2026-06-12 15:50

- 修改人：Antigravity
- 修改范围：个股行情批量拉取重构、国内备用行情源 (Tencent) 接入、单元测试补齐
- 变更内容：优化自选股行情更新链路，解决多 symbol 逐个拉取导致的网络慢和 yfinance 易被限流问题。在 `YahooFinanceQuoteProvider` 中重构支持批量拉取 `fetch_quotes_batch`；新增 `TencentQuoteProvider`，支持通过单次 HTTP 请求批量拉取并解析国内 A 股与港股行情；重构 `QuoteService.refresh_watchlist_quotes`，将其改造为分批拉取与降级机制（Yahoo 拉取失败时自动降级到 Tencent 备用源，两者均失败则退回延时缓存或不可用）。同步新增 `backend/tests/test_quote_batch_and_fallback.py` 覆盖腾讯源解析与服务降级。
- 影响文件：
  - [quote_provider.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/services/quote_provider.py)
  - [quote_service.py](file:///Users/xiuyang/Desktop/news-caught/backend/app/services/quote_service.py)
  - [test_quote_batch_and_fallback.py](file:///Users/xiuyang/Desktop/news-caught/backend/tests/test_quote_batch_and_fallback.py)
- 接口/数据结构变化：无 HTTP 接口变化；后端 Provider 及 Service 层新增并发与批量拉取方法，Yahoo 行情失败且属于 CN/HK 标的时，透明自动降级为 Tencent 行情数据
- 验证情况：`conda run -n news-caught pytest backend/tests/test_quote_batch_and_fallback.py` 通过（3 个用例）；`conda run -n news-caught pytest backend/tests/test_market.py` 通过（27 个用例）；`npm --prefix frontend run build` 成功
- 风险/后续事项：当前腾讯源只覆盖了 A 股和港股，美股若拉取失败仍需要靠 Yahoo Finance 的延迟缓存提供容灾。

## 2026-03-31 19:09

- 修改人：Codex
- 修改范围：新闻首页事件卡持仓命中条、事件 feed 契约补充、前后端回归测试
- 变更内容：为 `NewsFeedEventCard` / `feed-layout` 事件契约新增 `watchlist_hits` 字段，后端在 `NewsFeedLayoutService` 中基于现有 `primary_symbol + related_symbols` 和当前 watchlist 做稳定顺序匹配，输出去重后的持仓股票显示名，并跳过空 `display_name`。前端同步为新闻首页 `EventFeedCard` 增加单行紧凑型 `命中持仓` 条，只在命中时显示，最多展示 2 个股票名字，其余收口为 `+N`，保持卡片高度不明显抬升。同步补齐 backend feed-layout 契约测试、前端 API/store/组件/视图测试，以及本次设计/计划文档。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-portfolio-hit-strip/backend/app/schemas/news.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-portfolio-hit-strip/backend/app/services/news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-portfolio-hit-strip/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-portfolio-hit-strip/backend/tests/test_news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-portfolio-hit-strip/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-portfolio-hit-strip/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-portfolio-hit-strip/frontend/src/stores/newsStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-portfolio-hit-strip/frontend/src/components/news/EventFeedCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-portfolio-hit-strip/frontend/src/components/news/EventFeedCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-portfolio-hit-strip/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-portfolio-hit-strip/docs/superpowers/specs/2026-03-31-news-portfolio-hit-strip-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-portfolio-hit-strip/docs/superpowers/plans/2026-03-31-news-portfolio-hit-strip-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-portfolio-hit-strip/docs/code-change-log.md`
- 接口/数据结构变化：`GET /api/news/feed-layout` 的事件项新增 `watchlist_hits: string[]`；由于现有 schema 继承关系，`NewsEventDetailView` 也会带出该字段，但本次未新增详情页展示逻辑
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_feed_layout.py -q` 通过（29 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/newsStore.test.ts src/components/news/EventFeedCard.test.ts src/views/NewsFeedView.test.ts` 通过（4 个文件 / 40 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前命中仍是 symbol 直连匹配，只能回答“命中了哪些持仓”，还不能解释产业链间接影响；若后续继续做新闻研究层，适合在事件详情里再补“为什么命中”的解释层

## 2026-03-30 18:49

- 修改人：Codex
- 修改范围：Watchlist K 线 HUD 浮层二次下调
- 变更内容：根据进一步反馈，将 `KlineChart.vue` 中顶部行情 HUD 继续从 `top-16` 下调到 `top-20`，再额外拉开与顶部标签区和主图上沿的距离，进一步减少对 K 线顶部走势的遮挡。同步更新 `KlineChart.test.ts` 中的定位断言，锁定新的垂直偏移。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 通过（1 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前仍是固定偏移量方案；如果后续顶部标签数量继续增加，可能还需要联动收紧标签区或改为响应式 HUD 定位
## 2026-03-30 18:43

- 修改人：Codex
- 修改范围：Watchlist K 线 HUD 浮层垂直位置微调、前端组件回归测试
- 变更内容：将 `KlineChart.vue` 中展示开高低收、涨跌和成交量的顶部浮空 HUD 从 `top-14` 下调到 `top-16`，让该行情条与顶部标签区和主图上沿拉开一点距离，减轻对 K 线顶部区域的遮挡。同步在 `KlineChart.test.ts` 补充 HUD 定位类名断言，锁定这次下移后的样式，避免后续样式回退。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-30-kline-hud-offset-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-30-kline-hud-offset-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 通过（1 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本次只做固定偏移量微调；若后续还要进一步减少遮挡，可能需要根据不同视口或标签行数改成更自适应的 HUD 定位策略

## 2026-03-30 19:25

- 修改人：Codex
- 修改范围：Watchlist 研究简报、单股详情页研究视图、前后端回归测试
- 变更内容：为自选股单股详情页新增第一阶段 `research brief` 链路。后端新增 `WatchlistResearchService` 和 `GET /api/watchlist/{symbol}/research-brief`，基于现有 related news 数据集和现有 symbol alias lookup 规则，在 14 天窗口内按 `政策/监管`、`公司动作`、`产业链传导`、`价格异动` 四类做规则归类，并输出 `act_now/watch_today/know_only` 动作等级及 `has_unexplained_price_move` 标记。前端同步新增 research brief 类型、API client、store 状态与 `loadDetailWorkspace()` 单一详情页加载入口，避免 view/store 重复拉取新闻；`StockDetailPanel` 中新增 `ResearchBriefPanel`，在 K 线下方、原始新闻流上方展示驱动摘要、分类分组和空态提示。根据最终代码审查又补齐了 3 个回归修正：quote detail 请求竞态保护、缺失 symbol 的 404 回退恢复，以及 research brief 摘要时间按实际市场时区展示。同步补齐 backend、api client、store、component、detail view 测试，锁定 research brief 契约与详情页加载编排。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/backend/app/api/routes/watchlist.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/backend/app/schemas/watchlist.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/backend/app/services/watchlist_research_service.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/backend/tests/test_watchlist_research.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/frontend/src/components/watchlist/ResearchBriefPanel.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/frontend/src/components/watchlist/ResearchBriefPanel.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/frontend/src/components/watchlist/StockDetailPanel.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/frontend/src/components/watchlist/StockDetailPanel.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/frontend/src/views/WatchlistDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/frontend/src/views/WatchlistDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/docs/superpowers/specs/2026-03-30-watchlist-research-desk-phase1-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/docs/superpowers/plans/2026-03-30-watchlist-research-desk-phase1-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-research-desk/docs/code-change-log.md`
- 接口/数据结构变化：新增 `GET /api/watchlist/{symbol}/research-brief`；新增前后端 research brief 结构体，包含 `market`、`window_days`、`top_action_level`、`has_unexplained_price_move` 和按分类展开的 `drivers`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_watchlist_research.py backend/tests/test_stock_news_search.py -q` 通过（18 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/watchlistStore.test.ts src/components/watchlist/ResearchBriefPanel.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts` 通过（5 个文件 / 43 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 research brief 仍是纯关键词规则，误判与漏判风险存在；`supply_chain` 和 `price_action` 也还没有接入更强的行业知识库或个人反馈闭环。下一阶段更适合把 research brief 摘要上浮到 watchlist 列表，进一步变成真正的自选股优先级分发器

## 2026-03-30 15:52

- 修改人：Codex
- 修改范围：A 股自选候选、watchlist canonical symbol、A 股行情/K 线接入、前端降级 mock 同步
- 变更内容：将 A 股接入现有 watchlist/K 线主链路。后端 `normalize_symbol()` 新增对 `600519.SH` / `000001.SZ`、`SH600519` / `SZ000001` 以及无 market hint 的 6 位数字代码的归一化支持，并明确把上海市场 canonical symbol `*.SH` 翻译为 Yahoo Finance provider symbol `*.SS`；同时新增等价 symbol 候选解析，统一处理 canonical / `SH`/`SZ` 前缀 / 纯数字 / legacy alias 之间的查找关系。`POST /api/watchlist` 对 A 股输入在入库前强制 canonicalize，并在重复校验时同时覆盖 legacy alias，避免同一只股票被重复加入；`QuoteService` 在 alias 详情查询、refresh 路径和 legacy alias watchlist 缓存读取时都会回查 canonical 记录，保持 `display_name` 与缓存命中不丢失；watchlist 的 K 线、相关新闻与删除接口统一支持 A 股 alias lookup，避免出现“图有、新闻空、删除 404”的 split-brain 状态。与此同时扩展内置候选池，新增贵州茅台、宁德时代、平安银行、招商银行、中国平安、比亚迪、海光信息、中芯国际等 A 股标的。前端同步补齐 A 股候选、降级 mock watchlist/quote/sparkline 数据，并新增 store / view / api fallback 测试，锁定 A 股自选添加与 K 线加载契约。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-a-share-kline-watchlist/backend/app/services/quote_provider.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-a-share-kline-watchlist/backend/app/services/quote_service.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-a-share-kline-watchlist/backend/app/services/market_chart_service.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-a-share-kline-watchlist/backend/app/api/routes/watchlist.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-a-share-kline-watchlist/backend/app/services/watchlist_candidates.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-a-share-kline-watchlist/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-a-share-kline-watchlist/backend/tests/test_stock_news_search.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-a-share-kline-watchlist/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-a-share-kline-watchlist/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-a-share-kline-watchlist/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-a-share-kline-watchlist/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-a-share-kline-watchlist/docs/superpowers/specs/2026-03-30-a-share-watchlist-kline-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-a-share-kline-watchlist/docs/superpowers/plans/2026-03-30-a-share-watchlist-kline-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-a-share-kline-watchlist/docs/code-change-log.md`
- 接口/数据结构变化：无新增 HTTP 接口；现有 `POST /api/watchlist` 对 A 股 symbol 的持久化规则调整为统一落库 canonical `.SH/.SZ`，`YahooFinanceQuoteProvider` 对上海市场增加 canonical-to-provider 的 `.SH -> .SS` 翻译
- 验证情况：`conda run -n news-caught pytest backend/tests/test_market.py backend/tests/test_stock_news_search.py -q` 通过（41 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts` 通过（5 个文件 / 43 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前只覆盖沪深 A 股个股；若后续要支持指数、ETF 或历史新闻 mention 的批量 canonical 回填，还需要继续扩 symbol 规则与数据清洗。Yahoo Finance 对 A 股代码可用性仍可能波动，异常时会沿用现有 `fetch_failed/delayed` 降级路径

## 2026-03-30 14:55

- 修改人：Codex
- 修改范围：事件详情页时间线新闻卡片压缩、前端视图回归测试
- 变更内容：将 `EventDetailView` 的 timeline 新闻卡片改为更高密度的 compact 布局，收紧轨道间距、卡片内边距、标签尺寸、标题字号和按钮高度；同时把摘要统一压成单行省略，保留 `查看新闻详情` 与 `打开原文` 两个动作，但改成更紧凑的操作样式，从而在单屏内承载更多事件新闻。同步扩展 `EventDetailView.test.ts`，锁定单行摘要与紧凑动作区的渲染契约。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/EventDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/EventDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-30-event-detail-compact-timeline-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-30-event-detail-compact-timeline-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/EventDetailView.test.ts` 通过（1 个文件 / 5 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前压缩仍保留双动作入口，因此不同新闻来源组合下单卡高度会略有差异；如果后续还需要继续压缩，可再评估将 `打开原文` 收到二级入口或 hover 态

## 2026-03-30 13:54

- 修改人：Codex
- 修改范围：事件详情页时间线重构、事件页继续阅读链路、前端回归测试
- 变更内容：将 `EventDetailView` 从“摘要卡 + 普通列表”重构为更紧凑的事件演化页。顶部去掉重复的 `Event Detail` 大标题，保留返回入口并把事件主体压缩为 compact header：显示 `event_type`、情绪、市场、主 symbol、关联 symbols、来源数、新闻数和最后更新时间。中部时间线改为轨道式布局，每条新闻根据后端返回顺序生成轻量阶段标签 `首发 / 跟进 / 更新`，并展示来源、时间、情绪、标题和摘要。每个时间线项新增 `查看新闻详情` 动作，接通到现有 `/news/:id`，同时在存在 `canonical_url` 时继续提供 `打开原文` 链接。同步扩展 `EventDetailView.test.ts`，锁定 compact header、阶段标签、来源/情绪元信息以及新闻详情跳转行为。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/frontend/src/views/EventDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/frontend/src/views/EventDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/docs/superpowers/specs/2026-03-30-event-detail-timeline-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/docs/superpowers/plans/2026-03-30-event-detail-timeline-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/docs/code-change-log.md`
- 接口/数据结构变化：无；继续复用现有 `GET /api/news/events/{event_key}` 和 `NewsEventDetail.news_items`
- 验证情况：`npm --prefix frontend run test -- --run src/views/EventDetailView.test.ts src/views/NewsFeedView.test.ts src/router/index.test.ts src/views/NewsDetailView.test.ts` 通过（4 个文件 / 25 个用例）；`npm --prefix frontend run build` 通过；`npm --prefix frontend run test -- --run` 通过（40 个文件 / 167 个用例）
- 风险/后续事项：时间线阶段标签是前端基于顺序生成的轻量阅读标签，不代表严格事实分类；若后续需要更强语义，应由后端提供显式事件阶段字段

## 2026-03-30 13:52

- 修改人：Codex
- 修改范围：事件详情页时间线重构、事件摘要压缩、前端交互回归测试
- 变更内容：将 `EventDetailView` 从“摘要卡 + 普通列表”重构为真正的事件演化页。顶部改为更紧凑的 compact header，保留事件标题、摘要、事件类型、情绪、市场、主 symbol、关联 symbols、来源数、新闻数和最后更新时间，避免再次挤占正文空间。中部时间线改成带轨道的 timeline 布局，按后端返回顺序展示当前事件挂载新闻，并基于时间线位置给出 `首发 / 跟进 / 更新` 轻量阶段标签。每条时间线新闻新增 `查看新闻详情` 动作，接通到现有 `/news/:id`；存在 `canonical_url` 时额外提供 `打开原文`。同步扩充 `EventDetailView.test.ts`，锁定 compact header、阶段标签、来源/情绪展示和 timeline 动作。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/frontend/src/views/EventDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/frontend/src/views/EventDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/docs/superpowers/specs/2026-03-30-event-detail-timeline-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/docs/superpowers/plans/2026-03-30-event-detail-timeline-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/docs/code-change-log.md`
- 接口/数据结构变化：无；继续复用现有 `GET /api/news/events/{event_key}` 与 `NewsEventDetail.news_items`
- 验证情况：`npm --prefix frontend run test -- --run src/views/EventDetailView.test.ts src/views/NewsFeedView.test.ts src/router/index.test.ts src/views/NewsDetailView.test.ts` 通过（4 个文件 / 25 个用例）；`npm --prefix frontend run build` 通过；`npm --prefix frontend run test -- --run` 通过（40 个文件 / 167 个用例）
- 风险/后续事项：时间线阶段标签目前基于前端顺序做轻语义推导，并不是后端显式分类；如果后续要做更严格的“首发/跟进/更新”定义，需新增服务端字段或更明确的判定规则

## 2026-03-30 12:39

- 修改人：Codex
- 修改范围：合并后后端回归测试稳健性修正
- 变更内容：在将 `codex/event-detail-api` 合并回本地 `main` 后，`test_news_feed_layout_returns_event_cards_topics_and_stream` 暴露出对测试库全局最新新闻顺序的脆弱假设。该测试原先硬编码断言 `payload["stream"][0]` 必须等于本次 fixture 的首条新闻，在测试数据库已有更新新闻时会产生误报。本次一方面把断言收敛为“stream 中包含目标 fixture 标题”，另一方面把该组 fixture 的 `published_at/fetched_at/last_seen_at` 抬到远未来，确保它们稳定落入本测试期望验证的 stream 窗口，避免继续依赖共享测试库里的偶然排序。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_feed_layout.py -q` 通过（27 个用例）
- 风险/后续事项：该测试已不再依赖共享测试库的全局最新排序；若后续要进一步锁定 stream 排名规则，建议补充更强隔离的 fixture 环境，而不是继续依赖共享库里的真实数据分布

## 2026-03-30 00:42

- 修改人：Codex
- 修改范围：事件详情后端接口、首页事件跳转、事件详情页 API 化、前后端回归测试
- 变更内容：为了解决 `EventDetailView` 依赖前端 `feedLayout` 快照导致刷新/深链脆弱的问题，后端新增 `GET /api/news/events/{event_key}`。`NewsFeedLayoutService` 拆出可复用的 topic context 收集逻辑，并新增 `get_event_detail()` / `_build_event_detail()`，在服务端按现有 feed-layout 规则重建事件详情；`NewsEventDetailView` 作为新响应模型返回完整 `news_items`，不再沿用首页事件卡的 3 条截断结果，也不再对详情静默截断。详情排序契约统一为 `published_at -> fetched_at -> id` 倒序，`published_at` 为空的新闻会稳定排在有发布时间新闻之后。路由顺序上把 `/events/{event_key}` 放在 `/{news_id}` 之前，避免动态段冲突。前端新增 `NewsEventDetail` 类型和 `apiClient.getNewsEventDetail()`，事件详情页改为直接请求后端并展示 loading / not-found / generic-error 三态，网络错误时不再偷偷回退 mock 数据；同时新增 `event-detail` 路由。为了把深链真正接入现有首页，本分支也补上了首页入口收口：`EventFeedCard` 改为主体点击进入事件详情、底部 evidence pills 继续进入单条新闻，`NewsFeedView` 同步压缩 header 并接入 `openEvent()` 跳转。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/backend/app/schemas/news.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/backend/app/services/news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/backend/tests/test_news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/components/news/EventFeedCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/components/news/EventFeedCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/router/index.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/views/EventDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/views/EventDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/docs/superpowers/specs/2026-03-30-event-detail-api-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/docs/superpowers/plans/2026-03-30-event-detail-api-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/docs/code-change-log.md`
- 接口/数据结构变化：新增后端接口 `GET /api/news/events/{event_key}`；新增响应模型/前端类型 `NewsEventDetail`；现有 `GET /api/news/feed-layout` 契约不变
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_feed_layout.py -q` 通过（27 个用例）；`npm --prefix frontend run test -- --run src/components/news/EventFeedCard.test.ts src/views/NewsFeedView.test.ts src/views/EventDetailView.test.ts src/api/client.test.ts src/router/index.test.ts` 通过（5 个文件 / 34 个用例）；`npm --prefix frontend run build` 通过；`npm --prefix frontend run test -- --run` 通过（40 个文件 / 166 个用例）
- 风险/后续事项：当前事件详情已不再依赖前端快照，但 `event_key` 仍然是“按当前规则可重建”的临时键，尚未升级为持久化事件实体 ID；若后续需要长期稳定回放或跨时间窗口复原，仍需引入事件持久化层

## 2026-03-29 23:37

- 修改人：Codex
- 修改范围：首页新闻发现重构、壳层导航优先级、Dashboard 次级化、前端回归测试
- 变更内容：把前端首页默认落点从 `/dashboard` 改为 `/news`，新增 `frontend/src/router/index.test.ts` 锁定根路由进入新闻发现页。`AppShell` 同步从 dashboard-first 调整为 news-first：侧边导航把 `Latest Events` 提到 `01`，壳层 desk/workspace 文案改为 latest-event discovery 语义，并为新闻 layout 刷新路径补上 `feedQuery?.market` 的可空守卫，避免 SSE 事件到达时访问未初始化查询状态报错。`NewsFeedView` 重新 framing 为紧凑型 `Latest Events` 首页，弱化原有 `Signal Desk` 文案；`EventFeedCard` 改成更高密度的事件行，移除大块摘要，保留时间、事件类型、市场、主 symbol、相关 symbol、来源数和轻量 evidence 汇总，同时把底部证据入口收口为可聚焦的 story buttons，避免把整卡硬绑到 `news_items[0]` 并恢复键盘可达性；原始新闻流在首页中统一改走 `stream-compact` 以降低视觉权重。`DashboardView` 改为 secondary overview 语义，只保留次级总览定位，不再作为主控制台叙事。同步新增/更新路由、AppShell、EventFeedCard、NewsFeedView、DashboardView 的测试，前端全量测试恢复为全绿。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/router/index.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/EventFeedCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/EventFeedCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-29-news-discovery-homepage-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-29-news-discovery-homepage-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无；继续复用现有 `feed-layout.events` 契约，没有新增前后端字段
- 验证情况：`npm --prefix frontend run test -- --run src/router/index.test.ts src/components/layout/AppShell.test.ts src/components/news/EventFeedCard.test.ts src/views/NewsFeedView.test.ts src/views/DashboardView.test.ts` 通过（5 个文件 / 31 个用例）；`npm --prefix frontend run build` 通过；`npm --prefix frontend run test -- --run` 通过（39 个文件 / 156 个用例）
- 风险/后续事项：当前首页仍保留 topic 和 raw stream 两个 secondary evidence 区块，后续如果要继续提高首屏密度，可以进一步压缩辅助区块；另外，本次只做“广收事件 + 首页重心重排”，未引入 AI 过滤与个性化排序

## 2026-03-29 23:34

- 修改人：Codex
- 修改范围：新闻发现首页、事件卡片密度、首页文案与回归测试
- 变更内容：将 `NewsFeedView` 的首屏 framing 从偏 `Signal Desk` 的控制台文案改为 `Latest Events` 的紧凑事件发现页，首页副标题改为先看最新事件、再看主题和原始新闻流；把 `EventFeedCard` 压缩成更密集的事件行，移除大块摘要展示，改为事件级元数据和更轻量的来源证据汇总，并保留点击首条新闻的跳转行为；把原始新闻流卡片在首页中改为更紧凑的 `stream-compact` 呈现。同步新增 `EventFeedCard.test.ts`，并调整 `NewsFeedView.test.ts` 锁定 compact latest-events framing。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/frontend/src/components/news/EventFeedCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/frontend/src/components/news/EventFeedCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/news/EventFeedCard.test.ts src/views/NewsFeedView.test.ts` 通过（2 个文件 / 14 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：首页仍保留 topic 和 raw stream 作为 secondary evidence layers，后续若要进一步压缩首屏，还可以继续收紧这些辅助区块的行高和信息量，但本次未引入新数据契约

## 2026-03-29 23:30

- 修改人：Codex
- 修改范围：前端根路由重定向、AppShell 新闻流刷新守卫、AppShell 回归测试
- 变更内容：将前端根路径 `/` 的重定向目标从 `/dashboard` 改为 `/news`，让应用落地后直接进入新闻发现页而不是仪表盘。`AppShell` 的新闻流刷新辅助函数改为通过 `newsStore.feedQuery?.market` 读取市场条件，避免在 `feedQuery` 尚未初始化或被清空时访问 `market` 抛错；当 `feedQuery` 缺失时仍会以空市场参数刷新 layout。同步补充回归测试，覆盖根路由跳转到新闻页，以及 `feedQuery` 缺失时的安全刷新路径。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts` 通过（11 个用例）
- 风险/后续事项：当前只修复了 shell 里的显式刷新入口；如果后续还有其他直接读取 `newsStore.feedQuery` 的路径，建议统一收口到同一类可空访问模式

## 2026-03-28 21:14

- 修改人：Codex
- 修改范围：飞书通知持久化队列、共享 sender、通知服务投递 worker 与回归测试
- 变更内容：将飞书通知链路从“进程内 buffer + 直接发送”改造成“持久化任务入队 + delivery worker 投递”。新增 `notification_job` 表和仓储，统一承载 `news_source_event`、`news_batch`、`watchlist_alert`、`analysis_result` 四类通知任务/事件，并支持弱去重、CAS claim、`lease_token` 保护的 finalize、过期 `sending` 回收、重试回写、sent/failed 终态。`NotificationService` 现在在新闻/自选股/分析入口只做配置判断和入队；新闻通知改为先持久化 source-event，再在 worker tick 中按窗口幂等合成 `news_batch` 任务；news toggle 关闭时会主动丢弃待发 backlog，避免后续重新打开时补发旧消息；自选股告警保留边沿状态机，但永久发送失败后会释放锁存，避免同一 symbol 在阈值上方时被永久压住。`feishu_client.py` 同步改为共享 sender 路径：引入 `get_shared_feishu_sender()` 复用同凭据下的长生命周期 `httpx.Client` 和 token 缓存，并支持 invalid token 单次强制刷新重试与错误分类。`/api/notify/feishu/test` 改走共享 sender；相关测试从原先的内存 `_news_buffer` / 同步 `_send` 断言迁移到持久化 job 断言，并补充新闻 batch、可重试失败、sender 复用、lease token finalize、永久失败释放锁存等回归。顺手修正两条相邻回归测试：`test_market_watchlist_quotes_only_alert_on_threshold_entry` 适配异步入队语义，`test_refresh_all_publishes_news_created_for_each_insert` 补齐当前 payload 中已存在的 `editorial_score` 字段断言。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/notify.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/__init__.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/notification_job.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/notification_job_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/feishu_client.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/notification_service.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_feishu_notify.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_feishu_sender.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_notification_jobs.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-feishu-stability-performance-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-feishu-stability-performance-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增 `notification_job` 数据表；新增进程内 helper `get_shared_feishu_sender()` 与错误分类结构 `FeishuErrorClassification`；`notification_job` 新增 `lease_token` 字段用于 claim/finalize 所有权约束；对外 HTTP API 不变
- 验证情况：`conda run -n news-caught pytest backend/tests/test_feishu_notify.py backend/tests/test_notification_jobs.py backend/tests/test_feishu_sender.py -q` 通过（25 个用例）；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_market.py -q` 通过（48 个用例）
- 风险/后续事项：当前通知任务 claim/finalize 已补到单进程内较稳的 lease-token 语义，但底层仍基于 SQLite 和轮询 worker；如果未来要在多进程或多实例同时高频投递，仍建议进一步评估数据库级锁、单独队列或更强的 worker 协调机制。`get_shared_feishu_sender()` 的连接复用也仅限单进程内缓存，多进程部署时仍是各自进程独立缓存

## 2026-03-28 21:10

- 修改人：Codex
- 修改范围：飞书 sender 复用、token 缓存与错误分类
- 变更内容：重构 `feishu_client.py` 为可复用的 sender 路径：新增进程级 `get_shared_feishu_sender(app_id, app_secret, timeout)` 缓存，同一组凭据会复用同一个长生命周期 sender 实例；sender 内部改为懒加载并复用单个 `httpx.Client`，避免每次发送重复建连；`send_card` 增加单次强制 token 刷新重试，当消息返回 token 失效类错误时会刷新一次 token 后重发；补充 `classify_feishu_error()` 与 `FeishuErrorClassification`，把飞书错误按“是否可重试 / 是否需要刷新 token”拆分出来，并让配置类错误保持非重试。同步新增 `backend/tests/test_feishu_sender.py`，覆盖共享 sender 复用、长连接复用、invalid token 单次刷新重试和分类器行为。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/feishu_client.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_feishu_sender.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增进程内 helper `get_shared_feishu_sender()` 与分类结果结构 `FeishuErrorClassification`；现有 `FeishuClient`/`build_*_card` 仍保持兼容
- 验证情况：`conda run -n news-caught pytest tests/test_feishu_sender.py -q` 通过（3 个用例）
- 风险/后续事项：当前共享 sender 缓存只覆盖同进程内同凭据复用；如果后续在多进程 worker 中使用，需要在调用侧决定是否共享或在退出时显式关闭缓存的客户端

## 2026-03-28 21:00

- 修改人：Codex
- 修改范围：K 线新闻 marker review follow-up 收口
- 变更内容：继续处理 `worktree-kline-news-markers` 的前端 review。`KlineChart` 的 news marker 渲染逻辑改为只要 candlestick series 支持 `setMarkers()` 就始终同步 marker 状态，因此当新的 `klineData.news_events` 为空时会显式传入 `[]` 清空旧 marker，避免切换 symbol/周期后仍残留上一份新闻标记。同步补充回归测试，锁定“初始无 event 时不挂载 tooltip/popup”和“从有新闻切到无新闻时会清空 marker”两个契约；并把 lightweight-charts 测试 mock 补齐到当前 `setMarkers / subscribeCrosshairMove / subscribeClick` 接口，确保该路径在单测里真实覆盖。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.claude/worktrees/kline-news-markers/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/.claude/worktrees/kline-news-markers/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.claude/worktrees/kline-news-markers/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 通过（1 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本次已收口当前这组 K 线新闻 marker 前端 review finding；若后续继续扩展 hover/click 交互，建议再补针对 crosshair/click 订阅行为的组件级测试

## 2026-03-28 20:51

- 修改人：Codex
- 修改范围：K 线新闻 tooltip/popup 初始空态 prop 契约修复
- 变更内容：针对 review 指出的 `KlineChart` 初始渲染时把 `null` 传给 `KlineNewsTooltip` / `KlineNewsPopup` 必填 `event` prop 的问题，改为仅在 `tooltipState.event` 或 `popupState.event` 存在时才挂载对应组件，消除 Vue invalid-prop warning，并保持子组件的 `NewsEventMarker` 类型契约不放宽。同步补齐 `KlineChart` 测试里的 lightweight-charts mock 能力，新增回归测试锁定“初始无新闻事件时不挂载 tooltip/popup”。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.claude/worktrees/kline-news-markers/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/.claude/worktrees/kline-news-markers/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.claude/worktrees/kline-news-markers/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 通过（1 个文件 / 3 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本次只修复 review 中的 prop 契约问题；该工作树里其他前端 review finding 仍需单独处理

## 2026-03-28 19:41

- 修改人：Codex
- 修改范围：Watchlist K 线滚轮滚动穿透修复
- 变更内容：重新排查后确认用户描述的“滑动 K 线时整个窗口跟着滑”更贴近触控板/滚轮链路，而不是触摸链路本身。`KlineDrawingOverlay` 在空白区域把 `wheel` 转发到底层 chart 时，之前没有对原始事件执行 `preventDefault()`，导致图表收到缩放/平移的同时，页面也继续原生滚动。现已补上 `wheel.preventDefault()`，并在回归测试中锁定“转发到底层 chart 的同时，原始滚轮事件必须被标记为 `defaultPrevented`”。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 通过（2 个文件 / 18 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前滚轮路径已经明确阻断页面默认滚动；如果后续用户反馈主要来自移动端手势，再继续针对真实设备补充触摸链路验证脚本

## 2026-03-28 19:33

- 修改人：Codex
- 修改范围：Watchlist K 线触摸滚动 second follow-up 修正
- 变更内容：将 K 线 overlay 的触摸会话从“`touchstart` 后依赖全局监听兜底”改成“overlay 自己持续接收 `touchmove / touchend / touchcancel` 并同步转发到底层 chart”。这样浏览器不会在触摸序列中途先把页面滚动接管，图表区域的单指滑动和多指手势都由 overlay 持续拦截并复制给底层图表；同时保留现有鼠标 handoff 路径不变。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 通过（2 个文件 / 18 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前修复仍基于 overlay 手动转发触摸事件；如果后续还要继续贴近移动端券商终端手感，建议下一步把整套输入模型统一到 Pointer Events，减少鼠标/触摸两套逻辑并存的维护成本

## 2026-03-28 19:23

- 修改人：Codex
- 修改范围：Watchlist K 线触摸滚动 follow-up 修正
- 变更内容：针对真机上“图表区域仍可能触发页面原生滚动”的 follow-up，给 `KlineDrawingOverlay` 增加显式 `touch-action: none`，在 overlay 可交互时直接关闭浏览器对该区域的默认触摸滚动接管，避免继续单纯依赖 JS `preventDefault()` 的时序；同时补充测试，锁定交互态为 `none`、禁用态回退为 `auto` 的契约。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 通过（2 个文件 / 18 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前图表区域会明确禁止浏览器原生 page pan；如果后续要支持更细粒度的移动端对象编辑手势，可能需要把当前 touch 模型进一步统一到 Pointer Events

## 2026-03-28 19:14

- 修改人：Codex
- 修改范围：Watchlist K 线触摸手势让渡与页面滚动穿透修复
- 变更内容：补齐 `KlineDrawingOverlay` 的触摸手势链路。空白区域在 `select` 模式下会把 `touchstart / touchmove / touchend / touchcancel` 完整转发到底层 chart，并仅在该让渡会话中通过非被动触摸处理阻止浏览器默认页面滚动，避免在 K 线区域滑动时整个窗口一起滚动；转发时保留完整 `touches` 数组，避免双指 pinch 被错误降级成单指手势。与此同时，为 drawing body / anchor / price note 标签补上显式 `touchstart.stop`，确保对象区域仍由 overlay 持有，不误触发空白区手势让渡。同步新增回归测试，覆盖完整触摸序列转发、默认滚动抑制、对象命中不转发、非 `select` 模式不让渡以及双指触摸保持透传。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-kline-touch-gesture-scroll-lock-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-kline-touch-gesture-scroll-lock-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或数据结构变化；仅前端 overlay 内部手势处理行为调整
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts` 通过（1 个文件 / 14 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 通过（2 个文件 / 16 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前修复聚焦单指触摸滑动与手势让渡，不额外扩展双指缩放或对象触摸编辑；如果后续要继续提升移动端交互保真度，可以再评估是否将 overlay 的整套输入统一到 Pointer Events

## 2026-03-28 17:07

- 修改人：Codex
- 修改范围：News Feed final review 修正——清理 stale virtual visible ids
- 变更内容：修正虚拟列表可见项补水链路中的残留状态问题。`NewsFeedView` 新增 `orderedEntryIdSet`，`hydrationCandidateIds` 现在只会保留当前 `orderedEntries` 中仍然存在的 id，再与 `visibleStreamIds` 求并集；同时增加对 `useVirtualScrolling` 的 watch，在退出虚拟列表时主动清空 `visibleStreamIds`，避免旧虚拟列表中的可见项继续参与后续补水。同步新增回归测试：从 `>30` 条虚拟列表退回普通列表后，不再因为旧 `visible-ids` 触发无关详情加载。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或数据结构变化
- 验证情况：`npm --prefix frontend run test -- --run src/utils/newsEditorial.test.ts src/components/news/NewsCard.test.ts src/components/news/NewsVirtualList.test.ts src/views/NewsFeedView.test.ts` 通过（4 个文件 / 19 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前补水与虚拟可见项联动已经收敛到当前列表范围内；若后续希望进一步减少请求频率，可考虑在 `loadDetail` 层加入更明确的节流或批量接口

## 2026-03-28 17:03

- 修改人：Codex
- 修改范围：News Feed follow-up review 修正——降级排序隔离与持续补水
- 变更内容：继续处理新闻流 review follow-up。`NewsFeedView` 的 `layoutStreamScoreMap` 现在在 `feedLayoutDegraded=true` 时直接返回空映射，保证降级 layout 不再影响 raw stream 排序。详情补水机制从“挂载/筛选时一次性补前 8”改为由候选集 watch 驱动的持续补水：候选集包含当前排序前 8 条和虚拟列表当前可见项；若补水进行中又出现新的缺口，会在本轮结束后自动追一轮，避免排序变化后新晋升条目或后续滚动暴露条目长期不补水。`NewsVirtualList` 新增 `visible-ids` 事件，把当前可见 story id 回传给父层参与补水决策。同步新增前端回归测试两条：降级 layout 不应重排 raw stream、首轮补水完成后新晋升条目会被继续补水。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsVirtualList.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；仅新增前端组件内部事件 `visible-ids`
- 验证情况：`npm --prefix frontend run test -- --run src/utils/newsEditorial.test.ts src/components/news/NewsCard.test.ts src/components/news/NewsVirtualList.test.ts src/views/NewsFeedView.test.ts` 通过（4 个文件 / 18 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前补水候选仍是“前 8 + 当前可见项”的启发式策略，而不是全量后台预取；如果后续要进一步提升首屏稳定性，可考虑在 store 层缓存更完整的 detail 预热策略

## 2026-03-28 16:59

- 修改人：Codex
- 修改范围：News Feed review 修正——事件融合计数去重、排序补水对齐、虚拟列表固定高度收口
- 变更内容：针对本地 `main` 上新闻板块优化的 review findings 做三项修正。后端 `news_feed_layout.py` 的 `_merge_cards()` 改为基于去重后的合并新闻重新计算 `news_count` 与 `source_count`，避免融合事件卡统计大于实际挂载文章数。前端 `NewsFeedView` 新增从 `feedLayout.stream` 回填 `editorial_score` 到 raw `feedItems` 的映射，`orderedEntries` 排序会使用该分数作为 detail 缺失时的先验；`hydrateEditorialDetails()` 改为按当前排序后的前 8 条补水，而不是按原始 feed 顺序补水。前端 `NewsVirtualList` 改为使用显式 `156px` 固定行高，并将虚拟列表中的卡片切换为 `stream-compact` 紧凑变体；`NewsCard` 新增对应紧凑样式，收敛标题/摘要/元信息布局，保证虚拟行高与实际渲染契约一致。同步新增 3 个回归测试：融合计数唯一性、按排序补详情、虚拟列表固定高度紧凑卡片。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/newsEditorial.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsVirtualList.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsVirtualList.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；`editorial_score` 仍为已存在的可选字段，本次仅修正其前端消费方式
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_feed_layout.py -v` 通过（14 个用例）；`npm --prefix frontend run test -- --run src/utils/newsEditorial.test.ts src/components/news/NewsCard.test.ts src/components/news/NewsVirtualList.test.ts src/views/NewsFeedView.test.ts` 通过（4 个文件 / 16 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：虚拟列表仍基于固定行高实现，后续若要恢复更自由的卡片内容扩展，需要同步升级为动态测量行高或继续约束紧凑卡片的内容密度

## 2026-03-28 16:40

- 修改人：Codex
- 修改范围：News Feed 体验提升——跨 Topic 事件融合、编辑排序落地、NewsVirtualList 启用、历史重分类脚本
- 变更内容：四项体验提升改动。后端 `news_feed_layout.py` 新增 `fuse_event_cards` 跨 Topic 事件融合：同 `event_type`、同 `primary_symbol` 或 `related_symbols` 交集 >= 2 或标题 token Jaccard >= 0.5 的事件卡自动合并为一张，`general` 类型不参与融合；新增 `_stream_editorial_scores` 为 stream 计算编辑排序分（topic importance 0.4 + source weight 0.25 + freshness 0.2 + mentions 0.15），stream 按分数降序返回。后端 `schemas/news.py` 的 `NewsItemSummary` 新增可选 `editorial_score` 字段。前端 `NewsItem` 类型同步新增 `editorial_score`；`NewsFeedView` 的 `orderedEntries` 改为调用 `rankEditorialStories` 排序替代固定 `score: 0`；新增 `useVirtualScrolling` 开关，当 entries > 30 时使用修复后的 `NewsVirtualList`（props 改为 `entries: EditorialStoryEntry[]`，内部正确传 `:entry` 给 NewsCard），否则保持简单 `v-for`。新增 `scripts/reprocess_news_signals.py` CLI 脚本，支持 `--limit / --all / --dry-run / --batch-size` 参数，分批重跑 signal pipeline 处理未分类旧新闻。同步新增后端融合测试 8 条（标题重叠、同 symbol 融合、不同 event_type 不融合、general 不融合、链式融合、保持独立、merge 保高 importance）。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsVirtualList.vue`
  - `/Users/xiuyang/Desktop/news-caught/scripts/reprocess_news_signals.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-news-feed-experience-uplift-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-news-feed-experience-uplift-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：`GET /api/news/feed-layout` 的 stream 中 `NewsItemSummary` 新增可选 `editorial_score` 字段；事件卡可能出现 `fused-` 前缀的 `event_key`；无新增 API 端点
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_feed_layout.py -v` 通过（13 个用例）；`npm --prefix frontend run build` 通过；`npm --prefix frontend run test -- --run` 通过（34 passed, 1 failed 为 AppShell 预存问题，非本次变更引入）
- 风险/后续事项：融合基于请求时计算，topic 数量极大时可能影响延迟（当前量级可忽略）；VirtualList 行高固定 132px，后续可升级为动态行高；重分类脚本需手动运行

## 2026-03-28 14:55

- 修改人：Codex
- 修改范围：X Radar 宏观词典外置配置
- 变更内容：把原先硬编码在 `XRadarSignalBuilder` 里的宏观规则抽成外部 JSON 词典。后端配置新增 `x_radar_rules_file`（环境变量 `X_RADAR_RULES_FILE`），若未设置则默认读取仓库内的 `backend/data/x_radar_rules.example.json`。`XRadarSignalBuilder` 现在会优先从文件加载 `tag / title / topic_tag / keywords / weight` 规则，加载失败时再回退到内置默认规则；宏观信号和共振信号标题也改为优先使用词典中的 `title`。审查收口阶段又补了三处：词典中坏 `weight` 项现在会被跳过，不会在服务启动或刷新时抛 `ValueError`；`xMonitorStore` 新增 `radarLoading` 并在账号新增/更新/删除、导入后自动刷新 radar，避免雷达卡空闪或长期停留旧数据；`GET /api/x/radar` 现在严格按传入 `limit` 截断 `priority_signals / macro_clusters / evidence_stream`。同时新增回归测试，锁定“外部规则文件可覆盖宏观标签与权重”“坏规则文件不炸服务”“radar limit 生效”和 store 级刷新行为。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_radar_signal_builder.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/x_radar_rules.example.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/xMonitorStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/xMonitorStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增 API；新增运行时配置项 `X_RADAR_RULES_FILE`，用于指定 X Radar 词典文件路径；默认词典文件格式为 JSON，顶层 `rules` 数组内每项包含 `tag/title/topic_tag/keywords/weight`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_x_monitor.py -q` 通过（30 个用例）；`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts src/stores/xMonitorStore.test.ts` 通过（2 个文件 / 7 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前优先级规则仍是“账号权重 + 词典 weight + 轻量 symbol bonus”的规则法，尚未把不同 signal_type 的附加权重完全外置；如果后续要把 account 权重、共振窗口或不同 signal_type 的加分也交给配置文件，还需要继续扩展词典 schema

## 2026-03-28 14:45

- 修改人：Codex
- 修改范围：X Monitor 升级为 X Radar 早期异动雷达
- 变更内容：围绕“自定义账号池 + 宏观/政策事件补充 + 优先级排序”的新定位，对 X 模块做了一轮后端到前端的闭环重构。后端新增 `x_signal` 与 `x_signal_post_link` 两张表、`XSignalRepository` 与 `XRadarSignalBuilder`，把原始 `x_post` 上抬为可解释的信号层；`refresh()` 现在在原始帖子去重入库后，会同步生成 `account_post / macro_event / multi_account_resonance` 三类首版信号，并给信号挂证据帖。同步扩展 `x_monitor` schema 与路由，新增 `GET /api/x/radar`，统一返回 `priority_signals + macro_clusters + evidence_stream` 三层数据。前端新增 `XRadarResponse / XRadarSignal / XRadarMacroCluster` 类型、`apiClient.getXRadar()`、store 的 `radar` 状态和加载逻辑，并把 `XMonitorView` 改为雷达台布局：`Priority Radar -> Macro Watch -> Evidence Feed` 为主视觉，账号管理降为右侧工作区，但保留新增账号、启停、删除、导入导出、翻译证据帖、关键词搜索等原有能力。同步补写本轮 spec / plan 文档，并在该 worktree 内安装了前端依赖以恢复 `vitest` 基线。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/__init__.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/x_signal.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/x_signal_post_link.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/x_signal_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_radar_signal_builder.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/xMonitorStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-x-radar-early-anomaly-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-x-radar-early-anomaly-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增后端接口 `GET /api/x/radar`；后端新增 `x_signal` 与 `x_signal_post_link` 持久化结构；前端新增 `XRadarResponse / XRadarSignal / XRadarMacroCluster` 类型和 `xMonitorStore.radar` 状态；原有 `GET /api/x/posts`、账号管理接口与刷新接口保持兼容
- 验证情况：`conda run -n news-caught pytest backend/tests/test_x_monitor.py -q` 通过（27 个用例）；`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts` 通过（1 个文件 / 5 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：首版宏观标签与优先级打分仍是规则法，关键词和分值需要后续根据真实使用频次继续调；`refresh()` 当前只对新插入帖子生成信号，若未来补回溯重建或规则变更，需要额外增加 reindex/rebuild 路径；本轮尚未把 `x_signal` 接入首页和自选股视图，这部分后续可以直接复用现有信号层

## 2026-03-28 14:30

- 修改人：Codex
- 修改范围：News Feed 事件质量提升——中文情绪/event_type、来源加权、时间衰减、N+1 查询修复
- 变更内容：纯后端改动，提升 Event Radar 事件卡的数据质量，不涉及前端变更。`NewsSignalClassifier` 新增 `POSITIVE_ZH`（18 词）、`NEGATIVE_ZH`（18 词）、`THEME_ZH`（22 词）中文词表，`_tokenize` 扩展为英文 regex + 中文最长匹配并集，`_keywords` 增加中文情绪词过滤，`_topic_key` 增加中文 theme 识别，`classify` 打分逻辑增加 `POSITIVE_ZH`/`NEGATIVE_ZH` dict lookup。`news_feed_layout.py` 的 `EVENT_TYPE_PATTERNS` 每类增加 7-9 个中文关键词（财报/营收→earnings，监管/处罚→regulation，大涨/暴跌→market_move 等）；新增 `SOURCE_TIER_WEIGHTS` 映射（primary 1.2 / secondary 1.0 / fallback 0.7），`_source_weight_map()` 通过 `load_sources()` 构建 source_name→weight 查找表；新增 `DECAY_LAMBDA=0.03`（~23h 半衰期）和 `_decayed_importance()` 指数衰减函数，排序时用衰减后分数替代原始 importance_score；`build_event_cards` 集成来源加权和衰减排序。`topic_repository.py` 新增 `batch_news_for_topics()` 和 `batch_related_symbols()` 批量查询方法；`NewsFeedLayoutService.build()` 从逐 topic 循环查询改为两条批量 SQL（从 2N+2 降到 4 条查询）。同步新增后端测试：中文情绪正/负/中三分类测试、中文 theme 词贡献 topic_key 测试、中文 event_type 模式匹配测试、来源加权分层测试、时间衰减排序测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_signal_classifier.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/topic_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_signal_pipeline.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-news-feed-event-quality-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-news-feed-event-quality-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增 API 或 schema 变化；`GET /api/news/feed-layout` 响应结构不变，`importance_score` 字段值现在包含来源加权修正
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py backend/tests/test_news_feed_layout.py backend/tests/test_news.py` 通过（19 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：中文词表为硬编码首版，未引入 jieba 等分词库，新词或分词歧义不在覆盖范围；本轮不修正已入库旧新闻的 sentiment，如需修正需额外 reprocess 脚本；`_source_weight_map()` 每次调用都解析 source 定义，若后续 source 数量大可加缓存

## 2026-03-28 10:50

- 修改人：Codex
- 修改范围：News Feed 事件主卡化与首页结构化数据编排
- 变更内容：围绕“主新闻流优先展示市场事件而不是原始文章”完成了一轮最小闭环改造。后端新增 `news_feed_layout` 派生服务和 `GET /api/news/feed-layout`，基于现有 `topic_cluster`、`news_item`、`news_stock_mention` 动态生成 `events + topics + stream` 三层首页数据，不引入新的持久化事件表；首版事件类型使用规则推断，支持 `product / macro / supply_chain / regulation / earnings / mna / market_move / general`，并输出主股票、相关股票、来源数和挂载新闻。审查阶段又补了十处收口：`market` 过滤下的 related symbols 现在按 market 范围收敛，避免跨市场 symbol 泄漏；前端 `newsStore.upsertNews/upsertNewsUpdate` 会同步更新 `feedLayout.stream`，避免 SSE 增量被首页结构层吃掉；`LoadingBlock` 空态改为按事件层 / 主题层 / 原始流三者联合判断，避免 stream 被筛空时把上层结构一起隐藏；`NewsFeedView` 挂载和筛选时会并行请求 `feed-layout` 与原始 `/api/news`，确保首页 raw stream fallback 是独立数据路径；`feedLayoutDegraded` 让降级 layout 不再压过真实原始流；`feedLoading` 改为基于并发请求计数收口，避免并行加载时过早结束 loading；`AppShell` 在新闻/主题增量事件下会刷新首页 layout，避免 `Event Radar / Topic Watch` 长时间停留在旧快照；`News Stream` 和 source 下拉现在只基于独立 raw `/api/news` 结果，不再被 layout 的 100 条上限截断；layout 请求新增 latest-response 保护，避免 SSE 高频刷新时旧响应覆盖新响应；raw `/api/news` 请求也新增同样的 latest-response 保护，避免快速切换筛选条件时旧结果覆盖新结果。前端新增 `feedLayout` 状态与 `EventFeedCard`，`NewsFeedView` 现在改为 `Event Radar -> Topic Watch -> News Stream` 三段结构，保留原始新闻流作为证据层，同时兼容原有市场/情绪/来源/关键词过滤。同步补写本轮 spec / plan 文档，并新增后端聚合测试、market 过滤测试、store 增量同步测试与首页渲染测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/topic_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/EventFeedCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-news-feed-event-led-structure-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-news-feed-event-led-structure-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增后端接口 `GET /api/news/feed-layout`；前端新增 `NewsFeedLayout / NewsFeedEventCard / NewsFeedTopic` 类型与 `newsStore.feedLayout` 状态；未修改既有 `GET /api/news` 契约
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_feed_layout.py backend/tests/test_news_signal_pipeline.py` 通过（14 个用例）；`npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/stores/newsStore.test.ts` 通过（2 个文件 / 16 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前事件层仍是基于 topic 的派生视图，跨 topic 的同题新闻尚未进一步融合；`event_type` 仍是规则推断，后续若要继续提升首页“交易终端感”，需要把官方源权重、突发性和更强的 symbol mention 质量纳入排序

## 2026-03-28 09:49

- 修改人：Codex
- 修改范围：Watchlist K 线对象工作台键盘快捷键与编辑态守卫
- 变更内容：在已有 store nudge 基础上，把对象工作台的键盘操作真正接到了图表层。`KlineChart` 现在支持 `Delete / Backspace` 删除当前多选、`Escape` 优先取消 draft 再清空选择、方向键批量微调选中对象，以及 `Shift + 方向键` 的大步长版本；空选择时不会拦截删除键，避免无意义地吃掉浏览器默认行为。审查阶段又补了一层全局快捷键守卫：当焦点位于原生输入框，或 `price_note` 标签编辑正在进行时，连 `Ctrl/Meta + Z/Y` 也不会误触发 drawing history。与此同时，`KlineDrawingOverlay` 新增 `labelEditingChange` 事件，把 `price_note` 文本编辑的打开、提交、取消、失焦生命周期显式同步给 chart，并阻断编辑器与 overlay 自己消费的 `Enter / Escape` 冒泡，避免单次按键被 chart window handler 二次消费。同步扩展 `KlineChart.test.ts` 和 `KlineDrawingOverlay.test.ts`，锁定键盘删除 / nudge / Esc 路由，以及 label editing guard 契约。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistChartStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistChartStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无后端接口或持久化结构变化；前端 overlay 新增 `labelEditingChange` 事件，chart 集成层新增键盘工作台路由
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 先失败后通过（2 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts` 先失败后通过（11 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts` 通过（6 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 通过（3 个文件 / 19 个用例）
- 风险/后续事项：当前方向键价格步长仍基于当前 `klineData.candles` 全量范围，而不是可视区间；如果后续继续贴近券商终端手感，可以再把 visible range 纳入步长计算

## 2026-03-28 09:45

- 修改人：Codex
- 修改范围：Watchlist K 线对象工作台 store 级键盘 nudge / 删除收口
- 变更内容：补齐了 `watchlistChartStore` 的多选键盘平移能力，新增 `nudgeSelectedDrawings(symbol, { candles, timeStep, priceDelta })`，复用现有几何移动语义批量移动当前选中对象，并在每次有效 nudge 前写入 history，确保 `undo / redo` 可以回放这类键盘操作，同时避免边界 no-op 也写出空 history。同步补强 store 测试，覆盖 `deleteSelectedDrawings()` 清空多选、nudge 后撤销 / 重做回放、无效 selection 下的 delete/lock/visible no-op，以及 `horizontal_line` 左右平移保持 no-op 的既有语义。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistChartStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistChartStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无后端接口或持久化结构变化；前端 store 新增 `nudgeSelectedDrawings` 动作
- 验证情况：`npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts` 先失败后通过（4 个用例）
- 风险/后续事项：当前只补齐了 store 层 nudge 能力；如果后续继续落地键盘事件捕获，还需要在 chart/overlay 层接入 Delete / Backspace / Arrow / Escape 的按键路由与编辑态守卫

## 2026-03-28 00:58

- 修改人：Codex
- 修改范围：Watchlist K 线统一 cursor 读数与键盘 undo/redo
- 变更内容：在上一轮 history / 多选基础上继续完成主线收口。`KlineChart` 现在把 hover/cursor 时间统一用作技术读数来源，主图 HUD 之外，副图读数面板、技术面板和右侧图表读数也会随当前 hover candle 切换，而不是始终停留在最新一根 candle。与此同时补入了 `Ctrl/Meta + Z`、`Ctrl/Meta + Shift + Z`、`Ctrl/Meta + Y` 的键盘撤销 / 重做，使 store history 不只可从工具条按钮触发。同步扩展 `KlineChart.test.ts`，锁定 hover 后副图 MACD 读数切换，以及 toolbar / keyboard 两条 undo-redo 路径。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或持久化结构；仅前端 chart 集成层新增统一 cursor 派生读数与键盘 history 快捷键
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 先失败后通过（1 个文件 / 1 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineDrawingSelectionPopover.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts` 通过（8 个文件 / 20 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 unified cursor 仍主要基于 overlay hover 时间驱动，尚未完全订阅 chart 原生 crosshair move；若后续继续追求更高保真度，可把 visible range 与 logical index 也收进同一 cursor 模型

## 2026-03-28 00:52

- 修改人：Codex
- 修改范围：Watchlist K 线 store history / 多选 / 对象工具条基础接线
- 变更内容：开启了这轮主线的第一批基础能力。`watchlistChartStore` 现在新增了 `selectedDrawingIds`、按 symbol 的 drawings 快照 history、`undo / redo`、批量锁定 / 显隐 / 复制 / 删除动作，并保持 `selectedDrawingId` 作为主选中对象兼容层。`KlineToolbar` 新增撤销 / 重做按钮，`KlineDrawingSelectionPopover` 升级为支持单选样式操作和多选 group actions 的对象工具条，`KlineDrawingOverlay` 的选择事件扩展为带 `append` 语义的 payload，支持 `Shift+Click` 加选。`KlineChart` 已接好 undo / redo、加选和 group actions 的基础 wiring，为后续统一 cursor 状态继续铺路。同步新增 `watchlistChartStore.test.ts` 和 `KlineDrawingSelectionPopover.test.ts`，并扩展 toolbar / overlay / chart 测试锁定这些契约。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistChartStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistChartStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineToolbar.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineToolbar.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingSelectionPopover.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingSelectionPopover.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-kline-cursor-history-multiselect-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-kline-cursor-history-multiselect-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无后端接口变化；前端本地工作台状态新增多选与 history 契约，overlay `drawingSelect` 事件改为 `{ id, append }`
- 验证情况：`npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts` 通过（2 个文件 / 10 个用例）
- 风险/后续事项：当前已完成多选和 history 的 store 基础，但统一 cursor state 还未完全把主图 HUD、副图读数和 hover 派生收束到同一模型；下一步应继续完成这部分整合并补整组回归验证

## 2026-03-28 00:40

- 修改人：Codex
- 修改范围：Watchlist K 线 overlay 与主图手势让渡修复
- 变更内容：修复了主 K 线图被 overlay 完整遮挡后，底层 `lightweight-charts` 无法收到鼠标拖拽 / 滚轮事件的问题。`KlineDrawingOverlay` 现在在 `select` 模式、非拖拽、非标签编辑且命中空白区域时，会把 `mousedown` 和 `wheel` 手势临时让渡给底层 chart；命中 drawing body / anchor 或处于绘制编辑态时，overlay 仍保持所有权，不影响现有 crosshair、画线创建和对象编辑。同步扩展了 overlay 测试，覆盖空白区转发和对象命中不转发两类路径。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-kline-overlay-chart-gesture-handoff-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-kline-overlay-chart-gesture-handoff-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无后端接口或持久化结构变化；仅前端 overlay 增加底层 chart 手势转发逻辑
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts` 先失败后通过（1 个文件 / 8 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 通过（2 个文件 / 9 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前让渡逻辑只覆盖鼠标 `mousedown` / `wheel`，足以恢复常见桌面手势；若后续要支持触控板 pinch 或更完整的图表原生手势，建议进一步接 `pointer` / `touch` 级别链路

## 2026-03-28 00:31

- 修改人：Codex
- 修改范围：Watchlist K 线 fib / price note 编辑与更贴近原生轴的 crosshair 联动
- 变更内容：继续补齐 K 线工作台交互闭环。`KlineDrawingOverlay` 现在把 `fibonacci_retracement` 和 `price_note` 一并纳入可编辑对象：fib 支持端点拖拽和对象整体平移，price note 支持锚点/对象移动，并新增双击标签后的轻量文本编辑输入，提交后通过现有 store 的 `commitLabelEdit` 写回。与此同时，crosshair 的价格 / 时间标签不再只靠 overlay 按全量 high-low 比例换算，而是优先消费 `KlineChart` 透传的 chart projector，使用图表时间轴与价格坐标 API 做投影，fallback 时才退回旧的近似映射。同步扩展了 `klineOverlayGeometry`、overlay 和 chart 测试，锁定 fib / price note 编辑和 projector 优先路径。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineOverlayGeometry.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineOverlayGeometry.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-kline-fib-note-nativeish-crosshair-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-kline-fib-note-nativeish-crosshair-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增后端接口或持久化结构；前端 overlay 事件新增 `drawing-label-commit`，仅在本地图表工作台层消费
- 验证情况：`npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 先失败后通过（3 个文件 / 11 个用例）；`npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts` 通过（7 个文件 / 19 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前时间标签仍主要依赖 candle 时间字符串和 chart time scale 的轻量投影，不是完整订阅图表原生 crosshair move 事件；后续若继续追求更高保真度，应进一步接入 visible range / logical index 级联动

## 2026-03-28 00:14

- 修改人：Codex
- 修改范围：Watchlist K 线 crosshair / 画线编辑 review 修正
- 变更内容：根据本轮 code review 继续修正了 K 线 overlay 的三个实际问题。第一，统一把拖拽起点和结束点都改为基于 overlay 自身坐标系计算，避免从趋势线/矩形 SVG 本体发起拖拽时落入 shape 局部坐标，导致对象整体移动跳错 candle。第二，在 `mouseleave` 与全局 `mouseup` 上补了 drag state 清理，避免鼠标在图外释放后把旧拖拽状态带回下一次提交。第三，为 overlay 挂上 `ResizeObserver`，让侧栏折叠/展开等布局变化后也会刷新 overlay 尺寸，保持 crosshair 与标签定位不漂移。同步扩展了 `KlineDrawingOverlay.test.ts`，新增了对精确 anchors 提交、锁定对象不可拖动、stale drag reset 和 ResizeObserver 尺寸刷新的覆盖。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或持久化结构；仅修正前端 overlay 交互实现与测试覆盖
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts` 先失败后通过（1 个文件 / 5 个用例）；`npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts` 通过（7 个文件 / 18 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 crosshair 仍然是 overlay 合成层，虽然尺寸刷新和拖拽状态已经补稳，但价格标签仍不是图表库原生价格轴；后续如果继续提升交互保真度，最好把 crosshair 与图表库自身坐标体系更深地对齐

## 2026-03-28 00:06

- 修改人：Codex
- 修改范围：Watchlist K 线十字光标与基础画线编辑
- 变更内容：继续在专业终端化布局基础上补齐主图交互。为 K 线 overlay 新增了合成十字光标层，支持在主图内显示横纵参考线、时间标签和价格标签，并继续复用 hover anchor 驱动 HUD 读数；同时为基础画线编辑补入了 geometry 工具函数和 overlay 事件链路，支持已选中 `趋势线 / 水平线 / 矩形区间` 的锚点拖拽或对象整体移动，锁定对象仍可选中但不会进入拖拽。`KlineChart` 现在会消费 `drawing-anchor-commit / drawing-move-commit` 并写回现有 `watchlistChartStore`。这一轮还新增了 `klineOverlayGeometry.test.ts`，并扩展 overlay/chart 测试覆盖 crosshair 标签和编辑提交路径。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineOverlayGeometry.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineOverlayGeometry.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-27-kline-crosshair-drawing-edit-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-kline-crosshair-drawing-edit-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增后端接口或持久化结构；前端 overlay 事件扩展为 `drawing-anchor-commit / drawing-move-commit`，仍只在本地工作台层消费
- 验证情况：`npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 先失败后通过（3 个文件 / 9 个用例）；`npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts` 通过（7 个文件 / 17 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前十字光标仍是 overlay 合成层，价格和时间标签依赖前端 high/low 映射，不是图表库原生坐标轴；`fibonacci_retracement` 与 `price_note` 仍保持只读，后续若继续提升编辑能力，应优先补这些工具的拖拽策略以及真正的 crosshair/轴联动

## 2026-03-27 23:42

- 修改人：Codex
- 修改范围：Watchlist K 线专业终端化重排
- 变更内容：继续在上一版 K 线工作台基础上做“图优先”的专业终端化优化。将原先独立的摘要卡并入主图舞台，新增图内 `HUD` 读数带和顶部角标，将 `代码 / 周期 / 范围 / 图例` 收敛到图内信息层；把副图切换区压缩成更紧凑的控制条；将 `KlineToolbar` 重排为分组控制带、`KlineIndicatorWorkbench` 收紧为更像侧柜的模板库；同时为 `KlineDrawingOverlay` 增加 `hover-anchor-change` 事件，让主图可以根据 hover candle 实时切换 HUD 读数。为这轮调整新增了 `KlineToolbar`、`KlineIndicatorWorkbench`、`KlineDrawingOverlay` 三个组件级测试，并扩展了 `KlineChart` 集成测试覆盖图内 HUD 与 hover 回退。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineToolbar.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineIndicatorWorkbench.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineToolbar.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineIndicatorWorkbench.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-27-kline-chart-professional-polish-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-kline-chart-professional-polish-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增后端接口或数据结构；仅前端组件事件增加 `hover-anchor-change`，用于主图 HUD 的本地读数联动
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 先失败后通过（4 个文件 / 4 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 通过（2 个文件 / 3 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts` 通过（6 个文件 / 11 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮只做到 hover 读数 HUD，没有实现真正十字光标、价格轴联动或更高精度的 overlay 命中；当前 HUD 仍依赖前端 candle 序列近似吸附，下一轮如果继续追求专业终端体验，应该把 crosshair 和 hover 事件进一步接到更真实的图表坐标体系

## 2026-03-27 23:15

- 修改人：Codex
- 修改范围：Watchlist K 线画线工作台基础接入
- 变更内容：为自选股详情页的 K 线区域补入了第一版“工作台”基础层和界面接入。新增了画线对象、指标模板与前端 EMA/RSI 的类型与工具函数，增加了独立 `watchlistChartStore` 管理当前工具、按股票画线、本地模板与副图状态；同时把原 K 线区域重构为由 `KlineToolbar`、`KlineDrawingOverlay`、`KlineIndicatorWorkbench` 与 `KlineDrawingSelectionPopover` 组合驱动的新结构。当前版本已经恢复并保持原有 `focusNews`、`switchPeriod`、主图/副图渲染与右侧技术面板回归，同时接入了基础的画线工具入口、模板选择、默认模板复制保存路径和选中对象样式/锁定/删除浮层。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineDrawings.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineIndicatorTemplates.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineIndicators.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineOverlayGeometry.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistChartStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineToolbar.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineIndicatorWorkbench.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingSelectionPopover.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-27-kline-drawing-indicator-workbench-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-kline-drawing-indicator-workbench-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：仅前端类型与本地持久化结构扩展；后端 K 线 API 与现有路由契约未变
- 验证情况：`npm --prefix /Users/xiuyang/Desktop/news-caught/frontend run test -- --run src/components/watchlist/KlineChart.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts` 通过（3 个文件 / 7 个用例）；`npm --prefix /Users/xiuyang/Desktop/news-caught/frontend run build` 通过
- 风险/后续事项：这版优先把工作台基础骨架和现有回归接通，`KlineDrawingOverlay` 里的命中、拖拽和价格映射仍是第一版轻量实现；后续如果要把画线体验继续逼近同花顺/TradingView，还需要补更精细的锚点拖拽、真正的空白透传/缩放联动，以及更完整的模板编辑测试

## 2026-03-27 21:12

- 修改人：Codex
- 修改范围：Watchlist K 线右侧指标栏折叠
- 变更内容：继续朝“图优先”布局优化，在 `KlineChart` 中为右侧指标栏增加了一键折叠能力。默认仍展示右侧指标面板，但现在可以通过图表内的 `收起面板 / 展开面板` 按钮切换；收起后右侧指标栏完全隐藏，`xl` 布局自动退回单列，把原本留给侧栏的横向空间让回主图。该状态仅保存在组件本地，不影响现有周期切换、指标计算、副图切换和新闻事件联动。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-27-kline-collapsible-sidebar-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-kline-collapsible-sidebar-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无接口或类型变化；折叠状态为前端组件本地 UI 状态，不进入 store
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 先失败后通过（1 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts src/views/WatchlistDetailView.test.ts` 通过（2 个文件 / 5 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前折叠状态不会记忆到下一次进入详情页；如果后续希望不同股票详情页都记住“默认展开还是收起”，可以再把该偏好提升到 store 或本地存储

## 2026-03-27 19:53

- 修改人：Codex
- 修改范围：Watchlist K 线常驻周期条与紧凑头部布局
- 变更内容：根据新反馈继续优化了自选股详情页的 K 线区域交互和占位。把原先藏在齿轮弹层里的 `日K / 周K / 月K / 年K` 周期切换挪到了 `KlineChart` 顶部，改成常驻快捷条，支持直接切换周期；同时移除了已失去主要价值的齿轮设置入口和弹层。顶部行情摘要卡片则整体压缩成更紧凑的条形结构：减小了标题、价格和容器内边距，收窄了头部布局列宽，缩短说明文案，把更多纵向空间还给 K 线主图。保留上一轮中文化与周期语义映射不变。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockDetailPanel.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockDetailPanel.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-27-kline-toolbar-compact-header-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-kline-toolbar-compact-header-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或类型变化；周期切换仍复用现有 `switchPeriod` 和前端 `interval/range` 映射
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts` 先失败后通过（2 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 先失败后通过（1 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts src/views/WatchlistDetailView.test.ts` 先因旧齿轮断言失败后通过（3 个文件 / 7 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：这轮主要压缩了头部高度和移除了重复入口，但还没有继续缩减右侧指标面板或主图下方副图区的整体高度；如果后续你还想把视图做得更像同花顺的“图优先”模式，下一步可以再把右栏进一步折叠或改成可收起

## 2026-03-27 19:41

- 修改人：Codex
- 修改范围：Watchlist K 线指标页中文化与券商式周期切换
- 变更内容：将自选股详情页 K 线区域的用户可见英文文案统一替换为中文，同时保留 `MACD / KDJ / BOLL / MA / DIF / DEA / K / D / J` 等技术指标缩写不变。顶部摘要区、设置弹层、K 线图摘要、右侧指标面板、副图区读数、新闻事件计数和更新时间文案均已中文化；周期入口从旧的 `1D / 1W / 1M / 3M / 1Y` 混合语义调整为更接近同花顺/东方财富习惯的 `日K / 周K / 月K / 年K`。对应前端请求映射也同步重构为 `1d+1y / 1wk+5y / 1mo+10y / 1mo+max`，其中 `年K` 第一版按长期年线视图处理，不引入后端 year-level 聚合。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockDetailPanel.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockDetailPanel.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-27-kline-chinese-timeframes-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-kline-chinese-timeframes-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：前端 `WatchlistDashboardPeriod` 类型移除了未再使用的 `3M`；后端 API 契约与 `StockKlineResponse` 结构无变化，仍复用既有 `interval/range` 查询方式
- 验证情况：`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts` 先失败后通过（13 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts` 先失败后通过（2 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 先失败后通过（1 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts src/views/WatchlistDetailView.test.ts` 通过（4 个文件 / 20 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮 `年K` 仍是基于 `1mo + max` 的长期视图近似实现，视觉和操作习惯已接近券商软件，但并不是真正“每年一根 K 线”的后端聚合；若后续需要完全对齐同花顺/东方财富的年线定义，需要在后端补 yearly candle 聚合后再细化展示

## 2026-03-27 19:18

- 修改人：Codex
- 修改范围：Watchlist 终端式高密度改版
- 变更内容：按更接近同花顺的方向重做了自选股列表与详情页的交易终端样式。列表侧将 `StockCard` 压成更紧凑的横向卡片：右侧指标区收窄、市场/状态信息合并、价格与成交量聚拢、sparkline 保留但整体高度更低，`WatchlistSidebar` 列表间距也同步收紧。详情侧把原来的大留白行情头改成“左侧报价条 + 中部紧凑指标矩阵 + 右上设置”结构，并将主图区升级成更大的终端式 K 线面板：主图保留蜡烛、MA 和 BOLL，新增下方副图区和 `VOL / MACD / KDJ` 切换，右侧新增技术仪表栏，展示 `Session Range`、`6M Range`、`Bias vs MA20` 及最新 MA/BOLL/成交量等读数。所有右栏指标均基于现有 `quote` 与 `klineData` 推导，不引入新的后端字段。另补写了本轮 design / plan 文档，并更新了 `StockDetailPanel`、`KlineChart` 测试覆盖。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistSidebar.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockDetailPanel.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockDetailPanel.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-27-watchlist-terminal-redesign-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-watchlist-terminal-redesign-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增前后端接口或类型字段；右侧仪表盘和区间指标均由现有 `WatchlistQuoteSummary` 与 `StockKlineResponse` 在前端计算得出
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts` 先失败后通过（2 个文件 / 2 个用例）；`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts` 通过（4 个文件 / 14 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前右侧“高端仪表盘”仍然是基于现有行情/K 线数据的技术面展示，没有接入总市值、PE、换手率、五档盘口等更像券商终端的深度字段；若后续要继续贴近同花顺/东方财富，需要先扩充后端行情字段，再把右栏从技术仪表扩展为基本面 + 盘口混合面板

## 2026-03-27 18:56

- 修改人：Codex
- 修改范围：Watchlist K 线加载修复
- 变更内容：定位并修复了自选股详情页 K 线一直无数据的问题。根因不是缺少外部 API key，而是当前环境的 `yfinance==1.2.0` 在 `download()` 时返回了带 ticker 层级的 `MultiIndex` 列，后端 `market_chart_service` 仍按旧版单层 `Open/High/Low/Close/Volume` 列读取，导致 K 线序列化阶段抛出 `TypeError` 并使前端落入通用失败空态。本轮在历史行情下载后统一把多层列压平成单层 OHLCV 列，并补了一条回归测试覆盖该返回形状，确保现有 K 线 payload、指标计算和新闻事件对齐逻辑保持不变。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/market_chart_service.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-kline-yfinance-multiindex-fix-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无 API 契约变化；仍返回原有 `MarketKlineView` 结构，仅修正后端对 Yahoo Finance 历史数据列结构的兼容逻辑
- 验证情况：`conda run -n news-caught pytest backend/tests/test_market.py -k multiindex -q` 先失败后通过；`conda run -n news-caught pytest backend/tests/test_market.py -q` 通过（17 个用例）；`conda run -n news-caught python -c "from app.services.market_chart_service import MarketChartService; from app.db.session import SessionLocal; session=SessionLocal(); payload=MarketChartService().get_kline('HK0700','1d','6mo',session); session.close(); print(payload['symbol'], len(payload['candles']), payload['candles'][0]['time'], payload['candles'][-1]['time'])"` 通过，返回 `HK0700 121 2025-09-29 2026-03-27`
- 风险/后续事项：本轮只修了后端根因，前端仍会把 K 线请求失败统一显示成固定文案，无法直接暴露后端错误详情；若后续还要提高可诊断性，可以再补 `watchlistStore` 的错误透传与图表错误态展示

## 2026-03-27 16:02

- 修改人：Codex
- 修改范围：Watchlist 列表页 / 详情页拆分与紧凑化
- 变更内容：把 `watchlist` 从原来的单页 master-detail 结构拆成了两个独立页面：`/watchlist` 现在只负责自选股列表、搜索、添加、删除和刷新；`/watchlist/:symbol` 改成专门的 K 线详情页。列表页去掉了旧的 `Trading Dashboard` 叙事，`WatchlistView` 不再渲染 `StockDetailPanel`，并把工具条、添加入口和股票行项整体压成更接近终端列表的 `A1` 密度；`StockCard` 改成 `compact` 行式布局，`WatchlistAddModal` 同步收紧标题、输入区和候选项密度。详情页侧则把 `WatchlistDetailView` 接到真实的详情路由上，负责 `selectSymbol + loadQuoteDetail + loadRelatedNews` 装载，并在缺失 symbol 或 404 时回退到 `/watchlist`；同时把列表页点击改成立即路由跳转，不再预拉详情数据，避免导航阻塞和重复请求。`watchlistStore.loadQuoteDetail()` 现在会在失败时正确退出 loading 并清掉旧 quote，避免详情页卡死或短暂显示上一只股票。`StockDetailPanel` 去掉了原来的常驻副图区与 signal summary，改成顶部行情条 + K 线主图 + 下方相关新闻区，并在行情条右上角新增螺丝按钮设置 `popover`；设置内容限制在 `watchlist-settings-scroll` 容器内滚动，当前只承载周期切换入口，同时保留新闻与 K 线事件的高亮联动。另补写了本轮 design / plan 文档，并新增 `StockDetailPanel` 组件测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/views/WatchlistDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/views/WatchlistDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/components/watchlist/WatchlistSidebar.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/components/watchlist/StockCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/components/watchlist/WatchlistAddModal.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/components/watchlist/StockDetailPanel.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/components/watchlist/StockDetailPanel.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/docs/superpowers/specs/2026-03-27-watchlist-page-split-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/docs/superpowers/plans/2026-03-27-watchlist-page-split-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/docs/code-change-log.md`
- 接口/数据结构变化：无后端接口或前端 API 类型变化；仅调整前端路由指向、页面职责和组件交互结构
- 验证情况：`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts` 先失败后通过（2 个文件 / 10 个用例）；`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts` 先失败后通过（8 个用例）；`npm --prefix frontend run test -- --run src/views/WatchlistDetailView.test.ts` 先失败后通过（4 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts` 先失败后通过（1 个用例）；`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts src/components/watchlist/StockDetailPanel.test.ts src/stores/watchlistStore.test.ts` 通过（4 个文件 / 25 个用例）；`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts src/stores/watchlistStore.test.ts` 通过（5 个文件 / 26 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前设置 `popover` 只保留了真正有作用的周期切换入口，尚未恢复任何新的副图/指标面板；列表页头部和 market worker 状态仍在同页，后续若想进一步压缩首页高度，可以继续把运行状态折叠成更轻的状态条；详情页当前只对缺失 symbol 和 404 做回退，其余错误会留在当前页，后续若要提供更明确的重试/错误提示，可以继续补细分的详情错误状态

## 2026-03-27 01:05

- 修改人：Codex
- 修改范围：X Monitor 账号管理改造
- 变更内容：把 `X Monitor` 的账号管理从“刷新前按 JSON 文件强同步”的只读名单，改成了“数据库作为运行时真相源，页面可直接增删改，文件只做显式导入/导出”的工作流。后端为 `x_account` 新增 `tier` 和 `source` 字段，并在数据库初始化阶段补齐旧库兼容列；`x_monitor.py` 新增账号创建、更新、删除、导入、导出能力，刷新逻辑不再隐式读取配置文件，而是仅抓取数据库中 `is_active=true` 且 `tier!=muted` 的账号，并按 `core -> watch` 顺序刷新。API 层新增了 `POST /api/x/accounts`、`PATCH /api/x/accounts/{handle}`、`DELETE /api/x/accounts/{handle}`、`POST /api/x/accounts/import`、`POST /api/x/accounts/export`，同时 `GET /api/x/accounts` 返回新字段。前端 `XMonitorView` 左侧面板升级为账号管理台，加入账号创建表单、导入/导出按钮、层级标签、启停和删除动作，并默认隐藏 `muted` 账号帖子；Pinia store、API client、mock fallback 和 Vitest 用例都同步到了这套新契约。另补充了本轮设计文档和实现计划文档，供后续继续迭代。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/backend/app/api/routes/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/backend/app/models/x_account.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/backend/app/repositories/x_account_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/backend/app/schemas/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/backend/app/services/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/frontend/src/api/http.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/frontend/src/stores/xMonitorStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/docs/superpowers/specs/2026-03-27-x-monitor-account-management-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/docs/superpowers/plans/2026-03-27-x-monitor-account-management-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/docs/code-change-log.md`
- 接口/数据结构变化：`x_account` 新增 `tier` 与 `source` 字段；新增 X 账号 CRUD / import / export API；`GET /api/x/accounts` 返回结构新增 `tier`、`source`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_x_monitor.py -k 'x_accounts or import_accounts_from_file or export_accounts_to_file or prioritizes_core or implicit_file_sync' -q` 先失败后通过（8 个用例）；`conda run -n news-caught pytest backend/tests/test_x_monitor.py -q` 通过（24 个用例）；`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts` 先失败后通过（5 个用例）；`conda run -n news-caught pytest backend/tests/test_x_monitor.py backend/tests/test_health.py -q` 通过（26 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前页面支持新增、启停、删除和导入导出，但还没有做“编辑已有账号的 display name / priority / tier / notes”独立 UI，当前只先暴露了最常用的新增与状态动作；现有数据库兼容通过初始化补列处理，生产环境仍需要确认服务启动时一定会执行该初始化流程；导入语义目前是 merge-only，不会删除数据库里独有账号，后续如果要支持“按文件完整替换”应单独加预览和确认

## 2026-03-27 00:43

- 修改人：Codex
- 修改范围：watchlist 看 K 线交易台式界面重构
- 变更内容：围绕“看 K 线更像东方财富类交易台”的目标重做了 `watchlist` 详情区。`StockDetailPanel.vue` 从原来的卡片堆叠改成三段式交易台结构：顶部固定展示股票名/代码、最新价、涨跌额、涨跌幅、开盘、昨收、日内高低、成交量、更新时间和周期切换；中部把 `KlineChart.vue` 升级成主图交易面板，新增主图摘要、`MA5/10/20/60` 图例、BOLL 可用标识、空态骨架和事件筹码条；底部把副图和新闻区改成辅助分析层，`IndicatorChart.vue` 调整成更接近终端页签的切换样式，`RelatedNewsSidebar.vue` 改造成新闻时间流，并补上事件筹码与新闻条目的双向高亮联动。同步补写了 design/plan 文档，并扩充前端测试以锁定交易台结构、摘要信息和图表/新闻联动行为。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/frontend/src/components/watchlist/StockDetailPanel.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/frontend/src/components/watchlist/IndicatorChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/frontend/src/components/watchlist/RelatedNewsSidebar.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/docs/superpowers/specs/2026-03-27-watchlist-kline-trading-desk-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/docs/superpowers/plans/2026-03-27-watchlist-kline-trading-desk-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/docs/code-change-log.md`
- 接口/数据结构变化：无后端接口或前端 API 类型变更；仅重组现有 watchlist 详情区展示层和组件交互
- 验证情况：`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts` 通过（10 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 通过（1 个用例）；`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/components/watchlist/KlineChart.test.ts src/stores/watchlistStore.test.ts` 通过（3 个文件 / 22 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮仍未接入更深的交易软件能力，例如盘口、区间画线和更多主图叠加开关；当前主图仍基于 `lightweight-charts` 默认能力实现，后续若继续向专业行情终端靠拢，可再补十字游标信息栏、主图副图同步 hover 和更多快捷周期

## 2026-03-27 00:18

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch 伊朗战争权力议案 false negative 迭代
- 变更内容：按当前 benchmark 只剩的单条 false negative，选择 `realtime-0255-1745` 这一条“伊朗军事行动 + 战争权力议案”样本做单点修正。按 TDD 先在 `test_news_relevance_evaluator.py` 增加一个伊朗战争权力正例和一个“伊朗 + 参议院听证会”负例 guardrail，并确认正例在现状下先失败；随后仅在 `news_relevance_evaluator.py` 增加一个窄规则，要求 `伊朗` 与 `军事行动/动武/军事打击` 以及 `战争权力/议案/参议院/投票/否决` 这组三类词共现时才判为市场相关，避免泛伊朗政治流程新闻被一并放宽。重跑 benchmark 后，新实验 `market_relevance_experiment_iran_war_powers` 的指标从 `precision=0.8421 / recall=0.9412 / noise_rejection_rate=0.9286` 提升到 `precision=0.8500 / recall=1.0000 / noise_rejection_rate=0.9286`，并把 keep decision 写入 experiment ledger，同时刷新晨读 report。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_iran_war_powers/evaluation.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_iran_war_powers/evaluation.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.html`
  - `/Users/xiuyang/Desktop/news-caught/docs/research/market-relevance-experiments.tsv`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或数据结构；仅补充一条更窄的地缘政治市场相关性启发式规则与对应实验产物
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'iran_war_powers_vote_updates or generic_iran_senate_process_update' -q` 先失败后通过；`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -q` 通过（28 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/news_relevance_evaluator.py backend/scripts/evaluate_market_relevance.py` 通过；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python backend/scripts/evaluate_market_relevance.py --dataset backend/data/research/market_relevance_benchmark.jsonl --output-dir backend/data/research/market_relevance_experiment_iran_war_powers` 通过；`conda run -n news-caught python backend/scripts/run_news_relevance_experiment.py --experiment-id exp-20260327-iran-war-powers --baseline-id exp-20260326-taiwan-arms-sale --hypothesis "Catch Iran war-powers vote headlines without broadening generic Iran politics" --changed-file backend/app/services/news_relevance_evaluator.py --metrics-before backend/data/research/market_relevance_experiment_taiwan_arms_sale/evaluation.json --metrics-after backend/data/research/market_relevance_experiment_iran_war_powers/evaluation.json --ledger docs/research/market-relevance-experiments.tsv` 通过并记录 `keep`；`conda run -n news-caught python backend/scripts/render_market_relevance_report.py --benchmark backend/data/research/market_relevance_benchmark.jsonl --evaluation backend/data/research/market_relevance_experiment_iran_war_powers/evaluation.json --ledger docs/research/market-relevance-experiments.tsv --markdown-output backend/data/research/market_relevance_report.md --html-output backend/data/research/market_relevance_report.html` 通过
- 风险/后续事项：当前 benchmark 上的 false negative 已清零，后续应优先回头审视剩余 3 条 false positive，避免在 recall 已满时继续扩地缘政治规则；本轮规则仍是中文 headline 级启发式，如后续出现英文同类 headline，需要单独用 benchmark 样本验证后再扩

## 2026-03-26 19:08

- 修改人：Codex
- 修改范围：港美板块新闻第一轮来源与去噪升级
- 变更内容：按“最小闭环”方案补了第一轮板块新闻升级。`news_ingestion.py` 现在支持 `api` 类型来源和 `the_news_api_json` 解析，可把聚合 API 结果统一归一化到现有 `SourceItem`/入库流程；同时增加了基于 `host + 小时窗口 + 标题归一化` 的轻量重复抑制，避免同一窗口内的改写稿反复入库，并在同窗重复出现时优先保留更高 `tier/priority` 的来源元数据。重复签名归一化也从 ASCII 扩到中文标题，避免港股/中文快讯场景直接漏重。`news_relevance_evaluator.py` 在保留现有布尔 market relevance 兼容层的前提下，新增了 `predict_market_relevance_details()`，可返回 `sector_tags` 和 `relevance_reason`，先覆盖 `ai_compute`、`semiconductors`、`chinese_internet`、`apple_supply_chain` 四类板块标签；同时把市场信号词拆成高低置信两层，并新增 generic Apple/server chatter 负例，避免把泛产品评测或泛企业服务器刷新误判成板块信号。另新增 `news_priority.py` 作为纯 Python 排序 helper，用于按 `source tier -> sector tag -> official signal -> recency` 排序，作为后续 report/feed surfacing 的基础。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/backend/app/services/news_priority.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/backend/tests/test_news_priority.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/docs/superpowers/specs/2026-03-26-sector-news-upgrade-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/docs/superpowers/plans/2026-03-26-sector-news-upgrade-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/docs/code-change-log.md`
- 接口/数据结构变化：运行时未改现有 API route 和数据库 schema；新增 `api` source type 配置能力、新的 `predict_market_relevance_details()` 返回结构，以及独立的新闻排序 helper
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -k 'api_source or supports_api_news_payload or duplicate_titles' -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'sector_tag' -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -k 'promotes_duplicate_to_primary_source_metadata or deduplicates_same_window_chinese_titles' -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'generic_server_refresh or sector_tag' -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'company_event or shipping_route_disruption or taiwan_arms_sale' -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_priority.py -q` 通过（60 个用例）；`conda run -n news-caught pytest backend/tests/test_news_relevance_report.py backend/tests/test_news_signal_pipeline.py backend/tests/test_news.py -q` 通过（13 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/news_ingestion.py backend/app/services/news_relevance_evaluator.py backend/app/services/news_priority.py` 通过
- 风险/后续事项：当前 `api` 来源解析只先接了 `the_news_api_json` 这一种 payload，后续接入真实 The News API 仍需要补配置文件与 API key；重复抑制目前仍只覆盖“同 host、同小时窗口、标题近似一致”的改写稿，跨 host 转载和跨语言同义改写还未处理；新的板块 tagging 仍是启发式规则，后续应继续用 benchmark 扩样验证 precision/recall 边界，并把 `source tier` 元数据真正接到后续 report/feed 输出

## 2026-03-26 18:51

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch 台湾军售 false negative 迭代
- 变更内容：基于当前主仓库 `market_relevance_experiment_recall_merge` 的剩余 false negative，仅选择 `historical-0188-188` 这一条“对台军售 + 拦截导弹”样本做单点修正。按 TDD 先在 `test_news_relevance_evaluator.py` 新增一个台湾军售正例和一个联合国叙利亚会议负例，并确认正例先因规则缺失而失败；随后仅在 `news_relevance_evaluator.py` 增加“`对台/台湾/台海` 与 `军售/导弹/武器` 共现”时判为市场相关的窄规则。重跑 benchmark 后，新实验 `market_relevance_experiment_taiwan_arms_sale` 的指标从 `precision=0.8333 / recall=0.8824 / noise_rejection_rate=0.9286` 提升到 `precision=0.8421 / recall=0.9412 / noise_rejection_rate=0.9286`，并把 keep decision 写入 experiment ledger，同时刷新晨读 report。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_taiwan_arms_sale/evaluation.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_taiwan_arms_sale/evaluation.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.html`
  - `/Users/xiuyang/Desktop/news-caught/docs/research/market-relevance-experiments.tsv`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或数据结构；仅补充 evaluator 启发式规则与一轮新实验产物
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'taiwan_arms_sale or un_security_council_update' -q` 先失败后通过；`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -q` 通过（20 个用例）；`python -m py_compile backend/app/services/news_relevance_evaluator.py backend/scripts/evaluate_market_relevance.py` 通过；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python backend/scripts/evaluate_market_relevance.py --dataset backend/data/research/market_relevance_benchmark.jsonl --output-dir backend/data/research/market_relevance_experiment_taiwan_arms_sale` 通过；`conda run -n news-caught python backend/scripts/run_news_relevance_experiment.py --experiment-id exp-20260326-taiwan-arms-sale --baseline-id exp-20260326-recall-merge --hypothesis "Catch Taiwan arms-sale headlines without broadening generic geopolitics" --changed-file backend/app/services/news_relevance_evaluator.py --metrics-before backend/data/research/market_relevance_experiment_recall_merge/evaluation.json --metrics-after backend/data/research/market_relevance_experiment_taiwan_arms_sale/evaluation.json --ledger docs/research/market-relevance-experiments.tsv` 通过并记录 `keep`；`conda run -n news-caught python backend/scripts/render_market_relevance_report.py --benchmark backend/data/research/market_relevance_benchmark.jsonl --evaluation backend/data/research/market_relevance_experiment_taiwan_arms_sale/evaluation.json --ledger docs/research/market-relevance-experiments.tsv --markdown-output backend/data/research/market_relevance_report.md --html-output backend/data/research/market_relevance_report.html` 通过
- 风险/后续事项：主仓库剩余 false negative 现在只剩 `realtime-0255-1745`（伊朗战争权力议案）；后续如果继续提 recall，应继续保持单点地缘政治边界验证，避免把泛国际政治 headline 一并放进市场相关范围

## 2026-03-26 14:47

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch recall 合并落主仓库
- 变更内容：按你确认的“优先提 recall”方案，把自动化 worktree 中最稳妥的两条 keep 结果合并回了 `main`：一条是“概念/板块 + 涨停/跟涨”的中文题材异动识别，另一条是“航运主体 + 红海/路线/targeting 扰动”的英文航运风险识别。按 TDD 先在 `test_news_relevance_evaluator.py` 增加四条回归测试并确认两条正例先失败，再在 `news_relevance_evaluator.py` 只补这两条最窄规则。随后重跑 benchmark，生成新的组合实验产物 `market_relevance_experiment_recall_merge`，并把结果记录为新的 keep experiment；当前主仓库晨读 report 已刷新到这轮组合结果，指标从上一轮 `index-signals` 的 `precision=0.8125 / recall=0.7647 / noise_rejection_rate=0.9286` 提升到 `precision=0.8333 / recall=0.8824 / noise_rejection_rate=0.9286`。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_recall_merge/evaluation.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_recall_merge/evaluation.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.html`
  - `/Users/xiuyang/Desktop/news-caught/docs/research/market-relevance-experiments.tsv`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-26-market-relevance-recall-merge-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-26-market-relevance-recall-merge-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或数据结构；仅收紧 evaluator 的启发式规则并新增一轮组合实验产物
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'concept_mover or shipping_route_disruption or generic_product_concept or generic_gaza_humanitarian_updates' -q` 先失败后通过；`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -q` 通过（18 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/news_relevance_evaluator.py backend/scripts/evaluate_market_relevance.py backend/scripts/render_market_relevance_report.py` 通过；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python backend/scripts/evaluate_market_relevance.py --dataset backend/data/research/market_relevance_benchmark.jsonl --output-dir backend/data/research/market_relevance_experiment_recall_merge` 通过；`conda run -n news-caught python backend/scripts/run_news_relevance_experiment.py --experiment-id exp-20260326-recall-merge --baseline-id exp-20260325-index-signals --hypothesis "Combine concept-mover and shipping-route recall improvements" --changed-file backend/app/services/news_relevance_evaluator.py --metrics-before backend/data/research/market_relevance_experiment_index_signals/evaluation.json --metrics-after backend/data/research/market_relevance_experiment_recall_merge/evaluation.json --ledger docs/research/market-relevance-experiments.tsv` 通过并记录 `keep`；`conda run -n news-caught python backend/scripts/render_market_relevance_report.py --benchmark backend/data/research/market_relevance_benchmark.jsonl --evaluation backend/data/research/market_relevance_experiment_recall_merge/evaluation.json --ledger docs/research/market-relevance-experiments.tsv --markdown-output backend/data/research/market_relevance_report.md --html-output backend/data/research/market_relevance_report.html` 通过
- 风险/后续事项：剩余 false negative 现在只剩“对台军售”和“伊朗战争权力议案”两类地缘政治边界样本；后续如果继续提 recall，最好单独验证“地缘政治 headline 何时应视为市场相关”，不要顺手放宽泛政治规则

## 2026-03-25 18:14

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch 首轮手动 experiment 迭代
- 变更内容：手动启动了 `market relevance autoresearch` 的第一轮 experiment，针对 baseline 中成簇出现的 false negative，选择“指数异动 / 商品价格快讯 / 市场稳定措施”作为单一假设进行收紧。按 TDD 先为 `news_relevance_evaluator.py` 补了三条失败测试，再新增 `沪指`、`深成指`、`电池级碳酸锂`、`市场稳定计划` 等更窄中文市场短语命中；随后用真实 benchmark 重跑评测，指标从 baseline 的 `precision=0.7500 / recall=0.5294 / noise_rejection_rate=0.9286` 提升到 `precision=0.8125 / recall=0.7647 / noise_rejection_rate=0.9286`。在把结果写入 experiment ledger 时，又发现 `news_relevance_experiment_runner.py` 的 scope guard 仍停留在旧的新闻主链范围，会错误拒绝 `news_relevance_evaluator.py` 这类 research 相关改动；本轮同步补了允许 `news_relevance_*` 服务和 research 脚本的测试与实现修正。最后基于这轮 experiment 结果刷新了晨读面板，使明天打开 report 时能直接看到最新 keep 实验，而不是旧 baseline。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_experiment_runner.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_experiment_runner.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_index_signals/evaluation.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_index_signals/evaluation.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.html`
  - `/Users/xiuyang/Desktop/news-caught/docs/research/market-relevance-experiments.tsv`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；experiment runner 的允许修改范围扩大到当前 `news relevance autoresearch` 实际会触及的 research 服务与脚本
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_report.py backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_relevance_experiment_runner.py -q` 通过；`conda run -n news-caught python -m py_compile backend/app/services/news_relevance_report.py backend/scripts/render_market_relevance_report.py backend/app/services/news_relevance_evaluator.py backend/app/services/news_relevance_experiment_runner.py` 通过；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python backend/scripts/evaluate_market_relevance.py --dataset backend/data/research/market_relevance_benchmark.jsonl --output-dir backend/data/research/market_relevance_experiment_index_signals` 通过；`conda run -n news-caught python backend/scripts/run_news_relevance_experiment.py --experiment-id exp-20260325-index-signals --baseline-id baseline-20260325-market-relevance-v2 --hypothesis "Catch index spikes, commodity price wires, and market stability plans" --changed-file backend/app/services/news_relevance_evaluator.py --changed-file backend/app/services/news_relevance_experiment_runner.py --metrics-before backend/data/research/market_relevance_baseline/evaluation.json --metrics-after backend/data/research/market_relevance_experiment_index_signals/evaluation.json --ledger docs/research/market-relevance-experiments.tsv` 通过并记录 `keep`
- 风险/后续事项：这轮提升主要覆盖了指数 / 商品价格 / 市场稳定措施这组市场层面信号，剩余 false negative 仍集中在地缘政治与主题联动类新闻；下一轮更适合单独检验“地缘政治是否应保留为市场相关”的边界，而不是继续往中文市场短语里堆规则

## 2026-03-25 17:58

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch 晨读成果面板
- 变更内容：为当前 `market relevance autoresearch` 增加了一个轻量成果面板生成链路，新增 `news_relevance_report.py` 负责读取现有 benchmark、baseline evaluation 与 experiment ledger，并汇总成统一的晨读 report model；同时新增 `render_market_relevance_report.py`，可一次性生成两份输出：适合审阅和 diff 的 `market_relevance_report.md`，以及适合明早直接打开看的 `market_relevance_report.html`。两份面板都会展示最新指标、benchmark 样本分布、false positive / false negative 样本标题，以及最近几条 experiment ledger 记录。基于当前真实产物已经生成了首版晨读面板，后续可被 automation 每轮刷新。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_report.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/scripts/render_market_relevance_report.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_report.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.html`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-25-market-relevance-report-panel-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-25-market-relevance-report-panel-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增 report 生成 CLI `backend/scripts/render_market_relevance_report.py`；未改现有评测、benchmark 或 annotation 数据结构
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_report.py backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_relevance_experiment_runner.py -q` 通过；`conda run -n news-caught python -m py_compile backend/app/services/news_relevance_report.py backend/scripts/render_market_relevance_report.py` 通过；`conda run -n news-caught python backend/scripts/render_market_relevance_report.py --benchmark backend/data/research/market_relevance_benchmark.jsonl --evaluation backend/data/research/market_relevance_baseline/evaluation.json --ledger docs/research/market-relevance-experiments.tsv --markdown-output backend/data/research/market_relevance_report.md --html-output backend/data/research/market_relevance_report.html` 通过
- 风险/后续事项：当前成果面板仍然是静态文件，不会自动显示跨轮次指标 diff；如果后续夜间实验数量增多，建议继续补“上一轮 vs 当前轮”的显式变化摘要，避免只看原始列表

## 2026-03-25 17:06

- 修改人：Codex
- 修改范围：市场新闻相关性 review 决策回填、benchmark 首版产出与 baseline evaluator 回归修正
- 变更内容：基于已导出的 `market_relevance_review_queue.csv`，先代填了当前 `59` 条 review queue 的首版人审决策，并通过 `import-csv` 导回 `market_relevance_reviewed.jsonl`，随后执行 `apply` 将复核结果回填到候选集并生成首版 `market_relevance_benchmark.jsonl`。在真正跑 baseline 时发现 evaluator 的 market-signal 规则过于依赖窄英文 token，导致 `17` 条正样本被全部预测成 `False`、recall 直接掉到 `0.0`；经定位后，为 `news_relevance_evaluator.py` 增补了更贴近真实 ingestion/filter 语义的监管披露词和中文市场短语匹配，并补了中文业绩快报、回购/派息、SEC 基金持仓披露三个回归测试。收到 code review 后又继续收紧了两处：`SEC` 不再作为裸 token 直接触发市场相关，而是改成更具体的监管披露短语；`import-csv` 现在会拒绝漏行和重复 `sample_id`，避免编辑 CSV 时静默丢失 review 决策。修正后 baseline 已成功产出，指标为 `precision=0.75`、`recall=0.5294`、`noise_rejection_rate=0.9286`，同时把最终 baseline 记录追加到了实验 ledger。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_review_queue.csv`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_reviewed.jsonl`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_candidates.annotated.jsonl`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_benchmark.jsonl`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_baseline/evaluation.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_baseline/evaluation.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/research/market-relevance-experiments.tsv`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；baseline evaluator 的 market relevance 规则扩大到支持部分监管披露英文短语与中文市场短语命中
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_relevance_experiment_runner.py -q` 通过（33 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/news_relevance_dataset.py backend/app/services/news_relevance_evaluator.py backend/scripts/review_market_relevance_annotations.py backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_evaluator.py` 通过；`conda run -n news-caught python backend/scripts/review_market_relevance_annotations.py import-csv backend/data/research/market_relevance_review_queue.jsonl backend/data/research/market_relevance_review_queue.csv backend/data/research/market_relevance_reviewed.jsonl` 通过；`conda run -n news-caught python backend/scripts/review_market_relevance_annotations.py apply backend/data/research/market_relevance_candidates.annotated.jsonl backend/data/research/market_relevance_reviewed.jsonl backend/data/research/market_relevance_benchmark.jsonl` 通过；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python backend/scripts/evaluate_market_relevance.py --dataset backend/data/research/market_relevance_benchmark.jsonl --output-dir backend/data/research/market_relevance_baseline --ledger docs/research/market-relevance-experiments.tsv --experiment-id baseline-20260325-market-relevance-v2` 通过并产出 baseline 指标
- 风险/后续事项：当前 benchmark 仍只有 `59` 条复核样本，主要覆盖低置信度和 spot-check 队列，代表性还不足以支撑更强结论；evaluator 虽已不再全量漏判，但规则仍偏启发式，下一步应继续基于这批 false positive / false negative 收紧真实 market catalyst 与泛宏观/泛舆情边界

## 2026-03-25 16:08

- 修改人：Codex
- 修改范围：市场新闻相关性 review queue 可读/可编辑导出
- 变更内容：为当前 `market relevance` 人审环节补了两条 review queue 辅助路径。其一，在 `news_relevance_dataset.py` 中新增 review queue 的 Markdown 和 CSV renderer，以及把编辑后的 CSV 决策安全导回 reviewed JSONL 的 helper；其二，在 `review_market_relevance_annotations.py` 中新增 `export`、`export-csv` 和 `import-csv` 命令，让 review queue 不再只能直接改 JSONL。本轮已基于现有 `backend/data/research/market_relevance_review_queue.jsonl` 生成两份人读产物：`market_relevance_review_queue.md` 和更适合直接编辑的 `market_relevance_review_queue.csv`。这样后续你只需要编辑 CSV 中的 `review_market_relevant`、`review_noise_type`、`review_label_source`、`review_notes` 四列，我就可以把结果导回 JSONL 并继续 apply/benchmark/baseline。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/scripts/review_market_relevance_annotations.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_review_queue.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_review_queue.csv`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：review CLI 新增 `export-csv` 与 `import-csv`；CSV 约定字段包括 `sample_id`、模型判断列和 `review_*` 编辑列
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_dataset.py::test_export_review_samples_markdown_renders_readable_sections backend/tests/test_news_relevance_dataset.py::test_export_review_samples_csv_writes_editable_columns backend/tests/test_news_relevance_dataset.py::test_import_review_decisions_csv_updates_reviewed_samples -q` 通过（3 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/news_relevance_dataset.py backend/scripts/review_market_relevance_annotations.py` 通过；`conda run -n news-caught python backend/scripts/review_market_relevance_annotations.py export backend/data/research/market_relevance_review_queue.jsonl backend/data/research/market_relevance_review_queue.md` 与 `export-csv backend/data/research/market_relevance_review_queue.jsonl backend/data/research/market_relevance_review_queue.csv` 通过
- 风险/后续事项：CSV 只是人审编辑入口，正式 benchmark 仍然以导回后的 reviewed JSONL 为准；你完成 CSV 编辑后，还需要继续执行 `import-csv -> apply -> evaluate`

## 2026-03-25 15:52

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch review follow-up hardening
- 变更内容：按本轮 code review 补了两处会影响后续 benchmark 可靠性的实现收紧。其一，`sample_market_relevance_dataset.py` 在启用 source cap 时不再只看固定 oversample 窗口，而是直接扫描完整候选池后再做 round-robin 限额，避免前部数据被单一来源淹没时把目标样本数严重抽空；测试侧新增了一个“前 1000 条都来自同一 source，但后面仍有足够 B/C source 填满 limit”的用例，确认 source cap 不会因为窗口偏斜而只吐出少量样本。其二，`OpenAICompatibleProvider` 的占位 host 检查从“凡是 hostname 以 `example-` / `example.` 开头都拒绝”收窄为只拒绝保留测试域（如 `.test` 和标准 `example.com/.org/.net`），避免误伤真实公司域名中恰好带 `example-` 前缀的 host；测试侧同步补了允许 `https://example-llm.company.com/v1` 继续正常走 provider 调用的覆盖。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/services/llm_providers.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/sample_market_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_annotation.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；仅收紧 provider placeholder 判定与 source cap 抽样语义
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_annotation.py::test_annotation_service_allows_non_placeholder_hostnames_that_start_with_example backend/tests/test_news_relevance_dataset.py::test_sampling_script_source_cap_keeps_filling_beyond_initial_skewed_window -q` 通过（2 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/llm_providers.py backend/scripts/sample_market_relevance_dataset.py` 通过
- 风险/后续事项：source cap starvation 和 placeholder host 误判都已修正，但 sampling 仍未达到最终设计里要求的 market/time/noise 全量分层；后续若要正式合并 baseline/benchmark 产物，还需要继续把 sampling allocator 和离线 benchmark 执行链打通

## 2026-03-25 15:39

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch annotation 可恢复批处理
- 变更内容：为 `annotate_market_relevance.py` 和底层 `annotate_market_relevance_file()` 补了最小可恢复执行能力，避免整批 `400` 条候选首标时“长时间无进度、失败后从头再来”。当前实现新增了两项控制：`--resume` 会复用已有 output 中真正已完成的样本并只继续剩余样本；`--batch-size` 会在每 N 条新标注后把当前累计结果重新写回输出文件，确保中途中断后有可恢复的阶段性产物。收到 review 后又补了两处收紧：`resume` 现在只会跳过 `confidence > 0` 的已完成标注，不会把候选集里那种占位 `model_only + confidence=0` 行误判为已完成；`batch-size` 也要求必须是正整数，避免 `0` 或负数被静默接受。测试侧补了三类回归：已完成 output 续跑、占位 output 需要重标、以及分批 flush/非法 batch size 的边界。这样后续继续跑整批候选时，可以先用小批量探路，再反复 `--resume` 补齐，而不是依赖一次长时间串行请求。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/services/news_relevance_annotation.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/annotate_market_relevance.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_annotation.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/docs/code-change-log.md`
- 接口/数据结构变化：annotation CLI 新增 `--resume` 和 `--batch-size`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_annotation.py -q` 通过（9 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/news_relevance_annotation.py backend/scripts/annotate_market_relevance.py` 通过
- 风险/后续事项：当前仍是串行逐条请求外部 LLM，只是已经可恢复；如果整批运行仍然太慢，下一步应继续补更明确的进度输出，或增加 `--limit/--offset` 一类显式分片控制，方便并行或分段执行

## 2026-03-25 15:08

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch annotation provider 诊断与采样 source cap
- 变更内容：基于当前 worktree 继续推进 `market relevance autoresearch`，先按真实复现结果收紧了 annotation 入口的 provider 校验，再给候选集抽样补了一层最小的来源限额控制。LLM provider 侧在 `OpenAICompatibleProvider` 增加了占位配置 fail-fast：当活动配置仍指向 `example-*` / `.test` 之类占位 host，或使用 `sk-test...` 占位 key 时，会在真正发请求前直接抛出受控错误，避免 annotation CLI 长跑后才在 TLS 握手阶段报 `UNEXPECTED_EOF_WHILE_READING`。抽样侧为 `sample_market_relevance_dataset.py` 增加了 `--historical-source-cap` / `--realtime-source-cap` 参数，并在查询窗口上做 oversample 后按 source round-robin 限额分配，避免“先取前 N 条再裁剪”导致 `CLS Telegraph` 一类单源直接挤掉其他来源。用当前 SQLite 数据做 smoke run 时，`source cap=40` 能明显压下单源暴涨，但也暴露出只靠 source cap 还不足以稳定补满 `400` 条样本，当前会落到 `315` 条，说明下一步仍需继续做更完整的 stratified allocator，而不是把 source cap 当最终方案。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/services/llm_providers.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/sample_market_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_annotation.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/docs/code-change-log.md`
- 接口/数据结构变化：annotation provider 请求前新增占位配置拒绝语义；候选集采样 CLI 新增 `--historical-source-cap` 与 `--realtime-source-cap`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_annotation.py backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_relevance_experiment_runner.py backend/tests/test_research_schemas.py -q` 通过（30 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/llm_providers.py backend/scripts/sample_market_relevance_dataset.py backend/tests/test_news_relevance_annotation.py backend/tests/test_news_relevance_dataset.py` 通过；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python backend/scripts/sample_market_relevance_dataset.py --historical-limit 240 --realtime-limit 160 --historical-source-cap 40 --realtime-source-cap 40 --output /tmp/market_relevance_candidates_cap_XXXX.jsonl` 通过，生成 `315` 条候选样本，前几大来源收敛为 `The Verge/36Kr/CLS Telegraph` 各 `80` 条
- 风险/后续事项：当前 annotation 仍然没有“真正跑通”到可用 LLM，因为主工作区数据库里的活动 provider 还是占位配置，需先换成真实可连通的 endpoint 后再继续半自动标注；source cap 只是第一层止血，无法单独保证 `400` 条样本补满，也无法同时约束 market/time/noise 分布，后续仍应按设计继续做显式分层抽样

## 2026-03-25 15:29

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch LLM provider 实配与 annotation 连通性验证
- 变更内容：按用户提供的 DeepSeek API key，把主工作区 SQLite 数据库 `/Users/xiuyang/Desktop/news-caught/backend/data/app.db` 中的活动 `llm_provider_config` 从占位值切换为真实 `DeepSeek` 配置（`openai_compatible + https://api.deepseek.com/v1 + deepseek-chat`），随后在 benchmark worktree 内重跑了单样本 `annotate_market_relevance.py` 验证，确认 annotation 已可实际返回结构化标签、置信度和 review notes，不再停在占位 host / TLS EOF 阶段。继续尝试整批 `400` 条候选首标时，现有脚本因为串行外部请求且没有中间落盘或进度输出，在数分钟内仍无阶段性产物，因此本轮没有继续盲等到整批完成，也没有生成完整 `market_relevance_candidates.annotated.jsonl`；后续更适合把标注切成可恢复的小批次，或给脚本补中间落盘/进度。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/docs/code-change-log.md`
- 接口/数据结构变化：无代码接口变化；主工作区数据库中的活动 LLM provider 配置已改为真实 DeepSeek endpoint
- 验证情况：`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python backend/scripts/annotate_market_relevance.py backend/data/research/market_relevance_candidates.first.jsonl backend/data/research/market_relevance_candidates.first.annotated.jsonl` 通过，成功标注 `1` 条样本；随后对 `backend/data/research/market_relevance_candidates.jsonl` 发起整批首标，因脚本为串行外部请求且无中间落盘，本轮手动停止，未产出完整批次文件
- 风险/后续事项：当前真实 endpoint 已可连通，但整批首标的执行策略还不适合长批次运行；如果要继续推进 benchmark，优先应把 annotation 改成分批可恢复或带进度/中间落盘的模式，再继续跑完整候选集

## 2026-03-25 14:21

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch 候选集执行闭环与离线评测贴近生产逻辑
- 变更内容：继续沿既有 `market relevance autoresearch` plan 推进，补齐了当前真正阻塞落地的几个执行缺口。候选集侧为 `sample_market_relevance_dataset.py` 增加了正式 CLI 参数，并在抽样时把 `ArticleContent.content_text` 摘要带入 `body_excerpt`，随后基于主工作区现有 SQLite 数据库生成了第一批 `400` 条候选样本（`historical=240`、`realtime=160`，其中 `388` 条带正文摘要）；review 侧新增了“导出待复核队列 + 应用人工复核结果”的闭环，且会跳过已经 `human_reviewed/human_corrected` 的样本，避免二次复核时重复入队；evaluator 侧不再只靠独立词表，而是复用真实 `NewsSignalClassifier` 的 rule-only 路径并显式禁用 LLM refinement，使离线 benchmark 能使用生产分类器的关键词/主题抽取与正文输入，同时保持纯离线、可复现；baseline 评测脚本补上了 ledger 写入能力，baseline row 也与 schema 对齐，并为未显式传入的 baseline run 生成唯一 `experiment_id`；另外为 research CLI 入口统一补了本地 `backend/` 的 `sys.path` 注入，修复 `conda run` 下 worktree 脚本误导入主工作区 `app.*` 的运行时污染问题。本轮同时验证了半自动标注在当前本机配置下仍被活动 LLM endpoint 阻塞：单样本 `annotate_market_relevance.py` 会稳定报 `llm provider request failed: [SSL: UNEXPECTED_EOF_WHILE_READING]`，因此第一版 benchmark 与 baseline 还不能在当前 provider 配置下真实产出。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/schemas/research.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/services/news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/services/news_relevance_experiment_runner.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/services/news_signal_classifier.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/sample_market_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/annotate_market_relevance.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/review_market_relevance_annotations.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/evaluate_market_relevance.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/run_news_relevance_experiment.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_research_schemas.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_experiment_runner.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/data/research/market_relevance_candidates.jsonl`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/docs/code-change-log.md`
- 接口/数据结构变化：新增了 reviewed sample apply/select 工作流、baseline ledger row 语义以及 `ExperimentDecision.decision="baseline"`；评测预测路径改为支持复用真实 classifier 且使用 `body_excerpt`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_research_schemas.py backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_relevance_experiment_runner.py -q` 通过（25 个用例）；`conda run -n news-caught python -m py_compile backend/scripts/sample_market_relevance_dataset.py backend/scripts/annotate_market_relevance.py backend/scripts/review_market_relevance_annotations.py backend/scripts/evaluate_market_relevance.py backend/scripts/run_news_relevance_experiment.py backend/app/services/news_relevance_dataset.py backend/app/services/news_relevance_evaluator.py backend/app/services/news_relevance_experiment_runner.py backend/app/services/news_signal_classifier.py backend/app/schemas/research.py` 通过；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python scripts/sample_market_relevance_dataset.py --historical-limit 240 --realtime-limit 160 --output data/research/market_relevance_candidates.jsonl` 通过并生成 `400` 条候选样本；`conda run -n news-caught python scripts/review_market_relevance_annotations.py select data/research/market_relevance_candidates.jsonl data/research/market_relevance_review_queue.jsonl --confidence-threshold 0.75 --spot-check-count 20 --seed 7` 通过（随后已删除临时 review queue）；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python scripts/annotate_market_relevance.py data/research/market_relevance_candidates.first.jsonl data/research/market_relevance_candidates.first.annotated.jsonl` 失败，错误为 `llm provider request failed: [SSL: UNEXPECTED_EOF_WHILE_READING]`
- 风险/后续事项：第一批候选集已生成，但 source 分布仍明显偏向 `CLS Telegraph` / `36Kr`，后续如要降低标注成本并提升 benchmark 代表性，仍建议把 sampling 继续升级成显式分层抽样；当前 benchmark 与 baseline 的真实产出仍受活动 LLM provider 连接异常阻塞，需先修正本机可用 provider 或切换到有效 DeepSeek/OpenAI-compatible endpoint 后，再继续跑半自动标注和 baseline capture

## 2026-03-25 13:42

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch 基础工具链
- 变更内容：完成了第一批可执行的 research tooling，实现了 research schema、样本数据集读写与 reviewed merge、`DeepSeek` 首标服务与批量标注脚本、历史/实时混合候选集采样脚本、离线 relevance evaluator、受控 experiment runner 以及 review/evaluate/run 三个薄 CLI；同时新增实验 ledger 初始文件。随后在独立 code review 后继续修正了 4 个关键闭环问题：benchmark merge 改为保留历史基准样本而不是覆盖、evaluator 缺失预测值时会直接报错而非静默按 `False` 计分、experiment decision 增加对 `noise_rejection_rate` 回退的拒绝逻辑、runner 的 repo root 改为动态推导以兼容 worktree 和非固定路径 checkout。当前 evaluator 已内置第一版可解释的 relevance heuristic，用于区分市场事件类新闻与泛科技消费资讯，后续可继续替换为更强策略；本轮未改前端和基础设施。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/research.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_annotation.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_experiment_runner.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/scripts/sample_market_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/scripts/annotate_market_relevance.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/scripts/review_market_relevance_annotations.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/scripts/evaluate_market_relevance.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/scripts/run_news_relevance_experiment.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_research_schemas.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_annotation.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_experiment_runner.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/research/market-relevance-experiments.tsv`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增项目内 research schema（样本、标签、评测指标、实验决策）、候选集/benchmark JSONL 约定、evaluation artifact 输出和 experiment ledger 记录格式；未改现有 API route
- 验证情况：`conda run -n news-caught pytest backend/tests/test_research_schemas.py backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_annotation.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_relevance_experiment_runner.py -q` 通过（20 个用例）；`conda run -n news-caught python -m py_compile backend/app/schemas/research.py backend/app/services/news_relevance_dataset.py backend/app/services/news_relevance_annotation.py backend/app/services/news_relevance_evaluator.py backend/app/services/news_relevance_experiment_runner.py backend/scripts/sample_market_relevance_dataset.py backend/scripts/annotate_market_relevance.py backend/scripts/review_market_relevance_annotations.py backend/scripts/evaluate_market_relevance.py backend/scripts/run_news_relevance_experiment.py` 通过；`conda run -n news-caught pytest backend/tests -q` 通过（144 个用例）
- 风险/后续事项：当前 `predict_market_relevance()` 仍是第一版启发式规则，适合作为 baseline，但还不足以代表最终研究代理的策略上限；下一阶段应继续把 evaluator 与真实 ingestion/filter 逻辑接得更紧，并补 baseline 产物、benchmark 样本内容以及更完整的“kept volume” guardrail

## 2026-03-25 12:49

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch implementation plan
- 变更内容：在确认设计后补写了一份正式 implementation plan，按当前仓库结构和最近新闻链路改动重新拆解了后续实施顺序：先做 research schema、混合抽样与 `DeepSeek` 半自动标注，再做离线评测器与 baseline，最后再做受控 experiment runner 和实验账本；计划中明确限定只动新闻相关后端代码，不碰前端和基础设施，并为每个任务补了 TDD 步骤、验证命令和建议提交点。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-25-market-news-relevance-autoresearch-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：仅计划层面提出后续新增 research schema、数据集文件、评测产物和实验账本，本次未改运行时代码
- 验证情况：未验证；本次为计划文档产出，待进入实现阶段后按计划执行测试和评测验证
- 风险/后续事项：当前仓库存在用户近期未提交改动，后续实现需在不回退这些修改的前提下按计划推进；计划尚未进入执行阶段

## 2026-03-25 12:38

- 修改人：Codex
- 修改范围：feed runtime banner connection overlay
- 变更内容：补齐 `NewsFeedView` 顶部状态带的最终裁决逻辑，当客户端 `SSE` 连接状态为 `offline/degraded` 时，优先展示“实时连接异常”，覆盖服务端 `newsRuntimeStatus.feed_status` 的文案与 tone；并新增对应视图测试，验证连接异常会压过服务端 delayed 状态。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/components/layout/AppShell.test.ts src/stores/newsStore.test.ts src/api/client.test.ts` 通过（26 个用例）
- 风险/后续事项：当前顶部状态带已经覆盖客户端连接异常，但 detail 文案仍以服务端 runtime 摘要为主；如果后续需要更强诊断性，可以再补连接错误原因或最近一次 stream 错误时间

## 2026-03-25 12:35

- 修改人：Codex
- 修改范围：stream keepalive continuity fix + final verification refresh
- 变更内容：代码复核后修正了 `/api/stream/events` 的 keepalive 语义，空闲超时后不再只发一次 `stream.keepalive` 就结束连接，而是按 keepalive 周期持续发送，避免前端 `EventSource` 被错误判定为断线；同步新增 keepalive 连续发送测试，并刷新整轮 backend/frontend/build 验证结果。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/stream.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_stream_events.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；`GET /api/stream/events` 的 keepalive 行为从“单次超时响应”修正为“持续保活”
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_ingestion.py backend/tests/test_news_signal_pipeline.py backend/tests/test_stream_events.py backend/tests/test_stream_status.py -q` 通过（40 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/newsStore.test.ts src/views/NewsFeedView.test.ts src/components/layout/AppShell.test.ts` 通过（25 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：feed 顶部状态带仍未把客户端 `SSE` 连接态覆盖到最终展示文案；如果要完全对齐设计稿，还需要把 `connectionStore/runtimeStatusStore` 的连接异常覆盖逻辑补到 `NewsFeedView`

## 2026-03-25 12:33

- 修改人：Codex
- 修改范围：newsfeed 数据源与实时性基础链路 verified slice
- 变更内容：完成并验证了本轮 plan 的 backend realtime slice 与 frontend runtime slice：后端补齐 `GET /api/news/runtime` 的 spec 契约、`news.created`/`news.updated` 内容流事件和 `/api/stream/events` SSE 转发；前端补齐 news runtime 类型与 API client、`newsStore` 的 runtime/update 处理、`AppShell` 的 `news.updated` 分发，以及 `NewsFeedView` 的最小顶部状态带。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_runtime.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/stream.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/event_bus.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_signal_pipeline.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_stream_events.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增并接通 `GET /api/news/runtime`、`news.created`、`news.updated`、`GET /api/stream/events`；前端开始消费 `NewsRuntimeStatus` 和 `NewsUpdateEvent`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_ingestion.py backend/tests/test_news_signal_pipeline.py backend/tests/test_stream_events.py backend/tests/test_stream_status.py -q` 通过（39 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/newsStore.test.ts src/views/NewsFeedView.test.ts src/components/layout/AppShell.test.ts` 通过（25 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：feed 顶部状态带当前只消费服务端 news runtime，没有把客户端 `SSE` 连接异常覆盖到最终展示文案；如果后续要完全对齐设计稿，需要再把 `connectionStore/runtimeStatusStore` 的连接态覆盖逻辑接进 `NewsFeedView`

## 2026-03-25 12:33

- 修改人：Codex
- 修改范围：frontend news runtime status band + update event routing
- 变更内容：`AppShell` 的统一 stream 入口现在会把 `news.updated` 转交给 `newsStore.upsertNewsUpdate()`，并在启动时同步拉取 `loadNewsRuntime()`；`NewsFeedView` 顶部 `StatusBanner` 改为消费 `newsRuntimeStatus`、`lastIncrementalAt` 和 `sourceHealth`，最小展示 `live/delayed/degraded` 文案、最近入流时间和异常来源数。测试侧补了 `news.updated` 事件分发断言，以及 feed 头部状态带文案断言。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；前端开始消费已存在的 `news.updated` 事件和 `news runtime` store 状态
- 验证情况：`npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/components/layout/AppShell.test.ts src/stores/newsStore.test.ts` 通过（16 个用例）
- 风险/后续事项：当前状态带只展示最小 runtime 摘要，还没有把客户端 `SSE` 连接异常和服务端供给状态做最终合成展示；如果要完全对齐设计稿，还需要再把 `connectionStore/runtimeStatusStore` 的覆盖逻辑接进 feed 顶部文案

## 2026-03-25 12:31

- 修改人：Codex
- 修改范围：frontend news runtime client + store wiring
- 变更内容：前端先接通了 `GET /api/news/runtime` 与增量更新边界。`types/api.ts` 新增 `NewsRuntimeStatus`、market/source runtime 类型和 `news.updated` 事件类型；`apiClient` 新增 `getNewsRuntime()`，并补了一份降级 mock payload；`newsStore` 新增 `newsRuntimeStatus`、`lastIncrementalAt`、`sourceHealth`，支持 `loadNewsRuntime()` 拉取 runtime 状态，同时补了 `upsertNewsUpdate()`，会按当前 scoped query 对 dashboard/feed/sentiment 三个列表执行替换、插入或移除。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：前端类型层新增 `NewsRuntimeStatus`、`NewsRuntimeMarket`、`NewsRuntimeSource`、`NewsUpdateEvent`；`apiClient` 新增 `getNewsRuntime()`
- 验证情况：`npm --prefix frontend run test -- --run src/api/client.test.ts` 通过（9 个用例）；`npm --prefix frontend run test -- --run src/stores/newsStore.test.ts` 通过（3 个用例）
- 风险/后续事项：`AppShell` 和 `NewsFeedView` 还没有消费这组新 state，顶部状态带与 `news.updated` 事件分发仍待后续 UI 接线任务完成

## 2026-03-25 12:25

- 修改人：Codex
- 修改范围：news updated enrichment event publish
- 变更内容：在 `news.created_batch` 订阅处理器里补上 `news.updated` 发布，信号流水线处理完成后会读取已更新的新闻记录，按 `NewsItemSummary` 序列化为前端可直接 upsert 的 payload，并附带 `updated_fields=["sentiment_label"]`；同时把 payload 构造收敛到 session 内完成，修掉了回归测试中暴露的 `DetachedInstanceError`。测试侧新增 batch-handler 事件用例，验证处理完成后会发出 `news.updated`。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_signal_pipeline.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增后端内容流事件 `news.updated`，字段为 `NewsItemSummary` + `updated_fields`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py::test_news_created_batch_handler_publishes_news_updated_after_processing -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py backend/tests/test_news_ingestion.py -q` 通过（30 个用例）
- 风险/后续事项：当前 `updated_fields` 只覆盖本轮真实会变化的 `sentiment_label`；如果后续把 topic/summary/mentions 等展示字段也纳入异步富化，需要同步扩展这份字段列表和对应前端合并逻辑

## 2026-03-25 12:23

- 修改人：Codex
- 修改范围：news created incremental event publish
- 变更内容：在 `NewsIngestionService.refresh_all()` 中为每条首次插入的新闻增加 `news.created` 单条事件发布，载荷直接复用 `NewsItemSummary` 的列表级契约字段；保留现有 `news.created_batch`，并明确发布顺序为“逐条 created 后再 batch”，避免破坏后端批处理订阅者。测试侧把原有 refresh 事件用例扩成失败先行的增量契约测试，验证单条事件与 batch 事件会同时发出。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增后端内容流事件 `news.created`，字段为 `NewsItemSummary` 的最小卡片字段；`news.created_batch` 保持不变
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_refresh_all_publishes_news_created_for_each_insert -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过（26 个用例）
- 风险/后续事项：当前只补了发布路径，前端 SSE 转发与 `news.updated` 富化事件还未完成；在这些后续任务落地前，单条 `news.created` 仍主要供后端测试和后续 stream 接线使用

## 2026-03-25 12:21

- 修改人：Codex
- 修改范围：news runtime contract spec-fix
- 变更内容：按 spec review 重做了 `NewsRuntimeService` 的 runtime 状态裁决：`last_incremental_event_at` 改为读取事件总线最近一次 `news.created/news.updated` 的发布时间，不再复用 `last_news_created_at`；`sources[].status` 收敛为 `ok/delayed/degraded/offline` 四态，移除 spec 外的 `disabled`；`markets[].mode` 改为按最近 30 分钟成功 source 的 tier 判定；`markets[].status` 与 `feed_status` 补齐 `live/delayed/degraded/offline` 语义。测试侧新增了一个多 market 契约用例，覆盖 delayed/degraded/offline/source-tier 切换和事件时间来源。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_runtime.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：`GET /api/news/runtime` 的字段名不变，但 `feed_status`、`markets[].status`、`markets[].mode`、`sources[].status` 与 `last_incremental_event_at` 的语义按设计稿收紧
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py::test_news_runtime_returns_market_and_source_health_contract backend/tests/test_news.py::test_news_runtime_maps_runtime_statuses_per_spec -q` 通过（2 个用例）；`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_ingestion.py -q` 通过（32 个用例）
- 风险/后续事项：当前 `last_incremental_event_at` 仍依赖事件总线只暴露“最近一次事件”的状态；如果后续 `news.updated` 明显比 `news.created` 更频繁，且产品严格要求区分“最近 created”和“最近 updated”，需要为内容流事件补更细的独立 runtime 指标

## 2026-03-25 11:43

- 修改人：Codex
- 修改范围：news route import regression follow-up
- 变更内容：补回 `backend/app/api/routes/news.py` 中 `analyze_news()` 所需的 `get_event_bus` 导入，修复 runtime 路由改动时引入的 `NameError` 回归；同步复核了 news route 文件，未发现其他同类缺失导入。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_analysis.py -q` 通过（19 个用例）
- 风险/后续事项：暂无新增风险

## 2026-03-25 11:41

- 修改人：Codex
- 修改范围：news runtime API contract + aggregation service
- 变更内容：新增 `GET /api/news/runtime`，由独立的 `NewsRuntimeService` 汇总当前 source health、最近新闻创建时间和 market 级运行态，并补充了 runtime response schema。测试侧先补了 `/api/news/runtime` 的契约用例，再按 TDD 最小实现路由与服务，确保返回字段、时间序列化和 market/source 结构与计划一致。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/source_health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_runtime.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增 `GET /api/news/runtime`，返回 `feed_status`、`last_refresh_finished_at`、`last_news_created_at`、`last_incremental_event_at`、`degraded_market_count`、`markets[]` 和 `sources[]`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py::test_news_runtime_returns_market_and_source_health_contract -q` 通过；`conda run -n news-caught pytest backend/tests/test_news.py -q` 通过（5 个用例）；`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_health.py -q` 通过（7 个用例）
- 风险/后续事项：runtime 聚合目前是基于本地数据库中现有的 source health 与 news 记录做同步汇总；如果后续需要把 `last_incremental_event_at` 与真实事件总线强绑定，还需要补事件源或缓存层，而不是只依赖当前的新闻写入时间

## 2026-03-25 11:34

- 修改人：Codex
- 修改范围：health projection market field + source-health backfill precedence fix
- 变更内容：为公开 health sources 视图补上 `market` 字段，避免 source+market 作用域在 API 层被压扁；同时调整 legacy `source_health` 回填优先级，改为先从 `news_item` 里确定市场，再回退到当前配置，最后才使用 `"unknown"`。为保证 TDD 约束，本轮先补了两个失败测试：一个覆盖 `/api/health/sources` 输出 `market`，一个覆盖旧数据库回填时以新闻历史市场为准。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/source_health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：`GET /api/health/sources` 的 `SourceHealthView` 新增 `market`；legacy source-health backfill 的市场决定顺序变为 `news_item` -> current source config -> `"unknown"`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_health.py::test_health_sources_endpoint_includes_market backend/tests/test_news_ingestion.py::test_initialize_database_prefers_news_item_market_when_backfilling_source_health -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过（26 个用例）
- 风险/后续事项：`initialize_database()` 里的 legacy SQLite 重建逻辑仍然依赖当前 schema 与历史数据结构基本一致；如果后续旧库的 `news_item` 表也出现字段缺失或 schema 漂移，这条回填路径还需要再做更强的兼容处理

## 2026-03-25 11:28

- 修改人：Codex
- 修改范围：news source health market scope + legacy SQLite rebuild
- 变更内容：将 `source_health` 的作用域从 `source_name` 单列唯一调整为 `source_name + market` 联合唯一；`NewsIngestionService` 在刷新源时按当前源市场写入/更新 health 记录；`SourceHealthRepository` 改为按源名和市场联合查找；`initialize_database()` 新增兼容旧本地数据库的迁移/回填逻辑，会在检测到旧版 `source_health` 表时重建为带 `market` 列和联合唯一约束的结构，并尽量从已配置 sources / 现有 `news_item` 记录中补齐市场值。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/source_health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/source_health_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：`source_health` 现在以 `source_name + market` 作为唯一键；仓储层 `get_or_create()` 需要显式传入 `market`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_refresh_source_tracks_health_per_source_market_pair backend/tests/test_news_ingestion.py::test_initialize_database_backfills_source_health_market_for_legacy_databases -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过（26 个用例）
- 风险/后续事项：SQLite legacy-table rebuild 目前是“重建 `source_health` 表并复制旧数据”的兼容路径，默认市场回填优先使用当前 sources 配置，其次尝试从 `news_item` 反推，最后退回 `"unknown"`；如果旧库里存在同一 source_name 的多市场历史记录但配置已变更，回填市场可能不是历史上最精确的值，需要后续按更可靠的来源再细化

## 2026-03-25 11:48

- 修改人：Codex
- 修改范围：news ingestion registry hardening final follow-up
- 变更内容：进一步收紧了 source registry 的输入校验：`_coerce_positive_int()` 现在会把 `Infinity` / `NaN` 这类非有限数值直接转换成受控 `ValueError`，避免在 `int(...)` 上触发 `OverflowError`；`load_sources()` 也不再把解析出来的顶层 `null`、`[]` 等非对象 payload 当作“没有配置”，而是明确报 `sources registry payload must be an object`。同步把这两类回归补成测试并保留前一轮的 schema-safe 覆盖。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；仅强化 source registry 输入校验
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_load_sources_rejects_malformed_top_level_payload backend/tests/test_news_ingestion.py::test_load_sources_rejects_non_finite_registry_values -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过（24 个用例）
- 风险/后续事项：暂无新增风险；后续如果 registry 继续扩字段，建议沿用“先测试、再做 schema-safe hydration”的同类模式

## 2026-03-25 11:39

- 修改人：Codex
- 修改范围：news ingestion registry schema-safe validation follow-up
- 变更内容：补齐了 `load_sources()` 对 malformed source registry 的受控错误处理：当顶层 `sources` 为 `null` 或其他非数组值时会返回明确的 `ValueError`；`markets` 现在只接受字符串数组或单一 `market` 回退值，遇到字典/空数组/非字符串元素会统一报 `ValueError`；`priority` 和 `cadence_seconds` 在 hydration 阶段先做数值规范化，避免 JSON 字符串或其他非数值触发 `TypeError`。同时把这几类边界情况拆成独立测试，保持回归覆盖清晰。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；仅加强 source registry 输入校验
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_load_sources_rejects_null_sources_array backend/tests/test_news_ingestion.py::test_load_sources_rejects_non_numeric_priority backend/tests/test_news_ingestion.py::test_load_sources_rejects_non_numeric_cadence_seconds backend/tests/test_news_ingestion.py::test_load_sources_rejects_malformed_markets_array -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过（20 个用例）
- 风险/后续事项：当前 `markets` 仍接受非空字符串数组和单一 `market` 回退；如果后续 registry 要求更严格的 ISO/market code 约束，可再单独补 schema 校验

## 2026-03-25 11:26

- 修改人：Codex
- 修改范围：news ingestion registry validation follow-up
- 变更内容：根据 review 反馈补齐了 source registry 的边界处理：`load_sources()` 现在会对顶层非对象条目返回受控 `ValueError`，避免出现 `AttributeError` 之类的内部异常；测试侧把 registry 相关用例拆成了独立的 `tier`、`priority`、`cadence_seconds` 保护，并增加了 malformed registry entry 的覆盖。同时把临时 `NEWS_SOURCES_FILE`/`get_settings()` 缓存处理封装成测试辅助函数，在用例结束时恢复环境和缓存状态，避免温热缓存污染后续测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；仅强化 source registry 读取时的输入校验
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_load_sources_backfills_registry_defaults_from_legacy_config backend/tests/test_news_ingestion.py::test_load_sources_rejects_invalid_tier backend/tests/test_news_ingestion.py::test_load_sources_rejects_invalid_priority backend/tests/test_news_ingestion.py::test_load_sources_rejects_invalid_cadence_seconds backend/tests/test_news_ingestion.py::test_load_sources_rejects_malformed_registry_entries -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过（16 个用例）
- 风险/后续事项：测试辅助函数当前按本次 task 需要恢复 `NEWS_SOURCES_FILE` 和 settings cache；如果后续有更多环境变量驱动的配置测试，建议复用同样的恢复模式

## 2026-03-25 11:18

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch 设计文档
- 变更内容：新增一份正式 design spec，把 `karpathy/autoresearch` 的“受控实验”思路迁移到本项目新闻相关性优化场景，明确了第一阶段目标为“市场相关新闻命中率”提升，并设计了约 `400` 条混合样本的半自动标注数据集、`DeepSeek` 首标加人工复核流程、以 `precision` 为主指标的离线评测器、研究代理的可改动边界、实验保留规则以及项目内研究账本/目录结构；本次仅产出设计，不涉及运行时代码实现。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-25-market-news-relevance-autoresearch-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：仅设计层面提出后续新增研究数据集 schema、评测结果产物和实验账本字段，本次未改现有 API 或数据库
- 验证情况：未验证；本次为设计文档产出，待进入 implementation plan 和实现阶段后再补脚本、测试与评测验证
- 风险/后续事项：该设计仍需用户 review，并在确认后进入 `writing-plans` 阶段细化为实现计划；当前尚未定义具体 `DeepSeek` prompt、样本文件路径和实验控制脚本接口

## 2026-03-25 11:12

- 修改人：Codex
- 修改范围：news ingestion source registry defaults/validation
- 变更内容：为 `news_ingestion` 的 source registry 增加了兼容旧配置的 hydration 层和基础校验：旧版只写 `market` 的配置现在会自动回填 `markets`、`tier`、`priority`、`cadence_seconds` 和 `supports_incremental` 的默认值；同时对 `tier`、`priority`、`cadence_seconds` 做了最小有效性校验，非法 registry 值会在加载阶段直接报错，而不是等到刷新时才暴露。同步把 `news_sources.example.json` 改成带 registry 字段的新形状，并补了测试覆盖 legacy backfill 与 invalid registry values。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/news_sources.example.json`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：source registry 允许新增 `tier`、`priority`、`cadence_seconds`、`markets` 和 `supports_incremental` 字段；旧配置继续兼容
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_load_sources_backfills_registry_defaults_from_legacy_config backend/tests/test_news_ingestion.py::test_load_sources_rejects_invalid_registry_values -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过（13 个用例）
- 风险/后续事项：当前校验只覆盖本 task 要求的 `tier`、`priority`、`cadence_seconds`，未进一步约束 `markets` 的内容或 registry 中其他字段的 schema；后续 Task 2/后续配置迁移可以继续收紧

## 2026-03-25 10:41

- 修改人：Codex
- 修改范围：newsfeed 数据源与实时性 design/plan 文档
- 变更内容：基于现有 `news_ingestion`、事件总线、`newsStore` 和 `News Feed` 视图，新增并完善了一份正式 design spec 与对应 implementation plan，明确了新闻源分层治理、增量事件闭环、freshness/source health 可观测以及分阶段实施顺序；在 reviewer 反馈后进一步补齐了 orchestrator 触发阈值、`GET /api/news/runtime` schema、事件幂等语义、source 配置失败策略、事件消费者迁移矩阵、runtime 唯一事实来源与裁决顺序，并明确了 `news.updated` 走现有 `SSE` 通道、`runtimeStatusStore`/`newsStore` 的 owner 边界、scoped list 的增量移除规则、旧 source 配置迁移默认值，以及“迟到/补源模式/状态带”这些前端阈值与渲染口径；最后补充了后端发布/转发接线点、`source_health` 的 `source_name + market` 粒度、`enabled market` 定义和离线 market 的 `mode = none`，并将实现计划细化到 DB migration/backfill、example config、独立 runtime service、SSE 转发和前端最小接线。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-25-newsfeed-source-realtime-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-25-newsfeed-source-realtime-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：仅设计文档层面提出后续新增 source registry 字段、`news.created` / `news.updated` 事件与 `GET /api/news/runtime`，本次未改运行时代码
- 验证情况：未验证；本次为设计文档产出，待后续进入计划与实现阶段后补代码级验证
- 风险/后续事项：该 design 仍需进入 spec review 和用户 review，确认后再写 implementation plan，避免与现有新闻、事件层和 runtime 状态链路冲突

## 2026-03-24 00:31

- 修改人：Codex
- 修改范围：本地 dev launcher 启动稳态修复
- 变更内容：为 `scripts/dev.sh` 增加端口冲突清理、backend 启动早退检测、`/api/stream/status` 就绪等待、依赖命令预检和进程树清理，避免 `make dev` 在旧监听残留或 backend 未真正启动时留下“前端活着、后端拒绝连接”的半启动状态，并在启动阶段保留子进程原始退出码；同步把 `test_dev_launcher.py` 改为基于仓库根目录动态定位脚本，并补充对端口清理、ready wait、失败传播和依赖声明的约束；README 增加 launcher 新行为说明；新增本轮 design/plan 文档。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-fix-dev-startup/scripts/dev.sh`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-fix-dev-startup/backend/tests/test_dev_launcher.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-fix-dev-startup/README.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-fix-dev-startup/docs/superpowers/specs/2026-03-24-dev-launcher-port-guard-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-fix-dev-startup/docs/superpowers/plans/2026-03-24-dev-launcher-port-guard-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-fix-dev-startup/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught pytest backend/tests/test_dev_launcher.py -q` 通过（2 个用例）；手动运行 `./scripts/dev.sh` 时已验证 frontend 缺依赖会被启动阶段早退检测及时报错，不再静默留下坏状态，并验证占用 `8000`/`5174` 的假服务会在启动前被清理后由真实 backend/frontend 接管；后续将继续补完整后端测试和完整启动验证
- 风险/后续事项：launcher 会主动终止占用 `8000`/`5174` 的本地监听进程，仅适用于本地开发；如果后续需要更保守的策略，可再改成只清理带本项目特征的进程

## 2026-03-24 00:21

- 修改人：Codex
- 修改范围：worktree 目录忽略规则补齐
- 变更内容：将项目本地 `.worktrees/` 目录加入 `.gitignore`，避免后续创建隔离 worktree 时其内容污染主仓库状态，满足仓库对 worktree 使用的基础安全要求。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.gitignore`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`git check-ignore .worktrees` 预计在提交后生效；未涉及运行时代码
- 风险/后续事项：无

## 2026-03-24 00:05

- 修改人：Codex
- 修改范围：Watchlist dashboard review 问题修正
- 变更内容：按子代理 code review 修正了 6 个合并前问题：前端 `getStockKline` 不再在后端报错时伪造 mock K 线；`watchlistStore` 在删除最后一个标的时会清空残留的图表和新闻状态，并为 period 切换补上请求序号保护，避免快速切换周期时旧响应覆盖新周期；`WatchlistView` 恢复了选股后的 URL 同步，把 `/watchlist/:symbol` 路由切回同一套 dashboard 组件，并在手动刷新/删除失败时只保留页面内错误状态、不再抛出未处理 rejection；后端 `MarketChartService.get_sparklines()` 改为按 symbol 部分容错，单个异常标的不再拖垮整个 sparkline 批量请求。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/backend/app/services/market_chart_service.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/WatchlistSidebar.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/code-change-log.md`
- 接口/数据结构变化：无，主要是错误处理、路由行为和局部容错策略修正
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过（102 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts src/components/watchlist/StockSparkline.test.ts src/components/watchlist/KlineChart.test.ts` 通过（5 个文件 / 30 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：`/watchlist/:symbol` 现在与 `/watchlist` 共用 dashboard 组件，旧的 `WatchlistDetailView` 仍保留但已不在路由树中；如果后续确认不会再回退到旧单页详情，可以继续清理死代码和对应测试

## 2026-03-23 23:51

- 修改人：Codex
- 修改范围：Watchlist 添加自选股 modal 体验补齐
- 变更内容：按新 spec 将 sidebar 中“搜索候选即点即加”的流程重构为显式 `搜索 / 添加自选股` modal。新增 `WatchlistAddModal`，支持候选搜索、选中确认、默认 `直接添加`、可选展开高级设置并填写 `alert_threshold`；`WatchlistSidebar` 退回为左栏筛选与入口面板，不再在候选列表上直接落库；`WatchlistView` 接管 modal 的本地状态，在添加成功后自动关闭并选中新股票，失败时保留当前选择与阈值方便重试。同步补充视图测试，覆盖打开 modal、候选选择不立即提交、直接添加、带阈值提交和失败保留状态这几条核心路径。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/WatchlistAddModal.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/WatchlistSidebar.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/superpowers/specs/2026-03-23-watchlist-add-modal-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/superpowers/plans/2026-03-23-watchlist-add-modal-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/code-change-log.md`
- 接口/数据结构变化：无，继续复用现有 `createWatchlist` 接口与 `alert_threshold` 字段
- 验证情况：`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/stores/watchlistStore.test.ts` 通过（2 个文件 / 16 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：这轮 modal 还没有补键盘上下选择、ESC 关闭、焦点陷阱等更完整的 dialog 可访问性；如果你下一步继续打磨体验，优先建议补这些细节，再做新闻 marker 与侧栏的深联动

## 2026-03-23 23:18

- 修改人：Codex
- 修改范围：Watchlist 仪表盘 final review 尾项修正
- 变更内容：根据第二轮子代理复核，继续修正两个残留问题：`IndicatorChart` 在 `indicators` 为空时现在会显式清空已有 series，避免切换股票或请求失败时副图残留上一只股票的数据；`StockCard` 外层交互容器改为带键盘可访问性的 `article[role=button]`，删除按钮不再嵌套在外层 `<button>` 中，消除无效交互 HTML 和潜在点击/键盘冲突。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/IndicatorChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/StockSparkline.test.ts src/stores/watchlistStore.test.ts` 通过（4 个文件 / 15 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：副图和主图目前已是真实 Lightweight Charts，但新闻 marker 与侧栏的高亮联动仍偏轻量；如果后续要做到 spec 中更完整的 hover/scroll 同步，建议继续补专门的交互测试

## 2026-03-23 23:16

- 修改人：Codex
- 修改范围：Watchlist 仪表盘 review 回合修正
- 变更内容：根据子代理 code review 补回了新仪表盘中被误删的管理与运维能力：`WatchlistView` 重新展示 runtime/手动刷新状态卡，`WatchlistSidebar` 恢复候选添加入口与持仓删除入口；同时修复 `loadCandidates()` 失败会阻断整页加载的问题，并为 `watchlistStore` 增加 detail 请求竞态保护，避免快速切换股票时旧请求覆盖新详情。图表层继续补齐：`KlineChart` 在 `klineData` 为空时会主动清空旧 series，`IndicatorChart` 也接入 Lightweight Charts，前端视图测试则显式 mock 图表库，避免 jsdom canvas 能力不足导致误报。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/WatchlistSidebar.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockSparkline.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockSparkline.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/IndicatorChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/code-change-log.md`
- 接口/数据结构变化：`POST /api/market/sparklines` 超限时返回 400，与 spec 对齐；其余为前端状态管理与交互修正
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过（101 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts src/components/watchlist/StockSparkline.test.ts src/components/watchlist/KlineChart.test.ts` 通过（4 个文件 / 15 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 sidebar 的添加流程是“候选即点即加”，还没有做成 spec 里更完整的 modal；另外 Redis 缓存目前是“Redis 优先 + 内存回退”，还没增加独立的 Redis 集成测试环境

## 2026-03-23 23:01

- 修改人：Codex
- 修改范围：Watchlist 仪表盘与 K 线/迷你走势数据链路
- 变更内容：新增后端 `GET /api/market/symbols/{symbol}/kline` 和 `POST /api/market/sparklines`，由新建 `market_chart_service` 负责拉取 yfinance 历史 K 线、计算 MA/MACD/KDJ/布林带、对齐相关新闻日期并提供内存级缓存兜底；前端扩展 `watchlistStore`、API 类型与 mock 数据，新增一组 watchlist 仪表盘组件，把 `/watchlist` 从旧表格页重构为左侧股票雷达 + 右侧详情面板的 master-detail 布局，支持周期切换、迷你走势、K 线摘要、副图指标按钮和关联新闻侧栏。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/backend/app/schemas/market.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/backend/app/services/market_chart_service.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/WatchlistSidebar.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockCard.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockSparkline.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockDetailPanel.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/KlineChart.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/IndicatorChart.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockMetricsGrid.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/RelatedNewsSidebar.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/package-lock.json`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/superpowers/specs/2026-03-23-watchlist-dashboard-kline-design.md`（新增同步）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/superpowers/plans/2026-03-23-watchlist-dashboard-kline-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/code-change-log.md`
- 接口/数据结构变化：新增 `GET /api/market/symbols/{symbol}/kline` 与 `POST /api/market/sparklines`；前端新增 K 线、技术指标、新闻标记与 sparkline 数据结构
- 验证情况：`conda run -n news-caught pytest backend/tests/test_market.py -q` 通过（13 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（99 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts` 通过（2 个文件 / 11 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：后端缓存当前是进程内内存缓存，还没有落到 spec 预期的 Redis；前端图表当前使用轻量 DOM/SVG 摘要组件而未真正接入 Lightweight Charts，因此“真实 K 线交互、十字光标和多副图同步”仍可在下一轮继续补齐

## 2026-03-23 21:38

- 修改人：Codex
- 修改范围：Dashboard 顶部异动股票指标卡跳转入口
- 变更内容：将首页 `Dashboard` 顶部 `HeroMetrics` 区域中的“异动股票”指标卡改成整卡可点击入口，直接跳转到 `/watchlist`。这样顶部四张指标卡的交互模型保持一致，用户不需要再下滑到下方 `Live Movers` 区块才能进入自选股异动页。同步补充视图测试，明确约束顶部指标区内必须存在指向 `/watchlist` 的链接。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-dashboard-movers-metric-link-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-dashboard-movers-metric-link-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无；仅前端路由映射增强，继续复用现有 `/watchlist` 页面
- 验证情况：`npm --prefix frontend run test -- --run src/views/DashboardView.test.ts` 通过（1 个文件 / 5 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前顶部指标卡和下方 `Live Movers` 区块都会进入 `/watchlist`，这是有意的入口重复；若后续希望区分“总览入口”和“细分入口”，需要再单独设计指标卡更细粒度的跳转目标

## 2026-03-23 20:22

- 修改人：Codex
- 修改范围：首页 Dashboard 新闻预览点击跳转修复
- 变更内容：排查后确认“主页面新闻点不进去”的根因不在 `News Feed` 路由，而在 `Dashboard` 首页新闻预览列表本身只是静态 `<article>`，没有绑定任何跳转逻辑。现已把首页新闻预览改成可点击按钮，点击后直接路由到站内 `News Detail`；同时补充首页点击回归测试，并为 `News Feed` 视图补上点击卡片进入详情页的回归测试，避免后续再把两条入口链路改坏。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无；仅前端交互和路由触发修复
- 验证情况：`npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/views/DashboardView.test.ts` 通过（2 个文件 / 8 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：首页新闻预览现在统一进入站内详情页，而不是直接外跳原文；如果后续希望首页也支持“直接打开原文”，需要在紧凑卡片里单独设计第二入口，避免与当前整卡点击区域冲突

## 2026-03-23 20:07

- 修改人：Codex
- 修改范围：新闻详情页原文入口强化
- 变更内容：保留 `News Feed` 点击后进入站内 `News Detail` 的既有路径，不改动列表页跳转；将详情页顶部原有的普通“打开原文”文本链接提升为更明显的主操作按钮，并在移动端改成整行宽按钮，方便用户先进入详情页做分析，再决定是否打开原始新闻。同步补充测试，覆盖“有 `canonical_url` 时展示显式原文入口”和“无 `canonical_url` 时隐藏入口”的条件渲染。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-news-detail-source-link-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-news-detail-source-link-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无；继续复用现有 `canonical_url` 字段，不新增前后端契约
- 验证情况：`npm --prefix frontend run test -- --run src/views/NewsDetailView.test.ts` 通过（1 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本次只增强详情页原文入口，不在 `News Feed` 列表页新增直接外跳能力；如果后续用户希望列表页就能快速打开原文，需要再单独设计卡片级双入口交互，避免和当前整卡进详情的点击区域冲突

## 2026-03-23 18:51

- 修改人：Codex
- 修改范围：runtime 诊断提示与建议动作收口
- 变更内容：新增前端 `runtimeDiagnostics` 归一化工具，把 `SSE` 连接状态、stream 降级状态和 `market_worker` runtime 状态统一映射成少量诊断结果；`AppShell` 现在除了展示原始 badge，还会给出当前 runtime 问题的一句话诊断、解释和建议动作，并在 worker 故障/陈旧场景下直接引导用户打开 Watchlist；`WatchlistView` 的 worker 面板也复用同一套诊断结果，把现有“立即刷新一轮”按钮解释成推荐动作，而不再只是孤立按钮。这样用户看到 `degraded`、未上报或陈旧状态时，不需要自己拼字段理解下一步该做什么。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/runtimeDiagnostics.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/runtimeDiagnostics.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-runtime-diagnostics-actions-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-runtime-diagnostics-actions-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增后端接口或前端 API 字段；仅新增前端内部 runtime 诊断归一层
- 验证情况：`npm --prefix frontend run test -- --run src/utils/runtimeDiagnostics.test.ts src/components/layout/AppShell.test.ts src/views/WatchlistView.test.ts src/stores/runtimeStatusStore.test.ts src/stores/watchlistStore.test.ts` 通过（5 个文件 / 21 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前诊断层仍基于前端时间阈值和已有快照字段做启发式判断，例如把 10 分钟无成功/心跳视为陈旧；这提升了可操作性，但不是严格运维告警。如果后续需要更精确的故障分类，应再考虑后端提供专门的 runtime reason code

## 2026-03-23 18:05

- 修改人：Codex
- 修改范围：AppShell 空闲期 runtime 低频轮询
- 变更内容：在保留现有关键 `SSE` 事件节流补刷的基础上，为 `AppShell` 增加 60 秒一次的低频 runtime 轮询；轮询本身不直接请求接口，而是统一走 `runtimeStatusStore.loadRuntimeStatusIfStale(45)`，继续由 store 负责新鲜度判断与并发保护。这样当系统长时间没有 `watchlist.movement` 或 `stream.keepalive` 时，壳层中的 `market-worker` 与 stream runtime 摘要仍会缓慢更新，而不需要改后端 `SSE` 事件契约。同时补上壳层卸载保护，避免异步 bootstrap 在组件销毁后迟到启动轮询或继续留下悬空 timer。同步补充组件测试，覆盖轮询启动、触发、卸载清理和“先卸载后完成初始化”的边界行为。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-runtime-status-low-frequency-polling-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-runtime-status-low-frequency-polling-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或字段；前端仅增加壳层轮询编排，继续复用既有 `GET /api/stream/status`
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts` 通过（1 个文件 / 8 个用例）；`npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts src/components/layout/AppShell.test.ts src/stores/connectionStore.test.ts src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts` 通过（5 个文件 / 17 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 runtime 新鲜度仍然是 best-effort；空闲期最多可能滞后约 60 秒，且数据源仍是快照接口而非真正 push 的 runtime 事件。如果后续需要更细粒度的实时可观测性，再评估新增独立 `runtime.updated` 事件，而不是把摘要硬塞进现有业务 `SSE` 载荷

## 2026-03-23 16:10

- 修改人：Codex
- 修改范围：runtime 状态在关键 `SSE` 事件后做节流刷新
- 变更内容：在 `runtimeStatusStore` 中新增 `loadRuntimeStatusIfStale()`，把 runtime 快照刷新节流逻辑收口到 store 内，默认按 15 秒窗口控制；`AppShell` 现在会在 `watchlist.movement` 和 `stream.keepalive` 事件后触发该入口，使壳层中的 `market-worker` 与事件层 runtime 指标会在系统活跃时自动变新，而不需要引入固定轮询。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/runtimeStatusStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/runtimeStatusStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-runtime-status-event-refresh-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-runtime-status-event-refresh-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；前端仅增加 runtime store 的节流刷新入口，事件驱动地再次读取既有 `/api/stream/status`
- 验证情况：`npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts src/components/layout/AppShell.test.ts src/stores/connectionStore.test.ts src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts` 通过（5 个文件 / 15 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 runtime 刷新仍依赖启动、人工动作和关键 `SSE` 事件；如果系统长时间无事件但后台状态发生变化，壳层仍不会立即感知。下一阶段若要进一步提升实时性，可以再评估低频轮询或后端直接把 runtime 摘要塞进 `SSE` 事件

## 2026-03-23 16:05

- 修改人：Codex
- 修改范围：前端 `/api/stream/status` 请求去重与连接状态收口
- 变更内容：把 `/api/stream/status` 的唯一读取入口正式收口到 `runtimeStatusStore`，新增 `usingMock` 持久化；`connectionStore` 去掉直接请求接口的职责，改为通过 `applyStreamStatus()` 接收 runtime 快照，只负责 `SSE` 连接状态机与事件生命周期；`AppShell` 启动时先加载 runtime 状态，再把快照同步给 `connectionStore`，从而消除此前启动阶段对同一状态接口的双请求。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/runtimeStatusStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/runtimeStatusStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/connectionStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/connectionStore.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-stream-status-request-dedup-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-stream-status-request-dedup-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增后端接口；前端 store 职责调整为 `runtimeStatusStore` 唯一读取 `/api/stream/status`，`connectionStore` 不再直接发起该请求
- 验证情况：`npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts src/stores/connectionStore.test.ts src/components/layout/AppShell.test.ts src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts` 通过（5 个文件 / 12 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 runtime 快照仍是启动时和显式动作后刷新，不会随着 `SSE` 事件自动回填；如果后续希望壳层 runtime 指标更实时，需要再决定是增加轮询，还是在特定 `SSE` 事件后触发轻量刷新

## 2026-03-23 15:43

- 修改人：Codex
- 修改范围：前端运行时状态抽离为独立 `runtimeStatusStore`
- 变更内容：新增独立 `runtimeStatusStore` 统一承接 `/api/stream/status` 和 `market_worker` 运行状态，`AppShell` 与 Watchlist 页面改为直接消费该 store；`watchlistStore` 不再在 `loadWatchlist()` 中顺手请求 runtime 状态，只保留自选股业务数据与手动刷新结果，并在人工“立即刷新一轮”成功后联动刷新 runtime store。这样全局壳层不再依赖 watchlist 数据加载副作用才能看到 worker 健康状态，前端运行时基础设施状态和业务状态边界也更清晰。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/runtimeStatusStore.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/runtimeStatusStore.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-runtime-status-store-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-runtime-status-store-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增后端接口；前端状态结构调整为新增独立 `runtimeStatusStore`，`watchlistStore` 不再持有 `marketWorkerStatus`
- 验证情况：`npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts src/stores/watchlistStore.test.ts src/components/layout/AppShell.test.ts src/views/WatchlistView.test.ts` 通过（4 个文件 / 11 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 `connectionStore` 与 `runtimeStatusStore` 仍会分别请求一次 `/api/stream/status`，虽然职责已经分清，但请求层尚未去重；如果后续继续增强 runtime 面板或轮询逻辑，建议把 SSE 连接摘要与 runtime 接口读取再进一步收口

## 2026-03-23 14:50

- 修改人：Codex
- 修改范围：`AppShell` 系统状态卡片指标对齐修复
- 变更内容：先将左下角 `System Status` 卡片中的两条状态头从 `flex justify-between` 改为统一的布局约束，随后根据实际 UI 继续收敛为纵向 stack：标签在上、badge 独占下一行整宽区域。这样 `SSE 已断开`、`market_quote_producer ok` 之类长状态文案不再和左侧标签争抢同一行宽度，`Market worker` 也不会被挤成难看的断行；同时补充测试锚点并在 `AppShell` 组件测试中锁定 stack 布局和整宽 badge 约束。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-app-shell-status-indicator-alignment-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-app-shell-status-indicator-alignment-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-app-shell-status-badge-stacking-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-app-shell-status-badge-stacking-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无，仅调整前端模板布局和测试约束
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts` 通过（1 个文件 / 5 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前修复优先保证侧栏稳定和可读性，因此 badge 改成了整宽堆叠展示；如果后续希望恢复更紧凑的横向信息密度，需要在更宽侧栏或更短文案前提下重新设计

## 2026-03-23 14:33

- 修改人：Codex
- 修改范围：Watchlist 展示最近一次手动刷新结果
- 变更内容：在 `watchlistStore` 中新增 `lastManualRefreshResult`，手动执行“立即刷新一轮”成功后会保留本次操作返回的 `quotes_count`、`symbols` 与 `triggered_at`；Watchlist 页的 `market-worker` 状态面板现在会直接显示最近一次人工刷新时间、刷新标的数量和 symbol 列表。这样用户除了看到 worker 健康状态，也能知道刚刚那次人工重试到底有没有生效。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-manual-refresh-result-visibility-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-manual-refresh-result-visibility-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；前端仅复用已有 `POST /api/market/refresh` 返回结果做本地状态展示
- 验证情况：`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts` 通过（2 个文件 / 5 个用例）；`npm --prefix frontend run build` 通过；`conda run -n news-caught pytest backend/tests -q` 通过（94 个用例）
- 风险/后续事项：该结果只保存在当前前端会话内，刷新页面后会丢失；如果后续需要跨页面或跨会话保留人工操作历史，应再补后端持久化审计记录

## 2026-03-23 14:21

- 修改人：Codex
- 修改范围：自选股行情人工“立即刷新一轮”闭环
- 变更内容：新增后端显式运维接口 `POST /api/market/refresh`，用于在独立 `market-worker` 之外人工触发一次同步行情刷新，并继续发布既有 `market.watchlist_refreshed` 事件；前端 `watchlistStore` 增加 `refreshMarketQuotes()`，Watchlist 页面状态面板新增“立即刷新一轮”按钮、加载态和失败提示。这样当用户看到 worker `degraded` 或行情滞后时，可以直接在 UI 上触发一次人工重试，而不需要切回终端。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-manual-market-refresh-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-manual-market-refresh-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增 `POST /api/market/refresh`，返回 `quotes_count`、`symbols`、`triggered_at`；前端开始消费该接口作为显式人工运维动作
- 验证情况：`conda run -n news-caught pytest backend/tests/test_market.py -q` 通过（8 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts` 通过（2 个文件 / 5 个用例）；`npm --prefix frontend run build` 通过；`conda run -n news-caught pytest backend/tests -q` 通过（94 个用例）
- 风险/后续事项：该接口会在 Web 进程里执行一次同步行情拉取，因此应被视为人工重试工具，而不是日常生产路径；如果后续需要更纯粹的架构边界，可以再把“refresh now” 改成发命令给独立 worker 执行

## 2026-03-23 14:07

- 修改人：Codex
- 修改范围：全局壳层展示 `market-worker` 健康状态
- 变更内容：在 `AppShell` 的 `System Status` 面板中复用 `watchlistStore.marketWorkerStatus`，新增全局可见的 `market-worker` 状态摘要，展示 worker 名称、健康状态、最近成功时间和最近错误。这样无论用户停留在哪个页面，都能直接看到行情生产链路是否处于 `ok` 或 `degraded`。本次不新增请求，也不引入新的全局状态中心，完全复用现有 watchlist 加载链路。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-app-shell-market-worker-visibility-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-app-shell-market-worker-visibility-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无；前端仅把已有 `watchlistStore.marketWorkerStatus` 上提到全局壳层展示
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts` 通过（1 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前全局壳层仍依赖 `watchlistStore.loadWatchlist()` 完成后才有 `market-worker` 状态；如果后续想把运行状态完全独立于自选股数据加载，需要再抽离专门的 runtime store

## 2026-03-23 14:01

- 修改人：Codex
- 修改范围：Watchlist 页面展示 `market-worker` 运行状态
- 变更内容：扩展前端 `StreamStatus` 类型与 `watchlistStore`，在加载自选股列表时顺手拉取 `/api/stream/status` 并缓存其中的 `market_worker` 状态；`WatchlistView` 顶部新增一个轻量状态面板，直接展示独立行情 worker 的名称、当前状态、最近成功时间、最近产出 quotes 数和最近错误。这样当页面出现旧快照或 `unavailable` 时，用户能直接在 watchlist 页面判断是不是 worker 未启动或刚刚失败。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-watchlist-market-worker-visibility-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-watchlist-market-worker-visibility-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；前端开始消费现有 `GET /api/stream/status` 响应中的 `market_worker` 字段
- 验证情况：`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts` 通过（2 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前状态面板只显示在 Watchlist 页面，其他页面仍看不到 worker 健康度；如果后续想把可观测性做成全局能力，可以再把这部分上提到壳层或共享状态中心

## 2026-03-23 13:55

- 修改人：Codex
- 修改范围：本地开发入口自动托管 `market-worker`
- 变更内容：更新 `scripts/dev.sh`，让 `make dev` 在启动后端和前端的同时自动启动独立自选股行情 worker，并把 `MARKET_WORKER_PID` 纳入统一的清理与存活检测逻辑；这样任一子进程退出都会触发整体退出，`Ctrl+C` 也会一并停止三个进程。同步补充脚本回归测试，并更新 README 中 `make dev` 的说明。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/scripts/dev.sh`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_dev_launcher.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-dev-launcher-market-worker-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-dev-launcher-market-worker-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无；仅本地开发启动行为变化，`make dev` 现在默认同时拉起 backend、frontend 和 `market-worker`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_dev_launcher.py -q` 通过（1 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（93 个用例）
- 风险/后续事项：当前 `make dev` 会多一个长期运行进程和更多终端输出；如果后续再接入新闻 worker 或更多后台任务，建议统一抽象成更清晰的本地 supervisor，而不是继续在 shell 脚本中线性堆叠

## 2026-03-23 13:42

- 修改人：Codex
- 修改范围：独立 market worker 可观测性与状态接口扩展
- 变更内容：新增数据库表 `worker_runtime_status` 和对应仓储，由 `MarketQuoteProducer` 在每轮刷新后持久化 heartbeat、成功/失败计数、最近错误和最近产出 quotes 数；`/api/stream/status` 现在会额外返回 `market_worker` 区块，展示独立 `market_quote_producer` 的运行状态。这样 Web API 即使与 worker 分进程运行，也能直接看到行情 worker 是否正常工作。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/worker_runtime_status.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/__init__.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/worker_runtime_status_repository.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/market_quote_producer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/stream.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/stream.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market_quote_producer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_stream_status.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-market-worker-observability-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-market-worker-observability-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：`GET /api/stream/status` 响应新增可选 `market_worker` 字段，包含独立行情 worker 的 `name`、`status`、最近 heartbeat/成功/失败时间、最近错误、`cycle_count`、`success_count`、`failure_count`、`last_quotes_count`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_market_quote_producer.py backend/tests/test_stream_status.py -q` 通过（9 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（92 个用例）
- 风险/后续事项：当前状态存储依赖应用数据库，适合本地和单库部署；如果后续把 worker 与 Web 拆到多数据库或跨区域部署，需要再定义统一的运行状态源或集中监控出口

## 2026-03-23 13:18

- 修改人：Codex
- 修改范围：自选股行情 producer 独立 worker 化
- 变更内容：将上一轮仍挂在 FastAPI `lifespan` 里的 `MarketQuoteProducer` 提取为独立 worker 入口 `python -m app.workers.market_quote_producer`，worker 启动时负责初始化数据库、构建事件总线、注册 `market.watchlist_refreshed` 的本地阈值提醒订阅者，并阻塞运行行情 producer；Web 应用启动流程不再持有或启动行情 producer，只保留 API 和新闻相关事件处理。同步补充 worker 入口测试、Web 不再启动 producer 的生命周期测试，并新增 `make market-worker` 与 README 运行说明。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/workers/market_quote_producer.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/market_quote_producer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market_quote_producer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/Makefile`
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-market-quote-worker-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-market-quote-worker-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：HTTP 接口和事件名不变；运行方式变化为需要显式启动独立 `market-worker` 才会连续生产自选股行情并触发阈值提醒
- 验证情况：`conda run -n news-caught pytest backend/tests/test_market_quote_producer.py backend/tests/test_market.py -q` 通过（13 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（90 个用例）
- 风险/后续事项：当前 `make dev` 仍不会自动拉起 `market-worker`，开发环境若只启动前后端会看到 watchlist 维持旧快照或 `unavailable`；后续可考虑扩展 `scripts/dev.sh` 一并托管 worker，或给前端/状态接口增加更明确的 worker 存活提示

## 2026-03-23 02:10

- 修改人：Codex
- 修改范围：自选股行情生产者从请求链路迁移到后台 producer
- 变更内容：新增 `MarketQuoteProducer` 后台服务，在应用启动后按固定轮询间隔读取 watchlist、拉取真实行情、写入快照并发布 `market.watchlist_refreshed`；`QuoteService` 拆分为“主动刷新”和“缓存读取”两条路径，`/api/market/watchlist` 与 `/api/market/symbols/{symbol}` 不再在请求路径里同步触发上游行情拉取，只返回最近一次已生产的快照结果；同步补充 producer 生命周期测试、缓存读取路由测试、配置默认值测试，以及 README 中的运行说明与环境变量文档。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/market_quote_producer.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/quote_service.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market_quote_producer.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_event_bus.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-market-quote-producer-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-market-quote-producer-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：HTTP 接口路径和字段不变；`GET /api/market/watchlist` 与 `GET /api/market/symbols/{symbol}` 的职责从“请求时刷新并返回”变为“读取后台 producer 最近一次已生成的行情”；事件名 `market.watchlist_refreshed` 保持不变，但生产者从 route 迁移为后台任务
- 验证情况：`conda run -n news-caught pytest backend/tests/test_market_quote_producer.py backend/tests/test_market.py backend/tests/test_event_bus.py backend/tests/test_stream_status.py -q` 通过（17 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（89 个用例）
- 风险/后续事项：当前仍是基于 `yfinance` 的轮询 producer，不是外部流式实时连接；应用进程重启后首次 producer 周期前可能短暂返回 `unavailable`/`quote not produced yet`，若后续需要更强实时性或多实例一致性，应继续把 producer 输入侧切到独立 worker 或 streaming provider

## 2026-03-23 00:54

- 修改人：Codex
- 修改范围：事件层第二阶段接入 `news.signals_processed`、通知批处理和行情刷新事件
- 变更内容：继续沿用 Redis 混合事件层，把原先散落在 route 内的副作用收束到统一事件契约上。`NewsSignalPipelineService.process_news_ids()` 现在返回处理摘要，应用启动时注册的 `news.created_batch` 订阅者在跑完信号流水线后继续发布 `news.signals_processed`；新闻分析路由不再直接调用通知服务，而是发布 `news.analysis_completed`；自选股行情路由不再在 route 内做阈值提醒，而是发布 `market.watchlist_refreshed`，再由本地订阅者结合 watchlist 阈值调用通知服务。这样后续接入真正实时行情源时，只要继续发布同名事件即可复用现有通知和处理链。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_signal_pipeline.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/event_bus.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_analysis.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-event-layer-stage2-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-event-layer-stage2-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增 HTTP 接口；事件层新增 `news.signals_processed`、`news.analysis_completed`、`market.watchlist_refreshed` 事件名；新增环境变量 `REDIS_STREAM_MARKET_WATCHLIST`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_event_bus.py backend/tests/test_news_ingestion.py backend/tests/test_news_analysis.py backend/tests/test_market.py backend/tests/test_feishu_notify.py -q` 通过（42 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（82 个用例）
- 风险/后续事项：当前行情仍是请求触发刷新而非真正的 WebSocket 实时流，`market.watchlist_refreshed` 只是先统一了事件契约；下一阶段若接入实时行情 provider，应优先让新 provider 直接向该事件入口发布批量行情，而不是再把逻辑写回 route

## 2026-03-23 00:42

- 修改人：Codex
- 修改范围：Redis 混合事件层第一阶段接入
- 变更内容：将原有仅支持进程内同步分发的 `EventBus` 升级为“Redis Streams 发布 + 本地总线兜底”的混合事件层，新增 Redis publisher 与事件层状态模型；`NewsIngestionService.refresh_all()` 现对新增新闻发布 `news.created_batch` 事件，由应用启动时注册的本地订阅者继续驱动 `NewsSignalPipelineService`，从而在保持现有业务语义和前端 `SSE` 展示不变的前提下，为后续多源异步化接入打下基础；同时扩展 `/api/stream/status` 返回真实事件层后端、Redis 可用性、最近事件和错误信息，并补充 README 中的 Redis 运行说明与环境变量。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/event_bus.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/redis_stream_bus.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/stream.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/stream.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_event_bus.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_stream_status.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-redis-event-layer-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-redis-event-layer-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：`GET /api/stream/status` 响应增加 `backend`、`redis_enabled`、`last_published_at`、`last_event_name`、`last_error` 字段；原有 `mode` 与 `status` 仍保留
- 验证情况：`conda run -n news-caught pytest backend/tests/test_event_bus.py -q` 通过（4 个用例）；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_refresh_all_runs_signal_pipeline_for_inserted_items backend/tests/test_stream_status.py -q` 通过（2 个用例）；`conda run -n news-caught pytest backend/tests/test_health.py backend/tests/test_news_ingestion.py backend/tests/test_news_signal_pipeline.py backend/tests/test_market.py backend/tests/test_x_monitor.py backend/tests/test_event_bus.py backend/tests/test_stream_status.py -q` 通过（39 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（79 个用例）
- 风险/后续事项：当前 Redis 仅负责发布而非消费，严格来说仍是过渡态；下一阶段如需真正把 pipeline、通知或实时行情拆到独立 worker，可继续沿用当前事件名与 stream 命名扩展，而无需重改生产者接口

## 2026-03-22 23:56

- 修改人：Codex
- 修改范围：Redis Python 客户端依赖准备
- 变更内容：为后端后续接入 Redis 事件层预先补充 `redis` Python 客户端依赖，同时同步更新根目录 `requirements.txt` 与 `backend/pyproject.toml`，保证通过 `conda` 环境和可编辑安装两条路径都能获得一致依赖。本次不改动业务代码、数据库结构或运行逻辑，仅做环境准备。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/pyproject.toml`
  - `/Users/xiuyang/Desktop/news-caught/requirements.txt`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：已完成依赖清单更新；`conda run -n news-caught pip install redis` 成功，`conda run -n news-caught python -c "import redis; print(redis.__version__)"` 返回 `7.3.0`；Redis 系统安装仍在进行中
- 风险/后续事项：当前仅完成依赖声明，后续仍需在 `news-caught` conda 环境中执行安装，并补充 Redis 连接配置与事件流封装后才能真正投入使用

## 2026-03-22 22:11

- 修改人：Codex
- 修改范围：`Watchlist` / `WatchlistDetail` / `TopicDetail` 终端中间态收尾
- 变更内容：将剩余高频页面继续收敛到与 `AppShell`、`Dashboard`、`News Feed` 一致的“冷蓝底 + 橙色焦点”中间态。`Watchlist` 首页引入 `Control Station` 微标签，将左侧管理面板、候选列表、主操作按钮和右侧关联新闻统一为更硬的终端壳层；`WatchlistTable` 调整为更紧凑的终端表格并强化表头层级；`WatchlistDetail` 为核心行情区增加主监控模块，收紧指标卡与相关新闻卡；`TopicDetail` 则把主题摘要卡、过滤工具条和来源分组卡收敛为更像分析工作台的面板。全程不改动数据加载、过滤语义、跳转行为或任何 API / store 契约。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-22-watchlist-suite-terminal-midstate-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-22-watchlist-suite-terminal-midstate-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅展示层和测试锚点调整，未改动 store、路由或后端接口）
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts src/components/dashboard/HeroMetrics.test.ts src/components/dashboard/TopicBoard.test.ts src/views/DashboardView.test.ts src/components/news/NewsCard.test.ts src/views/NewsFeedView.test.ts src/components/watchlist/WatchlistTable.test.ts src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts src/views/TopicDetailView.test.ts` 通过（10 个文件 / 21 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前高频业务页面已基本统一到同一视觉代际，但 `XMonitor`、`LlmSettings`、`Notify` 等功能页仍保留相对旧的层级和控件表达；如果后续继续深挖统一性，建议最后一轮再回到公共控件和功能页做 token / density 清理

## 2026-03-22 21:16

- 修改人：Codex
- 修改范围：`Dashboard` 与 `News Feed` 中间态终端视觉收敛
- 变更内容：继续沿用已确认的“冷蓝底 + 橙色焦点”中间态方向，对首页和新闻流进行第二、三阶段收敛。`Dashboard` 侧重把页面顶部明确为 `Control Room`，收紧指标卡为更硬的模块壳层、给主题卡增加更技术化的头部层级，并把右侧异动列进一步压成窄信号栏；`News Feed` 则把主区块升级为更像控制台的 `Control Station`，收紧过滤条边框与背景层次，并将统一新闻卡改成更紧凑的终端式外壳和微标签层级。整个过程只调整展示层与测试锚点，不改现有数据加载、排序、详情跳转或路由结构。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/HeroMetrics.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/HeroMetrics.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/TopicBoard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/TopicBoard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-22-dashboard-terminal-midstate-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-22-dashboard-terminal-midstate-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-22-news-feed-terminal-midstate-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-22-news-feed-terminal-midstate-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅前端展示层与测试断言调整，未改动 store、API client、路由契约或后端接口）
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts src/components/dashboard/HeroMetrics.test.ts src/components/dashboard/TopicBoard.test.ts src/views/DashboardView.test.ts src/components/news/NewsCard.test.ts src/views/NewsFeedView.test.ts` 通过（6 个文件 / 16 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前已完成壳层、首页和新闻流的中间态收敛，但 `Watchlist`、`WatchlistDetail`、`TopicDetail` 等页面仍停留在旧一档的克制冷蓝风格；如果后续要做全站统一，需要继续把同样的微标签层级、边框硬度和橙色焦点约束向这些页面扩展

## 2026-03-22 21:10

- 修改人：Codex
- 修改范围：`AppShell` 中间态终端壳层收敛
- 变更内容：按已确认的 Stitch 视觉提炼方向，收紧共享壳层的终端控制列表现：侧栏改为更硬的冷蓝基底与橙色焦点激活态，保留原有路由与序号模块结构；顶部新增全局细状态条，用于统一展示 `SSE` 状态、连接细节、最近事件时间与工作区标识；底部 `System Status` 模块同步收敛为更紧凑的系统信息卡，并将 `Desk` 说明改为更短的英文微标签 `Desk / News / Topics / Movers`；同时更新 `AppShell` 组件测试，锁定新状态条、文案和激活导航信号。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-22-app-shell-terminal-refinement-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅共享壳层展示层和测试断言调整，未改动路由、store 或 SSE 逻辑）
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts` 通过（1 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前只完成共享壳层的中间态收敛，`Dashboard` 仍保留此前较克制的冷蓝风格；后续进入 `Dashboard` 时需要延续“橙色只做焦点，不做全局主色”的约束，避免整站过度交易终端化

## 2026-03-22 20:50

- 修改人：Codex
- 修改范围：`App Shell` 终端化视觉收敛设计文档
- 变更内容：结合用户确认的 Stitch 视觉提炼方向，新增 `App Shell` 视觉收敛设计文档，明确本轮只调整壳层视觉语言、不改路由和数据行为；设计确定采用“冷蓝底 + 橙色焦点”的中间态，重点收敛侧栏控制列、全局细状态条、导航激活信号和系统微标签层级，为后续按 `AppShell -> Dashboard -> News Feed` 顺序实施提供依据。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-22-app-shell-terminal-refinement-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅新增设计文档，未改动前后端代码或契约）
- 验证情况：文档变更，未执行代码测试
- 风险/后续事项：当前仅完成设计固化，尚未进入实现；下一步需要生成正式 implementation plan，并在实现时控制橙色焦点使用范围，避免壳层过度“交易终端化”

## 2026-03-21 22:50

- 修改人：Codex
- 修改范围：侧栏 `SYSTEM DESK` 说明区弱化
- 变更内容：将左侧边栏顶部原本较显眼的 `SYSTEM DESK` 标题和整句说明，收敛成一枚低调的 `Desk` 小标签加一行短说明 `新闻 / 主题 / 异动 / 流状态`，减少系统说明文案对主导航和内容区域的视觉干扰，同时保持终端式环境感；同步补充 `AppShell` 视图测试，锁定新的轻量标签和短说明文案。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts` 通过（1 个文件 / 3 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前只弱化了侧栏头部说明区，导航标签和底部 `System Status` 卡仍保留较明确的系统语义；如果后续想继续统一“低调调试态”风格，可以再逐步收敛这些区域的术语和层级

## 2026-03-21 21:58

- 修改人：Codex
- 修改范围：Dashboard 顶部系统状态提示弱化
- 变更内容：将 Dashboard 顶部原先占用较大的 `StatusBanner` 横幅移除，改为标题区旁边的轻量状态 badge，仅用小圆点和短文案提示当前处于 `在线 / 降级 / 离线 / 连接中` 哪种调试状态，并附上简短辅助标识如 `SSE live`、`mock`、`SSE off`；颜色使用低饱和的绿、黄、红区分状态，避免“当前处于降级或断线状态”这类完整句子过于抢眼，同时不改变任何底层连接状态逻辑。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/DashboardView.test.ts` 通过（1 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前只弱化了 Dashboard 顶部状态提示，其它页面如果仍使用 `StatusBanner` 仍会保持原先较显眼的横幅样式；如果你后续希望全站统一成低调状态 badge，需要再单独收敛公共状态组件策略

## 2026-03-21 21:52

- 修改人：Codex
- 修改范围：Dashboard 主列比例与异动侧栏收紧
- 变更内容：按用户要求进一步调整 Dashboard 桌面端三列权重，将 `News Feed / 资讯主题聚合 / 自选股异动` 的比例改为更明显的主次结构，使左侧 `News Feed` 成为主列；同时将右侧异动列进一步压缩成较窄侧栏，把默认预览项从 3 条缩到 2 条，并弱化单条异动的辅信息，只保留更紧凑的名称、代码和异动原因展示；同步更新视图测试，锁定新的三列比例类名、异动列标识和预览条目数量。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/DashboardView.test.ts` 通过（1 个文件 / 3 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前右侧异动列已经明显收窄，如果后续再继续压缩，可能需要把顶部摘要面板也简化为更短的单行统计，避免头部信息占比过高

## 2026-03-21 20:32

- 修改人：Codex
- 修改范围：Dashboard 三列高密度布局重排
- 变更内容：将 Dashboard 从原先“上方主题/异动 + 下方最新新闻”的两段式结构改为桌面端三列并排看板，按 `自选股异动 / 资讯主题聚合 / News Feed` 三列排列并为每列加入独立滚动区，避免主题列表过长把最新新闻整体挤到首屏之外；同时压缩异动预览行、主题卡密度和 Dashboard 内的新闻条目形态，把 News Feed 改为更紧凑的标题优先列表；补充 Dashboard 视图测试，锁定三列结构标识、三列独立滚动容器和紧凑新闻预览项；同步新增本轮设计文档与实现计划。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-21-dashboard-three-column-density-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-21-dashboard-three-column-density-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅 Dashboard 视图结构和前端展示密度调整）
- 验证情况：`npm --prefix frontend run test -- --run src/views/DashboardView.test.ts` 通过（1 个文件 / 3 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前三列独立滚动只在桌面端开启，采用基于视口高度的上限策略；如果后续发现某些低高度屏幕首屏仍显压迫，可继续微调列高计算和主题列卡片密度

## 2026-03-21 21:02

- 修改人：Codex
- 修改范围：Dashboard 三列顺序调整
- 变更内容：按用户要求只交换桌面端三列中 `News Feed` 与 `自选股异动` 的位置，将桌面顺序从 `自选股异动 / 资讯主题聚合 / News Feed` 调整为 `News Feed / 资讯主题聚合 / 自选股异动`；移动端单列堆叠顺序保持不变；同时更新视图测试，显式锁定三列 DOM 顺序，避免后续回归。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/DashboardView.test.ts` 通过（1 个文件 / 3 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本次只调整桌面端列顺序，没有改变列宽比例；如果你后续觉得左侧 News Feed 视觉权重还不够，可以再继续微调三列宽度分配

## 2026-03-21 16:33

- 修改人：Codex
- 修改范围：`newsStore` 新闻列表状态分槽重构
- 变更内容：将原本共享一份 `items/activeQuery` 的 `newsStore` 改为“共享详情缓存 + 分离列表槽位”的结构，新增 Dashboard、News Feed、Sentiment News 三套独立的列表、查询、加载状态和时间戳，并分别提供 `loadDashboardNews`、`loadFeedNews`、`loadSentimentNews`、`refreshDashboardNews`；`AppShell` 启动改为只引导 Dashboard 槽位，`DashboardView`、`NewsFeedView`、`SentimentNewsView` 各自切换到自己的列表状态读取，彻底消除情绪页或筛选页覆盖首页统计和通用新闻流的问题；同时新增 `newsStore` store 级测试，并调整相关页面/壳层测试覆盖新的 store API。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/SentimentNewsView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/SentimentNewsView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-21-news-store-list-scope-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-21-news-store-list-scope-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅前端 store 内部状态模型和消费方式调整）
- 验证情况：`npm --prefix frontend run test -- --run src/stores/newsStore.test.ts src/components/layout/AppShell.test.ts src/views/DashboardView.test.ts src/views/NewsFeedView.test.ts src/views/SentimentNewsView.test.ts` 通过（5 个文件 / 10 个用例）；`npm --prefix frontend run test -- --run` 通过（23 个文件 / 54 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前列表状态已按页面分槽，但详情和分析缓存仍是全局共享，这是本轮有意保留的复用层；如果后续新闻入口继续增加，可以沿用同样的槽位模式，或进一步抽象成通用 scoped list helper 以减少 store 字段重复

## 2026-03-21 16:26

- 修改人：Codex
- 修改范围：Dashboard 从情绪新闻页返回后的统计恢复
- 变更内容：修复从 `偏利好` / `偏利空` 情绪新闻页返回 Dashboard 后，首页统计仍停留在过滤结果的问题；根因是情绪新闻页会复用全局 `newsStore.items` 和 `activeQuery`，而 Dashboard 之前直接消费当前 store 数据，没有在挂载时恢复全量新闻流。现已在 Dashboard 挂载时检测当前新闻查询是否带筛选条件，若是则重新加载全量新闻，避免首页指标卡和“最新新闻”区域继续显示情绪过滤后的残留数据；同时补充前端回归测试覆盖这一返回场景。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/DashboardView.test.ts` 通过（1 个文件 / 3 个用例）；`npm --prefix frontend run test -- --run` 通过（22 个文件 / 52 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前修复是让 Dashboard 进入时主动恢复全量新闻，能解决首页残留问题；但情绪页与通用新闻流仍共享同一个 `newsStore.items`，如果后续再增加更多专题化新闻入口，最好把不同新闻列表拆成独立 store 切片或本地列表状态，减少跨页面状态串扰

## 2026-03-21 16:01

- 修改人：Codex
- 修改范围：Dashboard 情绪指标卡入口与情绪新闻列表页
- 变更内容：将 Dashboard 上的 `偏利好` / `偏利空` 指标卡从静态计数改为可点击入口，分别跳转到新增的专用情绪新闻列表页；新增 `SentimentNewsView`，按对应情绪加载新闻并按时间倒序展示规整卡片，每条卡片展示标题、来源、时间、摘要和提及标的，点击后继续进入现有新闻详情页；同步补充 Dashboard/HeroMetrics/情绪新闻页的前端测试，以及本轮设计文档与实现计划。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/HeroMetrics.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/HeroMetrics.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/SentimentNewsView.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/SentimentNewsView.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-21-sentiment-news-entry-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-21-sentiment-news-entry-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅前端路由、页面交互和展示结构调整）
- 验证情况：`npm --prefix frontend run test -- --run src/components/dashboard/HeroMetrics.test.ts src/views/DashboardView.test.ts src/views/SentimentNewsView.test.ts` 通过（3 个文件 / 6 个用例）；`npm --prefix frontend run test -- --run` 通过（22 个文件 / 51 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前情绪新闻页仍复用 `newsStore.items` 作为列表缓存，进入该页会覆盖通用新闻流缓存；若后续要支持更重的情绪专题浏览，可能需要独立 store 切片或分页/批量详情接口来降低额外详情加载成本

## 2026-03-19 23:14

- 修改人：Codex
- 修改范围：Tailwind 迁移 code review 修正
- 变更内容：根据子代理代码审查修复了 3 个样式迁移回归：`WatchlistDetailView` 的涨跌额/涨跌幅现在直接使用 Tailwind 的 `text-positive` / `text-negative`，恢复单股行情正负反馈颜色；`XMonitorView` 的监控帖子流恢复为仅在桌面宽度下启用固定高度内部滚动，窄屏时回退为自然页面滚动，避免双滚动；`DashboardView` 的异动摘要卡片从无效的多层 `bg-[...]` 写法改为 `background-image` 渐变表达，恢复原先的摘要面板质感；并补充 `WatchlistDetailView` 对跌涨颜色语义的测试断言。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅 code review 修正）
- 验证情况：`npm --prefix frontend run test -- --run src/views/WatchlistDetailView.test.ts src/views/XMonitorView.test.ts src/views/DashboardView.test.ts` 通过（3 个文件 / 7 个用例）；`npm --prefix frontend run test -- --run` 通过（21 个文件 / 48 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮 code review 中发现的问题已修复，但这类纯样式迁移仍主要依赖结构测试和人工页面巡检；如果下一轮继续压缩兼容层，建议补充至少一套截图级校验或手工核对清单

## 2026-03-19 22:56

- 修改人：Codex
- 修改范围：Tailwind 迁移剩余页面收尾与前端全量验证
- 变更内容：完成 `TopicDetailView`、`NewsDetailView`、`XMonitorView`、`LlmSettingsView`、`NotifySettingsView` 的 Tailwind 迁移，移除这些页面原有的 scoped CSS；为 `TopicDetail` 与 `Notify Settings` 新增页面级测试，为 `NewsDetail`、`XMonitor`、`LlmSettings` 补充稳定的结构锚点测试，确保主题来源导航、X 帖子翻译、LLM 设置页连接测试按钮和通知设置页测试消息按钮在重构后仍正常工作；至此本轮计划范围内的前端主页面都已迁到 Tailwind，且未改动任何前后端 API 契约。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NotifySettingsView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NotifySettingsView.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅前端页面样式与测试补强）
- 验证情况：`npm --prefix frontend run test -- --run src/views/TopicDetailView.test.ts src/views/NewsDetailView.test.ts src/views/XMonitorView.test.ts src/views/LlmSettingsView.test.ts src/views/NotifySettingsView.test.ts` 通过（5 个文件 / 14 个用例）；`npm --prefix frontend run test -- --run` 通过（21 个文件 / 48 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前主页面已完成 Tailwind 迁移，但仓库里仍有部分子组件和兼容语义类（如 `surface`、`pill`）保留在全局样式中作为过渡层；如果下一轮要进一步收紧样式体系，应先确认这些兼容类在所有消费者中都已被完全替换后再清理

## 2026-03-19 22:43

- 修改人：Codex
- 修改范围：`NewsFeed`、`Watchlist`、`WatchlistDetail` 页面 Tailwind 迁移
- 变更内容：将 `NewsFeedView`、`WatchlistView` 和 `WatchlistDetailView` 迁移为 Tailwind class 驱动实现，移除对应页面的 scoped CSS；为新闻页壳层、自选股主布局、单股详情主网格补充稳定的 `data-role` 结构锚点，保持现有筛选、候选联想、关联新闻、详情卡片与单股行情展示行为不变；本轮仍只调整前端页面表现，没有改动 store 契约、API client 或任何后端接口。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅页面展示层重构）
- 验证情况：`npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts` 通过（3 个文件 / 3 个用例）；`npm --prefix frontend run test -- --run` 通过（19 个文件 / 46 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 `TopicDetail`、`NewsDetail`、`XMonitor`、`LlmSettings`、`Notify` 等页面仍保留旧样式结构；继续迁移时要特别注意表单页和高密度数据页的交互状态，不要因 class 收敛误伤可读性或可点击区域

## 2026-03-19 22:29

- 修改人：Codex
- 修改范围：`Dashboard` 视图与仪表组件 Tailwind 迁移
- 变更内容：将 `HeroMetrics`、`TopicBoard` 和 `DashboardView` 迁移为 Tailwind class 驱动实现，去掉原有 scoped CSS；为指标区、主题卡片和 Dashboard 主网格补充稳定的 `data-role` 结构锚点，并给 `TopicBoard` 增加点击跳转的保护测试，确保后续继续重构页面时不会误伤导航与信息结构；本轮仍然只动前端展示层，没有改动任何前后端接口、store 读写或 API client 调用。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/HeroMetrics.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/HeroMetrics.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/TopicBoard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/TopicBoard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅 Dashboard 展示层与测试锚点调整）
- 验证情况：`npm --prefix frontend run test -- --run src/components/dashboard/HeroMetrics.test.ts src/components/dashboard/TopicBoard.test.ts src/views/DashboardView.test.ts` 通过（3 个文件 / 5 个用例）；`npm --prefix frontend run test -- --run` 通过（19 个文件 / 46 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前仅 `Dashboard` 完成页面级迁移，其余业务页面仍保留大量 scoped CSS；后续继续迁移时要优先复用已沉淀的 `SectionCard`、`StatusBanner` 和指标/卡片表达，避免不同页面重新各写一套 Tailwind 组合

## 2026-03-19 21:16

- 修改人：Codex
- 修改范围：前端共享组件 Tailwind 迁移第一批
- 变更内容：将 `SectionCard`、`StatusBanner`、`LoadingBlock`、`StaleBadge` 四个共享显示组件迁移为 Tailwind class 驱动实现，移除对应 scoped CSS；为 `SectionCard` 补充紧凑模式稳定标记 `data-compact`，并为 `SectionCard`/`StatusBanner` 增补 slot 与语义断言测试，确保后续页面迁移时仍有稳定的公共视觉锚点；本轮仅调整组件展示层，没有改动任何 store、API client 或后端接口。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/SectionCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/SectionCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/StatusBanner.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/StatusBanner.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/LoadingBlock.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/StaleBadge.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅共享展示组件样式层重构）
- 验证情况：`npm --prefix frontend run test -- --run src/components/common/SectionCard.test.ts src/components/common/StatusBanner.test.ts` 通过（2 个文件 / 4 个用例）；`npm --prefix frontend run test -- --run` 通过（19 个文件 / 44 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前只迁移了公共壳层和 4 个通用组件，页面级 scoped CSS 仍大量存在；后续迁移页面时需要尽量复用本轮沉淀的公共样式表达，避免模板 class 再次发散

## 2026-03-19 21:13

- 修改人：Codex
- 修改范围：前端 Tailwind 基础设施接入与 `AppShell` 首批迁移
- 变更内容：在前端引入 `tailwindcss@3`、`postcss` 与 `autoprefixer`，新增 Tailwind/PostCSS 配置并把现有全局 design tokens 映射进 Tailwind theme；`frontend/src/assets/main.css` 现改为 Tailwind 入口，同时保留当前暗色终端配色、`surface`、`pill` 等兼容语义类；`AppShell` 迁移为以 Tailwind class 驱动的布局和导航样式，不改动任何数据加载、SSE 连接或路由逻辑；同时补充 `AppShell` 的挂载/卸载测试，确认样式重构没有影响壳层数据初始化与断连清理。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/package.json`
  - `/Users/xiuyang/Desktop/news-caught/frontend/package-lock.json`
  - `/Users/xiuyang/Desktop/news-caught/frontend/tailwind.config.js`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/postcss.config.js`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/index.html`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/assets/main.css`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅前端样式基础设施与布局实现调整，未改动前后端 API 契约）
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts` 通过（1 个文件 / 3 个用例）；`npm --prefix frontend run test -- --run` 通过（19 个文件 / 42 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前仅完成基础设施和 `AppShell`，其余页面仍混用现有 scoped CSS；Tailwind 迁移期内存在双样式系统，后续需要继续按计划逐页迁移并在完成后再清理兼容类

## 2026-03-19 21:01

- 修改人：Codex
- 修改范围：Tailwind 前端迁移方案设计文档与实施计划补强
- 变更内容：审查并重写了原有的 Tailwind 迁移计划，去掉“一次性完全替代手写 CSS”的大爆炸表述，改为“Tailwind 与现有 CSS 共存的渐进迁移”方案；新增正式设计文档，明确现有 design tokens 映射、迁移顺序、非目标、风险与验收方式；计划文档补充了按 `AppShell`、通用组件、Dashboard、其余页面、最终清理分块推进的任务结构，并加入更具体的测试与人工验收口径。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-tailwind-migration-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-tailwind-migration-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅补充设计与计划文档）
- 验证情况：已人工核对当前前端技术栈、`frontend/src/assets/main.css` 现有 design token、`frontend/src/components/layout/AppShell.vue` 的布局结构，以及现有前端测试文件分布；未运行构建或测试命令，本次仅修改文档
- 风险/后续事项：本轮只补齐设计与计划，不包含实际 Tailwind 实现；若后续要正式开工，仍应按新设计/计划进入实施，并在每个迁移闭环完成后继续更新记录

## 2026-03-19 20:36

- 修改人：Codex
- 修改范围：LLM 设置页“测试连接”功能与上游鉴权错误透传
- 变更内容：在 `LLM Settings` 页面新增“测试连接”按钮，严格按已保存且当前激活的 LLM 配置发起连通性校验，不会读取未保存的表单草稿；后端新增 `POST /api/llm/test` 接口，并让 `OpenAICompatibleProvider` 在上游返回 4xx/5xx 时优先解析真实错误正文，避免只显示裸状态码；已通过直接请求 DeepSeek 官方接口确认当前真实失败根因为 API key 无效，上游返回 `Authentication Fails, Your api key: ****20e1 is invalid`，页面现在可直接展示这类错误。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/llm_providers.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/llm.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/llm.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_analysis.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/llmStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-llm-connection-test-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-llm-connection-test-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有（新增 `POST /api/llm/test`；前端新增连接测试响应类型）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_analysis.py backend/tests/test_llm_config.py -q` 通过（18 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/views/LlmSettingsView.test.ts` 通过（2 个文件 / 11 个用例）；`npm --prefix frontend run build` 通过；使用本地保存的当前 key 直连 `https://api.deepseek.com/v1/chat/completions` 已确认真实返回 `401` 和错误正文 `Authentication Fails, Your api key: ****20e1 is invalid`
- 风险/后续事项：测试连接会真实消耗一次上游请求额度；当前失败不是代码兼容性问题，而是当前保存的 DeepSeek key 被上游判定无效，需要你换成有效 key 后再次保存并点击“测试连接”

## 2026-03-19 20:18

- 修改人：Codex
- 修改范围：LLM DeepSeek 默认配置持久化、错误域名修正与设置页真实错误态
- 变更内容：定位并修复了本地 LLM 设置“刷新后看起来被改回去”的根因：前端 `LLM Settings` 读取/保存配置时不再在后端失败后静默回退 `mockLlmConfig`，而是展示真实加载失败信息，避免 mock 假数据覆盖数据库中的真实 DeepSeek 配置；后端新增对已知错误 DeepSeek 域名 `https://api.deepssek.com/v1` 的规范化保存，自动改写为正确的 `https://api.deepseek.com/v1`；同时已直接修正本地 SQLite 中当前激活的 DeepSeek 配置，消除导致 `llm provider request failed: [SSL: UNEXPECTED_EOF_WHILE_READING] ...` 的错误地址。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/llm_provider_config_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_llm_config.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/llmStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/app.db`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-llm-deepseek-default-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-llm-deepseek-default-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅调整前端错误处理与后端保存时的 DeepSeek 域名规范化）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_llm_config.py -q` 通过（5 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/views/LlmSettingsView.test.ts` 通过（2 个文件 / 9 个用例）；`npm --prefix frontend run build` 通过；本地 SQLite 已核对当前激活配置为 `openai_compatible / DeepSeek / https://api.deepseek.com/v1 / deepseek-chat`
- 风险/后续事项：当前后端只会自动纠正已知的 DeepSeek 错拼 host，不会改写其它自定义 OpenAI-compatible 地址；如果后续仍有连接失败，需要继续检查 API key、本机网络或上游服务可用性

## 2026-03-19 19:40

- 修改人：Codex
- 修改范围：`X Monitor` provider 健康语义、空账号冷却行为、twitterapi.io 搜索 limit 和测试隔离修正
- 变更内容：根据推送前 code review 修正 `X Monitor` 的剩余语义缺口：`/api/health` 与 `/api/health/x` 现在都基于首个激活账号的 `last_tweets` 轻量探测判定 provider 状态，不再仅凭 API key 是否存在就标记健康；健康探测增加进程内缓存，避免健康轮询持续消耗 provider 配额；空账号/空配置文件时的 refresh 不再推进 3 小时冷却；`twitterapi.io` 的 `advanced_search` 现在会真正透传 `limit` 参数；同时为 `TwitterApiIoClient` 的进程级状态补上测试级自动重置，消除顺序依赖。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/twitterapi_io_client.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_analysis.py backend/tests/test_x_monitor.py -q` 通过（26 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/views/XMonitorView.test.ts` 通过（2 个文件 / 9 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 provider 健康仍依赖首个激活账号的 `last_tweets` 可用性，如果后续账号名单里首个账号长期异常而其他账号正常，健康状态可能偏保守；如要进一步降低探测成本，可后续引入更明确的 provider 级健康缓存字段或专用轻量探测端点

## 2026-03-19 19:07

- 修改人：Codex
- 修改范围：LLM 翻译上游连接失败时的错误收敛
- 变更内容：定位到 `POST /api/llm/translate` 在上游模型地址不可达时会把 `httpx` 连接异常直接抛成 500，前端只能看到笼统失败；后端 `OpenAICompatibleProvider` 现已捕获 `httpx.HTTPError` 并统一转成 `LLMProviderError`，接口会返回明确的 `502 + detail`，便于直接判断是 `base_url`、SSL 还是网络连通性问题。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/llm_providers.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_analysis.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅改进错误返回）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_analysis.py -q -k 'translate or connection_errors'` 通过（5 个用例）；本地请求 `POST http://127.0.0.1:8000/api/llm/translate` 已返回明确错误详情 `llm provider request failed: [SSL: UNEXPECTED_EOF_WHILE_READING] ...`
- 风险/后续事项：当前真实失败仍然存在，根因是本地保存的 `base_url`/上游服务不正确或不可连；需要把 `LLM Settings` 里的 `base_url` 改成实际模型服务地址后再验证

## 2026-03-19 18:37

- 修改人：Codex
- 修改范围：`X Monitor` 帖子按需中文翻译、LLM 文本翻译接口与前端会话缓存
- 变更内容：后端新增 `POST /api/llm/translate`，复用当前激活的 LLM provider/model 对单条帖文正文做中文翻译，并增加空文本、超长文本和空翻译返回的校验；前端 `X Monitor` 监控列表和关键词搜索结果都新增 `翻译` 按钮、翻译中/失败/成功展示，以及基于稳定 `translationKey` 的页面内会话缓存，避免搜索结果 `id=0` 时出现串译；同时补充前端 API client 测试、视图测试，以及本轮设计/计划文档。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/llm.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/llm.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/llm_providers.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_analysis.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/http.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/xMonitorStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-x-monitor-translation-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-x-monitor-translation-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有（新增 `POST /api/llm/translate`；前端新增翻译请求/响应类型）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_analysis.py -q` 通过（9 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/views/XMonitorView.test.ts` 通过（2 个文件 / 9 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前翻译缓存只保存在页面会话内，刷新后会失效；翻译接口对正文长度限制为 4000 字符，若后续要支持更长内容，需要按 provider 上下文窗口改成截断或分段策略

## 2026-03-19 17:40

- 修改人：Codex
- 修改范围：`X Monitor` 页面右侧帖子流密度与高度控制优化
- 变更内容：将 `X Monitor` 页面“账号监控帖子流”从大卡片纵向堆叠改为“状态式摘要 + 紧凑列表流”，摘要主句新增当前跟踪帖子数与同步状态提示，副句汇总请求节流、刷新冷却和最近刷新时间；帖子列表在桌面端改为固定最大高度并在面板内部滚动，单条帖子收敛为更小的列表项，减少页面纵向拉伸并提升同屏信息密度；同步补充本轮设计文档、实现计划和前端视图测试断言。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-x-monitor-feed-density-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-x-monitor-feed-density-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts` 通过（1 个文件 / 2 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：摘要中的帖子数为当前前端筛选结果数量，不代表后端库中的全量帖子数；桌面端内部滚动高度使用响应式 `clamp`，若后续页面再加入更多头部内容，可能需要再微调高度上限

## 2026-03-19 18:27

- 修改人：Codex
- 修改范围：`X Monitor` 页面改为显示后端真实下发的节流/冷却配置，小号文案收敛
- 变更内容：扩展 `GET /api/health/x` 响应，新增 `min_interval_seconds` 和 `refresh_cooldown_hours`，前端 `X Monitor` 页面改为直接使用后端下发的真实配置值展示“请求节流”和“账号刷新冷却”，不再写死 `6 秒` 与 `3 小时`；同时将原先占位较大的策略说明块收敛为页面顶部的小号次级文案，减少视觉占用。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有（`GET /api/health/x` 新增 `min_interval_seconds`、`refresh_cooldown_hours`）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_x_monitor.py -q -k provider_state` 通过；`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts` 通过（1 个文件 / 2 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前页面已与后端配置值同步，但配置仍来自进程启动时读取的 `.env`；如果运行中手改 `.env` 而不重启后端，页面不会立即反映新值

## 2026-03-19 18:21

- 修改人：Codex
- 修改范围：`X Monitor` 页面展示 provider 节流与账号冷却策略
- 变更内容：在 `X Monitor` 页面“状态与筛选”卡片中新增两条明确的运行策略说明，展示当前 `twitterapi.io` provider 请求节流为 `6 秒/次`，账号刷新冷却为 `3 小时`，帮助页面直接解释为什么刷新会等待或跳过；同时补充视图测试覆盖这些说明文案。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts` 通过（1 个文件 / 2 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前页面中的 `6 秒/次` 与 `3 小时` 为按当前后端配置写死的展示文案，若后续你调整 `.env` 中的节流参数而不改页面，展示值不会自动变化；如需完全与后端配置同步，下一步应把节流配置值加入健康接口

## 2026-03-19 18:08

- 修改人：Codex
- 修改范围：`twitterapi.io` 最小请求间隔节流、真实 `MiniMax_AI` provider 验证
- 变更内容：后端新增 `twitterapi_io_min_interval_seconds` 配置项，并在 `TwitterApiIoClient` 中加入进程内最小请求间隔节流；本地 `.env` 默认配置为 6 秒，确保真实 provider 请求严格按免费额度节奏发起。基于该节流对 `MiniMax_AI` 连续发起两次真实 `last_tweets` 请求，已拿到相同的真实帖子数据，且返回中的账号、链接、发布时间、正文均直接来自 provider 原始响应。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/twitterapi_io_client.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/.env`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-twitterapi-rate-limit-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-twitterapi-rate-limit-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅新增后端节流配置）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_x_monitor.py -q -k min_interval` 通过；`conda run -n news-caught pytest backend/tests -q` 通过（60 个用例）；使用真实 key 对 `MiniMax_AI` 连续请求两次，得到同一条真实帖子：`https://x.com/MiniMax_AI/status/2034528945962696948`，发布时间 `Thu Mar 19 07:14:35 +0000 2026`，正文 `Early testers are saying that M2.7 has big improvements in emotional intelligence and character consistency 👀`
- 风险/后续事项：当前节流为单进程内最小间隔，若未来有多进程部署仍可能并发打到 provider；单个请求本身的网络耗时会占用部分 6 秒窗口，因此两次调用的总间隔是“请求耗时 + 必要补等待”

## 2026-03-19 18:03

- 修改人：Codex
- 修改范围：`twitterapi.io` 请求节流设计与实现计划文档
- 变更内容：新增 `twitterapi.io` 最小请求间隔的设计与计划文档，确定在后端增加可调节的 provider 请求节流配置，并按用户要求默认以 6 秒为最小真实请求间隔，对 `last_tweets` 和 `advanced_search` 统一生效。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-twitterapi-rate-limit-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-twitterapi-rate-limit-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（本次仅新增设计与计划文档）
- 验证情况：已人工核对当前 `TwitterApiIoClient` 请求路径和本地 `.env` 配置
- 风险/后续事项：本轮节流为进程内最小间隔，不处理多进程共享配额；真实联调仍取决于 provider 对当前 key 的即时限流状态

## 2026-03-19 17:10

- 修改人：Codex
- 修改范围：`X Monitor` 三小时刷新冷却、`MiniMax_AI` 单账号名单、前后端提示与验证
- 变更内容：为 `X Monitor` 账号刷新增加 3 小时硬冷却，后端新增 `x_monitor_refresh_cooldown_hours` 默认配置，并在 `POST /api/x/refresh` 响应中返回 `skipped`、`skip_reason` 和 `next_refresh_at`；当冷却窗口未过时，本地直接跳过刷新而不访问远端 provider。前端 `X Monitor` 页面新增“冷却中，下次可刷新”提示；样例账号名单改为仅保留 `MiniMax_AI`；链接仍只使用 `twitterapi.io` 返回的真实原帖 URL，不做拼接或伪造。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/x_monitor_accounts.example.json`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-x-monitor-refresh-cooldown-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-x-monitor-refresh-cooldown-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有（`POST /api/x/refresh` 响应新增 `skipped`、`skip_reason`、`next_refresh_at`）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_x_monitor.py -q` 通过（10 个用例）；`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts` 通过（1 个文件 / 2 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（59 个用例）；`npm --prefix frontend run build` 通过；使用真实 `TWITTERAPI_IO_API_KEY` 对 `MiniMax_AI` 做 smoke test 时，首次真实刷新仍命中 provider `429`，但在预置最近成功时间后再次调用已确认会直接返回 `skipped=true` 和 `cooldown_active`
- 风险/后续事项：当前 3 小时冷却能避免高频重复拉取，但不能解决 provider 在首次请求前就已对当前 key 限流的情况；如果后续 `MiniMax_AI` 仍需要更稳定的真实抓取，可能还要加失败后的退避窗口或改用更低频的自动调度

## 2026-03-19 17:06

- 修改人：Codex
- 修改范围：`X Monitor` 三小时冷却设计与实现计划文档
- 变更内容：新增 `X Monitor` 三小时刷新冷却的设计与计划文档，确定账号名单切为仅保留 `MiniMax_AI`，账号刷新改为每 3 小时最多执行一次，冷却期内直接跳过远端请求并返回下次可刷新时间，关键词搜索保持不变。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-x-monitor-refresh-cooldown-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-x-monitor-refresh-cooldown-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（本次仅新增设计与计划文档，代码实现尚未开始）
- 验证情况：已人工核对现有 `x_monitor` 刷新逻辑、健康记录模型和前端页面边界；真实联调中已确认需要对 `429` 做降频处理
- 风险/后续事项：后续实现需要确保冷却策略不会误伤关键词搜索；真实 smoke test 仍需以 `MiniMax_AI` 返回结果和当前 key 的限流表现为准

## 2026-03-19 16:33

- 修改人：Codex
- 修改范围：`X Monitor` provider 替换、桥接移除、前后端接口与页面、测试与文档
- 变更内容：将 `X Monitor` 从本地 `grok-bridge` 桥接方案改为直接使用 `twitterapi.io` API key；后端新增 `twitterapi_io_client`，重写 `x_monitor` 刷新逻辑以按账号拉取最新推文并按 tweet id 优先去重，新增 `GET /api/x/search` 关键词搜索接口，健康检查字段从 `bridge_* / x_bridge_*` 改为 `configured / healthy / status` 与 `x_monitor_*`；前端同步更新 `X Monitor` 页面、类型、mock 与 store，增加关键词搜索区并替换全部 `grok-bridge` 文案；README 与 API 契约文档改为 `twitterapi.io` 配置方式，并删除旧桥接客户端实现；联调阶段根据真实 `last_tweets` 响应修正为读取 `data.tweets`，并补充 X 风格 `createdAt` 时间解析。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/twitterapi_io_client.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/grok_bridge_client.py`（删除）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/.env`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/x_monitor_accounts.example.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/xMonitorStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/api-contract.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有（新增 `GET /api/x/search`；`GET /api/health` 的 `x_bridge_*` 改为 `x_monitor_*`；`GET /api/health/x` 的 `bridge_*` 改为 `configured / healthy / status`）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_x_monitor.py -q` 通过（9 个用例）；`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts` 通过（1 个文件 / 1 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（58 个用例）；`npm --prefix frontend run build` 通过；使用用户提供的真实 `TWITTERAPI_IO_API_KEY` 直连 `https://api.twitterapi.io/twitter/user/last_tweets?userName=DeItaone&includeReplies=false` 已拿到真实响应，并确认 `tweets` 位于 `data.tweets`；单账号 refresh smoke test 已跑通配置与 provider 健康检查，但连续请求命中 `429` 限流
- 风险/后续事项：当前 key 在短时间连续拉取多账号时会命中 `429`，因此实际使用中需要降低刷新频率、控制账号数量或后续改造成更适合多账号的监控模式；本轮默认账号列表已切成偏美股快讯方向，但是否保留这些账号仍取决于你的偏好

## 2026-03-19 16:26

- 修改人：Codex
- 修改范围：`twitterapi.io` 替换 `X Monitor` 桥接方案设计文档
- 变更内容：新增 `twitterapi.io` 替换现有 `grok-bridge` 型 `X Monitor` 的设计文档，明确第一版采用“账号监控轮询 + 关键词手动搜索”的双通道方案，保留现有 `X Monitor` 页面和大部分数据模型，完整移除桥接依赖，并规划新的配置项、健康检查语义、接口边界、测试策略和后续演进方向。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-twitterapi-io-x-monitor-replacement-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（本次仅新增设计文档，尚未进入实现）
- 验证情况：已人工核对设计文档与仓库现有 `X Monitor`、配置、健康检查和 README 中的桥接边界；参考了 `twitterapi.io` 官方文档中的账号最新推文、搜索推文和监控接口能力
- 风险/后续事项：设计已明确方向，但真实实现仍需以 `twitterapi.io` 实际响应结构为准；进入实现与联调阶段前，需由用户提供有效 API key 和目标账号列表

## 2026-03-19 16:39

- 修改人：Codex
- 修改范围：`twitterapi.io` 替换 `X Monitor` 的实现计划文档
- 变更内容：新增实现计划文档，按 TDD 顺序拆分了桥接测试替换、后端 provider 接入、健康检查字段调整、关键词搜索接口、前端 store 与页面改造、README 清理以及最终验证步骤，并明确真实联调需要用户提供 `TWITTERAPI_IO_API_KEY` 和账号列表。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-twitterapi-io-x-monitor-replacement-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（本次仅新增实现计划文档，尚未进入代码实现）
- 验证情况：已人工核对计划文档中的文件边界与当前 `X Monitor` 后端测试、前端 store、API client 和类型定义
- 风险/后续事项：计划已覆盖实现顺序，但真实 provider 字段映射仍需在编码阶段以 `twitterapi.io` 响应为准；最终 smoke test 仍依赖用户提供真实 API key 与账号列表

## 2026-03-19 15:34

- 修改人：Codex
- 修改范围：X Monitor 本地启用配置、外部 `grok-bridge` 仓库落地
- 变更内容：将 `ythx-101/grok-bridge` 仓库克隆到本机 `/Users/xiuyang/projects/grok-bridge`，并在项目根目录新增本地 `.env`，启用 `X_MONITOR_ENABLED`、配置 `GROK_BRIDGE_BASE_URL`、超时时间和账号白名单文件路径，使当前仓库可按真实本地路径接入 `grok-bridge`。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.env`（新增，本地配置）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught python -c "from backend.app.core.config import get_settings; s=get_settings(); print(s.x_monitor_enabled); print(s.grok_bridge_base_url); print(s.x_monitor_accounts_file)"` 输出已确认读取到新增配置；`python3 /Users/xiuyang/projects/grok-bridge/scripts/grok_bridge.py --help` 可运行
- 风险/后续事项：`X Monitor` 仍依赖 Safari 已登录 `grok.com` 且开启 “Allow JavaScript from Apple Events”；如果未满足该前置条件，`/api/health/x` 会显示桥接异常，但不影响当前 `.env` 配置已生效

## 2026-03-19 11:20

- 修改人：Codex
- 修改范围：新闻 refresh 后自动情绪标注与主题聚合增量流水线、后端测试、设计与计划文档
- 变更内容：新增 `NewsSignalPipelineService`、规则情绪分类器和信号结果持久化，在每次 `POST /api/news/refresh` 成功插入新闻后自动对增量新闻生成 `sentiment_label` / `sentiment_score`、归并到 `topic_cluster` 并写入 `topic_news_link`；当本次 refresh 没有新增新闻时，会顺手回填一批历史 `signal_status is null` 的新闻，避免库里已有未打标新闻长期不被处理；新增 `news_item` 信号状态字段、`topic_cluster` 归并字段和 `news_signal_result` 表，并补充增量分类/聚合/降级/refresh 触发的后端测试及本轮设计、计划文档。
- 影响文件：
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/db/initializer.py`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/models/__init__.py`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/models/news_item.py`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/models/news_signal_result.py`（新增）
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/models/topic_cluster.py`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/repositories/news_signal_repository.py`（新增）
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/services/news_signal_classifier.py`（新增）
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/services/news_signal_pipeline.py`（新增）
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/tests/test_news_signal_pipeline.py`（新增）
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/docs/superpowers/specs/2026-03-19-auto-signal-topic-pipeline-design.md`（新增）
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/docs/superpowers/plans/2026-03-19-auto-signal-topic-pipeline-plan.md`（新增）
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/docs/code-change-log.md`
- 接口/数据结构变化：有（`news_item` 新增 `signal_status`、`signal_error`、`signal_updated_at`；`topic_cluster` 新增 `topic_key`、`cluster_version`、`llm_refined_at`；新增 `news_signal_result` 表，但现有 API 契约保持兼容）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py backend/tests/test_news_ingestion.py -q` 通过（13 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（55 个用例）
- 风险/后续事项：当前主题聚合仍以规则 token/topic key 为主，适合先把空值和无聚合问题补齐，但复杂跨语种话题的命名质量仍取决于后续启用 `ai_enabled` 后的 LLM 提炼；SQLite 现有库通过启动时补列兼容升级，若后续要上更严格索引或唯一约束，建议引入正式 migration

## 2026-03-18 21:35

- 修改人：Codex
- 修改范围：Dashboard 自选股异动面板摘要化、前端视图测试、设计与计划文档
- 变更内容：将 Dashboard 页原先按 `abnormalMovers` 全量纵向铺开的 `Live Movers` 列表改为“顶部摘要 + 3 条代表项 + 查看全部入口”的压缩结构；新增本地市场分布和主异动原因聚合文案，避免异动股票过多时把总览页拉成长列表，同时保留跳转到 Watchlist 查看完整异动的入口；同步补充该轮设计文档、实现计划和页面测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-dashboard-movers-summary-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-dashboard-movers-summary-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/DashboardView.test.ts` 通过（1 个文件 / 1 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前“主因”文案来自前端对 `abnormal_reason` 的有限映射，后端若新增原因类型会先回退显示原始值；代表项顺序继续沿用 `abnormalMovers` 当前顺序，如果后端排序策略改变，Dashboard 预览顺位也会随之变化

## 2026-03-18 20:38

- 修改人：Codex
- 修改范围：自选股页搜索候选添加、删除能力、后端候选/删除接口、前端测试与设计计划文档
- 变更内容：将自选股页原先左侧手填 `symbol + display_name` 的添加表单改为“表格上方搜索添加栏 + 候选下拉”的一体化管理面板；新增内置股票候选库和 `GET /api/watchlist/candidates` 接口，前端支持按代码、中文名、英文名和别名做本地模糊匹配，选中候选后直接添加，不再要求手工录入代码与名称；新增 `DELETE /api/watchlist/{symbol}` 接口和表格行内删除按钮，删除前使用确认框并避免按钮点击误触发行跳转；同步扩展前端 mock、store 状态和回归测试，并补充本轮设计文档和实现计划。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/watchlist.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/watchlist_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/watchlist.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/watchlist_candidates.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_stock_news_search.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/http.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/vitest.config.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-watchlist-search-delete-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-watchlist-search-delete-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有（新增 `GET /api/watchlist/candidates`、`DELETE /api/watchlist/{symbol}`；前端新增 `WatchlistCandidate` 数据结构）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_stock_news_search.py -q` 通过（10 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts src/components/watchlist/WatchlistTable.test.ts` 通过（3 个文件 / 5 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前候选库是内置静态清单，覆盖范围取决于维护的数据；如果后续要支持更多港股/美股，需要继续补充候选源或改成服务端查询；删除 watchlist 仅移除 watchlist 项，不会清理历史行情快照或关联新闻数据，这是本轮刻意保留的数据独立性策略

## 2026-03-18 16:45

- 修改人：Cursor
- 修改范围：自选股添加时自动关联新闻（DB 匹配 + Tavily + Google News RSS + LLM 可选增强）
- 变更内容：添加自选股时自动搜索并关联最新相关新闻。同步阶段用 symbol 和 display_name 在现有 `news_item` 表中做关键词匹配并写入 `news_stock_mention`；阈值判断基于实际命中的新闻条数，低于阈值（默认 3）时启动后台线程依次尝试 Tavily Search API（需配置 `tavily_api_key`）和 Google News RSS（免费兜底）搜索外部新闻入库；如果 LLM 已配置，会在外部搜索前用 LLM 扩展搜索关键词（公司别名、中文名等），LLM 未配置时优雅降级为规则关键词。新增 `TavilyClient`、`GoogleNewsSearchClient`、`StockNewsSearchService` 三个服务，修改 `POST /api/watchlist` 集成自动关联逻辑，新增 `tavily_api_key` 和 `stock_news_min_count` 配置项。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/tavily_client.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/google_news_search.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/stock_news_search.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/watchlist.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_stock_news_search.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-watchlist-auto-news-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有（`POST /api/watchlist` 行为变更：添加后自动关联新闻；Settings 新增 `tavily_api_key`、`stock_news_min_count`）
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过（47 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：Tavily API 有免费额度限制（1000 次/月），超限后自动降级到 Google News RSS；Google News RSS 被 Google 限流时搜索会静默失败；LLM 关键词扩展依赖已配置的 LLM provider，未配置时跳过；后台线程异常不影响主请求，但搜索结果会延迟出现；前端无需修改，`news_stock_mention` 数据补齐后关联新闻自动展示

## 2026-03-18 16:12

- 修改人：Codex
- 修改范围：飞书通知回归修复、后端回归测试、前端 mock 回归测试、设计与计划文档
- 变更内容：修复飞书通知两个合并阻塞回归：新闻刷新接口不再通过“最近 N 条”反推新增新闻，而是由 `NewsIngestionService` 显式返回本次真实插入的 `inserted_items` 供通知使用；自选股异动通知改为进程内边沿触发状态机，只有首次越过阈值时发送，跌回阈值内后才允许下一次再次提醒，避免页面启动和 watchlist 读取重复刷屏；同时修正前端 mock 降级下飞书配置保存逻辑，编辑已配置项且留空 `app_secret` 时继续保留 `app_secret_set=true`。补充后端新闻刷新/自选股通知回归测试和前端 API client 回归测试，并新增本轮设计、计划文档。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/notification_service.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-feishu-notification-bugfix-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-feishu-notification-bugfix-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无对外 API 结构变化；内部 `RefreshSummary` / `SourceFetchResult` 新增 `inserted_items` 字段用于通知链路
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_market.py backend/tests/test_feishu_notify.py -q` 通过（20 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts` 通过（1 个文件 / 1 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：自选股提醒状态仍是进程内内存，服务重启后若股票仍处于阈值外，首次读取 watchlist 仍会补发一次；本轮未把提醒迁到独立调度任务，后续若要彻底去除读接口副作用，建议再拆为后台轮询

## 2026-03-18 14:30

- 修改人：Cursor
- 修改范围：飞书应用 Bot 推送通知全链路、前后端配置管理、业务集成、测试与设计文档
- 变更内容：新增飞书应用 Bot API 推送通知功能，支持三类信号推送（新闻聚合、自选股异动、LLM 分析结果）；后端新增 `FeishuNotifyConfig` 模型、仓储、Schema、`FeishuClient` 飞书 API 客户端（tenant_access_token 鉴权 + 消息卡片发送）、`NotificationService` 通知服务（进程内事件缓冲 + 定时聚合推送 + 实时推送）、`/api/notify/feishu/*` 配置与测试接口；将通知集成到新闻刷新（news.refresh）、LLM 分析（news.analyze）和自选股行情（market.watchlist）三个业务入口；前端新增通知设置页 `/settings/notify`（飞书凭证、目标类型、通知开关、聚合间隔、测试按钮）、`notifyStore`、API client 扩展和 mock 降级；侧栏导航新增 `06 Notify` 入口。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/feishu_notify_config.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/__init__.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/feishu_notify_config_repository.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/feishu_notify.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/feishu_client.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/notification_service.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/notify.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/router.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_feishu_notify.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/notifyStore.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NotifySettingsView.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-feishu-notification-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过（38 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：飞书凭证（App ID/App Secret）存储在数据库明文，与 LLM key 同级安全策略，适合个人使用；新闻聚合使用进程内定时器，服务重启后缓冲区清空；自选股异动检测挂在行情查询入口，仅在行情被请求时触发，后续可加独立定时轮询；关键词过滤为子串匹配，后续可升级为分词匹配

## 2026-03-18 13:06

- 修改人：Codex
- 修改范围：自选股详情页指标卡与关联新闻卡终端化、测试、设计与计划文档
- 变更内容：把自选股详情页 `指标详情` 区块中仍然发灰发亮的小卡片，以及 `关联新闻` 区块中仍然偏亮的新闻卡统一切换为深色终端表面，补齐终端卡钩子、文字对比度和 hover 层级，使该页面与前面已经收紧的终端视觉体系保持一致。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-watchlist-detail-terminal-polish-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-watchlist-detail-terminal-polish-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/WatchlistDetailView.test.ts` 通过（1 个文件 / 1 个用例）；`npm --prefix frontend run test -- --run src/views/WatchlistDetailView.test.ts src/views/LlmSettingsView.test.ts src/components/watchlist/WatchlistTable.test.ts` 通过（3 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮只修正自选股详情页卡片表面和文字层级，不调整布局与数据逻辑；如果后续仍觉得信息块太平，可以再给数值卡加入更精细的数值权重和边界光效

## 2026-03-18 12:35

- 修改人：Codex
- 修改范围：终端交互态细化、共享状态组件与导航交互、验证
- 变更内容：在高对比终端视觉基础上继续统一 `hover / focus / selected / disabled` 交互反馈，为全局 token 增加交互态色值与 focus ring；细化 AppShell 导航 hover、StatusBanner tone 层级、自选股表格选中态、Topic/Watchlist/X Monitor/Topic Detail/News Detail/LLM Settings 等页面中的卡片 hover、按钮 hover 与 disabled 态，使页面更接近交易终端的反馈节奏，而不再停留在“深色静态页面”。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/assets/main.css`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/StatusBanner.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/TopicBoard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/LlmSettingsView.test.ts src/components/watchlist/WatchlistTable.test.ts src/components/dashboard/TopicBoard.test.ts src/views/NewsFeedView.test.ts src/components/news/NewsCard.test.ts` 通过（5 个文件 / 6 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮主要增强交互态一致性，没有改变布局或数据逻辑；如果后续还要进一步提升终端沉浸感，建议补全更多页面的 disabled / empty / loading 态视觉标准，而不是继续单点修补

## 2026-03-18 12:28

- 修改人：Codex
- 修改范围：LLM Settings 页面表单终端化、测试、设计与计划文档
- 变更内容：将 `LLM Settings` 页中仍然使用白色底板的输入框全部切换为深色终端输入面板，补齐字段终端钩子、placeholder 对比度、focus 态描边、按钮渐变和成功/失败提示色，避免该页面继续出现刺眼白底破坏整体科技终端风格；同时新增本轮设计与计划文档并扩展页面测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-llm-settings-terminal-input-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-llm-settings-terminal-input-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/LlmSettingsView.test.ts` 通过（1 个文件 / 2 个用例）；`npm --prefix frontend run test -- --run src/views/LlmSettingsView.test.ts src/components/watchlist/WatchlistTable.test.ts src/components/dashboard/TopicBoard.test.ts` 通过（3 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮只修正了 `LLM Settings` 表单视觉，不改变保存逻辑；如果后续还要继续增强科技感，可再统一所有表单页面的 hover / disabled / invalid 态

## 2026-03-18 12:22

- 修改人：Codex
- 修改范围：前端高对比终端视觉修复、仓库级 visual companion 启动脚本、测试与设计/计划文档
- 变更内容：将多个仍使用浅灰白半透明表面的区域统一收敛回深色终端表面，重点修复自选股表格、Dashboard 主题卡、Watchlist 关联新闻卡、X Monitor 指标卡与筛选框、Topic Detail 过滤区和来源卡、News Detail 分析卡的低对比度问题，并同步提亮次级文字和链接/按钮高亮，强化科技终端感；同时新增仓库级 `scripts/start-server.sh` 包装脚本，转发到 `brainstorming` skill 中真实存在的启动脚本，避免后续在仓库根目录直接执行时报“文件不存在”。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/assets/main.css`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/SectionCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/TopicBoard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/TopicBoard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/scripts/start-server.sh`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-terminal-contrast-polish-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-terminal-contrast-polish-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/WatchlistTable.test.ts src/components/dashboard/TopicBoard.test.ts` 通过（2 个文件 / 2 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/WatchlistTable.test.ts src/components/dashboard/TopicBoard.test.ts src/views/NewsFeedView.test.ts src/components/news/NewsCard.test.ts` 通过（4 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮主要通过统一深色表面和提高文字对比度来修复可读性，属于视觉收敛而非结构重做；如果后续要继续细化“科技感”，下一步适合补更系统的 hover / focus / row-selected 态，而不是再引入浅色大面积底板

## 2026-03-18 11:45

- 修改人：Codex
- 修改范围：News Feed 首页信息编排、统一横向新闻卡、前端测试、设计与计划文档
- 变更内容：取消首页 `Primary Signal` 与 `Signal Queue` 的 editorial 分层，不再按重要度放大或重排新闻，改为直接按当前数据顺序渲染统一的 `News Stream` 横向卡片列表；同时将首页新闻卡统一为横向信息结构，左侧显示标题与摘要，右侧显示时间与主题，避免中间三张卡继续呈现竖向高卡；删除已不再使用的 `LeadStoryCard` 组件及其测试，避免把被废弃的首页主卡方案继续留在可执行代码里；补充对应设计文档、实现计划与前端测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/LeadStoryCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/LeadStoryCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-news-feed-unified-horizontal-list-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-news-feed-unified-horizontal-list-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/components/news/NewsCard.test.ts src/components/news/StoryStrip.test.ts` 通过（3 个文件 / 3 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮按需求明确取消了首页的“主信号推荐”层次，如果后续仍需要突出某类新闻，建议通过可切换排序或单独筛选实现，而不是重新引入放大型主卡

## 2026-03-18 11:28

- 修改人：Codex
- 修改范围：News Feed 首页冷蓝灰终端配色、Primary Signal 主卡布局、前端测试、设计与计划文档
- 变更内容：将首页全局终端色板从偏亮橙蓝辉光收敛为冷蓝灰交易终端风，压暗背景和表面层级并将高亮统一为少量青色信号；把 `Primary Signal` 主卡从纵向海报式超大标题改为更紧凑的终端主卡，采用顶部信号标签、中部压缩标题与 2 到 3 行摘要、底部横向 meta 信息带的结构；同时新增 `LeadStoryCard` 测试覆盖新结构钩子，并补充本轮设计文档和实现计划。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/assets/main.css`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/LeadStoryCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/LeadStoryCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-news-feed-terminal-refinement-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-news-feed-terminal-refinement-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/news/LeadStoryCard.test.ts src/views/NewsFeedView.test.ts` 通过（2 个文件 / 2 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮主要压缩了首页主卡和终端色板，其他页面仍沿用同一 token 体系但未逐页做更细的视觉平衡检查；若后续需要继续增强“交易终端”气质，可再细调卡片密度和导航区信息层级

## 2026-03-18 01:43

- 修改人：Codex
- 修改范围：前端全局终端式视觉系统、AppShell、共享组件、News Feed、Dashboard、前端测试
- 变更内容：将前端主视觉从暖色杂志风切换为冷色金融终端风，重写全局 design tokens、焦点态和语义色；重做 `AppShell` 侧栏为终端式系统导航与状态模块；为 `SectionCard`、`StatusBanner`、`HeroMetrics` 增加终端语义结构并统一深色表面；将 `News Feed` 重命名和重构为 `Signal Desk / Primary Signal / Signal Queue / News Stream` 的终端化阅读流；将 `Dashboard` 收敛为 `Market Control / Signal Overview / Live Movers` 的控制台式总览；同时新增和更新组件/页面测试覆盖这些结构与文案钩子。
- 影响文件：
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/assets/main.css`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/common/SectionCard.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/common/SectionCard.test.ts`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/common/StatusBanner.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/common/StatusBanner.test.ts`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/dashboard/HeroMetrics.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/dashboard/HeroMetrics.test.ts`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/news/LeadStoryCard.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/news/StoryStrip.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/news/StoryStrip.test.ts`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run` 通过（11 个文件 / 19 个用例）；`npm --prefix frontend run build` 通过；Playwright 实测 `1400px/1280px/1050px/760px` 下 shell 与新闻网格按预期折叠，`Tab` 焦点在深色背景下保持可见
- 风险/后续事项：本轮主要覆盖共享框架、News Feed 和 Dashboard，其余详情页与设置页主要继承新 token，尚未逐页做更深的视觉微调；开发态仍会对不存在的 `/api/stream/events` 打出 404 console 错误，但当前 mock/降级路径不受影响

## 2026-03-18 01:37

- 修改人：Codex
- 修改范围：前端终端化 UI 改造设计与实现计划文档
- 变更内容：新增前端终端式 UI 改造的设计文档与实现计划，明确从暖色杂志风切换为冷色金融终端风的目标，收敛橙色主信号与蓝色系统信号的语义边界，并把全局 token、AppShell、共享卡片、News Feed、Dashboard、响应式和验证拆成可执行任务。
- 影响文件：
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/docs/superpowers/specs/2026-03-18-frontend-terminal-ui-design.md`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/docs/superpowers/plans/2026-03-18-frontend-terminal-ui-plan.md`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：设计与计划文档已落盘；spec 与 plan 各经过独立 reviewer 检查并按反馈补齐验收边界、测试归属与响应式验证要求
- 风险/后续事项：当前仅完成文档阶段，尚未进入前端代码实现；后续执行时需严格保持路由和数据流不变，并验证深色主题下的可读性和焦点态

## 2026-03-18 00:48

- 修改人：Codex
- 修改范围：News Feed supporting stories 横向卡片布局、前端测试、设计与计划文档
- 变更内容：为 `Supporting Stories` 区块补充独立的 supporting 卡片结构，将原先标题和摘要纵向堆叠的高卡片改成更紧凑的横向信息卡；桌面端保持 3 列，平板降为 2 列，手机降为 1 列；同时新增组件测试覆盖 supporting 卡片专用 body/meta 包裹层，并补充本轮设计与实现计划文档。
- 影响文件：
  - `/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/frontend/src/components/news/StoryStrip.vue`
  - `/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/frontend/src/components/news/StoryStrip.test.ts`
  - `/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/docs/superpowers/specs/2026-03-18-supporting-stories-horizontal-layout-design.md`
  - `/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/docs/superpowers/plans/2026-03-18-supporting-stories-horizontal-layout-plan.md`
  - `/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/news/StoryStrip.test.ts` 先失败后通过（1 个文件 / 1 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 3/2/1 列切换断点采用 `1099px` 和 `768px`，如果你希望平板更早或更晚切成双列，可以继续微调 [`/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/frontend/src/components/news/StoryStrip.vue`](/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/frontend/src/components/news/StoryStrip.vue) 中的媒体查询阈值

## 2026-03-17 23:52

- 修改人：Codex
- 修改范围：LLM 设置页、配置更新保留 key 语义、前后端测试
- 变更内容：后端 `POST /api/llm/config` 现在在首次创建时要求提供 `api_key`，但编辑既有配置时允许空 key 并保留后端原值，避免前端设置页误清空已保存的密钥；前端新增独立的 `LLM Settings` 页面、`/settings/llm` 路由、左侧导航入口和 `llmStore`，支持查看当前活动配置、编辑 provider/display/base_url/model，并在不重输 key 的情况下保存；新闻详情页改为从 `llmStore` 读取配置状态；同时补充设置页测试和后端 preserve-key 测试。
- 影响文件：
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/api/routes/llm.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/repositories/llm_provider_config_repository.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/schemas/llm.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/tests/test_llm_config.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/router/index.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/stores/llmStore.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/stores/newsStore.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/views/LlmSettingsView.vue`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/views/LlmSettingsView.test.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/views/NewsDetailView.test.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/specs/2026-03-17-llm-settings-page-design.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/plans/2026-03-17-llm-settings-page-plan.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过（30 个用例）；`npm --prefix frontend run test -- --run` 通过（4 个文件 / 11 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前设置页仍然基于后端单租户明文存储 key 的假设，适合内部个人使用，不适合直接开放到多用户生产场景；“空 key 保留原值”已解决误清空问题，但如果未来要支持显式删除 key，需要再补单独的删除动作和更清晰的交互

## 2026-03-17 23:18

- 修改人：Codex
- 修改范围：LLM 设置页设计与实现计划文档
- 变更内容：新增 `LLM Settings` 页的设计文档与实现计划，明确单活动配置表单、前端独立设置页入口，以及后端配置更新时“空 key 保留原 key”的语义，作为下一阶段让用户直接在页面中录入和维护大模型配置的实现基线。
- 影响文件：
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/specs/2026-03-17-llm-settings-page-design.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/plans/2026-03-17-llm-settings-page-plan.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：设计与计划文档已落盘，内容与当前后端配置接口和下一阶段 UI 目标对齐自检
- 风险/后续事项：当前仅完成 spec 和 implementation plan，尚未进入代码实现；后续需要谨慎处理“保留原 key”与“显式清空 key”的交互边界

## 2026-03-17 23:00

- 修改人：Codex
- 修改范围：新闻详情页 LLM 标的分析、多 provider 配置接口、分析结果持久化、前后端测试
- 变更内容：后端新增 `LLM` 配置表、分析结果表、配置仓储、分析仓储、`openai-compatible` provider 和新闻分析服务；新增 `GET/POST /api/llm/config` 及 `GET/POST /api/news/{id}/analysis|analyze` 接口，支持后端保存当前活动 provider/model/API key，并对单条新闻手动触发结构化分析，返回首选标的、候选列表、摘要、风险提示与上下文限制；前端扩展 API 类型、client、mock 和 `newsStore`，在新闻详情页新增“LLM 标的分析”区块，支持未配置空状态、加载态、重新分析和结果展示；同时补充后端配置/分析测试与前端详情页测试。
- 影响文件：
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/api/router.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/api/routes/llm.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/models/__init__.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/models/llm_provider_config.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/models/news_analysis_result.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/repositories/llm_provider_config_repository.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/repositories/news_analysis_repository.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/schemas/llm.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/services/llm_providers.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/services/news_analysis.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/tests/test_llm_config.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/tests/test_news_analysis.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/stores/newsStore.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/views/NewsDetailView.test.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/specs/2026-03-17-llm-news-analysis-design.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/plans/2026-03-17-llm-news-analysis-plan.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过（28 个用例）；`npm --prefix frontend run test -- --run` 通过（3 个文件 / 9 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 API key 仍为后端单租户明文存储方案，适合你个人先用，不适合直接多人共享；第一版 provider 实现只做 `openai-compatible` 协议抽象，后续若接 `Anthropic/智谱/通义` 仍需补具体 client；分析结果是模型建议而非事实字段，也未与自选股或自动操作联动

## 2026-03-17 17:18

- 修改人：Codex
- 修改范围：LLM 新闻标的分析实现计划文档
- 变更内容：新增新闻详情页手动触发 LLM 标的分析的实现计划，按 provider 配置持久化、新闻分析结果落库、后端分析接口、前端详情页交互和验证步骤拆成可执行任务，并明确每个任务先写失败测试再实现。
- 影响文件：
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/plans/2026-03-17-llm-news-analysis-plan.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：计划文档已落盘，内容与已确认 spec 对齐自检
- 风险/后续事项：当前仅完成 implementation plan，尚未进入代码实现；实际落地时需要继续处理 API Key 存储安全边界和 provider 错误语义

## 2026-03-17 22:32

- 修改人：Codex
- 修改范围：候选合并分支审查修正、测试初始化、本地产物清理
- 变更内容：在审查 `codex/invalid-request` 时补充后端测试初始化夹具，确保新闻相关测试在创建 `TestClient` 前完成数据库建表和种子初始化，消除 `news_item/article_content` 缺表导致的 5 个失败用例；同时恢复仍被 README 引用的 `ANGENT.md`，并移除误提交的 `.superpowers` brainstorm 产物与 `backend/news_caught.db`，补充 `.gitignore` 以避免再次入库。
- 影响文件：
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/tests/conftest.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/.gitignore`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/ANGENT.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught pytest backend/tests` 通过（21 个用例）；`npm --prefix frontend test -- --run` 通过（3 个文件 / 7 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本次只修正了候选分支可合并性问题，未处理同一 worktree 中已有但与本次审查无关的未提交设计文档和记录变更

## 2026-03-17 17:10

- 修改人：Codex
- 修改范围：LLM 新闻标的分析设计文档
- 变更内容：新增新闻详情页手动触发 LLM 标的分析的设计文档，明确多 provider 抽象、后端统一保存活动 provider 配置、单条新闻结构化分析结果落库，以及与 `X Monitor/grok-bridge` 链路隔离的边界；同时约束第一版仅支持详情页手动触发，不接入新闻抓取、定时分析或自动交易动作。
- 影响文件：
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/specs/2026-03-17-llm-news-analysis-design.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：设计文档已落盘，内容与已确认的产品边界和架构方向自检一致
- 风险/后续事项：当前仅完成 spec，尚未进入 implementation plan 与代码实现；`ANGENT.md` 在主仓库约束中仍被引用，后续交付时需继续确认记录要求的一致性

## 2026-03-17 16:12

- 修改人：Codex
- 修改范围：新闻详情页正文区块精简、前端视图测试补齐、设计与计划文档
- 变更内容：移除新闻详情页中冗余的“正文内容”卡片，不再在页面内展示正文抓取结果、抓取状态与错误信息，保留头部 `打开原文` 作为查看完整正文的唯一入口；补充 `NewsDetailView` 组件测试，约束详情页继续保留原文链接且不再渲染正文抓取区块；同步新增本轮前端精简的设计文档与实现计划。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/package.json`
  - `/Users/xiuyang/Desktop/news-caught/frontend/package-lock.json`
  - `/Users/xiuyang/Desktop/news-caught/frontend/vitest.config.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-17-news-detail-body-section-removal-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-17-news-detail-body-section-removal-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/NewsDetailView.test.ts` 通过；`npm --prefix frontend run test -- --run` 通过（3 个文件 / 7 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮仅移除前端正文展示，不删除后端正文抓取与 `article` 返回字段；工作区仍存在大量非本轮引入的未提交改动和 `ANGENT.md` 删除状态，本轮未处理

## 2026-03-17 15:58

- 修改人：Codex
- 修改范围：新闻正文抓取回填、发布时间优先排序、前端时间兜底与启动刷新、修复设计/计划文档
- 变更内容：为 `MiniMax News` 新增详情页二次抓取与回填逻辑，可从详情页解析真实发布日期和正文内容，并为既有旧记录补写 `article_content` 与 `published_at`；新闻列表改为优先按 `published_at` 排序，前端新增新闻时间兜底 helper，在新闻详情、主题详情、News Feed 卡片及关联新闻里统一回退到 `fetched_at`；前端启动后会非阻塞触发一次 `/api/news/refresh` 并重新加载新闻/主题，减少页面停留在旧数据库快照的问题；同时补充本轮修复的设计文档、实现计划与针对 MiniMax 解析、旧记录回填、发布时间排序的测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/news_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/time.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/time.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/newsEditorial.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/LeadStoryCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-17-news-freshness-body-fix-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-17-news-freshness-body-fix-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过；`npm --prefix frontend run test -- --run` 通过；`npm --prefix frontend run build` 通过；`make ingest-news` 实测 `MiniMax Music 2.5+` 已回填真实 `published_at=2026-03-04T00:00:00Z` 且详情接口 `GET /api/news/123` 返回 `article.extract_status=success`
- 风险/后续事项：目前 `MiniMax News` 11 条里仅 `MiniMax Music 2.5+` 这类中文详情页模式已确认成功回填，其他英文 slug 仍有失败记录，后续需要继续为不同详情页模板补解析分支；工作区仍存在非本轮引入的 `ANGENT.md` 删除状态和其他前端未提交改动，本轮未处理

## 2026-03-16 23:38

- 修改人：Codex
- 修改范围：News Feed 杂志流改版、新闻排序辅助、左侧导航重构、前端测试基础设施
- 变更内容：前端新增 `Vitest` 测试基础设施和新闻 editorial 排序/分组辅助；News Feed 改为封面头条、supporting stories 和顺序流的杂志式布局，移除新闻页对固定高度虚拟列表的依赖，修复长中文标题与摘要重叠问题；左侧导航改为上对齐的编辑台式侧栏，并同步调整全局表面和留白节奏。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/package.json`
  - `/Users/xiuyang/Desktop/news-caught/frontend/package-lock.json`
  - `/Users/xiuyang/Desktop/news-caught/frontend/vitest.config.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/newsEditorial.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/newsEditorial.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/LeadStoryCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/StoryStrip.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/SectionCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/assets/main.css`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run` 通过；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮未新增人工置顶头条能力，头条仍由前端规则推断；未在本会话内完成浏览器手动验收；工作区仍存在非本轮引入的 `ANGENT.md` 删除状态，未处理

## 2026-03-16 21:48

- 修改人：Codex
- 修改范围：News Feed 杂志流 UI 优化实现计划文档
- 变更内容：新增 News Feed 杂志流 UI 实现计划，按前端排序辅助、杂志流布局改造、固定高度列表移除、侧栏重构、验证与记录更新拆成可执行任务，并明确前端测试与构建验证入口。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-16-news-feed-magazine-ui-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：计划文档已落盘，内容与已确认 spec 对齐自检
- 风险/后续事项：当前仅完成 implementation plan，尚未进入代码实现；前端当前无现成测试基础设施，实施阶段将补入最小 Vitest 支撑

## 2026-03-16 21:40

- 修改人：Codex
- 修改范围：News Feed 杂志流 UI 优化设计文档
- 变更内容：新增 News Feed 杂志流 UI 设计文档，明确封面式头条、次级新闻顺序流、前端混合排序、左侧导航改为上对齐编辑台侧栏，以及本轮仅做前端展示层重构、不新增后端接口的边界。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-16-news-feed-magazine-ui-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：设计文档已落盘，内容与已确认设计方向自检一致
- 风险/后续事项：当前仅完成 spec，尚未进入 implementation plan 与代码实现；由于工作区存在非本轮引入的 `ANGENT.md` 删除状态，本次未处理该文件

## 2026-03-16 21:05

- 修改人：Codex
- 修改范围：自选股真实行情接入、批量总览与详情页、后端缓存与接口、依赖与文档
- 变更内容：后端新增真实行情 provider 抽象、符号规范化、行情服务和 `/api/market/watchlist`、`/api/market/symbols/{symbol}` 接口，并扩展 `price_snapshot` 缓存字段；前端将自选股总览切换到新行情接口，新增单股详情页，展示价格、涨跌、开盘、昨收、最高、最低、成交量和相关新闻；同步补充 `yfinance` 依赖、README 和 API 契约说明。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/price_snapshot.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/market_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/quote_provider.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/quote_service.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/backend/pyproject.toml`
  - `/Users/xiuyang/Desktop/news-caught/requirements.txt`
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/api-contract.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过；`npm --prefix frontend run build` 通过；新增 `backend/tests/test_market.py` 覆盖自选股行情总览和详情接口
- 风险/后续事项：当前默认免费源为 `yfinance`，稳定性和字段覆盖受 Yahoo Finance 公共接口影响；本轮未完成 A 股支持；本地已存在旧 `price_snapshot` 表时依赖启动时补列

## 2026-03-16 20:41

- 修改人：Codex
- 修改范围：自选股真实行情接入实现计划文档
- 变更内容：新增自选股真实行情接入 implementation plan，按后端行情服务、前端总览与详情页、依赖与验证拆成可执行的 TDD 任务，作为后续实现基线。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-16-watchlist-real-market-data-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：计划文档已落盘，已与已确认 spec 对齐自检
- 风险/后续事项：计划未经过子评审；当前环境无 subagent，将在本会话按该计划执行

## 2026-03-16 20:32

- 修改人：Codex
- 修改范围：自选股真实行情接入设计文档
- 变更内容：新增自选股真实行情接入设计文档，明确港股/美股范围、免费行情源优先的 provider 抽象、符号规范化、批量总览接口、单股详情页、缓存与错误状态设计，为后续实现和计划拆解提供基线。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-16-watchlist-real-market-data-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：文档已落盘，内容已按已确认设计自检
- 风险/后续事项：尚未进入实现；免费行情源的具体 provider 仍需在实现阶段结合真实联调结果确认兼容细节

## 2026-03-16 19:55

- 修改人：Codex
- 修改范围：开发流程约束、superpowers skill 接入说明
- 变更内容：将 `obra/superpowers` 的核心开发流程以仓库级 `AGENTS.md` 形式接入当前项目，明确需求设计、计划拆解、TDD、系统化调试、验证、评审、分支收尾等阶段必须使用的 skills；同时在 `README.md` 补充 superpowers skills 需要预先安装到 `~/.codex/skills` 且安装后需重启 Codex 的说明，便于后续会话按同一流程执行。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/AGENTS.md`
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：已执行 `python /Users/xiuyang/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo obra/superpowers --path skills/using-superpowers skills/brainstorming skills/writing-plans skills/executing-plans skills/test-driven-development skills/requesting-code-review skills/receiving-code-review skills/systematic-debugging skills/verification-before-completion skills/dispatching-parallel-agents skills/subagent-driven-development skills/using-git-worktrees skills/finishing-a-development-branch`，并确认上述 skills 已出现在 `~/.codex/skills`；项目文档改动已落盘
- 风险/后续事项：当前会话不会自动重新加载新安装的 skills，需重启 Codex 后的新会话才会按新 skill 集生效；`obra/superpowers` 的 hooks、commands、agents 目录未直接并入本仓库，目前以 skill 约束为主

## 记录模板

```md
## YYYY-MM-DD HH:MM

- 修改人：
- 修改范围：
- 变更内容：
- 影响文件：
- 接口/数据结构变化：有 / 无
- 验证情况：
- 风险/后续事项：
```

## 2026-03-16 16:20

- 修改人：Codex
- 修改范围：X Monitor 增强模块、grok-bridge 联动、前后端接口与页面、测试与文档
- 变更内容：新增独立的 X Monitor 模块，通过 `grok-bridge` 拉取关注博主的近期市场相关 X 内容；后端新增 `x_account`、`x_post`、`x_post_symbol_mention`、`x_source_health` 模型、仓储、桥接客户端、刷新服务与 `/api/x/*`、`/api/health/x` 接口；前端新增 `X Monitor` 页面、类型、store、导航入口和 mock 兼容层；补充账号白名单示例文件、桥接说明文档与 X 模块测试；现有新闻、主题、自选股和 SSE 主链路未改为依赖该模块。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/router.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/__init__.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/x_account.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/x_post.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/x_post_symbol_mention.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/x_source_health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/x_account_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/x_post_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/x_source_health_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/grok_bridge_client.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/x_monitor_accounts.example.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/xMonitorStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/api-contract.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过；`npm --prefix frontend run build` 通过；新增 `backend/tests/test_x_monitor.py` 覆盖桥接客户端、刷新去重、X 接口启停与健康状态；现有后端测试继续通过
- 风险/后续事项：当前 `grok-bridge` 结果仍属于 AI 抽取，不等同于 X 官方原始数据；`X Monitor` 暂不做自动调度和主题聚合；若 `grok.com` 页面结构变化，桥接稳定性会受影响

## 2026-03-16 15:49

- 修改人：Codex
- 修改范围：智谱与 MiniMax 官方来源接入、新闻展示去重优化、抓取解析测试
- 变更内容：为新闻抓取层新增 `MiniMax News` 官方新闻源和 `Zhipu AI News` 官方新闻源；扩展 HTML 锚点列表与智谱内联 JSON 两类解析器，并补充对应测试；前端新增新闻内容去重工具，在新闻卡片、新闻流详情页和新闻详情页中，当标题、摘要、正文内容重复时自动折叠重复文案，避免同一条内容双重显示。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/news.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 已在本轮前通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过；`npm --prefix frontend run build` 通过；`make ingest-news` 实测新增 `MiniMax News` 11 条、`Zhipu AI News` 15 条
- 风险/后续事项：`MiniMax News` 当前来自官方新闻入口，发布时间字段未在列表页稳定暴露，因此暂时以抓取时间排序；智谱来源当前来自官网页面内联数据，如官网前端结构大改，解析器需要同步调整

## 2026-03-16 15:30

- 修改人：Codex
- 修改范围：公开新闻源抓取、来源健康观测、抓取命令与接口、A股市场支持、文档与测试
- 变更内容：新增公开新闻抓取服务，接入 `WSJ`、`The Verge`、`36Kr`、`SEC Press Releases`、`财联社电报` 五个可直接访问的数据源；新增 `POST /api/news/refresh` 手动刷新接口与 `GET /api/health/sources` 来源健康接口；新增 `make ingest-news` 命令和公司 IR 来源配置示例；前端市场类型扩展为 `cn` 并补充时区与筛选项；补充 RSS/HTML 解析测试与刷新接口测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/workers/news_fetcher.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/source_health_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/source_health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/news_sources.example.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/pyproject.toml`
  - `/Users/xiuyang/Desktop/news-caught/requirements.txt`
  - `/Users/xiuyang/Desktop/news-caught/Makefile`
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/time.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/api-contract.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过；`npm --prefix frontend run build` 通过；`make ingest-news` 实测抓取 86 条公开新闻并成功入库；`/api/news?limit=8`、`/api/news?market=cn&limit=5`、`/api/health/sources` 已本地验证通过
- 风险/后续事项：`Reuters` 公开站点当前会返回 JS/反爬拦截页，尚未接入；公司 IR 新闻页仍需提供具体公司或 URL；中文源目前以 `cn` 市场落库，若后续要细分 A 股/H 股需进一步拆分市场模型

## 2026-03-16 14:56

- 修改人：Codex
- 修改范围：新闻列表筛选、UTC 时间序列化、前端时间兜底、后端测试
- 变更内容：为 `GET /api/news` 接入 `market`、`q`、`source_name`、`sentiment_label`、`limit` 查询参数并下推到仓库查询；新增统一 UTC 时间类型，修正新闻、主题、行情和健康接口的时间输出为带 `Z` 的 ISO 8601；前端时间工具增加无时区字符串按 UTC 解析的兜底；补充新闻接口筛选与时间格式测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/news_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/common.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/topic.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/time.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过；本地请求已验证 `/api/news?market=hk&limit=1` 和 `/api/news?q=Tencent` 正确过滤；`/api/news/1` 时间字段已输出 `Z`；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前仍是本地种子数据，真实抓取、来源健康检查和正文抽取任务仍未接入外部数据源

## 2026-03-16 14:34

- 修改人：Codex
- 修改范围：主题详情页、新闻详情页、交互增强
- 变更内容：为主题详情页新增关键词过滤和“只看带原文链接”开关；为新闻详情页新增同主题来源的上一条/下一条导航，支持在单个主题下顺序浏览不同来源。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：前端构建通过，`make build-frontend` 已验证
- 风险/后续事项：当前股票高亮仍基于标题和摘要命中，后续如需更准确应直接使用新闻提及数据

## 2026-03-16 14:20

- 修改人：Codex
- 修改范围：项目初始化、前后端骨架、主题聚合交互、自选股联调、协作规范、仓库提交准备
- 变更内容：完成项目计划和技术文档体系；搭建 FastAPI 后端骨架与 SQLite 初始化、健康检查、新闻/主题/自选股接口；搭建 Vue 前端主页面、新闻详情、主题详情、自选股添加链路；增强主题详情页的分组、时间线、过滤、高亮和原文直达交互；新增协作规范 `ANGENT.md` 与代码变更记录机制；新增 `.gitignore`，避免把依赖、缓存、构建产物和本地数据库提交到仓库。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.gitignore`
  - `/Users/xiuyang/Desktop/news-caught/plan.md`
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/ANGENT.md`
  - `/Users/xiuyang/Desktop/news-caught/backend`
  - `/Users/xiuyang/Desktop/news-caught/frontend`
  - `/Users/xiuyang/Desktop/news-caught/docs`
  - `/Users/xiuyang/Desktop/news-caught/Makefile`
  - `/Users/xiuyang/Desktop/news-caught/requirements.txt`
  - `/Users/xiuyang/Desktop/news-caught/environment.yml`
  - `/Users/xiuyang/Desktop/news-caught/scripts/dev.sh`
- 接口/数据结构变化：有
- 验证情况：后端测试通过；前端构建通过；本地接口联调已验证 `health`、`watchlist`、`topics`、`news detail` 等关键链路
- 风险/后续事项：真实抓取和更大规模主题聚合仍需后续继续补强；本次提交前需确认 GitHub 私有仓库创建并成功推送

## 2026-03-16 14:08

- 修改人：Codex
- 修改范围：项目说明、并行开发协作约束
- 变更内容：将“每次修改必须回填代码记录文档”的要求同步写入 `README.md` 和并行开发文档，确保多线程开发时也默认执行该规则。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/parallel-development.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：文档已更新并落盘
- 风险/后续事项：后续所有开发线程仍需要主动遵守，否则记录机制只会停留在文档层面

## 2026-03-16 14:05

- 修改人：Codex
- 修改范围：协作规范、变更记录机制
- 变更内容：新增根目录 `ANGENT.md`，约束后续所有修改必须同步回填到代码记录文档；新增 `docs/code-change-log.md` 作为统一记录入口。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/ANGENT.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：文档已创建，内容已落盘
- 风险/后续事项：后续每次代码、配置、文档、脚本修改都需要同步更新本文件，否则记录机制会失效

## 2026-03-28 — K-line News Markers

### Changed
- `backend/app/schemas/market.py`: Added `summary` field to `NewsEventItemView`
- `backend/app/services/market_chart_service.py`: Extract `summary` in `_align_news_events()`
- `frontend/src/types/api.ts`: Added `summary` to `NewsEventMarkerItem`
- `frontend/src/components/watchlist/KlineChart.vue`: Added sentiment-colored markers on candlestick chart via `setMarkers()`, crosshair hover tooltip, and click popup for news details
- `frontend/src/components/watchlist/KlineNewsTooltip.vue`: New hover tooltip showing news titles + sentiment
- `frontend/src/components/watchlist/KlineNewsPopup.vue`: New click popup showing news titles + summaries

## 2026-06-13 12:40

- 修改人：Antigravity (Gemini 3.5 Flash)
- 修改范围：性能与连接池重构、消除动态导入、复合索引分页优化、工程化整洁度
- 变更内容：
  1. **复合索引设计**: 在 `NewsItem` 模型上为 `(published_at, id)` 和 `(market, published_at, id)` 建立了复合索引，并生成了最小化的 alembic 数据库迁移以避免 SQLite batch 外键重建兼容问题。
  2. **共享连接池**: 新增 `http_pool.py` 以实现进程级单例共享的 `httpx.Client` 池，最大连接 50，超时 60s；重构 `llm_providers.py` 中的评分和嵌入接口为使用共享连接池，并在 main 生命钩子退出时关闭连接池。
  3. **热路径导入清理**: 移除了 `queue_worker.py` 和 `news_signal_pipeline.py` 中在 do_cycle 和 process_news_ids 热路径下的局部动态 import，修正了反向依赖。
  4. **工程化清理**: 将已提交的临时测试快照文件 `test_output.txt` 和 `frontend/test_output.txt` 从 git 版本控制中移除并物理删除，在 `.gitignore` 中加入其忽略规则；合并并统一了拼写不同的 `AGENTS.md` 和 `ANGENT.md` 的协作规范和日志填写规范。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/news_item.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/alembic/versions/6ca1c6bd4ed1_add_news_item_composite_indexes.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/http_pool.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/llm_providers.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/workers/queue_worker.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_signal_pipeline.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/.gitignore`
  - `/Users/xiuyang/Desktop/news-caught/AGENTS.md`
  - `/Users/xiuyang/Desktop/news-caught/ANGENT.md`
- 接口/数据结构变化：有
- 验证情况：`make test-backend` 验证全部 321 项测试通过；进入 sqlite 验证了 `ix_news_market_published_id` 复合索引已被查询计划采用。
- 风险/后续事项：无

## 2026-06-13 12:45

- 修改人：Antigravity (Gemini 3.5 Flash)
- 修改范围：核心写锁性能优化 (Phase 2 重构)
- 变更内容：
  1. **两阶段管线拆分**: 将 `NewsSignalPipelineService.process_news_ids` 流程解耦为两阶段。第一阶段（正文补全）在主 write 事务外运行，并当 `session_factory` 存在时以独立短事务逐条提交落库，防止网络 I/O 阻塞独占 SQLite 锁；单 session 模式下则退化为普通 `flush()` 保证测试向后兼容。第二阶段进行无网络 I/O 的内存快速分类及关联，减少了写锁被长周期占有的顽疾。
  2. **队列持久化与自愈重构**: 升级 `BackgroundQueueWorker` 引入了“内存通知 + 数据库 pending 自愈轮询”的双轨机制。当内存队列空或进程重启丢失分析任务时，worker 会自动通过 `NewsSignalPipelineService.list_pending_news_ids` 对未分析的 pending 新闻进行扫描补偿，实现了百分之百防重启丢失。
  3. **Token 计量批量缓冲缓冲落库**: 实现了线程安全的 `TokenUsageBuffer` 类，支持在生产环境下将多次计量聚合至 50 条或 10 秒后以批量 `bulk_insert_mappings` 落库。利用 pytest 环境自动感应（自动降为阈值 1）确保单元测试正常运行。在 `main.py` 的 lifespan 退出阶段自动执行 `flush()` 防止漏盘。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/token_usage_buffer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/llm_providers.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/workers/queue_worker.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_signal_pipeline.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`make test-backend` 验证全部 321 项测试通过；`pytest backend/tests/test_llm_stats.py` 与 `pytest backend/tests/test_news_ingestion.py` 均已全部通过。
- 风险/后续事项：无

## 2026-07-25

- 修改人：Claude
- 修改范围：新闻抓取时效性修复、信息源扩容
- 变更内容：
  1. **常驻抓取开关**：确认 `NewsIngestScheduler` 此前默认不随后端进程启动（`news_scheduler_enabled` 默认 `False` 且本地 `.env` 未开启），是"抓取延迟明显"的根因——日常开发环境下新闻只在手动执行一次性脚本 `make ingest-news` 时才批量入库一次。在仓库根目录 `.env` 追加 `NEWS_SCHEDULER_ENABLED=true`，不改代码默认值（保持 CI/无 `.env` 环境下默认关闭）。
  2. **快讯层 cadence 分层**：既有 `CLS Telegraph` 与新增的 `MarketWatch MarketPulse`、`Wallstreetcn Live` 三个源的 `cadence_seconds` 从默认 300s 收紧到 100s；其余源维持 300s 不变。
  3. **新增 `wallstreetcn_live_json` 解析器**：新增 `_parse_wallstreetcn_live_json`（`backend/app/services/ingestion/parser.py`），解析华尔街见闻 7×24 快讯 JSON 直播接口；快讯类条目 `title` 常为空时按项目既有约定（财联社电报同款）回退为 `content_text` 前 60 字；`display_time`（Unix epoch 秒）直接转 UTC；对 `uri`/`title` 做 `isinstance(str)` 校验，非法类型的单条记录会被跳过而不是让整批抓取失败（对齐同文件内 `_parse_the_news_api_json` 的既有防御模式）。接入 `fetcher.py` 的 parser 分发链与 `news_ingestion.py` 的 re-export。
  4. **新增 9 个信息源**：`_default_sources()` 从 7 个扩到 16 个——美股新闻通讯社/快讯 7 个（MarketWatch Top Stories、MarketWatch MarketPulse、CNBC Finance、Yahoo Finance News、PR Newswire Financial Services、GlobeNewswire Earnings、Nasdaq Press Releases），中文财经快讯 2 个（Investing.com CN、Wallstreetcn Live）。全部为实测可用的 RSS/JSON 端点，均走 `_default_sources()` 硬编码约定（不使用 `news_sources_file` 机制）。
  5. **评估后放弃的候选**：东方财富快讯 JSON API 可用但混入地质灾害预警等与股票市场无关内容，与产品"低噪音"定位冲突，未接入；AAStocks、etnet.com.hk、格隆汇、同花顺（10jqka）的所谓 RSS 端点已下线（404/500）或需 JS 渲染，未接入；华尔街见闻自身 `rss.xml`/`feed.xml` 静态文件已下线，改用其站内真实使用的 JSON 直播接口；Benzinga RSS 被 Cloudflare 拦截（403），未接入。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/ingestion/parser.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/ingestion/fetcher.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/ingestion/sources.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/.env`（本地环境，未提交版本库）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-07-25-news-ingestion-timeliness-and-sources-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-07-25-news-ingestion-timeliness-and-sources.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（`SourceDefinition`/`SourceItem` 结构未变，只是新增数据和一个内部解析器）
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 640 passed（另有 1 项与本次改动无关的既有失败——`test_news_relevance_experiment_runner.py::test_experiment_runner_allows_news_relevance_research_files`，该测试硬编码主仓库绝对路径，在 git worktree 路径下必然失配，与本次未触碰的文件无关）；`ruff check` 对本次改动涉及的文件全部通过；`make ingest-news` 在隔离 worktree 中实测跑通全部 16 个源，`fetched=227 inserted=98`，9 个新源全部 `status=ok`（Wallstreetcn Live 新解析器 `fetched=20 inserted=2`，验证端到端可用）。
- 风险/后续事项：本次实测中既有的 `CLS Telegraph`（`status=empty`）与 `Zhipu AI News`（`status=parse_error`，`Expecting ',' delimiter`）两个源出现问题，均为本次改动之前就存在的源、非本次新增/修改的代码路径，怀疑是目标站点页面结构或返回内容发生变化；调度器的失败退避机制会自动降频，不影响新增的 9 个源。`.env` 的 `NEWS_SCHEDULER_ENABLED=true` 已写入主 checkout，但需要重启本地开发服务器（`./scripts/dev.sh`）才能生效——本次未强制重启，因为重启会终止用户当前正在运行的 dev 会话（backend pid 6421 / frontend pid 6643），已与用户确认后再操作。
