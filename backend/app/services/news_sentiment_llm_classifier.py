"""纯 LLM 情绪分类器（情绪评测重构 Phase 1 工作块 B）。

与 news_signal_classifier.py 里生产路径的"规则打底 + 置信度不足才 LLM 精修"
的混合分类器不同，这里是评测专用的"每条样本都直接问 LLM"纯分类器，用于
POST /sentiment/run 的 `llm:<provider>/<model>` run —— 真实评估 LLM 单独的
情绪判断能力，而不是生产路径的混合效果（混合效果由
news_sentiment_evaluator.build_hybrid_sentiment_classifier 覆盖）。

复用工作块 A 改造后的 analyze_json(system_prompt=, cache_scope=) 参数化入口，
专用 system prompt 只要求返回 {"sentiment_label", "sentiment_score"}，不会
和选股分析/情绪精修的 prompt schema 冲突，也不会互相命中对方的分类缓存
（cache_scope 各自独立）。
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.models.llm_provider_config import LLMProviderConfig
from app.schemas.sentiment_eval import SENTIMENT_LABELS, SentimentGoldSample
from app.services.llm_providers import build_provider

logger = logging.getLogger(__name__)

# 情绪评测专用 cache_scope：与生产路径的情绪精修(scope="sentiment")、
# 选股分析(scope=None/"news_analysis")均不同，三条路径互不命中彼此缓存。
SENTIMENT_EVAL_CACHE_SCOPE = "sentiment-eval"

SENTIMENT_EVAL_SYSTEM_PROMPT = (
    "You are a financial news sentiment classifier used for an offline evaluation "
    "harness. Return JSON only (no markdown, no extra commentary) with exactly these "
    "keys: sentiment_label (string, one of \"positive\", \"negative\", \"neutral\"), "
    "sentiment_score (number from -1.0 to 1.0; negative=bearish, positive=bullish, "
    "0=neutral)."
)


class NewsSentimentLLMClassifier:
    """把 (title, summary, body, market) 逐样本喂给 LLM，失败则回退规则分类。

    ``rule_fallback`` 是注入的规则分类函数（sample -> label），单样本 LLM 调用
    异常、返回非 dict、或 sentiment_label 缺失/非法时，回退到它并计数——不静默。
    ``fallback_count`` / ``call_count`` 供路由把回退比例写进响应 note。
    """

    def __init__(
        self,
        *,
        config: LLMProviderConfig,
        rule_fallback: Callable[[SentimentGoldSample], str],
    ) -> None:
        self.config = config
        self.rule_fallback = rule_fallback
        self.fallback_count = 0
        self.call_count = 0

    def classify(self, sample: SentimentGoldSample) -> str:
        self.call_count += 1
        try:
            payload = build_provider(self.config).analyze_json(
                prompt=self._build_prompt(sample),
                title=sample.effective_title,
                summary=sample.summary,
                market=sample.market,
                system_prompt=SENTIMENT_EVAL_SYSTEM_PROMPT,
                cache_scope=SENTIMENT_EVAL_CACHE_SCOPE,
            )
        except Exception as exc:  # noqa: BLE001 - 统一回退，异常类型由 provider 决定
            logger.warning(
                "sentiment eval LLM classification failed for sample %s: %s",
                sample.sample_id,
                exc,
            )
            self.fallback_count += 1
            return self.rule_fallback(sample)

        label = payload.get("sentiment_label") if isinstance(payload, dict) else None
        if not isinstance(label, str) or label not in SENTIMENT_LABELS:
            logger.warning(
                "sentiment eval LLM returned invalid sentiment_label for sample %s: %r",
                sample.sample_id,
                label,
            )
            self.fallback_count += 1
            return self.rule_fallback(sample)
        return label

    @staticmethod
    def _build_prompt(sample: SentimentGoldSample) -> str:
        return "\n".join(
            [
                f"Title: {sample.effective_title}",
                f"Summary: {sample.summary or ''}",
                f"Body: {sample.body or ''}",
                "Return JSON only with keys: sentiment_label, sentiment_score.",
            ]
        )
