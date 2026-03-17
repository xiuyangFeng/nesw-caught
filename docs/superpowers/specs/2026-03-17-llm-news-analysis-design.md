# 新闻详情页 LLM 标的分析设计

## 背景

当前项目已经具备新闻抓取、主题聚合、自选股和独立的 `X Monitor` 增强模块，但“从新闻正文中识别值得关注的股票标的”仍然缺失。现状有两个限制：

1. 新闻主链路没有通用的 LLM provider 抽象，无法稳定切换不同模型提供商。
2. `X Monitor` 依赖 `grok-bridge` 的 X 内容抽取链路，它服务的是 X 查询场景，不适合直接复用到新闻详情分析。

本轮目标是在不改变新闻抓取主链路的前提下，为新闻详情页增加一个手动触发的 LLM 分析能力，并把 provider 设计成可切换、可扩展。

## 目标

- 在新闻详情页提供“分析标的”入口，由用户手动触发单条新闻分析。
- 支持多 provider 切换，后端统一保存当前启用的 provider、模型和 API Key。
- 分析结果以结构化形式返回，至少包括：
  - 最值得关注的一个标的
  - 候选股票列表
  - 推荐理由
  - 摘要、风险提示、情绪和置信度
- 分析结果落库，便于详情页复用最近一次结果，避免每次打开都重复调用模型。

## 非目标

- 不把 LLM 接入新闻抓取、定时刷新或主题聚合主链路。
- 不与 `X Monitor` 共用 prompt、返回 schema 或 provider client。
- 不在第一版中实现多用户各自保存 API Key 的前端设置页。
- 不根据分析结果自动加入自选股、推送通知或生成交易建议。

## 方案

### 1. 以“新闻详情页手动触发”作为唯一入口

用户仅在 [NewsDetailView.vue](/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/views/NewsDetailView.vue) 中主动点击按钮时，才会触发 LLM 分析。这样可以控制成本、减少不必要调用，并把失败影响局限在单条详情页。

后端分析输入按以下优先级组装：

- 新闻标题
- 新闻摘要
- 已抓取正文
- 来源、市场、发布时间等元数据

若正文缺失，则退化为“标题 + 摘要”分析，但结果中需要标记上下文不足。

### 2. 新增独立的 LLM provider 抽象层

后端新增一层独立于 `X Monitor` 的 provider 抽象，例如：

- `LLMProviderClient` 接口
- `OpenAICompatibleProvider`
- 后续可扩展 `AnthropicProvider`、`ZhipuProvider` 等

第一版以统一请求/响应接口为准，不要求一次性覆盖所有厂商特有能力。核心要求是：

- 输入统一为 prompt + schema 约束
- 输出统一为结构化 JSON
- provider 配置可切换
- 错误语义明确，可区分“未配置”“鉴权失败”“网络失败”“模型返回非法结构”

### 3. 配置与分析结果分离建模

后端新增两类持久化对象。

`llm_provider_config` 负责保存当前启用配置：

- `provider_name`
- `display_name`
- `base_url`
- `model_name`
- `api_key`
- `is_active`
- 时间戳

当前阶段默认是单租户使用，因此后端保存一套活动配置即可。后续若要支持多人共用，可在此模型基础上扩展“每用户配置”或“前端设置页录入”。

`news_analysis_result` 负责保存对某条新闻的最近分析结果：

- `news_id`
- `provider_name`
- `model_name`
- `analysis_status`
- `top_pick_symbol`
- `top_pick_market`
- `top_pick_reason`
- `summary`
- `risk_notes`
- `sentiment`
- `raw_response_json`
- `analysis_error`
- `analyzed_at`

这样可以保证 provider 配置切换和分析结果缓存互不耦合。

### 4. 使用固定 JSON schema 约束模型输出

模型输出必须是固定 JSON，而不是自由文本。推荐结构如下：

```json
{
  "top_pick": {
    "symbol": "NVDA",
    "market": "us",
    "company_name": "NVIDIA",
    "confidence": 0.82,
    "reason": "..."
  },
  "candidates": [
    {
      "symbol": "NVDA",
      "market": "us",
      "company_name": "NVIDIA",
      "confidence": 0.82,
      "reason": "..."
    }
  ],
  "summary": "...",
  "risk_notes": "...",
  "sentiment": "positive",
  "context_limitations": "..."
}
```

约束原则：

- `top_pick` 允许为空，表示无明确首选标的
- `candidates` 可为空数组
- `market` 统一为 `us/hk/cn`
- `sentiment` 统一收敛到有限枚举
- 解析失败时整体记为 `error`，不向前端暴露半结构化垃圾文本

### 5. 前后端接口拆分为“配置”和“分析”两组

后端新增接口建议如下：

- `GET /api/llm/config`
  - 返回当前活动配置的非敏感信息，以及是否已配置可用 key
- `POST /api/llm/config`
  - 新增或更新当前活动 provider 配置
- `GET /api/news/{news_id}/analysis`
  - 返回该新闻最近一次分析结果
- `POST /api/news/{news_id}/analyze`
  - 手动触发分析，并返回最新结构化结果

前端交互建议如下：

- 进入新闻详情页时，先加载新闻详情，再读取已有分析结果
- 若未配置 provider，则展示“尚未配置 LLM”
- 若已有历史结果，则直接展示，并标注 `provider + model + analyzed_at`
- 用户点击“重新分析”时，再调用触发接口

### 6. UI 聚焦“首选标的 + 候选列表”

前端在详情页新增一块独立 section，展示：

- 首选标的卡片
  - 股票代码、市场、公司名
  - 置信度
  - 推荐理由
- 候选列表
  - 每个标的的代码、市场、置信度、理由
- 附加信息
  - 摘要
  - 风险提示
  - 情绪
  - provider/model

第一版不加入“加入自选股”快捷动作，避免把模型分析直接导向交易行为。

## 风险与取舍

- 单租户后端保存 API Key 上线最快，但后续多人共享时需要补前端设置页和权限边界。
- 模型输出即使被 JSON schema 约束，也可能给出不可靠结论，因此结果必须明确标识为“分析建议”，而不是事实字段。
- 如果新闻正文缺失，退化分析会降低准确率，所以接口需要向前端暴露 `context_limitations`。
- provider 切换后，旧结果可能与当前活动 provider 不一致，因此详情页必须展示结果的 provider/model 来源，避免误判为最新配置生成。
- 第一版不接入自动触发、通知、自选股联动，可以显著降低复杂度，但用户需要手动点击才能得到结果。

## 验证思路

- 后端配置接口测试：未配置、保存配置、覆盖配置、读取脱敏配置
- 后端分析接口测试：新闻不存在、正文缺失、provider 未配置、provider 调用失败、模型返回非法 JSON、成功返回结构化结果
- 前端详情页测试：未配置、无结果、分析中、成功、失败五种状态
- 最小回归验证：
  - `conda run -n news-caught pytest backend/tests`
  - `npm --prefix frontend run build`
