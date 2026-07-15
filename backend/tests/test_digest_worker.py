from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.workers.digest_worker import DigestWorker


def _build_worker(clock: dict[str, datetime], calls: list[tuple[str, str]], **kwargs) -> DigestWorker:
    def trigger(market: str, phase: str) -> None:
        calls.append((market, phase))

    return DigestWorker(
        session_factory=lambda: None,  # do_cycle 不触库
        trigger_fn=trigger,
        premarket_time="08:30",
        postmarket_time="16:30",
        now_factory=lambda: clock["now"],
        **kwargs,
    )


def test_digest_worker_fires_hk_premarket_once_and_is_idempotent() -> None:
    calls: list[tuple[str, str]] = []
    # 08:30 Asia/Hong_Kong == 00:30 UTC
    clock = {"now": datetime(2026, 7, 13, 0, 30, tzinfo=UTC)}
    worker = _build_worker(clock, calls)

    # 到点：港股盘前触发一次。
    assert worker.do_cycle() == 1
    assert calls == [("hk", "premarket")]

    # 幂等：同一分钟再 tick 不重复触发。
    calls.clear()
    assert worker.do_cycle() == 0
    assert calls == []

    # 次日同一时点：再次触发。
    clock["now"] = clock["now"] + timedelta(days=1)
    calls.clear()
    assert worker.do_cycle() == 1
    assert calls == [("hk", "premarket")]


def test_digest_worker_fires_us_postmarket() -> None:
    calls: list[tuple[str, str]] = []
    # 16:30 America/New_York (EDT, UTC-4) == 20:30 UTC
    clock = {"now": datetime(2026, 7, 13, 20, 30, tzinfo=UTC)}
    worker = _build_worker(clock, calls)

    assert worker.do_cycle() == 1
    assert calls == [("us", "postmarket")]


def test_digest_worker_skips_stale_time_outside_grace_window() -> None:
    calls: list[tuple[str, str]] = []
    # 08:45 HKT == 00:45 UTC，已超出 08:30 后的 10 分钟 grace 窗口，不应补发。
    clock = {"now": datetime(2026, 7, 13, 0, 45, tzinfo=UTC)}
    worker = _build_worker(clock, calls, grace_minutes=10)

    assert worker.do_cycle() == 0
    assert calls == []


def test_digest_worker_swallows_trigger_errors() -> None:
    # 到点时 trigger_fn 抛错不得让 do_cycle 崩溃（BaseWorker 之外再兜一层）。
    def failing_trigger(market: str, phase: str) -> None:
        raise RuntimeError("push failed")

    clock = {"now": datetime(2026, 7, 13, 0, 30, tzinfo=UTC)}
    worker = DigestWorker(
        session_factory=lambda: None,
        trigger_fn=failing_trigger,
        premarket_time="08:30",
        postmarket_time="16:30",
        now_factory=lambda: clock["now"],
    )

    # 不抛异常；因触发失败未计入 fired_count，但当天不再重试（已 dedupe）。
    assert worker.do_cycle() == 0
