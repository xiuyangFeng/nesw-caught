from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.news_priority import NewsPriorityItem, rank_news_items


def _item(
    title: str,
    *,
    source_tier: str = "primary",
    sector_tag: str | None = None,
    source_name: str = "Reuters",
    published_at: datetime | None = None,
    relevance_hints: tuple[str, ...] = (),
) -> NewsPriorityItem:
    return NewsPriorityItem(
        title=title,
        source_tier=source_tier,
        sector_tag=sector_tag,
        source_name=source_name,
        published_at=published_at,
        relevance_hints=relevance_hints,
    )


def test_rank_news_items_prefers_primary_sector_tagged_stories_over_secondary_generic_stories() -> None:
    now = datetime(2026, 3, 26, 10, 0, tzinfo=UTC)
    items = [
        _item(
            "Secondary generic market roundup",
            source_tier="secondary",
            published_at=now,
        ),
        _item(
            "Primary semiconductor catalyst",
            source_tier="primary",
            sector_tag="semiconductors",
            published_at=now - timedelta(minutes=20),
        ),
    ]

    ranked = rank_news_items(items, now=now)

    assert [item.title for item in ranked] == [
        "Primary semiconductor catalyst",
        "Secondary generic market roundup",
    ]


def test_rank_news_items_prefers_official_filing_signals_over_media_rewrites() -> None:
    now = datetime(2026, 3, 26, 10, 0, tzinfo=UTC)
    items = [
        _item(
            "Reuters summary of SEC filing",
            source_tier="primary",
            sector_tag="semiconductors",
            source_name="Reuters",
            published_at=now - timedelta(minutes=5),
            relevance_hints=("rewrite",),
        ),
        _item(
            "SEC filing on export controls",
            source_tier="primary",
            sector_tag="semiconductors",
            source_name="SEC",
            published_at=now - timedelta(minutes=15),
            relevance_hints=("filing", "regulatory"),
        ),
    ]

    ranked = rank_news_items(items, now=now)

    assert [item.title for item in ranked] == [
        "SEC filing on export controls",
        "Reuters summary of SEC filing",
    ]


def test_rank_news_items_uses_recency_as_the_final_tiebreaker() -> None:
    now = datetime(2026, 3, 26, 10, 0, tzinfo=UTC)
    items = [
        _item(
            "Older primary semiconductor update",
            sector_tag="semiconductors",
            published_at=now - timedelta(minutes=30),
        ),
        _item(
            "Newer primary semiconductor update",
            sector_tag="semiconductors",
            published_at=now - timedelta(minutes=5),
        ),
    ]

    ranked = rank_news_items(items, now=now)

    assert [item.title for item in ranked] == [
        "Newer primary semiconductor update",
        "Older primary semiconductor update",
    ]
