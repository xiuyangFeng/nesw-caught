"""标题级近重复判定。

- SimHash(64-bit)+ 汉明距离,识别"换了标点/微调措辞"的跨源重复标题;
- 预留二次判重接口(SecondaryDuplicateJudge),将来可接 embedding 相似度,
  当前默认实现不表态(返回 None),即灰区不判重。

设计取舍:simhash 不落库、不建索引,在 ±60 分钟去重窗口内对候选标题
即时计算。窗口内候选通常只有几十条,计算成本可忽略,换来零 schema 迁移。
"""

from __future__ import annotations

import logging
import math
import re
from collections import OrderedDict
from collections.abc import Callable
from functools import lru_cache
from hashlib import sha256
from typing import Protocol

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.services.llm_providers import LLMProviderError, build_provider

# 汉明距离 <= 该值:直接判定为重复。
SIMHASH_DUPLICATE_THRESHOLD = 3
# 汉明距离在 (SIMHASH_DUPLICATE_THRESHOLD, GRAY_ZONE_THRESHOLD] 之间:交给二次判重接口。
GRAY_ZONE_THRESHOLD = 6
# 标题 token 数低于该值时不做模糊判重(短标题误杀率高,只走精确签名)。
MIN_TOKENS_FOR_FUZZY = 4

_LATIN_TOKEN_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[一-鿿]")
# 数字指纹:整数/小数/百分数,含中文数量单位前的数字("50.68万"取 50.68 + 万)。
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
_CJK_MONTH_RE = re.compile(r"(\d{1,2})\s*月")
# simhash 记忆化容量:一次 prime 生命周期内窗口候选通常几十~几百条,
# 4096 足以让整批比较全部命中缓存(修复 P1-3 的 O(items×candidates×tokens))。
_SIMHASH_CACHE_SIZE = 4096


def tokenize_title(title: str) -> list[str]:
    """拉丁词 + 中文字符 bigram。混排标题两类 token 并存。"""
    lowered = title.lower()
    tokens = _LATIN_TOKEN_RE.findall(lowered)
    cjk_chars = _CJK_RE.findall(lowered)
    if len(cjk_chars) == 1:
        tokens.append(cjk_chars[0])
    else:
        # Pairwise bigram idiom: the two iterables differ in length by design
        # (offset by one), so strict pairing is deliberately off here.
        tokens.extend(a + b for a, b in zip(cjk_chars, cjk_chars[1:], strict=False))
    return tokens


@lru_cache(maxsize=_SIMHASH_CACHE_SIZE)
def simhash64(title: str) -> int:
    """标题 SimHash(64-bit),按标题字符串记忆化。

    修复 P1-3：`titles_look_duplicate` 此前每次调用都重算两侧 simhash
    (每 token 一次 sha256、无缓存),而它跑在【持有 SQLite 写连接的串行落库段】里,
    复杂度是 O(items × candidates × tokens)。同一批候选标题会被反复比较,
    记忆化后同一标题只算一次。测试可用 `simhash64.cache_clear()` 复位。
    """
    tokens = tokenize_title(title)
    if not tokens:
        return 0

    weights = [0] * 64
    for token in tokens:
        digest = sha256(token.encode("utf-8")).digest()
        token_hash = int.from_bytes(digest[:8], "big")
        for bit in range(64):
            if token_hash >> bit & 1:
                weights[bit] += 1
            else:
                weights[bit] -= 1

    value = 0
    for bit in range(64):
        if weights[bit] > 0:
            value |= 1 << bit
    return value


def hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


class SecondaryDuplicateJudge(Protocol):
    """二次判重接口:用于 simhash 灰区(距离 4~6)的精细判定。

    返回值语义:True=重复 / False=不重复 / None=不表态(按不重复处理)。
    将来接 embedding 相似度时实现本协议并替换 get_secondary_judge。
    """

    def is_duplicate(self, title_a: str, title_b: str) -> bool | None: ...


class NullSecondaryDuplicateJudge:
    """默认实现:不做任何二次判定(embedding 判重的占位)。"""

    def is_duplicate(self, title_a: str, title_b: str) -> bool | None:
        return None


