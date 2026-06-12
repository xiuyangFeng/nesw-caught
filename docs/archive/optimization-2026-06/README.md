# 2026-06 优化计划归档说明

本目录存放 2026-06 架构/重构优化相关规划文档，**13 项优化已于 2026-06-12 全部落地**。

## 归档文件

| 文件 | 说明 |
|------|------|
| [optimization_plan_2026-06.md](./optimization_plan_2026-06.md) | 基于代码勘察的 13 项优化计划（P0–P2），含验收标准与 Phase 划分 |
| [claude_optimization.md](./claude_optimization.md) | Claude 生成的架构与规划建议（数据模型、采集韧性、前端工程等） |
| [refactor-plan-2026-06.md](./refactor-plan-2026-06.md) | 2026-06 抓取/去重/仪表盘重构方案（多数项已由 optimization 计划覆盖并落地） |
| [gemini_optimization.md](./gemini_optimization.md) | Gemini 生成的架构建议（RSSHub、FTS5、SSE 等方向性参考） |

## 实施完成情况

| # | 优化项 | 状态 |
|---|--------|------|
| 1 | Alembic 替换手写迁移 | ✅ |
| 2 | SQLite WAL 并发写加固 | ✅ |
| 3 | 事件总线 handler 异常隔离 | ✅ |
| 4 | 重负载 handler 移出同步链路 | ✅ |
| 5 | LLM api_key 加密 + 响应脱敏 | ✅ |
| 6 | news_ingestion.py 模块拆分 | ✅ |
| 7 | 新闻列表 keyset 分页 | ✅ |
| 8 | 数据生命周期 + 清理任务 | ✅ |
| 9 | Worker 统一生命周期管理 | ✅ |
| 10 | CI 流水线 | ✅ |
| 11 | OpenAPI 类型自动生成脚本 | ✅（脚本已就绪，CI drift check 待接入） |
| 12 | KlineChart 巨型组件拆分 | ✅ |
| 13 | Embedding 灰区二次判重 | ✅（默认关闭，配置启用） |

## 验证记录

- 后端 `pytest backend/tests`：**300 passed**
- 前端 `vitest --run`：**192 passed**
- 前端 `npm run build`：成功

## 后续参考

实现细节与变更历史见 [docs/code-change-log.md](../../code-change-log.md)（2026-06-12 条目）。

**请勿再在本目录文档上继续编辑**；新需求应新建独立设计/计划文档。
