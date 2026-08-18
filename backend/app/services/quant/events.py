from __future__ import annotations

from dataclasses import dataclass

from app.services.quant.contracts import CandidateState

HARD_EVENT_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("年度报告", "periodic_report"),
    ("年报", "periodic_report"),
    ("半年报", "periodic_report"),
    ("季报", "periodic_report"),
    ("业绩预告", "earnings_preview"),
    ("业绩快报", "earnings_flash"),
    ("回购", "buyback"),
    ("增持", "insider_increase"),
    ("减持", "insider_decrease"),
    ("问询函", "inquiry"),
    ("重组", "m_and_a"),
    ("并购", "m_and_a"),
    ("诉讼", "litigation"),
    ("扩产", "capacity"),
    ("股权激励", "incentive"),
    ("大额订单", "order"),
)

A_SOURCES = ("巨潮", "cninfo", "sse.com", "szse.cn", "bse.cn", "上交所", "深交所", "北交所")
B_SOURCES = ("公司公告", "IR", "人民政府", "行业协会")
D_SOURCES = ("雪球", "微博", "weibo", "xueqiu", "twitter", "自媒体", "股吧")


@dataclass(frozen=True)
class ClassifiedEvent:
    event_type: str
    evidence_grade: str


def evidence_grade(source_name: str, source_url: str = "") -> str:
    blob = f"{source_name} {source_url}".lower()
    if any(token.lower() in blob for token in A_SOURCES):
        return "A"
    if any(token.lower() in blob for token in D_SOURCES):
        return "D"
    if any(token.lower() in blob for token in B_SOURCES):
        return "B"
    return "C"


def classify_event(
    *,
    title: str,
    source_name: str,
    source_url: str = "",
    summary: str | None = None,
) -> ClassifiedEvent:
    text = f"{title} {summary or ''}"
    event_type = "general"
    for keyword, mapped in HARD_EVENT_KEYWORDS:
        if keyword in text:
            event_type = mapped
            break
    return ClassifiedEvent(event_type=event_type, evidence_grade=evidence_grade(source_name, source_url))


def propose_state(
    *,
    evidence_grade: str,
    novelty: float,
    materiality: float,
    evidence_quality: float,
    reaction_gap: float,
) -> CandidateState:
    score = novelty * materiality * evidence_quality * reaction_gap
    if evidence_grade == "D":
        return CandidateState.DISCOVERED
    if score >= 0.45 and evidence_grade in {"A", "B"}:
        return CandidateState.VALIDATING
    if score >= 0.2:
        return CandidateState.DISCOVERED
    return CandidateState.DISCOVERED
