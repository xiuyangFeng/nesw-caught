# AI 对话推理流与模型快捷预设实现计划

## 任务 1：后端推理流事件（TDD）

1. 在 `backend/tests/test_llm_providers.py` 先增加失败测试，覆盖 `reasoning_content` 与 `content` 的事件顺序、推理首字节后的重试守卫。
2. 在 `backend/tests/test_llm_chat.py` 增加 SSE 契约失败测试，断言 reasoning 使用独立 JSON 字段。
3. 在 `backend/app/services/llm_providers.py` 增加 reasoning 事件解析与 token 估算。
4. 在 `backend/app/api/routes/llm.py` 映射 reasoning SSE 帧。
5. 运行相关 pytest，并立即更新 change log。

## 任务 2：前端推理状态与展示（TDD）

1. 扩展 `useChatStream.test.ts`，先断言 reasoning 与正文双缓冲的期望行为。
2. 为 `ChatMessageList` 增加组件测试，断言推理面板的出现、状态标题和无 reasoning 时的退化。
3. 扩展 `ChatMessage` 类型和 `useChatStream` SSE 解析/缓冲逻辑。
4. 在 `ChatMessageList.vue` 实现克制的可折叠推理面板。
5. 运行目标前端测试，并立即更新 change log。

## 任务 3：模型快捷预设（TDD）

1. 新增 `frontend/src/components/llm/providerPresets.ts` 及单元测试，固定预设元数据。
2. 扩展 `LlmSettingsView.test.ts`，先断言点击 Qwen/OpenAI 预设后表单字段变化和 API Key 保留。
3. 修改 `LlmConfigForm.vue`，加入预设选择区、推荐模型选择和官方文档链接，保留自定义输入。
4. 运行设置页测试，并立即更新 change log。

## 任务 4：验证与评审

1. 运行后端相关测试：`conda run -n news-caught pytest backend/tests/test_llm_providers.py backend/tests/test_llm_chat.py`。
2. 运行前端相关测试及全量：`npm --prefix frontend test -- --run ...`、`npm --prefix frontend test -- --run`。
3. 运行 `npm --prefix frontend run build`、后端 ruff 和 `git diff --check`。
4. 审查兼容性、错误处理、可访问性与未提交文件，补齐 change log 最终验证结果。
