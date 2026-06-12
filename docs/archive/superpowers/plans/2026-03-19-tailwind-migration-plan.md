# Tailwind Migration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不破坏当前前端行为和信息密度的前提下，引入 Tailwind CSS 并逐步替换现有分散的样式实现，建立可持续维护的前端样式基础设施。

**Architecture:** 采用“Tailwind 与现有 CSS 共存”的渐进迁移方案。先建立 Tailwind theme 与全局入口，再迁移 `AppShell` 和高复用组件，之后按页面逐个重构，最后清理失效的 scoped CSS 和旧语义类。

**Tech Stack:** Vue 3, Vite, TypeScript, Tailwind CSS, PostCSS, Vitest

---

## File Map

- Create: `frontend/tailwind.config.js` 或 `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Modify: `frontend/package.json`
- Modify: `frontend/src/assets/main.css`
- Modify: `frontend/index.html`
- Modify: `frontend/src/components/layout/AppShell.vue`
- Modify: `frontend/src/components/layout/AppShell.test.ts`
- Modify: `frontend/src/components/common/SectionCard.vue`
- Modify: `frontend/src/components/common/SectionCard.test.ts`
- Modify: `frontend/src/components/common/StatusBanner.vue`
- Modify: `frontend/src/components/common/StatusBanner.test.ts`
- Modify: `frontend/src/components/common/LoadingBlock.vue`
- Modify: `frontend/src/components/common/StaleBadge.vue`
- Modify: `frontend/src/components/dashboard/HeroMetrics.vue`
- Modify: `frontend/src/components/dashboard/HeroMetrics.test.ts`
- Modify: `frontend/src/components/dashboard/TopicBoard.vue`
- Modify: `frontend/src/components/dashboard/TopicBoard.test.ts`
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/views/DashboardView.test.ts`
- Modify: `frontend/src/views/NewsFeedView.vue`
- Modify: `frontend/src/views/NewsFeedView.test.ts`
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/views/WatchlistView.test.ts`
- Modify: `frontend/src/views/WatchlistDetailView.vue`
- Modify: `frontend/src/views/WatchlistDetailView.test.ts`
- Modify: `frontend/src/views/NewsDetailView.vue`
- Modify: `frontend/src/views/NewsDetailView.test.ts`
- Modify: `frontend/src/views/TopicDetailView.vue`
- Modify: `frontend/src/views/XMonitorView.vue`
- Modify: `frontend/src/views/XMonitorView.test.ts`
- Modify: `frontend/src/views/LlmSettingsView.vue`
- Modify: `frontend/src/views/LlmSettingsView.test.ts`
- Modify: `frontend/src/views/NotifySettingsView.vue`
- Modify: `docs/code-change-log.md`

## Chunk 1: Tailwind Foundation

### Task 1: Add the build pipeline and theme mapping

**Files:**
- Create: `frontend/tailwind.config.js` or `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Modify: `frontend/package.json`
- Modify: `frontend/src/assets/main.css`
- Modify: `frontend/index.html`

- [ ] **Step 1: Write the failing infrastructure expectation**
  - 记录迁移前状态：`frontend/package.json` 中没有 `tailwindcss`、`postcss`、`autoprefixer`。
  - 明确 `main.css` 里现有 token 需要映射到 Tailwind theme，而不是被默认色板直接覆盖。

- [ ] **Step 2: Install and configure Tailwind**

Run: `npm --prefix frontend install -D tailwindcss postcss autoprefixer`
Expected: lockfile 更新，Tailwind 与 PostCSS 进入 `devDependencies`。

- [ ] **Step 3: Add minimal Tailwind configuration**
  - 配置 `content` 覆盖 `index.html`、`src/**/*.{vue,ts}`。
  - 在 `theme.extend.colors` 中映射现有语义 token：`bg`、`panel`、`text`、`muted`、`system`、`positive`、`negative`。
  - 保持当前暗色终端背景，不在此步引入新的组件库。

- [ ] **Step 4: Restructure global CSS entry**
  - 在 `frontend/src/assets/main.css` 中引入 Tailwind 层。
  - 保留全局 reset、字体、少量 CSS 变量和迁移期兼容类。
  - 删除与 Tailwind 明显重复、且可在后续组件迁移中覆盖的全局样式。

- [ ] **Step 5: Verify the frontend still builds**

Run: `npm --prefix frontend run build`
Expected: PASS

## Chunk 2: Layout Shell Migration

### Task 2: Migrate `AppShell` without changing behavior

**Files:**
- Modify: `frontend/src/components/layout/AppShell.vue`
- Modify: `frontend/src/components/layout/AppShell.test.ts`

- [ ] **Step 1: Write or extend failing layout tests**
  - 断言侧边导航、当前激活路由标识、系统状态区仍可渲染。
  - 如果测试依赖 class 过于脆弱，优先断言语义文本和 `data-role` 标记，而不是具体 Tailwind class 全量快照。

- [ ] **Step 2: Run tests to verify current constraints**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`
Expected: PASS before refactor, providing a baseline for non-style behavior.

- [ ] **Step 3: Rewrite shell layout with Tailwind**
  - 把 grid、sticky、panel、nav item、status card 的 scoped CSS 迁移到模板 class。
  - 仅保留确实不适合内联 class 的少量 scoped CSS；迁移后删除冗余样式块。
  - 保持当前信息结构、文案和响应式断点行为一致。

- [ ] **Step 4: Re-run shell tests**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`
Expected: PASS

## Chunk 3: Shared Component Migration

### Task 3: Consolidate reusable visual primitives

