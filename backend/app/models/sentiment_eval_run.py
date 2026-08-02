from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SentimentEvalRun(Base):
    """一次 POST /eval/sentiment/run 触发的单个模型评测结果（同 batch_id 下多条）。

    情绪评测重构 Phase 1 工作块 B：落库 + 历史 + 回归对比，参见设计文档
    docs/superpowers/specs/2026-08-02-sentiment-eval-revamp-design.md「新数据表」节。

    注：设计文档「新数据表」表格未单列 importance_weighted_accuracy，但
    `SentimentEvaluationMetrics`（同一份契约的「SentimentEvalResponse 扩展」节）
    要求该字段随每个 model run 一起返回；为了 GET 只读回放能完整重建
    `SentimentModelRun.metrics`（而不是每次都重新跑一遍分类），这里额外加了
    这一列。属于对文档遗漏的补齐而非违背契约——语义上仍是"单个 model run 的
    一个指标"，不引入任何新概念。
    """

    __tablename__ = "sentiment_eval_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    dataset_path: Mapped[str] = mapped_column(String(512))
    dataset_hash: Mapped[str] = mapped_column(String(16), index=True)
    sample_count: Mapped[int] = mapped_column(Integer())
    # rule-baseline / llm:<provider>/<model> / hybrid:<provider>/<model> /
    # rule-sensitive (±0.10)（无 LLM 配置时的 legacy 降级 run）。
    model_name: Mapped[str] = mapped_column(String(128))
    config_json: Mapped[str | None] = mapped_column(Text(), default=None)
    accuracy: Mapped[float] = mapped_column(Float())
    macro_f1: Mapped[float] = mapped_column(Float())
    # 有 importance 标注样本时的加权准确率；数据集完全没有标注时为 None。
    importance_weighted_accuracy: Mapped[float | None] = mapped_column(Float(), default=None)
    # JSON 序列化的 list[SentimentLabelMetrics]。
    per_label_json: Mapped[str] = mapped_column(Text())
    # JSON 序列化的 confusion_matrix[actual][predicted] = 计数。
    confusion_json: Mapped[str] = mapped_column(Text())
    # 整个 batch 的说明文案（LLM 单样本失败回退计数、legacy 降级提示、回归提示等），
    # 同一 batch 下所有行写入同一份文案，GET 只读时任取一行即可还原。
    note: Mapped[str | None] = mapped_column(Text(), default=None)
