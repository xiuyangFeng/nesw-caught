"""存量 `news_item.url_hash` 回填脚本（FIX-C）。

背景
----
`app/services/ingestion/dedup_gate.normalize_url_for_hash()` 上线后，
persister 计算 `url_hash` 前会先归一化 URL（剥 `utm_*`/`spm`/`from` 等跟踪参数、
去 fragment、小写 scheme+host、去默认端口、参数排序、去多余末尾斜杠），
而入库的 `canonical_url` 仍保留原始可点击链接。

历史行的 `url_hash` 是按【原始 URL】算的：带跟踪参数的老文章再次被抓到时，
新算法算出的 hash 与库里旧行对不上 —— 精确去重闸直接漏杀，只剩 SimHash
第二道闸兜底。本脚本一次性把存量行的 `url_hash` 重算成新算法的结果。

设计要点
--------
1. **严格复用** `normalize_url_for_hash`，不在本脚本里另写一份归一化逻辑，
   否则两边迟早漂移（今天修一个跟踪参数，明天回填脚本又对不上）。
2. **默认 dry-run**：不加 `--apply` 一律只读，只打印统计与冲突样例。
3. **幂等**：hash 只依赖 `canonical_url`，重复跑第二次的「变更行数」必然为 0。
4. **唯一约束**：`url_hash` 带 unique 索引。归一化后多条历史行可能塌缩到同一个
   目标 hash（这正是我们想发现的存量重复），一个 hash 只能由一行持有：
   - 主行选择规则（见 `_select_primary`）：
     a) 若组内【已有行持有目标 hash】，就选它当主行 —— 此时整组零写入，
        天然不会撞唯一约束；
     b) 否则选 `effective_at` 最早的行，同刻按 `id` 最小。理由：最早的那条是
        这篇文章第一次入库的记录，`article_content` / `news_stock_mention` /
        `topic_news_link` / `news_analysis_result` 等外键表大概率挂在它身上，
        保留它对下游破坏最小；两级都取确定性极值，保证多次运行结果一致。
   - 非主行【不改 hash】，保持原值（依旧唯一，不违约束）。处置方式由
     `--merge-strategy` 决定，默认 `report-only`（只报告不动数据）。
     物理删除会级联影响多张外键表，风险过高，本脚本不提供。
5. **写入用两阶段**：同一批先把待改行统一挪到临时占位 hash，再写最终 hash。
   即使出现「A 要拿 B 现在的 hash」这类环形依赖，也不会中途撞唯一约束。
   两个阶段在同一事务内，崩溃会整体回滚，不会把临时 hash 留在库里。
6. **分批提交**：每 `--batch-size` 行提交一次，避免一个大事务长时间锁库。

用法
----
    PYTHONPATH=backend python backend/scripts/backfill_url_hash.py --dry-run
    PYTHONPATH=backend python backend/scripts/backfill_url_hash.py --apply
    PYTHONPATH=backend python backend/scripts/backfill_url_hash.py --dry-run \
        --database-url "sqlite:////tmp/probe.db"
"""

from __future__ import annotations

import argparse
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select, update  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.models.news_item import NewsItem  # noqa: E402
from app.services.ingestion.dedup_gate import normalize_url_for_hash  # noqa: E402
from app.services.ingestion.utils import _normalize_datetime  # noqa: E402

# 非主行的标记值，写入 news_item.ingest_status（String(32)）。
# 仅在 --merge-strategy=mark 时使用，便于后续人工/脚本复查这批存量重复。
DUPLICATE_INGEST_STATUS = "duplicate_url_hash"

MERGE_STRATEGIES = ("report-only", "mark")

DEFAULT_BATCH_SIZE = 500

# effective_at 缺失时的排序兜底：排到最后，避免 None 参与比较直接抛错。
_FAR_FUTURE = datetime.max.replace(tzinfo=UTC)


