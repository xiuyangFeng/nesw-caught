# 情绪评测模块重构（Phase 1）设计 — 2026-08-02

## 背景与问题（诊断结论）

现状 `/eval/sentiment` 模块的四个结构性问题：

1. **评测对象错位**：只评纯词典规则分类器（`allow_llm=False` 写死），"A/B"是同一分类器的两套阈值（±0.20 vs ±0.10），不是真实模型对比。
2. **金标自证其说**：仅 20 条手写造句，用词与规则词典同源，指标虚高、无泛化意义；没有任何采样/标注/复核脚本（对比 market_relevance 有完整 6 脚本链路）。
3. **无闭环**：评测结果不落库、无历史趋势、无回归告警；`news_sentiment_report.py` 全文件死代码。
4. **两个实打实 bug**：
   - `llm_providers.analyze_json` 的 system prompt（要求 `top_pick/candidates/risk_notes/sentiment/context_limitations`）与情绪分类器 user prompt（要求 `sentiment_label/sentiment_score/keywords/topic_title_hint/takeaway`）schema 冲突，LLM 精修大概率静默失效回退规则；
   - LLM 分类缓存 key 只含 (title, summary, market) 不含 prompt/用途，情绪分类与选股分析会互相命中对方缓存，拿到错误 schema。

## Phase 1 目标

1. 修上述两个 bug（工作块 A）。
2. 金标数据集工具链：从真实 `NewsItem` 采样 → LLM 预标注 → 人工复核 → 合并金标（工作块 C）。
3. 评测核心重构：真 A/B（规则 vs LLM vs 混合）、输入对齐线上路径、结果落库 + 历史 + 回归对比、盘活 report 死代码（工作块 B）。
4. 前端评测页改版适配（工作块 D）。

不在 Phase 1 范围：回测方法学修复、置信度校准、情绪时间线、背离提醒（Phase 2/3）。

## 接口契约（B 与 D 共同遵守，此文档为准）

### 金标样本 schema（已由主协调者预改好，见 `app/schemas/sentiment_eval.py`）

`SentimentGoldSample` 新增可选字段（全部向后兼容，旧格式文件可直接加载）：

- `title: str | None`、`summary: str | None`、`body: str | None` — 与线上分类输入对齐；缺省时以 `text` 充当 title（legacy 行为）。
- `market: str | None` — 命中市场（如 `us` / `cn-a` / `hk`），影响中英词典路径。
- `news_id: int | None` — 采样来源 NewsItem id（可追溯）。

评测时输入构造规则：`title = sample.title or sample.text`，`summary = sample.summary`，`body = sample.body`，`market = sample.market`。

### 新数据表 `sentiment_eval_run`（alembic 迁移，B 负责，注意保持单 head）

| 列 | 类型 | 说明 |
|---|---|---|
| id | int pk | |
| batch_id | str (uuid) | 一次 POST 触发的多个模型 run 同 batch |
| created_at | datetime (UTC) | |
| dataset_path | str | |
| dataset_hash | str | 金标文件内容 sha256 前 16 位 |
| sample_count | int | |
| model_name | str | `rule-baseline` / `llm:<provider>/<model>` / `hybrid:<provider>/<model>` |
| config_json | JSON str | 阈值、provider、model 等 |
| accuracy / macro_f1 | float | |
| per_label_json / confusion_json | JSON str | |
| note | str nullable | |

### API

**`POST /api/eval/sentiment/run`** — 执行评测并落库，返回 `SentimentEvalResponse`：

- 永远评：`rule-baseline`（±0.20 阈值，title+summary+body 全量输入）。
- 若存在激活的 LLM provider 配置：追加评 `llm:<provider>/<model>`（纯 LLM 分类，专用情绪 prompt，见下）与 `hybrid:<provider>/<model>`（生产路径 `classify(allow_llm=True)` 的标签）。LLM 调用失败的样本回退规则结果并在 note 中计数说明。
- 无 LLM 配置时降级：A/B 退回两套阈值对比（legacy 行为），note 说明"未配置 LLM，仅规则阈值对比"。
- comparison 固定为 `model_a = rule-baseline`，`model_b = llm`（有 LLM 时）或 `rule-sensitive (±0.10)`（无 LLM 时）。

**`GET /api/eval/sentiment`** — 只读，不再触发计算：返回最近一个 batch 的持久化结果 + 历史。库里无记录时若金标存在，返回 `available=True` 且 `primary=None`、note 提示"尚无评测记录，请点击重新评测"；金标缺失仍 `available=False`。

### `SentimentEvalResponse` 扩展（additive，向后兼容）

新增字段：

