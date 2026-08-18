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
