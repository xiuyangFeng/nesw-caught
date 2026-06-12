# 2026-03-19 TwitterAPI.io 请求节流设计

## 目标

- 在后端增加可调节的 `twitterapi.io` 最小请求间隔配置
- 免费额度场景下严格按请求间隔访问 provider
- 当前默认按用户要求配置为每 6 秒最多发起 1 次请求
- 真实联调用 `MiniMax_AI` 验证返回的帖子来自 provider 原始响应

## 方案

- 新增配置 `TWITTERAPI_IO_MIN_INTERVAL_SECONDS`
- `TwitterApiIoClient` 在进程内维护最近一次真实请求时间
- 每次 `_request()` 前检查距离上次请求是否已达到最小间隔
- 若不足，则 `sleep` 剩余秒数后再发请求
- 节流对 `last_tweets` 和 `advanced_search` 都生效

## 非目标

- 本轮不做跨进程共享限流
- 本轮不做复杂配额池或队列系统
- 本轮不改变 3 小时账号刷新冷却逻辑
