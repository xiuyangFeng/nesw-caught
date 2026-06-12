# Dashboard 三列高密度布局 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Dashboard 重构为桌面端三列并排、列内独立滚动的高密度情报看板，让主题聚合不再把最新新闻整体挤到首屏之外。

**Architecture:** 仅调整 `DashboardView.vue` 的布局和展示密度，不改 store、接口或路由。三列共享一个桌面端高度约束，各自通过独立滚动容器承载更紧凑的预览项；测试以 `DashboardView.test.ts` 锁定结构标识和关键预览行为。

**Tech Stack:** Vue 3, Vue Router, Pinia, Vue Test Utils, Vitest, Vite

---

## Chunk 1: 锁定新布局行为

### Task 1: 先写失败测试约束三列看板结构

**Files:**
- Modify: `frontend/src/views/DashboardView.test.ts`
- Test: `frontend/src/views/DashboardView.test.ts`

- [ ] **Step 1: 写失败测试**

新增断言，要求 Dashboard：
- 存在桌面端三列布局容器标识
- 存在 `movers / topics / feed` 三个独立列标识
- 每列都有独立滚动区域标识
- `News Feed` 使用紧凑条目标识
- `自选股异动` 仍只展示 3 条预览

- [ ] **Step 2: 运行测试确认失败**

Run: `npm --prefix frontend run test -- --run src/views/DashboardView.test.ts`

Expected: FAIL，因为当前组件仍是两段式布局，也没有独立滚动和紧凑新闻条目标识。

## Chunk 2: 实现三列高密度布局

### Task 2: 重写 Dashboard 主网格和列内容密度

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`
- Test: `frontend/src/views/DashboardView.test.ts`

- [ ] **Step 1: 调整主网格结构**

把 `dashboard-grid` 改为桌面端三列：
- 左列 `自选股异动`
- 中列 `资讯主题聚合`
- 右列 `News Feed`

为网格和列容器增加明确的 `data-role` 标识，方便测试锁定。

- [ ] **Step 2: 给每列加入独立滚动容器**

在桌面端为三列内容区设置统一高度和 `overflow-y-auto`，标题区保持在滚动区外。

- [ ] **Step 3: 压缩异动和新闻预览项**

更新 `DashboardView.vue` 中的两块局部渲染：
- 异动预览项改为更紧凑的列表行
- 新闻预览改为标题优先的一行式/两行式紧凑条目，而不是旧的大卡片

- [ ] **Step 4: 收紧主题聚合容器密度**

通过 Dashboard 容器级样式，压缩主题列的节奏与摘要行数，让 `TopicBoard` 在不改数据模型的前提下更适合列式看板。

- [ ] **Step 5: 运行目标测试确认通过**

Run: `npm --prefix frontend run test -- --run src/views/DashboardView.test.ts`

Expected: PASS

## Chunk 3: 完整验证与记录

### Task 3: 运行验证并更新记录

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: 运行 Dashboard 相关测试**

Run: `npm --prefix frontend run test -- --run src/views/DashboardView.test.ts`

Expected: PASS

- [ ] **Step 2: 运行前端构建**

Run: `npm --prefix frontend run build`

Expected: build 成功，exit code 0

- [ ] **Step 3: 更新代码变更记录**

在 `docs/code-change-log.md` 顶部新增记录，说明：
- Dashboard 改为三列独立滚动布局
- 三块内容密度收紧方式
- 实际验证命令
- 剩余风险（如窄屏回退和固定高度策略）
