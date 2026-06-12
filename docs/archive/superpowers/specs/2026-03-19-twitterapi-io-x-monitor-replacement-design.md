# 2026-03-19 TwitterAPI.io 替换 X Monitor 桥接方案设计

## 1. 背景

当前项目的 `X Monitor` 模块通过本地 `grok-bridge` 拉取和抽取 X 内容。这条链路存在几个明显问题：

- 数据来源不是直接的推文接口，而是桥接加 AI 抽取，稳定性和可控性不足。
- 运行依赖本地额外仓库、浏览器登录状态和桥接服务，不适合作为长期方案。
- 当前用户目标已经变更为：使用 `twitterapi.io` 的 API key，直接获取指定账号和指定关键词相关的推特信息。

因此，本轮设计的目标不是继续增强 `grok-bridge`，而是彻底移除该桥接方案，并将 `X Monitor` 重构为基于 `twitterapi.io` 的直连 provider。

## 2. 目标与非目标

### 2.1 目标

- 删除现有 `grok-bridge` 相关实现、配置、说明和测试依赖。
- 使用 `twitterapi.io` API key 直连获取推文数据。
- 同时支持两类入口：
  - 账号监控：拉取关注账号的最新推文。
  - 关键词搜索：按关键词、ticker 或组合条件搜索推文。
- 第一版优先实现账号监控闭环；关键词搜索在第一版中作为手动查询能力提供。
- 保持该模块独立于现有 `news` 主采集链路，不直接混入新闻刷新和主题聚合。
- 尽可能复用现有页面骨架、数据库表和路由，控制替换成本。

### 2.2 非目标

- 第一版不接入 twitterapi.io 的 stream 监控能力。
- 第一版不做高频自动调度或实时推送。
- 第一版不把关键词搜索结果默认写入本地历史库。
- 第一版不把 `x_` 命名整体重构为 `twitter_` 命名。
- 第一版不将推文自动并入新闻源、主题聚类、通知流水线或交易动作。

## 3. 约束与设计原则

- 替换任务应聚焦在“移除桥接、换成直连 provider”，避免演变为无必要的大重构。
- 前后端现有 `X Monitor` 页面和 `/api/x/*` 路由尽量保留，以减少 UI 和调用层扰动。
- 数据模型在第一版中尽量复用，优先保留 `x_account`、`x_post`、`x_source_health` 的职责。
- 健康检查语义需要去桥接化，不能再以 `bridge` 命名描述新的 provider 状态。
- 账号监控结果应继续本地持久化，便于后续筛选、历史查看和二次处理。
- 关键词搜索应先保持轻量，避免一上来引入搜索历史、缓存、清理策略等复杂度。

## 4. 官方能力与方案选择

基于 `twitterapi.io` 当前公开文档，和本项目目标最匹配的能力是：

- 账号最新推文：`Get User Last Tweets`
- 搜索推文：`Advanced Search`
- 多账号实时监控：`monitor tweet` 系列接口

本轮设计选择的方案如下：

### 方案 A：轮询型双通道

- 账号监控通过 `Get User Last Tweets` 轮询指定账号最新推文。
- 关键词搜索通过 `Advanced Search` 提供手动查询。

优点：

- 与当前项目结构最兼容。
- 实现和测试最直接。
- 可以先把桥接替换掉，再决定是否上实时流。

缺点：

- 如果监控账号很多且刷新过于频繁，成本会高于流式方案。

### 方案 B：流式账号监控 + 搜索补充

- 账号监控改用 monitor/stream 能力。
- 关键词搜索仍走 `Advanced Search`。

优点：

- 更适合多账号、近实时场景。

缺点：

- 需要管理远端监控规则和生命周期。
- 与当前项目现有“手动刷新 + 本地入库”的模型差异较大。
- 不适合当前“先替换桥接再稳定使用”的阶段。

### 方案结论

第一版采用方案 A。待账号规模、刷新频率和成本压力明确后，再评估是否将账号监控升级为 stream 方案。

## 5. 目标架构

第一版替换后的结构如下：

1. 配置层
   - 保留 `X_MONITOR_ENABLED`
   - 删除 `GROK_BRIDGE_BASE_URL`
   - 删除 `GROK_BRIDGE_TIMEOUT_SECONDS`
   - 保留 `X_MONITOR_ACCOUNTS_FILE`
   - 新增 `TWITTERAPI_IO_API_KEY`
   - 可选新增 `TWITTERAPI_IO_TIMEOUT_SECONDS`

