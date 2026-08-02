from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "News Caught Backend"
    environment: str = "development"
    api_prefix: str = "/api"
    log_level: str = "INFO"
    log_file_enabled: bool = True
    # 缺省为 backend/data/logs/backend.log（见 core/logging.py 的
    # _default_log_file_path）；data/ 已被 gitignore 覆盖。
    log_file_path: str | None = None
    log_file_max_bytes: int = 10 * 1024 * 1024
    log_file_backup_count: int = 5
    # plain：人类可读单行文本；json：单行 JSON（ts/level/logger/message）。
    log_format: str = "plain"
    database_url: str = Field(
        default=f"sqlite:///{Path(__file__).resolve().parents[2] / 'data' / 'app.db'}"
    )
    # ---------------------------------------------------------------------
    # 连接池与并发（2026-07-25 重构新增）
    # 此前 create_engine 未显式配置池，SQLAlchemy 对文件型 SQLite 默认
    # QueuePool(pool_size=5, max_overflow=10) —— 只有 15 条连接，却要同时服务
    # anyio 线程池里的全部同步路由 + 6 个后台 worker，池耗尽时请求会静默阻塞到
    # pool_timeout(默认 30s) 才报错，表现为“点一下几秒没反应”。
    # ---------------------------------------------------------------------
    db_pool_size: int = 20
    db_max_overflow: int = 30
    # 池满时的等待上限：宁可快速失败并让上层重试，也不要静默卡 30 秒。
    db_pool_timeout: float = 10.0
    db_pool_recycle: int = 1800
    # WAL 自动 checkpoint 页数（页大小 4KB → 2000 页 ≈ 8MB）。此前未设置，
    # 持续读连接会饿死 checkpoint，实测 app.db-wal 长到 6.3MB 与主库同量级，
    # 每次读都要先扫 WAL index，形成全局读放大。
    sqlite_wal_autocheckpoint_pages: int = 2000
    # FastAPI 同步(def)路由与 anyio.to_thread 共享的线程池上限，默认 40。
    # 本项目几乎所有路由都是 def，SSE 连接此前还会常驻占用线程，40 很容易被吃满。
    server_threadpool_size: int = 128

    stream_mode: str = "sse"
    # SSE 单连接事件队列上限：此前无界，慢客户端会无限堆积。
    stream_queue_maxsize: int = 500
    stream_keepalive_seconds: float = 15.0
    event_bus_backend: str = "hybrid"
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_stream_news_ingested: str = "stream:news:ingested"
    redis_stream_news_processed: str = "stream:news:processed"
    redis_stream_market_watchlist: str = "stream:market:watchlist"
    redis_stream_maxlen: int = 1000
    event_bus_publish_timeout_seconds: float = 1.0
    ai_enabled: bool = False
    http_timeout_seconds: float = 10.0
    llm_timeout_seconds: float = 60.0
    # LLM 请求遇到瞬态错误（httpx 超时/网络错误、429、5xx）时，在切换 backup provider
    # 之前对同一 provider 做的有限次重试：指数退避 llm_retry_backoff_seconds * 2**attempt
    # + 抖动。除 429 外的其余 4xx 判定为不可重试，直接进入既有的单次 failover 判定。
    # 该值是“初始尝试之外”的额外重试次数：设为 N 时同一 provider 最多总共尝试 N+1
    # 次（1 次初始 + N 次重试）；failover 后接手的 backup provider 不复用这个预算，
    # 只做单次尝试。
    llm_retry_max_attempts: int = 2
    llm_retry_backoff_seconds: float = 0.5
    takeaway_batch_limit: int = 12
    takeaway_daily_limit: int = 300
    takeaway_poll_interval_seconds: float = 5.0
    # TakeawayWorker 的 DB 兜底扫描间隔（秒）；<= 0 表示关闭。
    # `takeaway_queue` 由 feed layout 填充，而 feed layout 只在 **web 进程的请求
    # 线程** 里执行。多进程形态下 TakeawayWorker 搬到独立进程后，那个队列在本进程
    # 永远是空的，所以需要一条与 queue_worker 同形的 DB 兜底扫描来自愈。
    # 默认 0 = 关闭：单进程形态保持既有语义（只补齐 feed layout 精选出的高分条目），
    # 独立入口 `app.workers.pipeline_worker_main` 会显式打开它。
    takeaway_fallback_scan_interval_seconds: float = 0.0
    news_sources_file: str | None = None
    news_scheduler_enabled: bool = False
    news_scheduler_tick_seconds: float = 5.0
    news_backoff_max_multiplier: int = 8
    # ---------------------------------------------------------------------
    # 抓取并发与超时（2026-07-25 重构：此前全部是散落在各模块的硬编码常量）
    # ---------------------------------------------------------------------
    news_fetch_max_workers: int = 16
    news_crawl_max_workers: int = 8
    # 正文「解析」并发上限，刻意远小于上面的「抓取」并发（news_crawl_max_workers）。
    # 两者度量的是完全不同的资源：
    #   * 抓取阶段是网络等待，httpx 在 socket 上阻塞时会释放 GIL，8 并发有真实收益；
    #   * 解析阶段（BeautifulSoup + decompose + select_one/find_all + get_text）
    #     是纯 CPU 且全程持有 GIL —— 本环境未装 lxml，BeautifulSoup 退回纯 Python
    #     的 html.parser，实测 cpu/wall ≈ 1.00，即解析期间 GIL 一刻也不释放。
    # 8 个线程同时解析几百 KB 的 HTML 会把 uvicorn 事件循环和 anyio 请求线程一起
    # 饿死。端到端实测（120 条 540KB 页面，探测 /api/news/runtime）：
    #   改造前(8 并发解析 + 逐个 select_one)  爬完 72.4s  p50 588ms  p95 1197ms
    #   本值=2                                爬完 23.6s  p50 265ms  p95  425ms
    #   本值=1                                爬完 25.7s  p50 156ms  p95  300ms
    # 默认取 2 而不是 1：单槽位没有任何冗余，一个慢页面会把整批解析堵在队头；
    # 2 既保住了头阻塞的缓冲，又把点击延迟压下来一个量级。对点击延迟特别敏感的
    # 部署可以把它设成 1，代价是批次耗时约 +9%。
    news_crawl_parse_concurrency: int = 2
    # 单个页面进入解析前的最大字符数（按解码后的字符计，解析开销与文档规模近似线性）。
    # 个别超大页面（日志页 / 聚合页 / 无限滚动快照）会长时间独占解析槽位拖垮整批，
    # 超出即截断后再解析，而不是整条失败。<= 0 表示不限制。
    news_crawl_max_html_chars: int = 1_000_000
    news_classify_max_workers: int = 4
    news_signal_backlog_batch_size: int = 50
    # 正文抓取超时（此前 article_crawler 内硬编码 15.0）。
    crawl_timeout_seconds: float = 15.0
    # 单独收紧建连超时：httpx 的标量 timeout 会同时用于 connect/read/write/pool，
    # 导致慢连接叠加慢读取时单请求实际耗时可达 timeout 的数倍。
    http_connect_timeout_seconds: float = 5.0
    # 进程重启后所有源的 next_due 同时为 0 会形成惊群，用抖动打散首轮。
    news_scheduler_startup_jitter_seconds: float = 8.0
    queue_worker_poll_interval_seconds: float = 1.0
    queue_worker_fallback_scan_interval_seconds: float = 30.0
    # ---------------------------------------------------------------------
    # 后台重活 worker 的「进程归属」开关（多进程拆分）
    # ---------------------------------------------------------------------
    # True（默认，README 推荐的单机单进程形态）：
    #   BackgroundQueueWorker / TakeawayWorker / XHealthProbeWorker 随 uvicorn 的
    #   lifespan 一起启停，行为与拆分前完全一致。
    # False（多进程形态）：
    #   web 进程不再启动这三个 worker，改由独立入口
    #   `python -m app.workers.pipeline_worker_main` 承载。正文爬取 + BeautifulSoup
    #   解析是纯 CPU 且全程持 GIL 的工作，搬走之后才真正不再和请求线程抢 GIL
    #   （实测爬取活跃期 /api/news/runtime 的 p50 残余 265ms 即源于此）。
    #
    # 两种形态必须二选一：in-flight 租约（queue_worker.analysis_inflight）是
    # **进程内内存**，两个进程各跑一个 BackgroundQueueWorker 时租约互不可见，
    # 同一批 news_id 会被重复爬正文 + 重复调 LLM。因此独立入口默认会在检测到
    # 本开关仍为 true 时直接拒绝启动（见 pipeline_worker_main.ensure_exclusive_ownership）。
    pipeline_workers_enabled: bool = True
    # 多进程形态下，web 进程里那两个「没有消费者的进程内队列」
    # （analysis_queue / takeaway_queue）的回收间隔（秒）；<= 0 表示不回收。
    # scheduler 与 feed layout 仍在 web 进程里往它们塞数据，不回收就是慢性内存泄漏。
    orphan_queue_drain_interval_seconds: float = 60.0
    # 被 BackgroundQueueWorker 领取但尚未写回 signal_status 的新闻，在该租约时间内
    # 不再被 scheduler 重复投递（此前每 5s 重投一次，造成重复爬正文 + 双倍 LLM）。
    news_inflight_lease_seconds: float = 600.0
    # 手动 POST /news/refresh 的服务端冷却（秒）；0 = 关闭。默认 60 对齐前端节流。
    news_refresh_cooldown_seconds: float = 60.0
    x_monitor_enabled: bool = False
    x_monitor_accounts_file: str | None = None
    twitterapi_io_api_key: str | None = None
    twitterapi_io_timeout_seconds: float = 60.0
    # twitterapi.io 请求最小间隔(秒):账号间逐个请求,由 TwitterApiIoClient
    # ._wait_for_rate_limit 按此间隔 sleep;默认 1.0 避免多账号轮询打满限流。
    twitterapi_io_min_interval_seconds: float = 1.0
    x_monitor_refresh_cooldown_hours: int = 3
    x_radar_rules_file: str | None = None
    market_quote_provider: str = "yahoo_finance"
    market_quote_cache_ttl_seconds: int = 180
    # 财报/事件日历缓存 TTL：yfinance 日历调用慢，默认 6 小时。
    calendar_cache_ttl_seconds: int = 21600
    # 单机单进程默认形态:producer 随后端 lifespan 一起启停(见 app/main.py)。
    # 需要独立进程跑 producer（多进程部署）时,把该开关关掉,避免进程内/进程外
    # 双跑重复轮询;独立入口见 app.workers.market_quote_producer。
    market_quote_producer_enabled: bool = True
    market_quote_poll_interval_seconds: float = 15.0
    # 全市场（A股/港股/美股）都闭市时 producer 的降频间隔。盘中按
    # market_quote_poll_interval_seconds 走；闭市时价格不再变动，继续按 15s
    # 打 provider 纯属浪费配额，还会拖高被限流的概率。
    market_quote_idle_poll_interval_seconds: float = 120.0
    # 强制刷新（producer 轮询 / 手动 /market/refresh）的抓取下限。
    # market_quote_cache_ttl_seconds(180s) 是**读路径**的陈旧度阈值，用它当抓取
    # 门槛会让 15s 的轮询里 11 次空转、真实价格 3 分钟才更新一次。强制刷新改用
    # 这个更小的下限，既保证实时性，又能挡住刷新按钮被连点时的重复外网调用。
    market_quote_force_min_interval_seconds: float = 5.0
    tavily_api_key: str | None = None
    stock_news_min_count: int = 3
    data_cleanup_enabled: bool = True
    data_cleanup_interval_seconds: float = 86400.0
    data_cleanup_vacuum_interval_seconds: float = 604800.0
    news_item_retention_days: int = 180
    article_content_retention_days: int = 90
    price_snapshot_retention_days: int = 30
    # llm_token_usage 每次 LLM 调用一行、llm_classification_cache 无过期,两表无界
    # 增长,是撑爆 SQLite 文件的主要来源,需纳入定期清理。
    llm_token_usage_retention_days: int = 90
    llm_classification_cache_retention_days: int = 30
    # 删除前归档：保留期清理执行 DELETE 之前，把待删行落一份 JSON Lines 归档文件，
    # 便于事后追溯/人工恢复。目录缺省为 backend/data/archive。
    data_archive_dir: str | None = None
    # SQLite 定时备份：使用 sqlite3.Connection.backup() 在线备份 API，避免直接复制
    # 写入中的文件；目录缺省为 backend/data/backups，只保留最近 N 份。
    backup_enabled: bool = True
    backup_interval_seconds: float = 86400.0
    backup_retention_count: int = 7
    backup_dir: str | None = None
    dedup_secondary_judge: str | None = None
    # 情绪/利好利空评测金标集路径；缺省时用 backend/data/research 内置金标。
    sentiment_eval_dataset_file: str | None = None
    # Seed demo/example data (watchlist, news, X posts...) into an empty database
    # at startup. Defaults to True so local dev (scripts/dev.sh) and the test
    # suite keep their out-of-the-box demo experience; set SEED_DEMO_DATA=false
    # in production. Standalone seeding: `python scripts/seed_demo_data.py`.
    seed_demo_data: bool = True
    # Require X-App-Token verification on protected API routes. The test suite
    # disables this globally in backend/tests/conftest.py (VERIFY_APP_TOKEN=false)
    # instead of relying on runtime pytest detection.
    verify_app_token: bool = True
    # Enable the in-process TTL caches on read-heavy news routes. Disabled by
    # the test suite (ROUTE_CACHE_ENABLED=false) except in dedicated cache tests.
    route_cache_enabled: bool = True
    # SimpleTTLCache 容量上限（此前是裸 dict，无锁、无上限、无淘汰，feed-layout
    # 的 key 含 4 个查询参数，可被任意 URL 撑爆内存）。
    route_cache_max_entries: int = 512
    # 事件详情路由此前完全无缓存，而它正是“点事件卡片”的路径。
    event_detail_cache_ttl_seconds: float = 15.0
    # 行情图表/日历等外部数据抓取的并发度（此前 sparklines 在请求线程里串行
    # 逐个 yf.download，30 个标的最坏 300s）。
    market_chart_max_workers: int = 8
    # Token usage buffer batching: flush to DB every N rows or after this many
    # seconds. Tests set TOKEN_USAGE_FLUSH_N=1 for synchronous persistence.
    token_usage_flush_n: int = 50
    token_usage_flush_secs: float = 10.0
    # 每日盘前/盘后 AI 简报（Daily Digest）：定时用 LLM 生成结构化简报并推送。
    # digest_enabled 默认关闭，避免未配置 LLM/飞书的环境无谓触发；开启后由
    # DigestWorker 按各市场本地时区在盘前/盘后时点生成推送。
    digest_enabled: bool = False
    digest_premarket_time: str = "08:30"
    digest_postmarket_time: str = "16:30"
    digest_lookback_hours: int = 16
    # Reuse a cached classification result when the same (normalized) content is
    # classified again, skipping the LLM call and token accounting entirely.
    # Tests toggle this to assert both cached and uncached behavior.
    llm_classification_cache_enabled: bool = True

    # ---------------------------------------------------------------------
    # 告警治理（去重 / 免打扰 / 分级 / 合并摘要）——全部默认保守（关闭），
    # 不配置时行为与旧版一致，避免惊到既有测试。前端可在通知设置页覆盖，
    # 覆盖值只保存在 NotificationService 内存里（不落库、无迁移）。
    # ---------------------------------------------------------------------
    # 免打扰时段，"HH:MM" 24 小时制；start/end 任一为空即视为未启用。
    notify_quiet_hours_start: str | None = None
    notify_quiet_hours_end: str | None = None
    # 免打扰时段判定所用时区（复用 zoneinfo）。
    notify_quiet_hours_tz: str = "Asia/Shanghai"
    # 同 symbol / 同事件在 N 分钟窗口内只发一次；0 = 关闭去重窗口。
    notify_dedupe_window_minutes: int = 0
    # 合并摘要窗口：非 critical 告警先暂存 N 分钟再合并；0 = 关闭合并。
    notify_digest_window_minutes: int = 0
    # 合并阈值：窗口内累计达到该条数才合并成摘要，否则逐条发送。
    notify_digest_threshold: int = 3
    # 自选股异动升级为 critical 的涨跌幅绝对值阈值（%）。
    notify_critical_change_percent: float = 8.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
