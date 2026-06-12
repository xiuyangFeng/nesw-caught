# 飞书通知回归修复设计文档

> 日期：2026-03-18
> 状态：已确认

## 目标

修复飞书通知首版接入中的两个行为级回归：

1. 新闻刷新后必须只推送本次真实新增的新闻，不能靠“最近 N 条”反推。
2. 自选股异动通知不能在每次读取 `/api/market/watchlist` 时重复发送同一条提醒。

同时修正前端 mock 降级下飞书配置保存的一个兼容问题：编辑已配置项时留空 `app_secret`，不应把 `app_secret_set` 误改为 `false`。

## 已确认根因

### 新闻推送误选

当前 `/api/news/refresh` 在抓取完成后只拿到 `inserted_count`，然后调用 `NewsRepository.list_recent(limit=inserted_count)` 再去通知。这个重建过程按 `published_at/fetched_at` 排序，不等价于“本次真正插入的记录”，所以：

- 回填旧新闻时，可能漏掉刚插入但发布时间更早的记录；
- 已存在但发布时间更新的旧记录可能被误推；
- 插入数越大，误差越大。

### 自选股提醒重复发送

当前提醒逻辑挂在 `GET /api/market/watchlist` 上，只要涨跌幅仍高于阈值，每次页面启动或进入 watchlist 都会重新发送一次，读接口被附带成了重复通知入口。

### 前端 mock 兼容偏差

mock 保存逻辑把 `app_secret_set` 直接设为 `Boolean(payload.app_secret)`，导致“保留后端已有 secret”这个语义在 mock 环境里丢失。

## 方案

### 1. 让抓取服务显式返回本次新增新闻

- 为 `RefreshSummary` 增加 `inserted_items: list[NewsItem]` 字段。
- 为 `SourceFetchResult` 增加同样的聚合来源字段，或在 `_refresh_source()` 内部收集新插入对象并汇总到 `refresh_all()`。
- `_persist_item()` 改为返回新建的 `NewsItem | None`，调用方再据此累计插入数和新增对象列表。
- `/api/news/refresh` 直接遍历 `summary.inserted_items` 发送通知，不再通过 `list_recent()` 猜测。

这会把通知输入源从“推断”改成“事实”，修复根因且不扩大接口响应面。

### 2. 为自选股提醒增加越阈值边沿触发状态

- 在 `NotificationService` 中新增进程内状态 `symbol -> above_threshold`。
- `on_watchlist_alert()` 改成接收当前是否越阈值，并只在 `False -> True` 时发送提醒。
- 当股票恢复到阈值内时，将状态复位，允许下一次再次越阈值时重新提醒。
- `/api/market/watchlist` 仍可调用通知服务，但必须显式传入当前越阈值状态，让服务决定是否触发。

这保持本轮改动最小，不引入新调度器；缺点是状态随进程重启丢失，但相比“每次读接口都发”已经是可接受修复。

### 3. 保留 mock 下的 secret 已配置状态

- `frontend/src/api/client.ts` 的 mock fallback 保存逻辑改成：
  - 如果本次提交了非空 `app_secret`，则置 `app_secret_set = true`；
  - 否则保留原先的 `mockFeishuConfig.app_secret_set`。

## 测试策略

### 后端

- 在 `backend/tests/test_news_ingestion.py` 增加回归测试，证明 `/api/news/refresh` 只会把 `refresh_all()` 返回的 `inserted_items` 交给通知服务。
- 在 `backend/tests/test_market.py` 增加回归测试，证明 watchlist 连续两次读取且持续越阈值时只发一次；回落后再次越阈值才会再发。

### 前端

- 新增 `frontend/src/api/client.test.ts`，锁住 mock 保存飞书配置时的 `app_secret_set` 保留语义。

## 边界与取舍

- 本轮不把自选股提醒迁到独立后台任务，避免扩大范围。
- 本轮不持久化“是否已提醒”的状态；进程重启后首次再读仍可能补发一次，这比当前每次页面加载都刷屏的行为风险低很多。
- 本轮不调整飞书 API、配置页字段或消息卡模板。
