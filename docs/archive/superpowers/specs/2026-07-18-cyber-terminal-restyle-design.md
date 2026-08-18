# 前端「霓虹终端 · 克制版」视觉改造设计

- 日期：2026-07-18
- 状态：已评审（用户提问式需求澄清后确认）
- 前置文档：docs/superpowers/specs/2026-07-13-frontend-redesign-design.md（本设计为其延续与收口）

## 1. 背景

上次改版（2026-07-13）确立了"智能量化台"令牌层与壳层，但视图/组件层执行不齐：33 个 vue 文件残留 163 处硬编码 hex、ops 五卡仍是玻璃拟态、字体依赖 Google CDN、全站无背景纹理、K 线色硬编码、`prefers-reduced-motion` 仅 3 处覆盖。界面因此显得"不像这个产品"。

## 2. 用户画像（2026-07-18 提问确认）

- 风格方向：赛博/AI 科技感（克制点缀档，非全赛博朋克）
- 主题：保持深色
- 密度：适中
- 涨跌色：红涨绿跌（A股/港股惯例）
- 数字：等宽科技体（font-mono + tabular-nums）
- 动效：克制（hover 过渡、新消息入场、live 点脉冲三类）
- 主色：由实现方定 → 保持青色家族，微调为更"电"的青

## 3. 设计方向「霓虹终端 · 克制版」

在现有令牌体系上升级氛围，而非重建：

1. **底色加深**：`--bg` 系列压到 `#05070d` 量级深蓝黑；`--text` 亮度不变，保证对比度。
2. **背景纹理**：新增全站超低透明度网格（repeating-linear-gradient，约 3% 不透明度），叠加既有角落径向光晕，营造"监控大屏"感。
3. **面板质感**：`.surface` 保持实心 + 发丝边框，顶部加 1px 极浅渐变高光（`--surface-highlight`），增加层次但不玻璃。
4. **主色**：电青（`#3ee6ff` 量级）；live 状态点统一柔和脉冲辉光（`pulse-dot`）。
5. **涨跌色不变**：`--positive: #ff5a72`（红涨）/ `--negative: #1fd39a`（绿跌）。
6. **数字**：价格/涨跌幅/时间戳/计数统一 `.num`（等宽 + tabular-nums），全站扫漏。
7. **AI 触点**：紫→青渐变 + 克制辉光，仅 AI 徽标/研判卡/品牌字（维持现状）。
8. **动效**：全局统一 `fade-up`、`pulse-dot` 两组 keyframes；`prefers-reduced-motion` 全量覆盖。

## 4. 令牌变更清单

新增：
- `--grid-line`：网格纹理线色（极低透明度青白）
- `--surface-highlight`：面板顶部高光渐变

调整：
- `--bg` / `--bg-elevated` / `--panel` 系列：整体压深
- `--accent`：微调为更电的青（连带 `--neutral`、interactive/focus 系列）

删除：
- `.terminal-surface` 兼容别名（引用先替换为 `.surface`）

新增工具类 / 动效：
- `.bg-grid`：背景网格纹理
- `@keyframes fade-up`、`@keyframes pulse-dot` + `prefers-reduced-motion` 守卫

## 5. 字体自托管

- 移除 `index.html` 的 Google Fonts CDN。
- 采用 `@fontsource/inter` + `@fontsource/jetbrains-mono`（npm 依赖，构建期内联）。
- 中文不自托管 CJK 大字库，回落系统字体（PingFang SC / HarmonyOS / 微软雅黑）。
- 回退方案：若 fontsource 安装不可用，直接去掉 CDN 引用、使用 system-ui 字体栈。

## 6. 执行债清理范围

- ops 目录 5 张玻璃卡去 `backdrop-filter`，改 `.surface` 实心。
- 33 个 vue 文件 163 处硬编码 hex → 语义令牌；重灾区优先（XMonitorView、NewsDetailView、CalendarView、OpsSourcesCard）。
- `useKlineChartLifecycle.ts` K 线涨跌色改读 CSS 变量。
- 散落 scoped 的 `fade-in`/`list-fade-in` 动画替换为全局 keyframes。
- `animate-pulse` 裸用统一为 `pulse-dot`。

## 7. 硬约束

- 保留 `data-role`、`.pill` 等测试钩子；不改组件 props、store、api、路由。
- 不做浅色主题、不做响应式（`body min-width: 1120px` 桌面专用保留）、不加新功能。
- 不做扫描线/故障字效/HUD 直角边框等强赛博元素。

## 8. 验证

- `npm --prefix frontend run build`（含 vue-tsc）
- `npm --prefix frontend test`（重点 AppShell / NewsFeed / Dashboard / ops 组件）
- `npm --prefix frontend run check:api-drift`（应无漂移）
- dev server 目检首页/新闻流/自选股/健康页对比度与氛围
