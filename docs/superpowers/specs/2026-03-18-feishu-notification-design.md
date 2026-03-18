# 飞书推送通知设计文档

> 日期：2026-03-18  
> 状态：已确认

## 目标

为 News Caught 增加飞书（Lark）应用 Bot 推送通知能力，支持三类信号实时/聚合推送到飞书群聊或个人。

## 触发场景

| 信号类型 | 触发时机 | 推送策略 |
|----------|----------|----------|
| 新闻聚合 | 新闻抓取完成后 | 按时间窗口聚合（默认 60 分钟），批量推送 |
| 自选股异动 | 行情刷新时价格变动超过阈值 | 实时推送 |
| LLM 分析结果 | 新闻分析完成且有明确标的 | 实时推送 |

## 飞书接入方式

- **飞书应用 Bot API**（非 Webhook），需要 App ID + App Secret
- 通过 `tenant_access_token` 鉴权，token 有效期 2 小时，过期自动刷新
- 消息格式：飞书 Interactive Card（消息卡片）
- 发送目标：群聊（`chat_id`）或个人（`open_id`），在前端设置页配置

## 数据模型

### FeishuNotifyConfig（新增表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 主键 |
| app_id | str | 飞书应用 App ID |
| app_secret | str | 飞书应用 App Secret |
| target_type | str | `"chat"` 或 `"user"` |
| target_id | str | 群聊 chat_id 或用户 open_id |
| news_enabled | bool | 是否推送新闻聚合（默认 true） |
| news_keywords | str\|None | 新闻过滤关键词，逗号分隔 |
| news_batch_interval_minutes | int | 新闻聚合间隔（默认 60） |
| alert_enabled | bool | 是否推送自选股异动（默认 true） |
| analysis_enabled | bool | 是否推送 LLM 分析结果（默认 true） |
| is_active | bool | 总开关 |
| updated_at | datetime | 最后更新时间 |

### SignalEvent（扩展）

新增 `notified_at: datetime | None` 字段，标记事件是否已推送。

## 架构

```
业务层（news_ingestion / news_analysis / quote_service）
  ↓ publish event
EventBus（进程内）
  ↓ subscribe
NotificationService
  ├─ 实时通道：watchlist.alert / analysis.completed → 立即发送飞书卡片
  └─ 聚合通道：news.batch_ready → 定时检查缓冲区 → 批量发送
       ↓
FeishuClient（飞书 API 封装）
  ├─ get_tenant_access_token()
  └─ send_card_message()
```

## 后端接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/notify/feishu/config | 获取当前飞书配置 |
| POST | /api/notify/feishu/config | 创建/更新飞书配置 |
| POST | /api/notify/feishu/test | 发送测试消息验证连通性 |

## 消息卡片模板

### 新闻聚合卡片

- 标题：📰 新闻聚合推送（N 条）
- 内容：每条新闻一行：标题 | 来源 | 市场 | 时间
- 底部：查看详情链接

### 自选股异动卡片

- 标题：⚠️ 自选股异动
- 内容：股票名称、代码、当前价格、涨跌幅、触发阈值
- 颜色：涨为红/跌为绿

### LLM 分析结果卡片

- 标题：🔍 LLM 标的分析
- 内容：新闻标题、首选标的、候选列表、摘要、风险提示

## 前端

### 通知设置页 `/settings/notify`

与现有 LLM Settings 页面结构一致：
- 当前配置摘要卡片
- 配置表单：App ID、App Secret（密码输入）、目标类型（下拉）、目标 ID、三个通知开关、新闻聚合间隔
- 测试按钮：点击发送测试消息
- 导航：AppShell 侧栏新增入口 `06 Notify`

## 边界

- 第一版仅支持飞书单渠道，后续可扩展 Telegram/邮件/OpenClaw
- 飞书凭证存储在数据库（与 LLM key 同级安全策略），适合个人使用
- 新闻聚合使用进程内定时器，不引入外部调度器
- 自选股异动检测需要在行情刷新时主动比较阈值
