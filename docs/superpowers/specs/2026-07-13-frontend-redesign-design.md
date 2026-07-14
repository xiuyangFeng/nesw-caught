# 前端视觉改版设计规范：智能量化台（偏 B）

- **日期**：2026-07-13
- **状态**：待用户评审
- **预览**：本地 `http://localhost:4180`（`scratchpad/preview/index.html`）
- **方向**：数据量化台（B） × AI 智能感（C）融合，比例约 **78% B + 22% C（"偏 B"）**

---

## 1. 目标与非目标

### 目标
1. 把前端从「彭博终端 cosplay」（复古 CRT、全大写英文黑话）升级为**现代、精密、冷静的"智能量化台"**。
2. 保留强烈**科技感**，但以密度与精度承载，而非特效堆砌。
3. 顺手修掉现有设计系统的一致性硬伤（语义色撞车、硬编码色值、中英混用、导航噪音）。
4. 借助现有 **CSS 变量驱动**架构，用**令牌层**实现全站一次性视觉传导，降低改动面。

### 非目标
- 不改后端、不改数据结构、不改业务逻辑与路由。
- 不改交互流程/信息架构的功能层（导航**分组与文案**会调整，但页面能力不变）。
- 本轮不做移动端适配（保留桌面优先，见 §10 开放项）。

---

## 2. 设计方向一句话

> **实心深色卡片 + 发丝细边框 + 等宽数字 + 单一青色主色**承载"量化密度与冷静"；
> **紫→青渐变、玻璃与辉光只点亮 AI 触点**（AI 研判卡、品牌徽标），作为唯一的"智能"高光。

配色沿用 **A股/港股红涨绿跌**惯例。辉光克制：只在图表端点、AI 卡、聚焦态出现，不做满屏光污染。

---

## 3. 设计令牌（映射到现有 `src/assets/main.css` 变量名）

> 关键杠杆：**只改 `main.css` 的 `:root` 令牌 + `tailwind.config.js` 扩展，全站 20 屏自动继承。**
> 下表左列是现有变量名，直接替换其值即可。

### 3.1 底色与面板（玻璃 → 实心，是"偏 B"的核心改动）
| 变量 | 新值 | 说明 |
|---|---|---|
| `--bg` | `#070a12` | 冷深海军蓝底（原 `#050a12` 去暖转冷） |
| `--bg-elevated` | `#0b0f1a` | 抬升背景 |
| `--panel` | `#0d111b` | **实心卡片**（原为 `rgba(...glass)`，去毛玻璃） |
| `--panel-strong` | `#10151f` | 强调面板 |
| `--panel-stronger` | `#0c1017` | 更深内嵌面 |
| `--panel-soft` | `#0e131d` | 柔和面板 |
| `--field-bg` | `#0a0e18` | 输入控件底 |
| `--bg-accent` | `radial-gradient(680px 260px at 94% -10%, rgba(58,210,230,.08), transparent 60%), linear-gradient(180deg,#080c15,#05080f)` | 极克制的单青光晕 |

### 3.2 边框、文字
| 变量 | 新值 |
|---|---|
| `--border` | `rgba(150,160,200,.12)`（发丝级） |
| `--border-strong` | `rgba(150,160,200,.22)` |
| `--text` | `#eaf0fb` |
| `--text-soft` | `rgba(234,240,251,.74)` |
| `--text-faint` | `#8794a8` |
| `--muted` | `#8794a8` |

### 3.3 语义色（🔧 修掉旧撞车：原 neutral/warning/accent 全 = 同一青色）
| 变量 | 新值 | 语义 |
|---|---|---|
| `--positive` / `--positive-soft` | `#ff5a72` / `rgba(255,90,114,.14)` | **涨 / 利好（红）** |
| `--negative` / `--negative-soft` | `#1fd39a` / `rgba(31,211,154,.14)` | **跌 / 利空（绿）** |
| `--success` / `--success-soft` | `#1fd39a` / `rgba(31,211,154,.14)` | 系统健康 |
| `--danger` / `--danger-soft` | `#ff5a72` / `rgba(255,90,114,.14)` | 系统故障 |
| `--accent` / `--accent-soft` | `#3ad2e6` / `rgba(58,210,230,.12)` | **主色（单青）** |
| `--neutral` | `#3ad2e6` | 与 accent 对齐（中性强调） |
| `--warning` / `--warning-soft` | **`#ffcf5a`** / `rgba(255,207,90,.14)` | **告警（琥珀，与主色解耦）← 修复点** |
| `--system` / `--system-soft` | `#5fb8ff` / `rgba(95,184,255,.14)` | 链接 / 信息 / 聚焦 |
| `--focus-ring` | `rgba(58,210,230,.22)` | 聚焦环 |
| `--interactive-hover` | `rgba(58,210,230,.07)` | hover |
| `--interactive-selected` | `rgba(58,210,230,.12)` | 选中 |

