from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sentiment_eval_run import SentimentEvalRun


class SentimentEvalRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_run(
        self,
        *,
        batch_id: str,
        created_at: datetime,
        dataset_path: str,
        dataset_hash: str,
        sample_count: int,
        model_name: str,
        config_json: str | None,
        accuracy: float,
        macro_f1: float,
        importance_weighted_accuracy: float | None,
        per_label_json: str,
        confusion_json: str,
        note: str | None,
    ) -> SentimentEvalRun:
        row = SentimentEvalRun(
            batch_id=batch_id,
            created_at=created_at,
            dataset_path=dataset_path,
            dataset_hash=dataset_hash,
            sample_count=sample_count,
            model_name=model_name,
            config_json=config_json,
            accuracy=accuracy,
            macro_f1=macro_f1,
            importance_weighted_accuracy=importance_weighted_accuracy,
            per_label_json=per_label_json,
            confusion_json=confusion_json,
            note=note,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def _rows_desc(self) -> list[SentimentEvalRun]:
        stmt = select(SentimentEvalRun).order_by(
            SentimentEvalRun.created_at.desc(), SentimentEvalRun.id.desc()
        )
        return list(self.session.scalars(stmt))

    def list_recent_batches(self, *, limit: int = 20) -> list[list[SentimentEvalRun]]:
        """最近 ``limit`` 个 batch，每个 batch 内部按插入顺序（id 升序）排列。

        批次粒度按 ``batch_id`` 分组，批次顺序按批次内最新一行的 (created_at, id)
        降序——即最近触发的评测排在最前面。一次性把全表拉进内存分组，评测记录
        规模（每次评测 1~3 行、触发频率为人工点击）远小到不需要按批分页查询。
        """
        rows = self._rows_desc()
        order: list[str] = []
        grouped: dict[str, list[SentimentEvalRun]] = {}
        for row in rows:
            if row.batch_id not in grouped:
                grouped[row.batch_id] = []
                order.append(row.batch_id)
            grouped[row.batch_id].append(row)

        batches = [list(reversed(grouped[batch_id])) for batch_id in order[:limit]]
        return batches

    def get_latest_batch(self) -> list[SentimentEvalRun]:
        batches = self.list_recent_batches(limit=1)
        return batches[0] if batches else []

    def get_previous_batch_for_dataset_hash(
        self,
        *,
        dataset_hash: str,
        exclude_batch_id: str,
        search_limit: int = 50,
    ) -> list[SentimentEvalRun]:
        """在时间上早于 ``exclude_batch_id`` 的最近一个 dataset_hash 相同的 batch。"""
        for batch in self.list_recent_batches(limit=search_limit):
            if not batch:
                continue
            if batch[0].batch_id == exclude_batch_id:
                continue
            if batch[0].dataset_hash == dataset_hash:
                return batch
        return []
