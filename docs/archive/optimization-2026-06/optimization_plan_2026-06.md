# News-Caught 优化计划（2026-06，基于当前代码勘察）

> **归档状态**：已于 2026-06-12 全部实施完成。归档目录 [`docs/archive/optimization-2026-06/`](./README.md)。实现记录见 [`docs/code-change-log.md`](../../code-change-log.md)。

> 范围：只列 Plan，不含实现代码。每项含问题定位、方案、验收标准，供后续 AI 开发。
> 前提约束（已确认的项目决策）：数据源 < 20 个，**继续用 SQLite，不迁 Postgres**；去重二次判重接口（`SecondaryDuplicateJudge`）保留。

## 优先级总览

| # | 优化项 | 优先级 | 风险类型 | 预估工作量 |
|---|--------|--------|----------|-----------|
| 1 | 引入 Alembic 替换手写 schema 迁移 | P0 | 数据安全/技术债 | 1-2 天 |
| 2 | SQLite WAL + 并发写加固 | P0 | 稳定性 | 0.5 天 |
| 3 | 事件总线 handler 异常隔离 | P0 | 稳定性 | 0.5 天 |
| 4 | 重负载事件 handler 移出同步链路 | P0 | 性能/稳定性 | 1-2 天 |
| 5 | LLM api_key 明文存储加密 | P1 | 安全 | 0.5 天 |
| 6 | news_ingestion.py 千行模块拆分 | P1 | 可维护性 | 2-3 天 |
| 7 | 新闻列表 keyset 分页 | P1 | 功能/性能 | 1 天 |
| 8 | 数据生命周期（保留策略 + 清理任务） | P1 | 容量 | 1 天 |
| 9 | Worker 线程统一生命周期管理 | P1 | 稳定性 | 1-2 天 |
| 10 | CI 流水线（无 .github） | P2 | 工程化 | 0.5 天 |
| 11 | 前端类型从 OpenAPI 自动生成 | P2 | 工程化 | 1 天 |
| 12 | 前端巨型组件拆分（KlineChart 903 行等） | P2 | 可维护性 | 2-3 天 |
| 13 | 去重灰区 embedding 二次判重落地 | P2 | 准确性 | 1-2 天 |

---

## P0 — 必须先做（数据安全与稳定性）

### 1. 引入 Alembic，替换 `db/initializer.py` 手写迁移

**问题**：`alembic>=1.14.0` 在 `pyproject.toml` 依赖里，但项目从未初始化 alembic 目录。取而代之的是 576 行的 `backend/app/db/initializer.py`，含 16 个 `ensure_*_columns()` 函数手写 `ALTER TABLE`。每加一个字段都要手写一条 SQL + 存在性检查，无版本号、无回滚、无法知道某个库处于哪个 schema 版本。这是当前最大技术债。

**方案**：
- `alembic init backend/alembic`，配置读 `Settings.database_url`
- 用 `--autogenerate` 生成首个 baseline 迁移（对齐当前 models）
- 写一次性脚本：检测旧库（已被 `ensure_*` 改过的）并 `alembic stamp head`
- `initializer.py` 退化为「新库 create_all + stamp」或直接删除，启动时改跑 `alembic upgrade head`
- 删除全部 16 个 `ensure_*` 函数

**验收**：新字段只需改 model + `alembic revision --autogenerate`；旧数据库可无损升级；`initializer.py` < 50 行。

**坑**：SQLite 的 ALTER 能力有限，alembic 需开 `render_as_batch=True`（batch migration）。迁移前自动备份 db 文件。

### 2. SQLite 并发写加固（WAL）

**问题**：`db/session.py` 只设了 `connect_args={"timeout": 30}`。当前至少 4 类线程并发读写同一个 SQLite 文件（API 请求、news scheduler、market quote producer、notification delivery 线程），默认 journal 模式下写锁互斥，靠 30 秒 timeout 硬扛，高峰期仍可能 `database is locked`。

**方案**：
- engine 上挂 `connect` 事件，每连接执行 `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=30000; PRAGMA foreign_keys=ON`
- 长事务审查：摄入批量写入控制在单事务 ≤ 数百行，避免长写锁
- 文档注明：WAL 模式下 db 文件变三个（`-wal`/`-shm`），备份脚本需配合 `VACUUM INTO` 或 checkpoint

**验收**：并发摄入 + API 读压测无 locked 报错；读不再被写阻塞。

### 3. 事件总线 handler 异常隔离

**问题**：`InMemoryEventBus.publish()` 顺序同步调用所有 handler，**无 try/except**。`news.created_batch` 有两个订阅者（信号管线 + 通知），第一个抛异常会：① 跳过第二个 handler（通知丢失）；② 异常向上传播到 publisher，即新闻摄入线程，可能打断整次抓取循环。

