from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.x_account import XAccount
from app.models.x_post import XPost
from app.models.x_post_symbol_mention import XPostSymbolMention
from app.models.x_signal import XSignal
from app.models.x_signal_post_link import XSignalPostLink


class XSignalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_signal(
        self,
        *,
        signal_type: str,
        title: str,
        summary: str,
        market: str,
        topic_tag: str | None,
        macro_tag: str | None,
        primary_symbol: str | None,
        priority_score: float,
        confidence_score: float,
        source_count: int,
        first_seen_at,
        last_seen_at,
        status: str = "active",
    ) -> XSignal:
        signal = XSignal(
            signal_type=signal_type,
            title=title,
            summary=summary,
            market=market,
            topic_tag=topic_tag,
            macro_tag=macro_tag,
            primary_symbol=primary_symbol,
            priority_score=priority_score,
            confidence_score=confidence_score,
            source_count=source_count,
            first_seen_at=first_seen_at,
            last_seen_at=last_seen_at,
            status=status,
        )
        self.session.add(signal)
        self.session.flush()
        return signal

    def link_post(self, *, signal_id: int, post_id: int, evidence_rank: int, match_reason: str | None) -> None:
        self.session.add(
            XSignalPostLink(
                signal_id=signal_id,
                post_id=post_id,
                evidence_rank=evidence_rank,
                match_reason=match_reason,
            )
        )
        self.session.flush()

    def list_priority_signals(self, *, limit: int) -> list[XSignal]:
        stmt = (
            select(XSignal)
            .where(XSignal.status == "active")
            .order_by(XSignal.priority_score.desc(), XSignal.last_seen_at.desc(), XSignal.id.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def list_macro_clusters(self, *, limit: int) -> list[dict[str, object]]:
        rows = self.session.execute(
            select(
                XSignal.macro_tag,
                func.count(XSignal.id),
                func.sum(XSignal.source_count),
            )
            .where(XSignal.status == "active", XSignal.macro_tag.is_not(None))
            .group_by(XSignal.macro_tag)
            .order_by(func.max(XSignal.priority_score).desc(), func.max(XSignal.last_seen_at).desc())
            .limit(limit)
        )
        signal_ids_by_tag: dict[str, list[int]] = defaultdict(list)
        for signal in self.session.scalars(
            select(XSignal)
            .where(XSignal.status == "active", XSignal.macro_tag.is_not(None))
            .order_by(XSignal.priority_score.desc(), XSignal.id.asc())
        ):
            assert signal.macro_tag is not None
            if len(signal_ids_by_tag[signal.macro_tag]) < 5:
                signal_ids_by_tag[signal.macro_tag].append(signal.id)

        return [
            {
                "macro_tag": macro_tag,
                "title": f"{str(macro_tag).replace('_', ' ').title()} Watch",
                "signal_count": int(signal_count or 0),
                "source_count": int(source_count or 0),
                "top_signal_ids": signal_ids_by_tag.get(str(macro_tag), []),
            }
            for macro_tag, signal_count, source_count in rows
            if macro_tag
        ]

    def list_evidence_posts(self, *, limit: int) -> list[tuple[XPost, XAccount, list[str]]]:
        stmt = (
            select(XPost, XAccount)
            .join(XAccount, XAccount.id == XPost.account_id)
            .order_by(func.coalesce(XPost.posted_at, XPost.captured_at).desc(), XPost.id.desc())
            .limit(limit)
        )
        rows = list(self.session.execute(stmt))
        if not rows:
            return []
        post_ids = [post.id for post, _ in rows]
        mention_rows = self.session.execute(
            select(XPostSymbolMention.x_post_id, XPostSymbolMention.symbol)
            .where(XPostSymbolMention.x_post_id.in_(post_ids))
            .order_by(XPostSymbolMention.symbol.asc())
        )
        mentions_by_post: dict[int, list[str]] = defaultdict(list)
        for x_post_id, symbol in mention_rows:
            if symbol not in mentions_by_post[x_post_id]:
                mentions_by_post[x_post_id].append(symbol)
        return [(post, account, mentions_by_post.get(post.id, [])) for post, account in rows]
