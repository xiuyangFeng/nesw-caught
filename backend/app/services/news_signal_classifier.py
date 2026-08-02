from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.core.config import get_settings
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.services.llm_providers import build_provider
from app.services.news_structured_summary import build_structured_takeaway
from app.services.topic_naming import resolve_topic_display_name

logger = logging.getLogger(__name__)

# 情绪精修专用 system prompt：必须与 _llm_refine 的 user prompt 要求的 key 集合一致
# (sentiment_label/sentiment_score/summary/keywords/topic_title_hint/takeaway)。
# 不能复用 analyze_json 默认的选股分析 system prompt(top_pick/candidates/...)，
# 否则模型大概率按错误 schema 返回、导致 sentiment_label 等字段为空静默回退规则结果。
SENTIMENT_REFINE_SYSTEM_PROMPT = (
    "You are a financial news sentiment classifier. Return JSON only (no markdown, "
    "no extra commentary) with exactly these keys: "
    "sentiment_label (string, one of \"positive\", \"negative\", \"neutral\"), "
    "sentiment_score (number from -1.0 to 1.0; negative=bearish, positive=bullish, 0=neutral), "
    "summary (short string summarizing the news), "
    "keywords (JSON array of up to 6 lowercase keyword strings), "
    "topic_title_hint (short topic title string), "
    "takeaway (a single Chinese sentence, at most 60 characters, stating who is affected, "
    "whether it is bullish or bearish, and why; return an empty string if it cannot be judged)."
)

POSITIVE_TERMS = {
    "beat": 0.7,
    "growth": 0.6,
    "improves": 0.5,
    "improved": 0.5,
    "boost": 0.7,
    "constructive": 0.4,
    "expands": 0.5,
    "higher": 0.4,
    "strong": 0.6,
}

NEGATIVE_TERMS = {
    "weak": -0.7,
    "weakens": -0.8,
    "weaker": -0.7,
    "soft": -0.5,
    "softer": -0.5,
    "lower": -0.4,
    "risk": -0.5,
    "warning": -0.6,
    "pressure": -0.4,
}

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "into",
    "from",
    "after",
    "ahead",
    "near",
    "term",
    "still",
    "points",
    "point",
    "market",
    "markets",
    "update",
    "latest",
    "news",
    "officials",
    "existing",
    "without",
    "next",
    "cycle",
    "remains",
    "remain",
    "focus",
    "keeps",
    "unchanged",
    "described",
    "mixed",
    "timing",
}

THEME_TERMS = {
    "ai",
    "cloud",
    "revenue",
    "smartphone",
    "demand",
    "supply",
    "oil",
    "energy",
    "shipment",
    "shipments",
    "orders",
    "monetization",
    "platform",
}

POSITIVE_ZH = {
    "利好": 0.7,
    "上涨": 0.6,
    "大涨": 0.8,
    "反弹": 0.5,
    "增长": 0.6,
    "超预期": 0.7,
    "强劲": 0.6,
    "突破": 0.6,
    "新高": 0.7,
    "盈利": 0.6,
    "提振": 0.6,
    "看好": 0.5,
    "机遇": 0.5,
    "乐观": 0.5,
    "回暖": 0.5,
    "走高": 0.5,
    "攀升": 0.5,
    "提升": 0.4,
    "加快": 0.4,
}

NEGATIVE_ZH = {
    "利空": -0.7,
    "下跌": -0.6,
    "大跌": -0.8,
    "暴跌": -0.9,
    "下滑": -0.5,
    "亏损": -0.7,
    "衰退": -0.7,
    "风险": -0.5,
    "警告": -0.6,
    "收紧": -0.5,
    "放缓": -0.4,
    "承压": -0.5,
    "疲软": -0.6,
    "下调": -0.5,
    "违约": -0.7,
    "制裁": -0.6,
    "处罚": -0.6,
    "崩盘": -0.9,
}

THEME_ZH = {
    "财报": "财报",
    "营收": "营收",
    "业绩": "业绩",
    "并购": "并购",
    "收购": "收购",
    "监管": "监管",
    "上市": "上市",
    "融资": "融资",
    "芯片": "芯片",
    "半导体": "半导体",
    "人工智能": "人工智能",
    "模型": "模型",
    "新能源": "新能源",
    "产能": "产能",
    "供应链": "供应链",
    "出货": "出货",
    "订单": "订单",
    "宏观": "宏观",
    "通胀": "通胀",
    "降息": "降息",
    "加息": "加息",
    "利率": "利率",
}