def compute_url_hash(canonical_url: str) -> str:
    """与 persister.persist_item 完全一致的 url_hash 计算方式。"""
    return sha256(normalize_url_for_hash(canonical_url).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RowSnapshot:
    """回填只需要的四列投影，不加载 summary 等大文本列。"""

    news_id: int
    canonical_url: str
    old_hash: str
    new_hash: str
    effective_at: datetime | None
    source_name: str

    @property
    def changed(self) -> bool:
        return self.old_hash != self.new_hash


@dataclass
class ConflictGroup:
    """归一化后塌缩到同一个 hash 的一组历史行。"""

    new_hash: str
    primary: RowSnapshot
    duplicates: list[RowSnapshot]

    @property
    def size(self) -> int:
        return 1 + len(self.duplicates)


@dataclass
class BackfillPlan:
    """一次扫描的结果：谁要改成什么、哪些行塌缩到了一起。"""

    scanned: int = 0
    unchanged: int = 0
    skipped_blank_url: int = 0
    # (news_id, new_hash) —— 需要真正写库的行。
    updates: list[tuple[int, str]] = field(default_factory=list)
    conflicts: list[ConflictGroup] = field(default_factory=list)

    @property
    def changed(self) -> int:
        return len(self.updates)

    @property
    def conflict_groups(self) -> int:
        return len(self.conflicts)

    @property
    def conflict_rows(self) -> int:
        """冲突组涉及的总行数（含主行）。"""
        return sum(group.size for group in self.conflicts)

    @property
    def duplicate_rows(self) -> int:
        """冲突组里的非主行行数（= 存量重复条数）。"""
        return sum(len(group.duplicates) for group in self.conflicts)


@dataclass
class BackfillResult:
    plan: BackfillPlan
    applied: bool = False
    updated_rows: int = 0
    marked_rows: int = 0
    failed_rows: list[int] = field(default_factory=list)


def _sort_key(row: RowSnapshot) -> tuple[datetime, int]:
    effective = _normalize_datetime(row.effective_at) or _FAR_FUTURE
    return (effective, row.news_id)


def _select_primary(rows: list[RowSnapshot], new_hash: str) -> RowSnapshot:
    """冲突组主行选择。

    规则 a（约束优先）：组内已有行持有目标 hash 时选它 —— 整组零写入。
    规则 b（最早入库）：否则取 effective_at 最早、id 最小的行。
    """
    holders = [row for row in rows if row.old_hash == new_hash]
    if holders:
        return min(holders, key=_sort_key)
    return min(rows, key=_sort_key)


def _load_rows(session: Session) -> list[RowSnapshot]:
    stmt = select(
        NewsItem.id,
        NewsItem.canonical_url,
        NewsItem.url_hash,
        NewsItem.effective_at,
        NewsItem.source_name,
    ).order_by(NewsItem.id)
    rows: list[RowSnapshot] = []
    for news_id, canonical_url, url_hash, effective_at, source_name in session.execute(stmt):
        url = canonical_url or ""
        rows.append(
            RowSnapshot(
                news_id=news_id,
                canonical_url=url,
                old_hash=url_hash or "",
                new_hash=compute_url_hash(url) if url.strip() else "",
                effective_at=effective_at,
                source_name=source_name or "",
            )
        )
    return rows


def build_plan(session: Session) -> BackfillPlan:
    """扫描全表，产出「要改哪些行 / 有哪些冲突组」的计划（只读）。"""
    plan = BackfillPlan()
    grouped: dict[str, list[RowSnapshot]] = defaultdict(list)

    for row in _load_rows(session):
        plan.scanned += 1
        if not row.canonical_url.strip():
            # canonical_url 为空的行没法算出有意义的 hash，一律跳过，
            # 否则所有空 URL 行会塌缩到 sha256("") 上互相打架。
            plan.skipped_blank_url += 1
            continue
        grouped[row.new_hash].append(row)

    for new_hash, rows in grouped.items():
        if len(rows) == 1:
            row = rows[0]
            if row.changed:
                plan.updates.append((row.news_id, new_hash))
            else:
                plan.unchanged += 1
            continue

        primary = _select_primary(rows, new_hash)
        duplicates = sorted(
            (row for row in rows if row.news_id != primary.news_id), key=_sort_key
        )
        plan.conflicts.append(
            ConflictGroup(new_hash=new_hash, primary=primary, duplicates=duplicates)
        )
        if primary.changed:
            plan.updates.append((primary.news_id, new_hash))
        else:
            plan.unchanged += 1
        # 非主行保持原 hash 不变（依旧各自唯一），统计进「未变行数」。
        plan.unchanged += len(duplicates)

    # 按 id 排序，让分批顺序稳定、可复现。
    plan.updates.sort()
    plan.conflicts.sort(key=lambda group: group.primary.news_id)
    return plan


def _temp_hash(token: str, news_id: int) -> str:
    """两阶段写入用的临时占位 hash（长度 <= 64，且不可能与 sha256 十六进制串相撞）。"""
    return f"__backfill__{token}__{news_id}"


def _write_batch(session: Session, batch: list[tuple[int, str]], token: str) -> None:
    """两阶段写一批：先全挪到临时值，再落最终值，最后提交。"""
    for news_id, _ in batch:
        session.execute(
            update(NewsItem)
            .where(NewsItem.id == news_id)
            .values(url_hash=_temp_hash(token, news_id))
        )
    session.flush()
    for news_id, new_hash in batch:
        session.execute(update(NewsItem).where(NewsItem.id == news_id).values(url_hash=new_hash))
    session.flush()
    session.commit()


def _apply_updates(
    session: Session, updates: list[tuple[int, str]], *, batch_size: int
) -> tuple[int, list[int]]:
    """分批写入，返回 (成功行数, 失败的 news_id 列表)。"""
    token = uuid.uuid4().hex[:12]
    updated = 0
    failed: list[int] = []
    for start in range(0, len(updates), max(1, batch_size)):
        batch = updates[start : start + max(1, batch_size)]
        try:
            _write_batch(session, batch, token)
            updated += len(batch)
        except IntegrityError:
            # 整批回滚后逐行重试：把炸点缩小到具体行，其余行照常落库。
            session.rollback()
            for single in batch:
                try:
                    _write_batch(session, [single], token)
                    updated += 1
                except IntegrityError:
                    session.rollback()
                    failed.append(single[0])
    return updated, failed


def _mark_duplicates(session: Session, plan: BackfillPlan, *, batch_size: int) -> int:
    """把冲突组里的非主行标成 DUPLICATE_INGEST_STATUS（幂等：已标过的不重复计数）。"""
    targets = [
        row.news_id
        for group in plan.conflicts
        for row in group.duplicates
    ]
    if not targets:
        return 0
    marked = 0
    step = max(1, batch_size)
    for start in range(0, len(targets), step):
        batch = targets[start : start + step]
        result = session.execute(
            update(NewsItem)
            .where(NewsItem.id.in_(batch), NewsItem.ingest_status != DUPLICATE_INGEST_STATUS)
            .values(ingest_status=DUPLICATE_INGEST_STATUS)
        )
        marked += result.rowcount or 0
        session.commit()
    return marked


def run_backfill(
    session: Session,
    *,
    apply: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
    merge_strategy: str = "report-only",
) -> BackfillResult:
    """扫描 + （可选）写库。`apply=False` 时保证一行都不写。"""
    if merge_strategy not in MERGE_STRATEGIES:
        raise ValueError(f"unknown merge strategy: {merge_strategy}")

    plan = build_plan(session)
    result = BackfillResult(plan=plan)
    if not apply:
        return result

    result.applied = True
    updated, failed = _apply_updates(session, plan.updates, batch_size=batch_size)
    result.updated_rows = updated
    result.failed_rows = failed
    if merge_strategy == "mark":
        result.marked_rows = _mark_duplicates(session, plan, batch_size=batch_size)
    return result


def format_report(result: BackfillResult, *, merge_strategy: str, sample_limit: int) -> str:
    plan = result.plan
    mode = "APPLY（已写库）" if result.applied else "DRY-RUN（只读，未写库）"
    lines = [
        "=" * 64,
        f"url_hash 回填 · {mode}",
        "=" * 64,
        f"扫描行数            : {plan.scanned}",
        f"hash 未变行数       : {plan.unchanged}",
        f"hash 变更行数       : {plan.changed}",
        f"canonical_url 为空  : {plan.skipped_blank_url}（跳过）",
        f"冲突组数            : {plan.conflict_groups}",
        f"冲突组受影响行数    : {plan.conflict_rows}（其中非主行 {plan.duplicate_rows} 条）",
        f"重复处置策略        : {merge_strategy}",
    ]
    if result.applied:
        lines.append(f"实际更新行数        : {result.updated_rows}")
        lines.append(f"标记为重复行数      : {result.marked_rows}")
        if result.failed_rows:
            lines.append(f"写入失败 news_id    : {result.failed_rows}")

    if plan.conflicts:
        lines.append("")
        lines.append(f"冲突明细样例（最多 {sample_limit} 组）:")
        for group in plan.conflicts[:sample_limit]:
            lines.append(f"  - hash={group.new_hash[:16]}… 共 {group.size} 行")
            lines.append(
                f"      [主行] id={group.primary.news_id} "
                f"source={group.primary.source_name} url={group.primary.canonical_url[:120]}"
            )
            for row in group.duplicates:
                lines.append(
                    f"      [重复] id={row.news_id} "
                    f"source={row.source_name} url={row.canonical_url[:120]}"
                )
        if plan.conflict_groups > sample_limit:
            lines.append(f"  …… 另有 {plan.conflict_groups - sample_limit} 组未展开")

    if not result.applied and plan.changed:
        lines.append("")
        lines.append("提示：以上为预演结果，加 --apply 才会真正写库。")
    return "\n".join(lines)


def _build_session_factory(database_url: str | None):
    if not database_url:
        # 默认走 app 的共享 engine（读 Settings.database_url）。
        from app.db.session import SessionLocal

        return SessionLocal
    connect_args = (
        {"timeout": 30, "check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    engine = create_engine(database_url, future=True, connect_args=connect_args)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="按新的 URL 归一化规则回填存量 news_item.url_hash（默认 dry-run）。"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计不写库（默认行为）",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="真正写库；不加则只做预演",
    )
    parser.add_argument(
        "--merge-strategy",
        choices=MERGE_STRATEGIES,
        default="report-only",
        help=(
            "归一化后塌缩到同一 hash 的非主行如何处置："
            "report-only=只报告不动数据（默认）；"
            f"mark=把非主行的 ingest_status 标成 {DUPLICATE_INGEST_STATUS}。"
            "不提供物理删除：会级联影响 article_content / news_stock_mention 等外键表。"
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"每批提交的行数，默认 {DEFAULT_BATCH_SIZE}",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="覆盖默认的 Settings.database_url（例如指向生产库副本做只读预演）",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=5,
        help="报告里展开的冲突组样例数量，默认 5",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.batch_size <= 0:
        print("--batch-size 必须为正整数", file=sys.stderr)
        return 2

    session_factory = _build_session_factory(args.database_url)
    with session_factory() as session:
        result = run_backfill(
            session,
            apply=args.apply,
            batch_size=args.batch_size,
            merge_strategy=args.merge_strategy,
        )
    print(format_report(result, merge_strategy=args.merge_strategy, sample_limit=args.sample_limit))
    return 1 if result.failed_rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
