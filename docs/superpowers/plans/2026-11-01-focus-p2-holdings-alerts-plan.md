# 聚焦改造 P2：持仓与站内提醒 实施计划（2026-11-01）

> 设计：[2026-10-31-focus-redesign-design.md](../specs/2026-10-31-focus-redesign-design.md) §5.3、§5.4、§7
> 状态：**用户已确认 §2 全部决定（2026-11-01），执行中**。
> 分支：`feature/focus-p2`，每个任务一个提交，同步更新 `docs/code-change-log.md`。

## 1. 现状（代码实测）

| 项 | 现状 |
|---|---|
| 持仓字段 | `watchlist_item.position_size`、`average_cost` 已存在；自选股页"行情"标签下已有"持仓设置"编辑区 |
| 组合 | 自选股页已有"组合"标签（与 `/portfolio` 页面重复，均调 `GET /api/portfolio`） |
| 单股阈值 | `watchlist_item.alert_threshold` + 添加弹窗"高级"里的阈值输入；用户已确认**不按股票分别设** |
| 提醒 | `NotificationService` 全部绑定飞书：无飞书配置即全部丢弃。用户的飞书配置表为空，**当前实际上没有任何提醒发出** |
| 提醒去重 | 价格提醒用内存状态"越线才触发一次"，进程重启即丢失，且不是"每天一次" |
| 实时推送 | `/api/stream`（SSE）已订阅 `news.created` / `news.updated` / `market.watchlist_refreshed`，可加事件类型 |
| 新闻挂载点 | `queue_worker` 在新闻评分并提交后调用 `notification_service.on_news_created_batch(...)`；此时 A 股 `news_stock_mention` 已写入 |
| 静默时段 | `notify_quiet_hours_*` 配置存在，默认未设置 |
| 港股/美股新闻关联 | `a_share_mentions` 只索引 A 股；阿里（9988.HK）、智谱（HK2513）匹配不到 |

## 2. 设计决定

已由用户确认：

- 持仓直接在自选股里管理；**有持仓的股票用不同颜色高亮**。
- 价格提醒：全天涨跌幅（相对昨收）**超过 ±5%**，统一阈值，不分股票；同一只股**每天最多一次**。
- 只做站内提醒，不接飞书/手机推送；夜间不打扰，夜间事件早上再看。

本计划的取舍（执行前请确认）：

1. **提醒范围分期**：P2 只做"持仓价格 ±5%"和"持仓/关注股的新闻"两类。"海外重大事件""板块异动""AI 发现新机会"依赖 AI 判断，放到 P3。
2. **"重大新闻"的 P2 规则**（P3 换成 AI 判断）：新闻**标题**里出现股票简称或代码即算命中，A 股、港股、美股都适用；A 股额外复用 `news_stock_mention` 中置信度 ≥ 0.9（标题命中）的记录。
   - 持仓股命中 → **立即**提醒；
   - 仅关注（无持仓）的股票命中 → **每 30 分钟合并**成一条提醒；
   - 仅关注的股票**不做**价格提醒。
3. **夜间**：默认 22:00～08:00（北京时间）为静默时段。静默期间产生的提醒照常记录，但标记为"隔夜"，不弹出；08:00 后在提醒中心以"隔夜汇总"分组出现。
4. **删除飞书**：删除飞书客户端、飞书配置表、`notification_job` 表、投递 worker 与 `/settings/notify` 页面；用新的站内提醒取代。每日复盘生成后不再推送（复盘照常生成）。
5. **合并组合页**：删除独立的 `/portfolio` 页面与导航项（自选股页的"组合"标签保留）。删除单股阈值输入，`alert_threshold` 字段随迁移删除。

## 3. 数据与接口

新表 `alert`：

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `kind` | `holding_price_move` / `holding_news` / `watch_news_digest` / `sentiment_divergence` |
| `severity` | `immediate` / `digest` |
| `symbol` | 可空（合并提醒为空） |
| `title`、`body` | 展示文案 |
| `payload_json` | 结构化数据（涨跌幅、新闻 id 列表等） |
| `dedupe_key` | 唯一：价格 `price:{symbol}:{交易日}`；新闻 `news:{news_id}:{symbol}`；合并 `digest:{窗口起点}` |
| `overnight` | 是否在静默时段产生 |
| `created_at`、`visible_at`、`read_at` | `visible_at` 为可见时刻（静默期为次日 08:00） |

接口：

