# 文档索引

本目录区分**现行参考**与**历史归档**。后续优化和开发必须从现行文档与代码出发，不要把归档内容当成待办。

## 现行文档（持续维护）

| 文件 | 用途 |
|------|------|
| [current-state.md](./current-state.md) | **现状入口** — 2026-08-18 起的系统快照；开始新工作先读这份 |
| [code-change-log.md](./code-change-log.md) | **强制** — 每次代码/配置/接口变更的记录（只追加近期条目） |
| [stability-and-evolution.md](./stability-and-evolution.md) | 稳定性原则仍然有效；具体实现以代码为准 |
| [superpowers/README.md](./superpowers/README.md) | 进行中的设计/计划目录；完成后必须归档 |

## 第一阶段草稿（可能落后于代码）

这些文件保留作为产品意图参考，**不是当前接口或模块划分的权威来源**：

| 文件 | 说明 |
|------|------|
| [product-requirements.md](./product-requirements.md) | 2026-03 MVP 需求草稿 |
| [technical-architecture.md](./technical-architecture.md) | 2026-03 架构草稿；实际模块名与流水线以代码为准 |
| [api-contract.md](./api-contract.md) | 并行开发期 v0 契约；现行接口以 `frontend/openapi.json` 为准 |

## 新设计 / 计划

仅写入尚未完成的工作：

```text
docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
docs/superpowers/plans/YYYY-MM-DD-<topic>-plan.md
```

完成后立刻移至 `docs/archive/superpowers/`。目录为空表示当前没有进行中的设计任务。

## 归档目录（只读）

| 目录 / 文件 | 内容 |
|------|------|
| [archive/bootstrap/](./archive/bootstrap/) | 启动期总控计划、项目管理、并行开发提示词、旧优化诊断清单 |
| [archive/optimization-2026-06/](./archive/optimization-2026-06/) | 2026-06 十三项后端/前端优化（已全部落地） |
| [archive/superpowers/](./archive/superpowers/) | 已完成或已过期的设计稿与实施计划 |
| [archive/code-change-log-before-2026-08.md](./archive/code-change-log-before-2026-08.md) | 2026-07 及更早的变更流水 |

归档中的“未做 / 部分完成 / 风险或后续事项”**不自动继承**为新任务。
