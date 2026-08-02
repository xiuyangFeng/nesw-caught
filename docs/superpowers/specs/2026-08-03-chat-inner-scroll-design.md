# AI 对话内窗口滚动设计

## 问题

长对话会把聊天页右侧 Grid 的中间轨道按内容最小高度撑开。虽然 `ChatView` 设置了视口相关高度，Grid item 默认的 `min-height: auto` 仍允许消息内容突破该高度，最终表现为整个页面持续向下增长，顶部模型栏和底部输入区随页面滚动离开视口。

## 目标

- 聊天工作区始终限制在应用壳层当前视口高度内。
- 只有消息记录区域垂直滚动；模型栏、会话侧栏的新建按钮和底部输入栏保持可见。
- 消息滚动到顶部或底部时不把滚动继续传递给外层页面。
- 不改变其他页面的 AppShell 滚动策略。

## 方案

1. `ChatView` 根 Grid 使用动态视口高度 `calc(100dvh - 100px)`，增加 `min-h-0` 与 `overflow-hidden`。
2. 右侧三行 Grid 增加 `min-h-0 overflow-hidden`，让 `1fr` 消息轨道可以真正收缩。
3. `ChatMessageList` 外层增加 `overflow-hidden`；实际消息 viewport 保持 `overflow-y-auto`，并增加 `overscroll-behavior: contain` 与稳定滚动条槽位。
4. AppShell 仅在 `/chat` 路由且达到桌面 `shell` 断点时锁定为单视口高度，并把左侧导航改为必要时内部滚动；窄屏单列布局继续使用正常文档流，避免固定一屏后第二行主内容落到不可访问区域。其他路由仍使用原整页滚动。
5. 用组件测试固定上述布局契约，并通过浏览器实测长消息下页面高度与视口高度不再随内容增长。

## 风险

- `100dvh` 面向现代浏览器；Tailwind 输出仍保留明确的 CSS calc，不影响当前桌面 Chrome/Electron 环境。
- 本次只在桌面 `shell` 布局约束 `/chat`；窄屏聊天页和其他长页面仍按原有整页滚动行为工作。
