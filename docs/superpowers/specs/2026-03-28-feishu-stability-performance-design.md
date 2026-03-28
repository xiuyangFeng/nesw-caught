# 飞书通知稳定性与性能优化设计文档

> 日期：2026-03-28  
> 状态：已确认

## 目标

在不追求秒级实时的前提下，提升飞书通知链路的稳定性与性能，使其同时适配：

- 本地单机长期运行
- 后续迁移到服务器常驻抓取并推送
- 项目被 clone 下来后继续作为控制台使用

本轮目标优先级：

1. 尽量避免漏发重要通知
2. 接受少量重复通知
3. 将单条通知时延控制在几十秒量级
4. 降低重复鉴权、重复建连和进程内状态带来的不稳定性

## 当前问题

当前实现主要集中在 [notification_service.py](/Users/xiuyang/Desktop/news-caught/backend/app/services/notification_service.py) 和 [feishu_client.py](/Users/xiuyang/Desktop/news-caught/backend/app/services/feishu_client.py)，存在以下风险：

- 新闻聚合缓冲区 `_news_buffer` 存在内存中，服务重启后待发送新闻直接丢失
- 自选股阈值状态 `_watchlist_state` 也在进程内，多进程或重启后行为不稳定
- batch 调度依赖后台线程 `_batch_loop`，后续迁移到多 worker / 多实例时容易重复发送或调度失真
- `FeishuClient` 每次发送都新建 `httpx.Client`，连接池无法复用
- token 缓存仅存在于单个 `FeishuClient` 实例内，短时间多条消息会重复鉴权
- 失败发送仅记录日志，没有任务级重试、错误分类和可恢复机制

## 设计原则

- 投递语义采用“至少一次”，不追求严格 exactly-once
- 业务层和发送层解耦，业务不直接调用飞书 API
- 发送状态持久化，避免进程重启导致消息丢失
- 重试必须有边界，避免错误配置导致无限重试
- 本地单机可直接运行，不依赖 Redis / Celery 等额外基础设施

## 方案对比

### 方案 A：维持进程内模型，仅补连接复用和重试

优点：

- 改动最小
- 可较快缓解重复建连和短暂网络失败

缺点：

- 待发送消息仍可能因重启丢失
- 多进程和多实例下行为不可控
- 后续上服务器仍需重做

### 方案 B：引入数据库持久化通知任务队列

优点：

- 重启后任务不丢
- 可支持至少一次投递和有界重试
- 本地单机与未来服务器部署共享同一条链路
- 后续扩展其他通知渠道时边界更清晰

缺点：

- 需要新增任务模型和 worker 逻辑
- 首轮实现复杂度高于方案 A

### 方案 C：直接引入外部消息队列

优点：

- 扩展性最好
- 后续多实例和高吞吐更成熟

缺点：

- 当前阶段过重
- 本地部署和 clone 运行门槛显著提升

## 推荐方案

采用方案 B：数据库持久化通知任务队列。

原因：

- 能显著降低漏发风险，符合“宁可偶尔重复，也尽量不要漏掉重要通知”的业务取向
- 不引入额外基础设施，仍可保持本地单机易用
- 后续迁移服务器常驻时不需要推翻重写

## 目标架构

```text
业务层（news_ingestion / news_analysis / market watchlist）
  ↓ enqueue
NotificationService
  ├─ 规范化 payload
  └─ 写入 notification_job
       ↓
NotificationDeliveryWorker
  ├─ 扫描待发送任务
  ├─ 调用 FeishuClient 发送
  └─ 更新任务状态 / 重试时间
       ↓
FeishuClient
  ├─ 复用 HTTP 连接
  ├─ 缓存 tenant_access_token
  └─ 处理飞书 API 响应与错误分类
```

## 数据模型

新增 `notification_job` 表，建议字段如下：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 主键 |
| channel | str | 先固定为 `feishu` |
| event_type | str | `news_batch` / `watchlist_alert` / `analysis_result` |
| payload_json | json/text | 发送所需业务负载 |
| status | str | `pending` / `sending` / `sent` / `failed` |
| attempt_count | int | 已重试次数 |
| next_retry_at | datetime | 下次允许重试时间 |
| dedupe_key | str\|None | 弱去重键，避免明显重复 |
| last_error | str\|None | 最近一次失败原因 |
| lease_until | datetime\|None | 任务抢占租约，便于未来多 worker |
| created_at | datetime | 创建时间 |
| sent_at | datetime\|None | 实际发送时间 |

