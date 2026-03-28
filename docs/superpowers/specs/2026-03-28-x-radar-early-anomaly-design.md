# 2026-03-28 X Radar Early Anomaly 设计

## 1. 背景

当前 `X Monitor` 已经具备：

- 账号名单管理
- `twitterapi.io` provider 拉取
- 原始帖子去重入库
- 基础搜索与列表展示

但它当前更像“抓帖运维台”，而不是“异动雷达”：

- provider、采集、信号加工、查询展示耦合在同一个 service 内
- 页面主视角仍然是原始帖子流，用户需要自己判断哪些值得看
- 宏观/政策事件没有独立信号层，只能靠关键词搜索或人工阅读
- API key 或 provider 变化会直接影响整个模块边界

用户本轮目标已经明确为：

- 以“我自己关注的一组账号”为主线
- 补充“宏观 / 政策类事件”的早期感知
- 所有命中先进入候选池，再由系统进行优先级排序
- 第一落点仍是独立的 `X Radar` 页面，不先并入首页或自选股

因此，本轮不是继续优化帖子阅读体验，而是把模块升级为“新闻前哨站”。

## 2. 目标与非目标

### 2.1 目标

- 将 `X Monitor` 重构为 `X Radar`，优先输出“值得看的异动信号”，而不是原始帖子时间流。
- 保留当前账号池资产，以“名单驱动”作为主采集模式。
- 在名单驱动基础上增加“宏观 / 政策事件规则”命中能力。
- 引入独立的信号层模型，把原始帖子提升为可排序、可聚合、可解释的异动对象。
- 把 provider 接入与信号逻辑解耦，使 `twitterapi.io` 仅作为一个 adapter，而不是模块本体。
- 页面改为 `Priority Radar -> Macro Watch -> Evidence Feed` 三层结构。

### 2.2 非目标

- 本轮不接入首页事件流。
- 本轮不接入自选股详情页。
- 本轮不做全网无限扩张式舆情搜索，仍以自定义账号池为主。
- 本轮不引入复杂 LLM 推理或自动摘要工作流。
- 本轮不做完整情绪指数大盘，也不做历史回测体系。

## 3. 方案比较

### 方案 A：在现有 `x_post` 上直接补字段

做法：

- 继续沿用现有 `x_post` 为唯一核心表
- 增加 `event_type`、`priority_score`、`macro_tag` 等字段
- 页面仅在查询结果上做排序和聚合

优点：

- 改动最小，上线快
- 复用现有 API 和存储逻辑

缺点：

- “帖子”和“信号”语义混杂
- 后续 provider 扩展、聚合规则增强会越来越难维护
- 很难清楚表达“为什么这条值得看”

### 方案 B：原始层 + 信号层双层模型

做法：

- `x_post` 继续保存原始帖子
- 新增 `x_signal` 表保存异动信号
- 新增 `x_signal_post_link` 保存信号与证据帖子的映射
- provider、采集、信号计算、查询展示分别拆开

优点：

- 结构清楚，边界稳定
- 最符合“异动雷达”的产品定位
- 后续接首页和 watchlist 时可直接复用 `x_signal`

缺点：

- 需要增加新模型和聚合逻辑
- 实现成本高于直接补字段

### 方案 C：直接做情绪监控面板

做法：

- 重点做情绪分数、主题热度、账号情绪偏向
- 异动对象不单独建模

优点：

- 看起来很像成熟终端
- 对“情绪监控”叙事友好

缺点：

- 现阶段缺少足够规模数据与标注支撑
- 容易做成表层炫技，实际决策价值不足

## 4. 决策

采用方案 B：双层模型。

理由：

- 用户最核心的独特资产是“亲自筛选过的一组账号”，不是通用全网搜索。
- 模块要表达的价值是“提前发现异动”，不是“更舒服地看推文”。
- 只有把原始帖子提升成信号对象，页面才会从工具页变成产品能力。

## 5. 核心定位

`X Radar` 的核心问题不是“X 上发生了什么”，而是：

- 哪些我关注的账号刚刚释放了值得注意的市场信号？
- 哪些宏观 / 政策主题开始形成讨论？
- 哪些内容值得我在新闻发酵前先看一眼？