- `GET /api/alerts?unread_only=&limit=`：可见提醒列表（`visible_at <= now`），新的在前
- `GET /api/alerts/unread-count`
- `POST /api/alerts/{id}/read`、`POST /api/alerts/read-all`
- SSE 新增事件 `alert.created`（仅非静默期的立即提醒触发前端弹出）
- `GET /api/health` 不变；`/api/notify/*` 删除

配置（`.env` 可覆盖）：`ALERT_PRICE_MOVE_PERCENT=5`、`ALERT_QUIET_HOURS_START=22:00`、`ALERT_QUIET_HOURS_END=08:00`、`ALERT_TZ=Asia/Shanghai`、`ALERT_WATCH_DIGEST_MINUTES=30`。

## 4. 任务

### T0 基线
切分支；备份 `app.db`；记录 pytest / ruff / vitest / build 基线。

### T1 提醒存储与接口（TDD）
- 测试先行：`alert` 模型与 repository（按 `dedupe_key` 幂等插入、可见性过滤、已读）；路由 4 个接口。
- 实现模型、Alembic 迁移（含 downgrade）、repository、schema、路由。

### T2 提醒规则服务（TDD）
- `AlertService`，可注入时钟，规则全部有单测：
  - 价格：仅持仓（`position_size > 0`）；`|change_percent| >= 5`；按北京时间交易日去重（跨重启有效，依赖数据库唯一键）；不同市场持仓都适用。
  - 新闻：标题匹配简称/代码（含 A 股 mention 置信度 ≥ 0.9）；持仓立即，关注股进入 30 分钟合并窗口；同一新闻同一股票只提醒一次；简称太短（< 2 字）或常见词不参与匹配。
  - 静默时段：跨午夜窗口；静默期 `overnight=true`、`visible_at=次日 08:00`、不发 SSE。
  - 合并：`watch_news_digest` 由周期任务每 30 分钟把窗口内的关注股命中合并为一条。
- 挂接：`main.py` 行情刷新回调、`queue_worker` 新闻挂载点、情绪背离 worker（默认关闭，保持关闭）。

### T3 删除飞书与旧通知体系
- 删除 `notification_service.py`、`feishu_client.py`、`notification_delivery_worker.py`、`notify` 路由与 schema、`feishu_notify_config` / `notification_job` 模型与 repository、相关测试；`digest_worker` 去掉推送；`http_pool` 去掉飞书客户端。
- 迁移删除 `feishu_notify_config`、`notification_job` 表与 `watchlist_item.alert_threshold` 列（downgrade 复原）。
- 清理 `notify_*` 配置。

### T4 前端：提醒中心
- 侧栏铃铛 + 未读数；新页面 `/alerts`（今日 / 隔夜汇总分组、标记已读、全部已读）；SSE `alert.created` 触发 toast。
- 删除 `NotifySettingsView`、`notifyStore`、飞书相关 client/类型/mock；导航"通知"改为"提醒"。
- 测试：组件与 store 单测、冒烟路由。

### T5 前端：自选股持仓高亮与合并组合
- `WatchlistSidebar` / `StockCard`：持仓股使用醒目配色（左侧色条 + 浅色底 + "持仓"标签，配色取现有主题变量），列表顺序不变。
- 删除添加弹窗中的单股阈值输入；删除 `/portfolio` 页面、路由与导航项（旧书签由兜底路由带回仪表盘）。
- 测试：持仓/非持仓渲染差异、弹窗不再提交阈值。

### T6 文档与验证
- 更新 README、`docs/current-state.md`、`.env.example`；变更记录。
- 全量 pytest / ruff / vitest / build / api-drift；备份副本上迁移往返；`make dev` 实测：持仓高亮、手动构造一条 ±5% 行情与一条标题命中新闻验证提醒生成与弹出、静默时段行为（注入时钟的单测 + 接口实测）。
- 独立子任务评审；完成后归档本计划。

## 5. 风险

| 风险 | 缓解 |
|---|---|
| 标题关键词匹配误报（如"阿里"出现在"阿里云合作伙伴"） | P2 接受一定误报，按新闻+股票去重；P3 用 AI 判断替换 |
| 删除飞书后若将来想恢复外部推送 | 代码在 git 历史；`alert` 表与渠道无关，日后可加推送通道 |
| 港股/美股简称匹配依赖 `display_name` 质量 | 自选股名称可编辑；匹配时同时用代码 |
| 价格提醒依赖行情 producer 正常运行 | 系统健康页已有 worker 心跳监控 |
