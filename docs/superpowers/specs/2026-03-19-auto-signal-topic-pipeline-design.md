# 自动情绪标注与主题聚合增量流水线

## 背景

当前新闻刷新链路只负责抓取和入库 `news_item`，并不会自动生成情绪标签或主题聚合结果。数据库里绝大多数新闻的 `sentiment_label` 仍为空，`topic_cluster` / `topic_news_link` 也几乎只有初始化种子数据，导致 Dashboard 上的多空统计和主题聚合都无法反映真实新闻量。

## 目标

在每次 `POST /api/news/refresh` 成功插入新新闻后，自动对增量新闻执行：

1. 情绪分类，保证每条新新闻至少得到 `positive` / `negative` / `neutral` 之一
2. 主题归并，将新新闻链接到已有主题或创建新主题
3. 主题提炼，为新增或低置信主题生成标题、摘要、关键词和聚合情绪
4. 全链路可降级，LLM 不可用时仍能依赖规则链路产出可用结果

## 非目标

- 不重做现有前端结构
- 不引入复杂向量库或外部搜索索引
- 不对历史全量新闻做一次性离线重建；本轮只保证 refresh 后的新数据自动进入链路，并提供可复用的批处理入口

## 设计

### 总体流程

```text
POST /api/news/refresh
  ├─ NewsIngestionService.refresh_all()
  │   └─ 返回 inserted_items
  ├─ NewsSignalPipelineService.process_news_ids(inserted_item_ids)
  │   ├─ classify_news
  │   │   ├─ 规则情绪评分
  │   │   └─ 低置信条目可选走 LLM 校正
  │   ├─ assign_topics
  │   │   ├─ 规则生成 topic key
  │   │   ├─ 匹配已有 topic
  │   │   └─ 创建 topic + topic_news_link
  │   ├─ refine_topics
  │   │   ├─ 聚合关键词
  │   │   ├─ 计算 importance_score / sentiment_score
  │   │   └─ 新主题或低置信主题可选走 LLM 提炼标题与摘要
  │   └─ 返回处理摘要
  └─ API 继续返回 refresh summary
```

### 情绪分类策略

采用“两层判定”：

1. **规则基线**
   - 基于标题、摘要、正文（如有）做归一化文本
   - 使用正负向短语词典和轻量权重打分
   - 将命中映射为 `sentiment_score`
   - 阈值规则：
     - `score >= 0.2` => `positive`
     - `score <= -0.2` => `negative`
     - 其余 => `neutral`

2. **LLM 提质**
   - 仅在以下条件触发：
     - 规则命中弱、置信度低
     - 文本较长但存在多空混杂信号
     - 新闻被判定为新主题的代表条目
   - LLM 返回 JSON：`sentiment_label`、`sentiment_score`、`summary`、`keywords`、`topic_title_hint`
   - 若超时、限流、响应脏数据，则保留规则结果并记录错误，不阻断 refresh

### 主题聚合策略

不直接做昂贵的全量 pairwise clustering，而是用“归一化主题 key + 已有主题匹配”的增量归并方案。

1. **特征抽取**
   - 从标题/摘要中提取：
     - 标准化 token（小写、去停用词、去数字噪音）
     - 资本市场实体（股票代码、品牌名、行业关键词）
     - 事件关键词（如 `earnings`, `tariff`, `oil`, `shipment`, `guidance`, `AI`）

2. **候选 topic key**
   - 取 2 到 4 个高权重 token，按稳定顺序拼接成 key
   - 如果有股票 mention，则将核心股票/品牌 token 作为 key 前缀
   - 例如：`tencent ai enterprise`、`apple smartphone demand`

3. **匹配已有主题**
   - 先按 `topic_key` 精确匹配
   - 若没有，再按关键词交并比 + 股票重合度做近似匹配
   - 近似匹配得分低于阈值时创建新主题

4. **主题重算**
   - `importance_score` 由新闻数、最近出现时间、情绪强度、关联股票数综合得到
   - `sentiment_score` 为主题内新闻情绪均值
   - `last_seen_at` 更新为主题内最新新闻时间

### LLM 在主题层的职责

LLM 不负责“决定是否有主题”，只负责“把规则主题变得更像人写的”。

输入：主题内最近 3 到 5 条代表新闻标题/摘要 + 规则关键词  
输出：

- `topic_title`
- `topic_summary`
- `keywords`
- 可选修正后的 `sentiment_label` / `sentiment_score`

调用条件：

- 新建主题
- 规则标题过于机械
- 主题摘要为空

### 数据模型变更

#### `news_item`

新增字段：

- `signal_status`: `pending` / `processed` / `failed`
- `signal_error`: 最近一次处理错误摘要
- `signal_updated_at`
- `topic_cluster_id` 不直接加在本表，继续使用 `topic_news_link` 维持多对多扩展性

#### `topic_cluster`

新增字段：

- `topic_key`: 稳定归并 key，唯一索引
- `cluster_version`: 便于后续升级归并规则
- `llm_refined_at`: 最近一次 LLM 提炼时间

#### 新增 `news_signal_result`

用于记录单条新闻处理结果，避免把算法元数据全塞进 `news_item`：

- `news_id`
- `classifier_type` (`rule` / `llm` / `hybrid`)
- `signal_confidence`
- `topic_key`
- `keywords`
- `summary`
- `payload_json`

### 服务边界

#### `backend/app/services/news_signal_pipeline.py`

编排入口，负责批量处理新新闻、事务切分、错误汇总。

#### `backend/app/services/news_signal_classifier.py`

规则情绪计算、LLM 校正、摘要/关键词归一化。

#### `backend/app/services/topic_clustering.py`

topic key 生成、已有主题匹配、主题聚合分数重算。

#### `backend/app/repositories/news_signal_repository.py`

封装 `news_signal_result`、`topic_cluster`、`topic_news_link` 的写入与查询。

### 失败与降级策略

- 单条新闻失败不回滚整批 refresh
- LLM 失败回退规则结果并记录 `signal_error`
- 若主题提炼失败，保留规则生成的 `topic_title` / `topic_summary`
- API 刷新响应继续成功返回，只在日志和处理摘要中体现降级情况

### 测试策略

1. 分类测试
   - 正向、负向、中性文本的规则判定
   - 低置信场景触发 LLM
   - LLM 失败时规则降级生效

2. 聚合测试
   - 相似新闻归并到已有 topic
   - 新主题正确创建
   - topic `news_count`、`sentiment_score`、`importance_score` 正常更新

3. 集成测试
   - refresh 返回 inserted items 后自动跑 pipeline
   - 新新闻在 `/api/topics` 和 `/api/news/{id}` 中可见

## 关键决策

1. **同步执行增量流水线**
   保持 refresh 后页面立刻可见结果，不另开后台任务队列。

2. **规则先行，LLM 提质**
   保证无论 API 状态如何，每条新闻都有基础情绪和主题归属。

3. **topic key 驱动的增量聚合**
   先解决“能持续产出”，而不是一次性上复杂聚类系统。

4. **保留 `topic_news_link` 多对多结构**
   当前虽然多为单主题归属，但后续可扩展为一条新闻关联多个 topic。

## 风险与后续

- 规则词典初版会偏保守，中性占比会先偏高，但比大面积空值更可靠
- 中文快讯和极短标题的主题命名质量仍会依赖 LLM
- 如果后续新闻量继续扩大，topic 匹配可能需要引入更强的文本相似度或向量检索
