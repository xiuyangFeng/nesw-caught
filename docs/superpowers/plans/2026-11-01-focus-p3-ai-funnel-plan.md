# 聚焦改造 P3：AI 漏斗（2026-11-01）

> 设计依据：[2026-10-31-focus-redesign-design.md](../specs/2026-10-31-focus-redesign-design.md) §5.1～§5.3、§7。
> 分支：`feature/focus-p3`（基于 `fix/topic-clustering`）。

## 0. 用户确认（2026-11-01）

1. **关注板块**：AI 根据持仓与自选推断，用户可在自选页增删。板块名取东方财富行业/概念板块名称。
2. **提醒接管**：AI 为主、关键词兜底。AI 判定持仓受影响（利多/利空且强度 ≥ 中）才发持仓新闻提醒；AI 关闭、未配置或处理失败时回退到 P2 的关键词规则。AI 另外负责新增海外重大事件、关注板块、新机会提醒。
3. **terra 接入**：OpenAI 兼容的中转地址，用户在"模型设置"页自行填写地址与密钥，并设为默认模型。

## 1. 现状（实测，2026-11-01）

- `AI_ENABLED` 未开启，库里 21,435 条 `news_signal_result` 全是规则结果，从未自动调用过 LLM。
- `llm_provider_config` 只有一条 DeepSeek，单价按"每 1K token"存为输入 0.02、输出 1.0，即每百万 $20 / $1000，账本成本失真。
- `llm_token_usage` 只记模型、token 数和粗粒度 `operation_type`，费用在读取时按 1K 单价现算；月度预算只展示，不生效。
- 没有任何个股→板块数据；只有 `board_provider` 的东财行业板块行情榜（进程内缓存）。
- 调用层 `OpenAICompatibleProvider.complete(..., response_format=json_object)` 已有重试与故障切换，可直接复用。

## 2. 方案

### 2.1 数据（Alembic 新迁移）

| 表 | 用途 | 关键字段 |
|---|---|---|
| `news_ai_screen` | L1 粗筛结果，每条新闻一行 | `news_id`(唯一)、`importance` 0～3、`overseas`、`deep_read`(是否进 L2)、`title_zh`(外文标题译文)、`reason`、`status` ok/error、`error`、`model_name`、`screened_at` |
| `news_ai_analysis` | L2 精读结论，每条新闻一行 | `news_id`(唯一)、`summary_zh`、`view`(明确看法)、`major`(是否重大事件)、`status`、`error`、`model_name`、`analyzed_at` |
| `news_impact` | 结构化影响，每条新闻多行 | `news_id`、`target_type` stock/sector、`target_code`(股票代码，板块为空)、`target_name`、`direction` bullish/bearish/neutral、`strength` strong/medium/weak、`rationale`、`source` ai/user |
| `impact_correction` | 用户修正记录（传导规则） | `news_id`、`news_title`、`before_json`、`after_json`、`note`、`created_at` |
| `stock_sector` | 个股所属板块（AI 推断） | `symbol`、`sector`、`source` ai/user、唯一 (`symbol`,`sector`) |
| `focus_sector_override` | 用户对关注板块的增删 | `sector`(唯一)、`action` add/remove |

关注板块 = 自选/持仓股的 `stock_sector` 并集 + 用户 add − 用户 remove。

`llm_provider_config` 的 `input_price_per_1k` / `output_price_per_1k` 改为 `input_price_per_1m` / `output_price_per_1m`。存量数值不变：DeepSeek 那条按每百万重新解读为 $0.02 / $1.0，不再失真。`llm_token_usage` 结构不变，新增 `operation_type`：`ai_screen`、`ai_impact`、`sector_infer`。

### 2.2 漏斗服务（全部用默认模型 `get_default()`，JSON 模式）

- **L1 `NewsScreenService`**：取最近 24 小时未筛的新闻，每批 20 条，只用标题 + 摘要（摘要截 200 字）。上下文是持仓、关注股、关注板块清单。每条输出：`importance`、`overseas`、`deep_read`、`title_zh`、`reason`。输出逐条校验，缺条、错 id、越界值按"该条失败"处理，不拖累整批。
- **L2 `NewsImpactService`**：取 `deep_read` 且 `importance ≥ 2` 的新闻，按重要度、时间排序，每日上限 300 条（配置项）。输入全文（截 4,000 字，无正文用摘要）+ 持仓/关注/关注板块 + 最近 8 条用户修正作为示例。输出：`summary_zh`、`view`、`major`、`impacts[]`。板块名要求从候选列表里选（东财行业板块名 + 已有关注板块）。
- **板块推断 `SectorInferenceService`**：自选股新增、或某只股没有 `stock_sector` 时，调用一次，返回 1～3 个板块名。
- **失败降级**：单批失败记 `status=error`，下个周期最多重试 2 次；不阻塞新闻主链路。
- **月度预算**：模型配置了 `monthly_budget_usd` 且本月费用已达预算时，漏斗暂停，提醒回退关键词规则；状态接口如实显示。

### 2.3 Worker