**方案**：
- `publish()` 内对每个 handler 单独 try/except，记录 `logger.exception` + 计数器（handler 名、event 名）
- 失败信息写入 `EventBusStatus.last_error`，暴露到现有 runtime status 接口
- 可选：handler 失败次数指标，供前端 SourceHealthGrid 类似的运维面板展示

**验收**：单测——首个 handler 抛异常时，第二个 handler 仍被调用，publish 不向外抛。

### 4. 重负载事件 handler 移出同步发布链路

**问题**：`main.py::handle_news_created_batch` 在事件回调里**同步**执行整条信号管线（`NewsSignalPipelineService`，含 LLM 调用），再逐条 `news_repo.get_by_id(news_id)`（N+1 查询）。发布者（摄入调度线程）被阻塞到 LLM 全部返回，新闻量大时摄入节奏被 AI 延迟拖垮。

**方案**：
- 引入轻量内存任务队列（`queue.Queue` + 专职消费线程，纳入第 9 项的 worker 管理框架），事件 handler 只做「入队」
- N+1 修复：`get_by_id` 循环改 `WHERE id IN (...)` 一次批量查询
- 队列深度、处理延迟写入 `worker_runtime_status` 心跳

**验收**：摄入 tick 耗时与 LLM 耗时解耦（摄入侧只剩入队开销）；队列堆积可在 runtime status 中观测。

**坑**：进程内队列重启即丢——当前事件本身就是 best-effort（与现有 hybrid bus 语义一致），可接受；若将来要可靠性，再切 Redis Stream 消费者，接口先留好。

---

## P1 — 架构与安全

### 5. LLM api_key 加密存储 + 响应脱敏

**问题**：`llm_provider_config.api_key` 是 `Text` 明文列；需确认 API 响应是否原样返回 key。`.env` 虽已 gitignore，但 DB 文件本身可能被同步/备份到不安全位置。

**方案**：
- 用 `cryptography.Fernet` 对称加密落库，密钥来自环境变量 `NEWS_CAUGHT_SECRET_KEY`（首次启动自动生成并写入本地文件，权限 600）
- API 读取接口一律返回掩码（`sk-***last4`），仅写入时接收完整 key
- 迁移：alembic data migration 把存量明文加密（依赖第 1 项先行）

**验收**：DB 文件 strings 搜不到明文 key；前端设置页正常保存/使用。

### 6. `news_ingestion.py`（1010 行）模块拆分

**问题**:单文件混杂抓取、解析、去重接线、落库、源健康更新、线程池编排，是改动热区，AI/人改它的回归风险最高。

**方案**（按职责拆为包 `app/services/ingestion/`）：

```text
ingestion/
├── fetcher.py        # HTTP 抓取 + ThreadPoolExecutor 编排
├── parser.py         # RSS/HTML 解析 → 标准化 NewsDraft
├── dedup_gate.py     # 调 news_dedup（精确签名 + simhash + 二次判重）
├── persister.py      # 批量落库 + 事件发布
├── health.py         # source_health 更新
└── service.py        # 编排入口，保持原对外 API 不变
```

- 严格只移动不改逻辑（mechanical refactor），现有 `test_news_ingestion.py` 全绿作为安全网
- 对外入口签名不变，调用方零改动

**验收**：每个文件 < 300 行；原测试套件不改一行即通过。

### 7. 新闻列表 keyset 分页

**问题**：`GET /api/news` 只有 `limit ≤ 500`，无 cursor/offset。前端永远只能看最近 N 条，历史数据落库即不可达；且未来数据量大时一次拉 500 条全量序列化浪费。

**方案**：
- keyset 分页（非 offset）：`?cursor=<published_at>,<id>&limit=50`，按 `(published_at DESC, id DESC)` 复合排序，加对应索引
- 响应包裹 `{ items, next_cursor }`（注意：现接口返回裸数组，属 breaking change，前端 `newsStore` 同步改）
- 前端 NewsFeedView 接无限滚动（已有 `useVirtualList`，只差数据侧翻页）

**验收**：可连续翻页到最早数据；EXPLAIN 显示走索引而非全表扫。

### 8. 数据生命周期：保留策略 + 清理任务

**问题**：grep 全库无 retention/cleanup/vacuum 实现。`news_item`、`article_content`（正文全文）、`price_snapshot`（15 秒级轮询产物）无限增长，price_snapshot 是最快的膨胀点。

**方案**：
- 配置化保留期：`news_item` 180 天 / `article_content` 90 天 / `price_snapshot` 30 天 /（X 相关表同理）
- 挂到现有 scheduler 框架，每日低峰执行；分批 DELETE（每批 ≤ 1000 行）避免长写锁
- 每周 `PRAGMA incremental_vacuum`（需开 `auto_vacuum=INCREMENTAL`，注意：该 pragma 对已有库需 VACUUM 一次才生效，放进第 1 项的迁移流程）
- 清理结果写日志 + runtime status

