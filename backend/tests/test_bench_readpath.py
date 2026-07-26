"""`backend/scripts/bench_readpath.py` 的回归测试。

这个文件的重点**不是**验证"压测跑得快不快"，而是锁死基准脚本本身的两条防线——
上一轮做性能测量时真实踩过的两个坑，一旦防线失效，脚本就会安静地输出错误结论：

* **坑 1（客户端成为瓶颈）**：必须优先用外部原生客户端（ab/hey/wrk），回退到
  Python 客户端时必须在输出里带显著警告；SSE 长连接必须由**独立子进程**持有，
  不能用 Python 线程。
* **坑 2（鉴权失败被误读成很快）**：正式测量前必须做鉴权自检，401/403 立刻中止
  并以非零码退出；任何非 2xx 响应都不得进入 p50/p95/max 统计。

因此全部用例都跑在纯函数 / 可注入接口上，**不起任何真实服务、不发真实网络请求**。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.bench_readpath import (
    PYTHON_CLIENT_WARNING,
    READ_ENDPOINTS,
    AuthPreflightError,
    BenchError,
    BenchReport,
    LatencyStats,
    Sample,
    ScenarioResult,
    SseConnectionPool,
    build_crawl_load_command,
    build_parser,
    client_warning_for,
    compare_reports,
    default_sse_spawner,
    detect_client,
    main,
    parse_ab_output,
    percentile,
    render_comparison,
    render_report,
    run_python_load,
    summarize,
)

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "bench_readpath.py"


# --------------------------------------------------------------------------- #
# 坑 2 之一：鉴权自检失败必须中止，绝不能把 401 当成"很快"
# --------------------------------------------------------------------------- #


def test_preflight_aborts_on_401_instead_of_treating_it_as_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """假 client 全返 401（且返回得极快），脚本必须抛错中止而不是记录成低延迟。"""
    calls: list[str] = []

    def fake_probe(url: str, headers: dict[str, str], timeout: float = 10.0) -> Sample:
        calls.append(url)
        # 401 通常比真业务快一个数量级，正是"看起来性能极佳"的来源
        return Sample(status=401, elapsed_ms=0.4)

    monkeypatch.setattr("scripts.bench_readpath.http_probe", fake_probe)

    args = build_parser().parse_args(["--base-url", "http://127.0.0.1:9/api"])
    exit_code = main_with_args(args)

    assert exit_code == 2, "鉴权自检失败必须以非零码退出"
    # 第一个 endpoint 就该炸掉，不该继续把剩下的都测一遍
    assert len(calls) == 1


def test_preflight_raises_auth_error_type(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.bench_readpath import preflight

    with pytest.raises(AuthPreflightError) as excinfo:
        preflight(["http://x/api/topics"], lambda _url: Sample(status=403, elapsed_ms=0.2))
    assert "403" in str(excinfo.value)


def test_preflight_rejects_other_non_2xx_and_connection_failure() -> None:
    from scripts.bench_readpath import preflight

    with pytest.raises(BenchError):
        preflight(["http://x/api/topics"], lambda _url: Sample(status=500, elapsed_ms=1.0))
    with pytest.raises(BenchError):
        # status=0 表示连不上，同样不能当成"零延迟"
        preflight(["http://x/api/topics"], lambda _url: Sample(status=0, elapsed_ms=0.0))


def test_preflight_passes_through_all_endpoints_on_2xx() -> None:
    from scripts.bench_readpath import preflight

    urls = [f"http://x/api{path}" for _, path in READ_ENDPOINTS]
    samples = preflight(urls, lambda _url: Sample(status=200, elapsed_ms=5.0))
    assert len(samples) == len(READ_ENDPOINTS)


def main_with_args(args) -> int:
    """复用 main 的异常→退出码映射，但跳过 argparse。"""
    import scripts.bench_readpath as module

    try:
        return module.run_bench(args)
    except AuthPreflightError:
        return 2
    except BenchError:
        return 2


def test_main_returns_non_zero_on_auth_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """完整走 main()（含 argparse）时同样必须返回非零码。"""
    monkeypatch.setattr(
        "scripts.bench_readpath.http_probe",
        lambda url, headers, timeout=10.0: Sample(status=401, elapsed_ms=0.3),
    )
    assert main(["--base-url", "http://127.0.0.1:9/api", "--scenario", "idle"]) == 2


# --------------------------------------------------------------------------- #
# 坑 2 之二：非 2xx 不得进入延迟统计
# --------------------------------------------------------------------------- #


def test_summarize_excludes_non_2xx_from_latency() -> None:
    samples = [
        Sample(status=200, elapsed_ms=10.0),
        Sample(status=401, elapsed_ms=0.1),   # 极快的失败请求
        Sample(status=200, elapsed_ms=20.0),
        Sample(status=500, elapsed_ms=0.2),
        Sample(status=200, elapsed_ms=30.0),
        Sample(status=0, elapsed_ms=0.0),     # 连接失败
    ]

    stats = summarize(samples, wall_seconds=1.0)

    assert stats.count == 3
    assert stats.error_count == 3
    # p50 只由 [10, 20, 30] 计算：nearest-rank ceil(0.5*3)=2 → 20.0
    assert stats.p50_ms == 20.0
    assert stats.max_ms == 30.0
    assert stats.rps == 3.0
    # 只要混入了非 2xx，本行延迟就被标为不可信
    assert stats.latency_valid is False


def test_summarize_all_success_is_valid() -> None:
    stats = summarize([Sample(status=200, elapsed_ms=x) for x in (5.0, 6.0)], wall_seconds=2.0)
    assert stats.error_count == 0
    assert stats.latency_valid is True
    assert stats.rps == 1.0


def test_summarize_all_failures_reports_no_latency_not_zero() -> None:
    """全失败时分位数必须是 None，绝不能退化成 0（0ms 会被误读成极快）。"""
    stats = summarize([Sample(status=401, elapsed_ms=0.1)] * 5, wall_seconds=1.0)
    assert stats.count == 0
    assert stats.error_count == 5
    assert stats.p50_ms is None
    assert stats.p95_ms is None
    assert stats.max_ms is None
    assert stats.latency_valid is False


def test_python_load_filters_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """端到端走一遍 Python 执行器：混入失败响应后 p50 仍只由成功请求算出。"""
    responses = [
        Sample(status=200, elapsed_ms=100.0),
        Sample(status=503, elapsed_ms=0.5),
        Sample(status=200, elapsed_ms=100.0),
        Sample(status=200, elapsed_ms=100.0),
    ]
    box = iter(responses)

    stats = run_python_load(
        "http://x/api/topics", {}, requests=4, concurrency=1, probe=lambda _url: next(box)
    )
    assert stats.count == 3
    assert stats.error_count == 1
    assert stats.p50_ms == 100.0


def test_ab_parser_marks_latency_invalid_when_non_2xx_present() -> None:
    """ab 自己算的分位数无法剔除非 2xx，所以有错误就必须整行标记不可信。"""
    stdout = """
