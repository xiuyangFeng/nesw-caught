# Optimization Checklist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修通独立 scheduler→Redis→Web SSE，修正抓取健康判定，并尽量完成 effective_at / 页面只读 / 虚拟列表 / 相关性四项 P1。

**Architecture:** HybridEventBus 保留本地订阅；跨进程经 Redis Streams；Web 侧 RedisStreamConsumer 只注入 local_bus。健康状态拆分为多状态枚举驱动退避。列表排序统一 effective_at。

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, Redis Streams, Vue3/Pinia, vitest/pytest

## Global Constraints

- 模型仅用 cursor-grok-4.5-high-fast
- TDD；未要求不 git commit
- 每完成明确修改单元更新 docs/code-change-log.md
- 最小改动，匹配现有风格

---

## File map

| 区域 | 主要文件 |
|------|----------|
| P0-1 Redis | `redis_stream_bus.py`, `event_bus.py`, `main.py`, `config.py`, tests |
| P0-1 FE 对账 | `connectionStore.ts`, `AppShell.vue`, tests |
| P0-2 健康 | `persister.py`, `news_ingest_scheduler.py`, `source_health.py`, alembic, schemas/ops |
| P1-1 时间 | `news_item.py`, persister, utils/parser, repository, schemas, FE time UI |
| P1-2 生命周期 | `AppShell.vue`, newsStore, SSE debounce |
| P1-3 虚拟列表 | `NewsVirtualList.vue`, tests |
| P1-4 相关性 | signal/priority/topic 相关服务 |

---

### Task 1: P0-1 Redis consumer + stream map

- [x] 写失败测试：publisher 信封含 event_name；consumer 注入 local_bus 且不回写 Redis；`news.created`/`news.updated` 进 stream_map
- [x] 实现 `RedisStreamPublisher` 信封增强 + `RedisStreamConsumer`
- [x] `build_event_bus` / lifespan 启动 consumer（hybrid/redis）
- [x] 跑相关 pytest 转绿
- [x] 更新 code-change-log

### Task 2: P0-1 前端断线快照对账

- [x] 写失败测试：reconnect onOpen 触发 snapshot reconcile（不调用 refreshNews）
- [x] 实现 connectionStore / AppShell 接线
- [x] vitest 转绿；更新 code-change-log

### Task 3: P0-2 健康判定

- [x] 写失败测试：304→not_modified 不增 failure streak；200+0 条→empty；scheduler 仅对 http/parse_error 退避
- [x] 模型/迁移字段；persister + scheduler + 熔断低频探测
- [x] pytest 转绿；更新 code-change-log

### Task 4: P1-1 effective_at

- [x] 写失败测试：排序用 effective_at；dc:date；上海时区
- [x] 迁移 + 入库维护 + repository/schema/UI
- [x] 验证；更新 code-change-log

### Task 5: P1-2 页面生命周期

- [x] 写失败测试：bootstrap 不调用 refreshDashboardNews；SSE debounce；手动刷新 cooldown
- [x] 实现；vitest；更新 code-change-log

### Task 6: P1-3 虚拟列表

- [x] 写失败测试：100 条 DOM 行数有限且 viewport 高度有效
- [x] 修滚动根；转绿；更新 code-change-log

### Task 7: P1-4 相关性与主题

- [x] 写失败测试：门槛过滤；官方源优先；无 LLM 结构化摘要；主题中文名
- [x] 实现；pytest；更新 code-change-log

### Task 8: 总验证

- [x] `conda run -n news-caught pytest backend/tests`（相关或全量）
- [x] `npm --prefix frontend run build`（若改前端）
- [x] 汇总完成项 / 未完成 / 风险