### 3.4 新增令牌（在 `main.css` 与 `tailwind.config.js` 同步加）
| 变量 | 值 | 用途 |
|---|---|---|
| `--ai` | `#8b7cff` | AI 触点紫 |
| `--ai-2` | `#3ad2e6` | AI 渐变终点（与主色同青） |
| `--grad-ai` | `linear-gradient(100deg,#8b7cff,#3ad2e6)` | **仅用于 AI 徽标 / AI 研判卡边框 / 品牌字** |
| `--glow-accent` | `0 0 10px rgba(58,210,230,.28)` | 克制辉光（图表端点、live 点） |
| `--glow-ai` | `0 6px 22px rgba(94,124,220,.18)` | AI 卡外发光 |
| `--r-sm/md/lg/xl` | `8 / 12 / 16 / 20 px` | 圆角刻度 |
| `--shadow` | `0 20px 48px rgba(2,6,12,.42)` | 保留深色投影，略收 |

### 3.5 `tailwind.config.js` 调整
- `colors` 新增 `ai`、保持其余映射；`warning` 现在指向新的琥珀变量（无需改名，值变即可）。
- `borderRadius` 增加 `sm/md/lg/xl` 映射到 `--r-*`。
- `boxShadow` 增加 `glow`、`glow-ai`；移除/收敛旧的 `signal`（琥珀辉光不再作全局强调）。
- `backgroundImage.terminal` 与 `.terminal-surface` 类可下线（不再用终端质感面）。

---

## 4. 字体

> **待评审默认（用户离席期间所选，可推翻）**：数字 JetBrains Mono + 中文 HarmonyOS Sans SC。

| 角色 | 字体栈 |
|---|---|
| 正文 / 标题 | `'HarmonyOS Sans SC', 'Inter', 'PingFang SC', 'Hiragino Sans GB', system-ui, sans-serif` |
| 数字 / 代码 / 小标签 | `'JetBrains Mono', 'IBM Plex Mono', 'SFMono-Regular', monospace` |

规则：
- **所有数字**用等宽字体 + `font-variant-numeric: tabular-nums`（指标、涨跌幅、时间、代码列对齐）。
- 抛弃"全大写 + 宽字距用在所有文字"的旧做法；**大写仅保留在等宽小标签**（区块 eyebrow）。
- 层次靠**字重 + 间距 + 单一青色点睛**，而非到处渐变文字。
- 字体自托管（放 `frontend/src/assets/fonts/`，`@font-face` 引入），避免运行期外链 CDN。若评审改选"保留 IBM Plex"或"系统栈"，只需改这两条字体栈变量。

---

## 5. 间距、圆角、层级
- **圆角**：卡片 `--r-md (12px)`、大容器 `--r-lg (16px)`、pill `999px`、小控件 `--r-sm (8px)`。
- **密度**：卡片内边距 `12–15px`，列表行 `10–13px`；比现状更紧凑（体现 B 的密度）。
- **层级**：靠边框 + 极淡背景抬升，不靠大阴影；辉光仅用于 AI 卡与图表端点。

---

## 6. 通用组件规范

| 组件 / 类 | 规范 |
|---|---|
| `.surface` / SectionCard | 实心 `--panel` + `1px --border`，去 `backdrop-filter` |
| `.terminal-surface` | **下线**（并入 `.surface`） |
| `.pill`（positive/negative/success/danger/neutral/warning） | 等宽小字、`--r-sm`、对应语义软色底 + 实色字；warning 现为琥珀 |
| 指标块 Metric | 等宽大数字 + 小标签 + 角落 mini sparkline（单青、克制） |
| 表格 WatchlistTable 等 | tabular-nums 对齐、发丝行分隔、hover 用 `--interactive-hover` |
| 按钮 | 主按钮青色实心/描边；`.link-button` 用 `--system` |
| StatusBanner / StaleBadge / Toast | 用新语义色；告警走琥珀而非青 |
| Sparkline / 图表 | 单青描边 + 可选渐变面积填充 + **端点强调点（带 `--glow-accent`）** |
| **AI 触点**（AI 研判卡、AI pill、`✦` 标记、品牌字） | 唯一允许 `--grad-ai` / `--glow-ai` 的地方 |

---

## 7. 导航 / AppShell 重构

现状问题：13 项纯平铺、每项挂重复的 "MODULE"、中英混用、高亮用琥珀 `#ff9f2f`、大量硬编码色值。