成功标准：

- 打开页面先看到“高优先级异动”，而不是先看到原始帖子流。
- 同一事件下的多条帖子能被归并成单个信号卡。
- 每个信号卡都能解释“为什么值得看”以及“证据来自哪里”。
- provider 变更或 API key 失效不会强耦合到整个模块结构。

## 6. 架构设计

### 6.1 模块边界

将当前 `backend/app/services/x_monitor.py` 拆分为四层职责：

- `XProvider`
  - 统一外部 provider 协议
  - 定义 `fetch_account_posts`、`search_posts`、`probe_health`
- `TwitterApiIoProvider`
  - `twitterapi.io` 的具体实现
  - 只负责请求、限流、错误映射与 payload 归一化
- `XIngestionService`
  - 从账号池抓取帖子
  - 处理去重、原始入库、mention 提取
- `XSignalBuilder`
  - 根据原始帖子生成信号
  - 负责宏观事件命中、优先级打分、同题聚合
- `XRadarQueryService`
  - 面向前端输出 `Priority Radar`、`Macro Watch`、`Evidence Feed`

现有 `XMonitorService` 保留为编排层或被轻量替换为 façade，避免路由层直接理解底层细节。

### 6.2 数据模型

保留：

- `x_account`
- `x_post`
- `x_post_symbol_mention`
- `x_source_health`

新增：

#### `x_signal`

字段建议：

- `id`
- `signal_type`
  - `account_post`
  - `macro_event`
  - `multi_account_resonance`
- `title`
- `summary`
- `market`
- `topic_tag`
- `macro_tag`
- `primary_symbol`
- `priority_score`
- `confidence_score`
- `novelty_score`
- `resonance_score`
- `account_weight_score`
- `market_relevance_score`
- `source_count`
- `first_seen_at`
- `last_seen_at`
- `status`
  - `active`
  - `cooling`
  - `archived`

#### `x_signal_post_link`

字段建议：

- `signal_id`
- `post_id`
- `evidence_rank`
- `match_reason`

设计原则：

- `x_post` 是事实层，存“抓到了什么”
- `x_signal` 是解释层，存“为什么值得看”
- 一个信号可挂多条帖子，一条帖子也可参与多个信号，但第一版优先做“一帖一主信号，多帖聚合同主题信号”

### 6.3 Provider 抽象

新增 provider 协议层，而不是让 `twitterapi.io` client 直接被业务层调用。

目标：

- API key 过期只影响 adapter
- 未来可接其他 provider 或 fallback mock
- 路由、信号生成、前端查询不感知第三方接口细节

第一版协议：

- `fetch_account_posts(handle: str, limit: int = 20) -> list[dict]`
- `search_posts(query: str, limit: int = 20) -> list[dict]`
- `probe_health(handle: str | None = None) -> tuple[bool, str]`

## 7. 信号设计

### 7.1 第一版信号类型

首版只做三个高价值信号，避免泛化过度：

#### `account_post`

定义：

- 核心或观察账号发出命中高价值规则的帖子

典型例子：

- 关注账号发出企业合作、制裁、出口限制、财报预警等信息

#### `macro_event`

定义：

- 帖子命中宏观 / 政策词典

典型命中：

- 关税
- 利率
- 美联储 / 央行
- 出口管制
- 制裁
- 战争 / 冲突
- 财政刺激
- 监管调查

#### `multi_account_resonance`

定义：

- 多个关注账号在短时间窗口内围绕同一主题或宏观标签发帖

价值：

- 不是单点噪音，而是开始形成共识或传播

### 7.2 第一版优先级规则

第一版不引入复杂模型，使用规则打分：

`priority_score = account_weight + macro_weight + novelty + resonance + market_relevance`

拆解建议：

- `account_weight`
  - `core` > `watch`
  - 可结合 `priority` 字段做微调
- `macro_weight`
  - 不同宏观 / 政策标签有不同基础权重
- `novelty`
  - 同类主题在过去 12 至 24 小时是否首次出现
- `resonance`
  - 同一主题在窗口内是否有多个关注账号命中
- `market_relevance`
  - 是否带 ticker、公司名、行业主题、政策对象

### 7.3 宏观 / 政策规则

