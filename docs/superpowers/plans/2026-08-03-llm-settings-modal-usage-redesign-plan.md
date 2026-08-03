# LLM 设置弹窗化与用量账本实现计划

日期：2026-08-03

1. 更新 `LlmSettingsView.test.ts`：固定页面仅显示配置入口、点击打开居中 dialog、编辑复用 dialog、保存成功关闭。
2. 更新 `TokenTrendChart.test.ts`：固定输入/输出堆叠柱、日期、总量和交互明细；新增 `TokenUsageConsole.test.ts` 覆盖紧凑指标、模型排行、预算和刷新。
3. 新增 `LlmConfigModal.vue`，负责居中遮罩、关闭行为和编辑配置注入。
4. 将 `LlmConfigForm.vue` 收敛为纯表单内容，新增 `saved/cancel` 事件并保留现有校验、预设和保存契约。
5. 重构 `LlmSettingsView.vue` 页面布局和 `LlmConfigList.vue` 空态文案。
6. 重写 `TokenTrendChart.vue` 为堆叠柱状图，重构 `TokenUsageConsole.vue` 为紧凑用量账本。
7. 运行专项测试、前端全量测试、构建和 `git diff --check`，回填代码变更记录。
