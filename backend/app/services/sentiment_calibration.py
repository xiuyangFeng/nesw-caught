"""情绪置信度校准（工作块 E5）。

背景：`news_signal_classifier.py` 当前的 `signal_confidence = 0.35 +
min(|score|,1.0)*0.5` 只是 |score| 的线性变换，取值恒在 [0.35, 0.95]，low
桶（<0.33）恒空，未反映真实的方向命中率。本模块基于回测按 |sentiment_score|
分桶的经验命中率生成校准映射：

- `build_calibration(backtest_result)`：从一次回测结果的 `score_buckets` 生成
  映射；样本数 < 30 的桶经验命中率噪声大，`calibrated_confidence` 回退到旧线性
  公式在该桶中值处的取值，并标记 `low_sample=True`。
- `save_calibration` / `load_calibration`：JSON 落盘于
  `backend/data/research/sentiment_calibration.json`；写入走临时文件 + `os.replace`
  原子替换，避免并发读到半写文件。
- `get_calibrated_confidence(score)`：生产 hook 用，模块级懒缓存 + 文件 mtime
  失效；文件缺失/桶未命中时返回 None，由调用方回退旧公式。

全模块不导入 `signal_backtest.py`（避免循环依赖）：`build_calibration` 只依赖
传入的 dict 结构（`score_buckets` 的 `range_label/sample_count/hit_rate` 字段），
不直接依赖该模块的内部类型。
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

# 桶样本量门槛：低于此值经验命中率统计噪声太大，回退线性公式。
MIN_SAMPLE_COUNT = 30
# 建议阈值门槛：经验命中率达到此值才认为该分数量级"可信地"预示方向。
HIT_RATE_THRESHOLD = 0.55


def default_calibration_path() -> Path:
    """校准结果落盘路径（backend/data/research/sentiment_calibration.json）。"""
    return Path(__file__).resolve().parents[2] / "data" / "research" / "sentiment_calibration.json"


def _linear_fallback_confidence(score_mid: float) -> float:
    """旧线性公式（news_signal_classifier._classify）在给定分数处的取值，用于低样本回退。"""
    return round(min(0.95, 0.35 + min(abs(score_mid), 1.0) * 0.5), 4)


def _parse_range_label(range_label: str) -> tuple[float, float]:
    low_str, high_str = range_label.split("-", 1)
    return float(low_str), float(high_str)


def build_calibration(backtest_result: dict) -> dict:
    """从一次回测结果（含 `score_buckets`）生成校准映射。

    `backtest_result` 需含 `score_buckets`（list[dict]，每项含 range_label /
    sample_count / hit_rate）、`market` / `window_days` / `horizon` / `generated_at`
    （用于记录本次校准的来源上下文）。
    """
    score_buckets = backtest_result.get("score_buckets") or []
    generated_at = backtest_result.get("generated_at")
    if isinstance(generated_at, datetime):
        generated_at_value = generated_at
    else:
        generated_at_value = datetime.now(UTC)

    mapping: list[dict] = []
    suggested_threshold: float | None = None

    for bucket in score_buckets:
        score_min, score_max = _parse_range_label(bucket["range_label"])
        sample_count = int(bucket.get("sample_count") or 0)
        hit_rate = bucket.get("hit_rate")
        low_sample = sample_count < MIN_SAMPLE_COUNT or hit_rate is None

        if low_sample:
            score_mid = (score_min + score_max) / 2
            calibrated_confidence = _linear_fallback_confidence(score_mid)
        else:
            calibrated_confidence = round(float(hit_rate), 4)

        mapping.append(
            {
                "score_min": score_min,
                "score_max": score_max,
                "sample_count": sample_count,
                "hit_rate": hit_rate,
                "calibrated_confidence": calibrated_confidence,
                "low_sample": low_sample,
            }
        )

        if (
            suggested_threshold is None
            and not low_sample
            and hit_rate is not None
            and hit_rate >= HIT_RATE_THRESHOLD
        ):
            suggested_threshold = score_min

    # score_buckets 基于 |sentiment_score|（不区分方向），命中率同时适用于
    # positive（score >= threshold）与 negative（score <= -threshold）两侧，
    # 因此正负建议阈值取同一个 |score| 下界。
    return {
        "generated_at": generated_at_value,
        "market": backtest_result.get("market"),
        "window_days": backtest_result.get("window_days"),
        "horizon": backtest_result.get("horizon"),
        "mapping": mapping,
        "suggested_positive_threshold": suggested_threshold,
        "suggested_negative_threshold": suggested_threshold,
    }


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def save_calibration(data: dict, *, path: Path | None = None) -> None:
    """原子写入校准结果（临时文件 + os.replace），避免并发读到半写文件。"""
    target = path or default_calibration_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, default=_json_default)
        os.replace(tmp_path, target)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def load_calibration(*, path: Path | None = None) -> dict | None:
    """直接读盘（不走缓存），供路由/测试同步校验落盘内容。"""
    target = path or default_calibration_path()
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# —— 生产 hook 用：模块级懒缓存 + 文件 mtime 失效 ——
_cache_lock = Lock()
_cache: dict[str, tuple[float, dict]] = {}


def clear_cache() -> None:
    """清空懒缓存（测试用；生产路径靠 mtime 失效即可，通常无需手动调用）。"""
    with _cache_lock:
        _cache.clear()


def _load_cached(path: Path) -> dict | None:
    key = str(path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        with _cache_lock:
            _cache.pop(key, None)
        return None

    with _cache_lock:
        cached = _cache.get(key)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    with _cache_lock:
        _cache[key] = (mtime, data)
    return data


def get_calibrated_confidence(score: float, *, path: Path | None = None) -> float | None:
    """按 |score| 查校准映射，返回 calibrated_confidence；文件/桶缺失返回 None（调用方回退旧公式）。"""
    target = path or default_calibration_path()
    data = _load_cached(target)
    if not data:
        return None

    mapping = data.get("mapping") or []
    abs_score = min(abs(score), 1.0)
    for entry in mapping:
        score_min = entry.get("score_min")
        score_max = entry.get("score_max")
        if score_min is None or score_max is None:
            continue
        is_last_bucket = score_max >= 1.0 - 1e-9
        in_bucket = score_min <= abs_score < score_max or (
            is_last_bucket and score_min <= abs_score <= score_max + 1e-9
        )
        if in_bucket:
            confidence = entry.get("calibrated_confidence")
            return float(confidence) if confidence is not None else None
    return None
