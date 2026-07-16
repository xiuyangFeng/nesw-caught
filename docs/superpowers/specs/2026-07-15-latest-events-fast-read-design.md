# Latest Events 快读改版设计

日期：2026-07-15
状态：已与用户确认（布局方案、阅读交互、范围均已选定；用户授权后续免逐节确认）

## 背景与目标

「最新事件」板块（`/news`，NewsFeedView）是主阅读界面，但现状不匹配快速信息阅读：

- 三层结构「事件卡×6 → 主题卡×6 → 新闻流」占满首屏，用户主要刷新闻流，却要滚过两屏才到；
- 点卡片整页跳转详情页（Dashboard 反而有 0ms 阅读抽屉），且详情接口 4 次串行查询拖慢加载；
- 卡片只有情绪标签+标题+原文摘要，读者仍需自行判断 so-what；无已读状态、无视觉分级、无键盘操作。

目标：打开页面第一屏就是可扫读的新闻流，扫视即可分流轻重，点击就地阅读，读过留痕，低价值内容折叠。

用户决策记录：范围=前后端都动；主用层=新闻流；阅读交互=改用抽屉；布局=顶部紧凑条。

## 一、前端设计

### 1.1 布局：顶部紧凑条

- **事件胶囊条 `EventCapsuleStrip.vue`（新增）**：Event Radar 6 张大卡压成一行横向滑动胶囊，每枚含 `事件类型 · 情绪色点 · 市场 · 标题（截断）· 命中持仓标记`；点击进事件详情页（现有路由）。`EventFeedCard.vue` 组件保留（供事件详情等处复用），仅从本页移除。
- **主题 chips 行**：Topic Watch 压成一行 `主题名(新闻数)` chips，点击进主题详情；超出部分收进「▸更多」弹出层。
- 两行合计高度约 90px；Raw Stream 提升至首屏。数据源不变（`loadFeedLayout` 的 events/topics）。

### 1.2 新闻卡片改造（`NewsCard.vue`）

- **左缘色条**：3px 竖条，颜色=情绪方向（negative 红 / positive 绿 / neutral 灰，用现有令牌色），透明度按编辑分强度分档（entry.score 归一化三档）。
- **AI 结论行**：`ai_takeaway` 非空时以 accent 色显示 `→ {takeaway}`，原文摘要降为次行（stream-compact 下仅显示结论行）；为空时回退现状（显示原文摘要），无 AI 依赖感知。
- **已读态**：未读小圆点；已读整卡 opacity 0.55；打开抽屉即标已读。

### 1.3 阅读抽屉 + 键盘流

- 点卡片不再 `router.push`，改为打开 `NewsDetailDrawer`（复用 Dashboard 现有组件：`newsId` + `filteredNewsIds` + `changeNews`/`close`）；`filteredNewsIds` 传当前排序后的可见条目 id 序列，支持上/下篇连读；抽屉内保留「在完整页打开」链接（现有详情页路由不删）。
- 键盘（新增 composable `useFeedKeyboard`）：`j/k` 移动选中高亮（虚拟/普通列表均同步滚动到可视区），`Enter` 打开抽屉，`Esc` 关闭；抽屉打开时 `j/k` 切上下篇。输入框聚焦时快捷键失效。流底部固定一行快捷键提示。
- 事件胶囊/主题 chips 不参与 j/k 焦点序列，仅鼠标/Tab 访问。

### 1.4 低分折叠

- 按编辑分降序排列后，位于第 70 百分位之后的尾部（即排名后 30%，且至少留出前 10 条不折叠）折叠为一行「已折叠 N 条低优先级 · 展开」；展开状态会话内记住（组件内 state，不持久化）。
- 折叠只作用于 stream 尾部，不打断已展开阅读的位置；虚拟列表下折叠段以单一占位行参与虚拟化。

### 1.5 已读存储（`useReadStore` 或 utils）