说明：

- `dedupe_key` 只做弱约束，不做严格唯一投递语义
- `lease_until` 虽然本地单机下不一定立即需要，但可以提前为未来多实例留好边界

## 发送流程

### 新闻事件

1. 新闻抓取完成后，不直接写入内存 buffer
2. 业务层调用 `NotificationService` 入队新闻通知源事件
3. 聚合 worker 按配置时间窗挑选未发送新闻，生成一个 `news_batch` 任务
4. delivery worker 发送 batch 卡片
5. 成功后标记任务为 `sent`

### 自选股异动

1. 仍保留现有阈值越界判断思路
2. 首轮只把“真正发送”动作改为入库 job
3. 如果服务重启导致个别重复提醒，先接受，不在第一阶段引入复杂持久化状态机

### LLM 分析结果

1. 分析完成后直接创建 `analysis_result` 任务
2. 由 delivery worker 异步发送

## 重试与失败处理

### 可重试错误

- 网络超时
- 连接失败
- 飞书 5xx
- 限流或临时不可用
- token 过期且刷新后可恢复

### 不可重试错误

- `app_id` / `app_secret` 错误
- `target_id` 无效
- 权限不足
- 卡片格式非法

### 建议退避策略

| 尝试次数 | 下次重试间隔 |
|----------|--------------|
| 1 | 30 秒 |
| 2 | 2 分钟 |
| 3 | 5 分钟 |
| 4 | 15 分钟 |
| 5 | 30 分钟 |

超过上限后将任务标记为 `failed`，保留 `last_error` 供设置页或日志排查。

## FeishuClient 性能优化

当前瓶颈不是单次消息体大小，而是重复建连和重复鉴权。建议调整为：

- 复用长期存活的 `httpx.Client`，启用连接池
- token 缓存提升到长期 sender/provider 层，而不是跟随一次性 client 实例
- token 接近过期时提前刷新
- 若发送时收到 token 失效错误，允许强制刷新一次后重发当前请求

预期收益：

- 降低 TLS 握手和重复建连开销
- batch 连发时减少 token 获取次数
- 提升短时间内多条通知的整体吞吐稳定性

## 范围边界

本轮设计只关注稳定性和性能，不处理以下内容：

- 飞书卡片视觉样式重设计
- 多渠道通知抽象（Telegram/邮件等）
- 引入 Redis、Celery、Kafka 等外部基础设施
- 严格 exactly-once 语义
- watchlist 边沿状态的完整持久化状态机

## 分阶段实施建议

### 第一阶段

- 新增 `notification_job` 持久化模型、仓储和 worker
- 将分析结果和自选股告警发送改为先入队再发送
- 改造 `FeishuClient`，复用 HTTP 连接和 token
- 增加任务状态、失败分类和有界重试测试

### 第二阶段

- 将新闻聚合从进程内 `_news_buffer` 迁移到数据库驱动的聚合窗口
- 增加重启恢复场景测试

### 第三阶段

- 根据真实使用情况评估是否需要持久化 watchlist 去重状态
- 若后续迁移到多实例，再启用更严格的抢占租约和 worker 并发控制

## 验证策略

后端最小验证建议：

- `conda run -n news-caught pytest backend/tests/test_feishu_notify.py -q`

实现阶段需补充的关键测试：

- 任务入队成功与状态流转测试
- 可重试错误与不可重试错误分类测试
- 最大重试次数测试
- token 缓存与强制刷新路径测试
- 重启后待发送任务恢复测试
- 新闻聚合窗口测试

## 风险与后续事项

- 第一阶段仍可能出现少量重复通知，属于可接受取舍
- 若未来发送量显著上升，数据库轮询模式可能需要升级为更专业的队列方案
- 若后续要支持多实例并发发送，需要补齐任务租约和抢占冲突处理
