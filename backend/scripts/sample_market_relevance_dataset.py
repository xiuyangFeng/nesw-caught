from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.schemas.research import (
    MarketRelevanceAnnotation,
    MarketRelevanceContent,
    MarketRelevanceLabel,
    MarketRelevanceOrigin,
    MarketRelevanceSample,
)
from app.services.news_ingestion import load_sources
from app.services.news_relevance_dataset import save_samples

DEFAULT_HISTORICAL_LIMIT = 240
DEFAULT_REALTIME_LIMIT = 160
DEFAULT_BODY_EXCERPT_CHARS = 600
DEFAULT_SOURCE_CAP_OVERSAMPLE_FACTOR = 5
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "research" / "market_relevance_candidates.jsonl"


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be >= 0")
    return parsed


def _resolve_current_source_names(current_source_names: Iterable[str] | None) -> set[str]:
    if current_source_names is not None:
        return {name for name in current_source_names if name}
    return {source.name for source in load_sources() if not source.disabled}


def _optional_positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be > 0")
    return parsed


def _query_historical_news_items(session: Session, limit: int | None) -> list[NewsItem]:
    if limit is not None and limit <= 0:
        return []
    statement = select(NewsItem).order_by(NewsItem.fetched_at.asc(), NewsItem.id.asc())
    if limit is not None:
        statement = statement.limit(limit)
    return list(session.scalars(statement))


def _query_realtime_news_items(session: Session, limit: int | None, current_source_names: set[str]) -> list[NewsItem]:
    if (limit is not None and limit <= 0) or not current_source_names:
        return []
    statement = (
        select(NewsItem)
        .where(NewsItem.source_name.in_(sorted(current_source_names)))
        .order_by(NewsItem.fetched_at.desc(), NewsItem.id.desc())
    )
    if limit is not None:
        statement = statement.limit(limit)
    return list(session.scalars(statement))


def _query_window_size(limit: int, *, per_source_cap: int | None) -> int | None:
    if per_source_cap is None:
        return limit
    return None


def _load_article_excerpt_map(
    session: Session,
    rows: list[NewsItem],
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


def _apply_source_cap(rows: list[NewsItem], *, per_source_cap: int | None) -> list[NewsItem]:
    if per_source_cap is None:
        return rows

    buckets: dict[str, list[NewsItem]] = {}
    for row in rows:
        buckets.setdefault(row.source_name, []).append(row)

    selected: list[NewsItem] = []
    counts: dict[str, int] = {source_name: 0 for source_name in buckets}
    while True:
        advanced = False
        for source_name, bucket in buckets.items():
            if counts[source_name] >= per_source_cap:
                continue
            if not bucket:
                continue
            selected.append(bucket.pop(0))
            counts[source_name] += 1
            advanced = True
        if not advanced:
            break
    return selected


def _news_item_to_sample(
    news_item: NewsItem,
    *,
    source_type: str,
    sample_rank: int,
    body_excerpt: str | None,
) -> MarketRelevanceSample:
    return MarketRelevanceSample(
        sample_id=f"{source_type}-{sample_rank:04d}-{news_item.id}",
        source_type=source_type,  # type: ignore[arg-type]
        origin=MarketRelevanceOrigin(
            news_id=news_item.id,
            source_name=news_item.source_name,
            canonical_url=news_item.canonical_url,
            published_at=news_item.published_at,
        ),
        content=MarketRelevanceContent(
            title=news_item.title,
            summary=news_item.summary,
            body_excerpt=body_excerpt,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="model_only",
            model_name=None,
            confidence=0.0,
            review_notes="",
        ),
    )


def build_market_relevance_candidates(
    session: Session,
    *,
    historical_limit: int = DEFAULT_HISTORICAL_LIMIT,
    realtime_limit: int = DEFAULT_REALTIME_LIMIT,
    current_source_names: Iterable[str] | None = None,
    body_excerpt_chars: int = DEFAULT_BODY_EXCERPT_CHARS,
    historical_source_cap: int | None = None,
    realtime_source_cap: int | None = None,
) -> list[MarketRelevanceSample]:
    current_sources = _resolve_current_source_names(current_source_names)
    historical_rows = _apply_source_cap(
        _query_historical_news_items(
            session,
            _query_window_size(historical_limit, per_source_cap=historical_source_cap),
        ),
        per_source_cap=historical_source_cap,
    )[:historical_limit]
    realtime_rows = _apply_source_cap(
        _query_realtime_news_items(
            session,
            _query_window_size(realtime_limit, per_source_cap=realtime_source_cap),
            current_sources,
        ),
        per_source_cap=realtime_source_cap,
    )[:realtime_limit]
    article_excerpt_map = _load_article_excerpt_map(
        session,
        historical_rows + realtime_rows,
        excerpt_chars=body_excerpt_chars,
    )

    samples: list[MarketRelevanceSample] = []
    seen_urls: set[str] = set()

    def append_rows(rows: list[NewsItem], source_type: str) -> None:
        for row in rows:
            if row.canonical_url in seen_urls:
                continue
            seen_urls.add(row.canonical_url)
            samples.append(
                _news_item_to_sample(
                    row,
                    source_type=source_type,
                    sample_rank=len(samples) + 1,
                    body_excerpt=article_excerpt_map.get(row.id),
                )
            )

    append_rows(historical_rows, "historical")
    append_rows(realtime_rows, "realtime")
    return samples


def write_market_relevance_candidates(
    samples: list[MarketRelevanceSample],
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    save_samples(output_path, samples)
    return output_path


def main() -> Path:
    parser = argparse.ArgumentParser(description="Build market relevance candidate samples from current news data.")
    parser.add_argument("--historical-limit", type=_non_negative_int, default=DEFAULT_HISTORICAL_LIMIT)
    parser.add_argument("--realtime-limit", type=_non_negative_int, default=DEFAULT_REALTIME_LIMIT)
    parser.add_argument("--body-excerpt-chars", type=_non_negative_int, default=DEFAULT_BODY_EXCERPT_CHARS)
    parser.add_argument("--historical-source-cap", type=_optional_positive_int, default=None)
    parser.add_argument("--realtime-source-cap", type=_optional_positive_int, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    from app.db.session import SessionLocal

    with SessionLocal() as session:
        samples = build_market_relevance_candidates(
            session,
            historical_limit=args.historical_limit,
            realtime_limit=args.realtime_limit,
            body_excerpt_chars=args.body_excerpt_chars,
            historical_source_cap=args.historical_source_cap,
            realtime_source_cap=args.realtime_source_cap,
        )
    output_path = write_market_relevance_candidates(samples, args.output)
    print(f"wrote {len(samples)} samples -> {output_path}")
    return output_path


if __name__ == "__main__":
    main()
