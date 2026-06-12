# LLM Connection Test Design

**Goal**

在 `LLM Settings` 页面新增“测试连接”能力，要求用户必须先保存配置，再使用当前已保存的激活配置验证连通性；同时让上游 LLM 的 401/400 等错误尽量透传真实错误信息，便于定位无效 key。

**Context**

- 当前翻译请求已经能连到 DeepSeek 正确地址，但上游返回 `401 invalid api key`。
- 页面缺少独立的连接测试入口，用户只能通过翻译功能间接发现配置错误。
- 现有后端 `OpenAICompatibleProvider` 在上游返回 4xx/5xx 时只报 `status code`，丢失了真实错误正文。

**Approach Options**

1. 前端直接用表单值发测试请求
   - 优点：无需先保存。
   - 缺点：和用户要求冲突，也会让“实际生效配置”与“测试配置”分裂。

2. 后端基于当前已保存激活配置提供测试接口
   - 优点：和真实翻译/分析完全一致；符合“必须先保存再测试”；实现边界清晰。
   - 缺点：用户每次改 key 后需要先保存再测。

3. 保存时自动附带测试
   - 优点：步骤更少。
   - 缺点：会把“保存”和“测试”耦合，保存失败/测试失败语义混杂，不利于排错。

**Recommendation**

采用方案 2。保存和测试分离，但都基于同一条已保存配置，语义最稳定。

**Design**

### 1. Backend

- 新增 `POST /api/llm/test`。
- 读取 `llm_provider_config` 当前激活配置，若未配置返回 `400`。
- 使用最小 `chat/completions` 请求做连通性验证。
- 成功时返回 provider、model 和成功消息。
- 失败时复用统一 provider 错误处理，尽量把上游 JSON 错误正文里的 message 带回来。

### 2. Provider Error Handling

- `OpenAICompatibleProvider` 在收到 `>=400` 响应时，优先解析 JSON 中的：
  - `error.message`
  - 或顶层 `message`
- 若解析不到，再退回 `status code` 文案。
- 这样 DeepSeek 返回的 `Authentication Fails ... invalid` 能直接暴露给页面。

### 3. Frontend

- `LLM Settings` 页新增“测试连接”按钮。
- 按钮仅在已有已保存配置时可用；用户刚改了表单但未保存时，点击逻辑仍只测试后台当前激活配置。
- 页面显示独立的测试中/成功/失败状态，不和“保存配置”提示串用。

### 4. Testing

- 后端：
  - 新增 `/api/llm/test` 成功、未配置、上游认证失败透传测试。
  - 新增 provider 4xx 错误正文透传测试。
- 前端：
  - API client 新增 test 接口测试。
  - Store 新增测试连接状态测试。
  - 视图新增按钮渲染与点击测试。

### 5. Risks

- 测试连接会真实消耗一次上游请求额度，但请求体最小化。
- 页面显示的是“当前已保存配置”的测试结果，不是未保存表单草稿；这和用户要求一致，但需要在 UI 文案中说清楚。
