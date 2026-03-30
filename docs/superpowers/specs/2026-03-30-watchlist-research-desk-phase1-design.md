# Watchlist Research Desk Phase 1 Design

## 背景

当前 watchlist 单股详情页已经具备行情、K 线和相关新闻能力，但仍然要求用户自己完成第一轮信息筛选：哪些新闻是真驱动，哪些只是重复报道，哪些值得进一步跟踪。对以自选股为中心、周期偏 2 周到 2 个月的使用方式来说，这一层“噪音压缩”比继续扩新闻源更有价值。

本阶段的目标不是构建完整的研究系统，而是在现有详情页中补齐一层结构化的研究简报，让单股页面先回答“最近什么在驱动这只股票，以及这些驱动值不值得优先看”。

## 目标

- 在单股详情页新增研究简报区域，对最近相关新闻做结构化压缩。
- 将相关新闻按驱动类型归类，优先覆盖政策/监管、产品/订单/公司动作、产业链传导、价格异动解释四类。
- 给每条驱动分配动作等级，帮助用户快速区分“立即看”和“知道即可”。
- 在不依赖 LLM 的前提下先用可解释规则落地，保证可调试、可回归、可扩展。

## 非目标

- 不做 LLM 自动研报或主观多空判断。
- 不改造全站信息架构，范围仅限 watchlist 单股详情页链路。
- 不引入新的外部数据源或新的后台 worker。
- 不尝试一次性完成个性化学习闭环，只先为未来沉淀结构化入口。
- 不在 phase-1 生成模板化 `Research Focus` 文案，先把结构化驱动层做稳。

## 用户问题

当用户打开一只自选股时，系统应优先回答：

1. 最近 14 天这只票有哪些值得注意的驱动。
2. 哪些驱动属于政策/公司动作/产业链线索，哪些只是重复新闻。
3. 哪些驱动需要现在就点开看，哪些可以后看。
4. 当前新闻流里是否存在“价格先动、原因待解释”的空白区域。

## 方案对比

### 方案 A：只做前端规则归类

前端直接基于 `/related-news` 返回的新闻做关键词分类和优先级打标。

优点：开发快，不改后端接口。  
缺点：规则散落前端，不利于测试、复用和未来用于通知/排序。

### 方案 B：新增后端研究简报服务与接口

后端基于相关新闻生成研究简报，前端只负责展示。

优点：规则集中、接口清晰、后续可复用到通知和列表排序。  
缺点：会新增 schema、service 和 route，但范围仍可控。

### 方案 C：直接上 LLM 生成研究摘要

优点：文字表达更自然。  
缺点：不稳定、不可解释、难回归，而且当前并不需要先解决“文采”，而是先解决“筛选”。

### 结论

采用方案 B。第一阶段先把“结构化压缩”和“动作分层”做稳，后续若要引入 LLM，也应建立在这个结构化底座上。

## 交互设计

### 详情页新结构

在现有 `StockDetailPanel` 中，K 线主区下方、新闻列表上方新增 `Research Brief` 区块。

该区块包含两部分：

1. `Driver Summary`
   - 展示最近窗口内识别出的驱动数量。
   - 展示最高优先级动作标签，例如 `立即看`、`今日跟踪`。
   - 展示是否存在 `价格异动待解释` 提醒。

2. `Driver Buckets`
   - 按驱动类型分组展示：
     - 政策/监管/宏观
     - 产品/订单/公司动作
     - 产业链传导
     - 价格异动解释
   - 每组最多展示 2 条代表性驱动，避免过长。
   - 每条驱动显示标题、来源、时间、动作等级和简短理由。

### 动作等级

- `立即看`：高时效、高相关且匹配核心驱动类型。
- `今日跟踪`：相关，但持续性或直接性稍弱。
- `知道即可`：有参考价值，但优先级较低。

第一阶段不展示“忽略”结果，低质量项直接不进研究简报。

## 数据设计

新增后端响应对象 `WatchlistResearchBriefView`，包含：

- `symbol`
- `generated_at`
- `window_days`
- `top_action_level`
- `has_unexplained_price_move`
- `drivers`

约束：

- `window_days` 固定为 `14`
- `top_action_level` 为枚举：`act_now | watch_today | know_only | none`
- `drivers` 始终返回数组，允许为空
- 当 `drivers=[]` 时，`top_action_level` 必须为 `none`

每个 `driver` 包含：

- `category`
- `action_level`
- `reason`
- `news_item`

约束：

- `category` 为枚举：`policy_macro | company_action | supply_chain | price_action`
- `action_level` 为枚举：`act_now | watch_today | know_only`
- `driver` 代表“一条被选中的代表性驱动新闻”，不是聚合主题
- `news_item` 直接复用 `NewsItemSummary` 的最小信息集合，不再重复造完整详情结构

