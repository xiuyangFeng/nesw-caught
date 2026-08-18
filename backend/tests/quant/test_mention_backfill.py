from app.services.quant.mention_backfill import (
    build_mention_index,
    match_a_share_mentions,
)


def test_title_name_outranks_body_and_skips_stop_words() -> None:
    index = build_mention_index(
        [
            {"symbol": "600519.SH", "display_name": "贵州茅台", "market": "cn"},
            {"symbol": "000001.SZ", "display_name": "平安银行", "market": "cn"},
            {"symbol": "000839.SZ", "display_name": "国安", "market": "cn"},
        ]
    )
    hits = match_a_share_mentions(
        "贵州茅台发布年报",
        "与国安无关的摘要",
        "正文里再次出现贵州茅台，也出现国安两个字。",
        index=index,
    )
    symbols = {hit.symbol: hit for hit in hits}
    assert "600519.SH" in symbols
    assert symbols["600519.SH"].where == "title"
    assert symbols["600519.SH"].confidence == 0.9
    assert "000839.SZ" not in symbols


def test_six_digit_code_in_title_maps_symbol() -> None:
    index = build_mention_index([{"symbol": "300750.SZ", "display_name": "宁德时代", "market": "cn"}])
    hits = match_a_share_mentions("关注 300750 的订单", None, None, index=index)
    assert [hit.symbol for hit in hits] == ["300750.SZ"]
    assert hits[0].confidence == 0.95
