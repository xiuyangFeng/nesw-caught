# 前端「霓虹终端 · 克制版」改造实施计划

- 日期：2026-07-18
- 设计文档：docs/superpowers/specs/2026-07-18-cyber-terminal-restyle-design.md

## 步骤

1. **令牌层升级**：`frontend/src/assets/main.css`（底色压深、电青 accent、新增 `--grid-line`/`--surface-highlight`/`.bg-grid`、统一 `fade-up`/`pulse-dot` keyframes、reduced-motion 全量守卫、删 `.terminal-surface`）；`frontend/tailwind.config.js` 同步新令牌。
2. **字体自托管**：装 `@fontsource/inter`、`@fontsource/jetbrains-mono`；`index.html` 删 Google Fonts；入口引入 fontsource。
3. **壳层/共享组件**：`AppShell.vue` 品牌区/导航/状态条对齐新令牌；ops 5 张玻璃卡改 `.surface`。
4. **硬编码色清零**：33 文件 163 处 hex → 令牌（重灾区优先）；`useKlineChartLifecycle.ts` K 线色读 CSS 变量；`.num` 扫漏。按目录并行子任务，各自跑 vitest。
5. **动效收敛**：scoped 局部动画 → 全局 keyframes；补齐 reduced-motion。
6. **验证记录**：build + test + check:api-drift；更新 `docs/code-change-log.md`；dev server 目检。

## 硬约束

保留 `data-role`/`.pill` 测试钩子；不动业务逻辑；不做浅色主题/响应式/新功能。
