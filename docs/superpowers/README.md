# 进行中的设计 / 计划

本目录只存放**尚未完成**的设计与实施计划。目录名 `superpowers` 仅为历史兼容，不表示依赖任何外部套件。

```text
docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
docs/superpowers/plans/YYYY-MM-DD-<topic>-plan.md
```

## 规则

- 新功能或行为变更：先在这里写设计，再写可验证计划，然后实现。
- 对应功能已经合入主分支后，必须把设计/计划移到 `docs/archive/superpowers/`，不要继续留在本目录。
- 本目录为空表示当前没有进行中的设计任务，这是正常状态。
- 不要把 `docs/archive/` 里的旧方案当待办，也不要按旧计划“补做”已经落地或已放弃的项。

当前系统能力以 [docs/current-state.md](../current-state.md)、[README.md](../../README.md) 和代码为准。
