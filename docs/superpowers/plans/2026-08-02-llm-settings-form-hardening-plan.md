# LLM 模型设置表单稳定性优化计划

- [x] 在 `LlmSettingsView.test.ts` 增加数字输入导致 `raw.trim` 异常的回归用例，确认修复前失败。
- [x] 在 `LlmConfigForm.vue` 实现安全数字归一化、字段级校验、Base URL 变更时的 API Key 规则和可访问性提示。
- [x] 补充非法 URL、负数以及编辑密钥保留行为测试，运行目标前端测试。
- [x] 运行前端构建和后端 LLM 配置相关测试，检查 diff，并更新 `docs/code-change-log.md` 的最终验证结果与风险。
