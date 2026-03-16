from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.x_account import XAccount
from app.models.x_post import XPost
from app.models.x_post_symbol_mention import XPostSymbolMention


class XPostRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def exists(self, *, canonical_url: str | None, external_post_id: str | None, dedupe_hash: str) -> bool:
        conditions = [XPost.dedupe_hash == dedupe_hash]
        if canonical_url:
            conditions.append(XPost.canonical_url == canonical_url)
        if external_post_id:
            conditions.append(XPost.external_post_id == external_post_id)

        stmt = select(XPost.id).where(or_(*conditions)).limit(1)
        return self.session.scalar(stmt) is not None

    def create_post(
        self,
        *,
        account_id: int,
        external_post_id: str | None,
        canonical_url: str | None,
        content_text: str,
        market: str,
        sentiment_label: str,
        relevance_score: float | None,
        posted_at,
        captured_at,
        raw_payload_json: str | None,
        dedupe_hash: str,
    ) -> XPost:
        post = XPost(
            account_id=account_id,
            external_post_id=external_post_id,
            canonical_url=canonical_url,
            content_text=content_text,
            market=market,
            sentiment_label=sentiment_label,
            relevance_score=relevance_score,
            posted_at=posted_at,
            captured_at=captured_at,
            raw_payload_json=raw_payload_json,
            dedupe_hash=dedupe_hash,
        )
        self.session.add(post)
        self.session.flush()
        return post

    def add_mentions(self, x_post_id: int, mentions: list[dict[str, object]]) -> None:
        for mention in mentions:
            symbol = str(mention.get("symbol") or "").upper().strip()
            if not symbol:
                continue
            self.session.add(
                XPostSymbolMention(
                    x_post_id=x_post_id,
                    symbol=symbol,
                    market=str(mention.get("market") or "us"),
                    confidence=float(mention.get("confidence") or 0.0),
                )
            )
        self.session.flush()

    def list_posts(
        self,
        *,
        account_handle: str | None,
        symbol: str | None,
        market: str | None,
        query: str | None,
        limit: int,
    ) -> list[tuple[XPost, XAccount, list[str]]]:
        stmt: Select[tuple[XPost, XAccount]] = (
            select(XPost, XAccount)
            .join(XAccount, XAccount.id == XPost.account_id)
            .order_by(func.coalesce(XPost.posted_at, XPost.captured_at).desc(), XPost.id.desc())
        )

        if account_handle:
            stmt = stmt.where(XAccount.handle == account_handle.lstrip("@"))
        if market:
            stmt = stmt.where(XPost.market == market)
        if query:
            stmt = stmt.where(XPost.content_text.ilike(f"%{query}%"))
        if symbol:
            stmt = stmt.join(XPostSymbolMention, XPostSymbolMention.x_post_id == XPost.id).where(
                XPostSymbolMention.symbol == symbol.upper()
            )

        rows = list(self.session.execute(stmt.limit(limit)))
        if not rows:
            return []

        post_ids = [post.id for post, _ in rows]
        mention_rows = self.session.execute(
            select(XPostSymbolMention.x_post_id, XPostSymbolMention.symbol)
            .where(XPostSymbolMention.x_post_id.in_(post_ids))
            .order_by(XPostSymbolMention.symbol.asc())
        )
        mentions_by_post: dict[int, list[str]] = {}
        for x_post_id, mention_symbol in mention_rows:
            mentions_by_post.setdefault(x_post_id, [])
            if mention_symbol not in mentions_by_post[x_post_id]:
                mentions_by_post[x_post_id].append(mention_symbol)

        return [(post, account, mentions_by_post.get(post.id, [])) for post, account in rows]
