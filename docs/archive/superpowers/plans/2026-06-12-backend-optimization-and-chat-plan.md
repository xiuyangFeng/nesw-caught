# 后端多并发、多模型接入与新闻 AI 问答开发计划

本计划将基于设计方案逐步完成改造与开发，涵盖数据库迁移、后端服务改造、API 接口定义、前端页面开发以及全面的测试验证。

---

## 第一阶段：数据库与仓储层改造 (后端基础)

### 任务 1：修改数据库模型，引入 `is_default`
- **目标文件**: `backend/app/models/llm_provider_config.py`
- **变更点**:
  - 为 `LLMProviderConfig` 模型新增 `is_default` 属性。
- **验证**: 检查代码语法。

### 任务 2：实现数据库自动升级逻辑 (对 SQLite 友好)
- **目标文件**: `backend/app/db/initializer.py`
- **变更点**:
  - 编写 `ensure_llm_provider_config_columns` 方法，若表内没有 `is_default` 字段则执行 `ALTER TABLE llm_provider_config ADD COLUMN is_default BOOLEAN DEFAULT 0`。
  - 在 `initialize_database()` 注册调用此方法。
- **验证**: 运行 `conda run -n news-caught pytest backend/tests`（如果已有测试，应该能跑通，因为数据库会正确初始化）。

### 任务 3：编写 LLM 配置管理仓储方法
- **目标文件**: `backend/app/repositories/llm_provider_config_repository.py`
- **变更点**:
  - 修改 `upsert_active` 的定义，不再无条件将其他模型的 `is_active` 置为 `False`。
  - 实现 `list_all()` 方法返回所有的 `LLMProviderConfig` 列表。
  - 实现 `get_default()` 方法：返回 `is_default` 最新的 active 配置。如果没有 `is_default` 的， fallback 到首个 `is_active=True` 的配置。
  - 实现 `set_default(id)`：在事务中将对应的 `id` 的配置的 `is_default` 设为 `True`，其它所有配置的 `is_default` 设为 `False`。
  - 提供 `delete_config(id)` 和 `update_config_status(id, is_active)` 支持多模型管理的增删改。
- **验证**: 为仓储层编写新的单元测试 `backend/tests/repositories/test_llm_provider_config_repository.py`。

---

## 第二阶段：大模型异步驱动与并发优化 (后端核心)

### 任务 4：实现异步大模型服务驱动
- **目标文件**: `backend/app/services/llm_providers.py`
- **变更点**:
  - 创建 `AsyncOpenAICompatibleProvider` 辅助类，其 API 设计与 `OpenAICompatibleProvider` 类似，但所有网络请求使用 `httpx.AsyncClient` 异步处理。
  - 添加 `async_chat_stream(messages: list[dict[str, str]])` 异步生成器方法，用于处理 SSE 流式传输。
- **验证**: 检查代码及类型注解。

### 任务 5：将翻译、测试接口升级为异步，支持多并发
- **目标文件**: `backend/app/api/routes/llm.py`
- **变更点**:
  - 引入异步的 `build_async_provider`。
  - 把 `translate_text` 接口改成 `async def translate_text`，并在其内使用异步的翻译调用。
  - 把 `test_llm_connection` 接口改成 `async def test_llm_connection`，使用异步的测试调用。
- **验证**: 运行测试用例。

---

## 第三阶段：新增多模型管理与 AI 问答接口

### 任务 6：丰富 `/api/llm/config` 接口体系
- **目标文件**: `backend/app/api/routes/llm.py`
- **变更点**:
  - `GET /config`: 保持不变，返回默认模型配置（兼容以前的前端）。
  - `GET /config/all`: 返回全部配置列表。
  - `POST /config`: 允许通过传入 `id` 更新指定模型，或者新增模型（不破坏其他模型的 active 状态）。
  - `DELETE /config/{id}`: 删除指定模型配置。
  - `POST /config/{id}/default`: 设置某个模型配置为默认。
  - `POST /config/{id}/active`: 启用/禁用特定模型配置。
- **验证**: 使用 `pytest` 测试配置相关的 CRUD API。

### 任务 7：设计开发 AI Chat / 问答接口
- **目标文件**: `backend/app/api/routes/llm.py`
- **变更点**:
  - 定义 `LLMChatRequest` 和接口 `POST /chat` 或 `/chat/stream`。
  - 处理 `news_id` 上下文注入逻辑，读取新闻及其文章正文。
  - 组装 System Prompt，通过 `AsyncOpenAICompatibleProvider` 进行异步流式输出，采用 `StreamingResponse(..., media_type="text/event-stream")` 返回 SSE 流。
- **验证**: 编写单元测试验证流式接口。

---

## 第四阶段：前端页面与交互开发

### 任务 8：前端 LLM 管理页适配多模型
- **目标文件**:
  - `frontend/src/stores/llmStore.ts`
  - `frontend/src/views/LlmSettingsView.vue`
- **变更点**:
  - 修改 Store：新增 `loadAllConfigs()`, `deleteConfig(id)`, `setDefaultConfig(id)`, `toggleConfigActive(id)`。
  - 改造 `LlmSettingsView.vue`，展示已配好的模型列表（包含配置名称、模型、是否为默认、启用状态等）。
  - 支持在列表中点击“设为默认”、“启用/禁用”和“删除”按钮，并保留新增模型的表单（以卡片或抽屉形式）。
- **验证**: `npm --prefix frontend run build` 确保无编译错误。

### 任务 9：实现 AI Chat 聊天主页面
- **目标文件**:
  - `frontend/src/router/index.ts`
  - `frontend/src/components/layout/AppShell.vue`
  - `frontend/src/views/ChatView.vue` (新)
- **变更点**:
  - 在 `router/index.ts` 注册 `/chat` 路由。
  - 修改 `AppShell.vue` 导航，插入 "AI Chat"。
  - 编写 `ChatView.vue`：
    - 模型选择下拉框。
    - 带有 Markdown 样式的对话框气泡。
    - 绑定新闻上下文的展示区域（包括“清除上下文”按钮）。
    - 预设快捷提问词卡片。
- **验证**: `npm --prefix frontend run build`。

### 任务 10：新闻详情页增加 AI 对话直达按钮
- **目标文件**: `frontend/src/views/NewsDetailView.vue`
- **变更点**:
  - 在新闻摘要或详情下方增加“关于此新闻问 AI” 按钮。
  - 点击跳转到 `/chat?news_id={news_id}`，自动激活关联新闻逻辑。
- **验证**: `npm --prefix frontend run build`。

---

## 第五阶段：收尾与文档更新

- 运行所有后端测试。
- 执行 `npm --prefix frontend run build`。
- 更新 `docs/code-change-log.md`。
- 更新 `README.md`。