- localStorage 存已读 id 集合，上限 2000 条 FIFO 滚动清理；单机单用户，不动后端；将来跨浏览器同步再升级为表。

## 二、后端设计

### 2.1 数据模型与契约

- `news_item` 新增列 `ai_takeaway: Text | None`（Alembic 迁移，可空，无索引）。
- `NewsItemSummary`（`backend/app/schemas/news.py:6`）新增 `ai_takeaway: str | None`；feed / detail / feed-layout 各视图沿用该 schema 自动携带。
- 前端 `npm run generate:api` 重新生成 `api.d.ts`；`check:api-drift` 保持通过。

### 2.2 takeaway 生成（两条路径）

一句话结论的内容要求：谁受影响（标的/板块）+ 方向（利好/利空/中性）+ 一句因果，中文，≤60 字。

- **路径 A（顺路）**：`news_signal_classifier._llm_refine` 的 prompt 输出键增加 `takeaway`；解析时空值容忍（缺键→None），写入 `news_item.ai_takeaway`。精修本就调 LLM，零增量成本。
- **路径 B（补齐）**：feed layout 计算完成后，收集候选：stream 中按 editorial_score 降序前 20%（不足 8 条则取前 8 条）以及事件卡 news_items 内、且 `ai_takeaway IS NULL` 的 news_id，异步入队（进程内队列 + 后台 worker，仿照现有 `queue_worker` 模式；入队去重）。worker 批量调 LLM 生成，写回后 publish `news.signals_processed`（复用现有事件：路由缓存失效订阅与前端 SSE 处理链路均已存在，不新增事件类型）。
- **成本护栏**（config 新增项）：跟随 `ai_enabled` 总开关；单轮批量上限（默认 12 条）；单日生成上限（默认 300 条）。生成结果永久落库，一条新闻只生成一次。
- **降级**：`ai_enabled=False`、LLM 未配置或调用失败 → 字段保持 NULL，记 warning 日志（不吞异常为 pass），前端自动回退。

### 2.3 详情接口提速

- `get_news_detail`（`backend/app/api/routes/news.py:185`）现为 4 次串行仓库查询（item / article / mentions / topic）。改为仓库层单次往返组合查询（join / selectinload 或单 SQL 多结果集），路由层组装逻辑不变，响应 schema 不变。此接口直接决定抽屉打开速度。

## 三、错误处理与降级汇总

| 场景 | 行为 |
| --- | --- |
| LLM 关闭/未配置/失败 | takeaway 为 NULL，卡片回退原文摘要 |
| feed layout 降级（现有 `feedLayoutDegraded`） | 胶囊条/主题行整体隐藏，新闻流不受影响 |
| takeaway worker 异常 | 记日志+跳过该批，不影响 feed 主链路 |
| localStorage 不可用 | 已读功能静默失效，其余正常 |

## 四、测试策略

- **后端 pytest**（`conda run -n news-caught pytest backend/tests -q`）：迁移可升降；takeaway 服务（mock LLM）批量/去重/上限/失败降级；`_llm_refine` 新键解析与缺键容忍；detail 接口行为不变（含 article/mentions/topic 为空的组合）。
- **前端 vitest**：NewsCard 结论行渲染与 NULL 回退、色条分档、已读淡化；已读 store 上限清理；折叠分组逻辑；`useFeedKeyboard`（j/k/Enter/Esc、输入框聚焦豁免）；EventCapsuleStrip 渲染与点击路由。
- **契约**：`npm run check:api-drift`；`npm run typecheck`（必须 `-p tsconfig.app.json`）。
- **E2E**：现有全应用导航冒烟保持绿；NewsFeedView 相关断言随布局更新。

## 五、范围外（明确不做）

- Dashboard、详情页、事件/主题详情页的改版；
- 已读状态后端化/多端同步；
- takeaway 回填历史全量新闻（只覆盖进入 lead/supporting/事件卡的条目）；
- 路由整体异步化（optimization-plan #8 其余部分）、分析队列持久化（#6）——另行处理。
