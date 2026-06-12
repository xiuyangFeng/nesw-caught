# 大模型故障降级可视化感知与 Token 审计时序看板设计方案 (Round 5)

本设计方案旨在加强大模型 (LLM) 服务的容错可靠性 (Resilience) 及用量可审计性 (Auditable Metrics)。核心改进包含两个部分：
1. **大模型主备容灾切换的前端感知与高亮提醒**：流式/非流式请求时若触发 Failover，前端能接收到事件并展现出流光警示横幅及毛玻璃 Toaster 反馈。
2. **审计控制台 7 天 Token 消耗时序折线图**：自绘高对比度 Terminal 暗黑科技风的 SVG 渐变图表，清晰反映用量波动。

---

## 1. 核心业务流程与接口设计

### 1.1 Failover 容灾切换的 SSE/JSON 协议扩展

#### 流式接口 (SSE)
当调用 `AsyncOpenAICompatibleProvider.chat_stream` 时，若主配置网络超时或报错，会捕获异常并寻找备用模型重试。
* **信号前缀**：在重试之前，Generator 会先 `yield` 吐出一个特殊前缀标记：
  ```
  [FAILOVER_SIGNAL]:{"from_model": "gpt-4o", "to_model": "deepseek-chat", "reason": "Connection timed out"}
  ```
* **SSE 帧转换**：在 `backend/app/api/routes/llm.py` 中，迭代遇到该前缀时，解析为独立的 JSON 帧发送给前端：
  ```
  data: {"failover": {"from_model": "gpt-4o", "to_model": "deepseek-chat", "reason": "Connection timed out"}}
  ```
  常规的字符流依旧为：
  ```
  data: {"text": "实际生成的文本..."}
  ```

#### 非流式接口 (JSON)
* **动态属性挂载**：在 `AsyncOpenAICompatibleProvider` / `OpenAICompatibleProvider` 内部发生降级重试时，在实例上挂载临时属性 `failover_triggered`。
* **响应结构**：在非流式 `/api/llm/chat` 返回结果中，如果检测到该属性，返回如下结构：
  ```json
  {
    "text": "大模型研报分析文本...",
    "failover": {
      "from_model": "gpt-4o",
      "to_model": "deepseek-chat",
      "reason": "Connection timed out"
    }
  }
  ```

### 1.2 过去 7 天 Token 每日时序数据

* **接口路由**：扩展已有的 `GET /api/llm/stats`。
* **时序 SQL 查询**：
  在 SQLAlchemy 中使用 `func.date(LLMTokenUsage.created_at)` 分组并统计过去 7 天的 Token：
  ```python
  from datetime import datetime, timedelta, timezone
  seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
  
  stmt_daily = (
      select(
          func.date(LLMTokenUsage.created_at).label("day"),
          func.sum(LLMTokenUsage.prompt_tokens).label("prompt"),
          func.sum(LLMTokenUsage.completion_tokens).label("completion"),
          func.sum(LLMTokenUsage.total_tokens).label("total")
      )
      .where(LLMTokenUsage.created_at >= seven_days_ago)
      .group_by(func.date(LLMTokenUsage.created_at))
      .order_by(func.date(LLMTokenUsage.created_at).asc())
  )
  ```
* **响应扩展**：
  在 `/api/llm/stats` 的返回中，新增 `daily` 数组：
  ```json
  {
    "overall": { ... },
    "models": [ ... ],
    "operations": [ ... ],
    "daily": [
      { "date": "2026-06-06", "prompt_tokens": 1200, "completion_tokens": 1800, "total_tokens": 3000 },
      { "date": "2026-06-07", "prompt_tokens": 1500, "completion_tokens": 2500, "total_tokens": 4000 }
    ]
  }
  ```

---

## 2. 前端交互与视觉设计

### 2.1 大模型故障接管 UI 提示 (Failover Alert)
* **全局 Toaster 反馈**：接收到 `failover` 事件后，立即调用 `toastStore.showWarning('由于主模型异常，系统已为您无缝切换至备用模型！')`，提供微动效毛玻璃 Toast。
* **会话消息区警示横幅**：在 AI 对话页消息列表顶端，或者研报详情面板正上方，如果触发了降级，则渲染以下横幅：
  * **样式**：半透明黄色背景带模糊（`backdrop-filter: blur(8px) bg-amber-500/10 border-amber-500/30`），文字带有心跳发光效果。
  * **文案**：`⚡ 降级接接管中：本次对话已由默认模型 [old_model] 自动重试并切换至备用模型 [new_model] （原因：[reason]）`。

### 2.2 SVG 优雅时序折线图 (Token Trend Chart)
为了保持无外部重型依赖的高品质设计，我们在 `LlmSettingsView.vue` 审计控制台自绘高表现力 SVG 折线图。
* **图表网格与比例**：基于 SVG 坐标系统动态换算（`width="100%", height="180"`）。
* **视觉特效**：
  * **渐变发光折线**：折线使用青色霓虹发光（通过 `filter="url(#glow)"` 或者是 `drop-shadow` 滤镜渲染）。
  * **半透明面积填充**：折线下方填充一层带透明度的青色到全透明渐变的 `LinearGradient`。
  * **背景科技网格**：背景绘制 4-5 条细密的横向网格虚线及时间轴刻度，带有一些前卫的数字刻度标签。
  * **光标十字交互**：鼠标悬停在图表上时，利用 `mousemove` 捕获最近的数据点，显示当前日期的详细 Prompt / Completion / Total 详情气泡及虚线垂直线。

---

## 3. 验证与单元测试规划

### 3.1 后端单元测试
* **SSE 容灾信号捕获测试**：在 `backend/tests/test_llm_chat.py` 中，编写一个测试用例，模拟主模型请求发起网络异常（如 `httpx.ConnectTimeout`），触发容灾重试备份模型，验证流式输出的第一帧为 `data: {"failover": {...}}`，且后续生成正常。
* **非流式容灾属性测试**：验证 `provider.failover_triggered` 是否存在且正确挂载，以及 API 返回的 JSON 是否包含该属性。
* **统计时序接口测试**：往 `llm_token_usage` 表里造不同日期的测试数据，调用 `GET /api/llm/stats` 验证 `daily` 数组的累加求和及按日期排序正确。

### 3.2 前端测试与编译
* **组件回归测试**：在 `LlmSettingsView.test.ts` 中补齐 `stats` 返回中 `daily` 数组的 mock，确保 Vitest 用例及 TypeScript 编译打包完美成功。
