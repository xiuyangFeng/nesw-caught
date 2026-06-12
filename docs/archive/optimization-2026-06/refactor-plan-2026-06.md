# News-Caught 重构方案(2026-06)

> 范围:前端仪表盘视觉升级(暗色金融终端风)+ 后端抓取并发化与调度、去重/相关性算法、实时性。
> 节奏:分四个 Phase,每个 Phase 可独立交付、独立回滚。

---

## 1. 现状诊断(基于代码审查)

### 1.1 后端

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| P0 | `refresh_all` 串行抓取所有源,同步阻塞 HTTP | `news_ingestion.py:645` | 一个慢源(超时 30s)拖垮整轮;`POST /news/refresh` 同步执行,阻塞 API worker |
| P0 | `cadence_seconds` 定义了但**没有任何调度器使用它** | `news_fetcher.py` 仅一次性脚本 | 所有源同频刷新,靠手动触发;高频源不及时、低频源浪费请求 |
| P0 | 去重按"自然小时"取候选窗口 | `_find_duplicate_item` | 23:58 与 00:02 发布的同一新闻落在不同窗口 → 漏判重复 |
| P1 | 去重候选 = 窗口内**全部新闻**逐条比 signature | 同上 | O(N) 全量扫描,数据量增长后明显变慢;且只有精确 signature 匹配,标题差一个标点即判为新条目 |
| P1 | 失败无退避:`consecutive_failures` 只记录不降频 | `_refresh_source` | 坏源每轮照抓,浪费配额、拉高时延 |
| P1 | 信号 pipeline 仅在"本轮无新条目"时才处理积压 | `refresh_all` 尾部 | 逻辑反直觉:新闻越多,积压处理越被饿死 |
| P2 | `avg_latency_ms = (old+new)/2` 伪平均 | `_refresh_source` | 指标失真,应为 EMA |
| 约束 | **数据库是 SQLite**(`data/app.db`) | `config.py:14` | 并发写是大坑,直接多线程写库会 `database is locked` |

### 1.2 前端

- `DashboardView.vue` 423 行单文件,统计卡片基于"当前已加载新闻"计数(受分页影响,不是真实总量,应由后端给聚合接口)。
- 已有暗色基调和 SSE 状态轨,但缺少:趋势 sparkline、来源健康可视化、市场分布图、信号时间线;信息层级平。
- `HeroMetrics` / `TopicBoard` 偏简单文本卡,无图表。

---

## 2. 方案对比

### 2.1 抓取并发化 + 调度

| 方案 | 做法 | 优点 | 缺点 | 长期成本 |
|------|------|------|------|----------|
| **A(推荐)** | 常驻 ingest worker:`asyncio` + `httpx.AsyncClient` 并发抓取;每源独立 task 按 `cadence_seconds` 调度,失败指数退避;**抓取并发、落库仍单写线程**(队列汇聚) | 吞吐高;尊重 cadence;绕开 SQLite 并发写 | 改造 `_refresh_source` 为 async,工作量中 | 低 |
| B | `ThreadPoolExecutor(max_workers=8)` 并发抓取,落库串行 | 改动最小,1 天可上线 | 仍无 per-source 调度;线程开销 | 中(迟早重写) |
| C | Celery/RQ + Redis 分布式任务 | 水平扩展 | 单机自用项目过度设计,运维成本陡增 | 高 |

**推荐 A,可先落 B 作为 Phase 1 止血,再演进到 A。**
关键设计:**"抓取并发、写库串行"**——所有 fetch 结果进 `asyncio.Queue`,单一 consumer 写 SQLite,彻底规避锁冲突。

```
┌─source task(per cadence)─┐
│ RSS-A  (300s, backoff)   │──┐
│ HTML-B (600s)            │──┼──> asyncio.Queue ──> 单写线程 ──> SQLite
│ API-C  (120s)            │──┘         │
└──────────────────────────┘            └─> event_bus(逐条 news.created)
```

退避公式:`delay = cadence * min(2 ** consecutive_failures, 8)`,成功即复位。

### 2.2 去重与相关性

| 方案 | 做法 | 准确率 | 成本 |
|------|------|--------|------|
| 快速止血 | 窗口改为 `published_at ± 60min` 滑动窗;给 `published_at`、`url_hash` 建索引;候选查询限制同 market | 修掉边界漏判 | 半天 |
| **A(推荐)** | 止血基础上加 **SimHash 标题指纹**:标题规范化(去标点/全半角/空白)→ 64-bit SimHash 存列 → 汉明距离 ≤ 3 判重;DB 持久化指纹,候选筛选用指纹前缀分段索引 | 抗标点/措辞微调,O(log N) 查找 | 2~3 天,无外部依赖 |
| B | Embedding 向量相似度(LLM API + 向量检索) | 最高,能识别改写稿 | 每条新闻一次 API 调用,延迟+费用;需向量库。建议仅对"疑似重复"(SimHash 距离 4~10 的灰区)做二次判定,而非全量 |

