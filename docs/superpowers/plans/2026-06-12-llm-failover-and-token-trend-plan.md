# 大模型故障降级可视化感知与 Token 审计时序看板执行计划 (Round 5)

本执行计划将 Round 5 迭代拆解为五个核心阶段，以保障开发和测试的稳步前进。

---

## 1. 任务拆解与推进阶段

### 阶段一：后端容灾信号传递与时序统计接口扩展 (P0)
- [ ] 修改 `backend/app/services/llm_providers.py` 中的 `AsyncOpenAICompatibleProvider.chat_stream`，在捕获重试时 `yield f"[FAILOVER_SIGNAL]:{json.dumps({...})}"`。
- [ ] 修改 `OpenAICompatibleProvider._request_completion` 与 `AsyncOpenAICompatibleProvider._request_completion`，在触发 Failover 重试时挂载 `self.failover_triggered = {...}` 状态。
- [ ] 修改 `backend/app/api/routes/llm.py` 中 `/api/llm/chat` 的 SSE 和非流式分支，转换 failover 信号，并将元数据回填入 JSON / SSE 数据帧中。
- [ ] 在 `backend/app/api/routes/llm.py` 中的 `/stats` 路由中，编写按天统计过去 7 天 Token 每日消耗量的 SQLAlchemy 聚合查询，并扩展接口响应返回。

### 阶段二：后端单元测试覆盖 (P0)
- [ ] 在 `backend/tests/test_llm_stats.py` 或 `backend/tests/test_llm_chat.py` 中编写容灾重试的 SSE 接口与非流式接口测试，确保 failover 信号被正确产出与捕获。
- [ ] 编写 `/stats` 时序的单元测试，插入多天 Token 消耗后验证响应中 `daily` 字段返回的聚合数据是否准确。
- [ ] 运行 `conda run -n news-caught pytest backend/tests` 确认后端 100% 通过。

### 阶段三：前端大模型故障感知 UI 开发 (P1)
- [ ] 修改 `frontend/src/types/api.ts`，扩展 `MarketSnapshot` 之外与大模型相关的类型声明，特别是 `/api/llm/stats` 和 `/api/llm/chat` 包含的 failover 相关接口类型。
- [ ] 重构 `frontend/src/views/ChatView.vue` 中的 SSE 读取逻辑，当捕获到包含 `failover` 的 JSON 时：
  - 调用 `toastStore.showWarning` 弹出提示。
  - 在当前会话视图顶端或信息上方渲染高斯模糊的“降级接管横幅”，展示原模型、备用模型及原因。
- [ ] 重构 `frontend/src/components/watchlist/StockDetailPanel.vue`，在 AI 研报生成的流式/非流式响应中注入同样的 failover 监听，渲染降级状态横幅。

### 阶段四：前端 Token 消耗 SVG 时序图表开发 (P1)
- [ ] 修改 `frontend/src/views/LlmSettingsView.vue`，在“模型额度审计控制台”组件内新增 SVG 折线图。
- [ ] 自绘折线图结构，支持渐变发光线条、半透明渐变面积、科技风背景虚线与日期刻度。
- [ ] 编写鼠标 Hover 十字垂直交互线与数据悬停气泡提示组件，展示当天 Prompt / Completion / Total 分项 Token 消耗量。

### 阶段五：前端测试回归与项目构建 (Verify)
- [ ] 在 `frontend/src/views/LlmSettingsView.test.ts` 中 Mock 补齐 `daily` 时序数据，修复原本由于数据字段缺失引起的潜在 TS 与 Vitest 报错。
- [ ] 运行 `npm --prefix frontend run test -- --run`，确认 100% 前端用例成功。
- [ ] 运行 `npm --prefix frontend run build`，确认前端构建无警告、无 TS 编译报错。

---

## 2. 验证基准

### 后端验证
1. 运行 `conda run -n news-caught pytest backend/tests`。
2. 确保包含新建的 `test_llm_chat_failover_sse` 及 `test_llm_stats_daily` 全绿通过。

### 前端与集成验证
1. 启动项目 `make dev`，在 LLM 配置页可以看到优雅的 Token 折线消耗图，鼠标悬停可以显示时序浮标。
2. 在 `ChatView.vue` 提问，并手动在后端配置中引入连接超时或使用无效 URL，触发 Failover 自动容灾降级，页面右上角应立刻弹出毛玻璃警示 Toast，且聊天消息正上方出现心跳发光的“降级接管中”橙黄色横幅。
