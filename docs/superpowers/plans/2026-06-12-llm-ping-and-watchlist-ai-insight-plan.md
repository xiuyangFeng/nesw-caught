# 2026-06-12-llm-ping-and-watchlist-ai-insight-plan.md

## 目的

本文件为 news-caught 第三轮优化的实现与验证计划。

## 任务拆解与开发顺序

### Phase 1: 回归测试修复与加固
1. **llm_providers.py**
   - 将 `self.config.id` 替换为 `getattr(self.config, "id", 0)`。
   - 包含的 4 处均完成替换：`_request_completion`, `embed_text`, `AsyncOpenAICompatibleProvider._request_completion`, `AsyncOpenAICompatibleProvider.chat_stream`。
2. **测试验证**
   - 运行 `conda run -n news-caught pytest backend/tests/test_news_relevance_annotation.py`。
   - 确认该测试顺利通过。

### Phase 2: 后端端点开发与测试
1. **API 新增**
   - 在 `backend/app/api/routes/llm.py` 新增 `POST /api/llm/config/{config_id}/ping`。
   - 在 `backend/app/api/routes/watchlist.py` 新增 `POST /api/watchlist/{symbol}/ai-insight`。
2. **模型与 Schema 定义**
   - 在 `backend/app/schemas/llm.py` 中确认 `LLMConnectionTestView` 的定义是否满足，或扩展支持时延。
   - 在 `backend/app/schemas/watchlist.py` 中新增 `WatchlistAiInsightView`。
3. **编写单元测试**
   - 在 `backend/tests/test_llm_stats.py` 中新增对 `config_id` ping 连通测试和耗时计量的测试用例。
   - 在 `backend/tests/test_watchlist_research.py` 中新增对 `POST /api/watchlist/{symbol}/ai-insight` 动作及 Token 消耗审计落库的测试用例。
4. **全量回归**
   - 运行 `conda run -n news-caught pytest backend/tests` 确认 308 个测试全绿。

### Phase 3: 前端 API 适配与 Mock
1. **apiClient 扩展**
   - 修改 `frontend/src/api/client.ts` 注册 `pingLlmConfig` 与 `getWatchlistAiInsight`。
2. **mock 扩展**
   - 修改 `frontend/src/api/mock.ts` 适配上述两个新接口。
3. **Vitest 测试补充**
   - 在前端 client.test.ts 补充对这二者的单元测试。

### Phase 4: 前端 Store 与 UI 组件开发
1. **LlmStore 拓展**
   - 新增 `pingStatuses` 和 `pingConfig(id)`。
2. **WatchlistStore 拓展**
   - 新增 `aiInsights` 和 `loadAiInsight(symbol)`。
3. **LlmSettingsView UI 升级**
   - 为模型卡片注入 `📡 测速` 按钮。
   - 实现延迟微徽章（绿色/黄色/连接失败闪烁）展示。
4. **StockDetailPanel UI 升级**
   - 新增 `AI Insight Workspace` 投研卡片。
   - 实现流光加载动画。
   - 引入 Markdown 渲染支持。
5. **打包验证**
   - 运行 `npm --prefix frontend run build` 确保无报错。
   - 运行前端单元测试确认全绿。

## 验证矩阵

### 自动验证
```bash
conda run -n news-caught pytest backend/tests
npm --prefix frontend run build
npm --prefix frontend run test -- --run
```

### 手动验证
1. 单击 LlmSettings 页面卡片的测速按钮，观察是否有网络时延秒出并渲染微徽章。
2. 进入个股详情页（如 0700.HK），点击生成 AI 投研洞察，观察加载态、Markdown 渲染是否整洁、以及 Token 消耗面板数据是否增加。