class EmbeddingDuplicateJudge:
    """SimHash 灰区 embedding 二次判重。"""

    def __init__(
        self,
        *,
        provider_factory: Callable[[], object] | None = None,
        similarity_threshold: float = 0.85,
        cache_size: int = 512,
    ) -> None:
        self.provider_factory = provider_factory or self._default_provider_factory
        self.similarity_threshold = similarity_threshold
        self._cache: OrderedDict[tuple[str, str], bool | None] = OrderedDict()
        self._cache_size = cache_size
        self.logger = logging.getLogger(__name__)

    def _default_provider_factory(self):
        with SessionLocal() as session:
            config = LLMProviderConfigRepository(session).get_active()
        if config is None:
            raise LLMProviderError("llm provider is not configured")
        return build_provider(config)

    def _cache_key(self, title_a: str, title_b: str) -> tuple[str, str]:
        return tuple(sorted((title_a.strip(), title_b.strip())))

    def _remember(self, key: tuple[str, str], value: bool | None) -> bool | None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return value

    def is_duplicate(self, title_a: str, title_b: str) -> bool | None:
        key = self._cache_key(title_a, title_b)
        cached = self._cache.get(key)
        if key in self._cache:
            self._cache.move_to_end(key)
            return cached

        try:
            provider = self.provider_factory()
            left = provider.embed_text(title_a)
            right = provider.embed_text(title_b)
            similarity = _cosine_similarity(left, right)
            return self._remember(key, similarity >= self.similarity_threshold)
        except Exception:
            self.logger.exception("embedding duplicate judge failed")
            return self._remember(key, None)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def configure_secondary_judge_from_settings() -> None:
    settings = get_settings()
    if settings.dedup_secondary_judge == "embedding":
        set_secondary_judge(EmbeddingDuplicateJudge())
    else:
        set_secondary_judge(NullSecondaryDuplicateJudge())


_secondary_judge: SecondaryDuplicateJudge = NullSecondaryDuplicateJudge()


def get_secondary_judge() -> SecondaryDuplicateJudge:
    return _secondary_judge


def set_secondary_judge(judge: SecondaryDuplicateJudge) -> None:
    global _secondary_judge
    _secondary_judge = judge


def numeric_fingerprint(title: str) -> frozenset[str]:
    """标题里的数字/月份指纹。

    金融快讯恰恰靠数字区分:"CPI 同比上涨 0.2%" vs "0.6%"、
    "初请失业金 21.9万" vs "23.9万"、"11月销量" vs "10月销量"。
    千分位逗号统一去掉,避免 "1,250" 与 "1250" 被当成不同数字。
    """
    numbers = {value.replace(",", "") for value in _NUMBER_RE.findall(title)}
    months = {f"m{value}" for value in _CJK_MONTH_RE.findall(title)}
    return frozenset(numbers | months)


def numbers_contradict(title_a: str, title_b: str) -> bool:
    """两个标题的数字指纹是否互相矛盾(至少一侧有数字且两侧不相等)。"""
    left = numeric_fingerprint(title_a)
    right = numeric_fingerprint(title_b)
    if not left and not right:
        return False
    return left != right


def titles_look_duplicate(title_a: str, title_b: str) -> bool:
    """两个标题是否近重复(SimHash + 数字否决 + 可插拔二次判重)。"""
    tokens_a = tokenize_title(title_a)
    tokens_b = tokenize_title(title_b)
    if len(tokens_a) < MIN_TOKENS_FOR_FUZZY or len(tokens_b) < MIN_TOKENS_FOR_FUZZY:
        return False

    distance = hamming_distance(simhash64(title_a), simhash64(title_b))
    if distance <= SIMHASH_DUPLICATE_THRESHOLD:
        return True
    if distance <= GRAY_ZONE_THRESHOLD:
        # 修复 P2-3:灰区里"只差一个数字/月份"的金融数据快讯(距离多在 4~6)
        # 交给 embedding 判官几乎必然被判成重复。先做一道数字/日期差异否决,
        # 数字集不同即判为【不重复】,不再询问二次判官。
        if numbers_contradict(title_a, title_b):
            return False
        return get_secondary_judge().is_duplicate(title_a, title_b) is True
    return False
