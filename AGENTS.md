# AGENTS.md

## 目的

本文件为本项目接入 `obra/superpowers` 后的仓库级约束。目标是把需求澄清、方案设计、计划拆解、实现、调试、验证、评审这一整套流程固定下来，避免直接跳进代码修改。

## 生效前提

- 本仓库默认后续使用 Codex 协作开发。
- 相关 superpowers skills 需要先安装到本机 `~/.codex/skills`。
- 若 skill 未加载成功，先修复安装或重启 Codex，不要假装流程已经生效。

当前项目要求至少可用以下 skills：

- `using-superpowers`
- `brainstorming`
- `writing-plans`
- `executing-plans`
- `test-driven-development`
- `systematic-debugging`
- `verification-before-completion`
- `requesting-code-review`
- `receiving-code-review`
- `using-git-worktrees`
- `subagent-driven-development`
- `dispatching-parallel-agents`
- `finishing-a-development-branch`

## 总体规则

- 任何新功能、行为变更、重构、接口调整，默认先走 `brainstorming`，形成设计后再进入实现。
- 设计确认后，必须走 `writing-plans`，把实现拆成可验证的任务，不允许“边想边改”。
- 进入实现时，必须遵循 `test-driven-development`；没有先写失败测试的生产代码，视为不合规。
- Bug 排查默认走 `systematic-debugging`，先确认复现、收集证据、定位根因，再修复。
- 宣布完成前，必须执行 `verification-before-completion`，确认真实验证已做完，而不是口头判断“应该可以”。
- 实现阶段结束后，必须走 `requesting-code-review`；收到问题后按 `receiving-code-review` 处理。
- 涉及多步任务、长链路任务或并行任务时，优先使用 `subagent-driven-development`、`dispatching-parallel-agents` 或 `executing-plans`。
- 涉及隔离开发、风险较高改动、并行分支时，优先使用 `using-git-worktrees`。
- 收尾时按 `finishing-a-development-branch` 检查测试、分支状态、交付方式。

## 面向本项目的补充要求

- 先阅读最近的 [docs/code-change-log.md](/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md)，避免与最近改动冲突。
- 必须遵守 [ANGENT.md](/Users/xiuyang/Desktop/news-caught/ANGENT.md) 中的记录、提交、推送要求；若本文件与 `ANGENT.md` 有冲突，以用户直接指令优先，其次以 `ANGENT.md` 的项目记录要求优先。
- 设计文档和计划文档建议统一放在 `docs/superpowers/` 下：
  - 设计：`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
  - 计划：`docs/superpowers/plans/YYYY-MM-DD-<topic>-plan.md`
- 后端改动的最小验证通常包括 `conda run -n news-caught pytest backend/tests` 中的相关测试。
- 前端改动的最小验证通常包括 `npm --prefix frontend run build`；涉及交互时再补充手动验证说明。
- 每次完成明确修改单元后，必须更新 [docs/code-change-log.md](/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md)。

## 例外规则

- 用户明确要求跳过某个流程时，按用户指令执行，但要明确写出跳过的风险。
- 纯文案、小型文档修订或无行为变化的说明更新，可以不强制要求完整设计和 TDD，但仍需更新变更记录。