2. provider 客户端层
   - 新增 `twitterapi_io_client.py`
   - 负责：
     - 注入 `X-API-Key`
     - 封装 HTTP 请求
     - 统一错误转换
     - 超时控制
     - 响应字段归一化

3. 领域服务层
   - 保留 `x_monitor.py` 作为聚合服务入口
   - 内部拆成两个职责：
     - `refresh_account_posts()`：抓取账号最新推文并落库
     - `search_posts()`：执行关键词搜索并返回结果

4. 仓储/持久化层
   - 继续使用现有账号、帖子、健康状态仓储
   - 继续在本地保存账号监控抓到的推文

5. API 层
   - 保留 `/api/x/accounts`
   - 保留 `/api/x/posts`
   - 保留 `/api/x/refresh`
   - 新增 `/api/x/search`
   - 保留 `/api/health/x`，但返回字段改为 provider 语义

6. 前端层
   - 保留 `X Monitor` 页面和主入口
   - 页面文案从 `grok-bridge` 改为 `twitterapi.io`
   - 在现有页面中补入“关键词搜索”区域

## 6. 数据流设计

### 6.1 账号监控数据流

1. 用户在本地账号白名单文件中维护关注账号列表。
2. 后端刷新时读取账号配置并同步到 `x_account`。
3. 对每个激活账号调用 `twitterapi.io` 的最近推文接口。
4. 将结果映射成统一帖子结构。
5. 以 tweet id 为首选主去重键，URL 为次去重键。
6. 新帖子写入 `x_post`，并写入符号命中等关联信息。
7. 更新 `x_source_health` 中的成功/失败、耗时和错误信息。
8. 前端通过 `/api/x/posts` 拉取已落库结果展示。

### 6.2 关键词搜索数据流

1. 用户在前端输入关键词、ticker 或组合查询。
2. 前端调用后端 `/api/x/search`。
3. 后端将查询透传到 `twitterapi.io` 的 `Advanced Search`。
4. 后端将响应转换为统一的帖子摘要结构后直接返回。
5. 第一版不默认落库，只作为即时结果展示。

### 6.3 模块边界

- `X Monitor` 仍为独立旁路能力。
- 不自动参与 `news/refresh`。
- 不自动写入主题聚类。
- 不自动触发通知。
- 后续若要和 watchlist、notify、topic 打通，应另开设计，不在本轮方案中混入。

## 7. 数据模型策略

本轮建议尽量复用现有模型，避免把替换任务放大成重命名工程。

### 7.1 保留的现有模型

- `x_account`
- `x_post`
- `x_post_symbol_mention`
- `x_source_health`

### 7.2 字段策略

`x_post` 中如果已经有以下字段，应继续复用：

- `external_post_id`
- `canonical_url`
- `content_text`
- `posted_at`
- `captured_at`
- `market`
- `sentiment_label`
- `relevance_score`

本轮关键变化：

- `provider_name` 从 `grok-bridge` 改为 `twitterapi.io`
- 去重逻辑从“内容 hash + URL 容错”切换为“tweet id 优先”

### 7.3 搜索结果落库策略

第一版关键词搜索不默认落库。理由：

- 搜索是分析动作，不一定值得持久化。
- 避免引入搜索历史清理和重复查询治理。
- 将本轮替换聚焦在稳定接入和账号监控主闭环。

如果后续确认需要“保存搜索结果”，建议新增显式开关或单独保存动作，而不是第一版自动写库。

## 8. API 设计

### 8.1 保留接口

- `GET /api/x/accounts`
  - 返回当前本地同步的账号清单。

- `GET /api/x/posts`
  - 返回账号监控落库后的帖子流。
  - 继续支持账号、市场、symbol、关键词等过滤。

- `POST /api/x/refresh`
  - 手动触发账号监控刷新。

### 8.2 新增接口

- `GET /api/x/search`
  - 参数建议：
    - `q`: 搜索关键词，必填
    - `limit`: 结果数量
    - `sort`: 可选，先保持简单默认值
  - 返回统一帖子摘要结构。

### 8.3 健康检查调整

现有 `/api/health/x` 响应中带有 `bridge_*` 语义，不再适合新 provider。建议改为：

- `enabled`
- `configured`
- `healthy`
- `status`
- `provider_name`
- `last_success_at`
- `last_failure_at`
- `consecutive_failures`
- `total_fetches`
- `total_failures`
- `avg_latency_ms`
- `last_error`

同时，全局 `/api/health` 中的：

- `x_bridge_enabled`
- `x_bridge_healthy`

建议替换为：

- `x_monitor_enabled`
- `x_monitor_healthy`

