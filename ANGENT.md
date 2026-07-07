# 智能体协作与代码记录规范 (AGENTS & ANGENT Specification)

本规范为本项目开发协作的仓库级约束，适用于所有智能体（Agent）和人工协作者。旨在把需求澄清、方案设计、计划拆解、实现、调试、验证、评审以及代码修改追踪记录（Change Log）整套流程固定下来。

---

## 一、 协作与开发流程 (Superpowers Workflow)

### 1. 生效前提
- 本仓库默认后续使用 Codex 协作开发。
- 相关 superpowers skills 需要先安装到本机 `~/.codex/skills`。
- 若 skill 未加载成功，先修复安装或重启 Codex，不要假装流程已经生效。
- 当前项目要求至少可用以下 skills：`using-superpowers`, `brainstorming`, `writing-plans`, `executing-plans`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`, `requesting-code-review`, `receiving-code-review`, `using-git-worktrees`, `subagent-driven-development`, `dispatching-parallel-agents`, `finishing-a-development-branch`。

### 2. 总体规则
- **Brainstorming**: 任何新功能、行为变更、重构、接口调整，默认先走 `brainstorming`，形成设计后再进入实现。
- **Writing Plans**: 设计确认后，必须走 `writing-plans`，把实现拆成可验证的任务，不允许“边想边改”。
- **Test-Driven Development**: 进入实现时，必须遵循 TDD；没有先写失败测试的生产代码，视为不合规。
- **Systematic Debugging**: Bug 排查默认走系统调试，先确认复现、收集证据、定位根因，再修复。
- **Verification Before Completion**: 宣布完成前，必须执行验证，确认真实验证已做完，而不是口头判断。
- **Code Review**: 实现阶段结束后，必须走 `requesting-code-review`；收到问题后按 `receiving-code-review` 处理。
- **Subagents**: 涉及多步任务、长链路任务或并行任务时，优先使用子智能体。
- **Git Worktrees**: 涉及隔离开发、风险较高改动、并行分支时，优先使用 git worktree.

### 3. 面向本项目的补充要求
- 开始较大改动前，先阅读最近的 [docs/code-change-log.md](/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md)，避免与最近改动冲突。
- 必须遵守本文中“二、代码记录与提交规范”的要求；每次完成明确修改单元后，必须更新 [docs/code-change-log.md](/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md)。
- 设计文档和计划文档统一放在 `docs/superpowers/` 下：
  - 设计：`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
  - 计划：`docs/superpowers/plans/YYYY-MM-DD-<topic>-plan.md`
- 后端改动的最小验证通常包括 `conda run -n news-caught pytest backend/tests` 中的相关测试。
- 前端改动的最小验证通常包括 `npm --prefix frontend run build`；涉及交互时再补充手动验证说明。

### 4. 例外规则
- 用户明确要求跳过某个流程时，按用户指令执行，但要明确写出跳过的风险。
- 纯文案、小型文档修订或无行为变化的说明更新，可以不强制要求完整设计和 TDD，但仍需更新变更记录。

---

## 二、 代码记录与提交规范 (Code Change Log Rules)

### 1. 强制要求
任何修改都必须在提交修改内容的同时，回填到代码记录文档 [docs/code-change-log.md](/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md) 中。如果修改了代码但没有同步更新该记录文档，则该修改视为不完整。

### 2. 适用范围与改动粒度
所有后端/前端代码、配置文件、脚本、数据库模型、API 契约、文档、测试以及构建和运行方式的改动均须记录。每次完成一个明确修改单元后立即记录，不要等到最后统一补写。

推荐按以下粒度记录：
- 一个功能闭环
- 一次接口调整
- 一次数据模型变化
- 一次页面交互增强
- 一次测试或脚本修复

### 3. 记录格式
每条记录都应尽量简洁，但必须包含以下内容：
1. **日期** (格式 YYYY-MM-DD 或 YYYY-MM-DD HH:MM)
2. **修改人**
3. **修改范围**
4. **变更内容** (用事实描述，明确写出“改了什么”，不写空话)
5. **影响文件**
6. **接口/数据结构变化** (注明是否有变更，若有须写出兼容影响)
7. **验证情况** (如无验证必须写“未验证”，如有须注明测试命令或实测情况)
8. **风险或后续事项**

### 4. 建议模板
参考 [docs/code-change-log.md](/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md) 中的模板和历史示例。
