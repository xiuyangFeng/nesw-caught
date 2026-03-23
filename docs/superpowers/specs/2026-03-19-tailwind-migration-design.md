# Tailwind Migration Design

**Goal**

将前端样式体系迁移到 Tailwind CSS，但不以一次性推翻现有 UI 为目标；保留当前 `Market Intelligence Terminal` 的暗色终端视觉语言，把现有 design tokens、公共语义类和核心布局逐步映射到可维护的 Tailwind theme 与组件约定上。

**Context**

- 当前前端技术栈为 Vue 3 + Vite + TypeScript，没有引入 UI 组件库或原子化 CSS 框架。
- 现有 UI 并非完全无体系的“手写 CSS”，而是已经存在一层全局设计变量与语义类，例如 `frontend/src/assets/main.css` 中的 `--bg`、`--panel`、`--muted`、`.surface`、`.pill`。
- 核心页面与布局组件仍大量依赖各自的 `<style scoped>`，例如 `frontend/src/components/layout/AppShell.vue`，这会在页面持续演进时放大样式分散、复用困难和视觉一致性维护成本。
- 本轮目标是让后续 UI 重塑具备稳定基础，而不是在一个提交中同时完成框架迁移、视觉全面改版和交互系统重构。

**Approach Options**

1. Big bang: 一次性把所有组件和页面改成 Tailwind
   - 优点：理论上最“彻底”，旧样式清理速度快。
   - 缺点：回归面最大；很难定位布局和视觉问题；不适合当前已有多页视图和较多测试覆盖的项目。

2. Tailwind 与现有 CSS 共存，按布局层级逐步迁移
   - 优点：可以先稳定基础设施和 theme，再按 `AppShell -> common components -> views` 顺序分块迁移；每一步都可单独验证和回滚。
   - 缺点：迁移期内会同时存在 Tailwind 与少量旧 CSS，需要额外约束避免“双系统”长期并存。

3. 保留现有 CSS，只做轻量视觉增强
   - 优点：风险最小，投入最低。
   - 缺点：不能解决样式维护成本和复用问题，也不满足明确的 Tailwind 迁移目标。

**Recommendation**

采用方案 2。先把 Tailwind 作为新的样式基础设施引入，再以“theme 映射、通用表面/排版/状态模式、布局外壳、页面分块迁移、最后清理旧样式”的顺序推进。这样既保留当前视觉资产，也能把风险压缩到可控范围内。

**Design**

### 1. Migration Principles

- 不把“引入 Tailwind”与“重新发明整套视觉风格”绑定在一起。
- 先保留当前暗色终端基调，再在迁移过程中做有限度强化，例如更稳定的间距、排版和交互节奏。
- 允许迁移期内 Tailwind 与现有 CSS 变量共存，但必须定义结束条件，避免半迁移状态长期存在。
- 优先迁移布局骨架和复用度高的基础组件，再迁移单页业务视图。

### 2. Theme and Token Mapping

- 在 `frontend` 中引入 Tailwind、PostCSS 和配置文件。
- `tailwind.config.*` 不直接照搬默认 `slate` 色板，而是先映射现有语义 token：
  - `bg`, `panel`, `panel-strong`, `border`, `text`, `muted`
  - `system`, `positive`, `negative`, `accent`
- `frontend/src/assets/main.css` 保留为全局入口，但职责收敛为：
  - Tailwind base/components/utilities 导入
  - 字体声明与少量浏览器级 reset
  - 暂时保留的 CSS 变量与迁移期兼容样式
- 不在第一阶段引入新的组件库；先依赖 Vue 现有组件层完成样式迁移。

### 3. Component Styling Strategy

- 建立少量明确的可复用视觉模式，而不是在模板里无约束堆积 class：
  - surface/panel
  - terminal surface
  - status pill
  - section header
  - dense data list / table shell
- 对于重复度高的 class 组合，优先通过：
  - 组件封装
  - 有命名的模板片段
  - `@layer components` 中的少量语义类
  来保持可读性。
- 不要求所有旧的 `<style scoped>` 一步删空；只在对应组件完成 Tailwind 化后移除其冗余样式。

### 4. Migration Order

1. 基础设施
   - 安装 Tailwind 及 PostCSS
   - 配置 content 扫描范围
   - 建立 theme token 和基础字体/背景入口
2. 布局壳层
   - 先迁移 `AppShell.vue`
   - 确保侧边导航、系统状态卡、主内容区断点行为稳定
3. 通用组件
   - 优先迁移 `common/`、`dashboard/` 等复用度高的基础展示组件
4. 主要页面
   - 按页面独立推进：`Dashboard`、`News Feed`、`Watchlist`、`X Monitor`、`LLM Settings`、`Notify`
   - 每次只完成一个页面闭环
5. 清理阶段
   - 删除已无引用的全局类和组件内 scoped CSS
   - 收敛未使用 token 与兼容样式

### 5. Verification Strategy

- 自动验证
  - `npm --prefix frontend run test`
  - `npm --prefix frontend run build`
- 手动验证
  - 桌面宽屏下的 `AppShell` 导航、滚动和 sticky 行为
  - 窄屏断点下的单列回落
  - `Dashboard`、`X Monitor`、`LLM Settings` 三个高密度页面的视觉完整性
  - 表单、按钮、pill、卡片、列表 hover/focus 态
- 如果后续引入截图对比或 Playwright，可作为增强项，但不是本轮迁移前置条件。

### 6. Non-Goals

- 本轮不引入图表库或新的 headless component library。
- 本轮不做数据层、store 层或 API 契约改动。
- 本轮不以“所有页面完全去掉自定义 CSS”为硬指标，重点是完成可持续迁移路径。

### 7. Risks

- Tailwind class 直接写满模板，可能让复杂页面可读性变差；需要通过组件抽象和少量语义层约束。
- 迁移期双系统共存，若没有清理清单，容易长期残留重复 token 和样式。
- 当前已有视觉语言已经成型，若迁移时过度追求“新潮”，反而可能损失产品辨识度和信息密度。