**验收**：构造过期数据后任务正确清理且不删关联未过期数据（topic_news_link 等外键关系处理干净）。

### 9. Worker 线程统一生命周期管理

**问题**：后台线程散落 4+ 处、模式各异：`NewsIngestScheduler`（Event+Thread）、`MarketQuoteProducer`（Event+Thread）、`NotificationService`（`time.sleep` 轮询，停机最长等一个 poll 周期）、`stock_news_search`（临时起线程，无人回收）。无统一启停顺序、无统一心跳、`time.sleep` 不可中断。

**方案**：
- 抽 `BaseWorker`：统一 `start()/stop()`、用 `Event.wait(interval)` 替换所有 `time.sleep`（立即可中断）、统一异常兜底重启策略、统一心跳写 `worker_runtime_status`
- `lifespan` 中以注册表统一管理：启动按依赖序、停机逆序、带超时 join
- 临时线程（stock_news_search）收编为共享 `ThreadPoolExecutor`

**验收**：Ctrl-C 后全部线程 ≤ 2 秒内退出；每个 worker 在 runtime status 接口可见心跳。

---

## P2 — 工程化与前端

### 10. CI 流水线

**问题**：无 `.github/`，ruff/pytest/vitest 全靠本地自觉，多 AI 协作开发时回归无门禁。

**方案**：GitHub Actions 两个 job——后端（`ruff check` + `pytest`）、前端（`vue-tsc --noEmit` + `vitest run` + `vite build`）。PR 必跑，缓存 pip/npm。

**验收**：故意引入类型错误的 PR 被 CI 拦截。

### 11. 前端类型从 OpenAPI 自动生成

**问题**：`frontend/src/types/api.ts` 680 行手写类型，与后端 Pydantic schema 是两份真相，漂移只能靠运行时发现。

**方案**：
- 后端 CI 步骤导出 `openapi.json`（FastAPI 自带）
- `openapi-typescript` 生成 `types/generated.ts`，手写文件逐步改为 re-export
- CI 加 drift check：生成结果与提交不一致即失败

**验收**：改 Pydantic schema 忘记同步前端时 CI 报错。

### 12. 前端巨型组件拆分

**问题**：`KlineChart.vue` 903 行、`KlineDrawingOverlay.vue` 715 行、`DashboardView.vue` 646 行。K 线相关逻辑（指标、画图、overlay 几何）虽已有 utils 拆分，但组件本体仍堆叠图表初始化、事件绑定、状态同步。

**方案**：
- KlineChart → composables：`useKlineChart`（实例生命周期）、`useKlineIndicators`、`useKlineMarkers`、`useChartResize`
- DashboardView → 按区块拆子组件（已有 HeroMetrics/TopicBoard 模式，照搬）
- 遵守既有约定：涨跌配色为**红涨绿跌**，拆分时不得改动配色逻辑
- 每个 composable 配套 vitest（项目已有良好测试惯例）

**验收**：单文件 < 350 行；现有组件测试全绿。

### 13. 去重灰区 embedding 二次判重落地

**问题**：`news_dedup.py` 的 `SecondaryDuplicateJudge` 目前是 `NullSecondaryDuplicateJudge` 占位——simhash 距离 4~6 的灰区一律按不重复处理，跨源改写标题会漏判。

**方案**：
- 实现 `EmbeddingDuplicateJudge`：复用现有 `llm_providers` 的 embedding 能力（或本地 sentence-transformers 走可选依赖），余弦相似度 > 阈值判重
- 结果带 LRU 缓存（标题对 → 判定），控制 LLM 调用成本
- 配置开关 `dedup_secondary_judge: null | embedding`，默认 null（保持现状），灰度验证后再切
- **保留现有 Protocol 接口不动**（既定决策）

**验收**：构造改写标题用例集，灰区召回率提升且误杀率可控（用例进 `test_news_dedup.py`）。

---

## 建议实施顺序

```text
Phase 1（地基，~3 天）   : #1 Alembic → #2 WAL → #3 事件隔离
Phase 2（解耦，~4 天）   : #4 异步管线 → #9 worker 治理 → #5 key 加密
Phase 3（重构，~5 天）   : #6 ingestion 拆分 → #7 分页 → #8 数据清理
Phase 4（工程化，~4 天） : #10 CI → #11 类型生成 → #12 组件拆分 → #13 embedding 判重
```

依赖关系：#5、#8 依赖 #1（需要迁移框架）；#4 依赖 #9 的 BaseWorker 更优但可并行；#11 依赖 #10 的 CI 骨架。

**给后续开发 AI 的统一红线**：① 所有重构以现有测试全绿为前提，先跑 `make test` 建立基线；② SQLite 相关改动前备份 `backend/data/*.db`；③ 不引入 Postgres/重型消息队列——本项目刻意保持单机轻量；④ 前端涨跌色为红涨绿跌，不得按欧美惯例"修正"。
