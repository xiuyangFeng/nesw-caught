from __future__ import annotations

from dataclasses import dataclass

from app.schemas.research import (
    EvaluationMetrics,
    MarketRelevanceAnnotation,
    MarketRelevanceContent,
    MarketRelevanceLabel,
    MarketRelevanceOrigin,
    MarketRelevanceSample,
)
from app.services.news_relevance_evaluator import (
    EvaluationGuardrailError,
    evaluate_market_relevance,
    predict_market_relevance_details,
    predict_market_relevance,
    predict_market_relevance_batch,
)


def _sample(sample_id: str, *, expected: bool, predicted: bool) -> MarketRelevanceSample:
    return MarketRelevanceSample(
        sample_id=sample_id,
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=1,
            source_name="Reuters",
            canonical_url=f"https://example.com/{sample_id}",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="Market update",
            summary="Summary",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=expected,
            noise_type=None if expected else "off_topic",
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    ).model_copy(update={"predicted_market_relevant": predicted})


def test_evaluator_reports_precision_recall_and_noise_rejection() -> None:
    samples = [
        _sample("tp", expected=True, predicted=True),
        _sample("fp", expected=False, predicted=True),
        _sample("tn", expected=False, predicted=False),
        _sample("fn", expected=True, predicted=False),
    ]

    result = evaluate_market_relevance(samples, min_recall=0.0)

    assert result.metrics == EvaluationMetrics(precision=0.5, recall=0.5, noise_rejection_rate=0.5)
    assert result.false_positive_ids == ["fp"]
    assert result.false_negative_ids == ["fn"]


def test_evaluator_rejects_results_below_recall_guardrail() -> None:
    samples = [
        _sample("fn-1", expected=True, predicted=False),
        _sample("fn-2", expected=True, predicted=False),
        _sample("tn", expected=False, predicted=False),
    ]

    try:
        evaluate_market_relevance(samples, min_recall=0.4)
    except EvaluationGuardrailError as exc:
        assert "recall" in str(exc)
        return

    raise AssertionError("expected recall guardrail to fail")


@dataclass
class _FakeClassificationResult:
    keywords: list[str]
    topic_key: str


class _FakeClassifier:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, str | None, bool]] = []

    def classify(
        self,
        *,
        title: str,
        summary: str | None,
        body: str | None,
        allow_llm: bool = True,
    ) -> _FakeClassificationResult:
        self.calls.append((title, summary, body, allow_llm))
        return _FakeClassificationResult(keywords=["revenue", "guidance"], topic_key="nvidia revenue")


