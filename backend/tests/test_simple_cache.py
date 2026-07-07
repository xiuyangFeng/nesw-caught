"""Direct unit tests for the real SimpleTTLCache code paths (hit, TTL expiry,
disabled mode, clear) -- previously untestable because get() was hard-disabled
whenever pytest was running."""

import time

from app.core.simple_cache import SimpleTTLCache


def test_cache_hit_within_ttl():
    cache = SimpleTTLCache(ttl=60.0, enabled=True)
    cache.set("key", "value")
    assert cache.get("key") == "value"
    # A second read still hits (no read-through eviction)
    assert cache.get("key") == "value"


def test_cache_miss_for_unknown_key():
    cache = SimpleTTLCache(ttl=60.0, enabled=True)
    assert cache.get("missing") is None


def test_cache_entry_expires_after_ttl(monkeypatch):
    cache = SimpleTTLCache(ttl=10.0, enabled=True)
    now = time.time()
    monkeypatch.setattr("app.core.simple_cache.time.time", lambda: now)
    cache.set("key", "value")
    assert cache.get("key") == "value"

    # Advance the clock beyond the TTL: entry must expire and be evicted
    monkeypatch.setattr("app.core.simple_cache.time.time", lambda: now + 10.1)
    assert cache.get("key") is None
    assert "key" not in cache._cache


def test_disabled_cache_never_stores_nor_hits():
    cache = SimpleTTLCache(ttl=60.0, enabled=False)
    cache.set("key", "value")
    assert cache.get("key") is None
    assert not cache._cache


def test_clear_empties_cache():
    cache = SimpleTTLCache(ttl=60.0, enabled=True)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None
    assert not cache._cache
