# 2026-03-19 X Monitor 三小时冷却设计

## 背景

`twitterapi.io` 真实联调已确认可返回 `MiniMax_AI` / 其他账号的推文数据，但在短时间内连续请求多次时会命中 `429 Too Many Requests`。当前用户希望：

- 账号名单只保留 `MiniMax_AI`
- 账号刷新频率控制为每 3 小时一次
- 不允许编造链接，所有展示链接都必须来自真实 provider 返回

## 目标

- 为账号监控刷新增加 3 小时硬冷却
- 冷却期内调用 `/api/x/refresh` 时不访问远端 API
- 响应中明确标记本次是“已刷新”还是“因冷却跳过”
- 前端展示“下次可刷新时间”
- 默认账号名单改为仅保留 `MiniMax_AI`

## 非目标

- 本轮不新增后台定时任务
- 本轮不改变关键词搜索逻辑
- 本轮不引入复杂限流队列或分布式节流

## 方案

采用“硬性冷却”：

- 后端以 `x_source_health.last_success_at` 作为最近一次成功账号刷新时间
- 新增默认配置 `x_monitor_refresh_cooldown_hours=3`
- 如果当前时间距离最近成功刷新不足 3 小时，则：
  - 不调用 `twitterapi.io`
  - 返回 `skipped=true`
  - 返回 `skip_reason="cooldown_active"`
  - 返回 `next_refresh_at`

## 接口变化

`POST /api/x/refresh` 响应新增：

- `skipped: bool`
- `skip_reason: str | null`
- `next_refresh_at: datetime | null`

## 风险

- 冷却会让 3 小时内的手动刷新拿不到最新数据，这是显式取舍
- 如果未来要对不同账号做不同频率，当前全局冷却需要再升级为每账号冷却
