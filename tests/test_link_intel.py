"""Tests for browser.link_intel — LinkResolver cache and threading."""

import concurrent.futures
import threading

from browser.link_intel import LinkResolver, CACHE_MAX


class TestLinkResolverCache:
    """Cache hit / miss / eviction behaviour."""

    def _make_resolver(self):
        """Create a LinkResolver with a fake _follow that avoids network I/O."""
        resolver = LinkResolver(blocked_hosts=set())
        # Replace _follow so it never touches the network
        resolver._follow = lambda url: {
            "href": url,
            "final": url,
            "chain": [],
            "redirects": 0,
            "trackers": [],
            "tracking_params": [],
            "shortener": False,
        }
        return resolver

    def test_cache_hit_returns_from_cache(self):
        """Resolve same URL twice; second call should return cached result
        synchronously (callback invoked immediately, no thread spawn)."""
        resolver = self._make_resolver()
        results = []
        event = threading.Event()

        def cb(result):
            results.append(result)
            event.set()

        # First resolve — goes through _worker
        resolver.resolve("https://example.com", cb)
        event.wait(timeout=5)
        assert len(results) == 1
        assert results[0]["href"] == "https://example.com"

        # Second resolve — should hit cache (callback fires synchronously)
        event.clear()
        resolver.resolve("https://example.com", cb)
        # No need to wait — cache hit calls callback inline
        assert len(results) == 2
        assert results[1]["href"] == "https://example.com"

    def test_cache_eviction_removes_oldest_quarter(self):
        """When cache reaches CACHE_MAX, the oldest 25% entries are evicted."""
        resolver = self._make_resolver()

        # Manually fill the cache to capacity
        for i in range(CACHE_MAX):
            url = f"https://example.com/{i}"
            resolver._cache[url] = {"href": url, "final": url}

        assert len(resolver._cache) == CACHE_MAX

        # Trigger _worker which checks capacity and evicts before inserting
        event = threading.Event()
        resolver._worker("https://example.com/new", lambda r: event.set())
        event.wait(timeout=5)

        # After eviction of CACHE_MAX // 4 entries + insertion of 1
        expected_size = CACHE_MAX - (CACHE_MAX // 4) + 1
        assert len(resolver._cache) == expected_size

        # The first CACHE_MAX // 4 entries should be gone
        evicted_count = CACHE_MAX // 4
        for i in range(evicted_count):
            assert f"https://example.com/{i}" not in resolver._cache

        # Later entries should survive
        assert f"https://example.com/{CACHE_MAX - 1}" in resolver._cache

        # The new entry should be present
        assert "https://example.com/new" in resolver._cache

    def test_executor_attribute_exists(self):
        """LinkResolver must use a ThreadPoolExecutor stored as _executor."""
        resolver = LinkResolver()
        assert hasattr(resolver, "_executor")
        assert isinstance(resolver._executor, concurrent.futures.ThreadPoolExecutor)
