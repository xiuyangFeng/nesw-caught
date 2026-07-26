"""backend/scripts/backfill_url_hash.py 的回归测试。

全部用真实的 SQLAlchemy session + 临时 SQLite 文件库跑，不 mock 数据库：
唯一约束冲突正是本脚本最容易炸的地方，只有真库才能测出来。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.news_item import NewsItem
from app.services.ingestion.dedup_gate import normalize_url_for_hash
from scripts.backfill_url_hash import (
    DUPLICATE_INGEST_STATUS,
    build_plan,
    compute_url_hash,
    main,
    run_backfill,
)

BASE_TIME = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)


def legacy_hash(url: str) -> str:
    """回填前的老算法：直接对原始 URL 取 sha256。"""
    return sha256(url.encode("utf-8")).hexdigest()


@pytest.fixture()
def db_url(tmp_path: Path) -> str:
    """一个只建了 news_item 表的临时 SQLite 库。"""
    path = tmp_path / "backfill.db"
    url = f"sqlite:///{path}"
    engine = create_engine(url, future=True)
    NewsItem.__table__.create(engine)
    engine.dispose()
    return url


@pytest.fixture()
def session_factory(db_url: str):
    engine = create_engine(db_url, future=True)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    yield factory
    engine.dispose()


def insert_row(
    session: Session,
    *,
    url: str,
    minutes: int = 0,
    url_hash: str | None = None,
    source_name: str = "demo",
) -> int:
    published = BASE_TIME + timedelta(minutes=minutes)
    item = NewsItem(
        source_name=source_name,
        source_url="https://example.com/feed",
        title=f"title {url}",
        summary=None,
        canonical_url=url,
        url_hash=url_hash if url_hash is not None else legacy_hash(url),
        market="us",
        language="en",
        published_at=published,
        fetched_at=published,
        effective_at=published,
        ingest_status="ingested",
    )
    session.add(item)
    session.flush()
    session.commit()
    return item.id


def hashes_by_id(session: Session) -> dict[int, str]:
    return {
        row.id: row.url_hash
        for row in session.execute(select(NewsItem.id, NewsItem.url_hash)).all()
    }


def test_tracking_param_row_gets_normalized_hash(session_factory) -> None:
    """带跟踪参数的历史行，回填后 hash == 现算的归一化 hash。"""
    url = "https://example.com/news/a?utm_source=weixin&utm_medium=social&id=42#top"
    with session_factory() as session:
        news_id = insert_row(session, url=url)

    with session_factory() as session:
        result = run_backfill(session, apply=True)

    expected = compute_url_hash(url)
    # 归一化确实剥掉了跟踪参数，但保留了业务参数 id=42。
    assert normalize_url_for_hash(url) == "https://example.com/news/a?id=42"
    assert expected != legacy_hash(url)
    assert result.plan.changed == 1
    assert result.updated_rows == 1

    with session_factory() as session:
        assert hashes_by_id(session)[news_id] == expected


def test_already_canonical_row_is_untouched(session_factory) -> None:
    """已经是规范 URL 的行，回填后 hash 不变。"""
    url = "https://example.com/news/clean"
    with session_factory() as session:
        news_id = insert_row(session, url=url)
        before = hashes_by_id(session)[news_id]

    with session_factory() as session:
        result = run_backfill(session, apply=True)

    assert result.plan.scanned == 1
    assert result.plan.unchanged == 1
    assert result.plan.changed == 0
    assert result.updated_rows == 0

    with session_factory() as session:
        assert hashes_by_id(session)[news_id] == before


def test_dry_run_reports_conflict_group_without_writing(session_factory) -> None:
    """两条只差 utm_* 的历史行 → 1 个冲突组，且 dry-run 不写库。"""
    with session_factory() as session:
        first = insert_row(session, url="https://example.com/p?utm_source=a", minutes=0)
        second = insert_row(session, url="https://example.com/p?utm_source=b", minutes=30)
        before = hashes_by_id(session)

    with session_factory() as session:
        result = run_backfill(session, apply=False)

    plan = result.plan
    assert plan.scanned == 2
    assert plan.conflict_groups == 1
    assert plan.conflict_rows == 2
    assert plan.duplicate_rows == 1
    group = plan.conflicts[0]
    # 组内无人持有目标 hash → 取 effective_at 最早的那条当主行。
    assert group.primary.news_id == first
    assert [row.news_id for row in group.duplicates] == [second]
    assert result.applied is False
    assert result.updated_rows == 0

    with session_factory() as session:
        assert hashes_by_id(session) == before


def test_conflict_group_with_existing_holder_needs_no_write(session_factory) -> None:
    """组内已有行持有目标 hash 时选它当主行 —— 整组零写入，天然不撞唯一约束。"""
    clean = "https://example.com/p"
    with session_factory() as session:
        holder = insert_row(session, url=clean, minutes=120)
        tracked = insert_row(session, url=clean + "?utm_source=a", minutes=0)
        before = hashes_by_id(session)

    with session_factory() as session:
        result = run_backfill(session, apply=True)

    plan = result.plan
    assert plan.conflict_groups == 1
    # 尽管 tracked 的 effective_at 更早，主行仍是已持有目标 hash 的 holder。
    assert plan.conflicts[0].primary.news_id == holder
    assert [row.news_id for row in plan.conflicts[0].duplicates] == [tracked]
    assert plan.changed == 0
    assert result.updated_rows == 0

    with session_factory() as session:
        assert hashes_by_id(session) == before


def test_apply_updates_primary_and_keeps_unique_constraint(session_factory) -> None:
    """--apply 下主行 hash 更新、非主行保持原值，不违反 unique 约束。"""
    with session_factory() as session:
        first = insert_row(session, url="https://example.com/p?utm_source=a", minutes=0)
        second = insert_row(session, url="https://example.com/p?utm_source=b", minutes=30)
        third = insert_row(session, url="https://example.com/p?utm_source=c", minutes=60)
        # 一条无关的、本来就要变 hash 的普通行。
        other = insert_row(session, url="https://example.com/other?utm_campaign=x", minutes=90)
        second_before = hashes_by_id(session)[second]
        third_before = hashes_by_id(session)[third]

    with session_factory() as session:
        result = run_backfill(session, apply=True)

    assert result.failed_rows == []
    assert result.updated_rows == 2  # 冲突组主行 + 无关行

    with session_factory() as session:
        current = hashes_by_id(session)
    assert current[first] == compute_url_hash("https://example.com/p?utm_source=a")
    assert current[other] == compute_url_hash("https://example.com/other?utm_campaign=x")
    # 非主行 report-only：hash 原样保留。
    assert current[second] == second_before
    assert current[third] == third_before
    # unique 约束的实质检查：四行 hash 互不相同。
    assert len(set(current.values())) == len(current)


def test_apply_with_mark_strategy_marks_non_primary_rows(session_factory) -> None:
    with session_factory() as session:
        first = insert_row(session, url="https://example.com/p?utm_source=a", minutes=0)
        second = insert_row(session, url="https://example.com/p?utm_source=b", minutes=30)

    with session_factory() as session:
        result = run_backfill(session, apply=True, merge_strategy="mark")

    assert result.marked_rows == 1
    with session_factory() as session:
        statuses = {
            row.id: row.ingest_status
            for row in session.execute(select(NewsItem.id, NewsItem.ingest_status)).all()
        }
    assert statuses[first] == "ingested"
    assert statuses[second] == DUPLICATE_INGEST_STATUS

    # 再跑一次：已标过的行不重复计数（幂等）。
    with session_factory() as session:
        again = run_backfill(session, apply=True, merge_strategy="mark")
    assert again.marked_rows == 0


def test_second_run_is_idempotent(session_factory) -> None:
    urls = [
        "https://Example.com:443/a/?utm_source=x&spm=1.2#frag",
        "https://example.com/b?ref=weibo&id=7",
        "https://example.com/c",
        "https://example.com/p?utm_source=a",
        "https://example.com/p?utm_source=b",
    ]
    with session_factory() as session:
        for index, url in enumerate(urls):
            insert_row(session, url=url, minutes=index * 10)

    with session_factory() as session:
        first_run = run_backfill(session, apply=True)
    with session_factory() as session:
        after_first = hashes_by_id(session)

    with session_factory() as session:
        second_run = run_backfill(session, apply=True)
    with session_factory() as session:
        after_second = hashes_by_id(session)

    assert first_run.plan.changed >= 3
    assert second_run.plan.changed == 0
    assert second_run.updated_rows == 0
    assert after_second == after_first
    # 冲突组是数据的固有属性，两次扫描应当一致。
    assert second_run.plan.conflict_groups == first_run.plan.conflict_groups


def test_batch_size_does_not_change_result(tmp_path: Path) -> None:
    """分批提交不影响最终结果：batch-size=1 与 500 落库一致。"""
    urls = [
        "https://example.com/a?utm_source=x",
        "https://example.com/b?utm_medium=y",
        "https://example.com/c/?fbclid=z",
        "https://example.com/d?spm=1.2.3",
        "https://example.com/p?utm_source=a",
        "https://example.com/p?utm_source=b",
    ]

    def prepare(name: str):
        path = tmp_path / name
        engine = create_engine(f"sqlite:///{path}", future=True)
        NewsItem.__table__.create(engine)
        factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
        with factory() as session:
            for index, url in enumerate(urls):
                insert_row(session, url=url, minutes=index * 10)
        return engine, factory

    small_engine, small_factory = prepare("small.db")
    large_engine, large_factory = prepare("large.db")
    try:
        with small_factory() as session:
            small = run_backfill(session, apply=True, batch_size=1)
        with large_factory() as session:
            large = run_backfill(session, apply=True, batch_size=500)

        with small_factory() as session:
            small_hashes = hashes_by_id(session)
        with large_factory() as session:
            large_hashes = hashes_by_id(session)
    finally:
        small_engine.dispose()
        large_engine.dispose()

    assert small.updated_rows == large.updated_rows
    assert small.failed_rows == [] and large.failed_rows == []
    assert small_hashes == large_hashes
    assert len(set(small_hashes.values())) == len(small_hashes)


def test_hash_swap_between_rows_does_not_violate_unique(session_factory) -> None:
    """极端场景：两行的目标 hash 恰好是对方当前持有的 hash（环形依赖）。

    两阶段写入（先挪临时值、再落最终值）必须能扛住，否则第一条 UPDATE 就撞唯一约束。
    """
    url_a = "https://example.com/aa?utm_source=x"
    url_b = "https://example.com/bb?utm_source=y"
    with session_factory() as session:
        # 人为把两行的旧 hash 互换成对方的目标 hash。
        row_a = insert_row(session, url=url_a, minutes=0, url_hash=compute_url_hash(url_b))
        row_b = insert_row(session, url=url_b, minutes=10, url_hash=compute_url_hash(url_a))

    with session_factory() as session:
        result = run_backfill(session, apply=True, batch_size=500)

    assert result.failed_rows == []
    assert result.updated_rows == 2
    with session_factory() as session:
        current = hashes_by_id(session)
    assert current[row_a] == compute_url_hash(url_a)
    assert current[row_b] == compute_url_hash(url_b)


def test_blank_canonical_url_rows_are_skipped(session_factory) -> None:
    with session_factory() as session:
        blank = insert_row(session, url="", url_hash="legacy-blank")
        normal = insert_row(session, url="https://example.com/z?utm_source=q", minutes=5)

    with session_factory() as session:
        plan = build_plan(session)
    assert plan.skipped_blank_url == 1
    assert [news_id for news_id, _ in plan.updates] == [normal]

    with session_factory() as session:
        run_backfill(session, apply=True)
    with session_factory() as session:
        assert hashes_by_id(session)[blank] == "legacy-blank"


def test_cli_dry_run_prints_stats_and_leaves_db_untouched(
    db_url: str, session_factory, capsys: pytest.CaptureFixture[str]
) -> None:
    with session_factory() as session:
        insert_row(session, url="https://example.com/p?utm_source=a", minutes=0)
        insert_row(session, url="https://example.com/p?utm_source=b", minutes=30)
        before = hashes_by_id(session)

    exit_code = main(["--dry-run", "--database-url", db_url])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "DRY-RUN" in output
    assert "扫描行数            : 2" in output
    assert "冲突组数            : 1" in output

    with session_factory() as session:
        assert hashes_by_id(session) == before


def test_cli_apply_writes_and_defaults_to_report_only(db_url: str, session_factory) -> None:
    with session_factory() as session:
        news_id = insert_row(session, url="https://example.com/single?utm_source=a")

    assert main(["--apply", "--database-url", db_url]) == 0

    with session_factory() as session:
        assert hashes_by_id(session)[news_id] == compute_url_hash(
            "https://example.com/single?utm_source=a"
        )
