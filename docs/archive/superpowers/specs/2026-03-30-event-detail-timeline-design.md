# Event Detail Timeline Design

## 背景

首页 `Latest Events` 已经完成事件卡压缩和事件详情跳转，但当前 [EventDetailView.vue](/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/frontend/src/views/EventDetailView.vue) 仍然只是“摘要卡 + 普通新闻列表”。用户点进来后，事件级信息承接不足，阅读路径也没有自然衔接到单条新闻详情。

## 目标

把事件详情页升级为真正的“事件演化页”：

- 顶部摘要压缩成一屏内可扫完的 compact header
- 中部改成有节奏的时间线，而不是普通卡片列表
- 每条时间线新闻都能继续进入现有 `/news/:id` 详情页
- 保留现有 loading / not-found / generic-error 三态

本轮不做来源筛选、symbol 筛选或首发过滤器，避免把范围扩成一个新的分析工作台。

## 非目标

- 不修改后端事件详情接口契约
- 不新增事件持久化或新的详情字段
- 不改首页 feed-layout 数据流
- 不做拖拽、批注或多栏对比视图

## 方案对比

### 方案 A：轻量视觉优化

只收紧顶部信息、给新闻项增加跳转按钮。

优点：

- 改动小
- 风险低

缺点：

- 事件详情页的对象感仍然弱
- 用户进入后仍然像在看一个普通列表

### 方案 B：事件演化页

顶部使用 compact header，中部用 timeline 呈现新闻演化，每条新闻提供“查看新闻详情”和“打开原文”动作。

优点：

- 交互对象从“列表”升级为“事件”
- 对当前数据契约友好，不需要后端改字段
- 最能承接首页的点击动机

缺点：

- 需要重写详情页布局和测试

### 方案 C：事件工作台

在方案 B 上继续加来源筛选、symbol 筛选、分组聚类。

优点：

- 信息消费效率更高

缺点：

- 范围过大
- 会引入新的状态管理和更多交互验证

本轮采用方案 B。

## 页面结构

### 1. Compact Header

页头分为两层：

- 顶部操作层：返回 `Latest Events`
- 主体摘要层：事件标题、简短摘要、关键指标 chips

关键指标只保留：

- `event_type`
- `sentiment_label`
- `market`
- `primary_symbol`
- `related_symbols`
- `source_count`
- `news_count`
- `last_seen_at`

布局目标是压缩高度，避免再次形成大面积深色信息墙。

### 2. Timeline Section

时间线使用左右结构：

- 左侧为时间轨道和节点
- 右侧为新闻卡片

每条新闻展示：

- 阶段标签：`首发` / `跟进` / `更新`
- 来源
- 时间
- 情绪标签
- 标题
- 摘要
- 动作区

阶段标签不依赖后端新字段，直接基于当前时间线顺序生成：

- 第 1 条：`首发`
- 第 2 条：`跟进`
- 第 3 条及以后：`更新`

这是一个轻量语义标签，目的是帮助用户形成阅读节奏，而不是对新闻进行严格新闻学分类。

### 3. Item Actions

每条时间线项提供两个动作：

- `查看新闻详情`：跳转到现有 `/news/:id`
- `打开原文`：若存在 `canonical_url`，则以新窗口打开

这样用户可以沿两条路径继续阅读：

- 在产品内深入看结构化新闻详情
- 跳到源站看原始文章

## 交互与状态

### 正常态

- 加载成功后展示 compact header 与 timeline
- 时间线严格使用后端返回顺序，不在前端重排

### 加载态

- 延续当前 `LoadingBlock`

### 空/错误态

- 404：`事件已不存在，或已发生聚合变化`
- 其他异常：`加载事件详情失败`

### 返回行为

- 返回按钮始终回到 `news-feed`

## 实现边界

### 前端

主要修改：

- [frontend/src/views/EventDetailView.vue](/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/frontend/src/views/EventDetailView.vue)
- [frontend/src/views/EventDetailView.test.ts](/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/frontend/src/views/EventDetailView.test.ts)

可能复用：

- [frontend/src/components/common/SectionCard.vue](/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/frontend/src/components/common/SectionCard.vue)
- [frontend/src/utils/time.ts](/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/frontend/src/utils/time.ts)
- [frontend/src/utils/format.ts](/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-timeline/frontend/src/utils/format.ts)

如事件页模板开始显得过重，可以拆出一个小的时间线 item 子组件，但本轮优先保持在单视图内完成。

### 后端

本轮不改接口，只消费现有 `NewsEventDetail.news_items`。

## 测试策略

采用 TDD。

新增/调整前端测试覆盖：

1. 渲染 compact header 的核心事件信息
2. 时间线项显示阶段标签、来源、时间、情绪
3. 点击 `查看新闻详情` 会跳转到 `news-detail`
4. `canonical_url` 存在时显示原文动作，不存在时隐藏
5. loading / not-found / generic-error 三态保持有效

## 风险

- 事件详情页信息密度提高后，移动端可能出现横向拥挤；需要在样式上优先保证窄屏自动换行
- “首发/跟进/更新” 是前端轻语义标签，不应被误解为严格事实判定
- 若单事件挂载新闻非常多，时间线会变长；本轮先优先可读性，不引入分页或折叠
