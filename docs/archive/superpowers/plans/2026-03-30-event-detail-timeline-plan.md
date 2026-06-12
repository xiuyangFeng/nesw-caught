# Event Detail Timeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把事件详情页升级为 compact header + timeline 的事件演化页，并接通时间线到单条新闻详情页的继续阅读链路。

**Architecture:** 保持后端事件详情 API 不变，只重写前端 `EventDetailView` 的布局和交互。时间线阶段标签由前端基于后端顺序轻量推导，不新增接口字段。通过前端视图测试先锁定 header、timeline item 和路由动作，再做最小实现。

**Tech Stack:** Vue 3、Vue Router、Vitest、Vue Test Utils、Tailwind utility classes

---

## Chunk 1: 测试先行锁定新事件页行为

### Task 1: 扩展事件详情页测试数据和断言

**Files:**
- Modify: `frontend/src/views/EventDetailView.test.ts`

- [ ] **Step 1: 写失败测试，覆盖 compact header 与 timeline item 元信息**

补充断言，要求页面成功渲染后能够看到：

- 事件标题和摘要
- `event_type / sentiment / market / primary_symbol / related_symbols`
- `source_count / news_count / last_seen_at`
- 时间线项里的阶段标签：第一条 `首发`，第二条 `跟进`，后续 `更新`
- 时间线项里的来源、时间、情绪

- [ ] **Step 2: 运行测试并确认失败**

Run: `npm --prefix frontend run test -- --run src/views/EventDetailView.test.ts`

Expected: 至少 1 条断言失败，说明当前视图还未满足新的布局契约

- [ ] **Step 3: 写失败测试，覆盖时间线动作**

补充断言：

- 点击 `查看新闻详情` 会 `router.push({ name: 'news-detail', params: { id } })`
- 当 `canonical_url` 存在时显示 `打开原文`
- 当 `canonical_url` 为空时不显示该动作

- [ ] **Step 4: 重新运行测试并确认仍失败**

Run: `npm --prefix frontend run test -- --run src/views/EventDetailView.test.ts`

Expected: 动作相关断言失败，且失败原因与新交互缺失一致

## Chunk 2: 实现事件演化页

### Task 2: 重写 EventDetailView 布局和交互

**Files:**
- Modify: `frontend/src/views/EventDetailView.vue`
- Reference: `frontend/src/views/NewsDetailView.vue`

- [ ] **Step 1: 最小实现 compact header**

在 `EventDetailView.vue` 中压缩页头，保留返回动作、事件标题、简短摘要和关键 chips。

- [ ] **Step 2: 最小实现 timeline 布局**

在时间线 section 中：

- 遍历 `eventDetail.news_items`
- 基于索引生成阶段标签
- 渲染来源、时间、情绪、标题、摘要
- 保持严格使用后端顺序，不做前端重排

- [ ] **Step 3: 接入时间线动作**

新增：

- `openNewsDetail(newsId: number)`，跳转 `news-detail`
- 原文链接按钮，仅在 `canonical_url` 存在时渲染

- [ ] **Step 4: 运行事件页测试确认转绿**

Run: `npm --prefix frontend run test -- --run src/views/EventDetailView.test.ts`

Expected: PASS

### Task 3: 校验路由集成未回归

**Files:**
- Reference: `frontend/src/router/index.ts`
- Reference: `frontend/src/views/NewsFeedView.test.ts`

- [ ] **Step 1: 运行关联测试**

Run: `npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/router/index.test.ts src/views/NewsDetailView.test.ts`

Expected: PASS

- [ ] **Step 2: 若有回归，做最小修正**

只修与事件页跳转链路直接相关的问题，不扩展范围。

## Chunk 3: 记录、验证与收尾

### Task 4: 更新文档与变更记录

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: 追加本次变更记录**

记录：

- 事件详情页改为 compact header + timeline
- 时间线阶段标签与双动作
- 涉及测试更新

- [ ] **Step 2: 运行聚焦验证**

Run: `npm --prefix frontend run test -- --run src/views/EventDetailView.test.ts src/views/NewsFeedView.test.ts src/router/index.test.ts src/views/NewsDetailView.test.ts`

Expected: PASS

- [ ] **Step 3: 运行构建验证**

Run: `npm --prefix frontend run build`

Expected: PASS

- [ ] **Step 4: 运行前端全量测试**

Run: `npm --prefix frontend run test -- --run`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/EventDetailView.vue frontend/src/views/EventDetailView.test.ts docs/code-change-log.md
git commit -m "feat: redesign event detail timeline"
```