Complete requests:      300
Failed requests:        0
Non-2xx responses:      300
Requests per second:    9999.00 [#/sec] (mean)
"""
    csv_text = "Percentage served,Time in ms\n50,0.400\n95,0.900\n100,1.200\n"
    stats = parse_ab_output(stdout, csv_text)

    assert stats.error_count == 300
    assert stats.count == 0
    assert stats.latency_valid is False
    assert stats.rps == 9999.0


def test_ab_parser_clean_run() -> None:
    stdout = """
Complete requests:      300
Failed requests:        0
Requests per second:    3809.12 [#/sec] (mean)
"""
    csv_text = "Percentage served,Time in ms\n50,8.000\n95,12.500\n100,25.000\n"
    stats = parse_ab_output(stdout, csv_text)

    assert stats.count == 300
    assert stats.error_count == 0
    assert stats.latency_valid is True
    assert stats.p50_ms == 8.0
    assert stats.p95_ms == 12.5
    assert stats.max_ms == 25.0


def test_ab_parser_falls_back_to_stdout_percentile_table() -> None:
    stdout = """
Complete requests:      100
Failed requests:        0
Requests per second:    1197.00 [#/sec] (mean)

Percentage of the requests served within a certain time (ms)
  50%     25
  95%     40
 100%     61 (longest request)
"""
    stats = parse_ab_output(stdout, None)
    assert stats.p50_ms == 25.0
    assert stats.p95_ms == 40.0
    assert stats.max_ms == 61.0


# --------------------------------------------------------------------------- #
# 坑 1 之一：客户端探测 + 回退警告
# --------------------------------------------------------------------------- #


def test_detect_client_prefers_external_c_clients() -> None:
    assert detect_client("auto", which=lambda name: "/usr/sbin/ab" if name == "ab" else None) == "ab"
    # ab 不在时按顺序退到 hey
    assert detect_client("auto", which=lambda name: "/usr/local/bin/hey" if name == "hey" else None) == "hey"
    assert detect_client("auto", which=lambda name: "/usr/local/bin/wrk" if name == "wrk" else None) == "wrk"


def test_detect_client_falls_back_to_python_with_warning() -> None:
    client = detect_client("auto", which=lambda _name: None)
    assert client == "python"

    warning = client_warning_for(client)
    assert warning == PYTHON_CLIENT_WARNING
    assert "仅供参考" in warning
    assert "GIL" in warning

    # 警告必须真的出现在人类可读报告里，而不是只存在于常量中
    report = BenchReport(
        base_url="http://127.0.0.1:8991/api",
        client=client,
        client_warning=warning,
        requests=300,
        concurrency=32,
        started_at="2026-07-26T00:00:00+0800",
        scenarios=[ScenarioResult(name="idle", endpoints={"topics": summarize([Sample(200, 8.0)], 1.0)})],
    )
    rendered = render_report(report)
    assert PYTHON_CLIENT_WARNING in rendered
    assert "[WARNING]" in rendered


def test_external_client_has_no_warning() -> None:
    assert client_warning_for("ab") is None
    assert client_warning_for("wrk") is None


def test_detect_client_explicit_missing_binary_errors() -> None:
    with pytest.raises(BenchError):
        detect_client("wrk", which=lambda _name: None)
    with pytest.raises(BenchError):
        detect_client("nope", which=lambda _name: "/bin/nope")


def test_json_payload_records_client_type() -> None:
    """跨次对比要能看出"这次是不是换了客户端"，client 字段必须落进 JSON。"""
    report = BenchReport(
        base_url="http://x/api",
        client="python",
        client_warning=PYTHON_CLIENT_WARNING,
        requests=10,
        concurrency=2,
        started_at="2026-07-26T00:00:00+0800",
    )
    payload = report.to_dict()
    assert payload["client"] == "python"
    assert payload["client_warning"] == PYTHON_CLIENT_WARNING


# --------------------------------------------------------------------------- #
# 坑 1 之二：SSE 连接必须由子进程持有，不能用线程
# --------------------------------------------------------------------------- #


def test_default_sse_spawner_uses_curl_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakePopen:
        def __init__(self, cmd, stdout=None, stderr=None):
            captured["cmd"] = cmd
            captured["stdout"] = stdout

    monkeypatch.setattr(subprocess, "Popen", FakePopen)

    default_sse_spawner("http://x/api/stream/events", {"X-App-Token": "t"}, 600)

    cmd = captured["cmd"]
    assert cmd[0] == "curl", "SSE 连接必须由外部 curl 进程持有（不能是 Python 线程）"
    assert "-sN" in cmd
    assert "X-App-Token: t" in cmd
    assert "http://x/api/stream/events" in cmd


def test_sse_pool_spawns_one_process_per_connection_and_cleans_up() -> None:
    spawned: list[FakeProc] = []

    def spawner(url: str, headers: dict[str, str], max_seconds: int) -> FakeProc:
        proc = FakeProc()
        spawned.append(proc)
        return proc

    with SseConnectionPool("http://x/api/stream/events", {}, count=60, spawner=spawner) as pool:
        assert len(pool.processes) == 60
        assert len(spawned) == 60

    assert all(proc.terminated for proc in spawned), "退出上下文时必须把所有 curl 子进程收干净"


class FakeProc:
    def __init__(self) -> None:
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def kill(self) -> None:
        self.terminated = True


def test_sse_implementation_uses_subprocess_not_threads() -> None:
    """源码层面锁死：SSE 持连接的实现必须走 subprocess，不得引入线程池。"""
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "subprocess.Popen" in source
    spawner_body = source.split("def default_sse_spawner", 1)[1].split("\nclass SseConnectionPool", 1)[0]
    assert "subprocess.Popen" in spawner_body
    assert "Thread" not in spawner_body
    assert "threading" not in source, "基准脚本不应引入 threading 来持有 SSE 连接（见坑 1）"


# --------------------------------------------------------------------------- #
# 统计函数的正确性（含边界）
# --------------------------------------------------------------------------- #


def test_percentile_known_sequence() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    # nearest-rank：p50 → ceil(0.5*10)=5 → 第 5 个 → 5.0
    assert percentile(values, 0.50) == 5.0
    # p95 → ceil(0.95*10)=10 → 第 10 个 → 10.0
    assert percentile(values, 0.95) == 10.0
    assert percentile(values, 1.0) == 10.0


def test_percentile_is_order_independent() -> None:
    assert percentile([9.0, 1.0, 5.0, 3.0, 7.0], 0.50) == 5.0


def test_percentile_edge_cases() -> None:
    assert percentile([], 0.5) is None
    assert percentile([], 0.95) is None
    assert percentile([42.0], 0.5) == 42.0
    assert percentile([42.0], 0.95) == 42.0
    with pytest.raises(ValueError):
        percentile([1.0], 0.0)
    with pytest.raises(ValueError):
        percentile([1.0], 1.5)


def test_summarize_empty_sample_set() -> None:
    stats = summarize([], wall_seconds=1.0)
    assert stats.count == 0
    assert stats.error_count == 0
    assert stats.p50_ms is None
    assert stats.p95_ms is None
    assert stats.max_ms is None
    assert stats.rps == 0.0


def test_summarize_single_sample() -> None:
    stats = summarize([Sample(status=200, elapsed_ms=7.5)], wall_seconds=0.5)
    assert stats.p50_ms == 7.5
    assert stats.p95_ms == 7.5
    assert stats.max_ms == 7.5
    assert stats.rps == 2.0


# --------------------------------------------------------------------------- #
# --baseline 对比模式
# --------------------------------------------------------------------------- #


def _report_payload(client: str, p50: float, p95: float, rps: float) -> dict:
    return {
        "base_url": "http://127.0.0.1:8991/api",
        "client": client,
        "requests": 300,
        "concurrency": 32,
        "scenarios": [
            {
                "name": "idle",
                "params": {},
                "endpoints": {
                    "topics": {
                        "count": 300,
                        "error_count": 0,
                        "p50_ms": p50,
                        "p95_ms": p95,
                        "max_ms": p95 * 2,
                        "rps": rps,
                        "latency_valid": True,
                    }
                },
            }
        ],
    }


def test_compare_flags_p50_regression_beyond_threshold() -> None:
    baseline = _report_payload("ab", p50=8.0, p95=12.0, rps=3800.0)
    current = _report_payload("ab", p50=25.0, p95=40.0, rps=1197.0)

    rows = compare_reports(baseline, current, threshold_pct=20.0)
    by_metric = {row.metric: row for row in rows}

    assert by_metric["p50_ms"].delta_pct == pytest.approx(212.5)
    assert by_metric["p50_ms"].regressed is True
    assert by_metric["p95_ms"].regressed is True
    # rps 跌了才算劣化
    assert by_metric["rps"].delta_pct == pytest.approx(-68.5, abs=0.1)
    assert by_metric["rps"].regressed is True


def test_compare_does_not_flag_improvement_or_small_drift() -> None:
    baseline = _report_payload("ab", p50=25.0, p95=40.0, rps=1197.0)
    current = _report_payload("ab", p50=8.0, p95=12.0, rps=3809.0)

    rows = compare_reports(baseline, current, threshold_pct=20.0)
    assert all(row.regressed is False for row in rows)

    # 10% 的抖动在 20% 阈值内，不该报警
    drift = compare_reports(
        _report_payload("ab", 10.0, 20.0, 1000.0),
        _report_payload("ab", 11.0, 21.0, 950.0),
        threshold_pct=20.0,
    )
    assert all(row.regressed is False for row in drift)


def test_compare_skips_endpoints_absent_from_baseline() -> None:
    baseline = _report_payload("ab", 10.0, 20.0, 1000.0)
    current = _report_payload("ab", 10.0, 20.0, 1000.0)
    current["scenarios"].append(
        {
            "name": "sse",
            "params": {},
            "endpoints": {"topics": {"p50_ms": 999.0, "p95_ms": 999.0, "rps": 1.0}},
        }
    )
    rows = compare_reports(baseline, current)
    assert {row.scenario for row in rows} == {"idle"}


def test_compare_handles_missing_metric_values() -> None:
    baseline = _report_payload("ab", 10.0, 20.0, 1000.0)
    current = _report_payload("ab", 10.0, 20.0, 1000.0)
    current["scenarios"][0]["endpoints"]["topics"]["p50_ms"] = None
    rows = compare_reports(baseline, current)
    p50_row = next(row for row in rows if row.metric == "p50_ms")
    assert p50_row.delta_pct is None
    assert p50_row.regressed is False


def test_render_comparison_marks_regression_and_client_mismatch() -> None:
    rows = compare_reports(
        _report_payload("ab", 8.0, 12.0, 3800.0),
        _report_payload("python", 25.0, 40.0, 1197.0),
    )
    text = render_comparison(rows, baseline_client="ab", current_client="python")
    assert "REGRESSION" in text
    # 换了客户端必须显式提示不可直接比较（坑 1）
    assert "[WARNING]" in text
    assert "ab" in text and "python" in text


def test_render_comparison_reports_clean_run() -> None:
    rows = compare_reports(_report_payload("ab", 10.0, 20.0, 1000.0), _report_payload("ab", 10.0, 20.0, 1000.0))
    text = render_comparison(rows, baseline_client="ab", current_client="ab")
    assert "未检测到回归" in text
    # 表头里的 "REGRESSION" 是图例，只有数据行的标记列才代表真回归
    data_lines = [line for line in text.splitlines() if line.startswith("idle")]
    assert data_lines
    assert all("REGRESSION" not in line for line in data_lines)


def test_baseline_roundtrip_through_json(tmp_path: Path) -> None:
    """JSON 存档 → 读回 → 对比，字段必须能对齐（跨次对比的实际使用路径）。"""
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(_report_payload("ab", 8.0, 12.0, 3800.0), ensure_ascii=False), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    rows = compare_reports(loaded, _report_payload("ab", 8.0, 12.0, 3800.0))
    assert rows and all(row.delta_pct == 0.0 for row in rows)


def test_latency_stats_dict_roundtrip() -> None:
    stats = LatencyStats(count=10, error_count=2, p50_ms=8.0, p95_ms=12.0, max_ms=25.0, rps=100.0, latency_valid=False)
    assert LatencyStats.from_dict(stats.to_dict()) == stats


# --------------------------------------------------------------------------- #
# crawl 场景：不能伪造
# --------------------------------------------------------------------------- #


def test_crawl_scenario_refuses_to_fake_load() -> None:
    with pytest.raises(BenchError) as excinfo:
        build_crawl_load_command(None)
    assert "--crawl-command" in str(excinfo.value)

    assert build_crawl_load_command("echo hi") == ["/bin/sh", "-c", "echo hi"]


# --------------------------------------------------------------------------- #
# CLI 契约
# --------------------------------------------------------------------------- #


def test_cli_defaults_are_safe() -> None:
    args = build_parser().parse_args([])
    assert args.base_url == "http://127.0.0.1:8000/api"
    assert args.client == "auto"
    assert args.sse_connections == 60
    assert args.scenario is None  # 默认 idle + sse，在 run_bench 里展开


def test_help_text_warns_about_temp_db_and_never_points_at_app_db() -> None:
    help_text = build_parser().format_help()
    assert "临时库" in help_text
    assert "backend/data/app.db" in help_text  # 以"绝不要指向"的形式出现
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    # 脚本自身不得读写任何 DB：既不导入 ORM，也不导入后端 app 包
    assert "import sqlalchemy" not in source
    assert "from sqlalchemy" not in source
    assert "create_engine" not in source
    assert "from app." not in source
    # 默认 base-url 是 HTTP 地址，不含任何 DB 路径
    assert build_parser().parse_args([]).base_url.startswith("http://")
