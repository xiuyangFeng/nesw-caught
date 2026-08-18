# 2026-06-12-llm-ping-and-watchlist-ai-insight-design.md

## 目的

本文件定义 news-caught 第三轮优化的技术设计规范，旨在：
1. 修复后端 mock 配置缺失导致的 `AttributeError` 问题以通过全量测试回归。
2. 引入单个 LLM 配置的独立连通性 Ping 测速能力，并在前端渲染延迟反馈。
3. 引入个股一键 AI 洞察投研研判简报，汇聚关联新闻并借助 LLM 提供结构化的多维个股研判。

---

## 1. 缺陷修复设计 (AttributeError Regression Fix)

### 问题分析
在 `backend/app/services/llm_providers.py` 的 completions / embeddings / stream 发生异常时，Failover 逻辑会试图触发一次重试：
```python
        except (LLMProviderError, httpx.HTTPError) as exc:
            if _retry_count < 1:
                backup_config = find_backup_config(self.config.id)
```
但在部分单元测试中，例如 `test_news_relevance_annotation.py`，传入的 mock 配置对象 `self.config` 是 `types.SimpleNamespace`。这类 mock 对象缺少 `id` 属性，因而直接抛出 `AttributeError: 'SimpleNamespace' object has no attribute 'id'`，致使原本的断言机制和异常检查流程失效。

### 解决方案
在 `llm_providers.py` 所有访问 `self.config.id` 的地方，安全读取 `id` 字段值。
```python
# 替换前
backup_config = find_backup_config(self.config.id)

# 替换后
backup_config = find_backup_config(getattr(self.config, "id", 0))
```
这样在 mock 环境下（即 `self.config.id` 不存在时），获取值默认为 `0`，可避免在 Failover 降级触发重试时崩溃，并正常抛出底层的 provider配置或连通性异常。

---

## 2. LLM Config Ping 测速端点与交互设计

### 接口规范 (API Contract)
新增后端 API 端点用于对具体 LLM 配置独立发起连接测试。

- **URL**: `POST /api/llm/config/{config_id}/ping`
- **Dependency**: `session: Session = Depends(get_db_session)`
- **响应体模型 (LLMConnectionTestView)**:
  ```json
  {
    "provider_name": "openai_compatible",
    "model_name": "deepseek-chat",
    "message": "LLM connection succeeded",
    "latency_ms": 234
  }
  ```
- **核心逻辑**：
  1. 通过 `LLMProviderConfigRepository(session).get_by_id(config_id)` 获取配置。
  2. 若配置不存在，抛出 `404 Not Found`。
  3. 使用 `build_provider(config)` 获得驱动。
  4. 使用 `time.perf_counter()` 环绕计量 `provider.test_connection()` 的执行时延。
  5. 响应成功结果，返回时延大小；若捕获 `LLMProviderError`，则向上抛出 `502 Bad Gateway` 且包含异常细节。

### 前端 Store 与 UI 实现
1. **API Client**:
   在 `frontend/src/api/client.ts` 注册 `pingLlmConfig(id)` 方法，调用对应路由。
2. **LLM Store**:
   - 增加状态：
     ```typescript
     const pingStatuses = ref<Record<number, { loading: boolean; latency: number | null; error: string | null }>>({});
     ```
   - 增加动作 `pingConfig(id)`：
     ```typescript
     async function pingConfig(id: number) {
       pingStatuses.value[id] = { loading: true, latency: null, error: null };
       try {
         const response = await apiClient.pingLlmConfig(id);
         pingStatuses.value[id] = {
           loading: false,
           latency: response.data.latency_ms,
           error: null,
         };
       } catch (err: any) {
         pingStatuses.value[id] = {
           loading: false,
           latency: null,
           error: err.message || '连接失败',
         };
       }
     }
     ```
