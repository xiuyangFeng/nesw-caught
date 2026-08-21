from app.services.quant.research.pack import RESEARCH_MODULE_KEYS, build_research_pack


def test_research_pack_answers_all_section_61_modules_without_inventing_price() -> None:
    pack = build_research_pack(
        symbol="600519.SH",
        display_name="贵州茅台",
        news=[
            {
                "id": 11,
                "title": "贵州茅台发布年报",
                "source_name": "巨潮资讯网",
                "summary": "营收增长",
            }
        ],
        peers=["000858.SZ"],
    )
    assert [module.key for module in pack.modules] == list(RESEARCH_MODULE_KEYS)
    valuation = next(module for module in pack.modules if module.key == "valuation")
    assert valuation.gap == "no_financials_or_consensus"
    assert "目标价" not in (valuation.answer or "")
    events = next(module for module in pack.modules if module.key == "latest_events")
    assert events.evidence_ids == ["news:11"]
    assert pack.ask_ai_context
    assert "600519.SH" in pack.ask_ai_context


def test_research_pack_fills_valuation_with_financials_when_covered() -> None:
    pack = build_research_pack(
        symbol="600519.SH",
        display_name="贵州茅台",
        news=[],
        financials={
            "period_end": "2024-06-30",
            "available_at": "2024-08-31",
            "revenue_yoy": 0.21,
            "net_profit_yoy": 0.18,
            "roe": 16.5,
            "gross_margin": 92.0,
        },
    )
    valuation = next(module for module in pack.modules if module.key == "valuation")
    assert valuation.gap is None
    assert "2024-06-30" in (valuation.answer or "")
    assert "18.0%" in (valuation.answer or "")
    assert "16.5" in (valuation.answer or "")
    assert valuation.evidence_ids == ["financial:600519.SH:2024-06-30"]
    # 即便有财务，仍明确声明不给目标价（不编造价格锚）
    assert "不给出目标价" in (valuation.answer or "")


def test_latest_financials_returns_none_without_coverage() -> None:
    from app.services.quant.research.pack import latest_financials

    assert latest_financials("999999.SZ") is None
