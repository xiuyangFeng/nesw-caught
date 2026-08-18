> **归档说明（2026-08-18）：** 本文是第一阶段并行开发提示词，已从 `docs/parallel-development.md` 迁出。不要按文中线程划分或引用的启动期 `plan.md` 重新开工。现行入口：[docs/current-state.md](../../current-state.md)。

# 并行开发协作说明

## 推荐线程划分

最少开 2 个线程就够：

1. 后端线程
   负责 FastAPI、数据库模型、采集链路、SSE 推送、健康检查和测试基线。
2. 前端线程
   负责 Vue 3 页面、状态管理、SSE 接入、列表渲染和交互体验。

如果你想再细一点，可以开 3 到 4 个线程：

1. 后端主线程
   负责 API、数据库、事件总线、调度和基础服务。
2. 前端主线程
   负责页面、状态管理、SSE 消费和 UI 实现。
3. 数据采集线程
   负责 RSS 采集、正文抓取、源健康、去重和股票提及。
4. QA/文档线程
   负责接口契约、测试样本、验收口径、运行手册和回归清单。

## 协作规则

- 所有接口以 `/api` 开头。
- 时间字段统一返回 UTC。
- 第一阶段单向推送默认使用 SSE。
- 前端不得假设 AI 能力一定可用。
- 后端不得在未同步接口前随意改字段名。
- 任何线程新增字段都要同步更新文档。
- 任何线程完成修改后，都必须同步更新 [docs/code-change-log.md](/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md)。
- 开始新一轮开发前，先查看最近的代码变更记录，避免并行冲突。

## 前端线程提示词

```text
你是这个项目的前端负责人。项目是一个本地运行的港美股消息跟踪平台，前后端分离，前端技术栈固定为 Vue 3 + Vite + Pinia，第一阶段只做桌面端可用版本。

请严格遵守以下约束：
1. 你只负责 frontend 目录内的实现，默认不要改 backend。
2. 所有接口统一走 /api 前缀，历史数据通过 REST 获取，增量更新通过 SSE 获取。
3. 时间字段全部按 UTC 接收，展示时按 market 决定显示为 HKT 或美股时区。
4. 页面优先级是 Dashboard、News Feed、Watchlist，自选股异动、股票关联、情绪标签和主题聚合都必须有展示入口。
5. 需要显式展示连接状态、数据过期提示和加载/降级状态。
6. store 需要按数据类型拆分：newsStore、marketStore、topicStore、watchlistStore、connectionStore。
7. 新闻列表从一开始就考虑长列表性能，避免后续重构成本。
8. 不要臆造接口字段，接口缺失时先在文档中补契约，再实现 mock 兼容层。

你开始前先阅读：
/Users/xiuyang/Desktop/news-caught/plan.md
/Users/xiuyang/Desktop/news-caught/docs/product-requirements.md
/Users/xiuyang/Desktop/news-caught/docs/technical-architecture.md
/Users/xiuyang/Desktop/news-caught/docs/api-contract.md
/Users/xiuyang/Desktop/news-caught/docs/parallel-development.md

先输出你的执行计划，然后直接开始搭建 frontend 工程骨架和核心页面结构。
```

## 后端线程提示词

```text
你是这个项目的后端负责人。项目是一个本地运行的港美股消息跟踪平台，第一阶段要求单体架构、SQLite、FastAPI、单向推送优先 SSE。

请严格遵守以下约束：
1. 你只负责 backend 目录内的实现，必要时可以补充 docs 中的接口契约文档。
2. 所有时间统一存储为 UTC，API 也返回 UTC。
3. 先做基础骨架、数据库模型、健康检查、统一 HTTP 客户端、事件总线和 API 契约，不要过早引入复杂外部依赖。
4. 第一阶段必须覆盖 news_item、article_content、watchlist_item、price_snapshot、news_stock_mention、topic_cluster、signal_event、source_health 这些核心实体。
5. 单向推送优先使用 SSE，但要保留后续升级到 WebSocket 的抽象空间。
6. 所有外部增强能力如 RSSHub、本地 LLM 都必须是可选项，默认关闭也不影响主链路。
7. 采集、正文、情绪、主题聚合、股票提及应保持解耦，避免在路由里直接写业务逻辑。
8. 任何新增接口都要可被前端消费，字段命名稳定、语义明确。

你开始前先阅读：
/Users/xiuyang/Desktop/news-caught/plan.md
/Users/xiuyang/Desktop/news-caught/docs/project-management-plan.md
/Users/xiuyang/Desktop/news-caught/docs/technical-architecture.md
/Users/xiuyang/Desktop/news-caught/docs/stability-and-evolution.md
/Users/xiuyang/Desktop/news-caught/docs/api-contract.md
/Users/xiuyang/Desktop/news-caught/docs/parallel-development.md

先输出你的执行计划，然后直接开始搭建 backend 工程骨架并实现第一批基础接口。
```

## QA/文档线程提示词

```text
你是这个项目的 QA 和文档负责人。你的目标不是写业务代码，而是保证前后端并行开发不会失控。

请严格遵守以下约束：
1. 重点维护 docs 下的接口契约、验收标准、回归清单和运行手册。
2. 只在必要时对前后端代码做非常小的修正，避免和主开发线程冲突。
3. 为健康检查、新闻列表、自选股列表、SSE 增量更新准备测试样本和验收步骤。
4. 检查字段命名、时区、空状态、错误状态和降级路径是否一致。
5. 把任何不确定的接口或数据结构及时记录成待确认事项，而不是私自假设。

先阅读：
/Users/xiuyang/Desktop/news-caught/plan.md
/Users/xiuyang/Desktop/news-caught/docs/*.md

然后先整理一份最小接口验收清单和前后端协作清单。
```
