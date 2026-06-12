# 后端多并发、多模型接入与新闻 AI 问答设计方案

本方案旨在为 `news-caught` 项目提供后端性能优化（并发及异步支持）、更灵活的多模型配置管理，并新增一个面向用户的 AI 对话/聊天功能，允许用户直接基于特定的新闻进行提问。

---

## 1. 架构与性能优化 (多并发/异步化)

目前后端的 `OpenAICompatibleProvider` 在请求大模型接口时使用的是同步的 `httpx.Client`，这会阻塞 FastAPI 的工作线程。在多并发请求或批量操作（如批量个股分析、翻译等）时可能会引起性能瓶颈。

### 优化方案：
1. **异步大模型驱动**：
   在 `app/services/llm_providers.py` 中引入 `AsyncOpenAICompatibleProvider`，基于 `httpx.AsyncClient` 实现异步的网络请求。
2. **异步生成器 (Streaming)**：
   利用 `httpx.AsyncClient` 的 `stream` 方法，通过异步生成器接口 `async_chat_stream` 实时读取大模型返回的 chunks，避免把全部响应缓存在内存中。
3. **接口异步化**：
   将翻译 `/api/llm/translate`、测试 `/api/llm/test` 以及新增的对话 `/api/llm/chat` 全部声明为 `async def`，使用 `await` 调用异步大模型驱动，释放 FastAPI 的事件循环（Event Loop）来应对高并发。

---

## 2. 数据库与配置变更 (允许接入更多模型)

目前虽然数据库可以保存多条 LLM 配置记录，但每次配置新模型时，老配置的 `is_active` 会被批量设置为 `False`，导致同时只能存在一个活动的配置。

### 数据库变更：
在 `llm_provider_config` 表中引入 `is_default` 字段，以表明哪个模型配置是“默认模型配置”。

- **模型模型更改 (`app/models/llm_provider_config.py`)**：
  ```python
  is_default: Mapped[bool] = mapped_column(Boolean(), default=False, index=True)
  ```

- **自动升级迁移 (`app/db/initializer.py`)**：
  在 `initialize_database()` 执行时检查 `llm_provider_config` 是否已有名为 `is_default` 的列，如果不存在则通过 `ALTER TABLE` 语句自动补建（避免破坏已有的 SQLite 数据）。

- **仓储修改 (`app/repositories/llm_provider_config_repository.py`)**：
  - `list_all()`: 获取所有配置（包括已激活和禁用的）。
  - `get_default()`: 获取设置了 `is_default=True` 的配置；如果不存在，则取最新的 `is_active=True` 的配置作为向下兼容。
  - `upsert_config()`: 创建或更新指定的模型配置，不覆盖其他配置的 `is_active`。
  - `set_default(id)`: 将指定 ID 的配置设为默认，同时将其它的 `is_default` 设置为 `False`。
  - `delete_config(id)`: 允许删除特定配置。

---

## 3. 聊天与问答接口设计

新增一个 `/api/llm/chat` 端点，支持普通对话以及流式对话（SSE）。

- **接口路径**: `POST /api/llm/chat`
- **输入 Schema (`LLMChatRequest`)**:
  - `message`: `str` (当前用户输入)
  - `history`: `list[dict[str, str]]` (历史消息列表，形如 `[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]`)
  - `news_id`: `int | None` (关联的新闻 ID)
  - `config_id`: `int | None` (指定的模型 ID，若为空则使用默认模型)
  - `stream`: `bool = True` (是否启用流式返回)

- **逻辑流程**：
  1. 获取指定的 LLM 配置。如果没有指定，则使用默认配置。
  2. 如果指定了 `news_id`：
     - 在数据库中查询对应的新闻 `NewsItem`。
     - 获取关联的 `ArticleContent`（若存在）。
     - 构建新闻上下文 Prompt：
       ```text
       系统提示：你现在是金融和投资分析专家。用户正在就以下新闻内容与你进行对话：
       【新闻标题】：{title}
       【来源】：{source}
       【发布时间】：{published_at}
       【新闻内容摘要】：{summary}
       【新闻正文】：{content_text}

       请结合上述新闻内容，回答用户的相关提问。如果用户的提问超出该新闻范围，请礼貌地指出并以金融专家的视角进行客观回答。
       ```
     - 将该上下文作为 system 级别的消息（或首条 user 消息的 context 提示）插入到大模型输入中。
  3. 调用大模型的异步流式接口，逐个 token 通过 `StreamingResponse` (SSE, `text/event-stream`) 吐给前端。

---

## 4. 前端界面设计 (AI Chat)

我们需要为用户提供一个能进行 AI 聊天的专属页面，并提供在“新闻详情页”里直接向 AI 提问的快捷路径。

### A. 主页导航：
在 `AppShell.vue` 的 `navItems` 中新增 `05 AI Chat`，跳转路径 `/chat`。

### B. 聊天室主页面 (`ChatView.vue`)：
- **模型选择器**：下拉菜单列出所有配置的模型（如 `DepeSeek-V3`、`GPT-4o` 等），支持切换。
- **对话区域**：经典的气泡对话结构，支持 Markdown 渲染（如代码块、段落等）。
- **流式打字机效果**：通过 `EventSource` 或 `fetch` 流式读取返回字符并实时展示。
- **当前上下文新闻卡片**：如果用户是从某条新闻跳转来的，顶部会显示“正在就此新闻提问”的新闻卡片，点击可查看新闻原文。用户可以随时“清除上下文”转为普通聊天。
- **预设快捷提问**（在关联新闻时展示）：
  - “简述该新闻对相关股票的影响”
  - “该新闻的情感倾向是什么？主要风险点在哪？”
  - “为我总结这篇新闻的三个核心要点”

### C. 新闻详情页面入口 (`NewsDetailView.vue`)：
- 在详情页面的合适位置（例如新闻摘要下方或侧边栏）添加一个 **“基于此新闻向 AI 提问”** 按钮。
- 点击后，前端携带 `news_id` 跳转至 `/chat?news_id={id}` 页面，聊天页面自动载入新闻作为上下文，并发送默认的第一条问答（或预置输入框）。

---

## 5. 变更记录更新要求

在项目实现完毕、通过验证后，需要同步更新：
1. `docs/code-change-log.md`
2. 项目 `README.md`