## 9. 前端设计

### 9.1 页面定位

继续保留当前 `X Monitor` 页面路由和导航入口，不在本轮改名。

理由：

- 用户需求变化在于数据源，不在于产品概念彻底变化。
- 可以最小代价完成 provider 替换。
- 后续若确认模块要扩展为更宽泛的社交情报中心，再单独设计命名升级。

### 9.2 页面结构

页面建议保持单页双区：

- 区域一：账号监控
  - 健康状态
  - 账号白名单
  - 手动刷新按钮
  - 已落库推文列表

- 区域二：关键词搜索
  - 查询输入框
  - 搜索按钮
  - 搜索结果列表

### 9.3 页面文案调整

需要删除或替换以下语义：

- `grok-bridge 当前不可用`
- `用 grok-bridge 补充关注博主的市场相关 X 动态`
- 所有“桥接”表述

改为：

- `twitterapi.io 当前不可用`
- `通过 twitterapi.io 拉取关注账号与关键词相关的市场推文`
- 所有状态字段使用 provider/数据源语义

## 10. 错误处理与降级

### 10.1 后端错误分类

`twitterapi.io` client 应统一处理：

- API key 缺失
- 网络错误
- 超时
- 非 2xx 响应
- 结构化响应缺字段或格式异常

对外暴露时：

- `/api/x/refresh` 返回本次刷新错误摘要
- `/api/x/search` 返回明确的 HTTP 错误和简洁错误信息
- `/api/health/x` 反映最近一次 provider 访问状态

### 10.2 前端降级

- provider 未配置时，页面显示“未配置 API key”
- provider 请求失败时，显示最近错误和失败状态
- 不再保留针对 `grok-bridge` 的 mock 兼容语义

## 11. 测试策略

本轮改造的最小测试闭环建议包括：

### 11.1 后端

- `twitterapi.io` client 请求头、超时和错误转换测试
- 账号刷新：
  - 正常抓取
  - 空结果
  - 按 tweet id 去重
  - provider 失败时健康状态更新
- 搜索接口：
  - 参数校验
  - provider 响应映射
  - provider 失败返回
- 健康检查：
  - 未配置 API key
  - provider 成功
  - provider 失败

### 11.2 前端

- `X Monitor` 页面状态 banner 文案更新
- 页面能展示账号流和搜索结果
- 页面能处理 provider 未配置和错误状态
- 构建通过

### 11.3 手动验证

由于真实联调依赖：

- `TWITTERAPI_IO_API_KEY`
- 用户实际账号列表

实现和本地自动测试阶段可先使用 mock；最终联调时再由用户提供真实 key 和关注账号清单完成端到端验证。

## 12. 删除桥接的范围

本轮不是“停用桥接”，而是“完整移除桥接实现”。删除范围包括：

- `backend/app/services/grok_bridge_client.py`
- `GROK_BRIDGE_BASE_URL` 配置
- `GROK_BRIDGE_TIMEOUT_SECONDS` 配置
- README 中关于本地 `grok-bridge` 仓库与启动步骤的说明
- 健康检查中的 `bridge` 字段命名
- 测试中所有 `GrokBridgeClient` mock 和桥接语义断言
- 前端文案中的 `grok-bridge`

如果存在仅服务于桥接方案的本地说明或示例，也应一并清理。

## 13. 风险与后续事项

### 13.1 当前风险

- `twitterapi.io` 的实际返回结构需要在实现时以真实响应为准，不能只凭接口名假设字段。
- 若账号列表较多且刷新频繁，轮询方案可能带来额外成本。
- 原有 `x_post` 字段未必完全贴合 `twitterapi.io` 返回，需要实现阶段做字段映射核对。

### 13.2 后续演进方向

- 若账号监控规模扩大，可升级为 stream 监控方案。
- 若关键词搜索被频繁使用，可补缓存、历史或手动保存能力。
- 若后续要把推文结果接到通知、watchlist、topic，需要单开设计，避免污染本轮替换目标。

## 14. 设计结论

本轮采用“保留现有 `X Monitor` 产品入口与大部分数据模型，删除 `grok-bridge`，切换为 `twitterapi.io` 直连 provider”的方案。

第一版优先交付：

- 账号列表最新推文抓取与本地落库
- 页面手动刷新
- 关键词手动搜索
- 健康状态与错误可见
- 完整移除桥接依赖

该方案能直接满足用户“用 API key 获取关注推特信息，并删除原桥接功能”的目标，同时把改动控制在可测试、可迭代的范围内。