@dataclass(frozen=True)
class ClassificationResult:
    sentiment_label: str
    sentiment_score: float
    signal_confidence: float
    keywords: list[str]
    topic_key: str
    summary: str | None
    classifier_type: str
    llm_error: str | None = None
    topic_title_hint: str | None = None
    topic_summary_hint: str | None = None
    takeaway: str | None = None


class NewsSignalClassifier:
    def __init__(self, session) -> None:
        self.config_repository = LLMProviderConfigRepository(session)
        # 情绪 LLM 精修返回 payload 缺 key/类型错误时的失败计数(实例级，供日志/调试观察，
        # 不再像改造前那样完全静默回退)。
        self.llm_refine_failure_count = 0

    def classify(
        self,
        *,
        title: str,
        summary: str | None,
        body: str | None,
        allow_llm: bool = True,
    ) -> ClassificationResult:
        text = " ".join(part for part in [title, summary or "", body or ""] if part).lower()
        tokens = self._tokenize(text)
        score = (
            sum(POSITIVE_TERMS.get(token, 0.0) for token in tokens)
            + sum(NEGATIVE_TERMS.get(token, 0.0) for token in tokens)
            + sum(POSITIVE_ZH.get(token, 0.0) for token in tokens)
            + sum(NEGATIVE_ZH.get(token, 0.0) for token in tokens)
        )

        if score >= 0.2:
            label = "positive"
        elif score <= -0.2:
            label = "negative"
        else:
            label = "neutral"

        confidence = min(0.95, 0.35 + min(abs(score), 1.0) * 0.5)
        keywords = self._keywords(tokens)
        topic_key = self._topic_key(tokens, keywords)

        topic_title_hint = resolve_topic_display_name(
            topic_key=topic_key,
            topic_title=" ".join(token.capitalize() for token in topic_key.split()),
            keywords=keywords,
        )
        structured = build_structured_takeaway(title=title, summary=summary, keywords=keywords)
        summary_hint = summary or body or structured or title
        result = ClassificationResult(
            sentiment_label=label,
            sentiment_score=round(max(-1.0, min(1.0, score)), 4),
            signal_confidence=round(confidence, 4),
            keywords=keywords,
            topic_key=topic_key,
            summary=(summary_hint[:280] if summary_hint else None),
            classifier_type="rule",
            topic_title_hint=topic_title_hint,
            topic_summary_hint=(summary_hint[:280] if summary_hint else None),
            takeaway=structured[:120],
        )

        should_refine = allow_llm and get_settings().ai_enabled and confidence <= 0.55
        if not should_refine:
            return result
        return self._llm_refine(result, title=title, summary=summary, body=body)

    def _llm_refine(
        self,
        baseline: ClassificationResult,
        *,
        title: str,
        summary: str | None,
        body: str | None,
    ) -> ClassificationResult:
        config = self.config_repository.get_active()
        if config is None:
            return baseline

        prompt = "\n".join(
            [
                f"Title: {title}",
                f"Summary: {summary or ''}",
                f"Body: {body or ''}",
                "Return JSON only with keys: sentiment_label, sentiment_score, summary, keywords, topic_title_hint, takeaway.",
                "takeaway: 一句中文结论(<=60字),说明谁受影响、偏利好还是利空、原因;无法判断时返回空字符串。",
            ]
        )
        try:
            payload = build_provider(config).analyze_json(
                prompt=prompt,
                title=title,
                summary=summary,
                system_prompt=SENTIMENT_REFINE_SYSTEM_PROMPT,
                cache_scope="sentiment",
            )
        except Exception as exc:
            self._record_llm_refine_failure("llm_call_exception", detail=str(exc))
            return ClassificationResult(
                **{**baseline.__dict__, "classifier_type": "hybrid", "llm_error": str(exc)}
            )

        if not isinstance(payload, dict):
            self._record_llm_refine_failure(
                "invalid_payload_type", detail=f"payload type={type(payload).__name__}"
            )
            return baseline

        # 单次精修内的多个字段问题合并计一次失败(而不是每个字段各计一次)，
        # 计数语义是"这次 LLM 精修是否可信"，而非字段问题数量。
        issues: list[str] = []
        label_raw = payload.get("sentiment_label")
        label = str(label_raw or baseline.sentiment_label).lower()
        if label_raw is None:
            issues.append("missing_sentiment_label")
        elif label not in {"positive", "negative", "neutral"}:
            issues.append(f"invalid_sentiment_label={label_raw!r}")
            label = baseline.sentiment_label
        try:
            score = float(payload.get("sentiment_score"))
        except (TypeError, ValueError):
            issues.append(f"invalid_sentiment_score={payload.get('sentiment_score')!r}")
            score = baseline.sentiment_score
        if issues:
            self._record_llm_refine_failure("payload_schema_mismatch", detail="; ".join(issues))
        raw_keywords = payload.get("keywords")
        keywords = (
            [str(item).strip().lower() for item in raw_keywords if str(item).strip()]
            if isinstance(raw_keywords, list)
            else baseline.keywords
        )
        topic_title_hint = str(payload.get("topic_title_hint") or baseline.topic_title_hint)
        summary_text = (
            str(payload.get("summary") or baseline.summary)
            if (payload.get("summary") or baseline.summary)
            else None
        )
        takeaway_raw = payload.get("takeaway")
        takeaway_text = str(takeaway_raw).strip() if takeaway_raw else ""
        takeaway = takeaway_text[:120] if takeaway_text else None
        return ClassificationResult(
            sentiment_label=label,
            sentiment_score=round(max(-1.0, min(1.0, score)), 4),
            signal_confidence=round(min(0.99, max(baseline.signal_confidence, 0.7)), 4),
            keywords=keywords[:6] or baseline.keywords,
            topic_key=self._topic_key(
                self._tokenize(" ".join(keywords)), keywords[:6] or baseline.keywords
            ),
            summary=summary_text[:280] if summary_text else None,
            classifier_type="hybrid",
            llm_error=baseline.llm_error,
            topic_title_hint=topic_title_hint[:255]
            if topic_title_hint
            else baseline.topic_title_hint,
            topic_summary_hint=summary_text[:280] if summary_text else baseline.topic_summary_hint,
            takeaway=takeaway,
        )

    def _record_llm_refine_failure(self, reason: str, *, detail: str | None = None) -> None:
        """记 warning 日志 + 累加实例级失败计数。

        改造前 LLM 返回缺 key/类型错误时静默回退规则结果，问题难以从日志发现；
        这里保留同样的回退行为，只是不再完全静默。
        """
        self.llm_refine_failure_count += 1
        logger.warning(
            "news_signal_classifier sentiment LLM refine payload issue (reason=%s%s); "
            "falling back to rule baseline field(s)",
            reason,
            f", detail={detail}" if detail else "",
        )

    def _zh_tokens(self, text: str) -> list[str]:
        all_terms: dict[str, float | str] = {**POSITIVE_ZH, **NEGATIVE_ZH, **THEME_ZH}
        matched: list[str] = []
        seen: set[str] = set()
        for term in sorted(all_terms, key=len, reverse=True):
            if term in seen:
                continue
            if term in text:
                matched.append(term)
                seen.add(term)
        return matched

    def _tokenize(self, text: str) -> list[str]:
        en_tokens = [
            token for token in re.findall(r"[a-z0-9]+", text) if token and token not in STOPWORDS
        ]
        zh_tokens = self._zh_tokens(text)
        return en_tokens + zh_tokens

    def _keywords(self, tokens: list[str]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        zh_sentiment_terms = set(POSITIVE_ZH.keys()) | set(NEGATIVE_ZH.keys())
        for token in tokens:
            if (
                token in seen
                or token in POSITIVE_TERMS
                or token in NEGATIVE_TERMS
                or token in zh_sentiment_terms
            ):
                continue
            if len(token) <= 2 and token not in {"ai"}:
                continue
            ordered.append(token)
            seen.add(token)
        return ordered[:6]

    def _topic_key(self, tokens: list[str], keywords: list[str]) -> str:
        if not keywords:
            return "general-market-update"

        entity = keywords[0]
        theme = [token for token in keywords[1:] if token in THEME_TERMS or token in THEME_ZH][:2]
        if not theme:
            theme = keywords[1:3]
        candidate = [entity, *theme]
        return " ".join(candidate[:3]) if candidate else "general-market-update"
