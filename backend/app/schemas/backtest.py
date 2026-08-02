"""信号有效性回测响应模型。

字段命名统一英文，纯读汇总结构：命中率、平均前视收益、按 importance
（信号置信度）/ score（情绪分数绝对值）分桶的收益，以及样本量 / 可评估率等
诊断计数。Phase 2（工作块 E）additive 扩展：超额收益（代理基准）、陈旧快照
过滤计数、样本相关性诊断（per-news 命中率）、score 分桶、回测校准。旧字段
全部保留、不改语义。
"""

from pydantic import BaseModel, Field

from app.schemas.common import UTCDateTime


class SignalDirectionStatsView(BaseModel):
    """单个方向（利好 / 利空）的命中统计。"""

    label: str
    # 可评估样本量（news x symbol 对，已成功取到基准价与前视价）
    sample_count: int
    # 命中样本量：利好取后续上涨、利空取后续下跌
    hit_count: int
    # 命中率；sample_count 为 0 时为 null，避免除零
    hit_rate: float | None = None
    # 平均前视收益率（原始价格变动方向，未按信号方向取绝对值）
    avg_forward_return: float | None = None
    # 平均超额收益率 = forward_return - benchmark_return（代理基准，见 benchmark_note）
    avg_excess_return: float | None = None


class ImportanceBucketStatsView(BaseModel):
    """按信号置信度分桶（high / medium / low / unknown）的平均前视收益。

    局限：signal_confidence 当前多为 |sentiment_score| 的线性变换，信息量有限；
    建议优先参考 score_buckets，该桶字段仅为兼容前端现状保留。
    """

    bucket: str
    sample_count: int
    avg_forward_return: float | None = None
    avg_excess_return: float | None = None


class ScoreBucketStatsView(BaseModel):
    """按 |sentiment_score| 分桶（边界 0.2/0.4/0.6/0.8）的命中率与收益。"""

    range_label: str
    sample_count: int
    hit_rate: float | None = None
    avg_forward_return: float | None = None
    avg_excess_return: float | None = None


class CalibrationMappingEntryView(BaseModel):
    """单个 score 桶的经验命中率 -> 校准置信度映射。"""

    score_min: float
    score_max: float
    sample_count: int
    hit_rate: float | None = None
    calibrated_confidence: float
    # 样本数 < 30：命中率统计噪声大，calibrated_confidence 回退到旧线性公式的桶中值。
    low_sample: bool


class SentimentCalibrationView(BaseModel):
    """回测顺带重算的置信度校准结果（同步落盘 backend/data/research/sentiment_calibration.json）。"""

    generated_at: UTCDateTime
    market: str | None = None
    window_days: int
    horizon: str
    mapping: list[CalibrationMappingEntryView] = Field(default_factory=list)
    # 最小的、经验命中率 >= 0.55 且样本充足（>=30）的 |score| 桶下界；不存在则 null。
    suggested_positive_threshold: float | None = None
    suggested_negative_threshold: float | None = None


class BacktestSummaryView(BaseModel):
    """回测汇总响应。"""

    market: str | None = None
    window_days: int
    horizon: str
    generated_at: UTCDateTime
    # 候选样本量（窗口内、含方向情绪、可映射 symbol 的 news x symbol 对）
    total_signals: int
    # 可评估样本量（成功取到基准价 + 前视价）
    evaluable_count: int
    # 因快照稀疏/陈旧被跳过的样本量（含 skipped_stale_count）
    skipped_count: int
    # skipped_count 的子集：因 baseline 快照距发布时间超过
    # settings.signal_backtest_max_snapshot_age_hours 而跳过的样本量
    skipped_stale_count: int = 0
    # 可评估率 = evaluable_count / total_signals；无候选时为 null
    evaluable_rate: float | None = None
    # 代理市场基准的平均前视收益值；无可评样本时为 null
    benchmark_return: float | None = None
    # 基准来源说明（如实标注为代理基准，而非真实指数收益）
    benchmark_note: str = ""
    # 全部可评样本的平均超额收益（overall，各方向/各桶见对应结构）
    avg_excess_return: float | None = None
    # 可评样本覆盖的不重复新闻数（同一条新闻的多只股票样本不独立）
    distinct_news_count: int = 0
    # 先对每条新闻的（多样本）命中取均值，再对新闻等权求均值的命中率
    per_news_hit_rate: float | None = None
    positive: SignalDirectionStatsView
    negative: SignalDirectionStatsView
    importance_buckets: list[ImportanceBucketStatsView] = Field(default_factory=list)
    score_buckets: list[ScoreBucketStatsView] = Field(default_factory=list)
    calibration: SentimentCalibrationView | None = None
