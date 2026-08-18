# AI 对话推理流与模型快捷预设设计

## 背景

项目已有 `/api/llm/chat` SSE 流式回答、前端打字机渲染和中止生成能力，但后端只读取 OpenAI-compatible 流中的 `delta.content`。DeepSeek Reasoner、Qwen 推理模型等返回的 `delta.reasoning_content` 会被丢弃，前端也没有独立承载推理内容的消息结构。LLM 设置页目前要求用户逐项手填 Provider、Base URL 和模型名，容易写错地址，也缺少官方文档入口。

## 目标

1. 保留现有 SSE 与故障切换协议，新增独立的推理事件；正文和推理均实时到达前端。
2. AI 消息内以可折叠面板展示模型实际返回的推理内容，生成期间默认展开，结束后仍可查看。
3. 在 LLM 设置表单加入常见 OpenAI-compatible 服务预设，一键填入服务地址、显示名和推荐模型，并提供官方文档链接。
4. 保留完全自定义配置能力；预设不内置、不读取、不传输 API Key。

## 非目标

- 不伪造或从最终答案反推“思考过程”；模型未返回 reasoning 字段时不显示推理面板。
- 不迁移到 OpenAI Responses API，也不改变现有 `/chat/completions` 兼容层。
- 不新增数据库字段；预设仅用于前端表单填充。
- 不自动测试或保存配置，用户仍需填写自己的 API Key 并主动保存。

## 后端设计

### Provider 事件

`AsyncOpenAICompatibleProvider.chat_stream()` 新增事件类型：

- `("reasoning", chunk)`：来自 `delta.reasoning_content`；兼容读取字符串形式的 `delta.reasoning` 和 `delta.thinking`。
- `("token", chunk)`：现有最终答案正文。
- `("failover", metadata)`：现有故障切换元数据。

推理 chunk 与正文 chunk 都视为“首字节已发送”，一旦任一内容已发给客户端，上游中断后不得对同一 provider 重试，以免重复推理或正文。缺少 provider usage 时，推理与正文共同参与 completion token 估算。

### SSE 契约

`POST /api/llm/chat` 流式响应保持 `data: <json>\n\n`：

```json
{"reasoning":"先分析事件影响路径……"}
{"text":"结论是……"}
{"failover":{"from_model":"a","to_model":"b","reason":"..."}}
{"error":"..."}
```

已有只消费 `text` 的客户端继续兼容。

## 前端设计

### 消息状态

`ChatMessage` 新增可选 `reasoning` 字段。会话持久化仍复用 localStorage；发送历史时只发送最终 `content`，不把推理过程重新注入后续上下文。

`useChatStream` 维护推理和正文两个缓冲区，通过同一个 30ms 渲染节拍渐进更新，网络完成后等待两个缓冲区都排空再结束 streaming 状态和持久化。

### 推理面板

AI 气泡上方增加 `<details>` 面板：

- 有 reasoning 才出现；生成时标记“推理中”并默认展开。
- 生成结束后标题显示“模型推理过程”，用户可以折叠/展开。
- 采用现有控制台风格的细边框、单色状态灯和等宽小标题，避免抢夺最终答案的视觉优先级。
- 明示这是“模型返回的推理内容”；不同服务或模型可能不提供。

## 模型快捷预设

前端维护静态、可测试的预设表，每项包含显示名、Base URL、推荐模型列表、说明和官方文档链接。首批覆盖：

- OpenAI：`https://api.openai.com/v1`
- 通义千问 DashScope：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- DeepSeek：`https://api.deepseek.com/v1`
- Moonshot / Kimi：`https://api.moonshot.cn/v1`
- SiliconFlow：`https://api.siliconflow.cn/v1`
- Google Gemini OpenAI compatibility：`https://generativelanguage.googleapis.com/v1beta/openai`

点击预设仅覆盖 `provider_name`、`display_name`、`base_url`、`model_name`；API Key、预算和启用状态不变。另提供“自定义”入口清空预设选择但不强制清空用户已输入字段。

## 风险与兼容性

- reasoning 字段不是 OpenAI-compatible 标准的统一字段，不同服务可能完全不返回；实现采用白名单字段兼容并忽略未知结构。
- 部分供应商会调整模型名或文档地址；预设是便利入口而非后端约束，用户始终可自定义修改。
- 展示模型推理可能产生较长内容；面板默认不与最终答案混排，并允许折叠。

## 验收

1. Provider 测试证明 reasoning 先于正文时会按类型输出，且 reasoning 已发送后不进行同 provider 重试。
2. API 测试证明 SSE 分别输出 `reasoning` 与 `text` 字段。
3. 前端 composable 测试证明 reasoning 与正文均渐进写入消息并持久化。
4. 消息列表测试证明 reasoning 面板仅在有内容时出现。
5. 设置页测试证明点击 Qwen/OpenAI 等预设会填入正确地址与默认模型，官方文档链接安全打开，API Key 不被覆盖。
6. 相关后端测试、前端测试和 `npm --prefix frontend run build` 通过。
