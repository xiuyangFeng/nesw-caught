"""信号有效性回测响应模型。

字段命名统一英文，纯读汇总结构：命中率、平均前视收益、按 importance
（信号置信度）分桶的收益，以及样本量 / 可评估率等诊断计数。
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


class ImportanceBucketStatsView(BaseModel):
    """按信号置信度分桶（high / medium / low / unknown）的平均前视收益。"""

    bucket: str
    sample_count: int
    avg_forward_return: float | None = None


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
    # 因快照稀疏被跳过的样本量
    skipped_count: int
    # 可评估率 = evaluable_count / total_signals；无候选时为 null
    evaluable_rate: float | None = None
    positive: SignalDirectionStatsView
    negative: SignalDirectionStatsView
    importance_buckets: list[ImportanceBucketStatsView] = Field(default_factory=list)
