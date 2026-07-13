"""统一系统健康看板（Ops Health Dashboard）测试。

覆盖：聚合字段正确、阈值触发对应 alerts、无数据不崩、路由 200 返回。
参考 ``test_stream_status.py`` 的 monkeypatch 事件层写法。
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.llm_token_usage import LLMTokenUsage
from app.models.source_health import SourceHealth
from app.models.worker_runtime_status import WorkerRuntimeStatus
from app.models.x_source_health import XSourceHealth
from app.services import ops_health as ops_health_module
from app.services.event_bus import EventBusStatus


class _FakeBus:
    """可控的事件层桩，避免真实 Redis 依赖。"""

    def __init__(self, status: EventBusStatus) -> None:
        self._status = status

    def get_status(self) -> EventBusStatus:
        return self._status


def _ok_bus() -> _FakeBus:
    return _FakeBus(EventBusStatus(backend="hybrid", status="ok", redis_enabled=True))


def _clear_tables() -> None:
    with SessionLocal() as session:
        session.query(LLMTokenUsage).delete()
        session.query(SourceHealth).delete()
        session.query(XSourceHealth).delete()
        session.query(WorkerRuntimeStatus).delete()
        session.commit()


def test_build_ops_health_aggregates_fields(monkeypatch) -> None:
    _clear_tables()
    monkeypatch.setattr(ops_health_module, "get_event_bus", _ok_bus)

    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        session.add(
            WorkerRuntimeStatus(
                worker_name="market_quote_producer",
                status="ok",
                last_heartbeat_at=now - timedelta(seconds=10),
                last_success_at=now - timedelta(seconds=10),
                cycle_count=12,
                success_count=11,
                failure_count=1,
                last_quotes_count=5,
            )
        )
        session.add(
            SourceHealth(
                source_name="reuters",
                market="us",
                source_type="rss",
                last_success_at=now - timedelta(minutes=1),
                consecutive_failures=0,
                total_fetches=100,
                total_failures=10,
                avg_latency_ms=250.0,
                is_disabled=False,
            )
        )
        session.add(
            XSourceHealth(
                provider_name="twitterapi_io",
                last_success_at=now - timedelta(minutes=2),
                consecutive_failures=0,
                total_fetches=40,
                total_failures=0,
                avg_latency_ms=800.0,
            )
        )
        session.add(
            LLMTokenUsage(
                model_name="deepseek-chat",
                prompt_tokens=100,
                completion_tokens=200,
                total_tokens=300,
                operation_type="analysis",
                created_at=now - timedelta(hours=1),
            )
        )
        # 超过 24h 窗口的记录不应计入统计。
        session.add(
            LLMTokenUsage(
                model_name="deepseek-chat",
                prompt_tokens=999,
                completion_tokens=999,
                total_tokens=1998,
                operation_type="analysis",
                created_at=now - timedelta(hours=48),
            )
        )
        session.commit()

    with SessionLocal() as session:
        result = ops_health_module.build_ops_health(session)

    assert result.overall_status == "ok"
    assert result.alerts == []

    assert len(result.workers) == 1
    worker = result.workers[0]
    assert worker.name == "market_quote_producer"
    assert worker.status == "ok"
    assert worker.heartbeat_age_seconds is not None and worker.heartbeat_age_seconds >= 0

    assert len(result.sources) == 1
    source = result.sources[0]
    assert source.source_name == "reuters"
    # 100 抓取 / 10 失败 -> 成功率 0.9
    assert source.success_rate == 0.9

    assert len(result.x_sources) == 1
    assert result.x_sources[0].provider_name == "twitterapi_io"
    assert result.x_sources[0].success_rate == 1.0

    # 仅统计近 24h：一条 300 tokens 的记录。
    assert result.llm_usage.window_hours == 24
    assert result.llm_usage.call_count == 1
    assert result.llm_usage.total_tokens == 300
    assert result.llm_usage.prompt_tokens == 100
    assert result.llm_usage.completion_tokens == 200
    assert len(result.llm_usage.models) == 1
    assert result.llm_usage.models[0].model_name == "deepseek-chat"

    assert result.event_bus.backend == "hybrid"
    assert result.event_bus.status == "ok"

    # 测试库文件存在且能取到体积。
    assert result.database.exists is True
    assert result.database.size_bytes >= 0


def test_ops_health_alerts_triggered(monkeypatch) -> None:
    _clear_tables()
    # 事件层降级应触发 event_bus.degraded 告警。
    degraded_bus = _FakeBus(
        EventBusStatus(
            backend="hybrid",
            status="degraded",
            redis_enabled=True,
            last_error="redis unavailable",
        )
    )
    monkeypatch.setattr(ops_health_module, "get_event_bus", lambda: degraded_bus)
    # 把 DB 告警阈值调到 0，强制触发数据库体积 warning（测试库有实际体积）。
    monkeypatch.setattr(ops_health_module, "DB_SIZE_WARNING_MB", 0.0)
    monkeypatch.setattr(ops_health_module, "DB_SIZE_CRITICAL_MB", 1_000_000.0)

    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        # 心跳超时的 worker。
        session.add(
            WorkerRuntimeStatus(
                worker_name="news_ingest_scheduler",
                status="ok",
                last_heartbeat_at=now - timedelta(seconds=ops_health_module.WORKER_HEARTBEAT_TIMEOUT_SECONDS + 120),
                cycle_count=3,
                success_count=3,
                failure_count=0,
                last_quotes_count=0,
            )
        )
        # 连续失败并被禁用的新闻源。
        session.add(
            SourceHealth(
                source_name="flaky_feed",
                market="hk",
                source_type="rss",
                consecutive_failures=ops_health_module.SOURCE_CONSECUTIVE_FAILURE_THRESHOLD,
                total_fetches=20,
                total_failures=20,
                is_disabled=True,
            )
        )
        # 连续失败的 X 源。
        session.add(
            XSourceHealth(
                provider_name="twitterapi_io",
                consecutive_failures=ops_health_module.SOURCE_CONSECUTIVE_FAILURE_THRESHOLD + 3,
                total_fetches=10,
                total_failures=10,
            )
        )
        session.commit()

    with SessionLocal() as session:
        result = ops_health_module.build_ops_health(session)

    codes = {alert.code for alert in result.alerts}
    assert "worker.heartbeat_timeout" in codes
    assert "source.consecutive_failures" in codes
    assert "source.disabled" in codes
    assert "x_source.consecutive_failures" in codes
    assert "event_bus.degraded" in codes
    assert "database.size" in codes

    # 每条告警都带 level/code/subject/message。
    for alert in result.alerts:
        assert alert.level in {"warning", "critical"}
        assert alert.code
        assert alert.subject
        assert alert.message

    # 无 critical，但有 warning -> overall warning。
    assert result.overall_status == "warning"


def test_ops_health_database_critical(monkeypatch) -> None:
    _clear_tables()
    monkeypatch.setattr(ops_health_module, "get_event_bus", _ok_bus)
    monkeypatch.setattr(ops_health_module, "DB_SIZE_WARNING_MB", 0.0)
    monkeypatch.setattr(ops_health_module, "DB_SIZE_CRITICAL_MB", 0.0)

    with SessionLocal() as session:
        result = ops_health_module.build_ops_health(session)

    db_alerts = [alert for alert in result.alerts if alert.code == "database.size"]
    assert len(db_alerts) == 1
    assert db_alerts[0].level == "critical"
    assert result.overall_status == "critical"


def test_ops_health_no_data_does_not_crash(monkeypatch) -> None:
    _clear_tables()
    monkeypatch.setattr(ops_health_module, "get_event_bus", _ok_bus)

    with SessionLocal() as session:
        result = ops_health_module.build_ops_health(session)

    assert result.workers == []
    assert result.sources == []
    assert result.x_sources == []
    assert result.llm_usage.call_count == 0
    assert result.llm_usage.total_tokens == 0
    assert result.llm_usage.models == []
    # 默认阈值很大，空库不应产出体积告警 -> ok。
    assert result.overall_status == "ok"
    assert result.alerts == []


def test_ops_health_route_returns_payload(monkeypatch) -> None:
    _clear_tables()
    monkeypatch.setattr(ops_health_module, "get_event_bus", _ok_bus)

    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        session.add(
            WorkerRuntimeStatus(
                worker_name="data_cleanup",
                status="ok",
                last_heartbeat_at=now,
                last_success_at=now,
                cycle_count=1,
                success_count=1,
                failure_count=0,
                last_quotes_count=0,
            )
        )
        session.commit()

    client = TestClient(app)
    response = client.get("/api/ops/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_status"] in {"ok", "warning", "critical"}
    assert "alerts" in payload
    assert "workers" in payload
    assert "sources" in payload
    assert "x_sources" in payload
    assert "llm_usage" in payload
    assert "event_bus" in payload
    assert "database" in payload
    assert payload["event_bus"]["backend"] == "hybrid"
    worker_names = {worker["name"] for worker in payload["workers"]}
    assert "data_cleanup" in worker_names
    # generated_at 序列化为带 Z 的 UTC ISO 串。
    assert payload["generated_at"].endswith("Z")
