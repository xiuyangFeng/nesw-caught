# AI 对话内窗口滚动实现计划

1. 在 `ChatView.test.ts` 和 `ChatMessageList.test.ts` 先增加布局契约失败测试。
2. 为聊天根 Grid、右侧列和消息 viewport 增加高度收缩、overflow 与 overscroll 约束。
3. 运行目标测试和前端生产构建。
4. 在浏览器中构造长对话，验证外层页面不增长、消息内窗可滚动、输入栏保持可见。
5. 更新 `docs/code-change-log.md`。