def test_predict_market_relevance_filters_generic_tech_chatter() -> None:
    sample = MarketRelevanceSample(
        sample_id="generic-tech",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=2,
            source_name="Tech Blog",
            canonical_url="https://example.com/generic-tech",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="New smartphone camera features impress reviewers",
            summary="A roundup of display, battery, and gaming upgrades.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=False,
            noise_type="generic_tech",
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is False


def test_predict_market_relevance_keeps_market_moving_company_news() -> None:
    sample = MarketRelevanceSample(
        sample_id="company-event",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=3,
            source_name="Reuters",
            canonical_url="https://example.com/company-event",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="Nvidia lifts revenue guidance after AI demand surge",
            summary="Analysts expect the stronger outlook to support semiconductor stocks.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is True


def test_predict_market_relevance_keeps_chinese_earnings_flash() -> None:
    sample = MarketRelevanceSample(
        sample_id="earnings-flash-cn",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=7,
            source_name="CLS Telegraph",
            canonical_url="https://example.com/earnings-flash-cn",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="国药一致业绩快报：2025年净利润11.36亿元，同比增长76.8%",
            summary="公司披露最新业绩快报，净利润同比增长。",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is True


def test_predict_market_relevance_keeps_buyback_and_dividend_updates() -> None:
    sample = MarketRelevanceSample(
        sample_id="buyback-dividend",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=8,
            source_name="CLS Telegraph",
            canonical_url="https://example.com/buyback-dividend",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="英伟达计划将50%的自由现金流用于回报投资者",
            summary="预计将在下半年回购股票，并派息。",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is True


def test_predict_market_relevance_keeps_sec_fund_reporting_updates() -> None:
    sample = MarketRelevanceSample(
        sample_id="sec-fund-reporting",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=9,
            source_name="SEC",
            canonical_url="https://example.com/sec-fund-reporting",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="SEC Proposes Amendments to Reduce Burdens in Reporting of Fund Portfolio Holdings",
            summary="The proposal updates disclosure requirements for registered funds.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is True


def test_predict_market_relevance_does_not_treat_generic_sec_notice_as_market_signal() -> None:
    sample = MarketRelevanceSample(
        sample_id="sec-committee-notice",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=10,
            source_name="SEC",
            canonical_url="https://example.com/sec-committee-notice",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="SEC Seeks Candidates for Membership on the Investor Advisory Committee",
            summary="The Securities and Exchange Commission is seeking candidates for appointment as members of the SEC Investor Advisory Committee.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=False,
            noise_type="low_information",
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is False


def test_predict_market_relevance_keeps_index_spike_updates() -> None:
    sample = MarketRelevanceSample(
        sample_id="index-spike",
        source_type="realtime",
        origin=MarketRelevanceOrigin(
            news_id=11,
            source_name="36Kr",
            canonical_url="https://example.com/index-spike",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="沪指重返3900点上方",
            summary="36氪获悉，沪指重返3900点上方，日内涨超0.5%。",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is True


def test_predict_market_relevance_keeps_commodity_price_wire_updates() -> None:
    sample = MarketRelevanceSample(
        sample_id="commodity-price-wire",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=12,
            source_name="Mysteel",
            canonical_url="https://example.com/commodity-price-wire",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="财联社3月18日电，今日MMLC电池级碳酸锂（早盘）价格较昨日下跌1250元/吨。",
            summary="中间价报154900元/吨。",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is True


def test_predict_market_relevance_keeps_market_stability_measures() -> None:
    sample = MarketRelevanceSample(
        sample_id="market-stability-plan",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=13,
            source_name="CLS Telegraph",
            canonical_url="https://example.com/market-stability-plan",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="财联社3月18日电，据韩国金融监管机构，必要时将扩大100万亿韩元市场稳定计划。",
            summary="监管机构表示必要时将扩大市场稳定计划。",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is True


def test_predict_market_relevance_keeps_concept_mover_wires() -> None:
    sample = MarketRelevanceSample(
        sample_id="concept-mover-wire",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=14,
            source_name="CLS Telegraph",
            canonical_url="https://example.com/concept-mover-wire",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="【腾讯概念持续走高 世纪恒通20cm涨停】",
            summary="腾讯概念盘中持续走高，世纪恒通20cm涨停，云赛智联、绿盟科技、亚康股份等跟涨。",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is True


def test_predict_market_relevance_does_not_keep_generic_product_concept_story() -> None:
    sample = MarketRelevanceSample(
        sample_id="generic-product-concept",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=15,
            source_name="36Kr",
            canonical_url="https://example.com/generic-product-concept",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="腾讯概念新品发布会带动用户讨论",
            summary="文章介绍新版本功能体验，称相关概念热度走高，但没有任何二级市场价格信息。",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=False,
            noise_type="generic_tech",
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is False


def test_predict_market_relevance_keeps_shipping_route_disruption_updates() -> None:
    sample = MarketRelevanceSample(
        sample_id="shipping-route-disruption",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=16,
            source_name="WSJ World News",
            canonical_url="https://example.com/shipping-route-disruption",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="Shippers Wary of Red Sea Routes Despite Houthi Pledge to End Targeting",
            summary="The world's top three container operators said they fear instability in Gaza and broader regional tensions mean continued danger.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is True


def test_predict_market_relevance_does_not_keep_generic_gaza_humanitarian_updates() -> None:
    sample = MarketRelevanceSample(
        sample_id="gaza-humanitarian-update",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=17,
            source_name="CLS Telegraph",
            canonical_url="https://example.com/gaza-humanitarian-update",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="拉法口岸18日起重新开放 允许有限人员双向通行",
            summary="拉法口岸位于加沙地带南部与埃及交界处，对加沙地带人道主义援助至关重要。",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=False,
            noise_type="off_topic",
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is False


def test_predict_market_relevance_keeps_taiwan_arms_sale_updates() -> None:
    sample = MarketRelevanceSample(
        sample_id="taiwan-arms-sale",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=18,
            source_name="CLS Telegraph",
            canonical_url="https://example.com/taiwan-arms-sale",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="【国台办回应美国对台军售】据路透报道，美国一项涵盖先进拦截导弹的对台大型军售案准备呈交总统批准。",
            summary="发言人表示坚决反对有关国家向中国台湾地区出售武器。",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is True


def test_sector_tag_ai_compute_story() -> None:
    sample = MarketRelevanceSample(
        sample_id="sector-ai-compute",
        source_type="realtime",
        origin=MarketRelevanceOrigin(
            news_id=19,
            source_name="The News API",
            canonical_url="https://example.com/sector-ai-compute",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="Nvidia suppliers raise AI server outlook on stronger GPU demand",
            summary="Server builders said AI compute demand is accelerating into the second half.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    details = predict_market_relevance_details(sample)

    assert details.is_market_relevant is True
    assert "ai_compute" in details.sector_tags


def test_sector_tag_semiconductor_export_control_story() -> None:
    sample = MarketRelevanceSample(
        sample_id="sector-semiconductor",
        source_type="realtime",
        origin=MarketRelevanceOrigin(
            news_id=20,
            source_name="Reuters",
            canonical_url="https://example.com/sector-semiconductor",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="U.S. weighs tighter chip export controls on advanced AI semiconductors",
            summary="The proposal could hit semiconductor equipment and advanced chip supply chains.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    details = predict_market_relevance_details(sample)

    assert details.is_market_relevant is True
    assert "semiconductors" in details.sector_tags


def test_sector_tag_chinese_internet_story() -> None:
    sample = MarketRelevanceSample(
        sample_id="sector-chinese-internet",
        source_type="realtime",
        origin=MarketRelevanceOrigin(
            news_id=21,
            source_name="HKEX",
            canonical_url="https://example.com/sector-chinese-internet",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="Tencent flags stronger advertising demand and gaming recovery in latest results",
            summary="Management said the Chinese internet platform business improved across key segments.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    details = predict_market_relevance_details(sample)

    assert details.is_market_relevant is True
    assert "chinese_internet" in details.sector_tags


def test_sector_tag_apple_supply_chain_story() -> None:
    sample = MarketRelevanceSample(
        sample_id="sector-apple-supply-chain",
        source_type="realtime",
        origin=MarketRelevanceOrigin(
            news_id=22,
            source_name="The News API",
            canonical_url="https://example.com/sector-apple-supply-chain",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="Apple suppliers brace for stronger iPhone demand after display and camera orders rise",
            summary="Consumer electronics names tied to the Apple supply chain gained on the report.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    details = predict_market_relevance_details(sample)

    assert details.is_market_relevant is True
    assert "apple_supply_chain" in details.sector_tags


def test_sector_tag_does_not_keep_generic_product_chatter() -> None:
    sample = MarketRelevanceSample(
        sample_id="sector-generic-product-chatter",
        source_type="realtime",
        origin=MarketRelevanceOrigin(
            news_id=23,
            source_name="The Verge",
            canonical_url="https://example.com/sector-generic-product-chatter",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="iPhone camera review says display upgrade and battery life look better this year",
            summary="Reviewers highlighted the camera and display changes after early hands-on testing.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=False,
            noise_type="generic_tech",
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    details = predict_market_relevance_details(sample)

    assert details.is_market_relevant is False


def test_sector_tag_does_not_keep_generic_server_refresh_story() -> None:
    sample = MarketRelevanceSample(
        sample_id="sector-generic-server-refresh",
        source_type="realtime",
        origin=MarketRelevanceOrigin(
            news_id=24,
            source_name="The News API",
            canonical_url="https://example.com/sector-generic-server-refresh",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="Dell server demand improves in enterprise refresh cycle",
            summary="Customers are replacing older enterprise servers after a routine infrastructure refresh.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=False,
            noise_type="generic_tech",
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    details = predict_market_relevance_details(sample)

    assert details.is_market_relevant is False


def test_predict_market_relevance_does_not_keep_generic_un_security_council_update() -> None:
    sample = MarketRelevanceSample(
        sample_id="un-security-council-update",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=19,
            source_name="Xinhua",
            canonical_url="https://example.com/un-security-council-update",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="联合国安理会就叙利亚局势举行会议",
            summary="与会代表呼吁有关各方继续通过外交渠道缓和局势。",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=False,
            noise_type="off_topic",
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is False


def test_predict_market_relevance_uses_classifier_with_body_excerpt() -> None:
    sample = MarketRelevanceSample(
        sample_id="body-assisted",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=5,
            source_name="Reuters",
            canonical_url="https://example.com/body-assisted",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="Company update",
            summary="Short summary",
            body_excerpt="Detailed body text mentions revenue guidance for the next quarter.",
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )
    classifier = _FakeClassifier()

    assert predict_market_relevance(sample, classifier=classifier) is True
    assert classifier.calls == [
        (
            "Company update",
            "Short summary",
            "Detailed body text mentions revenue guidance for the next quarter.",
            False,
        )
    ]


def test_predict_market_relevance_batch_stays_rule_only_when_ai_is_enabled(monkeypatch) -> None:
    sample = MarketRelevanceSample(
        sample_id="offline-batch",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=6,
            source_name="Reuters",
            canonical_url="https://example.com/offline-batch",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="Nvidia lifts revenue guidance after AI demand surge",
            summary="Analysts expect the stronger outlook to support semiconductor stocks.",
            body_excerpt="Body text adds more demand and forecast detail.",
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    monkeypatch.setattr(
        "app.services.news_signal_classifier.get_settings",
        lambda: type("Settings", (), {"ai_enabled": True})(),
    )
    monkeypatch.setattr(
        "app.services.news_signal_classifier.build_provider",
        lambda _config: (_ for _ in ()).throw(AssertionError("batch prediction must stay offline")),
    )

    predicted = predict_market_relevance_batch([sample], session=object())

    assert predicted[0].predicted_market_relevant is True


def test_evaluator_requires_explicit_predictions() -> None:
    sample = MarketRelevanceSample(
        sample_id="missing-prediction",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=4,
            source_name="Reuters",
            canonical_url="https://example.com/missing-prediction",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="Oil prices move after OPEC talks",
            summary="Energy stocks were active in premarket trading.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    try:
        evaluate_market_relevance([sample], min_recall=0.0)
    except EvaluationGuardrailError as exc:
        assert "predicted_market_relevant" in str(exc)
        return

    raise AssertionError("expected evaluator to reject samples without explicit predictions")
