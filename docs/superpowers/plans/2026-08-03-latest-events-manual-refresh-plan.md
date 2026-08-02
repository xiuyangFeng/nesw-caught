# Latest Events 精简警报与手动抓取实现计划

日期：2026-08-03

## 目标

移除截图所示的 Latest Events Runtime 警报、Raw Stream 说明标题和 AppShell 顶部 SSE 状态条，并在 Latest Events 页头加入复用现有异步抓取链路的手动刷新按钮。

## 任务拆解

1. 测试先行：更新 `NewsFeedView.test.ts`，断言警报/说明不再渲染，并覆盖按钮默认、抓取中、成功和失败状态。
2. 测试先行：更新 `AppShell.test.ts`，断言 `shell-status-rail` 消失，同时保留侧栏 `system-status`。
3. 实现 Latest Events 页：移除无用状态计算和组件导入；用轻量新闻流容器替换 `SectionCard`；加入手动抓取函数、反馈状态与无障碍文案。
4. 实现 AppShell：移除顶部状态条及只服务该状态条的计算属性，保留底层连接、轮询和侧栏诊断。
5. 验证：运行两个专项测试文件、前端全量测试、前端构建和 `git diff --check`。
6. 将实际改动、验证结果和风险写入 `docs/code-change-log.md`。

## 验收标准

- Latest Events 首屏不再出现 Runtime 警报和 Raw Stream 标题说明；
- 主内容区不再出现 SSE LIVE / Last event / Workspace 状态条；
- “抓取最新新闻”按钮可触发一次现有异步抓取请求；
- 抓取中禁止重复点击，状态结束后可恢复；
- 现有事件、主题、筛选、新闻列表、抽屉和侧栏诊断不受影响；
- 专项测试、前端全量测试和构建通过。
