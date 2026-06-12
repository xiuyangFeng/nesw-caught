# 文档索引

本目录区分**现行参考文档**与**历史归档**，避免 `docs/` 根目录堆积过多已完结的设计稿。

## 现行文档（持续维护）

| 文件 | 用途 |
|------|------|
| [code-change-log.md](./code-change-log.md) | **强制** — 每次代码/配置/接口变更的记录 |
| [product-requirements.md](./product-requirements.md) | 产品需求与功能范围 |
| [technical-architecture.md](./technical-architecture.md) | 技术架构说明 |
| [api-contract.md](./api-contract.md) | API 契约摘要 |
| [stability-and-evolution.md](./stability-and-evolution.md) | 稳定性与演进策略 |
| [parallel-development.md](./parallel-development.md) | 并行开发约定 |
| [project-management-plan.md](./project-management-plan.md) | 项目管理计划 |

## 新设计 / 计划（Superpowers 流程）

新功能的设计与计划仍写入：

```text
docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
docs/superpowers/plans/YYYY-MM-DD-<topic>-plan.md
```

完成后可将文档移至 `docs/archive/superpowers/` 或对应主题归档目录。

## 归档目录

| 目录 | 内容 |
|------|------|
| [archive/optimization-2026-06/](./archive/optimization-2026-06/) | 2026-06 十三项后端/前端优化与重构计划（已全部落地） |
| [archive/superpowers/](./archive/superpowers/) | 2026-03 起历史 Superpowers 设计稿与实施计划（约 180+ 篇，只读参考） |

## 仓库根目录

- [plan.md](../plan.md) — 项目总规划（仍作为顶层入口）
- 具体变更以 `code-change-log.md` 为准