研究简报必须复用现有 `/api/watchlist/{symbol}/related-news` 背后的同一批相关新闻数据与相同的 symbol alias lookup 规则；phase-1 不允许引入第二套新闻检索逻辑。

## 规则设计

### 分类规则

先从现有 related news 数据集中筛出最近 14 天新闻，再基于新闻标题和摘要文本做关键词匹配，优先命中以下类别：

- 政策/监管/宏观：
  - policy, regulator, tariff, export control, guideline, subsidy, antitrust, approval
  - 政策, 监管, 发改委, 工信部, 补贴, 禁令, 制裁, 审批

- 产品/订单/公司动作：
  - launch, product, order, contract, guidance, earnings, capex, partnership
  - 订单, 合同, 产品, 发布, 指引, 财报, 扩产, 合作

- 产业链传导：
  - supply chain, supplier, upstream, downstream, demand, pricing, capacity
  - 产业链, 上游, 下游, 供应链, 需求, 涨价, 产能

- 价格异动解释：
  - surge, rally, drop, tumbles, jumps, after shares rose/fell
  - 大涨, 大跌, 飙升, 暴跌, 股价异动

若一条新闻命中多类，则按以下顺序选择主类：
政策/监管/宏观 > 产品/订单/公司动作 > 产业链传导 > 价格异动解释

### 动作等级规则

phase-1 仅使用 `驱动类型 + 时间新鲜度` 两维，不使用 `editorial_score` 或 `sentiment` 加权，避免规则漂移。

固定规则：

- `policy_macro` 或 `company_action`
  - 发布时间 `<= 7` 天：`act_now`
  - 发布时间 `> 7` 且 `<= 14` 天：`watch_today`
- `supply_chain`
  - 发布时间 `<= 14` 天：`watch_today`
- `price_action`
  - 发布时间 `<= 3` 天：`watch_today`
  - 发布时间 `> 3` 天：`know_only`
- 任何分类如果文本未命中核心驱动词，不进入 research brief

### 去重规则

- 同一分类内按标题标准化后去重。
- 每个分类最多保留 2 条代表性新闻。
- 结果按动作等级、发布时间倒序排列。

### 价格异动待解释

新接口通过复用现有 quote cache/`QuoteService.get_cached_symbol_quote()` 获取该 symbol 当前 `is_abnormal` 状态。

当个股当前 `is_abnormal=true`，且最近 14 天新闻中没有生成 `act_now` 或 `watch_today` 的驱动时，研究简报标记 `has_unexplained_price_move=true`，提醒用户优先寻找缺失原因。

## 组件与文件边界

### 后端

- `backend/app/services/watchlist_research_service.py`
  - 负责复用 related news 数据、规则归类、优先级打分、研究简报生成。
- `backend/app/schemas/watchlist.py`
  - 新增 research brief 相关 schema。
- `backend/app/api/routes/watchlist.py`
  - 新增 `GET /api/watchlist/{symbol}/research-brief`。
- `backend/tests/test_watchlist_research.py`
  - 覆盖规则归类、动作等级、A 股 alias lookup、价格异动待解释和路由行为。

### 前端

- `frontend/src/types/api.ts`
  - 新增 research brief 类型定义。
- `frontend/src/api/client.ts`
  - 新增 research brief API 调用和 mock fallback。
- `frontend/src/api/mock.ts`
  - 补齐 mock research brief 数据。
- `frontend/src/stores/watchlistStore.ts`
  - 增加 research brief 状态和“详情页工作区加载”编排逻辑，避免 view 重复请求新闻。
- `frontend/src/components/watchlist/ResearchBriefPanel.vue`
  - 新组件，展示研究简报。
- `frontend/src/components/watchlist/StockDetailPanel.vue`
  - 接入研究简报区块。
- `frontend` 对应测试文件
  - 覆盖 API、store、组件和详情页联动。

## 错误处理

- research brief 加载失败不阻断详情页主链路。
- 失败时隐藏研究简报并保留原有 K 线 + 新闻布局。
- 若接口 `200` 返回 `drivers=[]`，则展示空态文案“暂无可归因驱动，继续关注价格和原始新闻流”。
- “无相关新闻”和“有相关新闻但全部被过滤”统一视为 `drivers=[]`，使用同一空态。

## 验证策略

后端最小验证：

- `conda run -n news-caught pytest backend/tests/test_watchlist_research.py backend/tests/test_stock_news_search.py -q`

前端最小验证：

- `npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/watchlistStore.test.ts src/components/watchlist/ResearchBriefPanel.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts`
- `npm --prefix frontend run build`

## 风险与后续

- 关键词规则第一版会有误判，但它的优点是透明、易调参，适合作为阶段一底座。
- 当前未引入行业链条知识库，因此“产业链传导”仍然主要靠文本命中，后续可结合自定义标签进一步增强。
- 第一阶段仍是单股详情页能力；下一阶段可以把 research brief 摘要上浮到 watchlist 列表，直接做成自选股优先级分发器。
