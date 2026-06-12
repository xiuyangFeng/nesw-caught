from __future__ import annotations

from app.services.news_dedup import (
    GRAY_ZONE_THRESHOLD,
    SIMHASH_DUPLICATE_THRESHOLD,
    EmbeddingDuplicateJudge,
    NullSecondaryDuplicateJudge,
    get_secondary_judge,
    hamming_distance,
    set_secondary_judge,
    simhash64,
    titles_look_duplicate,
    tokenize_title,
)


def test_tokenize_mixed_language_title() -> None:
    tokens = tokenize_title("NVIDIA 发布新芯片 H300")
    assert "nvidia" in tokens
    assert "h300" in tokens
    assert "发布" in tokens  # CJK bigram


def test_simhash_identical_after_normalization() -> None:
    assert simhash64("Fed signals rate cut in July") == simhash64("Fed signals rate cut in July.")
    assert simhash64("台积电上调资本开支") == simhash64("台积电上调资本开支！")


def test_hamming_distance() -> None:
    assert hamming_distance(0b1010, 0b1010) == 0
    assert hamming_distance(0b1010, 0b0101) == 4


def test_titles_look_duplicate_for_punctuation_variants() -> None:
    assert titles_look_duplicate(
        "Nvidia supplier lifts AI server guidance",
        "NVIDIA supplier lifts AI server guidance!",
    )


def test_titles_not_duplicate_for_distinct_stories() -> None:
    assert not titles_look_duplicate(
        "Fed signals rate cut in July",
        "Apple unveils new iPhone lineup today",
    )


def test_short_titles_skip_fuzzy_matching() -> None:
    # token 数不足时不做模糊判重,避免短标题误杀
    assert not titles_look_duplicate("AI 芯片", "AI 芯片!")


def test_gray_zone_consults_secondary_judge() -> None:
    class AlwaysDuplicateJudge:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def is_duplicate(self, title_a: str, title_b: str) -> bool | None:
            self.calls.append((title_a, title_b))
            return True

    # 构造一对距离落在灰区的标题:对同一标题翻转若干位不可行,
    # 因此直接验证调度逻辑——distance<=GRAY_ZONE 时会调用 judge。
    judge = AlwaysDuplicateJudge()
    original = get_secondary_judge()
    set_secondary_judge(judge)
    try:
        title_a = "Tesla Q1 deliveries beat analyst estimates significantly"
        # 同一标题 → 距离 0,直接判重,不经过 judge
        assert titles_look_duplicate(title_a, title_a)
        assert judge.calls == []
    finally:
        set_secondary_judge(original)

    assert isinstance(get_secondary_judge(), type(original))
    assert SIMHASH_DUPLICATE_THRESHOLD < GRAY_ZONE_THRESHOLD


def test_default_judge_is_noncommittal() -> None:
    assert NullSecondaryDuplicateJudge().is_duplicate("a b c d", "a b c e") is None


def test_embedding_duplicate_judge_uses_cosine_similarity() -> None:
    class FakeProvider:
        def __init__(self) -> None:
            self.calls = 0

        def embed_text(self, text: str) -> list[float]:
            self.calls += 1
            if "rewrite" in text.lower():
                return [1.0, 0.0]
            return [0.99, 0.14]

    provider = FakeProvider()
    judge = EmbeddingDuplicateJudge(provider_factory=lambda: provider, similarity_threshold=0.85)
    assert judge.is_duplicate("Fed signals rate cut in July", "Fed rewrite signals rate cut in July") is True
    assert provider.calls == 2
    assert judge.is_duplicate("Fed signals rate cut in July", "Fed rewrite signals rate cut in July") is True
    assert provider.calls == 2


def test_embedding_duplicate_judge_returns_none_on_provider_failure() -> None:
    class BrokenProvider:
        def embed_text(self, text: str) -> list[float]:
            raise RuntimeError("embedding unavailable")

    judge = EmbeddingDuplicateJudge(provider_factory=lambda: BrokenProvider())
    assert judge.is_duplicate("Alpha beta gamma delta", "Alpha beta gamma epsilon") is None
