from __future__ import annotations

from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

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
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "research" / "market_relevance_candidates.jsonl"


def _resolve_current_source_names(current_source_names: Iterable[str] | None) -> set[str]:
    if current_source_names is not None:
        return {name for name in current_source_names if name}
    return {source.name for source in load_sources() if not source.disabled}


def _query_historical_news_items(session: Session, limit: int) -> list[NewsItem]:
    if limit <= 0:
        return []
    statement = select(NewsItem).order_by(NewsItem.fetched_at.asc(), NewsItem.id.asc()).limit(limit)
    return list(session.scalars(statement))


def _query_realtime_news_items(session: Session, limit: int, current_source_names: set[str]) -> list[NewsItem]:
    if limit <= 0 or not current_source_names:
        return []
    statement = (
        select(NewsItem)
        .where(NewsItem.source_name.in_(sorted(current_source_names)))
        .order_by(NewsItem.fetched_at.desc(), NewsItem.id.desc())
        .limit(limit)
    )
    return list(session.scalars(statement))


def _news_item_to_sample(news_item: NewsItem, *, source_type: str, sample_rank: int) -> MarketRelevanceSample:
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
            body_excerpt=None,
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
) -> list[MarketRelevanceSample]:
    current_sources = _resolve_current_source_names(current_source_names)
    historical_rows = _query_historical_news_items(session, historical_limit)
    realtime_rows = _query_realtime_news_items(session, realtime_limit, current_sources)

    samples: list[MarketRelevanceSample] = []
    seen_urls: set[str] = set()

    def append_rows(rows: list[NewsItem], source_type: str) -> None:
        for row in rows:
            if row.canonical_url in seen_urls:
                continue
            seen_urls.add(row.canonical_url)
            samples.append(_news_item_to_sample(row, source_type=source_type, sample_rank=len(samples) + 1))

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
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        samples = build_market_relevance_candidates(session)
    return write_market_relevance_candidates(samples)


if __name__ == "__main__":
    main()