新增 `AiFunnelWorker`（`BaseWorker`），每 30 秒一个周期：先跑 L1 一批，再跑 L2 最多 5 条，再补一次板块推断。以下情况不调用 LLM，直接空转：没有默认模型配置、`AI_FUNNEL_ENABLED=false`、超出预算。单进程模式在 `main.py` 启动，多进程模式在 `pipeline_worker_main.py` 启动。

### 2.4 提醒（改 `alert_service`）

- **AI 健康判定**：漏斗已启用、有默认模型、未超预算时，视为 AI 模式。
- **AI 模式**：`on_news_batch` 不再按关键词发持仓提醒，由漏斗在 L2 完成后调用 `on_news_impacts(news, analysis, impacts)`：
  - 持仓股影响为利多/利空且强度 ≥ 中 → `holding_news` 立即提醒，去重键沿用 `news:{id}:{symbol}`，正文带方向·强度与理由；
  - 自选（非持仓）股同样条件 → 进 30 分钟合并窗口（沿用 `watch_news_digest`）；
  - 关注板块受影响（强度 ≥ 中）→ 合并窗口，新 kind `sector_news`；
  - 海外新闻 `major=true` → `overseas_major` 立即提醒，每天最多 5 条；
  - 自选外个股"利多·强" → 合并窗口，新 kind `opportunity`。
- **兜底**：AI 不健康时 `on_news_batch` 照旧走关键词规则。新闻在 L1/L2 最终失败（重试用尽）时，漏斗对该条调用关键词规则补发，保证不漏。
- **防刷屏**：每只股票当天 AI 新闻提醒最多 5 条（超出的进合并窗口）。夜间静默沿用 P2。

### 2.5 接口

- `GET /api/news/{id}/ai`：返回 `screen`、`analysis`、`impacts`。
- `PUT /api/news/{id}/impacts`：用户提交修正后的影响列表（整表替换，`source=user`），同时写 `impact_correction`。
- `GET /api/watchlist/{symbol}/impacts?limit=`：该股最近的 AI 影响。
- `GET /api/focus-sectors`；`POST /api/focus-sectors`（`{sector}`）；`DELETE /api/focus-sectors/{sector}`。
- `GET /api/ai/funnel/status`：开关、模型、今日 L1/L2 条数、今日与本月 token 和费用、预算状态、最近错误。
- LLM 配置接口的单价字段改名为 `*_per_1m`（前端同步）。

### 2.6 前端

- 新闻详情：替换旧"LLM 标的分析"卡为"AI 影响"卡，显示重要度、译文标题、结论与看法，以及影响列表（方向·强度色块）。卡上可编辑：改方向/强度、删除、新增（个股或板块），保存即提交修正。
- 个股详情：新增"AI 影响"区块，列出最近影响。
- 自选页：顶部显示"关注板块"标签，可删除 AI 推断的板块、手动添加。
- 模型设置：单价标签改为"$/百万 tokens"；预设里加 terra（地址留空，由用户填写）；新增漏斗状态卡（今日条数、token、费用、预算）。
- 提醒页：新 kind 的标签与配色。

## 3. 任务

| # | 任务 | 验收 |
|---|---|---|
| T1 | 单价改每百万（迁移 + 计费 + 前端标签），terra 预设，漏斗配置项 | 迁移往返测试、计费单测 |
| T2 | 六张新表的模型与迁移 | `test_migration_parity`、往返 |
| T3 | L1 粗筛服务（prompt、校验、写库） | LLM mock 单测：正常、缺条、错 id、整批失败 |
| T4 | L2 精读服务（全文、修正示例、每日上限） | mock 单测：解析、上限、失败重试 |
| T5 | 板块推断 + 关注板块计算与接口 | mock 单测 + 接口测试 |
| T6 | `AiFunnelWorker`、注册、预算暂停、状态接口 | 单测：无配置空转、超预算暂停、周期顺序 |
| T7 | 提醒接入（AI 模式 / 兜底 / 新 kind / 每日上限） | 单测覆盖每条规则与回退 |
| T8 | 新闻 AI 接口、修正接口、个股影响接口，重新生成 `openapi.json` 与类型 | 接口测试、`check:api-drift` |
| T9 | 前端（新闻详情、个股详情、自选关注板块、模型设置、提醒页） | vitest + build |
| T10 | 文档、评审、实测 | 用户配好 terra 后跑一个真实交易日，按 `operation_type` 统计 token |

## 4. 不做

- 板块行情异动提醒（需要板块代码映射与行情，放到 P4 盯盘台一起做）。
- 盘后简报、明日关注、早间隔夜简报（P4）。
- 旧的情绪 LLM 复核与 takeaway（仍由 `AI_ENABLED` 控制、默认关闭，P4 视简报方案决定去留）。

## 5. 风险

- 中转地址的 JSON 模式兼容性未知：解析失败按单条失败处理，并在状态卡显示错误。
- AI 模式下持仓新闻提醒要等 L1 + L2 完成（预计 1 分钟内），比关键词规则慢。
- 首次启用时 24 小时内的存量新闻会集中跑 L1（约 2,000 条 ≈ 100 次调用），属一次性开销。
