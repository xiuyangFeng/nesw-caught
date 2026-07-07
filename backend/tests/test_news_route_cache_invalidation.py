"""Regression tests: news route caches must be invalidated via the active event bus.

Previously the cache-clearing handlers were subscribed at module import time on
the initial event bus singleton, which app.main lifespan then replaced with a
new instance -- so invalidation never fired and only the TTL applied.

The route caches are disabled suite-wide (conftest sets ROUTE_CACHE_ENABLED=false),
so these tests explicitly re-enable the two module-level cache instances and
assert on real cache-hit semantics: after an invalidating event is published,
previously cached values must no longer be served.
"""

from __future__ import annotations

import pytest

import app.services.event_bus as event_bus_module
from app.api.routes import news as news_routes
from app.services.event_bus import HybridEventBus

_LAYOUT_KEY = ("hk", 6, 6, 24)
_RUNTIME_KEY = "runtime"


@pytest.fixture(autouse=True)
def enable_route_caches():
    caches = (news_routes._feed_layout_cache, news_routes._runtime_cache)
    previous = [cache.enabled for cache in caches]
    for cache in caches:
        cache.enabled = True
        cache.clear()
    yield
    for cache, was_enabled in zip(caches, previous):
        cache.enabled = was_enabled
        cache.clear()


def _fill_caches() -> None:
    news_routes._feed_layout_cache.set(_LAYOUT_KEY, "layout-view")
    news_routes._runtime_cache.set(_RUNTIME_KEY, "runtime-view")


def _assert_caches_hit() -> None:
    assert news_routes._feed_layout_cache.get(_LAYOUT_KEY) == "layout-view"
    assert news_routes._runtime_cache.get(_RUNTIME_KEY) == "runtime-view"


def _assert_caches_miss() -> None:
    assert news_routes._feed_layout_cache.get(_LAYOUT_KEY) is None
    assert news_routes._runtime_cache.get(_RUNTIME_KEY) is None


@pytest.mark.parametrize(
    "event_name",
    ["news.signals_processed", "news.created_batch", "news.updated"],
)
def test_publish_clears_route_caches(event_name):
    bus = HybridEventBus(backend="memory")
    news_routes.register_cache_invalidation(bus)

    _fill_caches()
    _assert_caches_hit()

    bus.publish(event_name, {"news_ids": []})

    _assert_caches_miss()


def test_register_event_handlers_wires_invalidation_on_active_singleton(monkeypatch):
    """The bus installed by app.main._register_event_handlers (the one all
    publishers use afterwards) must carry the cache invalidation handlers."""
    from app import main as app_main

    old_bus = event_bus_module._instance
    monkeypatch.setattr(app_main, "build_event_bus", lambda: HybridEventBus(backend="memory"))
    try:
        app_main._register_event_handlers()

        _fill_caches()
        _assert_caches_hit()

        event_bus_module.get_event_bus().publish("news.created_batch", {"news_ids": []})

        _assert_caches_miss()
    finally:
        event_bus_module._instance = old_bus
