# Supporting Stories Horizontal Layout Design

## Goal

将 News Feed 中 `Supporting Stories` 区块从“高而竖”的三张卡片改成更紧凑的横向信息卡，降低中文长标题和长摘要把卡片撑得过高的问题，同时保留现有杂志流视觉语言。

## Scope

- 仅调整 supporting stories 卡片的结构与响应式布局
- 保持一行 3 张桌面布局
- 平板降为 2 列，手机降为 1 列
- 不调整 lead story、more in the edition 流、后端接口、排序逻辑

## Design

supporting 卡片改为双区布局：

- 顶部保留紧凑 metadata，优先展示情绪、来源和市场
- 中部改为横向主体，左侧放标题与摘要，右侧放时间与主题
- 标题和摘要更激进地截断，控制卡片高度

这样可以让三张卡在桌面端保持同一阅读节奏，不再出现每张卡都像正文页一样竖向拉长的问题。

## Responsive Rules

- `>= 1100px`：3 列
- `769px - 1099px`：2 列
- `<= 768px`：1 列

## Testing

- 新增组件测试，验证 supporting 卡片存在独立的横向 body 结构
- 运行定向 Vitest
- 运行前端 build，确保模板和样式改动不破坏编译
