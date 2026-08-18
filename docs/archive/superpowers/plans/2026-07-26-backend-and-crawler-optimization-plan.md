# 后端与爬虫抓取系统性优化方案 (22 项优化)

本计划用于导引 `news-caught` 后端与爬虫系统的全方位性能、鲁棒性与体验优化。

---

## 优化任务清单

### 🕸️ 一、 爬虫抓取与正文解析优化 (6 项)
1. **[网页抓取智能字符编码解析]** (`article_crawler.py`): 增加 `apparent_encoding` 与 `chardet` 探测降级机制，解决 GBK/GB2312 等中文新闻网页乱码问题。
2. **[国内主流行情新闻 DOM 选择器补充]** (`article_crawler.py`): 补充 `#artibody` (新浪)、`.news_body` (网易/腾讯) 等 DOM 选择器，并对段落密度提取进行去重。
3. **[Parser 解析引擎高性能加速]** (`parser.py`, `article_crawler.py`): 在 `BeautifulSoup` 中提供 `lxml` 解析器优先探测加速，解析速度提升 5x-10x。
4. **[XML / RSS 容错防崩处理]** (`parser.py`): 增加 XML 控制字符（如 `\x00`-`\x08`）与非法实体清洗防护，防止畸形 XML 导致 `ET.ParseError` 中断整批抓取。
5. **[RSS 抓取同批次条目内存去重]** (`parser.py`): 增加 `canonical_url` 单批次解析内存去重防护。
6. **[抓取 HTTP 默认 Header 与风控防封]** (`fetcher.py`): 为 Feed 抓取注入标准的 User-Agent 与 Accept-Language 标头，降低 403 封禁概率。

### ⚡ 二、 外部搜索与行情抓取优化 (6 项)
7. **[Google News RSS 港台语系与地区适配]** (`google_news_search.py`): 增强对 `zh-HK`/`zh-TW` 港台繁体语系及区域参数的支持，提升港台标的新闻抓取命中率。
8. **[股票搜索 LLM 扩展客户端连接池复用]** (`stock_news_search.py`): `_try_llm_expand` 迁移复用 `http_pool` 共享 Client，避免频繁建立/销毁 TCP 连接。
9. **[股票搜索多 Query 并发检索]** (`stock_news_search.py`): 将串行 `queries` 搜索重构为多线程并发检索，大幅缩短搜索等待延时。
10. **[腾讯行情接口连接池与 Keep-Alive 迁移]** (`quote_provider.py`): `TencentQuoteProvider` 迁移至 `http_pool` 共享 Client，支持 TCP Keep-Alive 复用。
11. **[美股带点 Symbol 格式标准化兼容]** (`quote_provider.py`): `normalize_symbol` 增加对美股带点代码（如 `BRK.A`, `BF.B`）的规范解析支持。
12. **[自选股数据库历史新闻索引友好匹配]** (`stock_news_search.py`): `sync_match_existing` 优化 SQL 查询，避免全表扫描。

### 🔒 三、 线程安全、连接池与资源回收 (3 项)
13. **[HTTP 连接池单例线程安全锁]** (`http_pool.py`): 增加 `threading.Lock` 双重检查锁，消除多线程并发创建 Client 时的竞态与泄漏。
14. **[Twitter API 限流器线程安全锁]** (`twitterapi_io_client.py`): `_wait_for_rate_limit` 增加类级别线程锁，防止并发计算限流间隔错乱。
15. **[Lifespan 退出全局 HTTP 连接池优雅回收]** (`http_pool.py`, `main.py`): 补齐所有单例客户端优雅关闭逻辑并在 `main.py` 退出时释放资源。

### 💾 四、 数据库、缓存与查询层性能优化 (5 项)
16. **[热门股票 hot_symbols 短 TTL 内存缓存]** (`quote_service.py`): `_get_hot_symbols` 3 表复杂 JOIN 增加 60s 内存缓存，降低 DB CPU 占用。
17. **[批量行情快照事务一次性 Commit 优化]** (`quote_service.py`): 批量刷新行情将逐条 commit 改为批处理单次提交，消除 SQLite 频繁磁盘 I/O 锁等待。
18. **[话题自动归类匹配批处理查询优化]** (`topic_service.py` / `news_signal_pipeline.py`): 优化批处理 SQL 查询，提升吞吐效率。
19. **[FTS5 全文检索触发器与同步防漏]** (`news_signal_repository.py`): 增加全文检索索引同步完整性防护。
20. **[大 A 股全量内存搜索拼音/代码匹配增强]** (`a_share_search_service.py`): 优化字母数字混排与大小写匹配分支，保持微秒级响应。

### 🛠️ 五、 错误日志与任务调度优化 (2 项)
21. **[抓取异常结构化上下文日志增强]** (`fetcher.py`, `persister.py`): 补充 Source Name / URL 上下文日志。
22. **[Scheduler 调度器防重复执行与任务退避]** (`news_ingest_scheduler.py`): 优化任务执行状态检查与退避机制。

---

## 验证方式
1. 单元测试与回归测试：`NEWS_CAUGHT_TEST_DB=/tmp/nc_opt_test.db conda run -n news-caught pytest backend/tests`
2. 同步更新 `docs/code-change-log.md` 与 `README.md`。
