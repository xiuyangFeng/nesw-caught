# 智能体协作与代码记录规范 (AGENTS & ANGENT Specification)

本规范为本项目开发协作的仓库级约束，适用于所有智能体（Agent）和人工协作者。旨在把需求澄清、方案设计、计划拆解、实现、调试、验证、评审以及代码修改追踪记录（Change Log）整套流程固定下来。

---

## 一、 协作与开发流程 (Codex Development Workflow)

### 1. 生效前提
- 本仓库默认后续使用 Codex 协作开发。
- 本仓库不要求安装、加载或调用 `superpowers` 套件及其 skills；不得因为相关 skill 不存在而中断正常开发。
- 下述流程是仓库级工程约束，由协作者直接执行，不依赖特定外部 skill、插件或工具包。

### 2. 总体规则
- **需求与设计**：任何新功能、行为变更、重构或接口调整，默认先澄清目标、边界、方案与风险，形成设计后再实现。
- **实现计划**：设计确认后，把实现拆成可验证的任务，明确测试与验收方式，不允许在缺少基本方案的情况下盲目修改。
- **测试驱动开发**：进入实现时遵循 TDD；原则上先写能暴露问题或描述新行为的失败测试，再修改生产代码并完成重构。
- **系统化调试**：Bug 排查先确认复现、收集证据、缩小范围并定位根因，再实施修复，避免仅针对表象打补丁。
- **完成前验证**：宣布完成前必须执行与改动范围相匹配的测试、构建或实测，并如实记录结果。
- **代码评审**：较大或高风险改动完成后应进行代码评审；评审意见需逐项验证后处理，不得未经判断机械接受或忽略。
- **子智能体**：涉及多步、长链路或可并行任务时，可优先使用子智能体，但不作为开发的强制依赖。
- **Git Worktrees**：涉及隔离开发、风险较高改动或并行分支时，可优先使用 git worktree，但不作为普通修改的强制前提。

### 3. 面向本项目的补充要求
- 开始工作前先读 [docs/current-state.md](/Users/xiuyang/Desktop/news-caught/docs/current-state.md) 和根目录 [README.md](/Users/xiuyang/Desktop/news-caught/README.md)，以**当前代码能力**为准，不要从早期总控计划或旧优化清单推导待办。
- 开始较大改动前，只阅读 [docs/code-change-log.md](/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md) **顶部近期条目**，确认是否与正在改的模块冲突。不要通读历史归档，也不要把变更记录里的“风险或后续事项”自动当成新任务。
- 必须遵守本文中“二、代码记录与提交规范”的要求；每次完成明确修改单元后，必须更新 [docs/code-change-log.md](/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md)。
- 设计文档和计划文档继续统一放在 `docs/superpowers/` 下；该目录名仅为历史兼容，不表示依赖 Superpowers 套件：
  - 设计：`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
  - 计划：`docs/superpowers/plans/YYYY-MM-DD-<topic>-plan.md`
  - **完成后必须归档**到 `docs/archive/superpowers/`，不要把已落地方案留在现行目录。
- `docs/archive/` 是只读历史。禁止把归档中的设计、计划、优化清单或启动期 todos 当作当前需求来实现，除非用户明确要求恢复某一项。
- 接口以实际路由和 `frontend/openapi.json` 为准；`docs/api-contract.md`、`docs/product-requirements.md`、`docs/technical-architecture.md` 是第一阶段草稿，可能落后于代码。
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
参考 [docs/code-change-log.md](/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md) 中的模板和历史示例。2026-07 及更早的条目在 [docs/archive/code-change-log-before-2026-08.md](/Users/xiuyang/Desktop/news-caught/docs/archive/code-change-log-before-2026-08.md)，只读。
