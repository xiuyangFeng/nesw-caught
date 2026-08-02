"""GET/POST /api/eval/sentiment[/run] 路由测试：真 A/B、落库、只读回放、历史、回归。

情绪评测重构 Phase 1 工作块 B。金标数据集用内置演示集
(data/research/sentiment_gold_benchmark.json)，规则分类器纯离线确定性可复现，
不联网；LLM 相关分支通过 mock build_provider 覆盖，同样不联网。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from app.db.session import SessionLocal, engine
from app.main import app
from app.models.sentiment_eval_run import SentimentEvalRun
from app.repositories.sentiment_eval_run_repository import SentimentEvalRunRepository
from app.services.news_sentiment_dataset import default_gold_dataset_path
from app.services.sentiment_eval_persistence import compute_dataset_hash


def _cleanup_llm_config_table() -> None:
    inspector = inspect(engine)
    if "llm_provider_config" not in inspector.get_table_names():
        return
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM llm_provider_config"))


def _cleanup_sentiment_eval_run_table() -> None:
    with SessionLocal() as session:
        session.query(SentimentEvalRun).delete()
        session.commit()


def _reset_state() -> None:
    _cleanup_llm_config_table()
    _cleanup_sentiment_eval_run_table()


def _default_dataset_hash() -> str:
    return compute_dataset_hash(default_gold_dataset_path())


def test_get_sentiment_eval_prompts_to_run_when_no_batch_persisted() -> None:
    _reset_state()
    client = TestClient(app)

    response = client.get("/api/eval/sentiment")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["primary"] is None
    assert payload["comparison"] is None
    assert payload["runs"] == []
    assert payload["llm_available"] is False
    assert payload["history"] == []
    assert payload["regression"] is None
    assert payload["evaluated_at"] is None
    assert "重新评测" in payload["note"]


def test_post_run_without_llm_falls_back_to_legacy_threshold_ab() -> None:
    _reset_state()
    client = TestClient(app)

    response = client.post("/api/eval/sentiment/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["llm_available"] is False
    assert payload["evaluated_at"] is not None

    run_names = [run["model_name"] for run in payload["runs"]]
    assert run_names == ["rule-baseline", "rule-sensitive (±0.10)"]
    assert payload["primary"]["model_name"] == "rule-baseline"
    assert payload["comparison"]["model_a"]["model_name"] == "rule-baseline"
    assert payload["comparison"]["model_b"]["model_name"] == "rule-sensitive (±0.10)"
    assert "未配置 LLM" in payload["note"]

    # metrics 结构完整包含新增字段。
    metrics = payload["runs"][0]["metrics"]
    assert "importance_weighted_accuracy" in metrics
    assert set(metrics.keys()) >= {
        "accuracy",
        "macro_f1",
        "sample_count",
        "per_label",
        "confusion_matrix",
    }

    # 落库后 GET 只读回放同一个 batch。
    follow_up = client.get("/api/eval/sentiment")
    assert follow_up.status_code == 200
    follow_up_payload = follow_up.json()
    assert follow_up_payload["available"] is True
    assert [run["model_name"] for run in follow_up_payload["runs"]] == run_names
    assert follow_up_payload["primary"]["model_name"] == "rule-baseline"
    assert follow_up_payload["note"] == payload["note"]
    assert len(follow_up_payload["history"]) == 1
    assert follow_up_payload["history"][0]["sample_count"] == payload["sample_count"]


def test_post_run_with_active_llm_config_appends_llm_and_hybrid_runs() -> None:
    _reset_state()
    client = TestClient(app)

    llm_config_response = client.post(
        "/api/llm/config",
        json={
            "provider_name": "openai_compatible",
            "display_name": "Test Provider",
            "base_url": "https://example-llm.test/v1",
            "model_name": "test-model",
            "api_key": "sk-test-secret",
        },
    )
    assert llm_config_response.status_code == 200

    fake_sentiment_provider = SimpleNamespace(
        analyze_json=lambda **kwargs: {"sentiment_label": "positive", "sentiment_score": 0.6}
    )
    fake_refine_provider = SimpleNamespace(
        analyze_json=lambda **kwargs: {
            "sentiment_label": "positive",
            "sentiment_score": 0.6,
            "summary": "s",
            "keywords": [],
            "topic_title_hint": "t",
            "takeaway": "ok",
        }
    )

    with (
        patch(
            "app.services.news_sentiment_llm_classifier.build_provider",
            return_value=fake_sentiment_provider,
        ),
        patch(
            "app.services.news_signal_classifier.build_provider",
            return_value=fake_refine_provider,
        ),
        patch(
            "app.services.news_signal_classifier.get_settings",
            return_value=SimpleNamespace(ai_enabled=True),
        ),
    ):
        response = client.post("/api/eval/sentiment/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["llm_available"] is True

    run_names = [run["model_name"] for run in payload["runs"]]
    assert run_names[0] == "rule-baseline"
    assert run_names[1] == "llm:openai_compatible/test-model"
    assert run_names[2] == "hybrid:openai_compatible/test-model"

    assert payload["comparison"]["model_b"]["model_name"] == "llm:openai_compatible/test-model"

    follow_up = client.get("/api/eval/sentiment")
    assert follow_up.status_code == 200
    assert [run["model_name"] for run in follow_up.json()["runs"]] == run_names


def test_post_run_with_llm_failures_reports_fallback_count_in_note() -> None:
    _reset_state()
    client = TestClient(app)

    llm_config_response = client.post(
        "/api/llm/config",
        json={
            "provider_name": "openai_compatible",
            "display_name": "Test Provider",
            "base_url": "https://example-llm.test/v1",
            "model_name": "test-model",
            "api_key": "sk-test-secret",
        },
    )
    assert llm_config_response.status_code == 200

    def _always_fail(**kwargs):
        raise RuntimeError("simulated llm outage")

    fake_sentiment_provider = SimpleNamespace(analyze_json=_always_fail)

    with (
        patch(
            "app.services.news_sentiment_llm_classifier.build_provider",
            return_value=fake_sentiment_provider,
        ),
        patch(
            "app.services.news_signal_classifier.get_settings",
            return_value=SimpleNamespace(ai_enabled=False),
        ),
    ):
        response = client.post("/api/eval/sentiment/run")

    assert response.status_code == 200
    payload = response.json()
    llm_run = next(run for run in payload["runs"] if run["model_name"].startswith("llm:"))
    # 所有样本的 LLM 分类都失败 => 回退规则分类，且回退计数应等于样本总数，写进 note。
    assert str(payload["sample_count"]) in payload["note"]
    assert "回退规则" in payload["note"]
    # 全部回退规则分类，llm run 的预测应与 rule-baseline 完全一致。
    rule_run = next(run for run in payload["runs"] if run["model_name"] == "rule-baseline")
    assert llm_run["metrics"]["accuracy"] == rule_run["metrics"]["accuracy"]


def test_post_run_detects_regression_against_previous_batch_with_same_dataset_hash() -> None:
    _reset_state()
    client = TestClient(app)

    dataset_hash = _default_dataset_hash()
    with SessionLocal() as session:
        repo = SentimentEvalRunRepository(session)
        # 人为写入一个"上一批"评测记录：同 dataset_hash，rule-baseline 的 macro_f1
        # 故意设成 1.0（真实规则分类器几乎不可能在演示金标集上打满分），
        # 保证这次真实评测出的 macro_f1 一定比它低超过 0.02 阈值，从而稳定触发回归判定。
        repo.add_run(
            batch_id="artificial-previous-batch",
            created_at=datetime.now(UTC) - timedelta(hours=1),
            dataset_path=str(default_gold_dataset_path()),
            dataset_hash=dataset_hash,
            sample_count=20,
            model_name="rule-baseline",
            config_json=None,
            accuracy=1.0,
            macro_f1=1.0,
            importance_weighted_accuracy=None,
            per_label_json="[]",
            confusion_json="{}",
            note=None,
        )
        session.commit()

    response = client.post("/api/eval/sentiment/run")

    assert response.status_code == 200
    payload = response.json()
    regression = payload["regression"]
    assert regression is not None
    assert regression["model_name"] == "rule-baseline"
    assert regression["previous_macro_f1"] == 1.0
    assert regression["regressed"] is True
    assert regression["delta"] < -0.02

    follow_up = client.get("/api/eval/sentiment")
    assert follow_up.json()["regression"]["model_name"] == "rule-baseline"


def test_two_consecutive_runs_without_llm_show_no_regression() -> None:
    _reset_state()
    client = TestClient(app)

    first = client.post("/api/eval/sentiment/run")
    assert first.status_code == 200
    # 规则分类器离线确定性可复现：连续两次评测同一份金标集，rule-baseline 结果相同。
    second = client.post("/api/eval/sentiment/run")
    assert second.status_code == 200

    payload = second.json()
    assert payload["regression"] is not None
    assert payload["regression"]["delta"] == 0.0
    assert payload["regression"]["regressed"] is False
    assert len(payload["history"]) == 2
