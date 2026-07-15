from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from app.models.x_account import XAccount
from app.models.x_post import XPost
from app.repositories.x_signal_repository import XSignalRepository


@dataclass(frozen=True)
class _MacroRule:
    tag: str
    title: str
    keywords: tuple[str, ...]
    weight: float
    topic_tag: str | None = None


MACRO_RULES: tuple[_MacroRule, ...] = (
    _MacroRule(tag="tariff", title="Tariff", keywords=("tariff", "duties"), weight=34.0, topic_tag="macro"),
    _MacroRule(tag="export_control", title="Export Control", keywords=("export control", "export controls"), weight=28.0, topic_tag="macro"),
    _MacroRule(tag="rate", title="Rate", keywords=("rate cut", "rates", "yield", "cpi", "inflation"), weight=24.0, topic_tag="macro"),
    _MacroRule(tag="fed", title="Fed", keywords=("fed", "fomc", "powell"), weight=22.0, topic_tag="macro"),
)

DEFAULT_RULES_FILE = Path(__file__).resolve().parents[2] / "data" / "x_radar_rules.example.json"


def _account_weight(account: XAccount) -> float:
    tier_bonus = {"core": 40.0, "watch": 22.0, "muted": 0.0}.get(account.tier, 10.0)
    return tier_bonus + min(max(account.priority, 0), 100) * 0.2


def _load_macro_rules(rules_file: str | None) -> tuple[_MacroRule, ...]:
    candidate = Path(rules_file) if rules_file else DEFAULT_RULES_FILE
    if not candidate.exists():
        return MACRO_RULES

    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return MACRO_RULES

    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, list):
        return MACRO_RULES

    loaded_rules: list[_MacroRule] = []
    for item in raw_rules:
        if not isinstance(item, dict):
            continue
        tag = str(item.get("tag") or "").strip()
        title = str(item.get("title") or tag.replace("_", " ").title()).strip()
        keywords = item.get("keywords")
        if not tag or not isinstance(keywords, list):
            continue
        normalized_keywords = tuple(
            str(keyword).strip().lower()
            for keyword in keywords
            if str(keyword).strip()
        )
        if not normalized_keywords:
            continue
        try:
            weight = float(item.get("weight") or 0.0)
        except (TypeError, ValueError):
            continue
        loaded_rules.append(
            _MacroRule(
                tag=tag,
                title=title or tag.replace("_", " ").title(),
                keywords=normalized_keywords,
                weight=weight,
                topic_tag=str(item.get("topic_tag")) if item.get("topic_tag") else None,
            )
        )

    return tuple(loaded_rules) or MACRO_RULES


class XRadarSignalBuilder:
    def __init__(self, signal_repo: XSignalRepository, *, rules_file: str | None = None) -> None:
        self.signal_repo = signal_repo
        self.rules = _load_macro_rules(rules_file)

    def _match_rule(self, content_text: str) -> _MacroRule | None:
        normalized = content_text.lower()
        for rule in self.rules:
            if any(keyword in normalized for keyword in rule.keywords):
                return rule
        return None

    def build(self, inserted_posts: list[tuple[XPost, XAccount, list[str]]]) -> None:
        if not inserted_posts:
            return

        matched_by_tag: dict[str, list[tuple[XPost, XAccount, list[str], _MacroRule]]] = defaultdict(list)
        for post, account, symbols in inserted_posts:
            account_weight = _account_weight(account)
            primary_symbol = symbols[0] if symbols else None
            account_signal = self.signal_repo.create_signal(
                signal_type="account_post",
                title=f"@{account.handle} posted a tracked update",
                summary=post.content_text,
                market=post.market,
                topic_tag="account",
                macro_tag=None,
                primary_symbol=primary_symbol,
                priority_score=account_weight + (8.0 if primary_symbol else 0.0),
                confidence_score=0.62,
                source_count=1,
                first_seen_at=post.posted_at or post.captured_at,
                last_seen_at=post.posted_at or post.captured_at,
            )
            self.signal_repo.link_post(signal_id=account_signal.id, post_id=post.id, evidence_rank=1, match_reason="account")

            rule = self._match_rule(post.content_text)
            if rule is None:
                continue
            matched_by_tag[rule.tag].append((post, account, symbols, rule))
            macro_signal = self.signal_repo.create_signal(
                signal_type="macro_event",
                title=f"{rule.title} signal from tracked accounts",
                summary=post.content_text,
                market=post.market,
                topic_tag=rule.topic_tag,
                macro_tag=rule.tag,
                primary_symbol=primary_symbol,
                priority_score=account_weight + rule.weight + (10.0 if primary_symbol else 0.0),
                confidence_score=0.82,
                source_count=1,
                first_seen_at=post.posted_at or post.captured_at,
                last_seen_at=post.posted_at or post.captured_at,
            )
            self.signal_repo.link_post(signal_id=macro_signal.id, post_id=post.id, evidence_rank=1, match_reason=rule.tag)

        for tag, matched_posts in matched_by_tag.items():
            distinct_accounts = {account.id for _, account, _, _ in matched_posts}
            if len(distinct_accounts) < 2:
                continue
            first_post, _, symbols, rule = matched_posts[0]
            last_seen_at = max((post.posted_at or post.captured_at) for post, _, _, _ in matched_posts)
            first_seen_at = min((post.posted_at or post.captured_at) for post, _, _, _ in matched_posts)
            resonance_signal = self.signal_repo.create_signal(
                signal_type="multi_account_resonance",
                title=f"{rule.title} resonance across tracked accounts",
                summary=f"{len(distinct_accounts)} tracked accounts are converging on {rule.title.lower()}.",
                market=first_post.market,
                topic_tag=rule.topic_tag,
                macro_tag=tag,
                primary_symbol=symbols[0] if symbols else None,
                priority_score=rule.weight + 60.0 + len(distinct_accounts) * 4.0,
                confidence_score=0.9,
                source_count=len(distinct_accounts),
                first_seen_at=first_seen_at,
                last_seen_at=last_seen_at,
            )
            for index, (post, _, _, _) in enumerate(matched_posts, start=1):
                self.signal_repo.link_post(
                    signal_id=resonance_signal.id,
                    post_id=post.id,
                    evidence_rank=index,
                    match_reason=f"{tag}_resonance",
                )
