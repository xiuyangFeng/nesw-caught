# LLM DeepSeek Default Persistence Design

**Goal**

修复本地 LLM 设置页在刷新后看起来被重置的问题，并确保当前默认配置稳定保持为 DeepSeek；同时修复由于错误 DeepSeek `base_url` 导致的上游 SSL 连接失败。

**Context**

- 当前真实配置保存在后端 `llm_provider_config` 表中。
- 前端 `LLM Settings` 页会在 `GET /api/llm/config` 失败时静默回退到 `mockLlmConfig`，导致页面刷新后可能显示假数据，而不是本地真实配置。
- 当前数据库中已存在一条激活配置，`base_url` 被误保存为 `https://api.deepssek.com/v1`，会触发 TLS/SSL 握手失败；DeepSeek 正确地址应为 `https://api.deepseek.com/v1`。

**Approach Options**

1. 只修正数据库里的 `base_url`
   - 优点：改动最小，能直接解决当前 SSL 报错。
   - 缺点：前端仍会在后端失败时回退 mock，刷新后“看起来被改回去”的误导仍存在。

2. 修正 `base_url`，并移除 LLM 配置接口的 mock fallback
   - 优点：后端数据库成为唯一真实来源；刷新页时不会再被 mock 覆盖；错误可以直接暴露给用户。
   - 缺点：当后端不可达时，LLM 设置页会明确报错，不再伪装成可用。

3. 在方案 2 基础上再加入系统级 DeepSeek 预置默认值
   - 优点：首次配置路径更短。
   - 缺点：引入新的全局默认策略，超出本次修复范围。

**Recommendation**

采用方案 2。它同时解决“刷新后被重置”的错觉和当前真实的 SSL 失败，且不引入额外默认策略。

**Design**

### 1. 真实来源与页面行为

- 后端 `llm_provider_config` 继续作为唯一真实来源。
- 前端 `apiClient.getLlmConfig()` 与 `apiClient.saveLlmConfig()` 不再对 LLM 配置使用 `withMockFallback`。
- `llmStore` 新增加载错误状态，`LlmSettingsView` 直接展示加载失败文案，避免把 mock 误当成真实配置。

### 2. DeepSeek 配置修正

- 增加后端测试，证明 `openai_compatible + deepseek-*` 配置在保存时若传入历史错误域名 `https://api.deepssek.com/v1`，会被规范化为 `https://api.deepseek.com/v1`。
- 在仓库现有本地数据库中同步修正当前激活配置，保证用户刷新页面后立刻看到正确值。

### 3. 错误处理

- 保持现有后端 `LLMProviderError -> 502` 语义不变。
- 配置读取/保存失败时，前端直接显示真实错误，不再静默降级。

### 4. Testing

- 前端：
  - `apiClient` 测试覆盖 LLM 配置读取/保存在后端失败时抛错而不是回退 mock。
  - `LlmSettingsView` 测试覆盖加载失败提示。
- 后端：
  - `test_llm_config.py` 覆盖错误 DeepSeek 域名规范化保存。

### 5. Risks

- 取消 mock fallback 后，后端不可达时用户会直接看到失败提示；这是有意改为真实语义。
- 域名规范化仅针对明确的 DeepSeek 错拼地址，不自动重写其它 OpenAI compatible 地址，避免误伤自定义 provider。
