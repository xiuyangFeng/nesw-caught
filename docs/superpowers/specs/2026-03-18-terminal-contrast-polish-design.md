# Terminal Contrast Polish Design

## 背景

当前前端已经转向冷蓝灰终端风，但多个局部组件仍沿用浅灰白半透明表面，例如自选股表格、主题卡、X Monitor 指标卡、筛选框、关联新闻卡，以及部分详情页信息块。这些浅表面叠加在深背景之上后，导致文字对比度不足，用户在截图中已经明确反馈“字看不清，科技感不够”。

另外，`brainstorming` visual companion 的启动脚本并不在仓库 `scripts/` 下，而是在 skill 目录：

- `/Users/xiuyang/.codex/skills/brainstorming/scripts/start-server.sh`

因此直接在仓库根目录执行 `scripts/start-server.sh` 会报不存在。

## 目标

- 把截图中发白、发灰、低对比度的表面统一替换成深色终端表面。
- 提升正文、次级文字、标签和表格内容的可读性。
- 保持冷蓝灰科技终端气质，不引入花哨或高噪声赛博配色。
- 在仓库内提供一个 `scripts/start-server.sh` 包装脚本，便于后续直接调用 visual companion。

## 非目标

- 不重做页面布局结构。
- 不改数据流、路由、接口或状态管理。
- 不移除现有 `newsEditorial` 工具函数和测试。

## 设计方案

### 1. 统一深色终端表面层级

新增并收敛全局表面 token：

- `--panel-stronger` 用于表格和卡片主表面
- `--panel-soft` 用于二级面板和 hover
- `--field-bg` 用于输入框、筛选框和下拉框
- `--text-faint` 用于次级信息，但仍需保持在深色背景上可读

所有原本使用 `rgba(255, 255, 255, 0.34~0.9)` 和 `#fffdf8` 的区域，统一改到上述深色面板层级。

### 2. 文本与语义色对比增强

- 主文本维持冷白。
- 次级文本从当前偏灰蓝、偏低对比度的状态，提亮到更清晰的灰蓝。
- positive / negative pill 保持语义色，但底色更深、更薄。
- 链接和按钮使用青蓝高亮，不再依赖浅色底托起可读性。

### 3. 优先修复的组件范围

第一优先级：

- `frontend/src/components/watchlist/WatchlistTable.vue`
- `frontend/src/components/dashboard/TopicBoard.vue`
- `frontend/src/views/WatchlistView.vue`
- `frontend/src/views/XMonitorView.vue`

第二优先级：

- `frontend/src/views/TopicDetailView.vue`
- `frontend/src/views/NewsDetailView.vue`
- `frontend/src/components/common/SectionCard.vue`

### 4. start-server 包装脚本

在仓库新增：

- `scripts/start-server.sh`

职责：

- 转发到 `/Users/xiuyang/.codex/skills/brainstorming/scripts/start-server.sh`
- 保留原始参数透传
- 当目标脚本不存在时，输出明确错误信息并退出非零

这样后续在仓库根目录执行 `scripts/start-server.sh --project-dir ...` 就可以直接使用。

## 测试与验证

- 先写组件测试，锁定新的“终端深色表面”结构钩子。
- 跑针对性 Vitest，覆盖至少：
  - `WatchlistTable`
  - `TopicBoard`
- 跑 `npm --prefix frontend run build`
- 手工说明 `scripts/start-server.sh` 的解析结果和实际路径来源

## 风险

- 本轮以视觉可读性为主，测试更偏结构钩子而不是像素级视觉断言。
- 全局 token 收紧后，个别未单测覆盖的页面视觉会同步变化，但这是本轮预期收益的一部分。