**相关性/优先级评分**:现有 `news_priority` 只是字典序排序,升级为加权分:

```
score = w1*tier + w2*official + w3*recency_decay(半衰期2h)
      + w4*watchlist_mention + w5*signal_strength
```

权重落配置文件,可灰度调参;输出 0~100 分存库,前端直接用。

### 2.3 实时性

| 方案 | 说明 | 评价 |
|------|------|------|
| **A(推荐)** | 抓取落库即逐条推 SSE(event_bus 已具备);信号 pipeline 改为**常驻消费者**订阅 `news.created_batch`,不再寄生于 refresh 流程 | 复用现有 SSE 链路,端到端延迟 = 抓取间隔 + 秒级 |
| B | 升级 WebSocket 双向 | 当前无双向需求,收益为零 |
| C | 前端轮询提频 | 否决,浪费且伪实时 |

实时性瓶颈本质在 2.1 的调度——cadence 生效后,高优源 60~120s 一轮,延迟自然下来。

### 2.4 前端仪表盘(暗色金融终端风)

设计 token(Tailwind theme 扩展):

```
背景层级: #070B14 (page) / #0D1322 (card) / #141C30 (elevated)
描边:     rgba(255,255,255,0.06),hover 提亮
涨跌色:   ⚠ 确认习惯——A股/港股用户通常【红涨绿跌】,
          现 dashboard 代码是 positive=绿。建议做成用户可切换的 token
强调色:   #53C2FF(信息) / #FFB454(警示) / #FF6F86(危险)
字体:     数字用 tabular-nums 等宽,标题 13~14px,正文 12px,高密度
```

布局重排(12 栅格):

```
┌────────────────────────────────────────────────────┐
│ KPI 行: 今日新闻量+sparkline | 信号数 | 多空比 | 源健康 │
├──────────────────────────┬─────────────────────────┤
│ 信号时间线 (实时滚动,      │ 异动榜 (涨跌色块,        │
│  按 score 着色)           │  mini bar)              │
├──────────────────────────┼─────────────────────────┤
│ 主题热度板 (TopicBoard     │ 来源健康热力条           │
│  升级: 气泡/热度条)       │ (per-source 状态矩阵)    │
└──────────────────────────┴─────────────────────────┘
```

配套改造:

- `DashboardView` 拆为 `KpiRow` / `SignalTimeline` / `MoversPanel` / `SourceHealthGrid` 四个组件,各自带 test。
- 图表用轻量 SVG 自绘 sparkline(项目已自绘 K 线,有现成功底),**不引入 ECharts 全量包**;若需要复杂图再按需引入。
- KPI 数据改由后端新增 `/api/dashboard/summary` 聚合接口,杜绝"前端用已加载分页数据当总量"。

---

## 3. 分阶段实施计划

| Phase | 内容 | 交付物 | 预估 |
|-------|------|--------|------|
| **1 止血** | 去重窗口改滑动窗 + 索引;ThreadPool 并发抓取;常驻调度 worker(cadence + 指数退避);EMA 延迟指标 | 抓取轮次耗时 ↓70%+,坏源自动降频 | 2~3 天 |
| **2 算法** | SimHash 去重落库;优先级评分模型 + 配置化权重;信号 pipeline 常驻消费者 | 重复率可量化下降;`/news` 按 score 排序 | 3~4 天 |
| **3 前端** | 设计 token → `/dashboard/summary` 接口 → 四组件重写 + sparkline/热力条;涨跌色偏好开关 | 新仪表盘 | 3~5 天 |
| **4 验证** | 去重回归集(用历史库重放);并发压测(50 源模拟);前端 vitest + 截图对比 | 测试报告 | 1~2 天 |

每个 Phase 独立分支 + PR,Phase 1/2 用历史数据重放验证不丢新闻、不误判重。

---

## 4. 风险与坑

1. **SQLite 并发写**:必须坚持单写线程;若未来源数 > 50 或多 worker,直接迁 PostgreSQL,不要在 SQLite 上加 WAL 硬扛。
2. **SimHash 迁移**:存量新闻需补算指纹(写一次性回填脚本),否则新旧数据隔离判重。
3. **涨跌色**:改色前先确认你的习惯(红涨绿跌 vs 绿涨红跌),做成偏好而非写死。
4. **去重收紧的误杀**:汉明阈值从 3 起步,灰区进人工抽检日志,稳定后再调。
5. **`POST /news/refresh`**:调度器上线后该接口改为"触发一次异步任务并立即返回 job id",不再同步阻塞。

---

## 5. 待确认问题

1. 涨跌色习惯:红涨绿跌(A股/港股惯例)?
2. 新闻源未来规模:维持 <20 个,还是会扩到 50+?(决定是否提前迁 PostgreSQL)
3. Phase 2 的 embedding 二次判重是否需要?(有 LLM 配置在库,但产生持续费用)