改造：
1. **分组导航**（4 组，去掉 01–13 编号与 "MODULE" 副标）：
   - **情报**：最新事件 `/news`、仪表盘 `/dashboard`、每日复盘 `/digest`、日历 `/calendar`
   - **交易**：自选股 `/watchlist`、组合 `/portfolio`、信号回测 `/analytics/backtest`
   - **智能**：AI 对话 `/chat`、X 监控 `/x-monitor`
   - **系统**：模型设置 `/settings/llm`、通知 `/settings/notify`、情绪评测 `/eval/sentiment`、系统健康 `/ops`
2. **文案语言**（待评审默认）：**中文主标签 + 等宽英文/代码小标签**（如「自选股 · WATCHLIST」），兼顾可读与科技感。连接状态文案统一（不再中英混杂）。
3. **激活态**：青色竖条 + 青色文字（替换琥珀），hover 轻微位移保留。
4. **系统状态栏 / 顶部 rail**：改用新语义色；告警走琥珀；清理硬编码 hex（`#8ea0b5` / `#ffd5b0` 等）改走令牌。

---

## 8. 图表与数据可视化
- **Sparkline / 趋势图**：单青主色，涨跌用 `--positive/--negative`，端点强调 + 克制辉光，可选渐变面积。
- **K 线（`lightweight-charts`）**：配置 theme 对齐——背景透明/`--panel`、网格 `--border`、上涨 `--positive`(红)、下跌 `--negative`(绿)、十字线青色。集中在 `KlineChart.vue` 的图表选项里改。
- **情绪计 / 仪表**：渐变条（绿→琥珀→红）+ 白色指针。

---

## 9. 落地计划（分阶段 — 待评审默认）

### 阶段 1：地基 + 核心屏
1. **令牌层**：重写 `src/assets/main.css` `:root` 令牌 + `tailwind.config.js`（新增 ai/圆角/glow，warning 改琥珀）。全局传导。
2. **通用组件精修**：`common/*`（SectionCard、StatusBanner、LoadingBlock、SkeletonFeed、StaleBadge、ToastContainer、Sparkline）+ `.pill`/`.surface` 等 `main.css` 组件类。
3. **AppShell / 导航重构**：分组、文案、激活态、去 MODULE、状态栏令牌化。
4. **核心屏**（4 个）：
   - `DashboardView`（+ HeroMetrics、SentimentGauge、TopicBoard、BreakingNewsSpotlight、SourceHealthGrid、SentimentTrendChart）
   - `NewsFeedView`（+ NewsCard、EventFeedCard、StoryStrip、NewsVirtualList）
   - `WatchlistView` / `WatchlistDetailView`（+ KlineChart 主题、StockCard、WatchlistTable、StockMetricsGrid、StockDetailPanel）
   - `ChatView`（+ ChatMessageList、ChatInputBar、ChatSessionSidebar）

### 阶段 2：长尾屏
XMonitor、Calendar、Digest、TopicDetail、EventDetail、NewsDetail、SentimentNews、SignalBacktest、OpsHealth、LlmSettings、NotifySettings、SentimentEval、Portfolio。

### 阶段 3：打磨
动效（尊重 `prefers-reduced-motion`）、图表统一、K 线配色对齐、可访问性（聚焦态/对比度）、响应式决策落地。

> 每阶段结束用本地 `localhost:4180`（或 `npm run dev`）做视觉验收后再进下一阶段。

---

## 10. 约束与开放项

### 硬约束（改版必须遵守）
- **保留测试契约**：现有组件测试断言了 `data-role`（如 `system-header`、`nav-active-signal`、`market-worker-pill`）、`data-route-active`、`.pill` 类名等。重构 UI 时**保留这些语义钩子**，视觉与测试同批更新，避免打挂 44 组件的既有测试。
- **不动业务/数据/路由逻辑**，只动样式与 AppShell 的展示结构。
- 字体自托管，不运行期外链。

### 开放项（评审时确认）
1. **字体**（默认：JetBrains Mono + HarmonyOS Sans SC）
2. **文案语言**（默认：中文主 + 英文小标签）
3. **落地范围**（默认：分阶段，先地基 + 核心屏）
4. **响应式**：现为 `min-width:1120px` 桌面专用。默认**本轮保留桌面优先**，响应式列入阶段 3 之后单独评估。

---

## 11. 验证方式
- `cd frontend && npm run typecheck`（必须带 `-p tsconfig.app.json`，已在 script 内）
- `cd frontend && npm run test`（vitest；含 `app-navigation` 冒烟与组件测试）
- 视觉验收：本地端口页面 / `npm run dev`，逐屏对照。
- 每阶段：类型检查 + 测试全绿 + 视觉验收三者齐备才算完成。

---

## 12. 每屏落地拆分（供后续写实施计划）
本规范聚焦"设计系统"。真正的代码落地建议按 §9 阶段拆成**多个实施计划**（令牌+通用组件 1 个、AppShell 1 个、每个核心屏各 1 个），逐个走 计划 → 实现 → 验证 循环。