- `evaluated_at: datetime | None` — 最近 batch 时间。
- `runs: list[SentimentModelRun]` — 本 batch 全部模型 run（含 rule/llm/hybrid），`primary` 保留为 rule-baseline。
- `llm_available: bool` — 是否有激活 LLM 配置。
- `history: list[SentimentEvalHistoryPoint]` — 最近 20 个 batch 摘要，字段：`batch_id, evaluated_at, dataset_hash, sample_count, entries: list[{model_name, accuracy, macro_f1}]`。
- `regression: SentimentEvalRegression | None` — 最新 batch 与上一个同 `dataset_hash` batch 的同名模型对比；`macro_f1` 下降超过 0.02 时 `regressed=True`，字段：`model_name, previous_macro_f1, current_macro_f1, delta, regressed`。多个模型有回归时取跌幅最大者，其余写进 note。
- `metrics` 内新增 `importance_weighted_accuracy: float | None` — 有 importance 标注的样本按权重的加权准确率（无标注样本权重 1.0；全部无标注时为 None…实现按"任一样本有 importance 则计算"）。

### 纯 LLM 情绪分类（B 负责，新文件 `app/services/news_sentiment_llm_classifier.py`）

- 独立的 system prompt（与 user prompt schema 一致）：要求仅返回 JSON `{"sentiment_label": "positive|negative|neutral", "sentiment_score": -1~1}`。
- 通过 A 改造后的 `analyze_json(system_prompt=..., cache_scope=...)` 参数化入口调用（A 的契约见下），不复用选股分析的 prompt。
- 包装成 `ClassifyFn`（`experiment_runner.py` 已支持注入），逐样本调用，单样本异常→回退规则分类并计数。

### 工作块 A 的契约（llm_providers 参数化）

- `analyze_json(...)` 新增可选参数：`system_prompt: str | None = None`（None 时用现有默认选股 system prompt，行为不变）与 `cache_scope: str | None = None`。
- 缓存 key 改为包含 `cache_scope`（或 system_prompt 摘要）：`compute_classification_fields_hash` 增加 scope 参数，默认值保持旧行为兼容存量缓存（选股分析路径 scope=`news_analysis`，情绪路径 scope=`sentiment`；至少保证两条路径 key 不同）。
- `news_signal_classifier._llm_refine` 传入与其 user prompt 匹配的专用 system prompt + `cache_scope="sentiment"`，并对 LLM 返回缺 key/类型错误的情况保留现有回退行为，但**新增失败计数/日志**（不再完全静默）。

### 数据集工具链（C 负责，`backend/scripts/`，镜像 market_relevance 链路风格）

1. `sample_sentiment_dataset.py` — 从 DB 按市场 × 现有 sentiment_label 分层采样 N 条（默认 300，参数化），输出候选 JSONL（含 news_id/title/summary/body/market/现有标签）。
2. `annotate_sentiment_dataset.py` — 对候选做 LLM 预标注（active provider，缺配置时回退规则分类并标记 `annotator: "rule"`），输出待复核 JSONL（含预标注标签 + 一句话理由 + status=pending）。
3. `review_sentiment_annotations.py` — 终端逐条复核（接受/改标/跳过），确认后经 `save_gold_samples()`（现有死代码，正好接线）合并进金标 JSON（默认写新文件，不覆盖内置 20 条演示集；提供 `--output`）。
4. 内置演示金标保留不动，`sentiment_eval_dataset_file` 配置指向新集。

### 实验报告脚本（B 负责，盘活 `news_sentiment_report.py`）

`backend/scripts/run_sentiment_experiment.py` — 离线跑一遍评测（参数：数据集路径、是否含 LLM），用 `build_sentiment_report` + `render_sentiment_report_markdown` 输出 Markdown 到 `backend/data/research/experiments/sentiment/<date>/report.md`。

### 前端（D 负责）

- `SentimentEvalView.vue` 改版：
  - "重新评测"按钮 → `POST /api/eval/sentiment/run`（loading 态），完成后刷新 GET。
  - 页面加载只 GET（不再隐式触发计算）。
  - 概览卡增加：评测时间、回归徽章（`regression.regressed` 时红色警示 + delta）。
  - 模型 run 卡片支持 1~3 个（rule / llm / hybrid），A/B 对比区沿用现有布局。
  - 历史区块：最近 batch 的 macro_f1 走势（简单 SVG 折线或表格，风格与站内一致），无历史时空状态。
  - `llm_available=false` 时显示提示"未配置 LLM，当前仅规则阈值对比"，并链接 `/settings/llm`。
- `types/api.ts` additive 扩展（手写补充类型，遵循现有 `SentimentEvalLabel` 手写先例；`types/generated/api.d.ts` 若有再生成脚本则再生成，否则按项目既有模式处理）。
- `api/client.ts` 新增 `runSentimentEval()`；mock 侧补充对应夹具。

## 验证要求（全部工作块）

- 后端：TDD，先写失败测试；`conda run -n news-caught pytest backend/tests/<相关文件> -q` 全绿；不破坏既有测试。
- 前端：相关 `*.test.ts` + `npm --prefix frontend run build`（vue-tsc）通过。
- 各工作块**不要**改 `docs/code-change-log.md`（由主协调者统一回填，避免冲突）。
- 各工作块只改本块契约内文件；发现必须越界修改时，在结果中说明而不是直接改。
