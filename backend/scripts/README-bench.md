# 读路径性能基准 `bench_readpath.py`

把上一轮读路径优化的手测数字（`/topics` p50 25→8ms、SSE 负载下 2980→7ms、
正文爬取期间 588→265ms）固化成**可复现、可归档、可跨次对比**的基准，
避免下一次改动静默回归。

## 为什么必须用这个脚本，而不是自己手搓一段压测

两个真实踩过的坑，脚本已经把防护写死了：

| 坑 | 现象 | 脚本里的防线 |
| --- | --- | --- |
| **1. 压测客户端自己成了瓶颈** | 用 `ThreadPoolExecutor` + urllib 做 32 并发，baseline 和优化版 p50 一模一样（~600ms / ~2300ms），差点判定"优化无效"。真正饱和的是抢 GIL 的 Python 客户端。换 `ab` 后差异立刻显现（25→8ms、1197→3809 rps） | `detect_client()` 按 `ab → hey → wrk` 顺序探测外部原生客户端，全都没有才回退 Python，并在**终端输出和 JSON 结果里**都打上 `PYTHON_CLIENT_WARNING`；`--baseline` 对比时若两次客户端不同也会单独告警 |
| **2. 鉴权失败被误读成"性能很好"** | 基线服务跑在独立 worktree、有自己的 `data/.app_token`，用主仓库 token 打过去全部 401；401 返回极快，于是"基线看起来飞快"，据此错误结论"SSE 优化无效" | `preflight()` 在**任何测量之前**对每个 endpoint 各打一发并断言 2xx，401/403 立刻中止、进程退出码 2；测量期的非 2xx 也绝不进 p50/p95/max，只进 `error_count`，并把该行标记为 `latency_valid=false` |

SSE 场景的 60 条长连接同样是坑 1 的变体：连接由**独立的 `curl -sN` 子进程**持有，
绝不用 Python 线程；建立后还会读 `/health` 的 `active_stream_connections`
确认服务端真的看到了这些连接，看不到就中止（避免"连接全被 401 掉、读接口当然很快"）。

## 用法

```bash
# 1) 另开终端，用【临时库】起后端，并关掉所有会干扰测量的后台 worker
#    ⚠️ 绝对不要让被压测的后端指向 backend/data/app.db —— 压测会把上千条请求打进真实数据
DATABASE_URL="sqlite:////tmp/r2_bench.db" SEED_DEMO_DATA=true \
  NEWS_SCHEDULER_ENABLED=false MARKET_QUOTE_PRODUCER_ENABLED=false \
  X_MONITOR_ENABLED=false BACKUP_ENABLED=false DATA_CLEANUP_ENABLED=false \
  PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8991 --log-level warning

# 2) 跑基准并存档
python backend/scripts/bench_readpath.py --base-url http://127.0.0.1:8991/api \
    --scenario idle --scenario sse --json /tmp/bench_after.json

# 3) 改动之后再跑一遍，和上次比（有回归时退出码为 1）
python backend/scripts/bench_readpath.py --base-url http://127.0.0.1:8991/api \
    --scenario idle --scenario sse --json /tmp/bench_new.json \
    --baseline /tmp/bench_after.json
```

脚本**自己不会拉起后端**，也**不读写任何数据库**——只发 HTTP。

## 场景

- `idle`：空载下的读接口延迟（`/news?limit=200`、`/news/feed-layout`、`/news/runtime`、`/topics`、`/health`）
- `sse`：先用 `--sse-connections`（默认 60）条独立 curl 子进程持住 SSE，再测同一批读接口
- `crawl`：**可选场景，默认不可用**。后端没有暴露任何触发正文爬取的 HTTP 接口，
  而本脚本按设计不写数据库，所以无法自动稳定地制造这个负载。必须用
  `--crawl-command '<产生爬取负载的命令>'` 显式提供；不提供就直接报错退出，
  绝不用空跑的数字冒充"爬取期间的延迟"。

## 结果解读

- 分位数定义是**最近秩**（`p = 排序后第 ceil(p*n) 个`）；用外部客户端时直接取客户端
  自己算的分位（`ab -e` 导出的 CSV，毫秒带小数）。**客户端类型会写进 JSON 的 `client` 字段**，
  跨客户端的绝对数字不可直接比较。
- 单次运行的抖动实测在 10~20% 量级（尤其 `/health`，它本身有额外工作量）。
  `--regression-threshold` 默认 20；判定真回归前建议**同一份改动跑 2~3 次**，
  只有稳定复现的劣化才算数。
- `err > 0` 的行会带 `!! 含非 2xx 响应，延迟数字不可信` 备注——这行的延迟直接作废，
  不要拿来做结论。

## 测试

```bash
NEWS_CAUGHT_TEST_DB=/tmp/nc_bench.db conda run -n news-caught pytest backend/tests/test_bench_readpath.py -q
```

测试全部跑在纯函数 / 可注入接口上，不起服务、不发真实请求，重点锁死上面那两条防线。