首版使用规则词典，不引入模型分类：

- 宏观词典文件化，便于迭代
- 每个标签包含：
  - `tag`
  - `keywords`
  - `aliases`
  - `weight`
  - `market_scope`

例如：

- `tariff`
- `rate`
- `fed`
- `export_control`
- `sanction`
- `war`
- `regulation`
- `fiscal_stimulus`

匹配策略：

- 标题 / 正文大小写归一
- 支持基础同义词
- 可同时命中多个标签，但要有一个主标签

### 7.4 聚合规则

首版聚合遵循“保守可解释”：

- 同一主标签
- 同一市场
- 在近 6 小时窗口
- 文本相似度或关键词重叠达到阈值

满足时聚为一个信号，并汇总：

- 首次来源账号
- 最近来源账号
- 证据帖子数
- 覆盖账号数

## 8. API 设计

保留现有：

- `GET /api/x/accounts`
- `POST /api/x/accounts`
- `PATCH /api/x/accounts/{handle}`
- `DELETE /api/x/accounts/{handle}`
- `POST /api/x/accounts/import`
- `POST /api/x/accounts/export`
- `POST /api/x/refresh`
- `GET /api/x/posts`
- `GET /api/x/search`

新增：

- `GET /api/x/radar`
  - 返回页面所需的三层结构
  - `priority_signals`
  - `macro_clusters`
  - `evidence_stream`

其中：

- `priority_signals` 面向顶部雷达卡
- `macro_clusters` 面向中层宏观事件聚合
- `evidence_stream` 继续保留原始帖子证据流

接口设计原则：

- 页面主要依赖 `GET /api/x/radar`
- 原始帖子接口保留，用于证据层与调试
- 搜索能力保留，但不再是页面主入口

## 9. 前端设计

页面从“状态与账号管理 + 帖子流”改为“雷达台 + 账号管理抽屉 / 侧栏”。

### 9.1 顶部

- 标题改为 `X Radar`
- 副标题明确定位：
  - 自定义账号池
  - 宏观 / 政策事件补充
  - 新闻前哨站
- 状态条展示：
  - provider 健康
  - 最近刷新
  - 本轮产出的信号数

### 9.2 第一层：Priority Radar

- 展示高优先级信号卡
- 每张卡必须回答：
  - 为什么值得看
  - 是谁先说的
  - 命中了什么标签
  - 证据有几条

卡片字段建议：

- 标题
- 一句话摘要
- 优先级标签
- 宏观 / 主题标签
- 账号数 / 帖子数
- 首次时间 / 最近时间

### 9.3 第二层：Macro Watch

- 以宏观 / 政策标签为维度聚合
- 展示最近活跃的主题簇

例如：

- `Tariff Watch`
- `Fed Watch`
- `Export Control`

### 9.4 第三层：Evidence Feed

- 展示原始帖子证据流
- 可以从信号卡下钻查看证据
- 保留翻译、原帖链接、symbol 命中等细节

### 9.5 账号管理

- 继续保留账号管理能力
- 但默认不作为页面主视觉中心
- 可放在侧栏、折叠卡或下方工作区

## 10. 测试策略

### 10.1 后端

- provider 抽象与 `twitterapi.io` adapter 测试
- refresh 后生成 `x_signal` 的集成测试
- 宏观 / 政策标签命中测试
- 多账号共振聚合测试
- `GET /api/x/radar` 返回结构测试
- 旧 `GET /api/x/posts` 回归测试

### 10.2 前端

- `X Radar` 页渲染 `Priority Radar / Macro Watch / Evidence Feed`
- 信号卡字段与状态文案断言
- 账号管理区仍可新增、启停、导入导出
- 原始证据流保留现有翻译与搜索基础能力

## 11. 风险与后续

- 规则打分首版一定不完美，需接受“先可解释，再逐步调优”。
- 若信号聚合过宽，可能把不同事件错并；若过严，又会失去共振价值，因此首版应保守。
- provider 健康与刷新冷却仍要保留，否则页面会在 API key 失效时显得“没有数据但原因不明”。
- 后续若接首页和自选股，应直接复用 `x_signal`，而不是再从原始帖子层重新推导。
