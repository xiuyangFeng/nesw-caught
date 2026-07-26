"""读路径性能基准脚本（把第二轮优化的手测数字固化成可复现基准）。

背景
----
上一轮读路径重构（SSE 改纯 asyncio、路由 TTL 缓存、feed-layout 下推 SQL 等）
的性能收益全是**一次性手工测量**得到的：`/topics` p50 25→8ms、SSE 负载下点击
延迟 2980→7ms、正文爬取期间 p50 588→265ms。这些数字没有留下任何可复现脚本，
下一个人改动读路径时不会有任何信号，静默回归是必然的。本脚本负责补上这一环。

两个必须被脚本固化防住的坑（都是上一轮真实踩过的）
--------------------------------------------------
**坑 1：Python 压测客户端会被自己的 GIL 卡住，掩盖服务端的优化。**
最早用 `ThreadPoolExecutor` + urllib 做 32 并发压测，baseline 与优化版看起来
一模一样（p50 都是 ~600ms / ~2300ms），差点得出"优化无效"的结论。真正的瓶颈
在压测客户端自己：32 个 Python 线程抢一把 GIL，客户端先于服务端饱和，测出来
的是客户端的天花板。换成原生 C 客户端 `ab` 之后差异立刻显现（`/topics`
25→8ms、吞吐 1197→3809 rps）。
→ 防护：`detect_client()` **优先探测外部 C 压测客户端**（ab / hey / wrk，按此
  顺序），只有全都不可用时才回退到 Python 客户端；一旦回退，报告与 JSON 结果里
  都会带上 `PYTHON_CLIENT_WARNING` 这条显著警告，并把 `client="python"` 写进
  结果，跨次对比时客户端不一致也会单独提示。

**坑 2：鉴权失败导致"零负载"被误读成"性能很好"。**
对比基线时，基线服务跑在独立 git worktree 里，它有自己的 `data/.app_token`，
和主仓库的不一样。用主仓库 token 打过去全部 401 被拒——于是基线"看起来飞快"，
其实压根没有产生任何负载，据此一度得出"SSE 优化无效"的错误结论。
→ 防护：`preflight()` 在**任何正式测量之前**对每个目标 endpoint 各发一个请求，
  断言状态码是 2xx；出现 401/403 立刻 `AuthPreflightError` 中止，进程以非零码
  退出，绝不允许把失败请求算成"很快"。其它非 2xx 同样中止。测量阶段的非 2xx
  响应也绝不计入延迟统计，而是单独计数并在报告里显示（见 `summarize()` 与
  `LatencyStats.latency_valid`）。

安全
----
本脚本**只发 HTTP 请求，不碰任何数据库**，也不会自己拉起后端。但被压测的那个
后端会真的写库，所以**务必用临时库起服务**，绝不要指向 `backend/data/app.db`：
压测会把几百上千条请求打进你的真实数据。推荐启动命令见 `--help` 结尾。

用法
----
    # 1) 另开一个终端，用临时库 + 关掉所有会干扰测量的后台 worker 起后端
    DATABASE_URL="sqlite:////tmp/r2_bench.db" SEED_DEMO_DATA=true \
      NEWS_SCHEDULER_ENABLED=false MARKET_QUOTE_PRODUCER_ENABLED=false \
      X_MONITOR_ENABLED=false BACKUP_ENABLED=false DATA_CLEANUP_ENABLED=false \
      PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8991 --log-level warning

    # 2) 跑基准并存档
    python backend/scripts/bench_readpath.py --base-url http://127.0.0.1:8991/api \
        --scenario idle --scenario sse --json /tmp/bench_after.json

    # 3) 下次改动后再跑一遍，和上次比
    python backend/scripts/bench_readpath.py --base-url http://127.0.0.1:8991/api \
        --scenario idle --scenario sse --json /tmp/bench_new.json \
        --baseline /tmp/bench_after.json
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TOKEN_FILE = REPO_ROOT / "data" / ".app_token"
DEFAULT_BASE_URL = "http://127.0.0.1:8000/api"

# 探测顺序即偏好顺序：三个都是原生（C/Go）客户端，不受 Python GIL 影响。
EXTERNAL_CLIENTS: tuple[str, ...] = ("ab", "hey", "wrk")
PYTHON_CLIENT = "python"

# 坑 1 的显著警告。测试会断言这个标记出现在回退时的输出里，改文案请同步改测试。
PYTHON_CLIENT_WARNING = (
    "[WARNING] 正在使用 Python 压测客户端（未找到 ab / hey / wrk，或被 --client python 显式指定）。"
    "Python 客户端受 GIL 限制，高并发下客户端自己就会先饱和、成为瓶颈，"
    "从而掩盖服务端的真实差异——数字仅供参考，不可作为优化有效性的依据，"
    "也不要与外部客户端跑出来的结果直接对比。"
)

# p50 劣化超过这个百分比就在对比模式里标记为回归。
REGRESSION_THRESHOLD_PCT = 20.0

SCENARIOS: tuple[str, ...] = ("idle", "sse", "crawl")

# 被测的只读接口。名字用于 JSON 结果与跨次对比的对齐键，不要随意改。
READ_ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("news_list", "/news?limit=200"),
    ("feed_layout", "/news/feed-layout"),
    ("news_runtime", "/news/runtime"),
    ("topics", "/topics"),
    ("health", "/health"),
)

SSE_PATH = "/stream/events"

# crawl 场景无法由本脚本安全触发的说明（见 build_crawl_load_command 的注释）。
CRAWL_UNAVAILABLE_HINT = (
    "crawl 场景需要后端正文爬取正在活跃运行，但当前后端【没有暴露任何触发正文爬取的 HTTP 接口】，"
    "而本脚本按设计只发 HTTP、不写数据库（避免误伤真实库）。因此 crawl 是**可选场景**，"
    "必须通过 --crawl-command 显式提供一条产生爬取负载的外部命令，例如一个往临时库塞待爬新闻并跑 pipeline 的脚本。"
    "不提供就直接报错退出，绝不用空跑的数字冒充『爬取期间的延迟』。"
)


class BenchError(RuntimeError):
    """基准脚本的通用错误：一律以非零码退出，绝不降级成"看起来很快"。"""


class AuthPreflightError(BenchError):
    """坑 2 专用：预检时被 401/403 拒绝，说明 token 不匹配，测量必须中止。"""


# --------------------------------------------------------------------------- #
# 数据结构
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Sample:
    """单次 HTTP 请求的结果。`status` 为 0 表示连接层面就失败了（超时/拒绝连接）。"""

    status: int
    elapsed_ms: float


@dataclass
class LatencyStats:
    """一个 endpoint 一轮压测的统计结果。

    `error_count` 与延迟分位数是**分开**的：非 2xx 响应绝不进入 p50/p95/max
    （坑 2）。外部客户端（ab/hey/wrk）自己算的分位数没法把非 2xx 剔出去，所以
    只要 `error_count > 0` 就把 `latency_valid` 置 False，报告里显式标注该行的
    延迟数字不可信，而不是假装它是干净的。
    """

    count: int = 0
    error_count: int = 0
    p50_ms: float | None = None
    p95_ms: float | None = None
    max_ms: float | None = None
    rps: float | None = None
    latency_valid: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "count": self.count,
            "error_count": self.error_count,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "max_ms": self.max_ms,
            "rps": self.rps,
            "latency_valid": self.latency_valid,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> LatencyStats:
        return cls(
            count=int(payload.get("count") or 0),
            error_count=int(payload.get("error_count") or 0),
            p50_ms=_as_float(payload.get("p50_ms")),
            p95_ms=_as_float(payload.get("p95_ms")),
            max_ms=_as_float(payload.get("max_ms")),
            rps=_as_float(payload.get("rps")),
            latency_valid=bool(payload.get("latency_valid", True)),
        )


@dataclass
class ScenarioResult:
    name: str
    params: dict[str, object] = field(default_factory=dict)
    endpoints: dict[str, LatencyStats] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "params": self.params,
            "endpoints": {name: stats.to_dict() for name, stats in self.endpoints.items()},
        }


@dataclass
class BenchReport:
    base_url: str
    client: str
    client_warning: str | None
    requests: int
    concurrency: int
    started_at: str
    scenarios: list[ScenarioResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "base_url": self.base_url,
            "client": self.client,
            "client_warning": self.client_warning,
            "requests": self.requests,
            "concurrency": self.concurrency,
            "started_at": self.started_at,
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
        }


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# 统计
# --------------------------------------------------------------------------- #


def percentile(values: Sequence[float], q: float) -> float | None:
    """最近秩（nearest-rank）分位数：p 分位取排序后第 ceil(p * n) 个元素。

    空序列返回 None（不返回 0——0ms 会被误读成"快到飞起"，正是坑 2 的形态）。
    单元素序列所有分位数都等于该元素。
    """
    if not values:
        return None
    if not 0.0 < q <= 1.0:
        raise ValueError(f"分位数 q 必须落在 (0, 1] 区间，收到 {q}")
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return float(ordered[rank - 1])


def summarize(samples: Sequence[Sample], wall_seconds: float | None = None) -> LatencyStats:
    """把一批请求样本折算成统计量。

    **坑 2 的核心防线**：只有 2xx 的样本进入 p50/p95/max；非 2xx（含连接失败的
    status=0）只进 `error_count`。否则一个全 401 的目标会因为 401 返回得飞快，
    在报告里显示成"性能极佳"。
    """
    ok = [sample.elapsed_ms for sample in samples if is_success(sample.status)]
    errors = sum(1 for sample in samples if not is_success(sample.status))
    rps: float | None = None
    if wall_seconds and wall_seconds > 0:
        rps = round(len(ok) / wall_seconds, 2)
    return LatencyStats(
        count=len(ok),
        error_count=errors,
        p50_ms=_round_ms(percentile(ok, 0.50)),
        p95_ms=_round_ms(percentile(ok, 0.95)),
        max_ms=_round_ms(max(ok)) if ok else None,
        rps=rps,
        latency_valid=errors == 0,
    )


def is_success(status: int) -> bool:
    return 200 <= status < 300


def _round_ms(value: float | None) -> float | None:
    return None if value is None else round(float(value), 3)


# --------------------------------------------------------------------------- #
# 客户端探测（坑 1）
# --------------------------------------------------------------------------- #


def detect_client(
    preferred: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> str:
    """选择压测客户端。

    `which` 做成参数是为了让测试能模拟"三个外部客户端都不存在"的机器，从而断言
    回退路径与警告标记（坑 1）。
    """
    if preferred and preferred != "auto":
        if preferred == PYTHON_CLIENT:
            return PYTHON_CLIENT
        if preferred not in EXTERNAL_CLIENTS:
            raise BenchError(f"未知的压测客户端：{preferred}（可选 {'/'.join(EXTERNAL_CLIENTS)}/python/auto）")
        if which(preferred) is None:
            raise BenchError(f"指定的压测客户端 {preferred} 不在 PATH 上")
        return preferred

    for name in EXTERNAL_CLIENTS:
        if which(name) is not None:
            return name
    return PYTHON_CLIENT


def client_warning_for(client: str) -> str | None:
    """回退到 Python 客户端时返回坑 1 的警告文案，否则返回 None。"""
    return PYTHON_CLIENT_WARNING if client == PYTHON_CLIENT else None


# --------------------------------------------------------------------------- #
# HTTP 基元
# --------------------------------------------------------------------------- #


def http_probe(url: str, headers: dict[str, str], timeout: float = 10.0) -> Sample:
    """发一个请求并返回 (状态码, 耗时)。任何异常都折算成一个非 2xx 样本。"""
    request = urllib.request.Request(url, headers=headers, method="GET")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            response.read()
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        try:
            exc.read()
        except Exception:
            pass
    except Exception:
        # 连接被拒 / 超时 / DNS 失败：用 0 表示"根本没拿到 HTTP 状态码"。
        status = 0
    return Sample(status=status, elapsed_ms=(time.perf_counter() - started) * 1000.0)


# --------------------------------------------------------------------------- #
# 鉴权预检（坑 2）
# --------------------------------------------------------------------------- #


def preflight(
    urls: Sequence[str],
    probe: Callable[[str], Sample],
) -> list[Sample]:
    """正式测量前对每个 endpoint 各打一发，确认真的能产生负载。

    - 401/403 → `AuthPreflightError`：这正是"基线 worktree 有自己的 .app_token、
      拿主仓库 token 打过去全被拒、于是基线看起来飞快"那个坑。
    - 其它非 2xx / 连接失败 → `BenchError`：同样中止，不允许拿失败请求当数据。
    """
    samples: list[Sample] = []
    for url in urls:
        sample = probe(url)
        samples.append(sample)
        if sample.status in (401, 403):
            raise AuthPreflightError(
                f"鉴权预检失败：{url} 返回 {sample.status}。"
                "这说明使用的 App Token 与目标服务不匹配（典型场景：基线服务跑在独立 worktree 里，"
                "有自己的 data/.app_token）。若继续测量，全部请求都会被拒，"
                "而被拒的请求返回极快，会把『零负载』误读成『性能极佳』——所以这里直接中止。"
                f"请用 --token 显式指定目标服务的 token，或确认 {DEFAULT_TOKEN_FILE} 属于目标服务。"
            )
        if sample.status == 0:
            raise BenchError(f"鉴权预检失败：{url} 无法建立连接，请确认后端已在 --base-url 上运行。")
        if not is_success(sample.status):
            raise BenchError(f"鉴权预检失败：{url} 返回 {sample.status}（期望 2xx），测量中止。")
    return samples


# --------------------------------------------------------------------------- #
# 压测执行器
# --------------------------------------------------------------------------- #


def run_python_load(
    url: str,
    headers: dict[str, str],
    requests: int,
    concurrency: int,
    probe: Callable[[str], Sample] | None = None,
) -> LatencyStats:
    """Python 回退客户端（坑 1 的受害者本人）。

    保留它只是为了在没装 ab/hey/wrk 的机器上仍能跑出**相对**趋势，输出必定带
    `PYTHON_CLIENT_WARNING`。绝不要拿它的绝对数字下"优化有效/无效"的结论。
    """
    call = probe or (lambda target: http_probe(target, headers))
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        samples = list(pool.map(lambda _: call(url), range(requests)))
    return summarize(samples, wall_seconds=time.perf_counter() - started)


def _run_command(cmd: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        list(cmd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def parse_ab_output(stdout: str, csv_text: str | None) -> LatencyStats:
    """解析 ApacheBench 输出。

    分位数优先取 `-e` 导出的 CSV（毫秒带小数，对 5-10ms 量级的接口精度足够），
    CSV 不可用时退回 stdout 里那张整数分位表。
    """
    complete = _grep_int(stdout, "Complete requests:")
    failed = _grep_int(stdout, "Failed requests:") or 0
    non_2xx = _grep_int(stdout, "Non-2xx responses:") or 0
    rps = _grep_float(stdout, "Requests per second:")

    percentiles: dict[int, float] = {}
    if csv_text:
        for line in csv_text.splitlines()[1:]:
            parts = line.split(",")
            if len(parts) < 2:
                continue
            try:
                percentiles[int(float(parts[0]))] = float(parts[1])
            except ValueError:
                continue
    if not percentiles:
        for line in stdout.splitlines():
            stripped = line.strip()
            if stripped.endswith("(longest request)"):
                stripped = stripped.replace("(longest request)", "").strip()
            parts = stripped.replace("%", "").split()
            if len(parts) == 2:
                try:
                    percentiles[int(parts[0])] = float(parts[1])
                except ValueError:
                    continue

    errors = failed + non_2xx
    ok_count = max(0, (complete or 0) - errors)
    return LatencyStats(
        count=ok_count,
        error_count=errors,
        p50_ms=_round_ms(percentiles.get(50)),
        p95_ms=_round_ms(percentiles.get(95)),
        max_ms=_round_ms(percentiles.get(100)),
        rps=rps,
        # ab 自己算的分位数把非 2xx 也算进去了，没法事后剔除；有错误就直接判定
        # 这行延迟不可信（坑 2：绝不让失败请求混进"很快"的数字里）。
        latency_valid=errors == 0,
    )


def parse_hey_output(stdout: str) -> LatencyStats:
    """解析 hey 的文本输出（`Latency distribution` + `Status code distribution`）。"""
    rps = _grep_float(stdout, "Requests/sec:")
    percentiles: dict[int, float] = {}
    max_ms: float | None = None
    ok_count = 0
    errors = 0
    in_status = False
    for raw in stdout.splitlines():
        line = raw.strip()
        if line.startswith("Slowest:"):
            slowest = _grep_float(line, "Slowest:")
            max_ms = None if slowest is None else slowest * 1000.0
        if " in " in line and line.endswith("secs") and line[:1].isdigit():
            head, _, tail = line.partition(" in ")
            try:
                pct = int(head.replace("%", "").strip())
                percentiles[pct] = float(tail.replace("secs", "").strip()) * 1000.0
            except ValueError:
                continue
        if line.startswith("Status code distribution"):
            in_status = True
            continue
        if in_status and line.startswith("["):
            code_text, _, rest = line.partition("]")
            try:
                code = int(code_text.strip("[ "))
                amount = int(rest.strip().split()[0])
            except (ValueError, IndexError):
                continue
            if is_success(code):
                ok_count += amount
            else:
                errors += amount
    return LatencyStats(
        count=ok_count,
        error_count=errors,
        p50_ms=_round_ms(percentiles.get(50)),
        p95_ms=_round_ms(percentiles.get(95)),
        max_ms=_round_ms(max_ms),
        rps=rps,
        latency_valid=errors == 0,
    )


def parse_wrk_output(stdout: str) -> LatencyStats:
    """解析 wrk `--latency` 的输出。"""
    rps = _grep_float(stdout, "Requests/sec:")
    non_2xx = _grep_int(stdout, "Non-2xx or 3xx responses:") or 0
    total = 0
    for line in stdout.splitlines():
        stripped = line.strip()
        if " requests in " in stripped:
            try:
                total = int(stripped.split()[0])
            except (ValueError, IndexError):
                total = 0
    percentiles: dict[int, float] = {}
    for raw in stdout.splitlines():
        parts = raw.strip().split()
        if len(parts) == 2 and parts[0].endswith("%"):
            try:
                percentiles[int(parts[0].rstrip("%"))] = _duration_to_ms(parts[1])
            except ValueError:
                continue
    return LatencyStats(
        count=max(0, total - non_2xx),
        error_count=non_2xx,
        p50_ms=_round_ms(percentiles.get(50)),
        p95_ms=_round_ms(percentiles.get(95)),
        max_ms=_round_ms(percentiles.get(99)),
        rps=rps,
        latency_valid=non_2xx == 0,
    )


def _duration_to_ms(text: str) -> float:
    value = text.strip()
    for suffix, factor in (("us", 0.001), ("ms", 1.0), ("s", 1000.0), ("m", 60000.0)):
        if value.endswith(suffix):
            return float(value[: -len(suffix)]) * factor
    return float(value)


def _grep_int(text: str, label: str) -> int | None:
    value = _grep_float(text, label)
    return None if value is None else int(value)


def _grep_float(text: str, label: str) -> float | None:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(label):
            continue
        rest = stripped[len(label):].strip()
        token = rest.split()[0] if rest.split() else ""
        token = token.rstrip("s").replace("[", "").replace(",", "")
        try:
            return float(token)
        except ValueError:
            continue
    return None


def run_external_load(
    client: str,
    url: str,
    headers: dict[str, str],
    requests: int,
    concurrency: int,
    duration_seconds: int,
    tmp_dir: Path,
    runner: Callable[[Sequence[str], float], subprocess.CompletedProcess[str]] = _run_command,
) -> LatencyStats:
    """用外部原生客户端压测（坑 1 的解药）。"""
    header_args: list[str] = []
    timeout = max(60.0, duration_seconds * 3.0)

    if client == "ab":
        csv_path = tmp_dir / "ab_percentiles.csv"
        for key, value in headers.items():
            header_args += ["-H", f"{key}: {value}"]
        # -l：接受可变长度响应（动态页面必须加，否则 ab 把长度不一致算成 Failed）
        # -k：复用连接，避免测出来的是 TCP 握手成本
        cmd = ["ab", "-n", str(requests), "-c", str(concurrency), "-l", "-k", "-q", "-S",
               "-e", str(csv_path), *header_args, url]
        proc = runner(cmd, timeout)
        csv_text = csv_path.read_text(encoding="utf-8") if csv_path.exists() else None
        if proc.returncode != 0 and "Requests per second" not in proc.stdout:
            raise BenchError(f"ab 执行失败（returncode={proc.returncode}）：{proc.stderr.strip()[:400]}")
        return parse_ab_output(proc.stdout, csv_text)

    if client == "hey":
        for key, value in headers.items():
            header_args += ["-H", f"{key}: {value}"]
        cmd = ["hey", "-n", str(requests), "-c", str(concurrency), *header_args, url]
        proc = runner(cmd, timeout)
        if proc.returncode != 0 and "Requests/sec" not in proc.stdout:
            raise BenchError(f"hey 执行失败（returncode={proc.returncode}）：{proc.stderr.strip()[:400]}")
        return parse_hey_output(proc.stdout)

    if client == "wrk":
        for key, value in headers.items():
            header_args += ["-H", f"{key}: {value}"]
        cmd = ["wrk", "-t", str(min(concurrency, 8)), "-c", str(concurrency),
               "-d", f"{duration_seconds}s", "--latency", *header_args, url]
        proc = runner(cmd, timeout)
        if proc.returncode != 0 and "Requests/sec" not in proc.stdout:
            raise BenchError(f"wrk 执行失败（returncode={proc.returncode}）：{proc.stderr.strip()[:400]}")
        return parse_wrk_output(proc.stdout)

    raise BenchError(f"不支持的外部压测客户端：{client}")


# --------------------------------------------------------------------------- #
# SSE 连接池（必须是独立进程，不是线程 —— 又一次的坑 1）
# --------------------------------------------------------------------------- #


def default_sse_spawner(url: str, headers: dict[str, str], max_seconds: int) -> subprocess.Popen[bytes]:
    """用 `curl -sN` 子进程持有一条 SSE 长连接。

    **绝不能用 Python 线程持有这些连接**：60 条 SSE 长连接如果跑在压测机的
    Python 进程里，它们自己就会把 GIL 和 socket 读循环占满，测出来的"读接口
    延迟"里混着客户端自身的调度延迟——正是坑 1 的另一种形态。每条连接一个独立
    的 curl 进程，由操作系统调度，和压测客户端彻底解耦。
    """
    header_args: list[str] = []
    for key, value in headers.items():
        header_args += ["-H", f"{key}: {value}"]
    cmd = ["curl", "-sN", "--max-time", str(max_seconds), *header_args, url]
    return subprocess.Popen(  # noqa: S603
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class SseConnectionPool:
    """持有 N 条 SSE 连接的上下文管理器；`spawner` 可注入以便测试。"""

    def __init__(
        self,
        url: str,
        headers: dict[str, str],
        count: int,
        max_seconds: int = 600,
        spawner: Callable[[str, dict[str, str], int], subprocess.Popen[bytes]] = default_sse_spawner,
    ) -> None:
        self.url = url
        self.headers = headers
        self.count = count
        self.max_seconds = max_seconds
        self._spawner = spawner
        self.processes: list[subprocess.Popen[bytes]] = []

    def open(self) -> list[subprocess.Popen[bytes]]:
        for _ in range(self.count):
            self.processes.append(self._spawner(self.url, self.headers, self.max_seconds))
        return self.processes

    def close(self) -> None:
        for proc in self.processes:
            try:
                proc.terminate()
            except Exception:
                continue
        for proc in self.processes:
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self.processes = []

    def __enter__(self) -> SseConnectionPool:
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def read_active_sse_connections(base_url: str, headers: dict[str, str]) -> int | None:
    """从 `/health` 读服务端视角的活跃 SSE 连接数。

    用来确认 SSE 场景**真的把负载建立起来了**——如果这里读到 0，说明 60 条 curl
    全挂了（比如 token 不对被 401），此时"读接口很快"毫无意义。同样是坑 2 的形态。
    """
    sample_url = f"{base_url.rstrip('/')}/health"
    request = urllib.request.Request(sample_url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    value = payload.get("active_stream_connections")
    return int(value) if isinstance(value, int) else None


# --------------------------------------------------------------------------- #
# 场景
# --------------------------------------------------------------------------- #


def build_crawl_load_command(crawl_command: str | None) -> list[str]:
    """crawl 场景的负载来源。

    上一轮手测到的 588→265ms 是"后台正文爬取活跃期间"的读接口延迟。后端没有任何
    HTTP 接口能触发正文爬取，而本脚本按设计不碰数据库（safety：绝不写
    backend/data/app.db），所以无法自动、稳定地制造这个负载。这里**不伪造**：
    不给 `--crawl-command` 就直接报错退出。
    """
    if not crawl_command:
        raise BenchError(CRAWL_UNAVAILABLE_HINT)
    return ["/bin/sh", "-c", crawl_command]


def measure_endpoints(
    base_url: str,
    headers: dict[str, str],
    client: str,
    requests: int,
    concurrency: int,
    duration_seconds: int,
    tmp_dir: Path,
) -> dict[str, LatencyStats]:
    results: dict[str, LatencyStats] = {}
    for name, path in READ_ENDPOINTS:
        url = f"{base_url.rstrip('/')}{path}"
        if client == PYTHON_CLIENT:
            results[name] = run_python_load(url, headers, requests, concurrency)
        else:
            results[name] = run_external_load(
                client, url, headers, requests, concurrency, duration_seconds, tmp_dir
            )
    return results


# --------------------------------------------------------------------------- #
# 报告渲染
# --------------------------------------------------------------------------- #


def render_report(report: BenchReport) -> str:
    lines: list[str] = []
    lines.append("=" * 96)
    lines.append("读路径性能基准 bench_readpath")
    lines.append("=" * 96)
    lines.append(f"目标        : {report.base_url}")
    lines.append(f"压测客户端  : {report.client}")
    lines.append(f"请求量/并发 : {report.requests} / {report.concurrency}")
    lines.append(f"开始时间    : {report.started_at}")
    if report.client_warning:
        lines.append("")
        lines.append(report.client_warning)
    for scenario in report.scenarios:
        lines.append("")
        params = "  ".join(f"{key}={value}" for key, value in scenario.params.items())
        lines.append(f"[场景 {scenario.name}] {params}".rstrip())
        lines.append("-" * 96)
        lines.append(f"{'endpoint':<16}{'p50(ms)':>10}{'p95(ms)':>10}{'max(ms)':>10}{'rps':>12}{'ok':>8}{'err':>7}  备注")
        for name, stats in scenario.endpoints.items():
            note = "" if stats.latency_valid else "!! 含非 2xx 响应，延迟数字不可信"
            lines.append(
                f"{name:<16}{_fmt(stats.p50_ms):>10}{_fmt(stats.p95_ms):>10}{_fmt(stats.max_ms):>10}"
                f"{_fmt(stats.rps):>12}{stats.count:>8}{stats.error_count:>7}  {note}"
            )
    lines.append("")
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


# --------------------------------------------------------------------------- #
# 对比模式
# --------------------------------------------------------------------------- #


@dataclass
class DeltaRow:
    scenario: str
    endpoint: str
    metric: str
    baseline: float | None
    current: float | None
    delta_pct: float | None
    regressed: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario": self.scenario,
            "endpoint": self.endpoint,
            "metric": self.metric,
            "baseline": self.baseline,
            "current": self.current,
            "delta_pct": self.delta_pct,
            "regressed": self.regressed,
        }


def compare_reports(
    baseline: dict[str, object],
    current: dict[str, object],
    threshold_pct: float = REGRESSION_THRESHOLD_PCT,
) -> list[DeltaRow]:
    """逐 scenario / endpoint 比较 p50、p95、rps，并标记回归。

    - p50 / p95：**变大**是劣化，`delta_pct = (cur - base) / base * 100`，
      超过 `threshold_pct` 记为回归。
    - rps：**变小**是劣化，同样用超过阈值的相对跌幅记为回归。
    只有 p50 参与"回归"判定的主口径（p95/rps 也标，但阈值同样是 threshold_pct）。
    基线里没有的 scenario/endpoint 直接跳过，不臆造对比。
    """
    rows: list[DeltaRow] = []
    baseline_map = _index_scenarios(baseline)
    current_map = _index_scenarios(current)
    for scenario_name, current_endpoints in current_map.items():
        baseline_endpoints = baseline_map.get(scenario_name)
        if baseline_endpoints is None:
            continue
        for endpoint_name, current_stats in current_endpoints.items():
            baseline_stats = baseline_endpoints.get(endpoint_name)
            if baseline_stats is None:
                continue
            for metric, higher_is_better in (("p50_ms", False), ("p95_ms", False), ("rps", True)):
                base_value = getattr(baseline_stats, metric)
                cur_value = getattr(current_stats, metric)
                delta_pct = _delta_pct(base_value, cur_value)
                regressed = False
                if delta_pct is not None:
                    regressed = (
                        delta_pct < -threshold_pct if higher_is_better else delta_pct > threshold_pct
                    )
                rows.append(
                    DeltaRow(
                        scenario=scenario_name,
                        endpoint=endpoint_name,
                        metric=metric,
                        baseline=base_value,
                        current=cur_value,
                        delta_pct=delta_pct,
                        regressed=regressed,
                    )
                )
    return rows


def _index_scenarios(report: dict[str, object]) -> dict[str, dict[str, LatencyStats]]:
    indexed: dict[str, dict[str, LatencyStats]] = {}
    scenarios = report.get("scenarios") or []
    if not isinstance(scenarios, list):
        return indexed
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        name = str(scenario.get("name") or "")
        endpoints = scenario.get("endpoints") or {}
        if not isinstance(endpoints, dict):
            continue
        indexed[name] = {
            str(key): LatencyStats.from_dict(value)
            for key, value in endpoints.items()
            if isinstance(value, dict)
        }
    return indexed


def _delta_pct(baseline: float | None, current: float | None) -> float | None:
    if baseline is None or current is None or baseline == 0:
        return None
    return round((current - baseline) / baseline * 100.0, 2)


def render_comparison(
    rows: Sequence[DeltaRow],
    baseline_client: str | None,
    current_client: str | None,
    threshold_pct: float = REGRESSION_THRESHOLD_PCT,
) -> str:
    lines: list[str] = []
    lines.append("=" * 96)
    lines.append(f"与基线对比（劣化超过 {threshold_pct:.0f}% 标记 REGRESSION）")
    lines.append("=" * 96)
    if baseline_client and current_client and baseline_client != current_client:
        lines.append(
            f"[WARNING] 基线用的是 {baseline_client} 客户端，本次用的是 {current_client}，"
            "不同压测客户端的绝对数字不可直接比较（见脚本开头的坑 1）。"
        )
    lines.append(f"{'scenario':<10}{'endpoint':<16}{'metric':<10}{'baseline':>12}{'current':>12}{'delta':>10}  标记")
    for row in rows:
        mark = "REGRESSION" if row.regressed else ""
        delta = "-" if row.delta_pct is None else f"{row.delta_pct:+.1f}%"
        lines.append(
            f"{row.scenario:<10}{row.endpoint:<16}{row.metric:<10}"
            f"{_fmt(row.baseline):>12}{_fmt(row.current):>12}{delta:>10}  {mark}"
        )
    regressions = [row for row in rows if row.regressed]
    lines.append("")
    if regressions:
        lines.append(f"检测到 {len(regressions)} 项回归。")
    else:
        lines.append("未检测到回归。")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def load_token(explicit: str | None, token_file: Path = DEFAULT_TOKEN_FILE) -> str | None:
    if explicit:
        return explicit.strip()
    if token_file.exists():
        content = token_file.read_text(encoding="utf-8").strip()
        return content or None
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bench_readpath.py",
        description="读路径性能基准：压测一个【已经在运行】的后端，输出可归档、可跨次对比的 p50/p95/max/rps。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "推荐的被测后端启动命令（务必用临时库，绝不要指向 backend/data/app.db）：\n"
            "  DATABASE_URL=\"sqlite:////tmp/r2_bench.db\" SEED_DEMO_DATA=true \\\n"
            "    NEWS_SCHEDULER_ENABLED=false MARKET_QUOTE_PRODUCER_ENABLED=false \\\n"
            "    X_MONITOR_ENABLED=false BACKUP_ENABLED=false DATA_CLEANUP_ENABLED=false \\\n"
            "    PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8991 --log-level warning\n"
            "\n"
            "本脚本自己不会拉起后端，也不会读写任何数据库文件——只发 HTTP。\n"
        ),
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"后端 API 前缀（默认 {DEFAULT_BASE_URL}）")
    parser.add_argument(
        "--scenario",
        action="append",
        choices=SCENARIOS,
        default=None,
        help="要跑的场景，可重复；默认 idle + sse。crawl 需配合 --crawl-command。",
    )
    parser.add_argument("--requests", type=int, default=300, help="每个 endpoint 的请求总数（默认 300）")
    parser.add_argument("--concurrency", type=int, default=32, help="并发数（默认 32）")
    parser.add_argument("--sse-connections", type=int, default=60, help="sse 场景预先持有的 SSE 连接数（默认 60）")
    parser.add_argument("--sse-max-seconds", type=int, default=600, help="每条 curl SSE 连接的最长存活秒数（默认 600）")
    parser.add_argument("--duration", type=int, default=10, help="wrk 这类按时长压测的客户端使用的秒数（默认 10）")
    parser.add_argument(
        "--client",
        default="auto",
        choices=("auto", *EXTERNAL_CLIENTS, PYTHON_CLIENT),
        help="压测客户端；auto=优先 ab/hey/wrk，都没有才回退 python（会显式警告）",
    )
    parser.add_argument("--token", default=None, help=f"App Token；默认读 {DEFAULT_TOKEN_FILE}")
    parser.add_argument("--json", dest="json_path", type=Path, default=None, help="把结果写成机器可读 JSON")
    parser.add_argument("--baseline", type=Path, default=None, help="读入上次的 JSON 结果做逐项 delta 对比")
    parser.add_argument(
        "--regression-threshold",
        type=float,
        default=REGRESSION_THRESHOLD_PCT,
        help=f"劣化超过该百分比标记回归（默认 {REGRESSION_THRESHOLD_PCT:.0f}）",
    )
    parser.add_argument("--crawl-command", default=None, help="crawl 场景使用的外部负载命令（见 --help 说明）")
    parser.add_argument("--warmup", type=int, default=20, help="正式测量前的预热请求数（默认 20，0 为关闭）")
    return parser


def run_bench(args: argparse.Namespace, out=sys.stdout) -> int:
    base_url = args.base_url.rstrip("/")
    token = load_token(args.token)
    headers = {"X-App-Token": token} if token else {}
    scenarios = args.scenario or ["idle", "sse"]

    client = detect_client(args.client)
    warning = client_warning_for(client)
    if warning:
        print(warning, file=out)

    urls = [f"{base_url}{path}" for _, path in READ_ENDPOINTS]

    # ---- 坑 2：先做鉴权预检，失败就地中止 ----
    print(f"[preflight] 对 {len(urls)} 个 endpoint 做鉴权自检…", file=out)
    preflight(urls, lambda url: http_probe(url, headers))
    print("[preflight] 全部返回 2xx，确认能产生真实负载。", file=out)

    tmp_dir = Path(f"/tmp/bench_readpath_{int(time.time())}")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    report = BenchReport(
        base_url=base_url,
        client=client,
        client_warning=warning,
        requests=args.requests,
        concurrency=args.concurrency,
        started_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    )

    for name in scenarios:
        if name == "idle":
            _warmup(base_url, headers, args.warmup)
            print("[scenario idle] 空载读接口测量中…", file=out)
            stats = measure_endpoints(
                base_url, headers, client, args.requests, args.concurrency, args.duration, tmp_dir
            )
            report.scenarios.append(ScenarioResult(name="idle", params={}, endpoints=stats))

        elif name == "sse":
            sse_url = f"{base_url}{SSE_PATH}"
            print(f"[scenario sse] 用独立 curl 子进程建立 {args.sse_connections} 条 SSE 连接…", file=out)
            pool = SseConnectionPool(sse_url, headers, args.sse_connections, args.sse_max_seconds)
            try:
                pool.open()
                time.sleep(3.0)
                active = read_active_sse_connections(base_url, headers)
                print(f"[scenario sse] 服务端上报的活跃 SSE 连接数：{active}", file=out)
                if active is not None and active < max(1, args.sse_connections // 2):
                    raise BenchError(
                        f"SSE 负载没建立起来（服务端只看到 {active} 条，期望约 {args.sse_connections} 条）。"
                        "常见原因是 token 不对导致 curl 被 401——此时读接口『很快』毫无意义，故中止。"
                    )
                _warmup(base_url, headers, args.warmup)
                stats = measure_endpoints(
                    base_url, headers, client, args.requests, args.concurrency, args.duration, tmp_dir
                )
            finally:
                pool.close()
            report.scenarios.append(
                ScenarioResult(
                    name="sse",
                    params={"sse_connections": args.sse_connections, "server_reported_active": active},
                    endpoints=stats,
                )
            )

        elif name == "crawl":
            cmd = build_crawl_load_command(args.crawl_command)
            print(f"[scenario crawl] 启动外部负载命令：{args.crawl_command}", file=out)
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603
            try:
                time.sleep(3.0)
                _warmup(base_url, headers, args.warmup)
                stats = measure_endpoints(
                    base_url, headers, client, args.requests, args.concurrency, args.duration, tmp_dir
                )
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except Exception:
                    proc.kill()
            report.scenarios.append(
                ScenarioResult(
                    name="crawl",
                    params={"crawl_command": args.crawl_command},
                    endpoints=stats,
                )
            )

    print(render_report(report), file=out)

    payload = report.to_dict()
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[json] 结果已写入 {args.json_path}", file=out)

    exit_code = 0
    if args.baseline is not None:
        baseline_payload = json.loads(args.baseline.read_text(encoding="utf-8"))
        rows = compare_reports(baseline_payload, payload, threshold_pct=args.regression_threshold)
        print(
            render_comparison(
                rows,
                baseline_client=str(baseline_payload.get("client") or "") or None,
                current_client=client,
                threshold_pct=args.regression_threshold,
            ),
            file=out,
        )
        if any(row.regressed for row in rows):
            exit_code = 1
    return exit_code


def _warmup(base_url: str, headers: dict[str, str], count: int) -> None:
    """预热：让路由级 TTL 缓存、SQLAlchemy 连接池、SQLite page cache 进入稳态。

    不预热的话第一个场景会额外背上冷启动成本，跨次对比里表现为无来由的抖动。
    """
    if count <= 0:
        return
    for _, path in READ_ENDPOINTS:
        url = f"{base_url.rstrip('/')}{path}"
        for _ in range(count):
            http_probe(url, headers)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_bench(args)
    except AuthPreflightError as exc:
        print(f"\n[FATAL][鉴权预检] {exc}", file=sys.stderr)
        return 2
    except BenchError as exc:
        print(f"\n[FATAL] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
