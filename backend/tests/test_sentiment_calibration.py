"""情绪置信度校准服务测试（工作块 E5，TDD）。

覆盖：
- build_calibration：按 score 桶经验命中率生成映射；样本量 < 30 的桶标记
  low_sample 并回退旧线性公式取值；suggested_positive/negative_threshold 取
  最小的、命中率 >= 0.55 且样本充足的桶下界。
- save_calibration 原子写 + load_calibration 读回一致。
- get_calibrated_confidence：懒缓存命中；文件 mtime 变化后重新加载；文件/桶
  缺失时返回 None（调用方回退旧公式）。
- 生产 hook（news_signal_classifier）：sentiment_confidence_calibration_enabled
  默认 False 时 signal_confidence 与改造前完全一致；开启且校准命中时改用校准值。

全程不联网、不写入仓库真实的 backend/data/research/sentiment_calibration.json
（用 tmp_path 传入自定义 path，避免测试间与真实回测落盘互相污染）。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.config import Settings
from app.services import sentiment_calibration as calib


def _score_bucket(range_label: str, sample_count: int, hit_rate: float | None) -> dict:
    return {
        "range_label": range_label,
        "sample_count": sample_count,
        "hit_rate": hit_rate,
        "avg_forward_return": 0.01,
        "avg_excess_return": 0.005,
    }


def _backtest_result(score_buckets: list[dict]) -> dict:
    return {
        "market": "us",
        "window_days": 30,
        "horizon": "1d",
        "generated_at": datetime(2026, 8, 2, tzinfo=UTC),
        "score_buckets": score_buckets,
    }


@pytest.fixture(autouse=True)
def _reset_calibration_cache():
    calib.clear_cache()
    yield
    calib.clear_cache()


def test_build_calibration_uses_empirical_hit_rate_for_well_sampled_buckets() -> None:
    """样本量充足（>=30）的桶，calibrated_confidence 直接取经验命中率。"""
    result = _backtest_result(
        [
            _score_bucket("0.0-0.2", 40, 0.5),
            _score_bucket("0.2-0.4", 35, 0.62),
        ]
    )
    calibration = calib.build_calibration(result)

    mapping = {(m["score_min"], m["score_max"]): m for m in calibration["mapping"]}
    entry = mapping[(0.0, 0.2)]
    assert entry["low_sample"] is False
    assert entry["calibrated_confidence"] == pytest.approx(0.5)

    entry2 = mapping[(0.2, 0.4)]
    assert entry2["low_sample"] is False
    assert entry2["calibrated_confidence"] == pytest.approx(0.62)


def test_build_calibration_low_sample_bucket_falls_back_to_linear_formula() -> None:
    """样本量 < 30 的桶标记 low_sample=True，且 calibrated_confidence 回退旧线性公式桶中值。"""
    result = _backtest_result([_score_bucket("0.4-0.6", 5, 0.9)])
    calibration = calib.build_calibration(result)

    entry = calibration["mapping"][0]
    assert entry["low_sample"] is True
    # 旧公式：0.35 + min(|score_mid|,1.0)*0.5，score_mid=(0.4+0.6)/2=0.5 -> 0.35+0.25=0.6
    assert entry["calibrated_confidence"] == pytest.approx(0.6)


def test_build_calibration_null_hit_rate_bucket_treated_as_low_sample() -> None:
    """空桶（sample_count=0，hit_rate=None）同样回退线性公式，不当作高置信度处理。"""
    result = _backtest_result([_score_bucket("0.6-0.8", 0, None)])
    calibration = calib.build_calibration(result)

    entry = calibration["mapping"][0]
    assert entry["low_sample"] is True
    # score_mid = (0.6+0.8)/2 = 0.7 -> 0.35 + 0.35 = 0.7
    assert entry["calibrated_confidence"] == pytest.approx(0.7)


def test_build_calibration_suggested_thresholds_pick_lowest_qualifying_bucket() -> None:
    """建议阈值 = 最小的、命中率 >= 0.55 且样本充足的桶下界；正负阈值对称取同一个 |score| 下界。"""
    result = _backtest_result(
        [
            _score_bucket("0.0-0.2", 40, 0.50),  # 不合格：命中率 < 0.55
            _score_bucket("0.2-0.4", 40, 0.56),  # 合格：应被选中（最小下界）
            _score_bucket("0.4-0.6", 40, 0.80),  # 合格但下界更大，不选
        ]
    )
    calibration = calib.build_calibration(result)

    assert calibration["suggested_positive_threshold"] == pytest.approx(0.2)
    assert calibration["suggested_negative_threshold"] == pytest.approx(0.2)


def test_build_calibration_no_qualifying_bucket_returns_none_thresholds() -> None:
    """没有桶同时满足样本充足 + 命中率 >= 0.55 时，建议阈值为 None。"""
    result = _backtest_result(
        [
            _score_bucket("0.0-0.2", 40, 0.50),
            _score_bucket("0.2-0.4", 5, 0.90),  # 命中率高但样本不足
        ]
    )
    calibration = calib.build_calibration(result)

    assert calibration["suggested_positive_threshold"] is None
    assert calibration["suggested_negative_threshold"] is None


def test_save_and_load_calibration_roundtrip(tmp_path: Path) -> None:
    """原子写入后可直接读回，字段与写入前一致（datetime 序列化为 ISO 字符串）。"""
    target = tmp_path / "sentiment_calibration.json"
    result = _backtest_result([_score_bucket("0.0-0.2", 40, 0.5)])
    calibration = calib.build_calibration(result)

    calib.save_calibration(calibration, path=target)
    assert target.exists()

    loaded = calib.load_calibration(path=target)
    assert loaded is not None
    assert loaded["market"] == "us"
    assert loaded["window_days"] == 30
    assert loaded["mapping"][0]["calibrated_confidence"] == pytest.approx(0.5)
    # generated_at 序列化为字符串（JSON 无原生 datetime 类型）
    assert isinstance(loaded["generated_at"], str)


def test_save_calibration_no_leftover_tmp_file(tmp_path: Path) -> None:
    """原子写入（tempfile + os.replace）后，目录内不应残留 .tmp 临时文件。"""
    target = tmp_path / "sentiment_calibration.json"
    calibration = calib.build_calibration(_backtest_result([_score_bucket("0.0-0.2", 40, 0.5)]))

    calib.save_calibration(calibration, path=target)

    leftovers = [p for p in tmp_path.iterdir() if p.name != target.name]
    assert leftovers == []


def test_get_calibrated_confidence_returns_none_when_file_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.json"
    assert calib.get_calibrated_confidence(0.5, path=missing) is None


def test_get_calibrated_confidence_matches_bucket_and_boundaries(tmp_path: Path) -> None:
    """score 落在 [score_min, score_max) 区间；末桶（0.8-1.0）含右端 1.0。"""
    target = tmp_path / "sentiment_calibration.json"
    result = _backtest_result(
        [
            _score_bucket("0.0-0.2", 40, 0.5),
            _score_bucket("0.8-1.0", 40, 0.9),
        ]
    )
    calib.save_calibration(calib.build_calibration(result), path=target)

    assert calib.get_calibrated_confidence(0.1, path=target) == pytest.approx(0.5)
    # 负分：按 |score| 查桶
    assert calib.get_calibrated_confidence(-0.1, path=target) == pytest.approx(0.5)
    assert calib.get_calibrated_confidence(1.0, path=target) == pytest.approx(0.9)
    # 未命中任何桶（0.2-0.4/0.4-0.6/0.6-0.8 均缺失）时返回 None
    assert calib.get_calibrated_confidence(0.5, path=target) is None


def test_get_calibrated_confidence_lazy_cache_hits_without_reread(tmp_path: Path, monkeypatch) -> None:
    """mtime 未变时命中缓存，不重新读盘（用 read_text 调用计数验证）。"""
    target = tmp_path / "sentiment_calibration.json"
    result = _backtest_result([_score_bucket("0.0-0.2", 40, 0.5)])
    calib.save_calibration(calib.build_calibration(result), path=target)

    read_calls = {"count": 0}
    original_read_text = Path.read_text

    def counting_read_text(self, *args, **kwargs):
        if self == target:
            read_calls["count"] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)

    first = calib.get_calibrated_confidence(0.1, path=target)
    second = calib.get_calibrated_confidence(0.1, path=target)

    assert first == second == pytest.approx(0.5)
    assert read_calls["count"] == 1


def test_get_calibrated_confidence_reloads_after_mtime_change(tmp_path: Path) -> None:
    """文件内容变化（mtime 更新）后，缓存失效，返回新值而非陈旧缓存。"""
    target = tmp_path / "sentiment_calibration.json"
    first_result = _backtest_result([_score_bucket("0.0-0.2", 40, 0.5)])
    calib.save_calibration(calib.build_calibration(first_result), path=target)
    assert calib.get_calibrated_confidence(0.1, path=target) == pytest.approx(0.5)

    second_result = _backtest_result([_score_bucket("0.0-0.2", 40, 0.9)])
    calib.save_calibration(calib.build_calibration(second_result), path=target)
    # 确保 mtime 严格前进（部分文件系统 mtime 精度为 1 秒）。
    import os
    import time

    later = target.stat().st_mtime + 2
    os.utime(target, (later, later))
    time.sleep(0)  # no-op，保持与其它测试风格一致（不做真实 sleep 等待）

    assert calib.get_calibrated_confidence(0.1, path=target) == pytest.approx(0.9)


def test_get_calibrated_confidence_missing_bucket_key_falls_back_to_none(tmp_path: Path) -> None:
    """文件存在但 mapping 结构异常（如空列表）时安全返回 None，不抛异常。"""
    target = tmp_path / "sentiment_calibration.json"
    target.write_text(json.dumps({"mapping": []}), encoding="utf-8")
    assert calib.get_calibrated_confidence(0.3, path=target) is None


def test_get_calibrated_confidence_corrupt_json_returns_none(tmp_path: Path) -> None:
    target = tmp_path / "sentiment_calibration.json"
    target.write_text("{not valid json", encoding="utf-8")
    assert calib.get_calibrated_confidence(0.3, path=target) is None


# —— 生产 hook：news_signal_classifier.classify() 的 signal_confidence 计算 ——


def test_classifier_confidence_unchanged_when_calibration_disabled_by_default(monkeypatch) -> None:
    """默认 sentiment_confidence_calibration_enabled=False 时，代码路径与改造前完全一致。"""
    from app.db.session import SessionLocal
    from app.services.news_signal_classifier import NewsSignalClassifier

    settings = Settings(sentiment_confidence_calibration_enabled=False)
    monkeypatch.setattr("app.services.news_signal_classifier.get_settings", lambda: settings)

    calls = {"count": 0}

    def fail_if_called(*args, **kwargs):
        calls["count"] += 1
        return 0.999  # 明显偏离旧公式的值，若被调用会让下面的断言失败

    monkeypatch.setattr(
        "app.services.news_signal_classifier.get_calibrated_confidence", fail_if_called
    )

    with SessionLocal() as session:
        classifier = NewsSignalClassifier(session)
        result = classifier.classify(
            title="strong growth beat", summary=None, body=None, allow_llm=False
        )

    # 旧公式：score 由 POSITIVE_TERMS 累加得到（strong=0.6, growth=0.6, beat=0.7 -> 1.9，clip 到 1.0）
    # confidence = min(0.95, 0.35 + 1.0*0.5) = 0.85
    assert result.signal_confidence == pytest.approx(0.85)
    assert calls["count"] == 0


def test_classifier_confidence_uses_calibration_when_enabled_and_bucket_hit(monkeypatch) -> None:
    """开启开关且校准命中桶时，signal_confidence 改用校准值而非旧线性公式。"""
    from app.db.session import SessionLocal
    from app.services.news_signal_classifier import NewsSignalClassifier

    settings = Settings(sentiment_confidence_calibration_enabled=True)
    monkeypatch.setattr("app.services.news_signal_classifier.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.services.news_signal_classifier.get_calibrated_confidence", lambda score: 0.42
    )

    with SessionLocal() as session:
        classifier = NewsSignalClassifier(session)
        result = classifier.classify(
            title="strong growth beat", summary=None, body=None, allow_llm=False
        )

    assert result.signal_confidence == pytest.approx(0.42)


def test_classifier_confidence_falls_back_when_calibration_enabled_but_bucket_missing(
    monkeypatch,
) -> None:
    """开关开启但校准查不到桶（返回 None）时，回退旧线性公式，行为与关闭时一致。"""
    from app.db.session import SessionLocal
    from app.services.news_signal_classifier import NewsSignalClassifier

    settings = Settings(sentiment_confidence_calibration_enabled=True)
    monkeypatch.setattr("app.services.news_signal_classifier.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.services.news_signal_classifier.get_calibrated_confidence", lambda score: None
    )

    with SessionLocal() as session:
        classifier = NewsSignalClassifier(session)
        result = classifier.classify(
            title="strong growth beat", summary=None, body=None, allow_llm=False
        )

    assert result.signal_confidence == pytest.approx(0.85)