3. **LlmSettingsView UI 渲染**:
   在每个配置卡片的右侧操作栏添加 `📡 测速` 按钮。
   根据 `pingStatuses[cfg.id]` 展示不同状态：
   - `loading === true`: 展示正在旋转或闪烁的测速 Loading 状态。
   - `latency !== null`: 展示发光绿色药丸徽章，如 `145 ms`；如果延迟较高（如 > 800ms），则采用黄色渲染。
   - `error !== null`: 展示红色小字 `连接失败` 并支持 hover 查看错误详情。

---

## 3. 自选股一键 AI 研判简报设计

### 接口规范 (API Contract)
为自选股 symbol 提供汇聚关联新闻并调用 LLM 生成深度简报的专属端点。

- **URL**: `POST /api/watchlist/{symbol}/ai-insight`
- **Dependency**: `session: Session = Depends(get_db_session)`
- **请求体**: 空 (无需 payload)
- **响应体模型 (WatchlistAiInsightView)**:
  ```json
  {
    "symbol": "0700.HK",
    "insight_text": "# AI 研判报告\n\n...",
    "generated_at": "2026-06-12T15:20:00Z"
  }
  ```
- **核心逻辑**：
  1. 通过 `_resolve_watchlist_stored_symbol(symbol, repository)` 得到 canonical 归一化自选股符号。
  2. 调用 `NewsMentionsRepository(session).list_related_news(resolved_symbol)` 获取最近 7 天的关联新闻，并截取最新的前 10 篇。
  3. 若无新闻，直接返回响应且提示 `“暂无该股票的关联新闻，无法生成 AI 研判。”`。
  4. 若有新闻，提取关联新闻的标题和摘要组装 Context，结合特定的投研 Prompt 规则发给激活的默认大模型。
  5. 捕获大模型输出的 Markdown/HTML 研判内容。
  6. 研判请求将通过底层的 Completion 请求链，从而被 `LLMTokenUsage` 拦截并完整审计并记录本轮产生的 Token 数目。

### AI 投研研判 Prompt 模板
```text
你是一个专业的证券投研专家，请分析以下关于 {display_name} ({symbol}) 的最新关联新闻：
[新闻列表]
{新闻项：发布时间，新闻标题，新闻摘要}

请根据以上提供的新闻，给出一份详实、客观、结构化（使用 Markdown 格式）的研判简报。请严格按照以下几个模块输出，切忌空话和重复描述：

1. **核心利好梳理**：概括新闻中提及的有利因素、业绩提振点或公司发展红利。
2. **核心利空与潜在风险**：梳理宏观政策扰动、竞争加剧或产业链供应链警报。
3. **后市策略研判**：
   - 短期情绪：评估消息面对股价短期波动的正面或负面拉动。
   - 中长期基本面：结合基本面 read-through，给出中长期展望建议。

要求：段落清晰，条理分明，利于看盘者快速脱水和做出策略决定。
```

### 前端 UI 与交互表现力
1. **API Client**:
   注册 `getWatchlistAiInsight(symbol)`。
2. **Watchlist Store**:
   - 增加状态：
     ```typescript
     const aiInsights = ref<Record<string, { loading: boolean; text: string | null; error: string | null }>>({});
     ```
   - 增加动作 `loadAiInsight(symbol)`，向后端发起研判并更新状态。
3. **StockDetailPanel UI 拼接**:
   - 在 K 线图下方和“RelatedNewsSidebar”上方，设计一处带有科技发光边框的 `SectionCard` 面板，命名为 **“AI 投研洞察 (AI Insight Workspace)”**。
   - 未生成洞察时，显示空态以及发光霓虹按钮 `✨ 一键生成 AI 洞察 (AI Workspace)`。
   - 点击后，触发扫光 loading 动效，阻断二次重复点击。
   - 成功返回后，使用内置的轻量 Markdown 解析模块（`markdown.ts`）直接在此板块渲染 HTML 输出，保留清晰的利好、风险及策略表格。
