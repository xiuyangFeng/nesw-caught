# news-caught 第二轮优化迭代设计方案

为了进一步提升系统的稳定性和智能化运维能力，本轮优化侧重于**可观测性（大模型 Token 审计）、高可用容灾（主备降级切换）及交互细节（自选股添加模糊搜索与自动补全）**。

---

## 1. 详细设计方案

### 1.1 模块 1：大模型 Token 审计与额度消耗统计
*   **目的**：为系统在后台自动分析新闻时的模型调用行为提供可见性，便于统计每日/每月算力成本。
*   **数据库模型 (`app/models/llm_token_usage.py`)**：
    新建 `LLMTokenUsage` 表，包含字段：
    - `id`
    - `model_name` (模型名称)
    - `prompt_tokens` (输入 token 数)
    - `completion_tokens` (输出 token 数)
    - `total_tokens` (总 token 数)
    - `operation_type` (业务分类，如 "chat", "analysis", "signal", "translate")
    - `created_at` (记录时间)
*   **后端记录机制**：
    在 `app/services/llm_providers.py` 的同步和异步请求拦截处：
    - 成功获取 completions 响应后，提取 payload 中的 `usage` 字典。
    - 针对流式 SSE 响应，在 `chat_stream` 结束时根据产出字符数以及 prompt 长度进行估算（若 API provider 支持 `stream_options.include_usage` 则优先取真实值）。
    - 触发异步/同步写入 `LLMTokenUsage` 表。
*   **API 接口设计**：
    新增 `GET /api/llm/stats`：
    - 返回历史总 token 计数，按模型、业务分类的分组统计。
*   **前端展示**：
    在 `LlmSettingsView.vue` 顶部新增 **“模型额度审计控制台 (LLM Usage Dashboard)”**：
    - 科技霓虹风格面板，展示累计总 Token 数、输入/输出比例。
    - 按模型和业务展示消耗分布，直观反应哪些新闻分析消耗了最多 Token。

### 1.2 模块 2：大模型连接异常自动容灾备份切换 (Failover)
*   **目的**：解决单一模型配置下，遇到限流（429）或网络服务超时（503）时整个新闻分析管道或聊天挂掉的问题。
*   **方案**：
    - 在 `LLMProviderConfigRepository` 中新增 `get_backup(exclude_id)` 逻辑：获取当前**其他已激活（`is_active = True`）**的模型配置。
    - 增强 `OpenAICompatibleProvider` 与 `AsyncOpenAICompatibleProvider`：
      - 执行 completions / embeddings / chat_stream 请求时，如果抛出 `LLMProviderError` 或 `httpx` 连接异常，且当前除当前配置外还有其他 active 的配置：
      - 自动切换为备用配置，重新构建 provider 并自动重试（递归上限 1 次，防止无限循环）。
      - 在日志中打印 `WARNING`：“默认模型 x 调用失败，已自动故障转移至备用模型 y 进行重试”。

### 1.3 模块 3：自选股添加模糊搜索与自动补全
*   **目的**：使用户添加股票时，不必手动记忆精确的 Symbol，直接输入名字或拼音即可补全。
*   **API 接口设计**：
    新增 `GET /api/market/search?q={query}`：
    - 使用 `httpx` 轮询 Yahoo Finance 的 suggestion 接口 `https://query1.finance.yahoo.com/v1/finance/search` 获取匹配的股票列表。
    - 考虑到离线开发/沙箱环境，增加兜底逻辑：若网络超时或失败，则通过 SQL `LIKE` 模糊查询本地 `price_snapshot` 中已经存留的股票代码和名称。
*   **前端交互设计**：
    - 改造 `WatchlistAddModal.vue`：
    - 对输入框绑定 `@input` 触发 debounced（300ms）搜索方法。
    - 在输入框下方悬浮磨砂玻璃质感的 Suggestion 下拉列表。
    - 选中某只股票后，自动填充 Symbol 和名称并高亮确认，点击添加完成绑定。
