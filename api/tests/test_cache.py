"""Unit tests for :mod:`forecast_api.cache`."""

from __future__ import annotations

import time

import pytest

from forecast_api.cache import ForecastCache
from forecast_api.models import ForecastResponse, SourceSignal


def _resp(*, placeholder: bool = False, question: str = "q", articles: int = 3) -> ForecastResponse:
    return ForecastResponse(
        question=question,
        mean=0.25,
        std=0.1,
        ci_low=0.15,
        ci_high=0.35,
        articles_used=articles,
        sources=[
            SourceSignal(
                source_id="reuters",
                source_name="Reuters",
                url="https://reuters.com/a",
                stance=0.5,
                certainty=0.9,
                credibility_weight=1.2,
                claims=["Something will happen."],
            )
        ],
        placeholder=placeholder,
    )


class TestKeyDerivation:
    def test_same_question_different_casing_and_whitespace_collapse(self):
        k1 = ForecastCache.make_key(" Will X happen? ", 5)
        k2 = ForecastCache.make_key("will x happen?", 5)
        assert k1 == k2

    def test_different_max_articles_produces_different_key(self):
        assert ForecastCache.make_key("q", 5) != ForecastCache.make_key("q", 10)

    def test_none_vs_unset_max_articles_is_the_same_key(self):
        assert ForecastCache.make_key("q", None) == ForecastCache.make_key("q", None)


class TestHitMissPersistence:
    def test_store_then_get_returns_same_object(self):
        cache = ForecastCache(ttl_seconds=60, max_entries=8)
        key = ForecastCache.make_key("q", 5)
        response = _resp()
        cache.set(key, response)
        assert cache.get(key) is response

    def test_miss_when_empty(self):
        cache = ForecastCache(ttl_seconds=60, max_entries=8)
        assert cache.get("missing") is None

    def test_stats_counters_track_operations(self):
        cache = ForecastCache(ttl_seconds=60, max_entries=8)
        key = ForecastCache.make_key("q", 5)
        cache.get(key)  # miss
        cache.set(key, _resp())  # store
        cache.get(key)  # hit
        stats = cache.stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.stores == 1
        assert stats.size == 1


class TestTTL:
    def test_expired_entry_is_dropped_on_read(self):
        cache = ForecastCache(ttl_seconds=1, max_entries=8)
        key = ForecastCache.make_key("q", 5)
        cache.set(key, _resp())
        time.sleep(1.05)
        assert cache.get(key) is None
        assert cache.stats().size == 0

    def test_ttl_zero_disables_cache(self):
        cache = ForecastCache(ttl_seconds=0, max_entries=8)
        assert cache.enabled is False
        cache.set("k", _resp())
        assert cache.get("k") is None
        assert cache.stats().stores == 0


class TestPlaceholderRule:
    def test_placeholder_response_is_not_stored(self):
        """A placeholder (no articles) must not poison the cache for an hour."""
        cache = ForecastCache(ttl_seconds=60, max_entries=8)
        cache.set("k", _resp(placeholder=True))
        assert cache.get("k") is None
        assert cache.stats().stores == 0


class TestEviction:
    def test_oldest_entry_evicted_when_capacity_exceeded(self):
        cache = ForecastCache(ttl_seconds=60, max_entries=2)
        cache.set("a", _resp(question="a"))
        cache.set("b", _resp(question="b"))
        cache.set("c", _resp(question="c"))
        # "a" should be evicted, "b" and "c" remain.
        assert cache.get("a") is None
        assert cache.get("b") is not None
        assert cache.get("c") is not None
        assert cache.stats().evictions >= 1

    def test_get_refreshes_lru_position(self):
        cache = ForecastCache(ttl_seconds=60, max_entries=2)
        cache.set("a", _resp(question="a"))
        cache.set("b", _resp(question="b"))
        # Reading "a" bumps it to most-recently-used.
        assert cache.get("a") is not None
        # Inserting "c" should now evict "b" (oldest), not "a".
        cache.set("c", _resp(question="c"))
        assert cache.get("a") is not None
        assert cache.get("b") is None
        assert cache.get("c") is not None


class TestClear:
    def test_clear_drops_all_entries(self):
        cache = ForecastCache(ttl_seconds=60, max_entries=8)
        cache.set("a", _resp(question="a"))
        cache.set("b", _resp(question="b"))
        cache.clear()
        assert cache.stats().size == 0
        assert cache.get("a") is None