**Files:**
- Modify: `frontend/src/components/common/SectionCard.vue`
- Modify: `frontend/src/components/common/SectionCard.test.ts`
- Modify: `frontend/src/components/common/StatusBanner.vue`
- Modify: `frontend/src/components/common/StatusBanner.test.ts`
- Modify: `frontend/src/components/common/LoadingBlock.vue`
- Modify: `frontend/src/components/common/StaleBadge.vue`

- [ ] **Step 1: Write or extend failing component tests**
  - 覆盖标题、slot 内容、状态文案、加载占位和 badge 文案渲染。
  - 不把测试绑定到具体颜色 class，避免后续 theme 迭代导致误报。

- [ ] **Step 2: Run shared-component tests**

Run: `npm --prefix frontend run test -- --run src/components/common/SectionCard.test.ts src/components/common/StatusBanner.test.ts`
Expected: PASS baseline

- [ ] **Step 3: Migrate shared components to Tailwind-backed patterns**
  - 收敛成统一的 panel、pill、banner、skeleton 表达方式。
  - 对重复 class 组合，优先通过组件 props 或少量全局语义类收口，避免模板过长。

- [ ] **Step 4: Re-run shared-component tests**

Run: `npm --prefix frontend run test -- --run src/components/common/SectionCard.test.ts src/components/common/StatusBanner.test.ts`
Expected: PASS

## Chunk 4: Dashboard First Page Migration

### Task 4: Migrate dashboard components and view as the first complete page

**Files:**
- Modify: `frontend/src/components/dashboard/HeroMetrics.vue`
- Modify: `frontend/src/components/dashboard/HeroMetrics.test.ts`
- Modify: `frontend/src/components/dashboard/TopicBoard.vue`
- Modify: `frontend/src/components/dashboard/TopicBoard.test.ts`
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/views/DashboardView.test.ts`

- [ ] **Step 1: Extend failing dashboard tests where coverage is missing**
  - 关键指标卡、主题板块和整体页面骨架都要有最小可回归断言。
  - 对数值区、列表区和空状态分别覆盖至少一个断言。

- [ ] **Step 2: Run dashboard tests to lock baseline**

Run: `npm --prefix frontend run test -- --run src/components/dashboard/HeroMetrics.test.ts src/components/dashboard/TopicBoard.test.ts src/views/DashboardView.test.ts`
Expected: PASS baseline

- [ ] **Step 3: Migrate dashboard layout and typography**
  - 用 Tailwind 重写 grid、section spacing、metric card、mono number、hover/focus 态。
  - 保留当前数据优先级和阅读顺序，不为了“更炫”牺牲可扫描性。

- [ ] **Step 4: Re-run dashboard tests**

Run: `npm --prefix frontend run test -- --run src/components/dashboard/HeroMetrics.test.ts src/components/dashboard/TopicBoard.test.ts src/views/DashboardView.test.ts`
Expected: PASS

## Chunk 5: Remaining Views Page by Page

### Task 5: Migrate the remaining views in small independent batches

**Files:**
- Modify: `frontend/src/views/NewsFeedView.vue`
- Modify: `frontend/src/views/NewsFeedView.test.ts`
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/views/WatchlistView.test.ts`
- Modify: `frontend/src/views/WatchlistDetailView.vue`
- Modify: `frontend/src/views/WatchlistDetailView.test.ts`
- Modify: `frontend/src/views/NewsDetailView.vue`
- Modify: `frontend/src/views/NewsDetailView.test.ts`
- Modify: `frontend/src/views/TopicDetailView.vue`
- Modify: `frontend/src/views/XMonitorView.vue`
- Modify: `frontend/src/views/XMonitorView.test.ts`
- Modify: `frontend/src/views/LlmSettingsView.vue`
- Modify: `frontend/src/views/LlmSettingsView.test.ts`
- Modify: `frontend/src/views/NotifySettingsView.vue`

- [ ] **Step 1: Pick one view at a time**
  - 迁移顺序建议：`NewsFeed` -> `Watchlist` -> `WatchlistDetail` -> `NewsDetail` -> `TopicDetail` -> `XMonitor` -> `LLM Settings` -> `Notify`。
  - 每完成一个页面，就立刻运行该页面相关测试和一次 build，不要堆到最后。

- [ ] **Step 2: For each page, write or extend failing tests first**
  - 补足页面骨架、按钮、筛选区、列表区、错误/空状态的最小断言。
  - 只在必要时断言关键 class；优先断言可见行为和语义结构。

- [ ] **Step 3: Migrate page styles**
  - 把 layout、spacing、surface、form control、dense list/table 迁移到 Tailwind。
  - 仅在 Tailwind 表达代价明显偏高时保留少量 scoped CSS。

- [ ] **Step 4: Verify each page immediately**
  - 运行该页面对应 vitest 文件。
  - 再运行一次 `npm --prefix frontend run build`。

## Chunk 6: Cleanup and Final Verification

### Task 6: Remove dead styles and verify the migration holistically

**Files:**
- Modify: `frontend/src/assets/main.css`
- Modify: all migrated components/views as needed
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Remove obsolete global classes and scoped CSS**
  - 清理已无引用的 `.surface`、`.pill` 等兼容类，前提是所有消费者都已迁移完成。
  - 删除迁移后空置或重复的 `<style scoped>` 块。

- [ ] **Step 2: Run the full frontend test suite**

Run: `npm --prefix frontend run test`
Expected: PASS

- [ ] **Step 3: Run the production build**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 4: Perform manual UI verification**
  - 桌面宽屏检查 `AppShell`、`Dashboard`、`X Monitor`、`LLM Settings`。
  - 窄屏检查单列回落和主要按钮可点击性。
  - 检查 hover、focus、disabled、empty/error/loading 状态是否仍清晰。

- [ ] **Step 5: Update the change log**
  - 记录 Tailwind 引入范围、页面迁移完成度、保留的兼容 CSS、验证命令和人工验收范围。
