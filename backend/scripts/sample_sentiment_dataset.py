"""从 DB 按 市场 x 现有 sentiment_label 分层采样新闻，产出待预标注的候选 JSONL。

镜像 backend/scripts/sample_market_relevance_dataset.py 的风格：纯查询/采样逻辑
拆成可测函数，main() 只负责拿 DB session、解析命令行参数、写文件。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from scripts.sentiment_dataset_lib import SentimentCandidate, write_jsonl

DEFAULT_LIMIT = 300
DEFAULT_POOL_LIMIT = 6000
DEFAULT_BODY_EXCERPT_CHARS = 1500
DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "research" / "sentiment_dataset_candidates.jsonl"
)
UNLABELED_BUCKET = "unlabeled"


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be > 0")
    return parsed


def _query_candidate_news_items(session: Session, pool_limit: int) -> list[NewsItem]:
    statement = select(NewsItem).order_by(NewsItem.effective_at.desc(), NewsItem.id.desc()).limit(pool_limit)
    return list(session.scalars(statement))


def _load_body_excerpt_map(
    session: Session,
    rows: Sequence[NewsItem],
    *,
    excerpt_chars: int,
) -> dict[int, str | None]:
    news_ids = [row.id for row in rows]
    if not news_ids:
        return {}
    statement = select(ArticleContent).where(ArticleContent.news_id.in_(news_ids))
    article_map = {item.news_id: item for item in session.scalars(statement)}
    excerpts: dict[int, str | None] = {}
    for row in rows:
        article = article_map.get(row.id)
        if article is None or not article.content_text:
            excerpts[row.id] = None
            continue
        excerpts[row.id] = article.content_text[:excerpt_chars]
    return excerpts


def _content_richness_score(row: Any, body: str | None) -> int:
    """正文/摘要优先：有正文 +2，有摘要 +1，用于桶内排序。"""
    score = 0
    if body:
        score += 2
    if getattr(row, "summary", None):
        score += 1
    return score


def _bucket_key(row: Any) -> tuple[str, str]:
    market = row.market or "unknown"
    label = row.sentiment_label or UNLABELED_BUCKET
    return (market, label)


def stratified_sample(
    rows: Sequence[Any],
    body_map: dict[int, str | None],
    *,
    limit: int,
) -> list[Any]:
    """按 (market, sentiment_label) 分层：桶内正文/摘要优先 + 新→旧排序，桶间轮询直到凑够 limit。

    行对象只需鸭子类型具备 id/title/summary/market/sentiment_label/published_at/effective_at
    属性即可，方便测试用轻量 fake 对象代替真实 ORM 行。
    """
    if limit <= 0 or not rows:
        return []

    buckets: dict[tuple[str, str], list[Any]] = {}
    for row in rows:
        buckets.setdefault(_bucket_key(row), []).append(row)

    for bucket in buckets.values():
        bucket.sort(
            key=lambda row: (
                _content_richness_score(row, body_map.get(row.id)),
                row.published_at or row.effective_at,
                row.id,
            ),
            reverse=True,
        )

    ordered_keys = sorted(buckets.keys())
    cursor = {key: 0 for key in ordered_keys}
    selected: list[Any] = []
    while len(selected) < limit:
        advanced = False
        for key in ordered_keys:
            if len(selected) >= limit:
                break
            bucket = buckets[key]
            index = cursor[key]
            if index >= len(bucket):
                continue
            selected.append(bucket[index])
            cursor[key] = index + 1
            advanced = True
        if not advanced:
            break
    return selected


def _row_to_candidate(row: Any, body: str | None) -> SentimentCandidate:
    return SentimentCandidate(
        news_id=row.id,
        title=row.title,
        summary=row.summary,
        body=body,
        market=row.market,
        published_at=row.published_at.isoformat() if row.published_at else None,
        existing_sentiment_label=row.sentiment_label,
    )


def build_sentiment_dataset_candidates(
    session: Session,
    *,
    limit: int = DEFAULT_LIMIT,
    pool_limit: int = DEFAULT_POOL_LIMIT,
    body_excerpt_chars: int = DEFAULT_BODY_EXCERPT_CHARS,
) -> list[SentimentCandidate]:
    rows = _query_candidate_news_items(session, pool_limit)
    if not rows:
        return []
    body_map = _load_body_excerpt_map(session, rows, excerpt_chars=body_excerpt_chars)
    selected = stratified_sample(rows, body_map, limit=limit)
    return [_row_to_candidate(row, body_map.get(row.id)) for row in selected]


def main() -> Path | None:
    parser = argparse.ArgumentParser(
        description="从 DB 按市场 x 现有情绪标签分层采样候选新闻，供预标注/复核使用。"
    )
    parser.add_argument("--limit", type=_positive_int, default=DEFAULT_LIMIT, help="采样条数上限（默认 300）")
    parser.add_argument(
        "--pool-limit",
        type=_positive_int,
        default=DEFAULT_POOL_LIMIT,
        help="参与分层采样前，先按 effective_at 倒序取的候选池上限",
    )
    parser.add_argument("--body-excerpt-chars", type=_positive_int, default=DEFAULT_BODY_EXCERPT_CHARS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    from app.db.session import SessionLocal

    with SessionLocal() as session:
        candidates = build_sentiment_dataset_candidates(
            session,
            limit=args.limit,
            pool_limit=args.pool_limit,
            body_excerpt_chars=args.body_excerpt_chars,
        )

    if not candidates:
        print("数据库中没有可用的新闻记录，无法采样，退出。")
        return None

    write_jsonl(args.output, candidates)
    print(f"wrote {len(candidates)} candidates -> {args.output}")
    return args.output


if __name__ == "__main__":
    main()
